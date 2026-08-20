import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib
import pathlib
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import QDate, QDateTime, QTimeZone
from PySide6.QtWidgets import QWidget

from constants import PredefinedAsset
from jal.db.asset import JalAsset
from jal.db.helpers import now_ts, now_dt
from jal.widgets.helpers import ts2axis, axis2ts, ts2d
from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_assets


# A test here pins the machine to a fixed zone, because what is under test is precisely the difference between the
# clock a timestamp is stored on and the clock the machine runs on.
@contextmanager
def pinned_tz(zone: str):
    saved = os.environ.get('TZ')
    os.environ['TZ'] = zone
    time.tzset()
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = saved
        time.tzset()


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
