from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from jal.db.db import JalDB
from jal.db.helpers import day_begin, year_begin, is_day_marker
from jal.db.settings import JalSettings


# ----------------------------------------------------------------------------------------------------------------------
# Re-reading stored timestamps on another clock.
#
# A stored timestamp is a wall-clock READING spelled as a UTC epoch (see stored_timestamp), so it only means anything
# together with the clock it was read on. When that clock turns out to have been another one - the user moved and
# entered the earlier years afterwards, or a source stamped its own zone into what was imported - the digits have to
# be re-read:
#
#     digits -> attached to the clock they were read on -> a true instant -> read again on the clock asked for
#
# It is never an hour delta: zoneinfo takes the offset from each row's own local date, so a summer row and a winter
# row of the same account move by different amounts and DST needs no table of rules here. Asking for 'UTC' as the
# target is what stops storing a reading and starts storing the instant itself.
#
# Two local times can't be re-read without a choice being made, and both are reported rather than silently resolved:
# the hour repeated at a fall-back transition is ambiguous (fold=0, the first of the two, is taken) and the hour
# skipped at spring-forward never existed (Python answers with the offset in force before the gap).


# Every stored timestamp that is a wall-clock reading, as (table, timestamp column, the account whose clock it was
# read on, what to show about the row). The last two are SQL expressions over 'o', the row of the table named first.
#
# A multi-leg operation is listed leg by leg, because each leg's digits came from its own source: the two ends of a
# cross-chain swap may sit on different clocks, and a run that names one account moves the leg on that account only.
# A leg whose account column is NULL means "the same account as the other leg" and is resolved as such.
#
# NEVER re-clocked, and deliberately absent from this map:
#   trades.settlement, asset_payments.ex_date, residence.since_timestamp - dates by definition, they state a day
#     and carry no time of day to convert;
#   ledger, ledger_totals, trades_opened, trades_closed - rebuilt from the operations, see the rebuild flag below;
#   quotes, chain_balances, token_list_updates - re-downloaded from their source, which has its own clock.
RECLOCKED_COLUMNS = (
    ("actions", "timestamp", "o.account_id", "o.note"),
    ("asset_actions", "timestamp", "o.account_id", "o.note"),
    ("asset_payments", "timestamp", "o.account_id", "o.note"),
    ("conversions", "timestamp", "o.account_id", "o.note"),
    ("swaps", "timestamp", "o.account_id", "o.note"),
    ("swaps", "in_timestamp", "COALESCE(o.in_account_id, o.account_id)", "o.note"),
    ("trades", "timestamp", "o.account_id", "o.note"),
    ("transfers", "withdrawal_timestamp", "o.withdrawal_account", "o.note"),
    ("transfers", "deposit_timestamp", "o.deposit_account", "o.note"),
    ("bridges", "out_timestamp", "o.out_account_id", "o.note"),
    ("bridges", "in_timestamp", "COALESCE(o.in_account_id, o.out_account_id)", "o.note"),
    # Not an operation, but a reading of the same clock: the moment an account was last confirmed against its
    # statement is compared straight against operation timestamps (see LedgerTransaction._reconciled), so leaving it
    # behind would move the reconciled mark of every operation within the offset of it. Never confirmed is stored as
    # 0, which is a day marker and is left alone like any other.
    ("accounts", "reconciled_on", "o.id", "''"),
)

# The operations that hold two moments, as (table, earlier leg, later leg). Moving one leg and not the other can put
# the arrival before the departure - legitimate enough when the two ends were read on clocks hours apart, but it has
# to be seen rather than discovered later by the ledger. Pairs that are already stored in that order are reported
# too, and marked as such: some of them were put there by hand, and a run that moves either leg undoes that.
PAIRED_COLUMNS = (
    ("transfers", "withdrawal_timestamp", "deposit_timestamp"),
    ("swaps", "timestamp", "in_timestamp"),
    ("bridges", "out_timestamp", "in_timestamp"),
)


# The reading that the wall clock of 'target' showed at the moment whose reading on 'source' is 'timestamp'.
# Same shape in and out - the digits of a reading, spelled as a UTC epoch.
def reclocked(timestamp: int, source: str, target: str) -> int:
    moment = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=ZoneInfo(source))
    return int(moment.astimezone(ZoneInfo(target)).replace(tzinfo=timezone.utc).timestamp())


# Whether the local time these digits spell exists once, twice or not at all on the clock they are read on.
# Returns '' for the ordinary case, 'ambiguous' for the hour a fall-back transition repeats and 'nonexistent' for
# the hour a spring-forward transition skips.
def clock_anomaly(timestamp: int, source: str) -> str:
    moment = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=ZoneInfo(source))
    if moment != moment.astimezone(timezone.utc).astimezone(moment.tzinfo):
        return 'nonexistent'
    if moment.utcoffset() != moment.replace(fold=1).utcoffset():
        return 'ambiguous'
    return ''


# Builds the WHERE clause that selects the rows one column of the map offers to the run, and its parameters.
# 'accounts' is a list of account ids, or None for every account; 'excluded' names the ones to leave out of that.
# A leg whose account is unknown (a transfer with one end outside JAL) belongs to no account that could be named,
# so it is reached only by a run that names none - and no exclusion can single it out either.
def _selection(timestamp_column: str, account_expression: str, accounts, excluded, begin: int, end: int) -> tuple:
    conditions = [f"o.{timestamp_column} IS NOT NULL"]   # an optional leg that was never filled in has no reading
    parameters = []
    if accounts is not None:
        conditions.append(f"{account_expression} IN ({','.join(str(int(x)) for x in accounts)})")
    if excluded:
        conditions.append(f"({account_expression} IS NULL OR "
                          f"{account_expression} NOT IN ({','.join(str(int(x)) for x in excluded)}))")
    if begin:
        conditions.append(f"o.{timestamp_column} >= :begin")
        parameters.append((":begin", begin))
    if end:
        conditions.append(f"o.{timestamp_column} <= :end")
        parameters.append((":end", end))
    return " AND ".join(conditions), parameters


# The account a row is booked on and what its note says, for the few rows a report names one by one - asked for
# separately so that the pass over every timestamp of the database stays a pass over timestamps.
def _details(table: str, account_expression: str, description: str, oids) -> dict:
    if not oids:
        return {}
    query = JalDB._exec(f"SELECT o.oid, COALESCE(a.name, ''), COALESCE({description}, '') FROM {table} AS o "
                        f"LEFT JOIN accounts AS a ON a.id={account_expression} "
                        f"WHERE o.oid IN ({','.join(str(int(x)) for x in oids)})")
    details = {}
    while query.next():
        oid, account, note = JalDB._read_record(query, cast=[int, str, str])
        details[oid] = {'account': account, 'note': note}
    return details


# Re-reads on 'to_clock' every stored reading that was made on 'from_clock', within the given window and accounts.
#   from_clock, to_clock - IANA zone names ('UTC' as the target means "store the instant from now on")
#   accounts      - list of account ids, or None for all of them
#   excluded      - list of account ids to leave out, whether or not 'accounts' names them
#   begin, end    - the window, given in the SOURCE clock, i.e. the digits as they are stored (0 = unbounded)
#   source_markers - the end-of-day stamps of the source these rows came from, on top of the common day markers
#   apply         - False (the default) only reports what would happen and writes nothing
#
# Returns a report: for every column, the rows selected, the ones left alone as day markers, the ones that move, and
# - of those - how many change their day or their year, beside the rows whose local time is ambiguous or never
# existed. Two findings are returned row by row rather than counted, because each one is a judgement the user has to
# make and neither can be made after the fact:
#   'made_markers' - the moments this run turns INTO a day. A marker is recognised by its value alone (see
#       is_day_marker), so three hours off Moscow spells a spending of 15:00 as noon, and from then on everything
#       reads it as a day rather than a moment. Nothing distinguishes it afterwards.
#   'reordered' - the two-leg operations whose legs end up out of order, including those that were in that order
#       already: some of those were put right by hand, and moving either leg undoes the correction.
#
# Day markers are skipped by the run: they state a day and re-reading one could only move it to another day.
def reclock(from_clock: str, to_clock: str, accounts: list = None, excluded: list = None, begin: int = 0, end: int = 0,
            source_markers: tuple = (), apply: bool = False) -> dict:
    _ = ZoneInfo(from_clock), ZoneInfo(to_clock)   # fail here, before anything is read, if a zone name is unknown
    report = {'from_clock': from_clock, 'to_clock': to_clock, 'accounts': accounts, 'excluded': excluded,
              'begin': begin, 'end': end, 'source_markers': tuple(source_markers), 'applied': False,
              'columns': [], 'reordered': []}
    changes = {}      # {(table, column): {oid: new_timestamp}} - everything the run would write
    for table, column, account_expression, description in RECLOCKED_COLUMNS:
        condition, parameters = _selection(column, account_expression, accounts, excluded, begin, end)
        column_report = {'table': table, 'column': column, 'selected': 0, 'markers': 0, 'changed': 0,
                         'days': 0, 'years': 0, 'made_markers': [], 'ambiguous': [], 'nonexistent': []}
        column_changes = {}
        query = JalDB._exec(f"SELECT o.oid, o.{column} FROM {table} AS o WHERE {condition}", parameters)
        while query.next():
            oid, timestamp = JalDB._read_record(query, cast=[int, int])
            column_report['selected'] += 1
            if is_day_marker(timestamp, source_markers):
                column_report['markers'] += 1
                continue
            anomaly = clock_anomaly(timestamp, from_clock)
            if anomaly:
                column_report[anomaly].append(oid)
            new_timestamp = reclocked(timestamp, from_clock, to_clock)
            if new_timestamp == timestamp:
                continue
            column_changes[oid] = new_timestamp
            column_report['changed'] += 1
            column_report['days'] += day_begin(new_timestamp) != day_begin(timestamp)
            column_report['years'] += year_begin(new_timestamp) != year_begin(timestamp)
            if is_day_marker(new_timestamp, source_markers):
                column_report['made_markers'].append({'oid': oid, 'stored': timestamp, 'becomes': new_timestamp})
        details = _details(table, account_expression, description, [x['oid'] for x in column_report['made_markers']])
        for row in column_report['made_markers']:
            row.update(details.get(row['oid'], {'account': '', 'note': ''}))
        report['columns'].append(column_report)
        changes[(table, column)] = column_changes
    report['reordered'] = _reordered_legs(changes)
    report['changed'] = sum(x['changed'] for x in report['columns'])
    report['selected'] = sum(x['selected'] for x in report['columns'])
    if apply:
        _write(changes)
        report['applied'] = True
    return report


# The two-leg operations the run touches whose legs end up in the wrong order. Each leg takes its new value if the
# run moves it and keeps the stored one if it doesn't, which is what makes a one-sided move visible here. A pair
# that was already stored out of order is listed as well, under 'already' - the run is not what put it there, but
# the run is what moves it, and a correction made by hand deserves to be looked at before it is overwritten.
def _reordered_legs(changes: dict) -> list:
    reordered = []
    accounts = {(table, column): (expression, description)
                for table, column, expression, description in RECLOCKED_COLUMNS}
    for table, first_column, second_column in PAIRED_COLUMNS:
        oids = set(changes.get((table, first_column), {})) | set(changes.get((table, second_column), {}))
        if not oids:
            continue
        query = JalDB._exec(f"SELECT o.oid, o.{first_column}, o.{second_column} FROM {table} AS o "
                            f"WHERE o.{second_column} IS NOT NULL AND o.oid IN ({','.join(str(x) for x in oids)})")
        pairs = []
        while query.next():
            oid, first, second = JalDB._read_record(query, cast=[int, int, int])
            new_first = changes.get((table, first_column), {}).get(oid, first)
            new_second = changes.get((table, second_column), {}).get(oid, second)
            if new_first > new_second:
                pairs.append({'table': table, 'oid': oid, 'before': (first, second), 'after': (new_first, new_second),
                              'already': first > second})
        departures = _details(table, *accounts[(table, first_column)], [x['oid'] for x in pairs])
        arrivals = _details(table, *accounts[(table, second_column)], [x['oid'] for x in pairs])
        for pair in pairs:
            pair['departure_account'] = departures.get(pair['oid'], {}).get('account', '')
            pair['arrival_account'] = arrivals.get(pair['oid'], {}).get('account', '')
            pair['note'] = departures.get(pair['oid'], {}).get('note', '')
        reordered += pairs
    return reordered


# Writes the whole run as one transaction - a half-re-clocked database has two conventions in it and no way to tell
# which row is on which. The ledger is asked for on the next start: every book it holds is keyed by timestamp.
def _write(changes: dict) -> None:
    database = JalDB()
    database.start_transaction()
    try:
        for (table, column), column_changes in changes.items():
            for oid, timestamp in column_changes.items():
                JalDB._exec(f"UPDATE {table} SET {column}=:timestamp WHERE oid=:oid",
                            [(":timestamp", timestamp), (":oid", oid)])
        JalSettings().setValue('RebuildDB', 1)
    except Exception:
        database.rollback_transaction()
        raise
    database.commit_transaction()
