from decimal import Decimal
from jal.db.symbol import JalSymbol
from jal.db.operations import AssetIncome


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
