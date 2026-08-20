import os
import time
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import QDateTime

from jal.widgets.helpers import ts2axis, axis2ts, ts2d


# Every test here pins the machine to a fixed zone, because what is under test is precisely the difference between
# the clock a timestamp is stored on and the clock the machine runs on. The offset is returned so a test can state
# the expected shift in terms of it instead of repeating the number.
@pytest.fixture
def fixed_tz():
    saved = os.environ.get('TZ')
    os.environ['TZ'] = 'Etc/GMT-2'        # POSIX inverts the sign: this is a fixed UTC+2 zone, no DST
    time.tzset()
    yield 2 * 3600
    if saved is None:
        os.environ.pop('TZ', None)
    else:
        os.environ['TZ'] = saved
    time.tzset()


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
