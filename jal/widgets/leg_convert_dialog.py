from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QDialogButtonBox,
                               QMessageBox)
from jal.db.asset import JalAsset
from jal.db.helpers import localize_decimal, remove_exponent
from jal.db.operations import Transfer
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.helpers import ts2dt


# ----------------------------------------------------------------------------------------------------------------------
# Shared machinery of the dialogs that replace TWO pending transfer legs by the single operation they always were.
#
# Not every pair in the unsettled list is a transfer waiting for its other end, and the ones that aren't can never be
# settled: Match pairs two sightings of ONE movement, and refuses anything else. What is left over are the movements
# that were recorded as two transfers because whoever imported them could not tell what they were - an exchange whose
# settlement the wallet never signed, a crossing through a contract the protocol registry doesn't know - and each has
# an operation of its own that states it correctly. Converting is how the user says which.
#
# The subclass supplies what differs: the operation, the words for it, which pairs it refuses, and what is worth
# knowing about a candidate before choosing it. Everything below is the same either way - one panel of candidates on
# the other side of the movement, ranked, each carrying the reason it cannot be used when it cannot.
class LegConvertDialog(QDialog):
    OID = Qt.UserRole

    def __init__(self, oid: int, parent=None):
        super().__init__(parent)
        self.changed = False    # the caller rebuilds the ledger on it - converting writes a real operation
        self._settlement = TransferSettlement()
        self._currency = JalAsset.get_base_currency()
        self._currency_name = JalAsset(self._currency).symbol()
        self.setWindowTitle(self.title())
        self.resize(820, 440)
        self._legs = {leg['oid']: leg for leg in Transfer.pending_legs()}
        self._anchor = self._legs.get(oid)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.prompt(), self))
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
        self._buttons.button(QDialogButtonBox.Ok).setText(self.ok_text())
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._fill()
        self._candidates.itemSelectionChanged.connect(self._selection_changed)
        self._selection_changed()

    # ------------------------------------------------------------------------------------------------------------------
    # What a subclass says about its own operation
    def title(self) -> str:
        raise NotImplementedError

    def ok_text(self) -> str:
        raise NotImplementedError

    # The line above the list, describing the leg the user came from
    def prompt(self) -> str:
        raise NotImplementedError

    # Why this pair can't become the operation, or '' when it can
    def refusal(self, sending_oid: int, arriving_oid: int) -> str:
        raise NotImplementedError

    # Writes the operation. Returns '' on success, or why it was refused after all.
    def commit(self, sending_oid: int, arriving_oid: int) -> str:
        raise NotImplementedError

    # What the resulting operation will be, in one line
    def result_text(self, sent: dict, arrived: dict) -> str:
        raise NotImplementedError

    # How near this candidate is to the anchor, smallest first - what "the likeliest counterpart" means for the
    # operation being built
    def proximity(self, leg: dict):
        return abs(leg['timestamp'] - self._anchor['timestamp'])

    # What is worth knowing about a candidate, as (notes, emphasize). The notes go in its tooltip; 'emphasize' sets
    # the row in bold, for the candidate that is more than a resemblance.
    def marks(self, leg: dict) -> tuple:
        return [], False

    # ------------------------------------------------------------------------------------------------------------------
    def anchor(self) -> dict:
        return self._anchor

    # The (sending, arriving) oids of the anchor and the given leg, in the order an operation is built from
    def as_pair(self, leg: dict) -> tuple:
        return (self._anchor['oid'], leg['oid']) if self._anchor['opart'] == Transfer.Outgoing \
            else (leg['oid'], self._anchor['oid'])

    # The two legs as (sending, arriving) - the same order, resolved to the records
    def as_legs(self, leg: dict) -> tuple:
        return (self._anchor, leg) if self._anchor['opart'] == Transfer.Outgoing else (leg, self._anchor)

    def _ranked(self) -> list:
        if self._anchor is None:
            return []
        opposite = Transfer.Incoming if self._anchor['opart'] == Transfer.Outgoing else Transfer.Outgoing
        candidates = [(leg, self.refusal(*self.as_pair(leg)))
                      for leg in self._legs.values() if leg['opart'] == opposite]
        # What cannot be converted sinks to the bottom whatever it resembles - offering it first would be offering
        # the user a mistake
        return sorted(candidates, key=lambda x: (bool(x[1]), self.proximity(x[0]), x[0]['oid']))

    def _fill(self) -> None:
        self._candidates.clear()
        for leg, refusal in self._ranked():
            value = leg['qty'] * leg['asset'].quote(leg['timestamp'], self._currency)[1]
            elapsed = (leg['timestamp'] - self._anchor['timestamp']) / 86400
            item = QTreeWidgetItem([ts2dt(leg['timestamp']), leg['account'].name(),
                                    localize_decimal(remove_exponent(leg['qty'])), Transfer.leg_symbol(leg),
                                    localize_decimal(value, precision=2), f"{elapsed:+.1f} " + self.tr("days")])
            item.setData(0, self.OID, leg['oid'])
            notes, emphasize = self.marks(leg)
            if refusal:
                notes = [self.tr("Not usable here: ") + refusal] + notes
                emphasize = False
            item.setToolTip(0, '\n'.join(notes))
            if refusal or emphasize:
                font = item.font(0)
                font.setItalic(bool(refusal))
                font.setBold(bool(emphasize))
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
        refusal = self.refusal(*self.as_pair(self._legs[oid])) if oid else ''
        if not oid:
            self._status.setText(self.tr("Choose the other half of the movement."))
        elif refusal:
            self._status.setText(self.tr("These two can't be one operation: ") + refusal)
        else:
            sent, arrived = self.as_legs(self._legs[oid])
            notes, _emphasize = self.marks(self._legs[oid])
            self._status.setText('\n'.join([self.result_text(sent, arrived)] + notes))
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(bool(oid and not refusal))

    def accept(self):
        oid = self._selected_oid()
        if not oid:
            return
        refusal = self.commit(*self.as_pair(self._legs[oid]))
        if refusal:
            QMessageBox().warning(self, self.tr("Legs are not converted"), refusal)
            return
        self.changed = True
        super().accept()
