from datetime import datetime
from dateutil import tz

from PySide2.QtCore import Qt, Slot
from PySide2.QtWidgets import QLabel, QDateTimeEdit, QLineEdit, QPushButton
from jal.constants import Setup
from jal.widgets.helpers import g_tr
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.reference_selector import AccountSelector
from jal.widgets.amount_editor import AmountEdit
from jal.widgets.delegates import WidgetMapperDelegateBase


# ----------------------------------------------------------------------------------------------------------------------
class TransferWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        WidgetMapperDelegateBase.__init__(self, parent)
        self.delegates = {1: self.timestamp_delegate,
                          3: self.float_delegate,
                          4: self.timestamp_delegate,
                          6: self.float_delegate,
                          8: self.float_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class TransferWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        AbstractOperationDetails.__init__(self, parent)
        self.name = "Transfer"

        self.from_date_label = QLabel(self)
        self.from_account_label = QLabel(self)
        self.from_amount_label = QLabel(self)
        self.to_date_label = QLabel(self)
        self.to_account_label = QLabel(self)
        self.to_amount_label = QLabel(self)
        self.fee_account_label = QLabel(self)
        self.fee_amount_label = QLabel(self)
        self.comment_label = QLabel(self)
        self.arrow_account = QLabel(self)
        self.copy_date_btn = QPushButton(self)
        self.copy_amount_btn = QPushButton(self)

        self.main_label.setText(g_tr("TransferWidget", "Transfer"))
        self.from_date_label.setText(g_tr("TransferWidget", "Date/Time"))
        self.from_account_label.setText(g_tr("TransferWidget", "From"))
        self.from_amount_label.setText(g_tr("TransferWidget", "Amount"))
        self.to_date_label.setText(g_tr("TransferWidget", "Date/Time"))
        self.to_account_label.setText(g_tr("TransferWidget", "To"))
        self.to_amount_label.setText(g_tr("TransferWidget", "Amount"))
        self.fee_account_label.setText(g_tr("TransferWidget", "Fee from"))
        self.fee_amount_label.setText(g_tr("TransferWidget", "Fee amount"))
        self.comment_label.setText(g_tr("TransferWidget", "Note"))
        self.arrow_account.setText(" ➜ ")
        self.copy_date_btn.setText("➜")
        self.copy_date_btn.setFixedWidth(self.copy_date_btn.fontMetrics().width("XXXX"))
        self.copy_amount_btn.setText("➜")
        self.copy_amount_btn.setFixedWidth(self.copy_amount_btn.fontMetrics().width("XXXX"))

        self.withdrawal_timestamp = QDateTimeEdit(self)
        self.withdrawal_timestamp.setCalendarPopup(True)
        self.withdrawal_timestamp.setTimeSpec(Qt.UTC)
        self.withdrawal_timestamp.setFixedWidth(self.withdrawal_timestamp.fontMetrics().width("00/00/0000 00:00:00") * 1.25)
        self.withdrawal_timestamp.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.deposit_timestamp = QDateTimeEdit(self)
        self.deposit_timestamp.setCalendarPopup(True)
        self.deposit_timestamp.setTimeSpec(Qt.UTC)
        self.deposit_timestamp.setFixedWidth(self.deposit_timestamp.fontMetrics().width("00/00/0000 00:00:00") * 1.25)
        self.deposit_timestamp.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.from_account_widget = AccountSelector(self)
        self.to_account_widget = AccountSelector(self)
        self.fee_account_widget = AccountSelector(self)
        self.withdrawal = AmountEdit(self)
        self.withdrawal.setAlignment(Qt.AlignRight)
        self.deposit = AmountEdit(self)
        self.deposit.setAlignment(Qt.AlignRight)
        self.fee = AmountEdit(self)
        self.fee.setAlignment(Qt.AlignRight)
        self.comment = QLineEdit(self)

        self.layout.addWidget(self.from_date_label, 1, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.from_account_label, 2, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.from_amount_label, 3, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.comment_label, 5, 0, 1, 1, Qt.AlignLeft)
        
        self.layout.addWidget(self.withdrawal_timestamp, 1, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.from_account_widget, 2, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.withdrawal, 3, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.comment, 5, 1, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.copy_date_btn, 1, 2, 1, 1)
        self.layout.addWidget(self.arrow_account, 2, 2, 1, 1, Qt.AlignCenter)
        self.layout.addWidget(self.copy_amount_btn, 3, 2, 1, 1)

        self.layout.addWidget(self.to_date_label, 1, 3, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.to_account_label, 2, 3, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.to_amount_label, 3, 3, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.fee_account_label, 4, 3, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.fee_amount_label, 5, 3, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.deposit_timestamp, 1, 4, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.to_account_widget, 2, 4, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.deposit, 3, 4, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.fee_account_widget, 4, 4, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.fee, 5, 4, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.commit_button, 0, 6, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 7, 1, 1)

        self.layout.addItem(self.verticalSpacer, 6, 0, 1, 1)
        self.layout.addItem(self.horizontalSpacer, 1, 5, 1, 1)

        self.copy_date_btn.clicked.connect(self.onCopyDate)
        self.copy_amount_btn.clicked.connect(self.onCopyAmount)

        super()._init_db("transfers")
        self.mapper.setItemDelegate(TransferWidgetDelegate(self.mapper))

        self.from_account_widget.changed.connect(self.mapper.submit)
        self.to_account_widget.changed.connect(self.mapper.submit)
        self.fee_account_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.withdrawal_timestamp, self.model.fieldIndex("withdrawal_timestamp"))
        self.mapper.addMapping(self.from_account_widget, self.model.fieldIndex("withdrawal_account"))
        self.mapper.addMapping(self.withdrawal, self.model.fieldIndex("withdrawal"))
        self.mapper.addMapping(self.deposit_timestamp, self.model.fieldIndex("deposit_timestamp"))
        self.mapper.addMapping(self.to_account_widget, self.model.fieldIndex("deposit_account"))
        self.mapper.addMapping(self.deposit, self.model.fieldIndex("deposit"))
        self.mapper.addMapping(self.fee_account_widget, self.model.fieldIndex("fee_account"))
        self.mapper.addMapping(self.fee, self.model.fieldIndex("fee"))
        self.mapper.addMapping(self.comment, self.model.fieldIndex("note"))

        self.model.select()

    @Slot()
    def saveChanges(self):
        record = self.model.record(0)
        note = record.value(self.model.fieldIndex("note"))
        if not note:  # If we don't have note - set it to NULL value  # TODO - is it really needed?
            self.model.setData(self.model.index(0, self.model.fieldIndex("note")), None)
        # Set related fields NULL if we don't have fee. This is required for correct transfer processing
        fee_amount = record.value(self.model.fieldIndex("fee"))
        if not fee_amount:
            fee_amount = 0
        if abs(float(fee_amount)) < Setup.CALC_TOLERANCE:
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_account")), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee")), None)
        super().saveChanges()

    def prepareNew(self, account_id):
        new_record = self.model.record()
        new_record.setNull("id")
        new_record.setValue("withdrawal_timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("withdrawal_account", account_id)
        new_record.setValue("withdrawal", 0)
        new_record.setValue("deposit_timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("deposit_account", 0)
        new_record.setValue("deposit", 0)
        new_record.setValue("fee_account", 0)
        new_record.setValue("fee", 0)
        new_record.setValue("asset", None)
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
        self.deposit_timestamp.setDateTime(self.withdrawal_timestamp.dateTime())
        # mapper.submit() isn't needed here as 'changed' signal of 'deposit_timestamp' is linked with it

    @Slot()
    def onCopyAmount(self):
        self.deposit.setText(self.withdrawal.text())
        self.mapper.submit()
