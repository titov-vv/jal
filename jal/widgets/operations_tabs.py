from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget, QStackedWidget, QMessageBox

from jal.widgets.corporate_action_widget import CorporateActionWidget
from jal.widgets.dividend_widget import DividendWidget
from jal.widgets.income_spending_widget import IncomeSpendingWidget
from jal.widgets.trade_widget import TradeWidget
from jal.widgets.transfer_widget import TransferWidget
from jal.db.operations import LedgerTransaction


class JalOperationsTabs(QStackedWidget):
    dbUpdated = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.widgets = {LedgerTransaction.NA: QWidget(self),
                        LedgerTransaction.IncomeSpending: IncomeSpendingWidget(self),
                        LedgerTransaction.Dividend: DividendWidget(self), LedgerTransaction.Trade: TradeWidget(self),
                        LedgerTransaction.Transfer: TransferWidget(self),
                        LedgerTransaction.CorporateAction: CorporateActionWidget(self)}
        for key, widget in self.widgets.items():
            if key != LedgerTransaction.NA:
                widget.dbUpdated.connect(self.dbUpdated)
            self.addWidget(widget)
        self.setCurrentIndex(0)

    # Returns a dictionary of {op_type, op_name} of operations that widget is able to handle
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

    def show_operation(self, op_type, operation_id):
        self._check_for_changes()
        self.setCurrentIndex(op_type)
        if op_type != LedgerTransaction.NA:
            self.widgets[op_type].set_id(operation_id)

    def new_operation(self, op_type, account_id):
        self._check_for_changes()
        self.widgets[op_type].createNew(account_id=account_id)
        self.setCurrentIndex(op_type)

    @Slot()
    def copy_operation(self):
        op_type = self.currentIndex()
        if op_type == LedgerTransaction.NA:
            return
        self._check_for_changes()
        self.widgets[op_type].copyNew()
