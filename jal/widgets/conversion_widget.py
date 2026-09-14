from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt, Slot, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_conversion_operation import Ui_ConversionOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.assets_dialogs import SymbolListDialog
from jal.db.operations import LedgerTransaction, FeeKind
from jal.db.helpers import db_row2dict, now_ts
from jal.db.symbol import JalSymbol
from jal.db.common_models import AccountListModel
from jal.db.asset_models import SymbolsListModel


# ----------------------------------------------------------------------------------------------------------------------
class ConversionWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'out_qty': self.decimal_long_delegate,
                          'in_qty': self.decimal_long_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class ConversionWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_ConversionOperation)
        self.name = self.tr("Wrapping")
        self.operation_type = LedgerTransaction.Conversion
        self.ui.account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.out_symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)
        self.ui.in_symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)



        super()._init_db("conversions")
        super()._init_fees([FeeKind.Gas], precision=2)   # on-chain gas, burned in a coin of the chain
        self.mapper.setItemDelegate(ConversionWidgetDelegate(self.mapper))

        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.account_widget.changed.connect(self.fee_account_changed)
        self.ui.out_symbol_widget.changed.connect(self.mapper.submit)
        self.ui.in_symbol_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.ui.timestamp, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.tx_hash, self.model.fieldIndex("tx_hash"))
        self.mapper.addMapping(self.ui.out_symbol_widget, self.model.fieldIndex("out_symbol_id"))
        self.mapper.addMapping(self.ui.out_qty, self.model.fieldIndex("out_qty"))
        self.mapper.addMapping(self.ui.in_symbol_widget, self.model.fieldIndex("in_symbol_id"))
        self.mapper.addMapping(self.ui.in_qty, self.model.fieldIndex("in_qty"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    # A conversion happens on one account, which pays the gas
    def _fee_payer(self) -> int:
        return self.ui.account_widget.selected_id

    @Slot()
    def fee_account_changed(self):
        self.fee_widget.set_fee_account(self._fee_payer())

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if fields['account_id'] == 0 or fields['account_id'] == '0':
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("An account isn't chosen for the wrapping"), QMessageBox.Ok)
            return False
        if fields['out_symbol_id'] in (0, '0') or fields['in_symbol_id'] in (0, '0'):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Both converted and received symbols should be set"), QMessageBox.Ok)
            return False
        if JalSymbol(int(fields['out_symbol_id'])).asset().id() == JalSymbol(int(fields['in_symbol_id'])).asset().id():
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Can't wrap an asset into itself"), QMessageBox.Ok)
            return False
        try:
            if Decimal(fields['out_qty']) <= Decimal('0') or Decimal(fields['in_qty']) <= Decimal('0'):
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Wrapping quantities should be positive"), QMessageBox.Ok)
            return False
        return True

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("account_id", account_id)
        new_record.setValue("tx_hash", None)
        new_record.setValue("out_symbol_id", 0)
        new_record.setValue("out_qty", '0')
        new_record.setValue("in_symbol_id", 0)
        new_record.setValue("in_qty", '0')
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("timestamp", now_ts())
        return new_record

