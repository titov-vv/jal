import importlib   # it is used for delayed import in order to avoid circular reference in child classes
import logging
from decimal import Decimal
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication

from jal.constants import PredefinedAsset
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.category import JalCategory
from jal.db.db import JalDB
from jal.db.helpers import is_day_marker
from jal.db.operations import LedgerTransaction, TaxStatus, AssetPayment, AssetIncome, Transfer
from jal.db.clock import ZONE_SPAN, wall_clock_reading
from jal.data_export.tax_parameters import TaxParameters, TAX_TREATY

REPORT_METHOD = 0
REPORT_TEMPLATE = 1
RATES_GAP = 14 * 86400   # how much older than its date a rate may be before it is warned of (holidays differ)


# Raised when a report can't be produced as asked; 'missing' lists (symbol, timestamp) of every quote that stopped it
class TaxReportStop(Exception):
    def __init__(self, missing: list):
        super().__init__("Tax report stopped by missing quotes")
        self.missing = missing


class TaxReport:
    PORTUGAL = 0
    RUSSIA = 1
    countries = {
        PORTUGAL: {"name": "Portugal", "module": "jal.data_export.tax_reports.portugal", "class": "TaxesPortugal", "flag": "pt"},
        RUSSIA: {"name": "Россия", "module": "jal.data_export.tax_reports.russia", "class": "TaxesRussia", "flag": "ru"}
    }
    jurisdiction = ''   # ISO 3166-1 alpha-2 code of the jurisdiction, names its parameter file
    currency_name = ''  # The name of the currency for tax values calculation
    currency_suffix = ''   # Suffix of the report-currency fields of a row ('_rub', '_eur')
    # The two sections every report has, in its jurisdiction's language: (name, template)
    summary_section = ('', '')
    uncovered_section = ('', '')
    texts = {}             # Report strings in the jurisdiction's language, see the country classes
    operation_labels = {}  # {(otype, subtype or None): label} in the jurisdiction's language
    # The zone whose wall clock this report counts its days and years on - the one of the jurisdiction the report is
    # filed in. Symmetric to Statement.source_timezone: a report names its own zone the way a statement names its
    # source's. An empty name leaves every stored timestamp read as it is.
    report_timezone = ''

    def __init__(self):
        self._currency_id = JalAsset.find({'symbol': self.currency_name, 'type_id': PredefinedAsset.Money}).id()
        if not self._currency_id:  # Zero value if no currency was found in DB for given currency symbol
            self.reports = {}
            logging.error(self.tr("Currency is not defined: ") + self.currency_name)
            return
        self.account = None           # Account for reporting
        self.account_currency = None  # Currency of the account for reporting
        self.year_begin = 0
        self.year_end = 0
        self.use_settlement = True
        self.one_currency_rate = False
        self.parameters = None
        self._section = ''
        self.section_notes = {}   # {section: [header lines]} a section states under its title
        self._printed = set()     # (otype, oid) of every operation a section printed
        self._missing = []        # (symbol, timestamp) of every quote a section needed and didn't find
        self._rates_end = None    # newest official rate into the report currency, read once per report
        self.rates_warnings = {}  # {(pair, date of the rate used): latest date it converted} for rates likely missing

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

    @staticmethod
    def create_report(country: int):
        try:
            report_data = TaxReport.countries[country]
        except KeyError:
            raise ValueError(f"Selected country item {country} has no country handler in tax report code")
        module = importlib.import_module(report_data['module'])
        try:
            class_instance = getattr(module, report_data['class'])
        except AttributeError:
            raise ValueError(f"Tax report class '{report_data['class']}' can't be loaded")
        return class_instance()

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

    def prepare_tax_report(self, year: int, account_id: int, **kwargs) -> dict:
        tax_report = {}
        self.account = JalAccount(account_id)
        self.account_currency = JalAsset(self.account.currency())
        # The year is a half-open window [year_begin, year_end): 'year_end' is the FIRST second of the next year,
        # so an operation stamped at midnight on 1 January belongs to that next year and to no other.
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']
        if 'use_one_currency_rate' in kwargs:
            self.one_currency_rate = kwargs['use_one_currency_rate']
        if 'generate_modelo3' in kwargs:
            self.generate_modelo3 = kwargs['generate_modelo3']
        self.parameters = TaxParameters(self.jurisdiction, year)
        if self.parameters.value(TAX_TREATY) is None:
            logging.warning(self.tr("There are no parameters found for tax report year: ") + str(year))
        self.section_notes, self._printed, self._missing = {}, set(), []
        self._rates_end, self.rates_warnings = None, {}
        sections = {}
        for report in self.reports:
            self._section = report
            sections[report] = self.reports[report][REPORT_METHOD]()
        if self._missing:
            raise TaxReportStop(self._missing)
        skipped, uncovered = self._not_covered()
        tax_report[self.summary_section[0]] = self.prepare_summary(sections, skipped, uncovered)
        tax_report.update(sections)
        tax_report[self.uncovered_section[0]] = self.prepare_not_covered(skipped, uncovered)
        return tax_report

    # A line the section being prepared states under its title - the treatment it assumed
    def add_header(self, line: str):
        self.section_notes.setdefault(self._section, []).append(line)

    def section_headers(self, section: str) -> list:
        return self.section_notes.get(section, [])

    # Records that a section printed this operation, so that it isn't listed as not covered
    def mark_printed(self, operation):
        if operation is not None:
            self._printed.add((operation.type(), operation.id()))

    def mark_printed_id(self, otype: int, oid: int):
        self._printed.add((otype, oid))

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

    # The operations that changed this deal's lot: the purchase's modifiers that wrote it as the deal's asset, less a
    # swap or wrapping that only rewrote what stayed behind when it took another part of the purchase elsewhere
    @staticmethod
    def deal_modifiers(deal) -> list:
        query = JalDB._exec("SELECT DISTINCT m_otype, m_oid FROM trades_opened WHERE otype=:otype AND oid=:oid "
                            "AND asset_id=:asset AND m_otype!=:trade AND NOT (m_otype=otype AND m_oid=oid) "
                            "ORDER BY timestamp",
                            [(":otype", deal.open_operation().type()), (":oid", deal.open_operation().id()),
                             (":asset", deal.asset().id()), (":trade", LedgerTransaction.Trade)])
        modifiers = []
        while query.next():
            operation = LedgerTransaction.get_operation(query.value(0), query.value(1), Transfer.Outgoing)
            if operation.type() in (LedgerTransaction.Swap, LedgerTransaction.Conversion) \
                    and operation.in_asset().id() != deal.asset().id():
                continue
            modifiers.append(operation)
        return modifiers

    # True if one of 'otypes' (swap, wrapping) brought this deal's lot into the deal's asset
    def carried_through(self, deal, otypes) -> bool:
        return any(x.type() in otypes for x in self.deal_modifiers(deal))

    # Why the jurisdiction's rule takes this operation out of the report, None if it doesn't
    def skip_reason(self, operation):
        if operation.type() == LedgerTransaction.AssetIncome and operation.subtype() == AssetIncome.TokenRentReturn:
            return self.texts['rent_return']
        return None

    # Every taxable or base-impacting operation of the account in the report's year that no section printed:
    # returns ({reason: count} of those the jurisdiction skips, [operations] no section claimed)
    def _not_covered(self):
        skipped, uncovered = {}, []
        query = JalDB._exec("SELECT o.otype, o.id FROM ledger_sequence AS s JOIN operations AS o ON o.id=s.operation_id "
                            "WHERE s.account_id=:account AND s.timestamp>=:begin AND s.timestamp<:end "
                            "GROUP BY o.id ORDER BY MIN(s.seq_no)",
                            [(":account", self.account.id()), (":begin", self.year_begin - ZONE_SPAN),
                             (":end", self.year_end + ZONE_SPAN)])
        while query.next():
            otype, oid = query.value(0), query.value(1)
            if (otype, oid) in self._printed:
                continue
            operation = LedgerTransaction.get_operation(otype, oid)
            if operation.account().id() != self.account.id() or operation.taxable() == TaxStatus.NotTaxable:
                continue
            if not self.in_year(self.operation_date(operation)):
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
            rows.append({
                'report_template': "operation",
                'date': self.operation_date(operation),
                'operation': self.operation_label(operation),
                'symbol': operation.symbol().symbol(),
                'number': operation.number(),
                'description': operation.description(),
                'reason': self.texts['uncovered']
            })
        return rows

    # Each section with its own totals as they stand, in the report's currency (tax figures left out), then the counts
    # of what is not covered and of the figures a later replay may still change
    def prepare_summary(self, sections: dict, skipped: dict, uncovered: list) -> list:
        rows = []
        for name, section in sections.items():
            rows.append({'report_template': "section", 'section': name,
                         'rows': len([x for x in section if x['report_template'] != "totals"])})
            totals = [x for x in section if x['report_template'] == "totals"]
            for field, value in (totals[0].items() if totals else []):
                if field.endswith(self.currency_suffix) and not field.startswith('tax'):
                    figure = field[:-len(self.currency_suffix)]
                    rows.append({'report_template': "figure", 'figure': self.texts.get(figure, figure), 'amount': value})
        pending = len([x for section in sections.values() for x in section if x.get('pending_replay')])
        for label, count in ((self.texts['skipped_total'], sum(skipped.values())),
                             (self.texts['uncovered_total'], len(uncovered))):
            link = self.uncovered_section[0] if count else ''   # an empty section makes no sheet to link to
            rows.append({'report_template': "count", 'label': label, 'count': count, 'link': link})
        rows.append({'report_template': "count", 'label': self.texts['pending_total'], 'count': pending, 'link': ''})
        day = lambda x: datetime.fromtimestamp(x, tz=timezone.utc).strftime('%d.%m.%Y')
        if self.parameters.value(TAX_TREATY) is None:
            rows.append({'report_template': "warning", 'warning': self.texts['parameters_missing'].format(
                year=datetime.fromtimestamp(self.year_begin, tz=timezone.utc).year)})
        elif self.parameters.unreviewed():
            rows.append({'report_template': "warning", 'warning': self.texts['parameters_unreviewed'].format(
                year=datetime.fromtimestamp(self.year_begin, tz=timezone.utc).year,
                reviewed=self.parameters.reviewed_through())})
        for (pair, quoted), latest in sorted(self.rates_warnings.items()):
            rows.append({'report_template': "warning",
                         'warning': self.texts['rates_missing'].format(pair=pair, rate=day(quoted), latest=day(latest))})
        return rows

    # The base rate of an income kind (TaxParameters.DIVIDEND, ...) times 'base', None if the year has no such rate
    def base_estimate(self, kind: str, base: Decimal):
        rate = self.parameters.rate(kind)
        return None if rate is None else rate * base

    # Check if 2-letter country code present in tax treaty parameter of current report
    def has_tax_treaty_with(self, country_code: str) -> bool:
        return self.parameters.treaty_with(country_code)

    # Returns a list of dividends that should be included into the report for given year
    def dividends_list(self) -> list:
        dividends = AssetPayment.get_list(self.account.id(), subtype=AssetPayment.Dividend)
        dividends += AssetIncome.get_list(self.account.id(), subtype=AssetIncome.StockDividend)
        dividends += AssetIncome.get_list(self.account.id(), subtype=AssetIncome.StockVesting)
        dividends = [x for x in dividends if self.year_begin <= self._moment(x.timestamp()) < self.year_end]
        return dividends

    # Returns operations of the given category that belong to the report's year. The database is asked for a wider
    # window than the year, because an operation stamped just outside it may well be inside it on the report's clock;
    # what is inside is then decided on that clock alone.
    def category_operations(self, category_id: int) -> list:
        operations = JalCategory(category_id).get_operations(self.year_begin - ZONE_SPAN, self.year_end + ZONE_SPAN)
        return [x for x in operations if self.year_begin <= self._moment(x.timestamp()) < self.year_end]

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

    def in_year(self, timestamp: int) -> bool:
        return self.year_begin <= timestamp < self.year_end

    # Returns a list of closed deals of the given asset types that belong to the report's year; 'close_otypes' as in
    # JalAccount.closed_trades_list(), deals closed by a trade only by default
    def trades_list(self, asset_type, close_otypes=None) -> list:
        trades = self.account.closed_trades_list(close_otypes=close_otypes)
        trades = [x for x in trades if x.asset().type() in asset_type]
        trades = [x for x in trades if self.in_year(self.deal_date(x))]
        return trades
