import json
import openpyxl
import pytest
from copy import deepcopy
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_dividends, create_quotes, create_trades, create_actions
from tests.test_taxes_pt import create_pt_scenario
from tests.test_tax_replay import create_ru_scenario
from tests.test_residence import _timeline
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.country import JalCountry
from jal.data_export.taxes import TaxReport, TaxReportCancelled
from jal.data_export.xlsx import XLSX
from jal.data_export.ru_ndfl3 import Ru_NDFL3, FOREIGN_SECTION
from jal.data_export.irs_modelo3 import IRS_Modelo3
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.widgets.icons import JalIcon
from jal.widgets.tax_widget import TaxWidget
from jal.widgets.helpers import reading2d


# The dated rows of every section but the Summary, as comparable texts
def _rows(taxes, report: dict) -> list:
    return sorted(f"{name}: {row!r}" for name, rows in report.items() if name != taxes.summary_section[0]
                  for row in rows if row['report_template'] not in ("totals", "skipped"))


# The two halves of a year hold between them exactly the rows of the whole year, each in the half its date falls in
@pytest.mark.parametrize("report_class, scenario, year, split", [(TaxesRussia, create_ru_scenario, 2025, d2t(250301)),
                                                                 (TaxesPortugal, create_pt_scenario, 2024, d2t(240701))])
def test_two_halves_make_the_year(prepare_db_taxes, report_class, scenario, year, split):
    scenario()
    taxes = report_class()
    whole = _rows(taxes, taxes.prepare_tax_report(year, 1))
    first = _rows(taxes, taxes.prepare_tax_report(year, 1, period=(taxes.year_begin, split)))
    assert (taxes.period_begin, taxes.period_end) == (taxes.year_begin, split)
    second = _rows(taxes, taxes.prepare_tax_report(year, 1, period=(split, taxes.year_end)))
    assert first and second
    assert sorted(first + second) == whole


def test_period_outside_the_year_is_refused(prepare_db_taxes):
    with pytest.raises(ValueError):
        TaxesRussia().prepare_tax_report(2025, 1, period=(d2t(241201), d2t(250301)))
    with pytest.raises(ValueError):
        TaxesRussia().prepare_tax_report(2025, 1, period=(d2t(250301), d2t(250301)))


# From / To follow the year, stay inside it and in order; the accounts follow the period; the report gets the period
def test_dialog_period_follows_the_year(prepare_db_taxes, monkeypatch):
    create_assets([("AAPL", "Apple Inc", "US0378331005", 2, PredefinedAsset.Stock, 'us')])   # ID 4
    create_dividends([(dt2t(2505151430), 1, 4, 100.0, 10.0, "AAPL CASH DIVIDEND")])
    Ledger().rebuild(from_timestamp=0)
    JalIcon()
    parent = QWidget()
    widget = TaxWidget(parent)
    widget.ui.Year.setValue(2025)
    assert (widget.ui.PeriodFrom.date(), widget.ui.PeriodTo.date()) == (QDate(2025, 1, 1), QDate(2025, 12, 31))
    assert (widget.period_begin, widget.period_end) == (d2t(250101), d2t(260101))
    assert widget.accounts == [1]

    widget.ui.PeriodFrom.setDate(QDate(2024, 6, 1))     # before the year
    widget.ui.PeriodTo.setDate(QDate(2026, 2, 1))       # after it
    assert (widget.ui.PeriodFrom.date(), widget.ui.PeriodTo.date()) == (QDate(2025, 1, 1), QDate(2025, 12, 31))
    widget.ui.PeriodTo.setDate(QDate(2025, 3, 31))
    widget.ui.PeriodFrom.setDate(QDate(2025, 4, 15))    # past To
    assert widget.ui.PeriodFrom.date() == QDate(2025, 3, 31)
    assert widget.accounts == []                        # the May dividend is outside the period

    widget.ui.PeriodTo.setDate(QDate(2025, 6, 30))
    widget.ui.PeriodFrom.setDate(QDate(2025, 5, 15))
    assert (widget.period_begin, widget.period_end, widget.accounts) == (d2t(250515), d2t(250701), [1])
    periods = []

    def prepare(_self, year, accounts, period=None, **kwargs):
        periods.append((year, accounts, period))
        raise TaxReportCancelled()
    monkeypatch.setattr(TaxReport, "prepare_tax_report", prepare)
    widget.SaveReport()
    assert periods == [(2025, [1], (d2t(250515), d2t(250701)))]

    widget.ui.Year.setValue(2024)
    assert (widget.ui.PeriodFrom.date(), widget.ui.PeriodTo.date()) == (QDate(2024, 1, 1), QDate(2024, 12, 31))
    assert widget.accounts == []


# Residence rows as (YYMMDD since, country code), currency 1, no zone; a None code leaves the country blank
def _residence(rows):
    _timeline([(d2t(since), 1, JalCountry(data={'code': code}, search=True).id() if code else 0, '')
               for since, code in rows])


# RU knows no part of a year: 183 days of it or more give the whole year, fewer give nothing
@pytest.mark.parametrize("rows, year, resident", [
    ([(240101, 'ru')], 2025, True),
    ([(250702, 'ru')], 2025, True),                   # 2 Jul - 31 Dec 2025: 183 days
    ([(250703, 'ru')], 2025, False),                  # 182 days
    ([(200101, 'ru'), (250702, 'pt')], 2025, False),  # 1 Jan - 1 Jul 2025: 182 days
    ([(200101, 'ru'), (240702, 'pt')], 2024, True),   # 1 Jan - 1 Jul 2024: 183 days, 29 February counted
    ([(200101, 'ru'), (250301, None), (250801, 'pt')], 2025, True),   # a blank row carries Russia on to 31 July
    ([(200101, 'pt'), (250301, 'ru'), (250601, 'pt'), (250801, 'ru')], 2025, True),   # 92 + 153 days
    ([(250101, 'pt')], 2025, False)])
def test_ru_resident_by_183_days(prepare_db_taxes, rows, year, resident):
    _residence(rows)
    taxes = TaxesRussia()

    assert taxes.resident_periods(year) == ([TaxReport.year_window(year)] if resident else [])


# PT splits a year by date: one period per stay, each from the first day of presence
@pytest.mark.parametrize("rows, year, periods", [
    ([(200101, 'pt')], 2025, [(250101, 260101)]),
    ([(200101, 'ru'), (250911, 'pt')], 2025, [(250911, 260101)]),                    # entry
    ([(200101, 'pt'), (250415, 'ru')], 2025, [(250101, 250415)]),                    # exit
    ([(200101, 'pt'), (250301, 'ru'), (250601, 'pt')], 2025, [(250101, 250301), (250601, 260101)]),   # and return
    ([(200101, 'ru'), (250301, 'pt'), (250601, None)], 2025, [(250301, 260101)]),    # a blank row carries Portugal on
    ([(200101, 'ru'), (240229, 'pt')], 2024, [(240229, 250101)]),                    # leap day
    ([(200101, 'ru')], 2025, []),
    ([], 2025, [])])
def test_pt_resident_by_date(prepare_db_taxes, rows, year, periods):
    _residence(rows)

    assert TaxesPortugal().resident_periods(year) == [(d2t(x), d2t(y)) for x, y in periods]


# The dialog proposes the first period the jurisdiction derives and names all of them; the user's edit stays until the
# country or the year changes; with nothing derived it offers the whole year. Another jurisdiction's periods that
# overlap the chosen one are named too.
def test_dialog_proposes_the_resident_period(prepare_db_taxes):
    _residence([(200101, 'ru'), (250301, 'pt'), (250601, 'ru'), (250911, 'pt')])   # RU 161 days in 2025
    JalIcon()
    parent = QWidget()
    widget = TaxWidget(parent)
    dates = lambda: (widget.ui.PeriodFrom.date(), widget.ui.PeriodTo.date())
    label = lambda: widget.ui.ResidenceLbl.text().split("\n")
    span = lambda x, y: f"{reading2d(d2t(x))} - {reading2d(d2t(y))}"
    widget.ui.Year.setValue(2025)
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('pt'))
    assert dates() == (QDate(2025, 3, 1), QDate(2025, 5, 31))
    assert label()[1:] == [f"{span(250301, 250531)}, {span(250911, 251231)}"]
    widget.ui.PeriodFrom.setDate(QDate(2025, 1, 1))
    widget.ui.PeriodTo.setDate(QDate(2025, 12, 31))
    assert dates() == (QDate(2025, 1, 1), QDate(2025, 12, 31))   # the user's choice

    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
    assert dates() == (QDate(2025, 1, 1), QDate(2025, 12, 31))   # nothing derived
    assert label() == [f"Also resident in Portugal: {span(250301, 250531)}, {span(250911, 251231)}"]
    widget.ui.PeriodFrom.setDate(QDate(2025, 6, 1))
    widget.ui.PeriodTo.setDate(QDate(2025, 9, 10))
    assert widget.ui.ResidenceLbl.isHidden()                     # no overlap left in the period
    widget.ui.PeriodTo.setDate(QDate(2025, 9, 11))
    assert label() == [f"Also resident in Portugal: {span(250911, 251231)}"]

    widget.ui.Year.setValue(2024)
    assert dates() == (QDate(2024, 1, 1), QDate(2024, 12, 31))
    assert label()[1:] == [span(240101, 241231)]
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('pt'))
    assert dates() == (QDate(2024, 1, 1), QDate(2024, 12, 31))   # nothing derived
    assert label() == [f"Also resident in Россия: {span(240101, 241231)}"]
    widget.ui.Year.setValue(2025)
    assert dates() == (QDate(2025, 3, 1), QDate(2025, 5, 31))


# ----------------------------------------------------------------------------------------------------------------------
# The PT scenario on account 1 (USD) and a second account in 'currency' with a dividend, a sale and an interest
def _second_account(currency: int, country: str = 'us') -> int:
    create_pt_scenario()
    create_quotes(2, 1, [(d2t(230101), 90.0)])     # USD/RUB
    create_quotes(3, 1, [(d2t(230101), 100.0)])    # EUR/RUB
    account = JalAccountCreator(currency_id=currency, number='X2', name='Second', investing=1, organization=1,
                                country=country).commit().id()
    create_actions([(d2t(230101), account, 1, [(PredefinedCategory.StartingBalance, 5000.0)]),
                    (dt2t(2406031430), account, 1, [(PredefinedCategory.Interest, 1.5, "CREDIT INT")])])
    create_trades(account, [(dt2t(2402011430), d2t(240205), 4, 10, 100.0, 1.0, "B1"),
                            (dt2t(2405021430), d2t(240506), 4, -10, 120.0, 1.0, "S1")])
    create_dividends([(dt2t(2403011430), account, 4, 5.0, 0.75, "AAPL CASH DIVIDEND")])
    Ledger().rebuild(from_timestamp=0)
    return account


def _data(rows: list) -> list:
    return [x for x in rows if x['report_template'] not in ("account", "subtotals", "totals")]


# {(section, label): amount} of the Summary's figures and counts, a figure keyed by the section above it; the estimates
# are left out, as one made on the netted bases is not the sum of two
def _summary(rows: list) -> dict:
    figures, section = {}, ''
    for row in rows:
        section = row.get('section', section) if row['report_template'] == "section" else section
        if row['report_template'] in ("section", "count"):
            figures[(row['report_template'], row.get('section') or row.get('label'))] = row.get('rows', row.get('count'))
        elif 'amount' in row and row['report_template'] != "estimate":
            figures[(section, row.get('figure') or row.get('label'))] = row['amount']
    return figures


# A report over two accounts: each section shows each account's rows under its header with its own subtotal, then the
# grand total of both; the Summary is the sum of the two single-account reports
@pytest.mark.parametrize("report_class", [TaxesRussia, TaxesPortugal])
@pytest.mark.parametrize("currency", [3, 2])
def test_two_accounts_are_netted(prepare_db_taxes, tmp_path, report_class, currency):
    second = _second_account(currency)
    taxes = report_class()
    singles = [taxes.prepare_tax_report(2024, x) for x in (1, second)]
    combined = taxes.prepare_tax_report(2024, [1, second])
    summary, uncovered = taxes.summary_section[0], taxes.uncovered_section[0]
    both = 0
    for name, rows in combined.items():
        if name in (summary, uncovered):
            continue
        parts = [x[name] for x in singles]
        assert _data(rows) == _data(parts[0]) + _data(parts[1])
        assert [x['account'] for x in rows if x['report_template'] == "account"] == \
               [taxes.texts['account_block'].format(number=number, currency=symbol)   # the test broker has no name
                for number, symbol, part in (("U7654321", "USD", parts[0]), ("X2", JalAsset(currency).symbol(), parts[1]))
                if part]
        totals = [x for part in parts for x in part if x['report_template'] == "totals"]
        assert [dict(x, report_template="totals") for x in rows if x['report_template'] == "subtotals"] == totals
        if not totals:
            continue
        both += len(totals) == 2
        grand, = [x for x in rows if x['report_template'] == "totals"]
        for field in grand:
            values = [x[field] for x in totals if x.get(field) is not None]
            in_report_currency = field.endswith(taxes.currency_suffix) or field == "tax2pay"
            if field != 'report_template':
                assert grand[field] == (sum(values) if values and (currency == 2 or in_report_currency) else None), field
    assert both >= 3     # dividends, shares and interest come from both accounts
    expected = {}
    for single in singles:
        for key, value in _summary(single[summary]).items():
            expected[key] = expected.get(key, 0) + value
    assert {k: v for k, v in _summary(combined[summary]).items() if v} == {k: v for k, v in expected.items() if v}
    assert taxes.sheet_parameters()['account'] == f"U7654321 (USD), X2 ({JalAsset(currency).symbol()})"
    assert taxes.sheet_parameters()['currency'] == ("USD" if currency == 2 else taxes.texts['account_currency'])
    assert any(taxes.texts['fifo_netted'] in taxes.section_headers(x) for x in taxes.reports)
    assert not any(taxes.texts['fifo'] in taxes.section_headers(x) for x in taxes.reports)

    file = str(tmp_path / "report.xlsx")
    xlsx = XLSX(file)
    for section in combined:
        xlsx.output_data(combined[section], taxes.report_template(section),
                         dict(taxes.sheet_parameters(), period="01/01/2024 - 31/12/2024"),
                         headers=taxes.section_headers(section))
    assert xlsx.save()
    cells = {c.value for sheet in openpyxl.load_workbook(file) for row in sheet.iter_rows() for c in row}
    assert {f"{taxes.texts['account_block'].format(number='X2', currency=JalAsset(currency).symbol())}",
            "Итого по счёту" if report_class is TaxesRussia else "Account total"} <= cells


# One ticked account gives the report of that account as it was: no header row, no subtotal
def test_one_account_in_a_list_is_the_single_report(prepare_db_taxes):
    create_pt_scenario()
    assert TaxesPortugal().prepare_tax_report(2024, [1]) == TaxesPortugal().prepare_tax_report(2024, 1)


# Every taxable account is ticked; an untick survives a period change
def test_dialog_ticks_accounts(prepare_db_taxes):
    second = _second_account(2)
    JalIcon()
    parent = QWidget()
    widget = TaxWidget(parent)
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
    widget.ui.Year.setValue(2024)
    assert widget.accounts == [1, second]
    widget.ui.Accounts.item(0).setCheckState(Qt.Unchecked)
    widget.ui.PeriodFrom.setDate(QDate(2024, 2, 1))
    assert widget.accounts == [second]


# The forms of a report over two accounts file each row under its own account's broker country and currency: the
# 3-NDFL lines are those merge_de5() makes of the two single-account files, the Modelo 3 lines those of the two files
@pytest.mark.parametrize("broker_as_income", [False, True])
def test_ndfl3_of_two_accounts(prepare_db_taxes, tmp_path, broker_as_income):
    second = _second_account(3, country='de')
    taxes = TaxesRussia()
    files = []
    for accounts in (1, second, [1, second]):
        report = taxes.prepare_tax_report(2024, accounts)
        form = Ru_NDFL3(2025, broker_as_income=broker_as_income)
        form.update_taxes(deepcopy(report), taxes.sheet_parameters())
        files.append(str(tmp_path / f"{len(files)}.de5"))
        form.save(files[-1])
    merged = Ru_NDFL3.merge_de5(files[:2])
    with open(files[2], 'r', encoding='utf-8') as file:
        combined = json.load(file)
    line = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)
    assert sorted(map(line, combined[FOREIGN_SECTION])) == sorted(map(line, merged[FOREIGN_SECTION]))
    assert {(x['CountryCode2'], x['CurrencyCode']) for x in combined[FOREIGN_SECTION]} == {('840', '840'), ('276', '978')}
    assert {k: v for k, v in combined.items() if k != FOREIGN_SECTION} == \
           {k: v for k, v in merged.items() if k != FOREIGN_SECTION}
    assert combined['CurrencyQuantity'] == len(combined[FOREIGN_SECTION]) > 0


def test_modelo3_of_two_accounts(prepare_db_taxes):
    second = _second_account(3, country='de')
    taxes = TaxesPortugal()
    lines = []
    for accounts in (1, second, [1, second]):
        form = IRS_Modelo3(2024)
        form.update_taxes(taxes.prepare_tax_report(2024, accounts), taxes.sheet_parameters())
        lines.append(form._tax_form.splitlines())
    assert sorted(lines[2]) == sorted(lines[0] + lines[1])
    assert {x[x.index("<CodPais>") + 9:x.index("</CodPais>")] for x in lines[2]} == {'840', '276'}
