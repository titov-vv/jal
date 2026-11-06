import importlib   # it is used for delayed import in order to avoid circular reference in child classes
import logging
from decimal import Decimal
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication

from jal.constants import PredefinedAsset, Setup
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.category import JalCategory
from jal.db.db import JalDB
from jal.db.helpers import is_day_marker
from jal.db.lots import LedgerLotStore, ScratchLotStore, replay
from jal.db.basis_policy import Basis, Clock, Treatment, BasisPolicy, JalPolicy
from jal.db.symbol import JalSymbol
from jal.db.operations import LedgerTransaction, LedgerError, TaxStatus, AssetPayment, AssetIncome, Transfer
from jal.db.clock import ZONE_SPAN, wall_clock_reading
from jal.db.country import JalCountry
from jal.db.residence import JalResidence
from jal.db.tax_override import JalTaxOverride, TaxOverride
from jal.data_export.tax_parameters import TaxParameters, TAX_TREATY

REPORT_METHOD = 0
REPORT_TEMPLATE = 1
RATES_GAP = 14 * 86400   # how much older than its date a rate may be before it is warned of (holidays differ)
ESTIMATE = 'tax2pay'     # the field of a row that holds a base estimation of the tax
GAIN = 'gain'            # kinds of tax base: capital gains (cost, disposal, profit) and income (gross amount)
INCOME = 'income'


# Raised when a report can't be produced as asked; 'missing' lists (symbol, timestamp) of every quote that stopped it,
# 'no_country' the names of assets whose country a row needed and didn't find, 'replay' why the lot replay stopped
class TaxReportStop(Exception):
    def __init__(self, missing: list, no_country: list = None, replay: str = ''):
        super().__init__("Tax report stopped by missing data")
        self.missing = missing
        self.no_country = no_country or []
        self.replay = replay


# Raised when the user stops a report while it runs
class TaxReportCancelled(Exception):
    pass


# The market value of a corporate action result in the account currency, estimated per received share as the higher
# of the old shares' last non-zero quote before the action times their cost share and the new shares' first non-zero
# quote after it; None without either quote
def exchange_estimate(action, result: dict):
    currency_id = action.account().currency()
    asset = JalSymbol(result['symbol_id']).asset()
    qty = abs(Decimal(result['qty']))
    before = [q for _, q in action.asset().quotes(0, action.timestamp() - 1, currency_id) if q]
    after = [q for _, q in asset.quotes(action.timestamp() + 1, Setup.MAX_TIMESTAMP, currency_id) if q]
    prices = ([before[-1] * Decimal(result['value_share']) * abs(action.qty()) / qty] if before else []) + after[:1]
    return max(prices) * qty if prices else None


# The jurisdiction's policy with the user's decisions on top: 'not a tax event' carries an exchange with its date,
# 'a tax event' disposes of it at market value, a price per received share disposes of a corporate action at it.
# 'applied(operation, kind)' hears of each decision used, 'missing_quote(symbol, timestamp)' of a value not found.
class DecidedPolicy(BasisPolicy):
    def __init__(self, policy, overrides: dict, applied, missing_quote):
        self._policy = policy
        self._overrides = overrides
        self._applied = applied
        self._missing_quote = missing_quote

    def _decision(self, operation):
        for kind in (TaxOverride.NotTaxEvent, TaxOverride.TaxEvent, TaxOverride.PricePerShare):
            if (operation.id(), kind) in self._overrides:
                self._applied(operation, kind)
                return kind, self._overrides[(operation.id(), kind)][0]
        return None, None

    def treatment(self, operation) -> Treatment:
        kind, _ = self._decision(operation)
        if kind == TaxOverride.NotTaxEvent:
            return Treatment(Basis.CARRY, Clock.KEEP)
        if kind == TaxOverride.TaxEvent:
            return Treatment(Basis.DISPOSAL, Clock.RESTART)
        return self._policy.treatment(operation)

    def action_result(self, action, result: dict) -> Treatment:
        treatment = self._policy.action_result(action, result)
        if result not in TaxOverride.exchange_results(action):
            return treatment
        kind, value = self._decision(action)
        if kind == TaxOverride.NotTaxEvent:
            return Treatment(Basis.CARRY, Clock.KEEP, treatment.share)
        if kind == TaxOverride.PricePerShare:
            return Treatment(Basis.DISPOSAL, Clock.RESTART, treatment.share,
                             TaxOverride.price(value) * abs(Decimal(result['qty'])))
        if kind == TaxOverride.TaxEvent and treatment.basis != Basis.DISPOSAL:
            value = exchange_estimate(action, result)
            if value is None:
                self._missing_quote(JalSymbol(result['symbol_id']).symbol(), action.timestamp())
                return treatment
            return Treatment(Basis.DISPOSAL, Clock.RESTART, treatment.share, value)
        return treatment

    def income_cost(self, income) -> Decimal:
        return self._policy.income_cost(income)

    def order(self, lots: list) -> list:
        return self._policy.order(lots)


class TaxReport:
    # Every jurisdiction a report exists for, keyed by its ISO 3166-1 alpha-2 code; the name is in its own language
    jurisdictions = {
        'pt': {"name": "Portugal", "module": "jal.data_export.tax_reports.portugal", "class": "TaxesPortugal"},
        'ru': {"name": "Россия", "module": "jal.data_export.tax_reports.russia", "class": "TaxesRussia",
               "flow": {"module": "jal.data_export.taxes_flow", "class": "TaxesFlowRus"}}
    }
    jurisdiction = ''   # ISO 3166-1 alpha-2 code of the jurisdiction, names its parameter file
    currency_name = ''  # The name of the currency for tax values calculation
    currency_suffix = ''   # Suffix of the report-currency fields of a row ('_rub', '_eur')
    # The two sections every report has, in its jurisdiction's language: (name, template)
    summary_section = ('', '')
    uncovered_section = ('', '')
    # The jurisdiction's tax bases in report order: (title, GAIN or INCOME, [sections]); then the sections outside
    # every base. Together they list each section of 'reports' once, in the order the sheets are written.
    bases = []
    outside = []
    texts = {}             # Report strings in the jurisdiction's language, see the country classes
    operation_labels = {}  # {(otype, subtype or None): label} in the jurisdiction's language
    # The zone whose wall clock this report counts its days and years on - the one of the jurisdiction the report is
    # filed in. Symmetric to Statement.source_timezone: a report names its own zone the way a statement names its
    # source's. An empty name leaves every stored timestamp read as it is.
    report_timezone = ''
    asset_source_override = False   # True if the report reads TaxOverride.AssetSource
    REPLAY_SHARE = 90               # Percent of the progress the replay takes, the sections the rest

    def __init__(self):
        self._currency_id = JalAsset.find({'symbol': self.currency_name, 'type_id': PredefinedAsset.Money}).id()
        if not self._currency_id:  # Zero value if no currency was found in DB for given currency symbol
            self.reports = {}
            logging.error(self.tr("Currency is not defined: ") + self.currency_name)
            return
        self.account = None           # Account for reporting
        self.account_currency = None  # Currency of the account for reporting
        self.year_begin = 0           # the calendar tax year, read by every year-keyed rule
        self.year_end = 0
        self.period_begin = 0         # the window of the events printed, inside the year
        self.period_end = 0
        self.use_settlement = True
        self.one_currency_rate = False
        self.parameters = None
        self._section = ''
        self.section_notes = {}   # {section: [header lines]} a section states under its title
        self._printed = set()     # (otype, oid) of every operation a section printed
        self._overrides = {}      # The user's decisions for this jurisdiction, see JalTaxOverride.for_jurisdiction()
        self._applied = {}        # {(oid, kind): operation} of every override this report applied
        self._missing = []        # (symbol, timestamp) of every quote a section needed and didn't find
        self._no_country = []     # names of the assets whose country a section needed and didn't find
        self._rates_end = None    # newest official rate into the report currency, read once per report
        self.rates_warnings = {}  # {(pair, date of the rate used): latest date it converted} for rates likely missing
        self.short_warnings = []  # a line for each short of an asset kind whose year-end rule isn't handled
        self._carried = []        # closing operations of stock shorts reported in an earlier year
        self.lots = LedgerLotStore()   # the lot store deals and lots are read from: the replay's while a report runs
        self._progress = None     # progress(percent, text) of a running report, see prepare_tax_report()
        self._cancelled = False

    @staticmethod
    def tr(text):
        return QApplication.translate("TaxReport", text)

    # A moment of an operation as the jurisdiction of this report saw it - the single place where a stored timestamp
    # becomes a date of the report. Everything that is a moment goes through here, both what is printed and what
    # decides which year an operation belongs to. An exchange rate is deliberately not asked for on this clock: the
    # amounts it explains are converted in the ledger, on the stored moment, and a rate taken from a different day
    # would stop being the one those amounts were made of.
    # 'day_only' is what the operation itself says about its timestamp (see LedgerTransaction.timestamp_is_day); the
    # marker check answers for a value that carries no such answer beside it.
    def _moment(self, timestamp: int, day_only: bool = False) -> int:
        if day_only or is_day_marker(timestamp):
            return self._date(timestamp)   # a reading that states a day carries no time of day to re-read
        return wall_clock_reading(timestamp, self.report_timezone)

    # A calendar date of an operation - a settlement day, an ex-date, or a payment whose source gave the day without
    # saying when in it the payment happened, stored as one of the day markers is_day_marker() knows. Such a date
    # carries no time of day to re-read on another clock, and moving it could only turn it into a different date, so
    # it is the same date in every jurisdiction. Named for what it is, so that a date is never mistaken for a moment
    # left unconverted.
    @staticmethod
    def _date(day: int) -> int:
        return day

    # The report class of a jurisdiction, imported on demand as the country modules import this one
    @staticmethod
    def report_class(code: str):
        try:
            report_data = TaxReport.jurisdictions[code]
        except KeyError:
            raise ValueError(f"Jurisdiction '{code}' has no tax report")
        module = importlib.import_module(report_data['module'])
        try:
            return getattr(module, report_data['class'])
        except AttributeError:
            raise ValueError(f"Tax report class '{report_data['class']}' can't be loaded")

    @staticmethod
    def create_report(code: str):
        return TaxReport.report_class(code)()

    # The money-flow report of a jurisdiction that asks for one, None for the others
    @staticmethod
    def create_flow_report(code: str):
        flow = TaxReport.jurisdictions.get(code, {}).get('flow')
        if flow is None:
            return None
        return getattr(importlib.import_module(flow['module']), flow['class'])()

    # True for an account in the jurisdiction's own country, whose income the authority gets reported by the bank
    @staticmethod
    def home_account(account, jurisdiction: str) -> bool:
        return account.country().code() == jurisdiction

    def report_template(self, report_name):
        if report_name == self.summary_section[0]:
            return self.summary_section[1]
        if report_name == self.uncovered_section[0]:
            return self.uncovered_section[1]
        if report_name not in self.reports:
            logging.warning(self.tr("No report template found for section: ") + report_name)
            return ""
        else:
            return self.reports[report_name][REPORT_TEMPLATE]

    # ------------------------------------------------------------------------------------------------------------------
    # Create a totals row from provided list of dictionaries
    # it calculates sum for each field in fields and adds it to return dictionary
    def insert_totals(self, list_of_values, fields):
        if not list_of_values:
            return
        totals = {"report_template": "totals"}
        for field in fields:
            values = [x[field] for x in list_of_values if x.get(field) is not None]
            totals[field] = sum(values) if values else None   # a figure no row has, as a base rate that's missing
        list_of_values.append(totals)

    # 'period' is a half-open (begin, end) inside the year, the whole year if None
    def prepare_tax_report(self, year: int, account_id: int, period=None, **kwargs) -> dict:
        tax_report = {}
        self.account = JalAccount(account_id)
        self.account_currency = JalAsset(self.account.currency())
        self.year_begin, self.year_end = self.year_window(year)
        self.period_begin, self.period_end = (self.year_begin, self.year_end) if period is None else period
        if not self.year_begin <= self.period_begin < self.period_end <= self.year_end:
            raise ValueError(f"Tax report period {self.period_begin}-{self.period_end} is outside the year {year}")
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']
        if 'use_one_currency_rate' in kwargs:
            self.one_currency_rate = kwargs['use_one_currency_rate']
        if 'generate_modelo3' in kwargs:
            self.generate_modelo3 = kwargs['generate_modelo3']
        self.parameters = TaxParameters(self.jurisdiction, year)
        if self.parameters.value(TAX_TREATY) is None:
            logging.warning(self.tr("There are no parameters found for tax report year: ") + str(year))
        self.section_notes, self._printed, self._missing, self._no_country = {}, set(), [], []
        self._overrides, self._applied = JalTaxOverride.for_jurisdiction(self.jurisdiction), {}
        self._rates_end, self.rates_warnings = None, {}
        self.short_warnings, self._carried = [], []
        self._progress = kwargs.get('progress')
        self._cancelled = False
        self.lots = ScratchLotStore()
        try:
            self._replay()
            for piece in self.year_end_shorts():
                if piece['open'].asset().type() not in self.SHORT_HANDLED:
                    self._warn_short(piece['open'].asset(), piece['open'])
            sections = {}
            for i, report in enumerate(self.reports):
                self._show_progress(self.REPLAY_SHARE + (100 - self.REPLAY_SHARE) * i / len(self.reports),
                                    f"{report}: %p%")
                self._section = report
                sections[report] = self.reports[report][REPORT_METHOD]()
            if self._missing or self._no_country:
                raise TaxReportStop(self._missing, self._no_country)
            skipped, uncovered = self._not_covered()
            tax_report[self.summary_section[0]] = self.prepare_summary(sections, skipped, uncovered)
            tax_report.update(sections)
            tax_report[self.uncovered_section[0]] = self.prepare_not_covered(skipped, uncovered)
        finally:
            self.lots.detach()
            self.lots = LedgerLotStore()
        return tax_report

    # The lots of the whole history replayed into the report's store by its jurisdiction's policy: the buy-backs of
    # the year's shorts come after the year, and lots arrive from other accounts
    def _replay(self):
        text = self.tr("Tax replay") + f" ({self.jurisdiction.upper()}): %p%"
        shown = [None]

        def progress(done: int, total: int):
            percent = self.REPLAY_SHARE * done // total
            if percent != shown[0]:
                shown[0] = percent
                self._show_progress(percent, text)

        try:
            policy = DecidedPolicy(self.basis_policy(), self._overrides, self._decided, self.missing_quote)
            replay(self.lots, policy, progress=progress if self._progress is not None else None)
        except LedgerError as e:
            raise TaxReportStop([], replay=str(e))

    # Reports the progress; a stop asked for meanwhile ends the report here, as the events are processed in 'progress'
    # A decision the replay used: listed with the others the report applied
    def _decided(self, operation, kind: int):
        self._applied[(operation.id(), kind)] = operation

    # The BasisPolicy the report replays the lots by: the jurisdiction's rules where they differ from JAL's
    def basis_policy(self):
        return JalPolicy()

    def _show_progress(self, percent: float, text: str):
        if self._progress is not None:
            self._progress(percent, text)
        if self._cancelled:
            raise TaxReportCancelled()

    # Stops the running report at its next progress step
    def cancel(self):
        self._cancelled = True

    # A line the section being prepared states under its title - the treatment it assumed
    def add_header(self, line: str):
        lines = self.section_notes.setdefault(self._section, [])
        if line not in lines:
            lines.append(line)

    def section_headers(self, section: str) -> list:
        return self.section_notes.get(section, [])

    # Records that a section printed this operation, so that it isn't listed as not covered
    def mark_printed(self, operation):
        if operation is not None:
            self._printed.add((operation.type(), operation.id()))

    def mark_printed_id(self, otype: int, oid: int):
        self._printed.add((otype, oid))

    # True if the user decided the operation is not a tax event in this jurisdiction; the section then leaves it out
    def excluded(self, operation) -> bool:
        if operation is None or (operation.id(), TaxOverride.NotTaxEvent) not in self._overrides:
            return False
        self._applied[(operation.id(), TaxOverride.NotTaxEvent)] = operation
        return True

    def excluded_id(self, otype: int, oid: int) -> bool:
        if (oid, TaxOverride.NotTaxEvent) not in self._overrides:
            return False
        return self.excluded(LedgerTransaction.get_operation(otype, oid))

    # The official rate of a currency into the report's one: the direct pair only, as its source is the jurisdiction's
    # (CBR for RUB, ECB for EUR) and a cross-rate would mix in another. A missing rate stops the report.
    def rate(self, currency_id: int, timestamp: int) -> Decimal:
        if currency_id == self._currency_id:
            return Decimal('1')
        quoted, rate = JalAsset(currency_id).quote(timestamp, self._currency_id, report_missing=False, direct_only=True)
        if not quoted:
            self.missing_quote(f"{JalAsset(currency_id).symbol()}/{self.currency_name}", timestamp)
        elif timestamp - quoted > RATES_GAP and self._rate_missing(currency_id, quoted, timestamp):
            key = (f"{JalAsset(currency_id).symbol()}/{self.currency_name}", quoted)
            self.rates_warnings[key] = max(self.rates_warnings.get(key, 0), timestamp)
        return rate

    # A rate older than its date is right if the bank froze it - it publishes no later one of that pair while its
    # other rates go on (the ECB's RUB since 1 Mar 2022). It is likely missing if the same pair has a later rate (a
    # hole in the series), or if no rate of the bank reaches the date (the rates were not downloaded).
    def _rate_missing(self, currency_id: int, quoted: int, timestamp: int) -> bool:
        later = JalDB._read("SELECT COUNT(*) FROM quotes WHERE asset_id=:asset AND currency_id=:currency "
                            "AND timestamp>:quoted", [(":asset", currency_id), (":currency", self._currency_id),
                                                       (":quoted", quoted)])
        return bool(later) or timestamp > self.rates_end() + RATES_GAP

    # The newest official rate the database holds into the report currency, of any currency
    def rates_end(self) -> int:
        if self._rates_end is None:
            self._rates_end = JalDB._read("SELECT MAX(q.timestamp) FROM quotes AS q JOIN assets AS a ON a.id=q.asset_id "
                                          "WHERE q.currency_id=:currency AND a.type_id=:money",
                                          [(":currency", self._currency_id), (":money", PredefinedAsset.Money)]) or 0
        return self._rates_end

    # Records a quote a section needed and didn't find; the report stops after all sections listed theirs
    def missing_quote(self, symbol: str, timestamp: int):
        if (symbol, timestamp) not in self._missing:
            self._missing.append((symbol, timestamp))

    # Records an asset whose country a section needed and didn't find; the report stops after all sections ran
    def missing_country(self, name: str):
        if name not in self._no_country:
            self._no_country.append(name)

    # The operations that changed this deal's lot: the purchase's modifiers that wrote it as the deal's asset, less a
    # swap or wrapping that only rewrote what stayed behind when it took another part of the purchase elsewhere
    def deal_modifiers(self, deal) -> list:
        modifiers = []
        for otype, oid in self.lots.lot_modifiers(deal.open_operation().type(), deal.open_operation().id(),
                                                  deal.asset().id()):
            operation = LedgerTransaction.get_operation(otype, oid, Transfer.Outgoing)
            if operation.type() in (LedgerTransaction.Swap, LedgerTransaction.Conversion) \
                    and operation.in_asset().id() != deal.asset().id():
                continue
            modifiers.append(operation)
        return modifiers

    # Why the jurisdiction's rule takes this operation out of the report, None if it doesn't
    def skip_reason(self, operation):
        if operation.type() == LedgerTransaction.AssetIncome and operation.subtype() == AssetIncome.TokenRentReturn:
            return self.texts['rent_return']
        return None

    # Every taxable or base-impacting operation of the account in the report's period that no section printed:
    # returns ({reason: count} of those the jurisdiction skips, [operations] no section claimed)
    def _not_covered(self):
        skipped, uncovered = {}, []
        query = JalDB._exec("SELECT o.otype, o.id FROM ledger_sequence AS s JOIN operations AS o ON o.id=s.operation_id "
                            "WHERE s.account_id=:account AND s.timestamp>=:begin AND s.timestamp<:end "
                            "GROUP BY o.id ORDER BY MIN(s.seq_no)",
                            [(":account", self.account.id()), (":begin", self.period_begin - ZONE_SPAN),
                             (":end", self.period_end + ZONE_SPAN)])
        while query.next():
            otype, oid = query.value(0), query.value(1)
            if (otype, oid) in self._printed:
                continue
            operation = LedgerTransaction.get_operation(otype, oid)
            if operation.account().id() != self.account.id() or operation.taxable() == TaxStatus.NotTaxable:
                continue
            if not self.in_period(self.operation_date(operation)):
                continue
            if self.excluded(operation):
                continue
            reason = self.skip_reason(operation)
            if reason is None:
                uncovered.append(operation)
            else:
                skipped[reason] = skipped.get(reason, 0) + 1
        return skipped, uncovered

    def operation_label(self, operation) -> str:
        key = (operation.type(), operation.subtype())
        if key in self.operation_labels:
            return self.operation_labels[key]
        return self.operation_labels.get((operation.type(), None), operation.name())

    def prepare_not_covered(self, skipped: dict, uncovered: list) -> list:
        rows = [{'report_template': "skipped", 'reason': reason, 'count': self.texts['skipped_count'].format(count)}
                for reason, count in skipped.items()]
        for operation in uncovered:
            rows.append(self._operation_row(operation, self.texts['uncovered']))
        for operation, year in self._carried:
            rows.append(self._operation_row(operation, self.texts['short_carried'].format(year=year)))
        for (oid, kind), operation in self._applied.items():   # the replay applies those of every account and year
            if kind == TaxOverride.NotTaxEvent and operation.account().id() == self.account.id() \
                    and self.in_period(self.operation_date(operation)):
                rows.append(self._operation_row(operation, self.texts['excluded'].format(self._overrides[(oid, kind)][1])))
        return rows

    def _operation_row(self, operation, reason: str) -> dict:
        return {'report_template': "operation", 'date': self.operation_date(operation),
                'operation': self.operation_label(operation), 'symbol': operation.symbol().symbol(),
                'number': operation.number(), 'description': operation.description(), 'reason': reason}

    # Each base with its sections and its total, then the sections outside every base, listed and not totalled; then
    # the counts of what is not covered
    def prepare_summary(self, sections: dict, skipped: dict, uncovered: list) -> list:
        rows = []
        totals = {}   # {base title: {figure: amount}}
        for title, kind, names in self.bases:
            rows.append({'report_template': "base", 'title': title})
            base = {}
            for name in names:
                figures = self._section_figures(sections[name])
                if kind == INCOME:   # gross income, whichever field the section keeps it in
                    figures = {'gross': x for x in figures.values()}
                rows += self._section_rows(name, sections[name], figures)
                for figure, amount in figures.items():
                    base[figure] = base.get(figure, Decimal('0')) + amount
            rows += [{'report_template': "base_total", 'figure': f"{self.texts['base_total']}: {self.texts[x]}",
                      'amount': base[x]} for x in base]   # none for a base whose sections are all empty
            totals[title] = base
        rows += self.base_sum_rows(sections, totals)
        rows.append({'report_template': "base", 'title': self.texts['outside']})
        for name in self.outside:
            rows += self._section_rows(name, sections[name], self._section_figures(sections[name]))
        for label, count in ((self.texts['skipped_total'], sum(skipped.values()) + len(self._carried)),
                             (self.texts['uncovered_total'], len(uncovered))):
            link = self.uncovered_section[0] if count else ''   # an empty section makes no sheet to link to
            rows.append({'report_template': "count", 'label': label, 'count': count, 'link': link})
        rows += self._estimate_rows(sections, totals)
        day = lambda x: datetime.fromtimestamp(x, tz=timezone.utc).strftime('%d.%m.%Y')
        if self.parameters.value(TAX_TREATY) is None:
            rows.append({'report_template': "warning", 'warning': self.texts['parameters_missing'].format(
                year=datetime.fromtimestamp(self.year_begin, tz=timezone.utc).year)})
        elif self.parameters.unreviewed():
            rows.append({'report_template': "warning", 'warning': self.texts['parameters_unreviewed'].format(
                year=datetime.fromtimestamp(self.year_begin, tz=timezone.utc).year,
                reviewed=self.parameters.reviewed_through())})
        rows += [{'report_template': "warning", 'warning': x} for x in self.short_warnings]
        for (pair, quoted), latest in sorted(self.rates_warnings.items()):
            rows.append({'report_template': "warning",
                         'warning': self.texts['rates_missing'].format(pair=pair, rate=day(quoted), latest=day(latest))})
        rows += self._decision_rows()
        return rows

    GAIN_FIGURES = ('spending', 'income', 'profit')   # acquisition cost, disposal value, profit / loss

    # The figures a section adds to its base, in the report's currency: those of a deal if it has them, else its amount
    def _section_figures(self, section: list) -> dict:
        totals = [x for x in section if x['report_template'] == "totals"]
        if not totals:
            return {}
        values = {k[:-len(self.currency_suffix)]: v for k, v in totals[0].items()
                  if k.endswith(self.currency_suffix) and not k.startswith('tax') and v is not None}
        if 'profit' in values:
            return {x: values[x] for x in self.GAIN_FIGURES if x in values}
        for figure in ('amount', 'value'):
            if figure in values:
                return {figure: values[figure]}
        return {}

    def _section_rows(self, name: str, section: list, figures: dict) -> list:
        rows = [{'report_template': "section", 'section': name,
                 'rows': len([x for x in section if x['report_template'] != "totals"])}]
        return rows + [{'report_template': "figure", 'figure': self.texts[x], 'amount': v} for x, v in figures.items()]

    # Lines the jurisdiction adds after its bases; 'totals' is {base title: {figure: amount}}
    def base_sum_rows(self, sections: dict, totals: dict) -> list:
        return []

    # The base estimation of each base and section that has one, and their sum when there are several: a gain base on
    # its profit at the capital gain rate, a loss as zero; any other section on the estimates of its rows
    def _estimate_rows(self, sections: dict, totals: dict) -> list:
        estimates = []
        for title, kind, names in self.bases:
            if kind == GAIN:
                estimates += self._gain_estimate(title, totals[title])
            else:
                estimates += [x for name in names for x in self._section_estimate(name, sections[name])]
        estimates += [x for name in self.outside for x in self._section_estimate(name, sections[name])]
        if not estimates:
            return []
        if len(estimates) > 1:
            estimates.append({'report_template': "estimate", 'label': self.texts['estimate_total'],
                              'amount': sum(x['amount'] for x in estimates)})
        return [{'report_template': "estimates", 'title': self.texts['estimates']}] + estimates

    def _gain_estimate(self, title: str, figures: dict) -> list:
        if 'profit' not in figures:
            return []
        amount = self.base_estimate(TaxParameters.CAPITAL_GAIN, max(figures['profit'], Decimal('0')))
        if amount is None:
            return []
        rate = format((self.parameters.rate(TaxParameters.CAPITAL_GAIN) * 100).normalize(), 'f')
        return [{'report_template': "estimate", 'label': self.texts['estimate_gain'].format(base=title, rate=rate),
                 'amount': round(amount, 2)}]

    @staticmethod
    def _section_estimate(name: str, section: list) -> list:
        totals = [x for x in section if x['report_template'] == "totals"]
        if totals and totals[0].get(ESTIMATE) is not None:
            return [{'report_template': "estimate", 'label': name, 'amount': totals[0][ESTIMATE]}]
        return []

    # The overrides this report applied: a title line, then one line per operation and kind, oldest first
    def _decision_rows(self) -> list:
        if not self._applied:
            return []
        rows = [{'report_template': "decisions", 'title': self.texts['decisions']}]
        day = lambda x: datetime.fromtimestamp(x, tz=timezone.utc).strftime('%d.%m.%Y')
        texts = {(TaxOverride.NotTaxEvent, ''): 'override_excluded',
                 (TaxOverride.Treaty, TaxOverride.TreatyApplies): 'override_treaty',
                 (TaxOverride.Treaty, TaxOverride.NoTreaty): 'override_no_treaty',
                 (TaxOverride.AssetSource, TaxOverride.AssetCountry): 'override_asset_source',
                 (TaxOverride.TaxEvent, ''): 'override_tax_event'}
        for (oid, kind), operation in sorted(self._applied.items(), key=lambda x: (x[1].timestamp(), x[0])):
            value, note = self._overrides[(oid, kind)]
            if kind == TaxOverride.PricePerShare:
                decision = self.texts['override_price'].format(value)
            else:
                decision = self.texts[texts[(kind, value)]]
            rows.append({'report_template': "decision",
                         'operation': f"{day(self.operation_date(operation))} {self.operation_label(operation)} "
                                      f"{operation.symbol().symbol()}".strip(),
                         'decision': f"{decision}: {note}"})
        return rows

    # The base rate of an income kind (TaxParameters.DIVIDEND, ...) times 'base', None if the year has no such rate
    def base_estimate(self, kind: str, base: Decimal):
        rate = self.parameters.rate(kind)
        return None if rate is None else rate * base

    # The form codes of a kind of row (TaxParameters.STOCK, ...) as (income, expense); none for an account of the
    # jurisdiction's own country, whose income the authority gets pre-filled
    def code(self, kind: str) -> tuple:
        if self.home_account(self.account, self.jurisdiction):
            return '', ''
        codes = self.parameters.code(kind)
        return ('', '') if codes is None else codes

    # The fields a row of the kind carries: its codes as printed, and the kind itself for the form exports, which read
    # the codes from the parameters (a home account's rows are exported too)
    def coded(self, kind: str) -> dict:
        return {'code': self.code_text(kind), 'kind': kind}

    # The codes of a kind of row as printed: "income / expense", or the income code alone; the section being prepared
    # states why when the account's own country leaves them out
    def code_text(self, kind: str) -> str:
        if self.home_account(self.account, self.jurisdiction):
            self.add_header(self.texts['home_codes'])
        income, expense = self.code(kind)
        return f"{income} / {expense}" if expense else income

    # States under the section's title how its base estimation was made, if any of its rows has one
    def add_estimate_header(self, rows: list, text: str, kind: str):
        if any(x.get(ESTIMATE) is not None for x in rows):
            self.add_header(text.format(rate=format((self.parameters.rate(kind) * 100).normalize(), 'f')))

    # True if a tax treaty with the country covers the operation: the user's decision on it first, then the parameters
    def has_tax_treaty_with(self, country_code: str, operation) -> bool:
        key = (operation.id(), TaxOverride.Treaty)
        if key in self._overrides:
            self._applied[key] = operation
            return self._overrides[key][0] == TaxOverride.TreatyApplies
        return self.parameters.treaty_with(country_code)

    # True if the user decided the operation's income comes from its asset and the asset's country
    def asset_source(self, operation) -> bool:
        key = (operation.id(), TaxOverride.AssetSource)
        if key not in self._overrides:
            return False
        self._applied[key] = operation
        return True

    # Returns a list of dividends that should be included into the report for given period, less those the user excluded
    def dividends_list(self) -> list:
        dividends = AssetPayment.get_list(self.account.id(), subtype=AssetPayment.Dividend)
        dividends += AssetIncome.get_list(self.account.id(), subtype=AssetIncome.StockDividend)
        dividends += AssetIncome.get_list(self.account.id(), subtype=AssetIncome.StockVesting)
        dividends = [x for x in dividends if self.in_period(self._moment(x.timestamp()))]
        return [x for x in dividends if not self.excluded(x)]

    # Returns operations of the given category that belong to the report's period. The database is asked for a wider
    # window than the period, because an operation stamped just outside it may well be inside it on the report's clock;
    # what is inside is then decided on that clock alone.
    def category_operations(self, category_id: int) -> list:
        operations = JalCategory(category_id).get_operations(self.period_begin - ZONE_SPAN, self.period_end + ZONE_SPAN)
        return [x for x in operations if self.in_period(self._moment(x.timestamp()))]

    # The day that puts a trade into a year: its settlement, or its trade date where the source gave no settlement.
    # A jurisdiction that reads the trade date overrides this.
    def trade_date(self, operation) -> int:
        return self.settlement_date(operation)

    # The day that puts a deal into a year - that of its closing operation
    def deal_date(self, deal) -> int:
        return self.trade_date(deal.close_operation())

    # The day that puts an operation into a year: a trade's by the jurisdiction's rule, any other its own moment
    def operation_date(self, operation) -> int:
        if operation.type() == LedgerTransaction.Trade:
            return self.trade_date(operation)
        return self._moment(operation.timestamp(), operation.timestamp_is_day())

    # The settlement of an operation, 0 for a kind that has none (an income in kind)
    @staticmethod
    def _settlement(operation) -> int:
        return operation.settlement() if hasattr(operation, 'settlement') else 0

    # The moment a leg's rate is read at: its settlement, or its trade moment when asked for or when there is none
    @staticmethod
    def rate_moment(operation, no_settlement: bool = False) -> int:
        settlement = TaxReport._settlement(operation)
        return operation.timestamp() if no_settlement or not settlement else settlement

    # The settlement day printed for a leg, its trade date where the source gave none
    def settlement_date(self, operation) -> int:
        settlement = self._settlement(operation)
        if settlement:
            return self._date(settlement)
        return self._moment(operation.timestamp(), operation.timestamp_is_day())

    # The year as a half-open window [begin, end): 'end' is the FIRST second of the next year, so an operation stamped
    # at midnight on 1 January belongs to that next year and to no other.
    @staticmethod
    def year_window(year: int) -> tuple:
        return (int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()),
                int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp()))

    # The half-open spans of the year in which the residence table puts the user in the jurisdiction's country
    def resident_spans(self, year: int) -> list:
        country_id = JalCountry(data={'code': self.jurisdiction}, search=True).id()
        begin, end = self.year_window(year)
        spans = []
        for since, until, country in JalResidence.spans():
            since, until = max(since, begin), end if until is None else min(until, end)
            if country == country_id and since < until:
                spans.append((since, until))
        return spans

    # The half-open periods of the year the jurisdiction holds the user resident in, by its own rule from the
    # residence table; None if the jurisdiction derives none
    def resident_periods(self, year: int):
        return None

    def in_period(self, timestamp: int) -> bool:
        return self.period_begin <= timestamp < self.period_end

    # Closed deals of the asset types in the report's period, less those the user excluded and the stock shorts reported
    # in the year of their sale (listed on "Not covered"); 'close_otypes' as in JalAccount.closed_trades_list()
    def trades_list(self, asset_type, close_otypes=None) -> list:
        trades = self.account.closed_trades_list(close_otypes=close_otypes, store=self.lots)
        trades = [x for x in trades if x.asset().type() in asset_type]
        trades = [x for x in trades if self.in_period(self.deal_date(x))]
        trades = [x for x in trades if not self.excluded(x.close_operation())]
        deals = []
        for deal in trades:
            if deal.qty() < Decimal('0') and self.trade_date(deal.open_operation()) < self.year_begin:
                if deal.asset().type() in self.SHORT_HANDLED:
                    year = datetime.fromtimestamp(self.trade_date(deal.open_operation()), tz=timezone.utc).year
                    self._carried.append((deal.close_operation(), year))
                    self.mark_printed(deal.close_operation())
                    continue
                self._warn_short(deal.asset(), deal.open_operation())
            deals.append(deal)
        return deals

    # Deals the replay realized at an exchange by a corporate action in the period, less those the user excluded
    def exchanges_list(self, asset_type) -> list:
        trades = self.account.closed_trades_list(close_otypes=(LedgerTransaction.CorporateAction,), store=self.lots,
                                                 realized=True)
        trades = [x for x in trades if x.asset().type() in asset_type and self.in_period(self.deal_date(x))]
        return [x for x in trades if not self.excluded(x.close_operation())]

    # The note of a realized exchange: the user's price, the user's decision, or the jurisdiction's rule
    def exchange_note(self, action) -> str:
        if (action.id(), TaxOverride.PricePerShare) in self._overrides:
            return self.texts['exchange_price']
        if (action.id(), TaxOverride.TaxEvent) in self._overrides:
            return self.texts['exchange_decided']
        return self.texts['exchange']

    SHORT_HANDLED = (PredefinedAsset.Stock,)   # asset kinds whose shorts follow the year-of-sale rule

    # Slices of a short sold in the report's period and not bought back in its year (later, or not yet), as
    # {'open': sale, 'qty', 'p_adj', 'q_adj', 'close': buy-back or None}
    def year_end_shorts(self) -> list:
        pieces = []
        for deal in self.account.closed_trades_list(store=self.lots):
            if deal.qty() < Decimal('0') and self.in_period(self.trade_date(deal.open_operation())) \
                    and self.trade_date(deal.close_operation()) >= self.year_end:
                pieces.append({'open': deal.open_operation(), 'qty': deal.qty(), 'p_adj': deal.p_adjustment(),
                               'q_adj': deal.q_adjustment(), 'close': deal.close_operation()})
        for asset_id in self.lots.assets(self.account.id()):
            for lot in self.account.open_trades_list(JalAsset(asset_id), store=self.lots):   # a short as a positive qty
                sale = lot.open_operation()
                if sale.type() == LedgerTransaction.Trade and sale.qty() < Decimal('0') \
                        and self.in_period(self.trade_date(sale)):
                    pieces.append({'open': sale, 'qty': -lot.open_qty(), 'p_adj': lot.p_adjustment(),
                                   'q_adj': lot.q_adjustment(), 'close': None})
        return sorted(pieces, key=lambda x: x['open'].timestamp())

    # The stock shorts of year_end_shorts(), each with its share of the sale's proceeds and fee, in the sale's currency
    def stock_year_end_shorts(self) -> list:
        pieces = [x for x in self.year_end_shorts() if x['open'].asset().type() in self.SHORT_HANDLED]
        for piece in pieces:
            sale = piece['open']
            share = piece['p_adj'] * piece['q_adj'] * abs(piece['qty'] / (sale.qty() * piece['q_adj']))
            piece['amount'] = share * abs(sale.qty()) * sale.price()
            piece['fee'] = share * sale.fee()
            self.mark_printed(sale)
        return pieces

    def _warn_short(self, asset, sale):
        line = self.texts['short_unhandled'].format(symbol=asset.symbol(), date=datetime.fromtimestamp(
            self.trade_date(sale), tz=timezone.utc).strftime('%d.%m.%Y'))
        if line not in self.short_warnings:
            self.short_warnings.append(line)
