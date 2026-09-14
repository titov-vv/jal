from PySide6.QtCore import Slot, QStringListModel, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_asset_payment_operation import Ui_AssetPaymentOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.db.helpers import db_row2dict, now_ts
from jal.db.operations import LedgerTransaction, AssetPayment, FeeKind
from jal.db.common_models import AccountListModel
from jal.db.asset_models import SymbolsListModel
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.assets_dialogs import SymbolListDialog


# ----------------------------------------------------------------------------------------------------------------------
class AssetPaymentWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'ex_date': self.timestamp_delegate,
                          'symbol_id': self.symbol_delegate,
                          'amount': self.decimal_delegate,
                          'tax': self.decimal_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class AssetPaymentWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_AssetPaymentOperation)
        self.operation_type = LedgerTransaction.AssetPayment
        self.ui.account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)
        super()._init_db("asset_payments")
        # A payment is charged in money (an ADR fee on a dividend) or in on-chain gas, and the gas of a claim is not
        # always paid by the wallet that receives it.
        super()._init_fees([FeeKind.Commission, FeeKind.Gas], account_may_differ=True, precision=2)
        names = AssetPayment.subtype_names()
        self.combo_model = QStringListModel([names[x] for x in sorted(names)])   # index == AssetPayment subtype
        self.ui.type.setModel(self.combo_model)
        self.mapper.setItemDelegate(AssetPaymentWidgetDelegate(self.mapper))

        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.account_widget.changed.connect(self.fee_account_changed)
        self.ui.symbol_widget.changed.connect(self.mapper.submit)
        self.ui.type.currentIndexChanged.connect(self.typeChanged)

        self.mapper.addMapping(self.ui.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.ex_date_editor, self.model.fieldIndex("ex_date"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.currency, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.symbol_widget, self.model.fieldIndex("symbol_id"))
        self.mapper.addMapping(self.ui.type, self.model.fieldIndex("type"), QByteArray().setRawData("currentIndex", 12))
        self.mapper.addMapping(self.ui.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.ui.dividend_edit, self.model.fieldIndex("amount"))
        self.mapper.addMapping(self.ui.tax_edit, self.model.fieldIndex("tax"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    # A payment happens on one account, which bears its fee unless the operation says otherwise
    def _fee_payer(self) -> int:
        return self.ui.account_widget.selected_id

    @Slot()
    def fee_account_changed(self):
        self.fee_widget.set_fee_account(self._fee_payer())

    @Slot()
    def typeChanged(self, dividend_type_id):
        if dividend_type_id == AssetPayment.AssetFee:
            self.ui.amount_label.setText(self.tr("Fee / Tax"))
        else:
            self.ui.amount_label.setText(self.tr("Dividend"))

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not fields['type']:
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Please set a type of the dividend."), QMessageBox.Ok)
            return False
        return True

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("ex_date", 0)
        new_record.setValue("type", 0)
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("symbol_id", 0)
        new_record.setValue("amount", '0')
        new_record.setValue("tax", '0')
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("ex_date", 0)
        new_record.setValue("number", '')
        return new_record
