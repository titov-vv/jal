from datetime import datetime
from dateutil import tz

from PySide6.QtCore import Slot, QStringListModel, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_dividend_operation import Ui_DividendOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.helpers import db_row2dict
from jal.db.operations import LedgerTransaction, Dividend


# ----------------------------------------------------------------------------------------------------------------------
class DividendWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'ex_date': self.timestamp_delegate,
                          'asset_id': self.symbol_delegate,
                          'amount': self.decimal_delegate,
                          'tax': self.decimal_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class DividendWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_DividendOperation)
        self.operation_type = LedgerTransaction.Dividend
        super()._init_db("dividends")
        self.combo_model = QStringListModel([self.tr("N/A"),
                                             self.tr("Dividend"),
                                             self.tr("Bond Interest"),
                                             self.tr("Stock Dividend"),
                                             self.tr("Stock Vesting")])
        self.ui.type.setModel(self.combo_model)
        self.ui.timestamp_editor.setFixedWidth(self.ui.timestamp_editor.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.ex_date_editor.setFixedWidth(self.ui.ex_date_editor.fontMetrics().horizontalAdvance("00/00/0000") * 1.5)
        self.ui.price_label.setVisible(False)
        self.ui.price_edit.setVisible(False)

        self.mapper.setItemDelegate(DividendWidgetDelegate(self.mapper))

        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.asset_widget.changed.connect(self.assetChanged)
        self.ui.type.currentIndexChanged.connect(self.typeChanged)
        self.ui.timestamp_editor.dateTimeChanged.connect(self.refreshAssetPrice)

        self.mapper.addMapping(self.ui.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.ex_date_editor, self.model.fieldIndex("ex_date"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.currency, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.asset_widget, self.model.fieldIndex("asset_id"))
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
        self.ui.price_label.setVisible(
            dividend_type_id == Dividend.StockDividend or dividend_type_id == Dividend.StockVesting)
        self.ui.price_edit.setVisible(
            dividend_type_id == Dividend.StockDividend or dividend_type_id == Dividend.StockVesting)
        self.refreshAssetPrice()

    def refreshAssetPrice(self):
        if self.ui.type.currentIndex() == Dividend.StockDividend or self.ui.type.currentIndex() == Dividend.StockVesting:
            dividend_timestamp = self.ui.timestamp_editor.dateTime().toSecsSinceEpoch()
            timestamp, price = JalAsset(self.ui.asset_widget.selected_id).quote(dividend_timestamp,
                                                                             JalAccount(self.ui.account_widget.selected_id).currency())
            if timestamp == dividend_timestamp:
                self.ui.price_edit.setText(str(price))
                self.ui.price_edit.setStyleSheet('')
                self.ui.price_edit.setToolTip("")
            else:
                self.ui.price_edit.setText(self.tr("No quote"))
                self.ui.price_edit.setStyleSheet("color: red")
                self.ui.price_edit.setToolTip(
                    self.tr("You should set quote via Data->Quotes menu for Date/Time of the dividend"))

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not fields['type']:
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Please set a type of the dividend."), QMessageBox.Ok)
            return False
        return True

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("ex_date", 0)
        new_record.setValue("type", 0)
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("asset_id", 0)
        new_record.setValue("amount", '0')
        new_record.setValue("tax", '0')
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("ex_date", 0)
        new_record.setValue("number", '')
        return new_record
