from decimal import Decimal
from jal.db.db import JalDB
from jal.db.helpers import format_decimal

# 'fees.amount' joins the amounts that duplicate detection matches as text - see jal_delta_69.py, which did the
# same for the four columns that were compared that way before it. The rows this delta creates were copied out of
# the fee columns verbatim, so they inherit whatever spelling those held, and a fee offered by a re-import would
# not be recognized as the one already stored.
# The fee columns go with it although they are about to be dropped: until then the mirror triggers copy them into
# 'fees' on every parent write, which would put a non-canonical spelling straight back.
CANONICAL_COLUMNS = {
    'trades': ['fee'],
    'transfers': ['fee'],
    'conversions': ['fee_qty'],
    'swaps': ['fee_qty'],
    'bridges': ['fee_qty'],
    'fees': ['amount']
}


# Rewrites every stored fee into the canonical spelling of the database. The conversion preserves the value -
# Decimal() reads both spellings - so it may be repeated, as an interrupted companion is required to allow.
# The fee columns come first: the mirror carries each one into 'fees' as it is rewritten, so the last pass finds
# most of the table canonical already.
# Clearing the ledger costs nothing here - delta 71 emptied it and asked for a rebuild.
def update() -> None:
    for table, columns in CANONICAL_COLUMNS.items():
        for column in columns:
            values = JalDB._read_to_list(
                f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column}<>''")
            for value in values:   # a single-column row is read as a scalar
                canonical = format_decimal(Decimal(value))
                if canonical != value:
                    JalDB._exec(f"UPDATE {table} SET {column}=:canonical WHERE {column}=:value",
                                [(":canonical", canonical), (":value", value)])
    JalDB().commit()
