from PySide6.QtCore import Slot, QEvent, QStringListModel, QByteArray
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QMessageBox
from jal.ui.widgets.ui_asset_payment_operation import Ui_AssetPaymentOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.helpers import set_visible_retaining_size
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.widgets.theme import Theme, Meaning
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
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
        self.ui.symbol_widget.changed.connect(self.assetChanged)
        self.ui.type.currentIndexChanged.connect(self.typeChanged)
        self.ui.timestamp_editor.dateTimeChanged.connect(self.refreshAssetPrice)

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

    @Slot()
    def assetChanged(self):
        self.mapper.submit()
        self.refreshAssetPrice()

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
        self.refreshAssetPrice()

    def refreshAssetPrice(self):
        if self.ui.type.currentIndex() == AssetPayment.StockDividend or self.ui.type.currentIndex() == AssetPayment.StockVesting:
            dividend_timestamp = self.ui.timestamp_editor.dateTime().toSecsSinceEpoch()
            timestamp, price = JalAsset.from_symbol(self.ui.symbol_widget.selected_id).quote(dividend_timestamp,
                                                                             JalAccount(self.ui.account_widget.selected_id).currency())
            palette = QPalette(QApplication.palette(self.ui.price_edit))
            if timestamp == dividend_timestamp:
                self.ui.price_edit.setText(str(price))
                self.ui.price_edit.setToolTip("")
            else:
                self.ui.price_edit.setText(self.tr("No quote"))
                palette.setColor(QPalette.Text, Theme.text(Meaning.NEGATIVE, palette.base().color()))
                self.ui.price_edit.setToolTip(
                    self.tr("You should set quote via Data->Quotes menu for Date/Time of the dividend"))
            self.ui.price_edit.setPalette(palette)

    # The "no quote" warning above is a palette color derived from the theme, so a theme switch has to redo it
    def changeEvent(self, event):
        if event.type() == QEvent.ApplicationPaletteChange:
            self.refreshAssetPrice()
        super().changeEvent(event)

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
