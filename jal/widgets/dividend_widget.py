from datetime import datetime
from dateutil import tz

from PySide6.QtCore import Qt, Slot, QStringListModel, QByteArray
from PySide6.QtWidgets import QLabel, QDateTimeEdit, QDateEdit, QLineEdit, QComboBox
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.reference_selector import AccountSelector, AssetSelector
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction, Dividend


# ----------------------------------------------------------------------------------------------------------------------
class DividendWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        WidgetMapperDelegateBase.__init__(self, parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'ex_date': self.timestamp_delegate,
                          'asset_id': self.symbol_delegate,
                          'amount': self.float_delegate,
                          'tax': self.float_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class DividendWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        AbstractOperationDetails.__init__(self, parent)
        self.name = "Dividend"
        self.operation_type = LedgerTransaction.Dividend
        self.combo_model = None

        self.date_label = QLabel(self)
        self.ex_date_label = QLabel(self)
        self.number_label = QLabel(self)
        self.type_label = QLabel(self)
        self.account_label = QLabel(self)
        self.symbol_label = QLabel(self)
        self.amount_label = QLabel(self)
        self.price_label = QLabel(self)
        self.tax_label = QLabel(self)
        self.comment_label = QLabel(self)

        self.main_label.setText(self.tr("Dividend"))
        self.date_label.setText(self.tr("Date/Time"))
        self.ex_date_label.setText(self.tr("Ex-Date"))
        self.type_label.setText(self.tr("Type"))
        self.number_label.setText(self.tr("#"))
        self.account_label.setText(self.tr("Account"))
        self.symbol_label.setText(self.tr("Asset"))
        self.amount_label.setText(self.tr("Dividend"))
        self.price_label.setText(self.tr("Price"))
        self.tax_label.setText(self.tr("Tax"))
        self.comment_label.setText(self.tr("Note"))

        self.timestamp_editor = QDateTimeEdit(self)
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)
        self.timestamp_editor.setFixedWidth(self.timestamp_editor.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.timestamp_editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.ex_date_editor = QDateEdit(self)
        self.ex_date_editor.setCalendarPopup(True)
        self.ex_date_editor.setTimeSpec(Qt.UTC)
        self.ex_date_editor.setFixedWidth(self.ex_date_editor.fontMetrics().horizontalAdvance("00/00/0000") * 1.5)
        self.ex_date_editor.setDisplayFormat("dd/MM/yyyy")
        self.type = QComboBox(self)
        self.account_widget = AccountSelector(self)
        self.asset_widget = AssetSelector(self)
        self.dividend_edit = QLineEdit(self)
        self.dividend_edit.setAlignment(Qt.AlignRight)
        self.price_edit = QLineEdit(self)
        self.price_edit.setAlignment(Qt.AlignRight)
        self.price_edit.setReadOnly(True)
        self.tax_edit = QLineEdit(self)
        self.tax_edit.setAlignment(Qt.AlignRight)
        self.number = QLineEdit(self)
        self.comment = QLineEdit(self)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.account_label, 2, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.symbol_label, 3, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.comment_label, 4, 0, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.account_widget, 2, 1, 1, 4)
        self.layout.addWidget(self.asset_widget, 3, 1, 1, 4)
        self.layout.addWidget(self.comment, 4, 1, 1, 8)

        self.layout.addWidget(self.ex_date_label, 1, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.ex_date_editor, 1, 3, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.type_label, 1, 5, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.amount_label, 2, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.tax_label, 3, 5, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.type, 1, 6, 1, 1)
        self.layout.addWidget(self.dividend_edit, 2, 6, 1, 1)
        self.layout.addWidget(self.tax_edit, 3, 6, 1, 1)

        self.layout.addWidget(self.number_label, 1, 7, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.price_label, 2, 7, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.number, 1, 8, 1, 1)
        self.layout.addWidget(self.price_edit, 2, 8, 1, 1)

        self.layout.addWidget(self.commit_button, 0, 9, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 10, 1, 1)

        self.layout.addItem(self.verticalSpacer, 5, 0, 1, 1)
        self.layout.addItem(self.horizontalSpacer, 1, 8, 1, 1)

        super()._init_db("dividends")
        self.combo_model = QStringListModel([self.tr("N/A"),
                                             self.tr("Dividend"),
                                             self.tr("Bond Interest"),
                                             self.tr("Stock Dividend")])
        self.type.setModel(self.combo_model)

        self.mapper.setItemDelegate(DividendWidgetDelegate(self.mapper))

        self.account_widget.changed.connect(self.mapper.submit)
        self.asset_widget.changed.connect(self.assetChanged)
        self.type.currentIndexChanged.connect(self.typeChanged)
        self.timestamp_editor.dateTimeChanged.connect(self.refreshAssetPrice)

        self.mapper.addMapping(self.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ex_date_editor, self.model.fieldIndex("ex_date"))
        self.mapper.addMapping(self.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.asset_widget, self.model.fieldIndex("asset_id"))
        self.mapper.addMapping(self.type, self.model.fieldIndex("type"), QByteArray().setRawData("currentIndex", 12))
        self.mapper.addMapping(self.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.dividend_edit, self.model.fieldIndex("amount"))
        self.mapper.addMapping(self.tax_edit, self.model.fieldIndex("tax"))
        self.mapper.addMapping(self.comment, self.model.fieldIndex("note"))

        self.model.select()

    @Slot()
    def assetChanged(self):
        self.mapper.submit()
        self.refreshAssetPrice()

    @Slot()
    def typeChanged(self, dividend_type_id):
        self.price_label.setVisible(dividend_type_id == Dividend.StockDividend)
        self.price_edit.setVisible(dividend_type_id == Dividend.StockDividend)
        self.refreshAssetPrice()

    def refreshAssetPrice(self):
        if self.type.currentIndex() == Dividend.StockDividend:
            price = JalDB().get_quote(self.asset_widget.selected_id,
                                      JalDB().get_account_currency(self.account_widget.selected_id),
                                      self.timestamp_editor.dateTime().toSecsSinceEpoch())
            if price is not None:
                self.price_edit.setText(str(price))
                self.price_edit.setStyleSheet('')
                self.price_edit.setToolTip("")
            else:
                self.price_edit.setText(self.tr("No quote"))
                self.price_edit.setStyleSheet("color: red")
                self.price_edit.setToolTip(
                    self.tr("You should set quote via Data->Quotes menu for Date/Time of the dividend"))

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("ex_date", 0)
        new_record.setValue("type", 0)
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("asset_id", 0)
        new_record.setValue("amount", 0)
        new_record.setValue("tax", 0)
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("ex_date", 0)
        new_record.setValue("number", '')
        return new_record
