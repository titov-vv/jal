import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from jal.constants import Setup
from jal.db.account import JalAccount
from jal.db.db import JalDB
from jal.db.helpers import remove_exponent
from jal.db.operations import AssetPayment, LedgerAssetShortage, LedgerTransaction
from jal.db.symbol import JalSymbol


# ----------------------------------------------------------------------------------------------------------------------
# Books the quantity a rebasing receipt token gained without ever announcing it.
#
# The balance of such a token (an Aave aToken is the case this was built from) is a scaled number times the protocol's
# index, and the amount carried by each Transfer event is re-derived from that ray math and truncates. So the sum of
# every event a wallet ever saw is a few units of the last decimal BELOW the balance the protocol will really hand
# back, and a fetcher - which can only book the events the chain emitted - is short by exactly that. Nothing reveals
# the gap while the position is open: it surfaces the moment the position is closed in full, because a "withdraw max"
# burns the true balance. The ledger then stops on the withdrawal's conversion, one crumb short of processing it.
#
# The crumb is booked where the ledger found it, as an AssetPayment.RebaseAdjustment at ZERO value: the position's
# cost basis was paid in full when it was opened and none of it belongs to the crumb, so the quantity comes in free
# and the per-unit basis of everything already held is left untouched.
#
# What guards this from papering over a genuinely missing transaction is that all of the following must hold:
#  - the ledger stopped on a Conversion, and on its OUT leg. That is the only operation a lending interaction is
#    imported as, and its out leg is the only side on which a receipt token is ever surrendered;
#  - the shortage is a vanishing fraction of the quantity being converted (Setup.REBASE_RESIDUE_TOLERANCE), which is
#    what makes it a truncation crumb rather than a quantity;
#  - it is worth next to nothing (Setup.REBASE_RESIDUE_MAX_VALUE), whenever the asset can be priced at all.
# Anything that fails one of them is left exactly as it is - the ledger stays stopped and the user is told where, as
# it was before this existed.
class RebaseResidue(JalDB):
    def __init__(self):
        super().__init__()

    def tr(self, text):
        return QApplication.translate("RebaseResidue", text)

    # Books the shortage the ledger stopped on, when it is a rebase residue. Returns True when an operation was
    # created (the caller has to rebuild the ledger for it to be taken into account), False when it was refused.
    def absorb(self, shortage: LedgerAssetShortage) -> bool:
        refusal = self.refusal_to_absorb(shortage)
        if refusal:
            logging.debug(self.tr("Asset shortage is not a rebase residue: ") + refusal)
            return False
        symbol = JalSymbol(shortage.symbol_id)
        gap = shortage.shortage()
        # One second before the operation that revealed it: the quantity has to be on the books by the time the
        # conversion is processed, and its own second is already taken by the conversion.
        payment = {'timestamp': shortage.operation.timestamp() - 1, 'number': shortage.operation.number(),
                   'type': AssetPayment.RebaseAdjustment, 'account_id': shortage.account_id,
                   'symbol_id': shortage.symbol_id, 'amount': gap,
                   'note': self.tr("Rebasing balance not reported by a transfer")}
        LedgerTransaction.create_new(LedgerTransaction.AssetPayment, payment)
        logging.info(self.tr("Rebase residue booked: ") + f"{remove_exponent(gap)} {symbol.symbol()} "
                     + JalAccount(shortage.account_id).name())
        return True

    # Why this shortage can't be booked as a rebase residue, or '' when it can
    def refusal_to_absorb(self, shortage: LedgerAssetShortage) -> str:
        if shortage.operation.type() != LedgerTransaction.Conversion:
            return self.tr("only a conversion can surrender a rebasing receipt token")
        gap = shortage.shortage()
        if gap <= Decimal('0'):
            return self.tr("nothing is missing")
        # Every posting is rounded to the account's precision, so a crumb finer than that would be booked as a zero
        # and leave the shortage exactly where it was - and the rebuild would come back to it forever. The account is
        # then simply too coarse for the asset it holds, which is the user's to fix and not something to paper over.
        if round(gap, JalAccount(shortage.account_id).precision()) == Decimal('0'):
            return self.tr("the account's precision is too coarse to hold the missing quantity")
        if gap > abs(shortage.required) * Decimal(Setup.REBASE_RESIDUE_TOLERANCE):
            return self.tr("the missing quantity is too large to be a rounding residue")
        currency = JalAccount(shortage.account_id).currency()
        quote_timestamp, price = JalSymbol(shortage.symbol_id).asset().quote(shortage.operation.timestamp(), currency)
        if quote_timestamp and gap * price > Decimal(Setup.REBASE_RESIDUE_MAX_VALUE):
            return self.tr("the missing quantity is worth too much to be a rounding residue")
        return ''
