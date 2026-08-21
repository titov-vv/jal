from bisect import bisect_right
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from jal.db.db import JalDB
from jal.db.helpers import day_begin, now_ts
from jal.universal_cache import UniversalCache


# ----------------------------------------------------------------------------------------------------------------------
# Where the user lived, as a timeline: one row of the 'residence' table per change, in force from its own date until
# the next one. A row carries three facts - the currency reports are made in, the country and the wall clock - and a
# row need not state all of them: 'country_id' 0 and an empty 'timezone' mean "this row doesn't say", in which case
# the last row that did say still holds. That carrying forward is done once, while the timeline is loaded, so that
# asking for a moment is a single bisect over dates.
#
# The timeline is asked for every timestamp that gets displayed or bucketed into a tax day, so it is kept in memory
# rather than queried each time - a query costs more than formatting the date it is needed for. It is written in one
# place only, the residence dialog, which drops the cache when it commits; restoring a database asks for a restart,
# so nothing else can leave the cache stale.
class JalResidence(JalDB):
    db_cache = UniversalCache()

    @classmethod
    def invalidate_cache(cls) -> None:
        cls.db_cache.clear_cache()

    # Returns the timeline as two parallel lists: the dates rows are in force from, and the (currency, country,
    # timezone) each of them states - with the facts of the earlier rows already carried forward.
    @classmethod
    def _load_timeline(cls) -> tuple:
        dates, rows = [], []
        currency = country = 0
        zone = ''
        query = cls._exec("SELECT since_timestamp, currency_id, country_id, timezone FROM residence "
                          "ORDER BY since_timestamp")
        while query.next():
            since, row_currency, row_country, row_zone = cls._read_record(query, cast=[int, int, int, str])
            currency = row_currency if row_currency else currency
            country = row_country if row_country else country
            zone = row_zone if row_zone else zone
            dates.append(since)
            rows.append((currency, country, zone))
        return dates, rows

    @classmethod
    def _timeline(cls) -> tuple:
        return cls.db_cache.get_data(cls._load_timeline)

    # The residence in force at the given moment, or today's one if no moment is given. Answers with an empty
    # residence for a moment that precedes the whole timeline - there is nothing to derive it from.
    @classmethod
    def _at(cls, timestamp: int = None) -> tuple:
        if timestamp is None:
            timestamp = day_begin(now_ts())
        dates, rows = cls._timeline()
        position = bisect_right(dates, timestamp)
        return rows[position - 1] if position else (0, 0, '')

    # Id of the currency the user reported in at the given moment (0 if the timeline doesn't reach that far back)
    @classmethod
    def currency(cls, timestamp: int = None) -> int:
        return cls._at(timestamp)[0]

    # Id of the country the user lived in at the given moment, or 0 if it was never stated for that moment
    @classmethod
    def country(cls, timestamp: int = None) -> int:
        return cls._at(timestamp)[1]

    # IANA name of the zone the user's wall clock was on at the given moment. Empty if the timeline doesn't state
    # one for that moment - a caller then keeps doing whatever it did before, as a fact the user never entered
    # can't be guessed for them.
    @classmethod
    def timezone(cls, timestamp: int = None) -> str:
        return cls._at(timestamp)[2]


# ----------------------------------------------------------------------------------------------------------------------
# The reading that the wall clock of 'zone' showed at the moment JAL stores as 'timestamp'. A stored timestamp is the
# reading of the user's own clock (see stored_timestamp), so the digits are turned back into an instant with the zone
# the user was on then, and that instant is read again on the zone asked for. The answer keeps the same shape it was
# given - the digits of a reading, spelled as a UTC epoch.
#
# A report filed in another country needs exactly this: a trade made at 23:30 in Lisbon happened at 01:30 of the next
# day in Moscow, and the day is what it is taxed in. The reading is returned untouched while either zone is unknown,
# so nothing moves until the user states where they lived.
def wall_clock_reading(timestamp: int, zone: str) -> int:
    home = JalResidence.timezone(timestamp)
    if not zone or not home or zone == home:
        return timestamp
    instant = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=ZoneInfo(home))
    return int(instant.astimezone(ZoneInfo(zone)).replace(tzinfo=timezone.utc).timestamp())


# ----------------------------------------------------------------------------------------------------------------------
# The inverse of wall_clock_reading(): the timestamp JAL stores for the moment at which the wall clock of 'zone' showed
# the given digits. A report whose year is a jurisdiction's needs this side of the mapping whenever the year is put to
# the DATABASE rather than to a row already fetched - the stored readings can't be re-read one by one inside a query,
# so it is the bounds of the window that are re-read instead. It also answers "which instant was the jurisdiction's 1
# January", which is what a balance taken at the turn of the year is a balance at.
#
# The zone the user was on is looked up by the reading given rather than by the answer returned, because the residence
# timeline is keyed on stored digits as well. That makes the inverse exact everywhere except within a few hours of a
# move, and there it errs by those hours.
def stored_reading(reading: int, zone: str) -> int:
    home = JalResidence.timezone(reading)
    if not zone or not home or zone == home:
        return reading
    instant = datetime.fromtimestamp(reading, tz=timezone.utc).replace(tzinfo=ZoneInfo(zone))
    return int(instant.astimezone(ZoneInfo(home)).replace(tzinfo=timezone.utc).timestamp())
