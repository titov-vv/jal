#!/usr/bin/env python3
# One-off: removes the transfer mark and hint from notes of settled transfers and of operations legs were converted to.
# Usage: clean_transfer_marks.py <path to jal.sqlite> [--apply]   (without --apply only counts what would change)
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jal.constants import TransferMark

_MARKED = f"(note LIKE '{TransferMark.CUSTODY} %' OR note LIKE '{TransferMark.BRIDGE} %')"
_TABLES = {'transfers': "withdrawal_account IS NOT NULL AND deposit_account IS NOT NULL",
           'swaps': '1', 'bridges': '1', 'asset_incomes': '1', 'actions': '1'}


# Returns the number of notes changed per table; committing is up to the caller
def clean_notes(connection) -> dict:
    changed = {}
    for table, condition in _TABLES.items():
        rows = connection.execute(f"SELECT oid, note FROM {table} WHERE {_MARKED} AND {condition}").fetchall()
        connection.executemany(f"UPDATE {table} SET note=? WHERE oid=?",
                               [(TransferMark.settled_note(note), oid) for oid, note in rows])
        changed[table] = len(rows)
    return changed


def main() -> None:
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != '--apply'):
        sys.exit(f"Usage: {sys.argv[0]} <path to jal.sqlite> [--apply]")
    if not os.path.isfile(sys.argv[1]):
        sys.exit(f"No such file: {sys.argv[1]}")
    apply = len(sys.argv) == 3
    connection = sqlite3.connect(sys.argv[1])
    try:
        changed = clean_notes(connection)
        connection.commit() if apply else connection.rollback()
    finally:
        connection.close()
    print(("Changed: " if apply else "Would change: ") + str(changed))


if __name__ == '__main__':
    main()
