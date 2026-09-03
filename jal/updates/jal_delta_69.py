from decimal import Decimal
from jal.db.db import JalDB
from jal.db.helpers import format_decimal

# Amounts that duplicate detection matches as text - the 'validation: True' fields of _db_fields that hold a
# number (see JalDB.locate_operation()). Until now a float producer wrote '3800.0' here where a Decimal one wrote
# '3.8E+3', so an operation stored by one of them was never recognized as the duplicate of the same operation
# offered by the other, and a re-imported statement was booked twice.
# Amount columns outside this list are left alone on purpose: nothing compares them as strings, and the ledger
# tables are rebuilt rather than migrated.
CANONICAL_COLUMNS = {
    'trades': ['qty', 'price'],
    'transfers': ['withdrawal', 'deposit', 'fee'],
    'asset_payments': ['amount'],
    'asset_actions': ['qty']
}


# Rewrites every stored amount that duplicate detection matches into the canonical spelling of the database.
# The conversion preserves the value - Decimal() reads both spellings - so it may be repeated: a second run
# finds every cell canonical already and writes nothing, as an interrupted companion is required to allow.
def update() -> None:
    for table, columns in CANONICAL_COLUMNS.items():
        for column in columns:
            # Rewriting by value and not row by row: one number is stored in one spelling, so a single statement
            # converts every row holding it
            values = JalDB._read_to_list(
                f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column}<>''")
            for value in values:   # a single-column row is read as a scalar
                canonical = format_decimal(Decimal(value))
                if canonical != value:
                    JalDB._exec(f"UPDATE {table} SET {column}=:canonical WHERE {column}=:value",
                                [(":canonical", canonical), (":value", value)])
    JalDB().commit()
