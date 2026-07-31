from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QDialogButtonBox,
                               QMessageBox)
from jal.db.asset import JalAsset
from jal.db.helpers import localize_decimal, remove_exponent
from jal.db.operations import Transfer
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.helpers import ts2dt


# ----------------------------------------------------------------------------------------------------------------------
# Turns two pending transfer legs into the Swap operation they always were.
#
# Not every pair of legs in the unsettled list is a transfer waiting for its other end. One asset leaving and ANOTHER
# arriving is an exchange, and no settlement will ever pair them however long they wait - Match refuses them outright,
# because two legs carrying different assets are not two sightings of one movement.
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
class SwapConvertDialog(QDialog):
    _DAY = 86400
    OID = Qt.UserRole

    def __init__(self, oid: int, parent=None):
        super().__init__(parent)
        self.changed = False    # the caller rebuilds the ledger on it - the conversion writes a real operation
        self._settlement = TransferSettlement()
        self._currency = JalAsset.get_base_currency()
        self._currency_name = JalAsset(self._currency).symbol()
        self.setWindowTitle(self.tr("Convert transfer legs into a swap"))
        self.resize(760, 420)
        self._legs = {leg['oid']: leg for leg in Transfer.pending_legs()}
        self._anchor = self._legs.get(oid)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self._anchor_text(), self))
        self._candidates = QTreeWidget(self)
        self._candidates.setHeaderLabels([self.tr("Date"), self.tr("Account"), self.tr("Qty"), self.tr("Asset"),
                                          self._currency_name, self.tr("Difference")])
        self._candidates.setRootIsDecorated(False)
        self._candidates.setAlternatingRowColors(True)
        self._candidates.setAllColumnsShowFocus(True)
        self._candidates.setUniformRowHeights(True)
        self._candidates.setSelectionMode(QTreeWidget.SingleSelection)
        layout.addWidget(self._candidates)
        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close, self)
        self._buttons.button(QDialogButtonBox.Ok).setText(self.tr("Convert"))
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._fill()
        self._candidates.itemSelectionChanged.connect(self._selection_changed)
        self._selection_changed()

    def _anchor_text(self) -> str:
        if self._anchor is None:
            return self.tr("This leg is not waiting for a counterpart any more.")
        side = self.tr("was exchanged for") if self._anchor['opart'] == Transfer.Outgoing \
            else self.tr("was received in exchange for")
        return f"{remove_exponent(self._anchor['qty'])} {Transfer.leg_symbol(self._anchor)} " \
               + self._anchor['account'].name() + ", " + ts2dt(self._anchor['timestamp']) + " — " + side + ":"

    # The legs on the other side, each with the reason it could not make a swap with the anchor ('' when it could).
    #
    # A leg naming the SAME transaction reference comes first and says so: that is proof the two moved together, and
    # it is what the shapes this dialog exists for look like. The rest follow by how close in time they are - a
    # resemblance, offered as one. What cannot be converted at all sinks to the bottom whatever it resembles.
    def _ranked(self) -> list:
        if self._anchor is None:
            return []
        opposite = Transfer.Incoming if self._anchor['opart'] == Transfer.Outgoing else Transfer.Outgoing
        candidates = [(leg, self._refusal_with(leg)) for leg in self._legs.values() if leg['opart'] == opposite]
        return sorted(candidates, key=lambda x: (bool(x[1]), not self._same_transaction(x[0]),
                                                 abs(x[0]['timestamp'] - self._anchor['timestamp']), x[0]['oid']))

    def _same_transaction(self, leg: dict) -> bool:
        return bool(leg['number']) and leg['number'] == self._anchor['number']

    def _refusal_with(self, leg: dict) -> str:
        return self._settlement.refusal_to_convert(*self._as_pair(leg))

    # The (sending, arriving) oids of the anchor and the given leg, in the order a swap is built from
    def _as_pair(self, leg: dict) -> tuple:
        return (self._anchor['oid'], leg['oid']) if self._anchor['opart'] == Transfer.Outgoing \
            else (leg['oid'], self._anchor['oid'])

    def _fill(self) -> None:
        self._candidates.clear()
        for leg, refusal in self._ranked():
            value = leg['qty'] * leg['asset'].quote(leg['timestamp'], self._currency)[1]
            elapsed = (leg['timestamp'] - self._anchor['timestamp']) / self._DAY
            item = QTreeWidgetItem([ts2dt(leg['timestamp']), leg['account'].name(),
                                    localize_decimal(remove_exponent(leg['qty'])), Transfer.leg_symbol(leg),
                                    localize_decimal(value, precision=2), f"{elapsed:+.1f} " + self.tr("days")])
            item.setData(0, self.OID, leg['oid'])
            tooltip = self.tr("Same transaction: ") + leg['number'] if self._same_transaction(leg) else ''
            if refusal:
                item.setToolTip(0, (self.tr("Not a swap: ") + refusal + '\n' + tooltip).strip())
                font = item.font(0)
                font.setItalic(True)
                for column in range(self._candidates.columnCount()):
                    item.setFont(column, font)
            else:
                item.setToolTip(0, tooltip)
                if self._same_transaction(leg):
                    font = item.font(0)
                    font.setBold(True)     # proof, not a resemblance - it should be visible without hovering
                    for column in range(self._candidates.columnCount()):
                        item.setFont(column, font)
            for column in (2, 4):
                item.setTextAlignment(column, Qt.AlignRight | Qt.AlignVCenter)
            self._candidates.addTopLevelItem(item)
        for column in range(self._candidates.columnCount()):
            self._candidates.resizeColumnToContents(column)

    def _selected_oid(self) -> int:
        items = self._candidates.selectedItems()
        return items[0].data(0, self.OID) if items else 0

    def _selection_changed(self) -> None:
        oid = self._selected_oid()
        refusal = self._refusal_with(self._legs[oid]) if oid else ''
        if not oid:
            self._status.setText(self.tr("Choose the other half of the exchange."))
        elif refusal:
            self._status.setText(self.tr("These two can't be one swap: ") + refusal)
        else:
            self._status.setText(self.tr("Both transfers are replaced by one swap: ") + self._swap_text(oid))
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(bool(oid and not refusal))

    def _swap_text(self, oid: int) -> str:
        sent, arrived = (self._anchor, self._legs[oid]) if self._anchor['opart'] == Transfer.Outgoing \
            else (self._legs[oid], self._anchor)
        text = f"{remove_exponent(sent['qty'])} {Transfer.leg_symbol(sent)} -> " \
               + f"{remove_exponent(arrived['qty'])} {Transfer.leg_symbol(arrived)}"
        if sent['account'].id() != arrived['account'].id():
            # The Swap operation records this as a cross-chain swap - it says so, because it is not what the user
            # asking to convert two legs of one wallet expects to get
            text += " (" + sent['account'].name() + " -> " + arrived['account'].name() + ")"
        return text

    def accept(self):
        oid = self._selected_oid()
        if not oid:
            return
        refusal = self._settlement.convert_to_swap(*self._as_pair(self._legs[oid]))
        if refusal:
            QMessageBox().warning(self, self.tr("Legs are not converted"), refusal)
            return
        self.changed = True
        super().accept()
