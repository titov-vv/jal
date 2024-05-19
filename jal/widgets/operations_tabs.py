from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget, QStackedWidget, QMessageBox

from jal.widgets.corporate_action_widget import CorporateActionWidget
from jal.widgets.asset_payment_widget import AssetPaymentWidget
from jal.widgets.income_spending_widget import IncomeSpendingWidget
from jal.widgets.trade_widget import TradeWidget
from jal.widgets.transfer_widget import TransferWidget
from jal.widgets.term_deposit_widget import TermDepositWidget
from jal.db.operations import LedgerTransaction


class JalOperationsTabs(QStackedWidget):
    dbUpdated = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.widgets = {LedgerTransaction.NA: QWidget(self),
                        LedgerTransaction.IncomeSpending: IncomeSpendingWidget(self),
                        LedgerTransaction.AssetPayment: AssetPaymentWidget(self),
                        LedgerTransaction.Trade: TradeWidget(self),
                        LedgerTransaction.Transfer: TransferWidget(self),
                        LedgerTransaction.CorporateAction: CorporateActionWidget(self),
                        LedgerTransaction.TermDeposit: TermDepositWidget(self)}
        for key, widget in self.widgets.items():
            if key != LedgerTransaction.NA:
                widget.dbUpdated.connect(self.dbUpdated)
            self.addWidget(widget)
        self.setCurrentIndex(0)

    # Returns a dictionary of {type, name} of operations that widget is able to handle
    def get_operations_list(self) -> dict:
        operations = {}
        for key, widget in self.widgets.items():
            if hasattr(widget, "name"):
                operations[key] = widget.name
        return operations

    def _check_for_changes(self):
        for key, widget in self.widgets.items():
            if key == LedgerTransaction.NA:
                continue
            if widget.modified:
                reply = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                              widget.name +
                                              self.tr(" has uncommitted changes,\ndo you want to save it?"),
                                              QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    widget.saveChanges()
                else:
                    widget.revertChanges()

    def show_operation(self, otype, oid):
        self._check_for_changes()
        self.setCurrentIndex(otype)
        if otype != LedgerTransaction.NA:
            self.widgets[otype].set_id(oid)

    def new_operation(self, otype, account_id):
        self._check_for_changes()
        self.widgets[otype].createNew(account_id=account_id)
        self.setCurrentIndex(otype)

    @Slot()
    def copy_operation(self):
        otype = self.currentIndex()
        if otype == LedgerTransaction.NA:
            return
        self._check_for_changes()
        self.widgets[otype].copyNew()
