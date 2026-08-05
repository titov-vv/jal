import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from jal.constants import Setup
from jal.db.account import JalAccount
from jal.db.chain_balance import JalChainBalance
from jal.db.db import JalDB
from jal.db.helpers import remove_exponent, now_ts
from jal.db.operations import AssetPayment, LedgerAssetShortage, LedgerTransaction
from jal.db.symbol import JalSymbol


# ----------------------------------------------------------------------------------------------------------------------
# Books the quantity a rebasing receipt token gained without ever announcing it.
#
# There are TWO such quantities and they are different in kind, which is why this class does two things rather than
# one. Both surface the same way - the ledger stops, one short, on the withdrawal that closes the position - and
# absorb() tries them in order:
#
#   1. the TRUNCATION CRUMB, a few units of the last decimal, worth nothing. Booked as a RebaseAdjustment at zero
#      value, because the position's basis was paid in full and none of it belongs to the crumb. This is the older
#      of the two and everything down to refusal_to_absorb() describes it.
#   2. the ACCRUED INTEREST, which is a real quantity of real value that the position earned while it was held.
#      Recognized as income - an AssetPayment.StakingReward - and only at withdrawal, which is when it stops being
#      unrealized. See _realize_accrual() and the note above it.
#
# The second one is what a size-and-value heuristic can never reach: 2.24% of a position and $173 of value is not a
# rounding artifact by any measure, and nothing about its SIZE tells it apart from a transaction that was missed.
# What tells them apart is an independent measurement of what the chain really holds, which is what makes case 2
# possible at all and what its guard is built on.
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

    # Books the shortage the ledger stopped on, when it is one of the two things a rebasing position leaves behind.
    # Returns True when an operation was created (the caller has to rebuild the ledger for it to be taken into
    # account), False when both were refused.
    #
    # The two are different in kind and are tried in that order:
    #  - a truncation CRUMB, a few units of the last decimal, booked free of cost (_absorb_crumb below);
    #  - the accrued INTEREST, which is a real quantity of real value, recognized as income (_realize_accrual).
    # The crumb goes first because it is the narrower case and the one that costs nothing to book: a shortage small
    # and worthless enough to be rounding is rounding, whatever else is known about the position.
    def absorb(self, shortage: LedgerAssetShortage) -> bool:
        if self._absorb_crumb(shortage):
            return True
        return self._realize_accrual(shortage)

    def _absorb_crumb(self, shortage: LedgerAssetShortage) -> bool:
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

    # ------------------------------------------------------------------------------------------------------------------
    # REALIZATION. The other, larger thing a rebasing position leaves behind: the interest it earned while it was
    # held, which no event ever announced and which the books therefore never received.
    #
    # It is deliberately NOT recognized while the position is open. The accrued units are withdrawable at any second,
    # but the gain is unrealized, and JAL's convention for unrealized value is valuation data rather than operations -
    # nobody books an operation when a stock ticks up. So it is measured and displayed (jal/net/chain_balances.py) and
    # left alone until a withdrawal turns it into something the wallet actually received. That is one operation per
    # position lifetime, at a timestamp with real meaning, and it is how a bank posts interest.
    #
    # It is an AssetPayment.StakingReward and not the RebaseAdjustment above, because the two are opposite in the one
    # way that matters: a crumb is a rounding artifact that costs nothing and must not move any basis, while this is
    # income, and it opens a lot at the market value of the day exactly as any other reward does.
    #
    # THE WHOLE tracked delta is recognized, not merely the part the withdrawal was short of. The alternative leaves
    # an orphan: booking only the shortage empties the books while the chain still holds a remainder, and since the
    # portfolio is ledger-driven that remainder would drop out of sight entirely. Worked through: books 7637.23,
    # chain 7808.43, withdraw 7700 -> recognize 171.20, books become 7808.43, 108.43 is left and the chain agrees.
    def _realize_accrual(self, shortage: LedgerAssetShortage) -> bool:
        refusal = self.refusal_to_realize(shortage)
        if refusal:
            logging.debug(self.tr("Asset shortage is not an accrued rebase: ") + refusal)
            return False
        symbol = JalSymbol(shortage.symbol_id)
        accrued = self._tracked_delta(shortage)
        # One second before the operation that revealed it, exactly as the crumb is booked: the quantity has to be on
        # the books by the time the withdrawal is processed, and the withdrawal's own second is taken.
        payment = {'timestamp': shortage.operation.timestamp() - 1, 'number': shortage.operation.number(),
                   'type': AssetPayment.StakingReward, 'account_id': shortage.account_id,
                   'symbol_id': shortage.symbol_id, 'amount': accrued,
                   'note': self.tr("Interest accrued on a rebasing balance, realized on withdrawal")}
        LedgerTransaction.create_new(LedgerTransaction.AssetPayment, payment)
        # The measurement has now been spent, and keeping it would be dangerous rather than merely stale: the books
        # have just risen by the whole delta, so the same snapshot compared against them again would report the
        # withdrawn quantity as a fresh accrual and recognize it a second time. The chain is asked again at the next
        # refresh, and until then this position simply has no measurement - which is the state every other asset is
        # in and shows nothing wrong.
        JalChainBalance().forget(shortage.account_id, symbol.asset().id())
        logging.info(self.tr("Accrued rebasing interest realized: ") + f"{remove_exponent(accrued)} "
                     + f"{symbol.symbol()} " + JalAccount(shortage.account_id).name())
        return True

    # How much more the chain says this position held than the books did at the moment the ledger stopped, or None
    # when the chain was never read for it.
    #
    # The measurement is taken as the LATEST one there is, deliberately unlike the date gating that the reports
    # apply. A report asks "what did this position hold on that date" and must never answer with a quantity measured
    # afterwards; this asks "how much accrual is known about at all", which is a fact about the position and not
    # about the date the withdrawal happens to carry.
    def _tracked_delta(self, shortage: LedgerAssetShortage):
        asset_id = JalSymbol(shortage.symbol_id).asset().id()
        snapshot = JalChainBalance().latest(shortage.account_id, asset_id, now_ts())
        if snapshot is None:
            return None
        return snapshot['amount'] - shortage.available

    # Why this shortage can't be recognized as accrued interest, or '' when it can
    def refusal_to_realize(self, shortage: LedgerAssetShortage) -> str:
        if shortage.operation.type() != LedgerTransaction.Conversion:
            return self.tr("only a conversion can surrender a rebasing receipt token")
        if shortage.shortage() <= Decimal('0'):
            return self.tr("nothing is missing")
        # The flag is the whole licence to do this. Only a token whose quantity can grow on its own may have a
        # shortage explained away as interest; on anything else a shortage means a movement was missed, and that is
        # what the ledger stopping is FOR.
        if not JalSymbol(shortage.symbol_id).asset().rebasing():
            return self.tr("the asset is not marked as rebasing")
        accrued = self._tracked_delta(shortage)
        if accrued is None:
            return self.tr("the on-chain balance of this position has never been read")
        if accrued <= Decimal('0'):
            return self.tr("the chain holds no more than the books do")
        # THE GUARD, and the reason this is safe where a size-and-value heuristic is not. Restated from 'the shortage
        # must not exceed the tracked delta', which is the same inequality: the withdrawal may take out no more than
        # the chain itself says the wallet was holding. A genuinely missed transaction asks for more than that and
        # still stops the ledger dead - which is the whole point, since a missed transaction is indistinguishable
        # from accrual by size alone once the accrual is large enough to matter (2.24% and $173 on the position this
        # was measured against, past every threshold a heuristic could sensibly draw).
        #
        # It does mean a STALE measurement refuses: interest keeps accruing after a snapshot is taken, so a close
        # made well after the last refresh asks for slightly more than the chain was last seen holding. That is the
        # safe direction and it is recoverable - refresh the on-chain balances and rebuild.
        if shortage.required > shortage.available + accrued:
            return self.tr("the missing quantity exceeds the last known on-chain balance "
                           "- refresh on-chain balances and rebuild")
        if round(accrued, JalAccount(shortage.account_id).precision()) == Decimal('0'):
            return self.tr("the account's precision is too coarse to hold the accrued quantity")
        return ''
