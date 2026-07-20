from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Slot, QByteArray
from PySide6.QtWidgets import QMessageBox
from jal.ui.widgets.ui_transfer_operation import Ui_TransferOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.delegates import WidgetMapperDelegateBase
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.assets_dialogs import SymbolListDialog
from jal.db.operations import LedgerTransaction
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
        # Delegates are keyed by model field name, not by widget name, so the editors that share a field with
        # another page ('gas' with 'fee', 'asset_amount' with 'withdrawal', ...) are covered by these entries too.
        self.delegates = {'withdrawal_timestamp': self.timestamp_delegate,
                          'withdrawal': self.decimal_delegate,
                          'deposit_timestamp': self.timestamp_delegate,
                          'deposit': self.decimal_delegate,
                          'fee': self.decimal_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class TransferWidget(AbstractOperationDetails):
    # Indices of TransferTypeCombo - must stay in step with the page order of MoneyAssetPages in the .ui file
    MONEY_TRANSFER = 0
    ASSET_TRANSFER = 1
    # Indices of FeeGasCombo - must stay in step with the page order of FeeGasPages in the .ui file
    NO_FEE = 0
    MONEY_FEE = 1
    ASSET_GAS = 2

    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_TransferOperation)
        self.name = self.tr("Transfer")
        self.operation_type = LedgerTransaction.Transfer
        self._from_account_model = AccountListModel(self)
        self._from_account_dialog = AccountListDialog(self)
        self.ui.from_account_widget.setup_selector(self._from_account_model, self._from_account_dialog)
        self._to_account_model = AccountListModel(self)
        self._to_account_dialog = AccountListDialog(self)
        self.ui.to_account_widget.setup_selector(self._to_account_model, self._to_account_dialog)
        self._fee_account_model = AccountListModel(self)
        self._fee_account_dialog = AccountListDialog(self)
        self.ui.fee_account_widget.setup_selector(self._fee_account_model, self._fee_account_dialog)
        self._symbols_model = SymbolsListModel(self)
        self._symbols_dialog = SymbolListDialog(self)
        self.ui.symbol_widget.setup_selector(self._symbols_model, self._symbols_dialog)
        self._gas_symbols_model = SymbolsListModel(self)
        self._gas_symbols_dialog = SymbolListDialog(self)
        self.ui.gas_symbol_widget.setup_selector(self._gas_symbols_model, self._gas_symbols_dialog)

        self.ui.copy_date_btn.setFixedWidth(self.ui.copy_date_btn.fontMetrics().horizontalAdvance("XXXX"))
        self.ui.copy_amount_btn.setFixedWidth(self.ui.copy_amount_btn.fontMetrics().horizontalAdvance("XXXX"))
        self.ui.withdrawal_timestamp.setFixedWidth(self.ui.withdrawal_timestamp.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.deposit_timestamp.setFixedWidth(self.ui.deposit_timestamp.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self.ui.fee_account_widget.setValidation(False)
        self.ui.symbol_widget.setValidation(False)
        self.ui.gas_symbol_widget.setValidation(False)

        self.ui.copy_date_btn.clicked.connect(self.onCopyDate)
        self.ui.copy_amount_btn.clicked.connect(self.onCopyAmount)

        super()._init_db("transfers")
        self.mapper.setItemDelegate(TransferWidgetDelegate(self.mapper))

        # Editors of the two stacked widgets that write the same model field. Only the one on the visible page may
        # stay mapped - see _map_value_widget() for why.
        self._value_widgets = {"withdrawal": (self.ui.withdrawal, self.ui.asset_amount),
                               "deposit": (self.ui.deposit, self.ui.asset_cost_basis),
                               "fee": (self.ui.fee, self.ui.gas)}

        self.ui.from_account_widget.changed.connect(self.mapper.submit)
        self.ui.from_account_widget.changed.connect(self.account_changed)
        self.ui.to_account_widget.changed.connect(self.mapper.submit)
        self.ui.to_account_widget.changed.connect(self.account_changed)
        self.ui.fee_account_widget.changed.connect(self.mapper.submit)
        self.ui.symbol_widget.changed.connect(self.mapper.submit)
        self.ui.gas_symbol_widget.changed.connect(self.mapper.submit)
        # currentIndexChanged fires for both a user choice and a programmatic one, so it may only do what is safe
        # while a record is being loaded: switch the page and move the mapping. 'activated' is emitted for a user
        # choice alone, which is what makes it the right place to drop the data of the mode being left behind.
        self.ui.TransferTypeCombo.currentIndexChanged.connect(self.transfer_type_changed)
        self.ui.TransferTypeCombo.activated.connect(self.transfer_type_selected)
        self.ui.FeeGasCombo.currentIndexChanged.connect(self.fee_kind_changed)
        self.ui.FeeGasCombo.activated.connect(self.fee_kind_selected)
        self.mapper.currentIndexChanged.connect(self.record_changed)

        self.mapper.addMapping(self.ui.withdrawal_timestamp, self.model.fieldIndex("withdrawal_timestamp"))
        self.mapper.addMapping(self.ui.from_account_widget, self.model.fieldIndex("withdrawal_account"))
        self.mapper.addMapping(self.ui.from_currency, self.model.fieldIndex("withdrawal_account"))
        self.mapper.addMapping(self.ui.deposit_timestamp, self.model.fieldIndex("deposit_timestamp"))
        self.mapper.addMapping(self.ui.to_account_widget, self.model.fieldIndex("deposit_account"))
        self.mapper.addMapping(self.ui.to_currency, self.model.fieldIndex("deposit_account"))
        self.mapper.addMapping(self.ui.CostBasisCurrencyLabel, self.model.fieldIndex("deposit_account"))
        self.mapper.addMapping(self.ui.fee_account_widget, self.model.fieldIndex("fee_account"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.fee_currency, self.model.fieldIndex("fee_account"))
        self.mapper.addMapping(self.ui.symbol_widget, self.model.fieldIndex("symbol_id"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.gas_symbol_widget, self.model.fieldIndex("fee_symbol_id"), QByteArray("selected_id_str"))
        self.mapper.addMapping(self.ui.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.ui.note, self.model.fieldIndex("note"))
        # Both combos start at index 0, so loading a record that is also at index 0 emits no currentIndexChanged and
        # would leave the shared fields unmapped. Apply the starting mapping explicitly.
        self.transfer_type_changed(self.ui.TransferTypeCombo.currentIndex())
        self.fee_kind_changed(self.ui.FeeGasCombo.currentIndex())

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

    def _validated(self):
        fields = db_row2dict(self.model, 0)
        if not self._validated_transfer_type(fields):
            return False
        if not self._validated_fee(fields):
            return False
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

    # A fee paid in an asset instead of money exists to record on-chain gas, which is always burned in the native
    # coin of the blockchain. Restricting it to crypto keeps the asset-denominated fee out of ordinary bank and
    # broker transfers, where a fee is a money amount and the ledger has no position to take it from.
    def _validated_fee(self, fields) -> bool:
        fee_kind = self.ui.FeeGasCombo.currentIndex()
        if fee_kind == self.NO_FEE:
            # Related fields must be NULL when there is no fee. This is required for correct transfer processing.
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_account")), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee")), None)
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_symbol_id")), None)
            return True
        try:
            fee = Decimal(fields['fee']) if fields['fee'] else Decimal('0')
        except InvalidOperation:
            fee = Decimal('0')
        if fee == Decimal('0'):
            QMessageBox().warning(self, self.tr("Incomplete data"),
                                  self.tr("A fee is chosen for the transfer, but the fee amount is empty"), QMessageBox.Ok)
            return False
        if fee_kind == self.ASSET_GAS:
            if fields['fee_symbol_id'] in (None, '', '0', 0):
                QMessageBox().warning(self, self.tr("Incomplete data"),
                                      self.tr("An asset isn't chosen to pay the gas in"), QMessageBox.Ok)
                return False
            if JalSymbol(int(fields['fee_symbol_id'])).asset().type() != PredefinedAsset.Crypto:
                QMessageBox().warning(self, self.tr("Wrong data"),
                                      self.tr("A fee may be paid in a crypto asset only"), QMessageBox.Ok)
                return False
        else:
            self.model.setData(self.model.index(0, self.model.fieldIndex("fee_symbol_id")), None)
        # Both fee kinds are booked against an account with an organization - see Transfer.processLedger()
        if fields['fee_account'] in (None, '', '0', 0):
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("An account isn't chosen for fee collection from"), QMessageBox.Ok)
            return False
        if not JalAccount(int(fields['fee_account'])).organization():
            QMessageBox().warning(self, self.tr("Incomplete data"), self.tr("Can't collect fee from an account without organization assigned"), QMessageBox.Ok)
            return False
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
        new_record.setValue("deposit_account", 0)
        new_record.setValue("deposit", '0')
        new_record.setNull("fee_account")
        new_record.setValue("fee", '0')
        new_record.setNull("symbol_id")
        new_record.setNull("fee_symbol_id")
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
        # The two selectors describe the record that has just been loaded: an asset transfer carries 'symbol_id',
        # gas carries 'fee_symbol_id', and a money fee is what is left once a fee account is set. setCurrentIndex()
        # emits currentIndexChanged (page and mapping follow) but never 'activated', so loading clears nothing.
        if self.ui.symbol_widget.selected_id:
            self.ui.TransferTypeCombo.setCurrentIndex(self.ASSET_TRANSFER)
        else:
            self.ui.TransferTypeCombo.setCurrentIndex(self.MONEY_TRANSFER)
        if self.ui.gas_symbol_widget.selected_id:
            self.ui.FeeGasCombo.setCurrentIndex(self.ASSET_GAS)
        elif self.ui.fee_account_widget.selected_id:
            self.ui.FeeGasCombo.setCurrentIndex(self.MONEY_FEE)
        else:
            self.ui.FeeGasCombo.setCurrentIndex(self.NO_FEE)
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
    def fee_kind_changed(self, index):
        self.ui.FeeGasPages.setCurrentIndex(index)
        self._map_value_widget("fee", self.ui.gas if index == self.ASSET_GAS else self.ui.fee)

    @Slot()
    def fee_kind_selected(self, index):
        if index == self.NO_FEE:
            self.ui.fee_account_widget.selected_id = 0
            self.ui.gas_symbol_widget.selected_id = 0
            self.ui.fee.setText('')
            self.ui.gas.setText('')
        elif index == self.MONEY_FEE:
            self.ui.gas_symbol_widget.selected_id = 0   # A money fee isn't paid in an asset
            self.ui.gas.setText('')
        else:
            self.ui.fee.setText('')
            self._sync_gas_account()
        self.mapper.submit()

    # Gas is burned by the wallet that signs the transaction, so it is always taken from the account the assets
    # leave - the same rule the chain fetchers apply ("the gas is always paid by the wallet being fetched"). GasPage
    # has no account selector of its own, but Transfer.processLedger() books either kind of fee against an account,
    # so the fee account follows 'From'.
    def _sync_gas_account(self):
        if self.ui.FeeGasCombo.currentIndex() == self.ASSET_GAS:
            self.ui.fee_account_widget.selected_id = self.ui.from_account_widget.selected_id

    @Slot()
    # Method shows/hides asset data that is relevant to current to/from account combination
    def account_changed(self):
        self._sync_gas_account()
        if self.ui.TransferTypeCombo.currentIndex() == self.ASSET_TRANSFER:
            # The cost basis only has to be restated when the asset lands in an account of another currency
            visible = not JalAccount(self.ui.from_account_widget.selected_id).currency() == JalAccount(self.ui.to_account_widget.selected_id).currency()
            self.ui.value_label.setVisible(visible)
            self.ui.asset_cost_basis.setVisible(visible)
            self.ui.CostBasisCurrencyLabel.setVisible(visible)
