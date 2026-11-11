import openpyxl
import pytest
from decimal import Decimal
from PySide6.QtWidgets import QWidget, QMessageBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_quotes, create_dividends
from jal.constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.data_export.taxes import TaxReport
from jal.data_export.tax_parameters import TaxParameters
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.widgets.icons import JalIcon
from jal.widgets.tax_widget import TaxWidget


# A US dividend of 100 USD with 10 USD withheld on account 1, paid on 15 May of 'year'; 1 USD = 100 RUB = 0.9 EUR
def _us_dividend(year: int):
    create_assets([("AAPL", "Apple Inc", "US0378331005", 2, PredefinedAsset.Stock, 'us')])   # ID 4
    yy = year % 100
    create_quotes(2, 1, [(d2t(int(f"{yy}0101")), 100.0)])
    create_quotes(2, 3, [(d2t(int(f"{yy}0101")), 0.9)])
    create_dividends([(dt2t(int(f"{yy}05151430")), 1, 4, 100.0, 10.0, "AAPL CASH DIVIDEND")])
    Ledger().rebuild(from_timestamp=0)


def _warnings(report: dict, section: str) -> list:
    return [x['warning'] for x in report[section] if x['report_template'] == "warning"]


def _dividend_row(report: dict, section: str) -> dict:
    rows = [x for x in report[section] if x['report_template'] == "dividend"]
    assert len(rows) == 1
    return rows[0]


# RU: 13% of the gross, less the withheld tax where a treaty with the source country exists. A year past the
# file's review keeps its latest values and says so; a year before its first one has no treaty and no estimate.
@pytest.mark.parametrize("year, treaty, tax2pay, warning", [
    (2019, "Нет", None, "налоговых параметров для 2019 года нет"),
    (2025, "Да", Decimal('300.00'), None),     # (13 - 10) USD * 100
    (2026, "Да", Decimal('300.00'), None),
    (2027, "Да", Decimal('300.00'), "проверены по 2026 год"),
])
def test_ru_dividend_treaty_by_parameter_year(prepare_db_taxes, year, treaty, tax2pay, warning):
    _us_dividend(year)
    report = TaxesRussia().prepare_tax_report(year, 1)
    row = _dividend_row(report, "Дивиденды")
    assert row['tax_treaty'] == treaty
    assert row['tax2pay'] == tax2pay
    totals = [x for x in report["Дивиденды"] if x['report_template'] == "totals"][0]
    assert totals['tax2pay'] == tax2pay
    found = [x for x in _warnings(report, "Сводка") if "параметр" in x]
    assert (len(found) == 1 and warning in found[0]) if warning else found == []


# PT: a US dividend is under a treaty; the file starts with 2022 and was reviewed through 2026
@pytest.mark.parametrize("year, treaty, warning", [
    (2021, "N", "no tax parameters for 2021"), (2024, "Y", None), (2025, "Y", None), (2026, "Y", None),
    (2027, "Y", "last reviewed for 2026"),
])
def test_pt_dividend_treaty_by_parameter_year(prepare_db_taxes, year, treaty, warning):
    _us_dividend(year)
    report = TaxesPortugal().prepare_tax_report(year, 1)
    row = _dividend_row(report, "Dividends")
    assert row['tax_treaty'] == treaty
    assert row['tax_eur'] == Decimal('9.00')
    found = [x for x in _warnings(report, "Summary") if "parameters" in x]
    assert (len(found) == 1 and warning in found[0]) if warning else found == []


# Every jurisdiction the tax dialog lists builds a report and shows the options of its own alone
def test_every_listed_jurisdiction_builds_a_report(prepare_db_taxes):
    JalIcon()   # loads the icon cache the country flags come from
    parent = QWidget()
    widget = TaxWidget(parent)
    assert widget.ui.Country.currentData() == 'ru'
    assert [widget.ui.Country.itemData(i) for i in range(widget.ui.Country.count())] == list(TaxReport.jurisdictions)
    for index in range(widget.ui.Country.count()):
        widget.ui.Country.setCurrentIndex(index)
        code = widget.country
        assert {x for x, rows in widget._rows.items() for row in rows if not row.isHidden()} == {code}
        report = TaxReport.create_report(code)
        assert type(report).__name__ == TaxReport.jurisdictions[code]['class']
        assert report.jurisdiction == code
        sections = report.prepare_tax_report(2025, 1)
        assert list(sections)[0] == report.summary_section[0]
        assert list(sections)[-1] == report.uncovered_section[0]


# The dialog saves the report of the jurisdiction it shows, whatever its position in the list
@pytest.mark.parametrize("code, first_sheet", [('pt', "Summary"), ('ru', "Сводка")])
def test_dialog_saves_the_selected_jurisdiction(prepare_db_taxes, tmp_path, monkeypatch, code, first_sheet):
    _us_dividend(2025)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    JalIcon()
    parent = QWidget()
    widget = TaxWidget(parent)
    widget.ui.Year.setValue(2025)
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData(code))
    widget.ui.XlsFileName.setText(str(tmp_path / "report.xlsx"))
    widget.SaveReport()
    assert openpyxl.load_workbook(tmp_path / "report.xlsx").sheetnames[0] == first_sheet


# A year past the review, or before the file, is warned of in a message after saving as well as on the Summary sheet
@pytest.mark.parametrize("year, expected", [(2025, None), (2027, "last reviewed for 2026"), (2019, "no tax parameters")])
def test_dialog_warns_of_parameters(prepare_db_taxes, tmp_path, monkeypatch, year, expected):
    _us_dividend(year)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _self, _parent, title, text, *args: warnings.append(text) or QMessageBox.Ok)
    JalIcon()
    parent = QWidget()
    widget = TaxWidget(parent)
    widget.ui.Year.setValue(year)
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
    widget.ui.XlsFileName.setText(str(tmp_path / "report.xlsx"))
    widget.SaveReport()
    parameter_warnings = [x for x in warnings if "parameters" in x]
    assert parameter_warnings == [] if expected is None else expected in parameter_warnings[0]


# The form codes of each kind of row: RU income / expense codes from 2020, PT Anexo J codes from 2022; crypto has no
# PT code (the quadro is its classification), a year before the file has none at all
@pytest.mark.parametrize("code, year, kind, expected", [
    ('ru', 2020, TaxParameters.STOCK, ('1530', '201')),
    ('ru', 2025, TaxParameters.ETF, ('1530', '201')),
    ('ru', 2025, TaxParameters.BOND, ('1530', '201')),
    ('ru', 2025, TaxParameters.COUPON, ('1530', '')),
    ('ru', 2025, TaxParameters.DERIVATIVE, ('1532', '206')),
    ('ru', 2025, TaxParameters.DIVIDEND, ('1010', '')),
    ('ru', 2025, TaxParameters.INTEREST, ('4800', '')),
    ('ru', 2025, TaxParameters.CRYPTO, ('6035', '435')),
    ('ru', 2025, TaxParameters.CRYPTO_INCOME, ('4800', '')),
    ('ru', 2019, TaxParameters.STOCK, None),
    ('pt', 2025, TaxParameters.STOCK, ('G01', '')),
    ('pt', 2025, TaxParameters.ETF, ('G20', '')),
    ('pt', 2025, TaxParameters.BOND, ('G10', '')),
    ('pt', 2025, TaxParameters.COUPON, ('E21', '')),
    ('pt', 2025, TaxParameters.DERIVATIVE, ('G30', '')),
    ('pt', 2025, TaxParameters.DIVIDEND, ('E11', '')),
    ('pt', 2025, TaxParameters.INTEREST, ('E21', '')),
    ('pt', 2025, TaxParameters.CRYPTO, None),
    ('pt', 2021, TaxParameters.STOCK, None),
    ('ru', 2025, "unknown", None),
])
def test_form_codes(prepare_db, code, year, kind, expected):
    assert TaxParameters(code, year).code(kind) == expected
