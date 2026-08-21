import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import csv
import importlib
import importlib.util
import pathlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from PySide6.QtCore import QDate, QDateTime, QTimeZone
from PySide6.QtWidgets import QWidget

from constants import PredefinedAsset, PredefinedCategory
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.db import JalDB
from jal.db.reclock import RECLOCKED_COLUMNS, reclock
from jal.db.residence import JalResidence, wall_clock_reading
from lxml import etree

from jal.data_import.broker_statements.ibkr import IBKR_DAY_MARKERS, StatementIBKR
from jal.data_import.broker_statements.kucoin import StatementKuCoin
from jal.db.helpers import is_day_marker, local_timestamp, now_ts, now_dt
from jal.db.ledger import Ledger
from jal.widgets.helpers import ts2axis, axis2ts, ts2d
from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import (create_assets, create_actions, create_dividends, create_trades, create_transfers,
                          d2t, pinned_tz)


# The offset is handed out so a test can state the shift it expects in terms of it instead of repeating the number.
@pytest.fixture
def fixed_tz():
    with pinned_tz('Etc/GMT-2'):          # POSIX inverts the sign: this is a fixed UTC+2 zone, no DST
        yield 2 * 3600


# A QDateTimeAxis label is produced by rendering the plotted value in local time, so the value handed to a chart
# has to be shifted for that label to read the same date as the table cell beside it.
def test_ts2axis_makes_a_local_rendering_read_as_the_stored_clock(fixed_tz):
    stored = 1758803292                                       # renders as 2025-09-25 12:28:12 everywhere in JAL
    assert stored - ts2axis(stored) == fixed_tz     # the local rendering adds the offset back
    assert QDateTime.fromSecsSinceEpoch(ts2axis(stored)).toString('yyyy-MM-dd hh:mm:ss') == '2025-09-25 12:28:12'


# What a chart reports back (the coordinate of a hovered point) has to arrive at the timestamp it was built from,
# or the point cannot be looked up in the data behind the series.
def test_axis2ts_is_the_inverse_of_ts2axis(fixed_tz):
    for stored in [0, 1104537600, 1662854400, 1758803292]:
        assert axis2ts(ts2axis(stored)) == stored


# The tooltip and the axis of one chart must not disagree: the tooltip is rendered on the stored clock by ts2d().
def test_axis_and_tooltip_agree_on_the_day(fixed_tz):
    stored = 1735689540                                       # 2024-12-31 23:59:00 - a whole day away under UTC+2
    axis_value = ts2axis(stored)
    assert QDateTime.fromSecsSinceEpoch(axis_value).toString('yyyy-MM-dd') == '2024-12-31'
    assert ts2d(axis2ts(axis_value)) == ts2d(stored)
    assert datetime.fromtimestamp(stored, tz=timezone.utc).strftime('%Y-%m-%d') == '2024-12-31'


# ----------------------------------------------------------------------------------------------------------------------
# A date field of an operation form is mapped straight onto the stored integer by TimestampDelegate: it is handed a
# UTC QDateTime and whatever the editor makes of it is written back. An editor left on the machine's own clock
# therefore renders a day that is not the stored one and returns a day that is not the rendered one - west of
# Greenwich a settlement stored as the 25th shows as the 24th, and moving it one day on stores the 27th.
OPERATION_FORMS = sorted((pathlib.Path(__file__).resolve().parent.parent / "jal" / "ui" / "widgets").glob("*_operation.ui"))


# The host is given a parent for the reason spelled out in test_dialog_buttons.py: a parentless Qt window leaves
# its object graph to Python's cyclic collector, which takes it apart in an order Qt does not survive.
@pytest.fixture
def owner(prepare_db):
    parent = QWidget()
    yield parent
    parent.deleteLater()


def _date_editors(root):
    return [element for element in root.iter("widget") if element.get("class") in ("QDateEdit", "QDateTimeEdit")]


def _build(path, owner):
    module = importlib.import_module("jal.ui.widgets.ui_" + path.stem)
    ui = getattr(module, next(name for name in dir(module) if name.startswith("Ui_")))()
    ui.setupUi(QWidget(owner))
    return ui


@pytest.mark.parametrize("path", OPERATION_FORMS, ids=lambda path: path.name)
def test_operation_forms_fix_the_clock_of_every_date_editor(path):
    local = []
    for element in _date_editors(ET.parse(path).getroot()):
        spec = element.find("./property[@name='timeSpec']/enum")
        if spec is None or not spec.text.endswith("UTC"):
            local.append(element.get("name"))
    assert not local, f"{path.name}: {local} are left on the clock of whatever machine the form is opened on"


# ... and what the form is built into has to behave that way: the day it renders is the day that was stored, and
# the day the user leaves in it is the day that comes back. Qt 6.11 happens to keep an unconfigured editor on the
# clock of the value it was handed, which is the right answer by accident - the declaration above is what makes it
# the answer on purpose.
@pytest.mark.parametrize("path", OPERATION_FORMS, ids=lambda path: path.name)
def test_a_date_editor_keeps_the_day_it_was_given(path, owner):
    with pinned_tz('Etc/GMT+5'):     # POSIX inverts the sign: a fixed UTC-5 zone, where a day-boundary error shows
        ui = _build(path, owner)
        for element in _date_editors(ET.parse(path).getroot()):
            editor = getattr(ui, element.get("name"))
            stored = 1758758400                                             # 2025-09-25 00:00:00 UTC
            editor.setDateTime(QDateTime.fromSecsSinceEpoch(stored, QTimeZone(0)))    # setEditorData() does this
            assert editor.date().toString('yyyy-MM-dd') == '2025-09-25', element.get("name")
            editor.setDate(QDate(2025, 9, 26))                              # ... and the user moves it a day on
            assert editor.dateTime().toSecsSinceEpoch() == stored + 86400, element.get("name")  # setModelData() reads


# ----------------------------------------------------------------------------------------------------------------------
# 'Now' has one spelling in the application - now_ts() - and it is the wall clock, because that is the clock every
# stored timestamp is written on. Anything that measures a stored value against the true UTC instant instead is out
# by the local offset: a quote goes stale hours early, a bond expires on the wrong side of midnight, and a chain
# balance read this evening lands beyond the end of today.
def test_now_is_the_wall_clock_and_not_the_instant(fixed_tz):
    assert now_ts() - int(datetime.now(tz=timezone.utc).timestamp()) == pytest.approx(fixed_tz, abs=1)


# An editor is pre-filled with the same moment that would be stored for it, or an operation entered without touching
# the date field is dated an offset away from when the user entered it.
def test_now_dt_is_the_moment_now_ts_would_store(fixed_tz):
    assert now_dt().toSecsSinceEpoch() == pytest.approx(now_ts(), abs=1)


# The days left to an expiry are counted between two moments on the same clock. Ten days less a minute is nine days
# left, whatever the machine's offset - mixing the clocks turns it back into ten.
def test_days_to_expiration_counts_on_the_stored_clock(prepare_db, fixed_tz):
    create_assets([('XYZ', 'Test bond', '', 2, PredefinedAsset.Bond, 0)])   # asset id 4
    asset = JalAsset(4)
    asset.update_data({'expiry': now_ts() + 10 * 86400 - 60})
    assert asset.days2expiration() == 9
    asset.update_data({'expiry': now_ts() - 2 * 86400 - 60})
    assert asset.days2expiration() == -2


# ----------------------------------------------------------------------------------------------------------------------
# A tax year is a HALF-OPEN window. 'year_end' is already the first second of the NEXT year (see
# TaxReport.prepare_tax_report), so testing it with '<=' puts an operation stamped at midnight on 1 January into two
# consecutive reports at once - declared, and taxed, twice. Statement importers produce exactly such timestamps
# whenever a source gives a date without a time.
def test_a_payment_at_new_year_midnight_belongs_to_one_year_only(prepare_db_taxes):
    create_assets([('GE', 'General Electric Company', 'US3696043013', 2, PredefinedAsset.Stock, 'us')])   # id 4
    midnight = d2t(250101)
    create_dividends([(midnight, 1, 4, 10.0, 1.0, "Dividend paid at the turn of the year")])
    report = TaxesRussia()
    report.account = JalAccount(1)
    for year, expected in [(2024, []), (2025, [midnight])]:
        report.year_begin = d2t(year % 100 * 10000 + 101)
        report.year_end = d2t((year + 1) % 100 * 10000 + 101)
        assert [x.timestamp() for x in report.dividends_list()] == expected


# The money and asset flows of a year are the same window, and the report they feed states the year's opening and
# closing balances beside them - a movement counted in two years cannot be reconciled against either.
def test_a_movement_at_new_year_midnight_flows_in_one_year_only(prepare_db):
    account = JalAccountCreator(currency_id=2, number='X1', name='Test', investing=0).commit()
    create_actions([(d2t(250101), account.id(), 1, [(PredefinedCategory.Interest, Decimal('100'))])])
    Ledger().rebuild(from_timestamp=0)
    assert account.get_flow(d2t(240101), d2t(250101), JalAccount.MONEY_FLOW, 'in') == Decimal('0')
    assert account.get_flow(d2t(250101), d2t(260101), JalAccount.MONEY_FLOW, 'in') == Decimal('100')


# ----------------------------------------------------------------------------------------------------------------------
# The moment a fixture names, as a stored timestamp - spelled out here because the shifts under test are hours and
# minutes, which the YYMMDD helpers of tests/helpers.py cannot express.
def _stamp(year, month, day, hour=0, minute=0, second=0) -> int:
    return int(datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp())


# A statement reports a wall-clock reading and never says which clock. Stamping those digits as they are puts an
# operation an offset away from everything entered by hand, so each module names the zone its source keeps its books
# in and the reading is converted once, at the boundary.
def test_a_source_reading_is_converted_from_the_zone_the_source_names(fixed_tz):
    statement = StatementKuCoin()                       # KuCoin writes UTC ("Time(UTC)" is its column label)
    assert statement.source_timezone == 'UTC'
    assert statement._timestamp('2025-09-25 12:28:12') - _stamp(2025, 9, 25, 12, 28, 12) == fixed_tz


# ... and a source that names no zone keeps its digits, which is what every module did before any of them declared one.
def test_an_undeclared_source_keeps_its_reading(fixed_tz):
    statement = StatementKuCoin()
    statement.source_timezone = ''
    assert statement._timestamp('2025-09-25 12:28:12') == _stamp(2025, 9, 25, 12, 28, 12)


# The conversion is an identity exactly when the machine runs on the zone the source reports in - which is what lets
# the golden fixtures of tests/test_statements_cex.py be pinned to UTC and stay the moments they name.
def test_a_source_reading_is_untouched_when_the_clocks_agree():
    with pinned_tz('UTC'):
        assert StatementKuCoin()._timestamp('2025-09-25 12:28:12') == _stamp(2025, 9, 25, 12, 28, 12)


# Every source that reports an absolute instant instead of a wall clock reaches the very same stored clock, or a
# chain operation and the exchange withdrawal that funded it are ordered by their offsets rather than by what
# happened first.
def test_an_instant_and_a_utc_reading_land_on_the_same_stored_clock(fixed_tz):
    instant = _stamp(2025, 9, 25, 12, 28, 12)           # what a chain reports for that moment: absolute UTC seconds
    assert local_timestamp(instant) == StatementKuCoin()._timestamp('2025-09-25 12:28:12')
    assert local_timestamp(instant) - instant == fixed_tz


# A date has no time of day to convert and shifting it can only turn it into a different date - a settlement day, an
# ex-date or the bounds of a reporting period must read the same whatever zone the source or the machine keeps.
def test_a_reported_date_is_never_shifted(fixed_tz):
    statement = StatementKuCoin()
    assert statement._date(datetime(2025, 9, 25)) == d2t(250925)
    statement.source_timezone = 'America/New_York'
    assert statement._date(datetime(2025, 9, 25)) == d2t(250925)


# The offset in force at the operation's own instant is used, not today's - Moscow kept DST until 2011, so the same
# wall-clock reading is a different moment in summer and in winter.
def test_the_offset_of_the_operation_is_used_and_not_the_current_one():
    statement = StatementKuCoin()
    statement.source_timezone = 'Europe/Moscow'
    with pinned_tz('UTC'):
        assert statement._timestamp('2010-07-01 12:00:00') == _stamp(2010, 7, 1, 8)    # UTC+4, Moscow summer time
        assert statement._timestamp('2010-12-01 12:00:00') == _stamp(2010, 12, 1, 9)   # UTC+3, Moscow winter time


# An XML statement writes both kinds of fact into attributes that look alike, and only the written form tells them
# apart: "20250925;122812" is a moment and "20250925" is a calendar day. Reading the second as the first would
# convert a settlement day or an ex-date out of its own date. The zone is declared here rather than taken from
# StatementIBKR, which deliberately declares none - see the comment on it.
def test_an_xml_attribute_is_a_moment_or_a_day_by_the_form_it_is_written_in(fixed_tz):
    class ZonedStatement(StatementIBKR):
        source_timezone = 'America/New_York'
    statement = ZonedStatement()
    element = etree.fromstring('<Trade dateTime="20250925;122812" settleDateTarget="20250929"/>')
    assert statement.attr_timestamp(element, 'dateTime', None) == _stamp(2025, 9, 25, 16, 28, 12) + fixed_tz
    assert statement.attr_timestamp(element, 'settleDateTarget', None) == d2t(250929)


# IBKR itself is left on no zone at all, so what it reports is stored as the digits it wrote. Its end-of-day marker
# is the reason: 20:20 is not a time the payment happened, it is the day it belongs to - and a converted marker
# lands on the next one. The tax corrections that arrive months later are matched to their dividend against what is
# already stored, so the reading has to keep meaning what it meant when that row was written.
def test_ibkr_readings_are_stored_as_the_source_wrote_them():
    statement = StatementIBKR()
    assert statement.source_timezone == ''
    element = etree.fromstring('<CashTransaction dateTime="20241227;202000" settleDate="20241227"/>')
    for zone in ('Europe/Lisbon', 'Etc/GMT+5', 'UTC'):
        with pinned_tz(zone):
            stored = statement.attr_timestamp(element, 'dateTime', None)
            assert ts2d(stored) == ts2d(d2t(241227)), zone
            assert datetime.fromtimestamp(stored, tz=timezone.utc).strftime('%H:%M') == '20:20', zone
            assert statement.attr_timestamp(element, 'settleDate', None) == d2t(241227), zone


# ----------------------------------------------------------------------------------------------------------------------
# The other end of the same boundary. A tax report is filed in a country, and the days and years it counts are that
# country's - a stored reading is the user's own wall clock and has to be re-read on the clock of the jurisdiction
# before it is printed as a date or bucketed into a year.

# Puts the whole timeline on one zone: as far as these tests are concerned the user lived there from the beginning
def _resident_in(zone: str):
    JalDB._exec("UPDATE residence SET timezone=:zone", [(":zone", zone)])
    JalResidence.invalidate_cache()


# Gives a report the account and the year window that prepare_tax_report() would set up for it
def _report_for(report, year: int):
    report.account = JalAccount(1)
    report.account_currency = JalAsset(report.account.currency())
    report.year_begin = d2t(year % 100 * 10000 + 101)
    report.year_end = d2t((year + 1) % 100 * 10000 + 101)
    return report


def test_a_report_dates_a_moment_on_the_clock_of_the_country_it_is_filed_in(prepare_db_taxes):
    _resident_in('Europe/Lisbon')
    evening = _stamp(2025, 6, 10, 23, 30)                                # a summer evening in Lisbon, where...
    assert ts2d(TaxesPortugal()._moment(evening)) == ts2d(_stamp(2025, 6, 10))     # ... the report is filed at home
    assert ts2d(TaxesRussia()._moment(evening)) == ts2d(_stamp(2025, 6, 11))       # ... but Moscow is already asleep


# The year an operation is declared in follows that same clock: half past eleven on 31 December in Lisbon is the new
# year in Moscow, so the dividend belongs to the next Russian declaration and to no other.
def test_a_moment_late_at_night_belongs_to_the_next_tax_year_of_another_jurisdiction(prepare_db_taxes):
    create_assets([('GE', 'General Electric Company', 'US3696043013', 2, PredefinedAsset.Stock, 'us')])   # id 4
    new_year_eve = _stamp(2024, 12, 31, 23, 30)
    create_dividends([(new_year_eve, 1, 4, 10.0, 1.0, "Dividend paid late on New Year's eve")])
    _resident_in('Europe/Lisbon')

    assert [x.timestamp() for x in _report_for(TaxesRussia(), 2024).dividends_list()] == []
    assert [x.timestamp() for x in _report_for(TaxesRussia(), 2025).dividends_list()] == [new_year_eve]
    assert [x.timestamp() for x in _report_for(TaxesPortugal(), 2024).dividends_list()] == [new_year_eve]


# A day is not a moment. A settlement day, and a payment whose source stated the day without the hour, are both
# stored as the midnight they were given - and midnight has no time of day to re-read on another clock, so a report
# of another country must leave it alone. Read as a moment it would land on the day before, and here in the year
# before: a Portuguese report of a life lived in Moscow.
def test_a_day_stored_without_a_time_of_day_is_never_read_on_another_clock(prepare_db_taxes):
    create_assets([('GE', 'General Electric Company', 'US3696043013', 2, PredefinedAsset.Stock, 'us')])   # id 4
    create_trades(1, [(d2t(241220), d2t(241224), 4, Decimal('10'), Decimal('100'), Decimal('1')),
                      (d2t(241230), d2t(250101), 4, Decimal('-10'), Decimal('130'), Decimal('1'))])
    create_dividends([(d2t(250101), 1, 4, 10.0, 1.0, "Dividend dated by its day alone")])
    Ledger().rebuild(from_timestamp=0)
    _resident_in('Europe/Moscow')
    report = TaxesPortugal()

    assert report._moment(d2t(250101)) == d2t(250101)
    assert report._date(d2t(250101)) == d2t(250101)
    assert _report_for(report, 2024).trades_list([PredefinedAsset.Stock]) == []
    assert len(_report_for(report, 2025).trades_list([PredefinedAsset.Stock])) == 1
    assert [x.timestamp() for x in _report_for(report, 2025).dividends_list()] == [d2t(250101)]


# Midnight is not the only spelling of a day. A payment known only by the day it happened is entered by hand at the
# middle of that day, and noon states the day just as much as midnight does - is_day_marker() is what says so, and a
# report of another jurisdiction has to leave both alone. A minute either side is an ordinary moment again.
def test_a_payment_dated_by_the_middle_of_its_day_is_never_read_on_another_clock(prepare_db_taxes):
    create_assets([('GE', 'General Electric Company', 'US3696043013', 2, PredefinedAsset.Stock, 'us')])   # id 4
    noon = _stamp(2025, 6, 10, 12, 0)
    create_dividends([(noon, 1, 4, 10.0, 1.0, "Dividend known only by the day it happened")])
    _resident_in('Europe/Lisbon')
    report = TaxesRussia()

    assert report._moment(noon) == noon                            # untouched, though Moscow is two hours ahead
    assert report._moment(noon + 60) == noon + 60 + 2 * 3600       # a minute later is a moment, and it moves
    assert [x.timestamp() for x in _report_for(report, 2025).dividends_list()] == [noon]


# The end-of-day stamps a broker puts on an accounting day are that broker's alone, so they are NOT part of the
# common set: an evening entry on a cash account legitimately reads 20:20, and read as a day it would be frozen on
# the clock it was entered on. It is a moment, and a report filed eight hours to the east dates it on the next day.
def test_an_evening_spending_is_not_mistaken_for_an_end_of_day_marker(prepare_db_taxes):
    evening = _stamp(2025, 6, 10, 20, 20)
    create_actions([(evening, 1, 1, [(PredefinedCategory.Fees, Decimal('-10'))])])
    _resident_in('America/New_York')
    report = _report_for(TaxesRussia(), 2025)

    assert not is_day_marker(evening)
    assert is_day_marker(evening, IBKR_DAY_MARKERS)                # ... unless the caller names the source it came from
    assert ts2d(report._moment(evening)) == ts2d(_stamp(2025, 6, 11))
    assert len(report.category_operations(PredefinedCategory.Fees)) == 1


# The operations of a category are picked by the database, by timestamp, so the window has to be widened before the
# question is put to it - a fee that belongs to the report's year on the report's clock would otherwise never be
# fetched to be considered at all.
def test_a_fee_late_on_new_years_eve_reaches_the_report_of_the_year_it_falls_in(prepare_db_taxes):
    create_actions([(_stamp(2024, 12, 31, 23, 30), 1, 1, [(PredefinedCategory.Fees, Decimal('-10'))])])
    _resident_in('Europe/Lisbon')

    assert _report_for(TaxesRussia(), 2024).category_operations(PredefinedCategory.Fees) == []
    assert len(_report_for(TaxesRussia(), 2025).category_operations(PredefinedCategory.Fees)) == 1


# None of this happens until the user states where they lived, and a report that names no jurisdiction never asks:
# an unknown clock leaves every reading exactly as it is, which is what keeps today's reports what they were.
def test_nothing_moves_while_a_zone_is_unknown(prepare_db_taxes):
    evening = _stamp(2024, 12, 31, 23, 30)
    assert JalResidence.timezone(evening) == ''
    assert TaxesRussia()._moment(evening) == evening

    _resident_in('Europe/Lisbon')
    assert wall_clock_reading(evening, '') == evening


# ----------------------------------------------------------------------------------------------------------------------
# What to do with the readings already stored when the clock they were read on turns out to have been another one -
# the user enters a residence history reaching back over years already booked, or the application moves to storing
# instants. reclock() re-reads the digits, and reports what it would do before it is allowed to write anything.

@pytest.fixture
def reclock_db(prepare_db):
    JalAccountCreator(currency_id=2, number='M1', name='Moscow broker', investing=1).commit()   # account 1
    JalAccountCreator(currency_id=2, number='L1', name='Lisbon bank', investing=0).commit()     # account 2
    create_assets([('GE', 'General Electric Company', 'US3696043013', 2, PredefinedAsset.Stock, 'us')])   # asset 4
    yield


def _stored(table: str, column: str, oid: int) -> int:
    return int(JalDB._read(f"SELECT {column} FROM {table} WHERE oid=:oid", [(":oid", oid)]))


def _spending(timestamp: int, account_id: int) -> tuple:
    return timestamp, account_id, 1, [(PredefinedCategory.Fees, Decimal('-10'))]


def _column_report(report: dict, table: str, column: str = 'timestamp') -> dict:
    return next(x for x in report['columns'] if x['table'] == table and x['column'] == column)


# The command line lives outside the package, as the tool it is, so it is loaded by its path rather than imported
def _shift_clock():
    specification = importlib.util.spec_from_file_location(
        "shift_clock", pathlib.Path(__file__).resolve().parent.parent / "tools" / "shift_clock.py")
    tool = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(tool)
    return tool


def _exported(path: str) -> list:
    with open(path, newline='', encoding='utf-8-sig') as csv_file:
        return list(csv.reader(csv_file))


# The offset is not a number the run is given, it is a question asked of each row's own date: Moscow has stood at
# +3 since 2014 while Lisbon keeps summer time, so two readings of one account, one in July and one in December,
# are re-read two and three hours back respectively.
def test_a_summer_and_a_winter_reading_are_re_read_by_their_own_offsets(reclock_db):
    summer, winter = _stamp(2021, 7, 1, 15), _stamp(2021, 12, 1, 15)
    create_trades(1, [(summer, d2t(210702), 4, Decimal('10'), Decimal('100'), Decimal('1')),
                      (winter, d2t(211202), 4, Decimal('10'), Decimal('100'), Decimal('1'))])

    report = reclock('Europe/Moscow', 'Europe/Lisbon', apply=True)
    assert _stored('trades', 'timestamp', 1) == summer - 2 * 3600
    assert _stored('trades', 'timestamp', 2) == winter - 3 * 3600
    assert _column_report(report, 'trades')['changed'] == 2


# A reading that states a day is left exactly where it is - it carries no time of day to re-read, and re-reading it
# could only move it to another day. The end-of-day stamp of a source is one of those days, but only for the source
# it belongs to: the same digits on a cash account are an evening, and an evening is a moment like any other.
def test_a_reading_that_states_a_day_is_left_where_it_is(reclock_db):
    midnight, noon, end_of_day = d2t(210701), _stamp(2021, 7, 1, 12), _stamp(2021, 7, 1, 20, 20)
    create_actions([_spending(midnight, 2), _spending(noon, 2), _spending(end_of_day, 2)])

    report = reclock('Europe/Moscow', 'Europe/Lisbon', source_markers=IBKR_DAY_MARKERS, apply=True)
    assert _column_report(report, 'actions')['markers'] == 3
    assert _column_report(report, 'actions')['changed'] == 0
    assert [_stored('actions', 'timestamp', x) for x in (1, 2, 3)] == [midnight, noon, end_of_day]

    reclock('Europe/Moscow', 'Europe/Lisbon', apply=True)          # ... the same rows, with no source named
    assert [_stored('actions', 'timestamp', x) for x in (1, 2)] == [midnight, noon]
    assert _stored('actions', 'timestamp', 3) == end_of_day - 2 * 3600


# The dates an operation carries beside its moment are dates by definition, and they are not in the map at all -
# a settlement day and an ex-date belong to the day they name whatever clock anything else is read on.
def test_the_dates_of_an_operation_are_never_re_read(reclock_db):
    assert ('trades', 'settlement') not in [(table, column) for table, column, *_ in RECLOCKED_COLUMNS]
    assert ('asset_payments', 'ex_date') not in [(table, column) for table, column, *_ in RECLOCKED_COLUMNS]
    moment = _stamp(2021, 7, 1, 15)
    create_trades(1, [(moment, d2t(210705), 4, Decimal('10'), Decimal('100'), Decimal('1'))])
    create_dividends([(moment, 1, 4, 10.0, 1.0, "Dividend of the same day")])
    JalDB._exec("UPDATE asset_payments SET ex_date=:ex_date", [(":ex_date", d2t(210630))])

    reclock('Europe/Moscow', 'Europe/Lisbon', apply=True)
    assert _stored('trades', 'timestamp', 1) == moment - 2 * 3600      # the moment beside them did move...
    assert _stored('trades', 'settlement', 1) == d2t(210705)           # ... and neither of these did
    assert _stored('asset_payments', 'ex_date', 1) == d2t(210630)


# Two local times cannot be re-read without a choice being made: the hour a clock repeats when it goes back is two
# different moments spelled the same, and the hour it skips going forward never happened at all. Both are reported
# with the rows they are in, so the user decides what those rows meant instead of the run deciding silently.
def test_an_hour_the_clock_repeats_or_skips_is_reported_and_not_hidden(reclock_db):
    repeated = _stamp(2021, 10, 31, 1, 30)        # Lisbon puts its clock back that night, so 01:30 comes twice
    skipped = _stamp(2021, 3, 28, 1, 30)          # ... and forward in March, over an hour that never happens
    create_actions([_spending(repeated, 2), _spending(skipped, 2)])

    report = reclock('Europe/Lisbon', 'UTC')
    assert _column_report(report, 'actions')['ambiguous'] == [1]
    assert _column_report(report, 'actions')['nonexistent'] == [2]


# A marker is recognised by its value alone, so a run can MAKE one: three hours off Moscow turns a spending stored
# at three in the afternoon into noon, and everything downstream reads noon as a day rather than a moment. Those
# rows are counted while they can still be told apart - after the run nothing distinguishes them from a date that
# was always one.
def test_a_moment_that_lands_on_a_marker_is_counted_before_it_becomes_one(reclock_db):
    afternoon = _stamp(2021, 7, 1, 15)
    create_actions([_spending(afternoon, 2), _spending(afternoon + 60, 2)])

    report = reclock('Europe/Moscow', 'UTC')
    assert _column_report(report, 'actions')['changed'] == 2
    assert [(x['oid'], x['becomes'], x['account']) for x in _column_report(report, 'actions')['made_markers']] == \
           [(1, afternoon - 3 * 3600, 'Lisbon bank')]


# A dry run is the default, and it is the whole point of the tool: it says what would happen and touches nothing.
def test_a_dry_run_reports_everything_and_writes_nothing(reclock_db):
    moment = _stamp(2021, 7, 1, 15)
    create_actions([_spending(moment, 2)])

    report = reclock('Europe/Moscow', 'Europe/Lisbon')
    assert report['changed'] == 1 and report['applied'] is False
    assert _stored('actions', 'timestamp', 1) == moment


# Re-clocking is a reading of one instant on another clock, so reading it back on the first returns the digits it
# started from - a run made in the wrong direction, or with the wrong zone, is undone by its own inverse.
def test_a_round_trip_returns_every_reading_it_started_from(reclock_db):
    moments = [_stamp(2021, month, 15, 15, 17) for month in range(1, 13)]
    create_actions([_spending(x, 2) for x in moments])

    reclock('Europe/Moscow', 'America/New_York', apply=True)
    reclock('America/New_York', 'Europe/Moscow', apply=True)
    assert [_stored('actions', 'timestamp', x) for x in range(1, 13)] == moments


# Each account was kept on its own clock - the RU brokers of a user who had already moved, IBKR on its own - so a
# run names the accounts it is about, and everything else keeps the digits it has.
def test_only_the_accounts_the_run_names_are_re_read(reclock_db):
    moment = _stamp(2021, 7, 1, 15)
    create_actions([_spending(moment, 1), _spending(moment, 2)])

    reclock('Europe/Moscow', 'Europe/Lisbon', accounts=[1], apply=True)
    assert _stored('actions', 'timestamp', 1) == moment - 2 * 3600
    assert _stored('actions', 'timestamp', 2) == moment


# The window is stated in the clock the digits are stored on, which is the one the application shows - a row outside
# it is not selected at all, however far the run would have moved it.
def test_the_window_is_read_in_the_clock_the_digits_are_stored_on(reclock_db):
    inside, outside = _stamp(2021, 7, 1, 15), _stamp(2021, 7, 3, 15)
    create_actions([_spending(inside, 2), _spending(outside, 2)])

    report = reclock('Europe/Moscow', 'Europe/Lisbon', begin=d2t(210701), end=_stamp(2021, 7, 2, 23, 59, 59), apply=True)
    assert _column_report(report, 'actions')['selected'] == 1
    assert _stored('actions', 'timestamp', 1) == inside - 2 * 3600
    assert _stored('actions', 'timestamp', 2) == outside


# An operation that holds two moments may have one of them re-read and not the other - the two ends were booked on
# different accounts, and the run is about one of them. That can put the arrival before the departure, which is
# legitimate when the clocks are hours apart but has to be seen rather than found later by the ledger.
def test_a_leg_that_ends_up_before_the_one_it_follows_is_reported(reclock_db):
    departure, arrival = _stamp(2021, 7, 1, 10), _stamp(2021, 7, 1, 10, 30)
    oid = create_transfers([(departure, 1, Decimal('100'), 2, Decimal('100'), None)])[0]
    JalDB._exec("UPDATE transfers SET deposit_timestamp=:arrival WHERE oid=:oid",
                [(":arrival", arrival), (":oid", oid)])

    report = reclock('Europe/Lisbon', 'Europe/Moscow', accounts=[1])   # the sending end alone, two hours forward
    assert [x['oid'] for x in report['reordered']] == [oid]
    assert report['reordered'][0]['after'] == (departure + 2 * 3600, arrival)
    assert report['reordered'][0]['already'] is False
    assert report['reordered'][0]['departure_account'] == 'Moscow broker'
    assert report['reordered'][0]['arrival_account'] == 'Lisbon bank'
    assert _column_report(report, 'transfers', 'deposit_timestamp')['selected'] == 0


# A pair that is already stored with its arrival before its departure is reported too, and marked as such: the run
# is not what put it that way - somebody may well have done it by hand to make the ledger read right - but the run
# is what moves it, and that correction is about to be overwritten.
def test_a_pair_that_was_already_out_of_order_is_reported_as_such(reclock_db):
    departure, arrival = _stamp(2021, 7, 1, 10), _stamp(2021, 7, 1, 9, 30)     # the arrival stands first already
    oid = create_transfers([(departure, 1, Decimal('100'), 2, Decimal('100'), None)])[0]
    JalDB._exec("UPDATE transfers SET deposit_timestamp=:arrival WHERE oid=:oid",
                [(":arrival", arrival), (":oid", oid)])

    report = reclock('Europe/Lisbon', 'Europe/Moscow', accounts=[1])
    assert [(x['oid'], x['already']) for x in report['reordered']] == [(oid, True)]


# Whole groups of accounts move together - every RU broker, everything that is not already on UTC - and a group is
# as often stated by what it leaves out as by what it holds. An exclusion applies to whatever was selected, so
# "everything except these" needs no account named at all.
def test_an_excluded_account_is_left_alone_however_it_was_selected(reclock_db):
    moment = _stamp(2021, 7, 1, 15)
    create_actions([_spending(moment, 1), _spending(moment, 2)])

    report = reclock('Europe/Moscow', 'Europe/Lisbon', excluded=[2])
    assert _column_report(report, 'actions')['selected'] == 1
    report = reclock('Europe/Moscow', 'Europe/Lisbon', accounts=[1, 2], excluded=[2], apply=True)
    assert _column_report(report, 'actions')['selected'] == 1
    assert _stored('actions', 'timestamp', 1) == moment - 2 * 3600
    assert _stored('actions', 'timestamp', 2) == moment


# The moment an account was last reconciled is a reading of the same clock, and it is compared straight against
# operation timestamps - left behind, it would move the reconciled mark of every operation within the offset of it.
# It is in the window like anything else, and 'never reconciled' is stored as a zero, which is a day marker.
def test_the_reconciliation_of_an_account_is_re_read_with_its_operations(reclock_db):
    reconciled = _stamp(2021, 7, 1, 15)
    JalDB._exec("UPDATE accounts SET reconciled_on=:moment WHERE id=1", [(":moment", reconciled)])

    reclock('Europe/Moscow', 'Europe/Lisbon', end=_stamp(2021, 6, 30, 23, 59, 59), apply=True)
    assert _stored('accounts', 'reconciled_on', 1) == reconciled          # outside the window, so untouched

    reclock('Europe/Moscow', 'Europe/Lisbon', apply=True)
    assert _stored('accounts', 'reconciled_on', 1) == reconciled - 2 * 3600
    assert _stored('accounts', 'reconciled_on', 2) == 0                   # never reconciled, and it stays that way


# The tool that drives the engine takes accounts by name, and a database may hold hundreds of them - a term deposit
# is one account each. ALL (or ANY) is how they are all asked for without naming a single one, and a name that
# matches nothing stops the run instead of quietly leaving that account behind.
def test_the_command_line_takes_all_the_accounts_without_naming_them(reclock_db):
    tool = _shift_clock()

    assert tool.account_ids(None) is None                 # naming nothing at all means every account, too
    assert tool.account_ids(['ALL']) is None
    assert tool.account_ids(['any']) is None
    assert tool.account_ids(['Lisbon bank']) == [2]
    assert tool.account_ids(['Moscow broker', 'Lisbon bank']) == [1, 2]
    assert tool.named_ids(None) == []                      # ... but nothing excluded is nothing excluded
    assert tool.named_ids(['Lisbon bank']) == [2]
    for names in (['Moscow broker', 'Ministry of Finance'], ['ALL']):   # the keyword is no account of --except
        with pytest.raises(SystemExit):
            tool.named_ids(names)


# Both findings are written out to be gone through row by row, which a report of counts cannot be. The markers a run
# makes are exported by the dry run alone - it is the last moment at which the two readings can be seen side by side.
def test_the_findings_are_exported_for_review(reclock_db, tmp_path):
    tool, prefix = _shift_clock(), str(tmp_path / "run")
    afternoon = _stamp(2021, 7, 1, 15)
    create_actions([_spending(afternoon, 2)])
    oid = create_transfers([(_stamp(2021, 7, 1, 10), 1, Decimal('100'), 2, Decimal('100'), None)])[0]
    JalDB._exec("UPDATE transfers SET deposit_timestamp=:arrival WHERE oid=:oid",
                [(":arrival", _stamp(2021, 7, 1, 10, 30)), (":oid", oid)])

    report = reclock('Europe/Moscow', 'UTC', accounts=[1, 2])
    markers = _exported(tool.export_made_markers(prefix, report))
    assert markers[0] == ["operation", "column", "id", "account", "stored", "becomes", "marker", "note"]
    assert markers[1][:4] == ["actions", "timestamp", "1", "Lisbon bank"]
    assert markers[1][5:7] == ["2021-07-01 12:00:00", "12:00:00"]

    report = reclock('Europe/Lisbon', 'Europe/Moscow', accounts=[1])
    legs = _exported(tool.export_reordered_legs(prefix, report))
    assert legs[0][:2] == ["operation", "id"] and legs[0][6] == "already_reordered"
    assert legs[1][:6] == ["transfers", "1", "2021-07-01 10:00:00", "2021-07-01 12:00:00",
                           "2021-07-01 10:30:00", "2021-07-01 10:30:00"]
    assert legs[1][6:9] == ["", "Moscow broker", "Lisbon bank"]

    assert tool.export_reordered_legs(prefix, reclock('UTC', 'UTC')) == ''    # nothing found, nothing written
    tool.print_report(report, {'reordered': prefix})   # ... and the report the user actually reads is printable
