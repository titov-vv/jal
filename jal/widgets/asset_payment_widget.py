from decimal import Decimal
from PySide6.QtCore import Slot, QStringListModel, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_asset_payment_operation import Ui_AssetPaymentOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.helpers import set_visible_retaining_size
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.db.helpers import db_row2dict, now_ts
from jal.db.operations import LedgerTransaction, AssetPayment
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
                          'price': self.decimal_long_delegate,   # a per-share price, as a trade's is
                          'tax': self.decimal_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class AssetPaymentWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_AssetPaymentOperation)
        self.operation_type = LedgerTransaction.AssetPayment
        self.ui.account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)
        super()._init_db("asset_payments")
        self.combo_model = QStringListModel([self.tr("N/A"),
                                             self.tr("Dividend"),
                                             self.tr("Bond Interest"),
                                             self.tr("Stock Dividend"),
                                             self.tr("Stock Vesting"),
                                             self.tr("Bond Amortization"),
                                             self.tr("Fee / Tax"),
                                             self.tr("Gas fee"),
                                             self.tr("Staking reward"),
                                             self.tr("Dust attack"),
                                             self.tr("Reward"),
                                             self.tr("Rebase adjustment"),
                                             self.tr("Token account rent"),
                                             self.tr("Token account rent returned")])   # index == AssetPayment subtype
        self.ui.type.setModel(self.combo_model)
        set_visible_retaining_size(self.ui.price_label, False)
        set_visible_retaining_size(self.ui.price_edit, False)

        self.mapper.setItemDelegate(AssetPaymentWidgetDelegate(self.mapper))

        self.ui.account_widget.changed.connect(self.mapper.submit)
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
        self.mapper.addMapping(self.ui.price_edit, self.model.fieldIndex("price"))
        self.mapper.addMapping(self.ui.tax_edit, self.model.fieldIndex("tax"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    @Slot()
    def typeChanged(self, dividend_type_id):
        if dividend_type_id == AssetPayment.BondAmortization:
            self.ui.amount_label.setText(self.tr("Repayment"))
        elif dividend_type_id == AssetPayment.Fee:
            self.ui.amount_label.setText(self.tr("Fee / Tax"))
        elif dividend_type_id == AssetPayment.GasFee:
            self.ui.amount_label.setText(self.tr("Gas spent"))      # a quantity of the coin, not a sum of money
        elif dividend_type_id in (AssetPayment.StakingReward, AssetPayment.Reward):
            self.ui.amount_label.setText(self.tr("Coins received"))
        elif dividend_type_id == AssetPayment.DustAttack:
            self.ui.amount_label.setText(self.tr("Dust received"))      # a quantity of the coin, not a sum of money
        elif dividend_type_id == AssetPayment.RebaseAdjustment:
            self.ui.amount_label.setText(self.tr("Quantity gained"))    # a quantity of the token, booked at zero
        elif dividend_type_id == AssetPayment.TokenRent:
            self.ui.amount_label.setText(self.tr("Rent locked"))        # a quantity of the coin, not a sum of money
        elif dividend_type_id == AssetPayment.TokenRentReturn:
            self.ui.amount_label.setText(self.tr("Rent returned"))
        else:
            self.ui.amount_label.setText(self.tr("Dividend"))
        price_visible = dividend_type_id == AssetPayment.StockDividend or dividend_type_id == AssetPayment.StockVesting
        set_visible_retaining_size(self.ui.price_label, price_visible)
        set_visible_retaining_size(self.ui.price_edit, price_visible)

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not fields['type']:
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Please set a type of the dividend."), QMessageBox.Ok)
            return False
        # The value granted shares were received at is what their whole cost basis rests on.
        # A zero is refused beside an empty one: nobody was ever granted shares worth nothing.
        if fields['type'] in (AssetPayment.StockDividend, AssetPayment.StockVesting):
            if not fields['price'] or Decimal(fields['price']) <= Decimal('0'):
                QMessageBox().warning(self, self.tr("Incomplete data"),
                                      self.tr("Please set the price the stock was granted at."), QMessageBox.Ok)
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
        new_record.setValue("price", '')
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("timestamp", now_ts())
        new_record.setValue("ex_date", 0)
        new_record.setValue("number", '')
        return new_record
