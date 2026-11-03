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


def _dividend_row(report: dict, section: str) -> dict:
    rows = [x for x in report[section] if x['report_template'] == "dividend"]
    assert len(rows) == 1
    return rows[0]


# RU: 13% of the gross, less the withheld tax where a treaty with the source country exists. russia.json ends with
# 2025, so a 2026 report finds no treaty at all and asks for the full 13%.
@pytest.mark.parametrize("year, treaty, tax2pay", [
    (2025, "Да", Decimal('300.00')),     # (13 - 10) USD * 100
    (2026, "Нет", Decimal('1300.00')),   # no parameters for 2026
])
def test_ru_dividend_treaty_by_parameter_year(prepare_db_taxes, year, treaty, tax2pay):
    _us_dividend(year)
    row = _dividend_row(TaxesRussia().prepare_tax_report(year, 1), "Дивиденды")
    assert row['tax_treaty'] == treaty
    assert row['tax2pay'] == tax2pay


# PT: portugal.json ends with 2024, so 2025 and 2026 reports mark a US dividend as without a treaty
@pytest.mark.parametrize("year, treaty", [(2024, "Y"), (2025, "N"), (2026, "N")])
def test_pt_dividend_treaty_by_parameter_year(prepare_db_taxes, year, treaty):
    _us_dividend(year)
    row = _dividend_row(TaxesPortugal().prepare_tax_report(year, 1), "Dividends")
    assert row['tax_treaty'] == treaty
    assert row['tax_eur'] == Decimal('9.00')


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
