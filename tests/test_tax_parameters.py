import pytest
from decimal import Decimal
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_quotes, create_dividends
from jal.constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.data_export.taxes import TaxReport
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


# Every jurisdiction the tax dialog lists builds a report and shows exactly one option box of its own
def test_every_listed_jurisdiction_builds_a_report(prepare_db_taxes):
    JalIcon()   # loads the icon cache the country flags come from
    parent = QWidget()
    widget = TaxWidget(parent)
    assert widget.ui.Country.count() == len(TaxReport.countries)
    boxes = {TaxReport.PORTUGAL: widget.ui.PtBox, TaxReport.RUSSIA: widget.ui.RuBox}
    for index in range(widget.ui.Country.count()):
        widget.ui.Country.setCurrentIndex(index)
        assert [x for x, box in boxes.items() if not box.isHidden()] == [index]
        report = TaxReport.create_report(index)
        assert type(report).__name__ == TaxReport.countries[index]['class']
        sections = report.prepare_tax_report(2025, 1)
        assert list(sections)[0] == report.summary_section[0]
        assert list(sections)[-1] == report.uncovered_section[0]
