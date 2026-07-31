from decimal import Decimal
from jal.db.bridge_matcher import BridgeMatcher
from jal.db.helpers import remove_exponent
from jal.db.operations import Transfer
from jal.widgets.helpers import ts2dt
from jal.widgets.leg_convert_dialog import LegConvertDialog


# ----------------------------------------------------------------------------------------------------------------------
# Turns two pending transfer legs into the Bridge operation they always were - one asset crossing chains.
#
# JAL already completes a crossing whose SENDING leg the fetcher recognized: that leg is stored as a pending
# half-bridge, and the bridge matcher pairs it with the arriving transfer (Operations -> "Match cross-chain legs...").
# What reaches this dialog is the crossing whose send was NOT recognized, because the contract it went through is not
# in the protocol registry - so both ends were imported as plain transfers and there is no half to complete.
#
# Match cannot rescue those: a bridge that takes its cut delivers LESS than was sent, and "what arrived isn't what was
# sent" is exactly how a transfer settlement tells a bridge from a transfer and refuses the pair. Without this such a
# movement has no path at all - refused by Match on the quantity, by the swap conversion on the asset, and invisible
# to the bridge matcher, which has nothing to match.
#
# A crossing whose two ends happen to be equal CAN be settled as a plain transfer instead, and that is a real choice
# rather than a mistake: as a transfer the basis simply travels with the asset. A bridge states the crossing (and what
# it kept back) explicitly, so it is the more faithful record - but Match is not wrong there, and this dialog does not
# try to stop it.
class BridgeConvertDialog(LegConvertDialog):
    def __init__(self, oid: int, parent=None):
        self._matcher = BridgeMatcher()
        self._claimed = {}     # arriving leg oid -> pending half-bridges that could claim it instead
        super().__init__(oid, parent)

    def title(self) -> str:
        return self.tr("Convert transfer legs into a bridge")

    def ok_text(self) -> str:
        return self.tr("Convert")

    def prompt(self) -> str:
        anchor = self.anchor()
        if anchor is None:
            return self.tr("This leg is not waiting for a counterpart any more.")
        side = self.tr("crossed chains and arrived as") if anchor['opart'] == Transfer.Outgoing \
            else self.tr("arrived, having crossed chains from")
        return f"{remove_exponent(anchor['qty'])} {Transfer.leg_symbol(anchor)} " \
               + anchor['account'].name() + ", " + ts2dt(anchor['timestamp']) + " — " + side + ":"

    def refusal(self, sending_oid: int, arriving_oid: int) -> str:
        return self._settlement.refusal_to_bridge(sending_oid, arriving_oid)

    def commit(self, sending_oid: int, arriving_oid: int) -> str:
        return self._settlement.convert_to_bridge(sending_oid, arriving_oid)

    # A crossing is two transactions on two chains, so nothing in the two legs points at the other and there is no
    # proof to rank by - only how soon the money turned up, and how little of it the crossing kept back.
    def proximity(self, leg: dict):
        sent, arrived = self.as_legs(leg)
        kept = sent['qty'] - arrived['qty']
        share = float(kept / sent['qty']) if sent['qty'] and kept >= 0 else 1.0
        return (abs(leg['timestamp'] - self.anchor()['timestamp']), share)

    # The one thing worth saying about a candidate: an arriving leg that a pending half-bridge is also waiting for.
    # Both mechanisms end at the same Bridge operation and this leg can serve either, but only one - taking it here
    # leaves that half with nothing to complete it, while the send it already holds stays on the books, and the same
    # crossing is then recorded twice. It is not refused: the half may be an unrelated move, and only the user knows.
    def marks(self, leg: dict) -> tuple:
        arriving = self.as_pair(leg)[1]
        if arriving not in self._claimed:
            self._claimed[arriving] = self._matcher.halves_claiming(arriving)
        halves = self._claimed[arriving]
        if not halves:
            return [], False
        return [self.tr("Careful: a cross-chain send already recorded as a pending bridge could be waiting for this "
                        "arrival (operation #") + f"{halves[0]}"
                + self.tr("). If it is the one, complete it instead - Operations, right-click it, "
                          "'Match cross-chain legs...' - or this crossing ends up recorded twice.")], False

    def result_text(self, sent: dict, arrived: dict) -> str:
        text = self.tr("Both transfers are replaced by one bridge: ") \
               + f"{remove_exponent(sent['qty'])} {Transfer.leg_symbol(sent)} " + sent['account'].name() \
               + " -> " + f"{remove_exponent(arrived['qty'])} {Transfer.leg_symbol(arrived)} " \
               + arrived['account'].name()
        kept = sent['qty'] - arrived['qty']
        if kept > Decimal('0'):
            text += self.tr(", the crossing kept ") + f"{remove_exponent(kept)} {Transfer.leg_symbol(sent)}"
        return text
