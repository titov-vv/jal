from jal.db.helpers import remove_exponent
from jal.db.operations import Transfer
from jal.widgets.helpers import ts2dt
from jal.widgets.leg_convert_dialog import LegConvertDialog


# ----------------------------------------------------------------------------------------------------------------------
# Turns two pending transfer legs into the Swap operation they always were.
#
# One asset leaving and ANOTHER arriving is an exchange, and no settlement will ever pair them however long they wait -
# Match refuses them outright, because two legs carrying different assets are not two sightings of one movement.
#
# They get recorded that way when whoever produced them could not tell what the transaction was: an intent-based DEX
# (CoW Protocol and the like) settles a swap through a transaction the wallet never signed, so nothing in it names the
# protocol; an exchange's statement may report the two sides of a conversion as a withdrawal and a deposit. Left as
# transfers they misstate the money twice over - the disposal is never recognized, and what arrived opens at no cost
# basis at all - which is why this is a conversion into one operation rather than a way to hide the two rows.
#
# The dialog offers the candidates and lets the user decide, because deciding is what is needed here: sharing a
# transaction reference is proof that two legs belong together and is marked as such, but plenty of real swaps carry no
# shared reference, and two legs that merely look alike are not an exchange just because both are unsettled.
class SwapConvertDialog(LegConvertDialog):
    def title(self) -> str:
        return self.tr("Convert transfer legs into a swap")

    def ok_text(self) -> str:
        return self.tr("Convert")

    def prompt(self) -> str:
        anchor = self.anchor()
        if anchor is None:
            return self.tr("This leg is not waiting for a counterpart any more.")
        side = self.tr("was exchanged for") if anchor['opart'] == Transfer.Outgoing \
            else self.tr("was received in exchange for")
        return f"{remove_exponent(anchor['qty'])} {Transfer.leg_symbol(anchor)} " \
               + anchor['account'].name() + ", " + ts2dt(anchor['timestamp']) + " — " + side + ":"

    def refusal(self, sending_oid: int, arriving_oid: int) -> str:
        return self._settlement.refusal_to_convert(sending_oid, arriving_oid)

    def commit(self, sending_oid: int, arriving_oid: int) -> str:
        return self._settlement.convert_to_swap(sending_oid, arriving_oid)

    # The two sides of a same-chain swap are one transaction, so a leg naming the same reference comes first and is
    # marked - that is proof they moved together, and it is what the shapes this dialog exists for look like.
    def proximity(self, leg: dict):
        return (not self._same_transaction(leg), abs(leg['timestamp'] - self.anchor()['timestamp']))

    def marks(self, leg: dict) -> tuple:
        if not self._same_transaction(leg):
            return [], False
        return [self.tr("Same transaction: ") + leg['number']], True

    def _same_transaction(self, leg: dict) -> bool:
        return bool(leg['number']) and leg['number'] == self.anchor()['number']

    def result_text(self, sent: dict, arrived: dict) -> str:
        text = self.tr("Both transfers are replaced by one swap: ") \
               + f"{remove_exponent(sent['qty'])} {Transfer.leg_symbol(sent)} -> " \
               + f"{remove_exponent(arrived['qty'])} {Transfer.leg_symbol(arrived)}"
        if sent['account'].id() != arrived['account'].id():
            # The Swap operation records this as a cross-chain swap - it says so, because it is not what the user
            # asking to convert two legs of one wallet expects to get
            text += " (" + sent['account'].name() + " -> " + arrived['account'].name() + ")"
        return text
