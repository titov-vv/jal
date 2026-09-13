from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt, Slot, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_swap_operation import Ui_SwapOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.helpers import set_visible_retaining_size
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.assets_dialogs import SymbolListDialog
from jal.db.operations import LedgerTransaction, FeeKind
from jal.db.helpers import db_row2dict, now_ts
from jal.db.symbol import JalSymbol
from jal.db.common_models import AccountListModel
from jal.db.asset_models import SymbolsListModel


# ----------------------------------------------------------------------------------------------------------------------
class SwapWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'in_timestamp': self.timestamp_delegate,
                          'out_qty': self.decimal_long_delegate,
                          'in_qty': self.decimal_long_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class SwapWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_SwapOperation)
        self.name = self.tr("Swap")
        self.operation_type = LedgerTransaction.Swap
        self.ui.account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.in_account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.out_symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)
        self.ui.in_symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)

        self.ui.in_account_widget.setValidation(False)

        self.ui.cross_chain_check.clicked.connect(self.cross_chain_toggled)

        super()._init_db("swaps")
        super()._init_fees([FeeKind.Gas], precision=2)   # on-chain gas, burned in a coin of the chain
        self.mapper.setItemDelegate(SwapWidgetDelegate(self.mapper))

        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.account_widget.changed.connect(self.fee_account_changed)
        self.ui.in_account_widget.changed.connect(self.mapper.submit)
        self.ui.out_symbol_widget.changed.connect(self.mapper.submit)
        self.ui.in_symbol_widget.changed.connect(self.mapper.submit)
        self.mapper.currentIndexChanged.connect(self.record_changed)

        self.mapper.addMapping(self.ui.timestamp, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.tx_hash, self.model.fieldIndex("tx_hash"))
        self.mapper.addMapping(self.ui.out_symbol_widget, self.model.fieldIndex("out_symbol_id"))
        self.mapper.addMapping(self.ui.out_qty, self.model.fieldIndex("out_qty"))
        self.mapper.addMapping(self.ui.in_symbol_widget, self.model.fieldIndex("in_symbol_id"))
        self.mapper.addMapping(self.ui.in_qty, self.model.fieldIndex("in_qty"))
        self.mapper.addMapping(self.ui.in_timestamp, self.model.fieldIndex("in_timestamp"))
        self.mapper.addMapping(self.ui.in_account_widget, self.model.fieldIndex("in_account_id"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.in_tx_hash, self.model.fieldIndex("in_tx_hash"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    # Gas is burned on the source chain, so the account the swap starts from pays it
    def _fee_payer(self) -> int:
        return self.ui.account_widget.selected_id

    @Slot()
    def fee_account_changed(self):
        self.fee_widget.set_fee_account(self._fee_payer())

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
        # A cross-chain swap receives on another account, later; without it the receiving leg is the swap itself and
        # its fields are stored NULL (which is what makes the operation an ordinary same-chain swap)
        if self.ui.cross_chain_check.isChecked():
            if fields['in_account_id'] in (0, '0', '', None):
                QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("An account isn't chosen for the received asset"), QMessageBox.Ok)
                return False
            if str(fields['in_account_id']) == str(fields['account_id']):
                QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("A cross-chain swap should receive the asset on another account"), QMessageBox.Ok)
                return False
            if int(fields['in_timestamp']) < int(fields['timestamp']):
                QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("The asset can't be received before it was exchanged"), QMessageBox.Ok)
                return False
        else:
            self.model.setData(self.model.index(0, self.model.fieldIndex("in_timestamp")), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("in_account_id")), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("in_tx_hash")), '')
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
        new_record.setNull("in_timestamp")      # a new swap is same-chain until told otherwise
        new_record.setNull("in_account_id")
        new_record.setValue("in_tx_hash", None)
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("timestamp", now_ts())
        if not new_record.isNull("in_timestamp"):
            new_record.setValue("in_timestamp", now_ts())
        return new_record

    @Slot()
    def record_changed(self, idx):
        cross_chain = bool(self.ui.in_account_widget.selected_id)
        self.ui.cross_chain_check.setCheckState(Qt.CheckState.Checked if cross_chain else Qt.CheckState.Unchecked)
        self.set_cross_chain_data_visible(cross_chain)

    def set_cross_chain_data_visible(self, visible: bool):
        set_visible_retaining_size(self.ui.in_account_widget, visible)
        set_visible_retaining_size(self.ui.in_timestamp, visible)
        set_visible_retaining_size(self.ui.in_tx_hash, visible)

    @Slot()
    def cross_chain_toggled(self, _state):
        cross_chain = self.ui.cross_chain_check.isChecked()
        self.set_cross_chain_data_visible(cross_chain)
        if cross_chain:
            self.ui.in_timestamp.setDateTime(self.ui.timestamp.dateTime())   # the asset usually arrives soon after
        else:
            self.ui.in_account_widget.selected_id = 0
            self.ui.in_tx_hash.setText('')
        self.mapper.submit()
