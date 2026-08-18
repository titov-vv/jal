from PySide6.QtCore import Signal, Slot, QSize
from PySide6.QtWidgets import QWidget, QStackedWidget, QMessageBox

from jal.widgets.corporate_action_widget import CorporateActionWidget
from jal.widgets.asset_payment_widget import AssetPaymentWidget
from jal.widgets.income_spending_widget import IncomeSpendingWidget
from jal.widgets.trade_widget import TradeWidget
from jal.widgets.transfer_widget import TransferWidget
from jal.widgets.conversion_widget import ConversionWidget
from jal.widgets.swap_widget import SwapWidget
from jal.widgets.bridge_widget import BridgeWidget
from jal.db.operations import LedgerTransaction


class JalOperationsTabs(QStackedWidget):
    dbUpdated = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.widgets = {LedgerTransaction.NA: QWidget(self)}
        operation_widget_classes = ((LedgerTransaction.IncomeSpending, IncomeSpendingWidget),
                                    (LedgerTransaction.AssetPayment, AssetPaymentWidget),
                                    (LedgerTransaction.Trade, TradeWidget),
                                    (LedgerTransaction.Transfer, TransferWidget),
                                    (LedgerTransaction.CorporateAction, CorporateActionWidget),
                                    (LedgerTransaction.Conversion, ConversionWidget),
                                    (LedgerTransaction.Swap, SwapWidget),
                                    (LedgerTransaction.Bridge, BridgeWidget))
        for key, widget_class in operation_widget_classes:
            try:
                self.widgets[key] = widget_class(self)
            except RuntimeError:
                self.widgets[key] = QWidget(self)  # no live DB connection (e.g. Qt Designer)
        for key, widget in self.widgets.items():
            if key != LedgerTransaction.NA and hasattr(widget, "dbUpdated"):
                widget.dbUpdated.connect(self.dbUpdated)
            self.addWidget(widget)
        self.setCurrentIndex(0)

    # QStackedWidget.sizeHint() by default follows only the *current* page, which here (index 0) is always the blank
    # LedgerTransaction.NA placeholder - so without this override the widget reports a degenerate 0x0 hint
    # (harmless in the real app, where the surrounding layout stretches it, but leaves it invisible in Qt Designer).
    # Report the largest of its real pages instead, floored at a reasonable minimum for when none are available
    # (e.g. no live DB connection, so every page is itself a blank placeholder - see JalOperationsTabs.__init__).
    _MIN_SIZE_HINT = QSize(400, 300)

    def sizeHint(self):
        return self._largest_page_size(lambda w: w.sizeHint())

    def minimumSizeHint(self):
        return self._largest_page_size(lambda w: w.minimumSizeHint())

    def _largest_page_size(self, size_of):
        hint = self._MIN_SIZE_HINT
        for widget in self.widgets.values():
            size = size_of(widget)
            if size.width() * size.height() > hint.width() * hint.height():
                hint = size
        return hint

    # Returns a dictionary of {type, name} of operations that widget is able to handle
    def get_operations_list(self) -> dict:
        operations = {}
        for key, widget in self.widgets.items():
            if hasattr(widget, "name"):
                operations[key] = widget.name
        return operations

    # Asks what to do with any operation that still has unsaved changes before the view moves off it.
    # Returns False when it must not move: either the user asked to stay, or a save was asked for and refused
    # (saveChanges() runs the widget's own validation, which reports its complaint and leaves the edits pending).
    def _check_for_changes(self) -> bool:
        for key, widget in self.widgets.items():
            if key == LedgerTransaction.NA:
                continue
            if not widget.modified:
                continue
            answer = QMessageBox().warning(self, self.tr("You have unsaved changes"),
                                           widget.name +
                                           self.tr(" has unsaved changes,\ndo you want to save them?"),
                                           QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                           QMessageBox.Save)
            if answer == QMessageBox.Cancel:
                return False
            if answer == QMessageBox.Save:
                widget.saveChanges()
                if widget.modified:   # the widget refused to save, so the edits are still there to lose
                    return False
            else:
                widget.revertChanges()
        return True

    # The three navigation entry points below return False when the move was called off, so that whatever drove
    # them - a table selection, a toolbar button - can put itself back the way it was.
    def show_operation(self, otype, oid) -> bool:
        if not self._check_for_changes():
            return False
        self.setCurrentIndex(otype)
        if otype != LedgerTransaction.NA:
            self.widgets[otype].set_id(oid)
        return True

    def new_operation(self, otype, account_id) -> bool:
        if not self._check_for_changes():
            return False
        self.widgets[otype].createNew(account_id=account_id)
        self.setCurrentIndex(otype)
        return True

    @Slot()
    def copy_operation(self) -> bool:
        otype = self.currentIndex()
        if otype == LedgerTransaction.NA:
            return False
        if not self._check_for_changes():
            return False
        self.widgets[otype].copyNew()
        return True
