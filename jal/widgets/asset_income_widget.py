from decimal import Decimal
from PySide6.QtCore import Slot, QStringListModel, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_asset_income_operation import Ui_AssetIncomeOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.helpers import set_visible_retaining_size
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.db.helpers import db_row2dict, now_ts
from jal.db.operations import LedgerTransaction, AssetIncome, FeeKind
from jal.db.common_models import AccountListModel
from jal.db.asset_models import SymbolsListModel
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.assets_dialogs import SymbolListDialog


# ----------------------------------------------------------------------------------------------------------------------
class AssetIncomeWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'ex_date': self.timestamp_delegate,
                          'symbol_id': self.symbol_delegate,
                          'amount': self.decimal_long_delegate,   # a quantity of the asset, not a sum of money
                          'price': self.decimal_long_delegate,    # a per-unit price, as a trade's is
                          'tax': self.decimal_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class AssetIncomeWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_AssetIncomeOperation)
        self.operation_type = LedgerTransaction.AssetIncome
        self.ui.account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)
        super()._init_db("asset_incomes")
        # The gas of a claim, which is not always paid by the wallet that receives what was claimed
        super()._init_fees([FeeKind.Commission, FeeKind.Gas], account_may_differ=True, precision=2)
        names = AssetIncome.subtype_names()
        self.combo_model = QStringListModel([names[x] for x in sorted(names)])   # index == AssetIncome subtype
        self.ui.type.setModel(self.combo_model)
        set_visible_retaining_size(self.ui.price_label, False)
        set_visible_retaining_size(self.ui.price_edit, False)

        self.mapper.setItemDelegate(AssetIncomeWidgetDelegate(self.mapper))

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
        self.mapper.addMapping(self.ui.amount_edit, self.model.fieldIndex("amount"))
        self.mapper.addMapping(self.ui.price_edit, self.model.fieldIndex("price"))
        self.mapper.addMapping(self.ui.tax_edit, self.model.fieldIndex("tax"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    # An income arrives on one account, which bears the fee of the claim unless the operation says otherwise
    def _fee_payer(self) -> int:
        return self.ui.account_widget.selected_id

    @Slot()
    def fee_account_changed(self):
        self.fee_widget.set_fee_account(self._fee_payer())

    # The price is asked for only where the source states one; everywhere else it is read from the quote series
    @Slot()
    def typeChanged(self, income_type_id):
        if income_type_id in (AssetIncome.StockDividend, AssetIncome.StockVesting):
            self.ui.amount_label.setText(self.tr("Shares received"))
        elif income_type_id == AssetIncome.DustAttack:
            self.ui.amount_label.setText(self.tr("Dust received"))
        elif income_type_id == AssetIncome.RebaseAdjustment:
            self.ui.amount_label.setText(self.tr("Quantity gained"))   # booked at zero, see the subtype
        elif income_type_id == AssetIncome.TokenRentReturn:
            self.ui.amount_label.setText(self.tr("Rent returned"))
        else:
            self.ui.amount_label.setText(self.tr("Coins received"))
        price_visible = income_type_id in (AssetIncome.StockDividend, AssetIncome.StockVesting)
        set_visible_retaining_size(self.ui.price_label, price_visible)
        set_visible_retaining_size(self.ui.price_edit, price_visible)

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not fields['type']:
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Please set a type of the income."), QMessageBox.Ok)
            return False
        # The value granted shares were received at is what their whole cost basis rests on.
        # A zero is refused beside an empty one: nobody was ever granted shares worth nothing.
        if fields['type'] in (AssetIncome.StockDividend, AssetIncome.StockVesting):
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
