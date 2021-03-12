from datetime import datetime
from dateutil import tz

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QLabel, QDateTimeEdit, QDateEdit, QLineEdit
from jal.widgets.helpers import g_tr
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.reference_selector import AccountSelector, AssetSelector
from jal.widgets.amount_editor import AmountEdit
from jal.widgets.delegates import WidgetMapperDelegateBase


# ----------------------------------------------------------------------------------------------------------------------
class TradeWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        WidgetMapperDelegateBase.__init__(self, parent)
        self.delegates = {1: self.timestamp_delegate,
                       2: self.timestamp_delegate,
                       6: self.float_delegate,
                       7: self.float_delegate,
                       8: self.float_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class TradeWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        AbstractOperationDetails.__init__(self, parent)
        self.name = "Trade"

        self.date_label = QLabel(self)
        self.settlement_label = QLabel()
        self.number_label = QLabel(self)
        self.account_label = QLabel(self)
        self.symbol_label = QLabel(self)
        self.qty_label = QLabel(self)
        self.price_label = QLabel(self)
        self.fee_label = QLabel(self)
        self.comment_label = QLabel(self)

        self.main_label.setText(g_tr("TradeWidget", "Buy / Sell"))
        self.date_label.setText(g_tr("TradeWidget", "Date/Time"))
        self.settlement_label.setText(g_tr("TradeWidget", "Settlement"))
        self.number_label.setText(g_tr("TradeWidget", "#"))
        self.account_label.setText(g_tr("TradeWidget", "Account"))
        self.symbol_label.setText(g_tr("TradeWidget", "Asset"))
        self.qty_label.setText(g_tr("TradeWidget", "Qty"))
        self.price_label.setText(g_tr("TradeWidget", "Price"))
        self.fee_label.setText(g_tr("TradeWidget", "Fee"))
        self.comment_label.setText(g_tr("TradeWidget", "Note"))

        self.timestamp_editor = QDateTimeEdit(self)
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)
        self.timestamp_editor.setFixedWidth(self.timestamp_editor.fontMetrics().width("00/00/0000 00:00:00") * 1.25)
        self.timestamp_editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.settlement_editor = QDateEdit(self)
        self.settlement_editor.setCalendarPopup(True)
        self.settlement_editor.setTimeSpec(Qt.UTC)
        self.settlement_editor.setFixedWidth(self.settlement_editor.fontMetrics().width("00/00/0000") * 1.5)
        self.settlement_editor.setDisplayFormat("dd/MM/yyyy")
        self.account_widget = AccountSelector(self)
        self.asset_widget = AssetSelector(self)
        self.qty_edit = AmountEdit(self)
        self.qty_edit.setAlignment(Qt.AlignRight)
        self.price_edit = AmountEdit(self)
        self.price_edit.setAlignment(Qt.AlignRight)
        self.fee_edit = AmountEdit(self)
        self.fee_edit.setAlignment(Qt.AlignRight)
        self.number = QLineEdit(self)
        self.comment = QLineEdit(self)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.account_label, 2, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.symbol_label, 3, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.comment_label, 4, 0, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.account_widget, 2, 1, 1, 4)
        self.layout.addWidget(self.asset_widget, 3, 1, 1, 4)
        self.layout.addWidget(self.comment, 4, 1, 1, 4)

        self.layout.addWidget(self.settlement_label, 1, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.settlement_editor, 1, 3, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.number_label, 1, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.qty_label, 2, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.price_label, 3, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.fee_label, 4, 5, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.number, 1, 6, 1, 1)
        self.layout.addWidget(self.qty_edit, 2, 6, 1, 1)
        self.layout.addWidget(self.price_edit, 3, 6, 1, 1)
        self.layout.addWidget(self.fee_edit, 4, 6, 1, 1)

        self.layout.addWidget(self.commit_button, 0, 8, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 9, 1, 1)

        self.layout.addItem(self.verticalSpacer, 6, 6, 1, 1)
        self.layout.addItem(self.horizontalSpacer, 1, 6, 1, 1)

        super()._init_db("trades")
        self.mapper.setItemDelegate(TradeWidgetDelegate(self.mapper))

        self.account_widget.changed.connect(self.mapper.submit)
        self.asset_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.settlement_editor, self.model.fieldIndex("settlement"))
        self.mapper.addMapping(self.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.asset_widget, self.model.fieldIndex("asset_id"))
        self.mapper.addMapping(self.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.qty_edit, self.model.fieldIndex("qty"))
        self.mapper.addMapping(self.price_edit, self.model.fieldIndex("price"))
        self.mapper.addMapping(self.fee_edit, self.model.fieldIndex("fee"))
        self.mapper.addMapping(self.comment, self.model.fieldIndex("note"))

        self.model.select()

    def prepareNew(self, account_id):
        new_record = self.model.record()
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("settlement", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("asset_id", 0)
        new_record.setValue("qty", 0)
        new_record.setValue("price", 0)
        new_record.setValue("fee", 0)
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("settlement", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        return new_record