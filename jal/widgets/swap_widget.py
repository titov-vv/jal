from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt, Slot, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_swap_operation import Ui_SwapOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.assets_dialogs import SymbolListDialog
from jal.db.operations import LedgerTransaction
from jal.db.helpers import db_row2dict, now_ts
from jal.db.symbol import JalSymbol
from jal.db.common_models import AccountListModel
from jal.db.asset_models import SymbolsListModel


# ----------------------------------------------------------------------------------------------------------------------
class SwapWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'out_qty': self.decimal_long_delegate,
                          'in_qty': self.decimal_long_delegate,
                          'fee_qty': self.decimal_long_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class SwapWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_SwapOperation)
        self.name = self.tr("Swap")
        self.operation_type = LedgerTransaction.Swap
        self._account_model = AccountListModel(self)
        self._account_dialog = AccountListDialog(self)
        self.ui.account_widget.setup_selector(self._account_model, self._account_dialog)
        self._out_symbols_model = SymbolsListModel(self)
        self._out_symbols_dialog = SymbolListDialog(self)
        self.ui.out_symbol_widget.setup_selector(self._out_symbols_model, self._out_symbols_dialog)
        self._in_symbols_model = SymbolsListModel(self)
        self._in_symbols_dialog = SymbolListDialog(self)
        self.ui.in_symbol_widget.setup_selector(self._in_symbols_model, self._in_symbols_dialog)
        self._fee_symbols_model = SymbolsListModel(self)
        self._fee_symbols_dialog = SymbolListDialog(self)
        self.ui.fee_symbol_widget.setup_selector(self._fee_symbols_model, self._fee_symbols_dialog)

        self.ui.timestamp.setFixedWidth(self.ui.timestamp.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.fee_symbol_widget.setValidation(False)

        self.ui.fee_check.clicked.connect(self.fee_toggled)

        super()._init_db("swaps")
        self.mapper.setItemDelegate(SwapWidgetDelegate(self.mapper))

        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.out_symbol_widget.changed.connect(self.mapper.submit)
        self.ui.in_symbol_widget.changed.connect(self.mapper.submit)
        self.ui.fee_symbol_widget.changed.connect(self.mapper.submit)
        self.mapper.currentIndexChanged.connect(self.record_changed)

        self.mapper.addMapping(self.ui.timestamp, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.tx_hash, self.model.fieldIndex("tx_hash"))
        self.mapper.addMapping(self.ui.out_symbol_widget, self.model.fieldIndex("out_symbol_id"))
        self.mapper.addMapping(self.ui.out_qty, self.model.fieldIndex("out_qty"))
        self.mapper.addMapping(self.ui.in_symbol_widget, self.model.fieldIndex("in_symbol_id"))
        self.mapper.addMapping(self.ui.in_qty, self.model.fieldIndex("in_qty"))
        self.mapper.addMapping(self.ui.fee_symbol_widget, self.model.fieldIndex("fee_symbol_id"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.fee_qty, self.model.fieldIndex("fee_qty"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if fields['account_id'] == 0 or fields['account_id'] == '0':
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("An account isn't chosen for the swap"), QMessageBox.Ok)
            return False
        if fields['out_symbol_id'] == 0 or fields['out_symbol_id'] == '0' or fields['in_symbol_id'] == 0 or fields['in_symbol_id'] == '0':
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Both sold and received symbols should be set for the swap"), QMessageBox.Ok)
            return False
        if JalSymbol(int(fields['out_symbol_id'])).asset().id() == JalSymbol(int(fields['in_symbol_id'])).asset().id():
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Can't swap an asset into itself (use bridge operation to re-list an asset)"), QMessageBox.Ok)
            return False
        try:
            if Decimal(fields['out_qty']) <= Decimal('0') or Decimal(fields['in_qty']) <= Decimal('0'):
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Swap quantities should be positive"), QMessageBox.Ok)
            return False
        # Set related fields NULL if we don't have fee. This is required for correct swap processing
        if not fields['fee_qty'] or Decimal(fields['fee_qty']) == Decimal('0'):
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_symbol_id")), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_qty")), None)
        elif fields['fee_symbol_id'] == '0' or fields['fee_symbol_id'] == 0:
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("A symbol isn't chosen for the swap fee"), QMessageBox.Ok)
            return False
        return True

    def revertChanges(self):
        super().revertChanges()
        self.record_changed(0)

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("account_id", account_id)
        new_record.setValue("tx_hash", None)
        new_record.setValue("out_symbol_id", 0)
        new_record.setValue("out_qty", '0')
        new_record.setValue("in_symbol_id", 0)
        new_record.setValue("in_qty", '0')
        new_record.setNull("fee_symbol_id")
        new_record.setValue("fee_qty", '0')
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("timestamp", now_ts())
        return new_record

    @Slot()
    def record_changed(self, idx):
        if self.ui.fee_symbol_widget.selected_id:
            self.ui.fee_check.setCheckState(Qt.CheckState.Checked)
            self.set_fee_data_visible(True)
        else:
            self.ui.fee_check.setCheckState(Qt.CheckState.Unchecked)
            self.set_fee_data_visible(False)

    def set_fee_data_visible(self, visible: bool):
        self.ui.fee_symbol_widget.setVisible(visible)
        self.ui.fee_qty.setVisible(visible)

    @Slot()
    def fee_toggled(self, _state):
        with_fee = self.ui.fee_check.isChecked()
        self.set_fee_data_visible(with_fee)
        if not with_fee:
            self.ui.fee_symbol_widget.selected_id = 0
            self.ui.fee_qty.setText('')
        self.mapper.submit()
