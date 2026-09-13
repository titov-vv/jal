from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Slot, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_transfer_operation import Ui_TransferOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.helpers import set_visible_retaining_size
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.assets_dialogs import SymbolListDialog
from jal.db.operations import LedgerTransaction, FeeKind
from jal.db.helpers import db_row2dict, now_ts
from jal.db.account import JalAccount
from jal.db.symbol import JalSymbol
from jal.db.common_models import AccountListModel
from jal.db.asset_models import SymbolsListModel
from jal.constants import PredefinedAsset


# ----------------------------------------------------------------------------------------------------------------------
class TransferWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Delegates are keyed by model field name, not by widget name, so the editor that shares a field with
        # another page ('asset_amount' with 'withdrawal', ...) is covered by these entries too.
        self.delegates = {'withdrawal_timestamp': self.timestamp_delegate,
                          'withdrawal': self.decimal_delegate,
                          'deposit_timestamp': self.timestamp_delegate,
                          'deposit': self.decimal_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class TransferWidget(AbstractOperationDetails):
    # Indices of TransferTypeCombo - must stay in step with the page order of MoneyAssetPages in the .ui file
    MONEY_TRANSFER = 0
    ASSET_TRANSFER = 1

    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_TransferOperation)
        self.name = self.tr("Transfer")
        self.operation_type = LedgerTransaction.Transfer
        self.ui.from_account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.to_account_widget.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.symbol_widget.setup_selector(SymbolsListModel, SymbolListDialog, self)

        self.ui.symbol_widget.setValidation(False)

        self.ui.copy_date_btn.clicked.connect(self.onCopyDate)
        self.ui.copy_amount_btn.clicked.connect(self.onCopyAmount)

        super()._init_db("transfers")
        # A transfer is charged in money or in on-chain gas, and by an account that is not always one of
        # its legs - three stored transfers are charged to a third one.
        super()._init_fees([FeeKind.Commission, FeeKind.Gas], account_may_differ=True, precision=2)
        self.mapper.setItemDelegate(TransferWidgetDelegate(self.mapper))

        # Editors of the two stacked widgets that write the same model field. Only the one on the visible page may
        # stay mapped - see _map_value_widget() for why.
        self._value_widgets = {"withdrawal": (self.ui.withdrawal, self.ui.asset_amount),
                               "deposit": (self.ui.deposit, self.ui.asset_cost_basis)}

        self.ui.from_account_widget.changed.connect(self.mapper.submit)
        self.ui.from_account_widget.changed.connect(self.account_changed)
        self.ui.from_account_widget.changed.connect(self.fee_account_changed)
        self.ui.to_account_widget.changed.connect(self.mapper.submit)
        self.ui.to_account_widget.changed.connect(self.account_changed)
        self.ui.symbol_widget.changed.connect(self.mapper.submit)
        # currentIndexChanged fires for both a user choice and a programmatic one, so it may only do what is safe
        # while a record is being loaded: switch the page and move the mapping. 'activated' is emitted for a user
        # choice alone, which is what makes it the right place to drop the data of the mode being left behind.
        self.ui.TransferTypeCombo.currentIndexChanged.connect(self.transfer_type_changed)
        self.ui.TransferTypeCombo.activated.connect(self.transfer_type_selected)
        self.mapper.currentIndexChanged.connect(self.record_changed)

        self.mapper.addMapping(self.ui.withdrawal_timestamp, self.model.fieldIndex("withdrawal_timestamp"))
        # An unsettled transfer keeps one of its ends NULL, and a NULL is refused by the 'int' user property of the
        # selector - which leaves the account of the record shown before it on screen. The string property takes it
        # (empty text = nothing chosen), so both ends are mapped through it, as the other selectors below are.
        self.mapper.addMapping(self.ui.from_account_widget, self.model.fieldIndex("withdrawal_account"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.from_currency, self.model.fieldIndex("withdrawal_account"))
        self.mapper.addMapping(self.ui.deposit_timestamp, self.model.fieldIndex("deposit_timestamp"))
        self.mapper.addMapping(self.ui.to_account_widget, self.model.fieldIndex("deposit_account"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.to_currency, self.model.fieldIndex("deposit_account"))
        self.mapper.addMapping(self.ui.CostBasisCurrencyLabel, self.model.fieldIndex("deposit_account"))
        self.mapper.addMapping(self.ui.symbol_widget, self.model.fieldIndex("symbol_id"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))
        # The combo starts at index 0, so loading a record that is also at index 0 emits no currentIndexChanged and
        # would leave the shared fields unmapped. Apply the starting mapping explicitly.
        self.transfer_type_changed(self.ui.TransferTypeCombo.currentIndex())

        self.model.select()

    # Points 'field' at 'widget' and drops the editor of the other page from the mapping. A QDataWidgetMapper writes
    # *every* mapped widget back to the model on submit, so an editor left mapped on the hidden page would overwrite
    # what the user typed on the visible one with its own stale (usually empty) text.
    def _map_value_widget(self, field: str, widget) -> None:
        section = self.model.fieldIndex(field)
        for editor in self._value_widgets[field]:
            if editor is not widget:
                self.mapper.removeMapping(editor)
        self.mapper.addMapping(widget, section)
        # addMapping() does NOT load the record into the widget, and by the time the mode is switched the mapper has
        # already populated whatever was mapped when the record arrived - it emits currentIndexChanged, which drives
        # the switch, only after populating. So the editor that just became visible has to be filled here; without
        # it each operation kept displaying the amount of the one selected before it.
        row = self.mapper.currentIndex()
        if row >= 0:
            self.mapper.itemDelegate().setEditorData(widget, self.model.index(row, section))

    # Gas is burned by the wallet that signs the transaction, so a new fee starts on the sending account - but
    # a transfer may be charged anywhere, so this is a default and not a rule (see FeeWidget.set_default_account).
    def _fee_payer(self) -> int:
        return self.ui.from_account_widget.selected_id

    @Slot()
    def fee_account_changed(self):
        self.fee_widget.set_fee_account(self._fee_payer())

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not self._validated_accounts(fields):
            return False
        if not self._validated_transfer_type(fields):
            return False
        return True

    # A transfer may be left with one of its ends unknown - "money on the way" that is settled when the counterpart is
    # met (see the Transfer class). An empty selector reads back as 0, which the database must not be given: 0 is a
    # value, and only NULL says "not known yet" to the operation and to the ledger sequence. Both ends empty is not
    # a transfer at all, though - nothing would be moving.
    def _validated_accounts(self, fields) -> bool:
        empty = 0
        for field in ("withdrawal_account", "deposit_account"):
            if fields[field] in (None, '', '0', 0):
                self.model.setData(self.model.index(0, self.model.fieldIndex(field)), None)
                empty += 1
        if empty == 2:
            QMessageBox().warning(self, self.tr("Incomplete data"),
                                  self.tr("At least one account of the transfer must be chosen"), QMessageBox.Ok)
            return False
        if not empty:
            # An address stands for the end that has no account, so a transfer naming both of them has no such end left to describe.
            self.model.setData(self.model.index(0, self.model.fieldIndex("counterparty_address")), None)
        return True

    # An asset transfer is told apart from a money one by 'symbol_id' being set, so the field has to be NULL - not
    # '0' - for a money transfer, or Transfer will process it as moving an asset.
    def _validated_transfer_type(self, fields) -> bool:
        if self.ui.TransferTypeCombo.currentIndex() == self.ASSET_TRANSFER:
            if fields['symbol_id'] in (None, '', '0', 0):
                QMessageBox().warning(self, self.tr("Incomplete data"),
                                      self.tr("An asset isn't chosen for the asset transfer"), QMessageBox.Ok)
                return False
            return True
        self.model.setData(self.model.index(0, self.model.fieldIndex("symbol_id")), None)
        return True

    def revertChanges(self):
        super().revertChanges()
        self.record_changed(0)

    def prepareNew(self, account_id):
        new_record = super().prepareNew(account_id)
        new_record.setValue("withdrawal_timestamp", now_ts())
        new_record.setValue("withdrawal_account", account_id)
        new_record.setValue("withdrawal", '0')
        new_record.setValue("deposit_timestamp", now_ts())
        new_record.setNull("deposit_account")   # Unknown until chosen - a new transfer starts as an outgoing leg
        new_record.setValue("deposit", '0')
        new_record.setNull("symbol_id")
        new_record.setValue("number", None)
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("oid")
        new_record.setValue("withdrawal_timestamp", now_ts())
        new_record.setValue("deposit_timestamp", now_ts())
        return new_record

    @Slot()
    def onCopyDate(self):
        self.ui.deposit_timestamp.setDateTime(self.ui.withdrawal_timestamp.dateTime())
        self.mapper.submit()

    @Slot()
    def onCopyAmount(self):
        self.ui.deposit.setText(self.ui.withdrawal.text())
        self.mapper.submit()

    @Slot()
    def record_changed(self, idx):
        # The selector describes the record that has just been loaded. setCurrentIndex() emits currentIndexChanged
        # (page and mapping follow) but never 'activated', so loading clears nothing.
        if self.ui.symbol_widget.selected_id:
            self.ui.TransferTypeCombo.setCurrentIndex(self.ASSET_TRANSFER)
        else:
            self.ui.TransferTypeCombo.setCurrentIndex(self.MONEY_TRANSFER)
        self.account_changed()

    @Slot()
    def transfer_type_changed(self, index):
        self.ui.MoneyAssetPages.setCurrentIndex(index)
        if index == self.ASSET_TRANSFER:
            self._map_value_widget("withdrawal", self.ui.asset_amount)
            self._map_value_widget("deposit", self.ui.asset_cost_basis)
        else:
            self._map_value_widget("withdrawal", self.ui.withdrawal)
            self._map_value_widget("deposit", self.ui.deposit)
        self.account_changed()   # Display right combination of visible widgets

    @Slot()
    def transfer_type_selected(self, index):
        if index == self.MONEY_TRANSFER:
            self.ui.symbol_widget.selected_id = 0   # A money transfer moves no asset
        self.mapper.submit()

    @Slot()
    # Method shows/hides asset data that is relevant to current to/from account combination
    def account_changed(self):
        if self.ui.TransferTypeCombo.currentIndex() == self.ASSET_TRANSFER:
            # The cost basis only has to be restated when the asset lands in an account of another currency
            visible = not JalAccount(self.ui.from_account_widget.selected_id).currency() == JalAccount(self.ui.to_account_widget.selected_id).currency()
            set_visible_retaining_size(self.ui.value_label, visible)
            set_visible_retaining_size(self.ui.asset_cost_basis, visible)
            set_visible_retaining_size(self.ui.CostBasisCurrencyLabel, visible)
