from PySide6.QtWidgets import QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QDialogButtonBox, QMessageBox
from jal.db.common_models import PeerTreeModel, CategoryTreeModel
from jal.db.helpers import remove_exponent
from jal.db.operations import Transfer
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.helpers import ts2dt
from jal.widgets.reference_dialogs import PeerListDialog, CategoryListDialog
from jal.widgets.reference_selector import ReferenceSelectorWidget


# ----------------------------------------------------------------------------------------------------------------------
# Records a pending money leg as the spending or the income it is when its other end is a person and not an account.
# Asks for the two things a transfer doesn't carry: the peer and the category.
class TransferPaymentDialog(QDialog):
    def __init__(self, oid: int = 0, parent=None):
        super().__init__(parent)
        self.changed = False    # the caller rebuilds the ledger on it - converting writes a real operation
        self._oid = oid
        self._settlement = TransferSettlement()
        self._leg = next((leg for leg in Transfer.pending_legs() if leg['oid'] == oid), None)
        self._refusal = self._settlement.refusal_to_convert_to_income_spending(oid)
        sending = self._leg is not None and self._leg['opart'] == Transfer.Outgoing
        self.setWindowTitle(self.tr("Record as a spending") if sending else self.tr("Record as an income"))
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        description = QLabel(self._leg_description(sending))
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QGridLayout()
        form.addWidget(QLabel(self.tr("Peer:")), 0, 0)
        self._peer = ReferenceSelectorWidget(self)
        self._peer.setup_selector(PeerTreeModel, PeerListDialog, self)
        form.addWidget(self._peer, 0, 1)
        form.addWidget(QLabel(self.tr("Category:")), 1, 0)
        self._category = ReferenceSelectorWidget(self)
        self._category.setup_selector(CategoryTreeModel, CategoryListDialog, self)
        form.addWidget(self._category, 1, 1)
        form.addWidget(QLabel(self.tr("Note:")), 2, 0)
        self._note = QLineEdit(self)
        form.addWidget(self._note, 2, 1)
        form.setColumnStretch(1, 1)
        layout.addLayout(form)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._peer.changed.connect(self._update_ok_button)
        self._category.changed.connect(self._update_ok_button)
        self._update_ok_button()

    def _leg_description(self, sending: bool) -> str:
        if self._leg is None:
            return self.tr("This transfer is not waiting for its other end any more.")
        if self._refusal:
            return self.tr("This leg can't be recorded this way: ") + self._refusal
        leg = self._leg
        what = self.tr("{} left {} on {}.") if sending else self.tr("{} arrived at {} on {}.")
        text = what.format(f"{remove_exponent(leg['qty'])} {Transfer.leg_symbol(leg)}", leg['account'].name(),
                           ts2dt(leg['timestamp']))
        return '\n'.join([text] + ([leg['note']] if leg['note'] else []))

    def _update_ok_button(self) -> None:
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(
            bool(not self._refusal and self._peer.selected_id and self._category.selected_id))

    def accept(self):
        refusal = self._settlement.convert_to_income_spending(self._oid, self._peer.selected_id,
                                                              self._category.selected_id, self._note.text())
        if refusal:
            QMessageBox().warning(self, self.tr("The leg is not converted"), refusal)
            return
        self.changed = True
        super().accept()
