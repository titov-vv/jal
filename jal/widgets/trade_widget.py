from datetime import datetime
from dateutil import tz

from jal.ui.widgets.ui_trade_operation import Ui_TradeOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.db.operations import LedgerTransaction


# ----------------------------------------------------------------------------------------------------------------------
class TradeWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'timestamp': self.timestamp_delegate,
                          'settlement': self.timestamp_delegate,
                          'asset_id': self.symbol_delegate,
                          'qty': self.decimal_long_delegate,
                          'price': self.decimal_long_delegate,
                          'fee': self.decimal_long_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class TradeWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_TradeOperation)
        self.operation_type = LedgerTransaction.Trade
        super()._init_db("trades")
        self.ui.timestamp_editor.setFixedWidth(self.ui.timestamp_editor.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.settlement_editor.setFixedWidth(self.ui.settlement_editor.fontMetrics().horizontalAdvance("00/00/0000") * 1.5)

        self.mapper.setItemDelegate(TradeWidgetDelegate(self.mapper))

        self.ui.account_widget.changed.connect(self.mapper.submit)
        self.ui.asset_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.ui.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.ui.settlement_editor, self.model.fieldIndex("settlement"))
        self.mapper.addMapping(self.ui.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.currency_price, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.currency_fee, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.ui.asset_widget, self.model.fieldIndex("asset_id"))
        self.mapper.addMapping(self.ui.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.ui.qty_edit, self.model.fieldIndex("qty"))
        self.mapper.addMapping(self.ui.price_edit, self.model.fieldIndex("price"))
        self.mapper.addMapping(self.ui.fee_edit, self.model.fieldIndex("fee"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("settlement", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("asset_id", 0)
        new_record.setValue("qty", '0')
        new_record.setValue("price", '0')
        new_record.setValue("fee", '0')
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("settlement", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        return new_record