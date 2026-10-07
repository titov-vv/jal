from decimal import Decimal
from jal.db.db import JalDB
from jal.db.helpers import format_decimal
from jal.db.operations import LedgerTransaction
from jal.db.lending_interest import split_welded_interest


# Takes the interest a rebasing receipt token welded onto a supply or a withdrawal out of every stored conversion
# and books it as an AssetIncome.LendingInterest - what the statement import does for a new one.
# The income is created before the conversion is rewritten and is not created twice (see locate_operation()), and
# a conversion already rewritten has nothing left to split - so an interrupted run may be repeated.
def update() -> None:
    conversions = JalDB._read_to_list("SELECT oid, timestamp, account_id, tx_hash, out_symbol_id, out_qty, "
                                      "in_symbol_id, in_qty, note FROM conversions", named=True)
    for conversion in conversions:
        interest = split_welded_interest(conversion)
        if interest is None:
            continue
        LedgerTransaction.create_new(LedgerTransaction.AssetIncome, interest)
        JalDB._exec("UPDATE conversions SET out_qty=:out_qty, in_qty=:in_qty WHERE oid=:oid",
                    [(":out_qty", format_decimal(Decimal(conversion['out_qty']))),
                     (":in_qty", format_decimal(Decimal(conversion['in_qty']))), (":oid", conversion['oid'])])
    JalDB().commit()
