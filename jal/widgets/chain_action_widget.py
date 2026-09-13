from PySide6.QtCore import Slot, QStringListModel, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_chain_action_operation import Ui_ChainActionOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.db.helpers import db_row2dict, now_ts
from jal.db.operations import LedgerTransaction, ChainAction, FeeKind
from jal.db.common_models import AccountListModel
from jal.db.asset_models import SymbolsListModel
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.assets_dialogs import SymbolListDialog


# ----------------------------------------------------------------------------------------------------------------------
class ChainActionWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'symbol_id': self.symbol_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class ChainActionWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_ChainActionOperation)
        self.operation_type = LedgerTransaction.ChainAction
        self.ui.account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)
        super()._init_db("chain_actions")
        # The whole ledger footprint of an action: gas that was consumed, or a rent that is only locked
        super()._init_fees([FeeKind.Gas, FeeKind.Rent], precision=2)
        names = ChainAction.subtype_names()
        self.combo_model = QStringListModel([names[x] for x in sorted(names)])   # index == ChainAction subtype
        self.ui.type.setModel(self.combo_model)

        self.mapper.setItemDelegate(ChainActionWidgetDelegate(self.mapper))

        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.account_widget.changed.connect(self.fee_account_changed)
        self.ui.symbol_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.ui.timestamp, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.type, self.model.fieldIndex("type"), QByteArray().setRawData("currentIndex", 12))
        self.mapper.addMapping(self.ui.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.symbol_widget, self.model.fieldIndex("symbol_id"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    # An action happens on the account that signed the transaction, and that account bears its cost by default
    def _fee_payer(self) -> int:
        return self.ui.account_widget.selected_id

    @Slot()
    def fee_account_changed(self):
        self.fee_widget.set_fee_account(self._fee_payer())

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not fields['type']:
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Please set what the event was."), QMessageBox.Ok)
            return False
        return True

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("timestamp_day_only", 0)
        new_record.setValue("number", '')
        new_record.setValue("type", 0)
        new_record.setValue("account_id", account_id)
        new_record.setNull("symbol_id")
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("number", '')
        return new_record
