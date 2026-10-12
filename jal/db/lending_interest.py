from decimal import Decimal
from jal.db.db import JalDB
from jal.db.helpers import format_decimal
from jal.db.symbol import JalSymbol
from jal.db.operations import LedgerTransaction, AssetIncome


# A rebasing receipt token (an Aave aToken) announces the interest it accrued by welding it onto the next movement:
# it mints 'amount + accrued' on a supply and burns 'amount - accrued' on a withdrawal. Either way the quantity
# received exceeds the one given by exactly that interest.
# This takes the interest out of a conversion: the quantities of 'conversion' are made equal in place and the
# AssetIncome.LendingInterest that books the difference is returned - None when the conversion carries none.
# Only a pair of the token and its plain underlying is read this way. Against another receipt token the difference
# is an exchange rate between two units, and a shortfall is a truncation crumb (see RebaseResidue).
def split_welded_interest(conversion: dict):
    out_qty, in_qty = Decimal(conversion['out_qty']), Decimal(conversion['in_qty'])
    given, received = JalSymbol(conversion['out_symbol_id']).asset(), JalSymbol(conversion['in_symbol_id']).asset()
    if given.rebasing() == received.rebasing() or in_qty <= out_qty:
        return None
    plain = received if given.rebasing() else given
    if plain.protocol():
        return None
    if given.rebasing():
        symbol_id, conversion['out_qty'] = conversion['out_symbol_id'], in_qty
    else:
        symbol_id, conversion['in_qty'] = conversion['in_symbol_id'], out_qty
    # One second earlier: a withdrawal surrenders the interest, so it has to be on the books by then
    return {'timestamp': conversion['timestamp'] - 1, 'number': conversion.get('tx_hash', ''),
            'type': AssetIncome.LendingInterest, 'account_id': conversion['account_id'], 'symbol_id': symbol_id,
            'amount': in_qty - out_qty, 'note': conversion.get('note', '')}


# Stored conversions that still carry welded interest, as (conversion, interest) pairs with the conversion already
# made equal - of every asset, or of 'asset_id' alone. Nothing is written.
def stored_welded_interest(asset_id: int = 0) -> list:
    query = ("SELECT c.oid, c.timestamp, c.account_id, c.tx_hash, c.out_symbol_id, c.out_qty, c.in_symbol_id, "
             "c.in_qty, c.note FROM conversions c")
    params = []
    if asset_id:
        query += (" JOIN asset_symbol o ON o.id=c.out_symbol_id JOIN asset_symbol i ON i.id=c.in_symbol_id "
                  "WHERE o.asset_id=:asset_id OR i.asset_id=:asset_id")
        params = [(":asset_id", asset_id)]
    found = []
    for conversion in JalDB._read_to_list(query + " ORDER BY c.timestamp", params, named=True):
        interest = split_welded_interest(conversion)
        if interest is not None:
            found.append((conversion, interest))
    return found


# Books what stored_welded_interest() found - what the statement import does for a new conversion.
# The income is created before the conversion is rewritten and is not created twice (see locate_operation()), and
# a conversion already rewritten has nothing left to split - so an interrupted run may be repeated.
def book_welded_interest(found: list) -> None:
    for conversion, interest in found:
        LedgerTransaction.create_new(LedgerTransaction.AssetIncome, interest)
        JalDB._exec("UPDATE conversions SET out_qty=:out_qty, in_qty=:in_qty WHERE oid=:oid",
                    [(":out_qty", format_decimal(Decimal(conversion['out_qty']))),
                     (":in_qty", format_decimal(Decimal(conversion['in_qty']))), (":oid", conversion['oid'])])
    JalDB().commit()
