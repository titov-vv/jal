from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt, Slot, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_bridge_operation import Ui_BridgeOperation
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
class BridgeWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'out_timestamp': self.timestamp_delegate,
                          'in_timestamp': self.timestamp_delegate,
                          'out_qty': self.decimal_long_delegate,
                          'in_qty': self.decimal_long_delegate,
                          'fee_qty': self.decimal_long_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class BridgeWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_BridgeOperation)
        self.name = self.tr("Bridge")
        self.operation_type = LedgerTransaction.Bridge
        self._from_account_model = AccountListModel(self)
        self._from_account_dialog = AccountListDialog(self)
        self.ui.from_account_widget.setup_selector(self._from_account_model, self._from_account_dialog)
        self._to_account_model = AccountListModel(self)
        self._to_account_dialog = AccountListDialog(self)
        self.ui.to_account_widget.setup_selector(self._to_account_model, self._to_account_dialog)
        self._out_symbols_model = SymbolsListModel(self)
        self._out_symbols_dialog = SymbolListDialog(self)
        self.ui.out_symbol_widget.setup_selector(self._out_symbols_model, self._out_symbols_dialog)
        self._in_symbols_model = SymbolsListModel(self)
        self._in_symbols_dialog = SymbolListDialog(self)
        self.ui.in_symbol_widget.setup_selector(self._in_symbols_model, self._in_symbols_dialog)
        self._fee_symbols_model = SymbolsListModel(self)
        self._fee_symbols_dialog = SymbolListDialog(self)
        self.ui.fee_symbol_widget.setup_selector(self._fee_symbols_model, self._fee_symbols_dialog)

        self.ui.copy_date_btn.setFixedWidth(self.ui.copy_date_btn.fontMetrics().horizontalAdvance("XXXX"))
        self.ui.copy_amount_btn.setFixedWidth(self.ui.copy_amount_btn.fontMetrics().horizontalAdvance("XXXX"))
        self.ui.out_timestamp.setFixedWidth(self.ui.out_timestamp.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.in_timestamp.setFixedWidth(self.ui.in_timestamp.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.fee_symbol_widget.setValidation(False)
        # The arriving leg is empty while the bridge is a pending half, so neither of its selectors may demand a value
        self.ui.to_account_widget.setValidation(False)
        self.ui.in_symbol_widget.setValidation(False)

        self.ui.copy_date_btn.clicked.connect(self.onCopyDate)
        self.ui.copy_amount_btn.clicked.connect(self.onCopyAmount)
        self.ui.fee_check.clicked.connect(self.fee_toggled)

        super()._init_db("bridges")
        self.mapper.setItemDelegate(BridgeWidgetDelegate(self.mapper))

        self.ui.from_account_widget.changed.connect(self.mapper.submit)
        self.ui.to_account_widget.changed.connect(self.mapper.submit)
        self.ui.out_symbol_widget.changed.connect(self.mapper.submit)
        self.ui.in_symbol_widget.changed.connect(self.mapper.submit)
        self.ui.fee_symbol_widget.changed.connect(self.mapper.submit)
        self.mapper.currentIndexChanged.connect(self.record_changed)

        self.mapper.addMapping(self.ui.out_timestamp, self.model.fieldIndex("out_timestamp"))
        self.mapper.addMapping(self.ui.from_account_widget, self.model.fieldIndex("out_account_id"))
        self.mapper.addMapping(self.ui.out_qty, self.model.fieldIndex("out_qty"))
        self.mapper.addMapping(self.ui.out_symbol_widget, self.model.fieldIndex("out_symbol_id"))
        self.mapper.addMapping(self.ui.in_timestamp, self.model.fieldIndex("in_timestamp"))
        self.mapper.addMapping(self.ui.to_account_widget, self.model.fieldIndex("in_account_id"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.in_qty, self.model.fieldIndex("in_qty"))
        self.mapper.addMapping(self.ui.in_symbol_widget, self.model.fieldIndex("in_symbol_id"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.fee_symbol_widget, self.model.fieldIndex("fee_symbol_id"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.fee_qty, self.model.fieldIndex("fee_qty"))
        self.mapper.addMapping(self.ui.out_tx_hash, self.model.fieldIndex("out_tx_hash"))
        self.mapper.addMapping(self.ui.in_tx_hash, self.model.fieldIndex("in_tx_hash"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    # A field of the arriving leg is empty while the asset is still in transit (SQL NULL reads back as '')
    @staticmethod
    def _empty(value) -> bool:
        return value in (0, '0', '', None)

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if self._empty(fields['out_account_id']):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("A sending account should be set for the bridge"), QMessageBox.Ok)
            return False
        if self._empty(fields['out_symbol_id']):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("A sent symbol should be set for the bridge"), QMessageBox.Ok)
            return False
        try:
            if Decimal(fields['out_qty']) <= Decimal('0'):
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Bridge quantities should be positive"), QMessageBox.Ok)
            return False
        # An empty arriving leg is a valid state: the bridge stays a pending half until the asset arrives on the other
        # chain and the user adopts the transfer it came as (see jal/db/bridge_matcher.py). Its fields are stored NULL.
        if self._empty(fields['in_account_id']) and self._empty(fields['in_symbol_id']) and self._empty(fields['in_qty']):
            for field in ("in_timestamp", "in_account_id", "in_symbol_id", "in_qty"):
                self.model.setData(self.model.index(0, self.model.fieldIndex(field)), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("in_tx_hash")), '')
            return self._validated_fee(fields)
        if self._empty(fields['in_account_id']) or self._empty(fields['in_symbol_id']):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Both the account and the symbol should be set for a received asset (leave the whole leg empty if it hasn't arrived yet)"), QMessageBox.Ok)
            return False
        if fields['out_account_id'] == fields['in_account_id']:
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Bridge should move the asset between two different accounts"), QMessageBox.Ok)
            return False
        if JalSymbol(int(fields['out_symbol_id'])).asset().id() != JalSymbol(int(fields['in_symbol_id'])).asset().id():
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Bridge should move the same asset between accounts (use swap operation to exchange assets)"), QMessageBox.Ok)
            return False
        if int(fields['in_timestamp']) < int(fields['out_timestamp']):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Bridge can't receive the asset before it was sent"), QMessageBox.Ok)
            return False
        try:
            if Decimal(fields['in_qty']) <= Decimal('0'):
                raise InvalidOperation
            if Decimal(fields['in_qty']) > Decimal(fields['out_qty']):
                QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Bridge can't receive more asset than was sent"), QMessageBox.Ok)
                return False
        except (InvalidOperation, TypeError):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Bridge quantities should be positive"), QMessageBox.Ok)
            return False
        return self._validated_fee(fields)

    def _validated_fee(self, fields) -> bool:
        # Set related fields NULL if we don't have fee. This is required for correct bridge processing
        if not fields['fee_qty'] or Decimal(fields['fee_qty']) == Decimal('0'):
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_symbol_id")), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_qty")), None)
        elif fields['fee_symbol_id'] in (0, '0'):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("A symbol isn't chosen for the bridge fee"), QMessageBox.Ok)
            return False
        return True

    def revertChanges(self):
        super().revertChanges()
        self.record_changed(0)

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("out_timestamp", now_ts())
        new_record.setValue("out_account_id", account_id)
        new_record.setValue("out_symbol_id", 0)
        new_record.setValue("out_qty", '0')
        new_record.setNull("in_timestamp")      # the arriving leg stays empty until the asset is received
        new_record.setNull("in_account_id")
        new_record.setNull("in_symbol_id")
        new_record.setNull("in_qty")
        new_record.setNull("fee_symbol_id")
        new_record.setValue("fee_qty", '0')
        new_record.setValue("out_tx_hash", None)
        new_record.setValue("in_tx_hash", None)
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("out_timestamp", now_ts())
        if not new_record.isNull("in_timestamp"):
            new_record.setValue("in_timestamp", now_ts())
        return new_record

    @Slot()
    def onCopyDate(self):
        self.ui.in_timestamp.setDateTime(self.ui.out_timestamp.dateTime())
        self.mapper.submit()

    @Slot()
    def onCopyAmount(self):
        self.ui.in_qty.setText(self.ui.out_qty.text())
        self.mapper.submit()

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
