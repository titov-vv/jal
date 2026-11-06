import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_dividends
from tests.test_taxes_pt import create_pt_scenario
from tests.test_tax_replay import create_ru_scenario
from tests.test_residence import _timeline
from jal.constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.db.country import JalCountry
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
