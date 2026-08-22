from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from PySide6.QtCore import QDate, QTime, QDateTime, QTimeZone
from jal.db.helpers import is_day_marker, now_ts
from jal.db.residence import JalResidence


# ----------------------------------------------------------------------------------------------------------------------
# The clock the application is read on.
#
# JAL stores an INSTANT - plain UTC seconds, the same number wherever the database is opened. What a person sees,
# types on a form and files a tax return on is a READING: the digits their own clock showed at that instant. The two
# differ by the offset in force then, and which offset that was is a fact about the person rather than about the row
# - the residence timeline is what holds it (see JalResidence).
#
# This module is the single place the two meet. Everything that displays a timestamp, and every editor that returns
# one, goes through the few functions below instead of looking a zone up for itself, so there is one answer to
# "which clock is this shown on" and one place to change it.
#
# A reading is spelled as a UTC epoch of its own digits, which is how JAL spelled every timestamp before it stored
# instants: strftime() then prints it without a second conversion, and it stays directly comparable with the year
# bounds a tax report counts in.
#
# Two rules everything passing through here obeys:
#   - a DAY MARKER is never re-read (see is_day_marker). It states a day and holds no time of day to convert, so it
#     reads the same on every clock - which is what makes the dates of 22 years read after the move to instants
#     exactly as they read before it;
#   - while the timeline states no zone, the reading IS the stored value. A database whose owner never said where
#     they lived behaves as it always did, and nothing in it appears to move.
# ----------------------------------------------------------------------------------------------------------------------


# Wider than any gap between two wall clocks (the farthest apart are 26 hours), so a window widened by it can't miss
# a row that belongs inside it on another clock than the one the query was written in.
ZONE_SPAN = 2 * 24 * 60 * 60


# The IANA zone of the user's own clock at the given instant, or of today's if none is given. Empty while the
# timeline doesn't say - see the second rule above.
def user_zone(timestamp: int = None) -> str:
    return JalResidence.timezone(timestamp)


# The reading that the wall clock of 'zone' showed at the stored instant 'timestamp'. Same shape in and out: the
# digits of a reading, spelled as a UTC epoch.
#
# A report filed in another country needs exactly this - a trade made at 23:30 in Lisbon happened at 01:30 of the
# next day in Moscow, and the day is what it is taxed in.
def wall_clock_reading(timestamp: int, zone: str) -> int:
    if not zone or not user_zone(timestamp):
        return timestamp
    return int(datetime.fromtimestamp(timestamp, tz=ZoneInfo(zone)).replace(tzinfo=timezone.utc).timestamp())


# The inverse: the instant at which the wall clock of 'zone' showed the given digits. A report whose year is a
# jurisdiction's needs this side of the mapping whenever the year is put to the DATABASE rather than to a row
# already fetched - stored instants can't be re-read one at a time inside a query, so it is the bounds of the window
# that are re-read instead. It also answers "which instant was the jurisdiction's 1 January", which is what a
# balance taken at the turn of the year is a balance at.
#
# The zone the user was on is looked up by the reading given rather than by the instant returned, the timeline being
# keyed on dates rather than on either. That makes the inverse exact everywhere except within hours of a move.
def stored_reading(reading: int, zone: str) -> int:
    if not zone or not user_zone(reading):
        return reading
    return int(datetime.fromtimestamp(reading, tz=timezone.utc).replace(tzinfo=ZoneInfo(zone)).timestamp())


# ----------------------------------------------------------------------------------------------------------------------
# The reader - a stored instant as the user's own clock showed it, in the three shapes the application asks for: a
# Python datetime to format, a Qt datetime to hand an editor, and the bare digits to compare or to print.
def local_time(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=_zone(_reading_zone(timestamp)))


def local_reading(timestamp: int) -> int:
    return int(local_time(timestamp).replace(tzinfo=timezone.utc).timestamp())


def local_datetime(timestamp: int) -> QDateTime:
    return QDateTime.fromSecsSinceEpoch(timestamp, local_zone(timestamp))


# The instant a reading of the user's own clock names - the writer to the reader above, and its exact inverse: a day
# marker states a day, a day is the same day on every clock, and neither of them moves one.
def local_moment(reading: int) -> int:
    return reading if is_day_marker(reading) else stored_reading(reading, user_zone(reading))


# The instant at which the user's own clock reached these digits, for a BOUND the user stated rather than a value
# read off a row: the day a date field names, the first second of a month a report counts by. Midnight is where such
# a bound usually falls, and there it opens a day instead of naming one - so, unlike local_moment() above, it is
# converted like any other reading.
def window_bound(reading: int) -> int:
    return stored_reading(reading, user_zone(reading))


# The zone a QDateTime or a QDateTimeEdit holding this instant is kept on. Qt converts in both directions once it is
# set, so an editor given this zone renders the user's own reading and returns the instant the digits left in it
# stand for - which is why this module has no separate writer for editors.
def local_zone(timestamp: int = None) -> QTimeZone:
    return _qt_zone(_reading_zone(timestamp) if timestamp is not None else user_zone())


# 'Now' as an editor has to be pre-filled with it, or an operation entered without touching the date field is dated
# an offset away from when the user entered it. Today's zone is asked for rather than the moment's: a 'now' that
# happens to land on midnight is still a moment, not a day being named.
def now_dt() -> QDateTime:
    return QDateTime.fromSecsSinceEpoch(now_ts(), local_zone())


# ----------------------------------------------------------------------------------------------------------------------
# A day the user picked in a date field, as the instants that bound it on the user's own clock. A holdings date, a
# report date and the ends of a date range are days rather than moments, and the money in an account at the end of a
# day is the money there when that day ended where the user was, not when it ended in Greenwich.
def day_start(date: QDate) -> int:
    return date.startOfDay(_zone_of_day(date)).toSecsSinceEpoch()


def day_finish(date: QDate) -> int:
    return date.endOfDay(_zone_of_day(date)).toSecsSinceEpoch()


def today_finish() -> int:
    return day_finish(now_dt().date())


# ----------------------------------------------------------------------------------------------------------------------
def _zone(name: str):
    return ZoneInfo(name) if name else timezone.utc


def _qt_zone(name: str) -> QTimeZone:
    return QTimeZone(name.encode()) if name else QTimeZone(QTimeZone.UTC)


# The zone a stored instant is read on: the user's own, except that a day marker is read on none - see the rules at
# the top of this module.
def _reading_zone(timestamp: int) -> str:
    return '' if is_day_marker(timestamp) else user_zone(timestamp)


# The timeline is asked about a day by the middle of it, which is inside that day whatever the offset - and a day is
# all the question needs, the answer changing only on the day of a move.
def _zone_of_day(date: QDate) -> QTimeZone:
    return _qt_zone(user_zone(QDateTime(date, QTime(12, 0), QTimeZone(QTimeZone.UTC)).toSecsSinceEpoch()))
