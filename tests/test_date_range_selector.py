import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ledger
from tests.helpers import create_actions
import jal.db.clock
from jal.db.clock import day_start, day_finish
from jal.db.ledger import Ledger
from jal.reports.profit_loss import ProfitLossReportWindow
from jal.reports.reports import Reports
from jal.widgets.custom.date_range_selector import DateRangeSelector, CUSTOM
from jal.widgets.helpers import ManipulateDate

TODAY = QDate(2026, 11, 27)   # a Friday
ALL_ITEMS = "week;month;quarter;year;QTD;YTD;this_year;last_year;all"


@pytest.fixture
def owner(prepare_db):
    parent = QWidget()
    yield parent
    parent.deleteLater()


@pytest.fixture
def today(monkeypatch):
    def set_today(day: QDate):
        monkeypatch.setattr(jal.db.clock, "now_ts", lambda: day_start(day) + 12 * 3600)
    set_today(TODAY)
    return set_today


def _selector(owner) -> DateRangeSelector:
    selector = DateRangeSelector(owner)
    selector.setConfig(ALL_ITEMS)
    return selector


def _pick(selector, item):
    index = selector.range_combo.findData(item)
    selector.range_combo.setCurrentIndex(index)
    selector.range_combo.activated.emit(index)


def _shown(selector) -> tuple:
    return selector.from_date.date(), selector.to_date.date()


@pytest.mark.parametrize("today, preset, first, last", [
    (TODAY, ManipulateDate.PreviousWeek, QDate(2026, 11, 16), TODAY),
    (TODAY, ManipulateDate.PreviousMonth, QDate(2026, 10, 1), TODAY),
    (TODAY, ManipulateDate.PreviousQuarter, QDate(2026, 7, 1), TODAY),
    (TODAY, ManipulateDate.PreviousYear, QDate(2025, 1, 1), TODAY),
    (TODAY, ManipulateDate.QuarterToDate, QDate(2026, 8, 1), TODAY),
    (TODAY, ManipulateDate.YearToDate, QDate(2025, 11, 1), TODAY),
    (TODAY, ManipulateDate.ThisYear, QDate(2026, 1, 1), TODAY),
    (TODAY, ManipulateDate.LastYear, QDate(2025, 1, 1), QDate(2025, 12, 31)),
    (TODAY, ManipulateDate.AllDates, None, TODAY),
    (QDate(2026, 1, 15), ManipulateDate.PreviousWeek, QDate(2026, 1, 5), QDate(2026, 1, 15)),
    (QDate(2026, 1, 15), ManipulateDate.PreviousMonth, QDate(2025, 12, 1), QDate(2026, 1, 15)),
    (QDate(2026, 1, 15), ManipulateDate.PreviousQuarter, QDate(2025, 10, 1), QDate(2026, 1, 15)),
    (QDate(2026, 1, 15), ManipulateDate.QuarterToDate, QDate(2025, 10, 1), QDate(2026, 1, 15)),
    (QDate(2026, 3, 31), ManipulateDate.PreviousQuarter, QDate(2025, 10, 1), QDate(2026, 3, 31)),
    (QDate(2026, 4, 1), ManipulateDate.PreviousQuarter, QDate(2026, 1, 1), QDate(2026, 4, 1)),
    (QDate(2026, 11, 16), ManipulateDate.PreviousWeek, QDate(2026, 11, 9), QDate(2026, 11, 16)),
])
def test_presets(today, preset, first, last):
    assert preset(today) == (first, last)


def test_preset_covers_whole_days(owner, today):
    selector = _selector(owner)
    _pick(selector, 'last_year')
    assert _shown(selector) == (QDate(2025, 1, 1), QDate(2025, 12, 31))
    assert selector.getRange() == (day_start(QDate(2025, 1, 1)), day_finish(QDate(2025, 12, 31)))
    _pick(selector, 'all')
    assert selector.getRange() == (0, day_finish(TODAY))


def test_preset_follows_the_clock(owner, today):
    selector = _selector(owner)
    _pick(selector, 'this_year')
    today(QDate(2027, 1, 2))
    _pick(selector, 'this_year')
    assert _shown(selector) == (QDate(2027, 1, 1), QDate(2027, 1, 2))


def test_manual_edit_is_custom_and_includes_to_day(owner, today):
    selector = _selector(owner)
    _pick(selector, 'quarter')
    emitted = []
    selector.changed.connect(lambda begin, end: emitted.append((begin, end)))
    selector.to_date.setDate(QDate(2026, 9, 30))
    assert selector.range_combo.currentData() == CUSTOM
    assert emitted == [(day_start(QDate(2026, 7, 1)), day_finish(QDate(2026, 9, 30)))]


def test_repicking_preset_reapplies_it(owner, today):
    selector = _selector(owner)
    _pick(selector, 'quarter')
    selector.from_date.setDate(QDate(2026, 8, 15))
    _pick(selector, 'quarter')
    assert selector.range_combo.currentData() == 'quarter'
    assert _shown(selector) == (QDate(2026, 7, 1), TODAY)


def test_dates_never_cross(owner, today):
    selector = _selector(owner)
    _pick(selector, 'month')
    selector.from_date.setDate(QDate(2026, 12, 5))
    assert _shown(selector) == (QDate(2026, 12, 5), QDate(2026, 12, 5))
    selector.to_date.setDate(QDate(2026, 1, 10))
    assert _shown(selector) == (QDate(2026, 1, 10), QDate(2026, 1, 10))
    assert selector.getRange() == (day_start(QDate(2026, 1, 10)), day_finish(QDate(2026, 1, 10)))


def test_set_range_shows_days_as_custom(owner, today):
    selector = _selector(owner)
    selector.setRange(day_start(QDate(2026, 2, 1)), day_finish(QDate(2026, 2, 28)))
    assert selector.range_combo.currentData() == CUSTOM
    assert _shown(selector) == (QDate(2026, 2, 1), QDate(2026, 2, 28))
    assert selector.getRange() == (day_start(QDate(2026, 2, 1)), day_finish(QDate(2026, 2, 28)))
    selector.setRange(0, day_finish(TODAY))
    assert selector.getRange() == (0, day_finish(TODAY))


def test_first_preset_applies_on_setup(owner, today):
    selector = _selector(owner)
    assert selector.range_combo.currentData() == 'week'
    assert selector.getRange() == (day_start(QDate(2026, 11, 16)), day_finish(TODAY))


# An operation late on the "To" day belongs to the range
def test_operations_list_includes_to_day(owner, today, prepare_db_ledger):
    from jal.widgets.operations_widget import OperationsWidget
    late = day_start(QDate(2026, 9, 30)) + 23 * 3600 + 59 * 60
    create_actions([(late, 1, 1, [(5, Decimal('10'))])])
    Ledger().rebuild(from_timestamp=0)
    window = OperationsWidget(owner)
    window.ui.DateRange.setRange(day_start(QDate(2026, 9, 1)), day_start(QDate(2026, 9, 30)))
    QApplication.processEvents()
    assert window.operations_model.rowCount() == 1
    window.ui.DateRange.to_date.setDate(QDate(2026, 9, 29))
    assert window.operations_model.rowCount() == 0


# "Previous year" used to end on 1 January and add an empty 13th month to the report
def test_profit_loss_previous_year_has_twelve_months(owner, today):
    window = ProfitLossReportWindow(Reports(None, None))
    window.setParent(owner)
    _pick(window.ui.ReportRange, 'last_year')
    months = window.ui.ReportTableView.model()._month_list
    assert [(x['year'], x['number']) for x in months] == [(2025, n) for n in range(1, 13)]
