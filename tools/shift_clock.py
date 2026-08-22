#!/usr/bin/env python3
r"""Re-read the timestamps of a JAL database on another clock.

Every timestamp JAL stores is a wall-clock READING - the digits a clock showed, spelled as a UTC
epoch - so it means what it means only together with the clock it was read on. This tool re-reads a
chosen set of them on another clock: it is what a user runs after entering a residence history that
reaches back over years already booked, and what the move to storing true UTC is executed with.

    python3 tools/shift_clock.py --database jal.sqlite \
        --account "Уралсиб" --from 2022-09-11 --to 2026-12-31 \
        --clock Europe/Moscow --to-clock Europe/Lisbon [--markers ibkr] [--apply]

--account is repeatable and takes ALL (or ANY) for the whole database; --except takes accounts back
out of whatever it selected, which is how a group is named when the group is "everything but these".
--from/--to are given in the SOURCE clock, i.e. the digits as they are stored and as the application
shows them. Nothing is written without --apply: by default the run only reports what it would do.

Two findings are written out as CSV beside the report, to be gone through row by row: the moments the
run turns into days (dry run only - afterwards they cannot be told from a date) and the two-leg
operations left with the arrival before the departure (every run).

Run it on a copy first; the database must already be at the schema version this code expects.
"""
import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfoNotFoundError

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # no window is ever shown, and no display need be present
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from PySide6.QtWidgets import QApplication
from jal.data_import.broker_statements.ibkr import IBKR_DAY_MARKERS
from jal.db.db import JalDB, JalDBError
from jal.db.helpers import day_end
from jal.db.reclock import reclock

ANY_ACCOUNT = ('ALL', 'ANY')       # what --account is given instead of naming them one by one
MARKER_SETS = {'ibkr': IBKR_DAY_MARKERS}


# Reads a moment of the source clock as the digits it is stored under. A date alone is enough - it is the whole day
# then, which is why the end of the window is stretched to its last second.
def moment(text: str, whole_day_end: bool = False) -> int:
    for form in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            stamp = int(datetime.strptime(text, form).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
        return day_end(stamp) if whole_day_end and form == "%Y-%m-%d" else stamp
    sys.exit(f"'{text}' is not a date or a moment of the form 'YYYY-MM-DD HH:MM:SS'")


def timestamp_text(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# Turns the names given on the command line into account ids. An unknown name stops the run: it is far more likely
# a typo than an account the user meant to leave out, and leaving one out silently is what this tool must never do.
def named_ids(names: list) -> list:
    ids, unknown = [], []
    for name in names if names else []:
        account_id = JalDB._read("SELECT id FROM accounts WHERE name=:name", [(":name", name)])
        if account_id:
            ids.append(int(account_id))
        else:
            unknown.append(name)
    if unknown:
        sys.exit("No account is named " + ", ".join(f"'{x}'" for x in unknown))
    return ids


# ... and --account takes the whole database as a word, because a database holds one account per term deposit and
# naming a few hundred of them is not a way to ask for all of them. Naming none of them asks for the same thing.
def account_ids(names: list):
    if names is None or any(x.upper() in ANY_ACCOUNT for x in names):
        return None
    return named_ids(names)


# Writes one of the findings out for the user to go through row by row, and returns the path it went to (or '' when
# there was nothing to write). A spreadsheet is where a list like this gets read, so the byte order mark goes in
# front - without it Excel reads the account names of a Cyrillic ledger as mojibake.
def write_csv(path: str, header: list, rows: list) -> str:
    if not rows:
        return ''
    with open(path, 'w', newline='', encoding='utf-8-sig') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        writer.writerows(rows)
    return path


# The moments this run turns into days. Written on a dry run, where they can still be reviewed against the database
# as it is: once the run has been applied nothing tells them from a date that was always one.
def export_made_markers(prefix: str, report: dict) -> str:
    rows = [[column['table'], column['column'], row['oid'], row['account'], timestamp_text(row['stored']),
             timestamp_text(row['becomes']), timestamp_text(row['becomes'])[11:], row['note']]
            for column in report['columns'] for row in column['made_markers']]
    return write_csv(f"{prefix}_day_markers.csv",
                     ["operation", "column", "id", "account", "stored", "becomes", "marker", "note"],
                     sorted(rows, key=lambda row: (row[0], row[2])))


# The two-leg operations left out of order, written on every run - the ones marked 'already' were out of order
# before it, and some of those were put that way by hand.
def export_reordered_legs(prefix: str, report: dict) -> str:
    rows = [[item['table'], item['oid'], timestamp_text(item['before'][0]), timestamp_text(item['after'][0]),
             timestamp_text(item['before'][1]), timestamp_text(item['after'][1]),
             'yes' if item['already'] else '', item['departure_account'], item['arrival_account'], item['note']]
            for item in report['reordered']]
    return write_csv(f"{prefix}_reordered_legs.csv",
                     ["operation", "id", "departure", "departure_after", "arrival", "arrival_after",
                      "already_reordered", "departure_account", "arrival_account", "note"], rows)


def _total(report: dict, figure: str) -> int:
    return sum(len(x[figure]) if isinstance(x[figure], list) else x[figure] for x in report['columns'])


def print_report(report: dict, exports: dict) -> None:
    accounts = "every account" if report['accounts'] is None else f"{len(report['accounts'])} account(s)"
    accounts += f" except {len(report['excluded'])}" if report['excluded'] else ""
    window = "the whole history" if not (report['begin'] or report['end']) else \
        f"{timestamp_text(report['begin']) if report['begin'] else 'the beginning'} .. " \
        f"{timestamp_text(report['end']) if report['end'] else 'the end'}, as the {report['from_clock']} clock spelt it"
    print(f"\n{report['from_clock']} -> {report['to_clock']}, {accounts}, {window}")
    if report['source_markers']:
        print(f"End-of-day markers of the source: "
              f"{', '.join(f'{x // 3600:02d}:{x % 3600 // 60:02d}' for x in report['source_markers'])}")
    print(f"\n{'table':<16}{'column':<22}{'rows':>8}{'dates':>7}{'moved':>8}{'+day':>7}{'+year':>7}"
          f"{'->date':>8}{'ambig':>7}{'gap':>6}")
    for column in report['columns']:
        print(f"{column['table']:<16}{column['column']:<22}{column['selected']:>8}{column['markers']:>7}"
              f"{column['changed']:>8}{column['days']:>7}{column['years']:>7}{len(column['made_markers']):>8}"
              f"{len(column['ambiguous']):>7}{len(column['nonexistent']):>6}")
    print(f"{'TOTAL':<38}{report['selected']:>8}{_total(report, 'markers'):>7}{report['changed']:>8}"
          f"{_total(report, 'days'):>7}{_total(report, 'years'):>7}{_total(report, 'made_markers'):>8}"
          f"{_total(report, 'ambiguous'):>7}{_total(report, 'nonexistent'):>6}")
    print("\n'dates' are the rows that state a day and are left alone, and '->date' the moments that BECOME one by\n"
          "landing on midnight - nothing can tell those apart afterwards. 'ambig' fall in an hour the source\n"
          "clock repeats (the first of the two is taken) and 'gap' in an hour it skips (the offset before the gap).")
    for column in report['columns']:
        for kind in ('ambiguous', 'nonexistent'):
            if column[kind]:
                print(f"  {kind} on {column['table']}.{column['column']}: "
                      f"{', '.join(str(x) for x in column[kind])}")
    made_markers = _total(report, 'made_markers')
    if made_markers:
        print(f"\n{made_markers} moment(s) become a day by landing on a marker. " +
              (f"Listed in {exports['made_markers']} - go\nthrough them before applying anything, "
               "afterwards they are indistinguishable from a real date."
               if exports.get('made_markers') else "A dry run lists them one by one."))
    if report['reordered']:
        already = len([x for x in report['reordered'] if x['already']])
        print(f"\n{len(report['reordered'])} operation(s) are left with their legs out of order, the arrival before\n"
              f"the departure - {already} of them already were, which may well have been somebody's correction.\n"
              f"Listed in {exports['reordered']}:")
        for item in report['reordered']:
            print(f"  {item['table']} #{item['oid']}{' (already)' if item['already'] else ''}: "
                  f"{timestamp_text(item['before'][0])} -> {timestamp_text(item['before'][1])}   becomes   "
                  f"{timestamp_text(item['after'][0])} -> {timestamp_text(item['after'][1])}")
    if report['applied']:
        print(f"\n{report['changed']} timestamp(s) WRITTEN. Start the application to let it rebuild the ledger.")
    else:
        print(f"\nNothing was written - this was a dry run. Add --apply to move these {report['changed']} timestamp(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-read the timestamps of a JAL database on another clock",
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--database", required=True,
                        help="the database file to work on - give a COPY unless you mean it")
    parser.add_argument("--account", action="append", metavar="NAME",
                        help=f"an account to re-clock; repeat for several, or say {' / '.join(ANY_ACCOUNT)} "
                             f"for every account of the database (default: every account)")
    parser.add_argument("--except", dest="excluded", action="append", metavar="NAME",
                        help="an account to leave out; repeat for several. Applies to whatever --account selected")
    parser.add_argument("--from", dest="begin", metavar="WHEN",
                        help="the earliest moment to touch, in the SOURCE clock (default: the beginning)")
    parser.add_argument("--to", dest="end", metavar="WHEN",
                        help="the latest moment to touch, in the SOURCE clock (default: the end)")
    parser.add_argument("--clock", required=True, metavar="ZONE", help="the clock those timestamps were read on")
    parser.add_argument("--to-clock", required=True, metavar="ZONE",
                        help="the clock to read them on instead ('UTC' stores the instant itself)")
    parser.add_argument("--markers", action="append", choices=sorted(MARKER_SETS), default=None,
                        help="the source whose end-of-day stamps state a day rather than a time of day")
    parser.add_argument("--csv", metavar="PREFIX", default="reclock",
                        help="where the findings are written: PREFIX_day_markers.csv, PREFIX_reordered_legs.csv")
    parser.add_argument("--apply", action="store_true", help="write the changes instead of only reporting them")
    args = parser.parse_args()

    if not os.path.isfile(args.database) or not os.path.getsize(args.database):
        sys.exit(f"'{args.database}' is not a database file")
    _ = QApplication.instance() or QApplication([])   # QSqlDatabase needs an application object to exist before it
    error = JalDB().init_db(db_file=os.path.realpath(args.database))
    if error.code != JalDBError.NoError:
        sys.exit(f"{error.message} {error.details}")

    markers = sum((MARKER_SETS[x] for x in args.markers), ()) if args.markers else ()
    try:
        report = reclock(args.clock, args.to_clock, accounts=account_ids(args.account),
                         excluded=named_ids(args.excluded),
                         begin=moment(args.begin) if args.begin else 0,
                         end=moment(args.end, whole_day_end=True) if args.end else 0,
                         source_markers=markers, apply=args.apply)
    except ZoneInfoNotFoundError as failure:
        sys.exit(f"{failure} - a clock is named the way the IANA database names it, i.e. 'Europe/Lisbon'")
    # The markers a run makes are exported by the dry run only: it is the run that still has both readings to show,
    # and the applied one has already made them. The legs left out of order are exported by both, because there the
    # question - is this pair right? - outlives the run that raised it.
    exports = {'reordered': export_reordered_legs(args.csv, report)}
    if not args.apply:
        exports['made_markers'] = export_made_markers(args.csv, report)
    print_report(report, exports)


if __name__ == "__main__":
    main()
