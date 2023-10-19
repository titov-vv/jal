from datetime import datetime
from dateutil import tz
from decimal import Decimal

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_transfer_operation import Ui_TransferOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.db.operations import LedgerTransaction
from jal.db.helpers import db_row2dict
from jal.db.account import JalAccount


# ----------------------------------------------------------------------------------------------------------------------
class TransferWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'withdrawal_timestamp': self.timestamp_delegate,
                          'withdrawal': self.decimal_delegate,
                          'deposit_timestamp': self.timestamp_delegate,
                          'deposit': self.decimal_delegate,
                          'fee': self.decimal_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class TransferWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_TransferOperation)
        self.name = self.tr("Transfer")
        self.operation_type = LedgerTransaction.Transfer

        self.ui.copy_date_btn.setFixedWidth(self.ui.copy_date_btn.fontMetrics().horizontalAdvance("XXXX"))
        self.ui.copy_amount_btn.setFixedWidth(self.ui.copy_amount_btn.fontMetrics().horizontalAdvance("XXXX"))
        self.ui.withdrawal_timestamp.setFixedWidth(self.ui.withdrawal_timestamp.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.deposit_timestamp.setFixedWidth(self.ui.deposit_timestamp.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.fee_account_widget.setValidation(False)
        self.ui.asset_widget.setValidation(False)

        self.ui.copy_date_btn.clicked.connect(self.onCopyDate)
        self.ui.copy_amount_btn.clicked.connect(self.onCopyAmount)

        super()._init_db("transfers")
        self.mapper.setItemDelegate(TransferWidgetDelegate(self.mapper))

        self.ui.from_account_widget.changed.connect(self.mapper.submit)
        self.ui.to_account_widget.changed.connect(self.mapper.submit)
        self.ui.fee_account_widget.changed.connect(self.mapper.submit)
        self.ui.asset_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.ui.withdrawal_timestamp, self.model.fieldIndex("withdrawal_timestamp"))
        self.mapper.addMapping(self.ui.from_account_widget, self.model.fieldIndex("withdrawal_account"))
        self.mapper.addMapping(self.ui.from_currency, self.model.fieldIndex("withdrawal_account"))
        self.mapper.addMapping(self.ui.withdrawal, self.model.fieldIndex("withdrawal"))
        self.mapper.addMapping(self.ui.deposit_timestamp, self.model.fieldIndex("deposit_timestamp"))
        self.mapper.addMapping(self.ui.to_account_widget, self.model.fieldIndex("deposit_account"))
        self.mapper.addMapping(self.ui.to_currency, self.model.fieldIndex("deposit_account"))
        self.mapper.addMapping(self.ui.deposit, self.model.fieldIndex("deposit"))
        self.mapper.addMapping(self.ui.fee_account_widget, self.model.fieldIndex("fee_account"))
        self.mapper.addMapping(self.ui.fee_currency, self.model.fieldIndex("fee_account"))
        self.mapper.addMapping(self.ui.fee, self.model.fieldIndex("fee"))
        self.mapper.addMapping(self.ui.asset_widget, self.model.fieldIndex("asset"))
        self.mapper.addMapping(self.ui.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))

        self.model.select()

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        # Set related fields NULL if we don't have fee. This is required for correct transfer processing
        if not fields['fee'] or Decimal(fields['fee']) == Decimal('0'):
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_account")), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee")), None)
        else:
            if not JalAccount(fields['fee_account']).organization():
                QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Can't collect fee from an account without organization assigned"), QMessageBox.Ok)
                return False
        if fields['asset'] == 0:   # Store None if asset isn't selected
            self.model.setData(self.model.index(0, self.model.fieldIndex("asset")), None)
        return True

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("withdrawal_timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("withdrawal_account", account_id)
        new_record.setValue("withdrawal", '0')
        new_record.setValue("deposit_timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("deposit_account", 0)
        new_record.setValue("deposit", '0')
        new_record.setValue("fee_account", 0)
        new_record.setValue("fee", '0')
        new_record.setValue("asset", None)
        new_record.setValue("number", None)
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("withdrawal_timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("deposit_timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        return new_record

    @Slot()
    def onCopyDate(self):
        self.ui.deposit_timestamp.setDateTime(self.ui.withdrawal_timestamp.dateTime())
        # mapper.submit() isn't needed here as 'changed' signal of 'deposit_timestamp' is linked with it

    @Slot()
    def onCopyAmount(self):
        self.ui.deposit.setText(self.ui.withdrawal.text())
        self.mapper.submit()
