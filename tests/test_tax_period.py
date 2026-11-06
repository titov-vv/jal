import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_dividends
from tests.test_taxes_pt import create_pt_scenario
from tests.test_tax_replay import create_ru_scenario
from jal.constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.data_export.taxes import TaxReport, TaxReportCancelled
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.widgets.icons import JalIcon
from jal.widgets.tax_widget import TaxWidget


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
    assert widget.account == 1

    widget.ui.PeriodFrom.setDate(QDate(2024, 6, 1))     # before the year
    widget.ui.PeriodTo.setDate(QDate(2026, 2, 1))       # after it
    assert (widget.ui.PeriodFrom.date(), widget.ui.PeriodTo.date()) == (QDate(2025, 1, 1), QDate(2025, 12, 31))
    widget.ui.PeriodTo.setDate(QDate(2025, 3, 31))
    widget.ui.PeriodFrom.setDate(QDate(2025, 4, 15))    # past To
    assert widget.ui.PeriodFrom.date() == QDate(2025, 3, 31)
    assert widget.account is None                       # the May dividend is outside the period

    widget.ui.PeriodTo.setDate(QDate(2025, 6, 30))
    widget.ui.PeriodFrom.setDate(QDate(2025, 5, 15))
    assert (widget.period_begin, widget.period_end, widget.account) == (d2t(250515), d2t(250701), 1)
    periods = []

    def prepare(_self, year, account_id, period=None, **kwargs):
        periods.append((year, account_id, period))
        raise TaxReportCancelled()
    monkeypatch.setattr(TaxReport, "prepare_tax_report", prepare)
    widget.SaveReport()
    assert periods == [(2025, 1, (d2t(250515), d2t(250701)))]

    widget.ui.Year.setValue(2024)
    assert (widget.ui.PeriodFrom.date(), widget.ui.PeriodTo.date()) == (QDate(2024, 1, 1), QDate(2024, 12, 31))
    assert widget.account is None
