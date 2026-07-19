import logging
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, Slot, QDateTime, QTimeZone, QLocale
from PySide6.QtWidgets import QDialog, QDataWidgetMapper, QStyledItemDelegate, QComboBox, QLineEdit, QMessageBox, QHeaderView
from jal.ui.ui_account_edit_dlg import Ui_AccountDialog
from jal.constants import AccountData, PredefinedAccountType, PredefinedAgents, AssetLocation
from jal.db.helpers import localize_decimal
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.common_models import AccountRecordModel, AccountDataModel
from jal.db.token_blacklist import normalize_address, is_valid_address
from jal.widgets.custom.db_lookup_combobox import DbLookupComboBox
from jal.widgets.icons import JalIcon


# ----------------------------------------------------------------------------------------------------------------------
# Compound delegate for the account details grid (mirrors SymbolDialog's AssetAttributeDelegate): the 'datatype'
# column picks an AccountData attribute, the 'value' column shows an editor that depends on the picked attribute's
# type (str/int/float/country).
class AccountAttributeDelegate(QStyledItemDelegate):
    def __init__(self, key_column, value_column, parent=None):
        super().__init__(parent=parent)
        self._key = key_column
        self._value = value_column
        self._types = AccountData()

    def _value_type(self, index):
        type_idx = index.model().data(index.sibling(index.row(), self._key), role=Qt.EditRole)
        return self._types.get_type(type_idx)

    # Returns the attribute type of the row the given index belongs to
    def _row_datatype(self, index):
        return index.model().data(index.sibling(index.row(), self._key), role=Qt.EditRole)

    def createEditor(self, aParent, option, index):
        # Attributes maintained by the application are shown but never edited by hand - returning no editor
        # makes both cells of such a row read-only.
        if AccountData.is_internal(self._row_datatype(index)):
            return None
        if index.column() == self._key:
            editor = QComboBox(aParent)
            self._types.load2combo(editor)
            return editor
        datatype_of = self._value_type(index)
        if datatype_of == "country":
            editor = DbLookupComboBox(aParent)
            editor.setKeyField("id")
            editor.setTable("countries_ext")
            editor.setField("name")
            return editor
        if datatype_of == "chain":
            editor = QComboBox(aParent)
            locations = AssetLocation()
            for location_id in AssetLocation.BLOCKCHAINS:   # Only blockchains, not the exchanges of the same list
                editor.addItem(locations.get_name(location_id), userData=location_id)
            return editor
        return QLineEdit(aParent)  # str / int / float share a plain line editor

    def setEditorData(self, editor, index):
        if index.column() == self._key:
            editor.setCurrentIndex(editor.findData(index.model().data(index, Qt.EditRole)))
            return
        datatype_of = self._value_type(index)
        raw = index.model().data(index, Qt.EditRole)
        if datatype_of == "str":
            editor.setText(raw if raw else '')
        elif datatype_of == "int":
            try:
                editor.setText(str(int(raw)))
            except (TypeError, ValueError):
                editor.setText('0')
        elif datatype_of == "float":
            try:
                amount = Decimal(raw)
            except (InvalidOperation, TypeError):
                amount = Decimal('0')
            editor.setText(localize_decimal(amount))
        elif datatype_of == "country":
            try:
                editor.setKey(int(raw))
            except (TypeError, ValueError):
                editor.setKey(0)
        elif datatype_of == "chain":
            try:
                editor.setCurrentIndex(editor.findData(int(raw)))
            except (TypeError, ValueError):
                editor.setCurrentIndex(0)

    def setModelData(self, editor, model, index):
        if index.column() == self._key:
            model.setData(index, editor.currentData())
            model.setData(index.sibling(index.row(), self._value), '')  # Reset value on attribute-type change
            return
        datatype_of = self._value_type(index)
        if datatype_of == "str":
            model.setData(index, editor.text())
        elif datatype_of == "int":
            model.setData(index, str(QLocale().toInt(editor.text())[0]))
        elif datatype_of == "float":
            model.setData(index, str(QLocale().toDouble(editor.text())[0]))
        elif datatype_of == "country":
            model.setData(index, str(editor.getKey()))
        elif datatype_of == "chain":
            model.setData(index, str(editor.currentData()))


# ----------------------------------------------------------------------------------------------------------------------
# Dialog to create/edit a single account together with its flexible attributes (account_data). Called from
# AccountListDialog for 'Add' and 'Edit' actions.
#
# The whole edit session runs inside a single database transaction (mirrors SymbolDialog): the account row is
# written to the database as soon as it is created, so its attribute rows always know their real account_id.
# 'OK' commits the transaction, 'Cancel' (or closing the dialog) rolls it all back.
class AccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_AccountDialog()
        self.ui.setupUi(self)
        self._account_id = 0

        self.ui.CurrencyCombo.setKeyField("id")
        self.ui.CurrencyCombo.setField("symbol")
        self.ui.CurrencyCombo.setTable("currencies")
        self.ui.OrganizationCombo.setKeyField("id")
        self.ui.OrganizationCombo.setField("name")
        self.ui.OrganizationCombo.setTable("agents")

        self._model = AccountRecordModel(self)
        self._mapper = QDataWidgetMapper(self._model)
        self._mapper.setModel(self._model)
        self._mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self._mapper.addMapping(self.ui.NameEdit, self._model.fieldIndex("name"))
        self._mapper.addMapping(self.ui.CurrencyCombo, self._model.fieldIndex("currency_id"))
        self._mapper.addMapping(self.ui.TypeCombo, self._model.fieldIndex("account_type"))
        self._mapper.addMapping(self.ui.OrganizationCombo, self._model.fieldIndex("organization_id"))
        self._mapper.addMapping(self.ui.ActiveCheck, self._model.fieldIndex("active"))
        self._mapper.addMapping(self.ui.InvestingCheck, self._model.fieldIndex("investing"))
        # 'reconciled_on' is set by JAL operations, not edited here - it's shown read-only via _load_reconciled().
        self._model.select()

        self._data_model = AccountDataModel(self)
        self.ui.DataTable.setModel(self._data_model)
        self._data_model.select()
        self._configure_data_view()

        # Registry of the dialog's grid sub-models (all OnManualSubmit): accept() submits them, reject() reverts.
        self._grid_models = ((self.tr("Account data"), self._data_model),)

        self.ui.AddDataButton.setIcon(JalIcon[JalIcon.ADD])
        self.ui.RemoveDataButton.setIcon(JalIcon[JalIcon.REMOVE])
        self.ui.OkButton.setIcon(JalIcon[JalIcon.OK])
        self.ui.CancelButton.setIcon(JalIcon[JalIcon.CANCEL])

        self.ui.AddDataButton.clicked.connect(self.onAddData)
        self.ui.RemoveDataButton.clicked.connect(self.onRemoveData)

    def _configure_data_view(self):
        model = self._data_model
        view = self.ui.DataTable
        view.setColumnHidden(model.fieldIndex("id"), True)
        view.setColumnHidden(model.fieldIndex("account_id"), True)
        view.horizontalHeader().setSectionResizeMode(model.fieldIndex("value"), QHeaderView.Stretch)
        self._attribute_delegate = AccountAttributeDelegate(model.fieldIndex("datatype"), model.fieldIndex("value"), view)
        view.setItemDelegateForColumn(model.fieldIndex("datatype"), self._attribute_delegate)
        view.setItemDelegateForColumn(model.fieldIndex("value"), self._attribute_delegate)

    def getSelectedId(self):
        return self._account_id

    # Shows the currently loaded account's reconciliation timestamp (set by JAL operations, not edited here) as a
    # read-only label. An empty label means the account has never been reconciled.
    def _load_reconciled(self):
        raw = self._model.data(self._model.index(0, self._model.fieldIndex("reconciled_on")), Qt.EditRole)
        try:
            timestamp = int(raw)
        except (TypeError, ValueError):
            timestamp = 0
        text = self.tr("Reconciled @") + QDateTime.fromSecsSinceEpoch(timestamp, QTimeZone(0)).toString("dd/MM/yyyy HH:mm:ss") if timestamp else ''
        self.ui.ReconciledValue.setText(text)

    # Opens the dialog to edit an existing account. Starts a database transaction committed on OK / rolled back on
    # Cancel (see class docstring for why the whole session is transactional).
    def setSelectedId(self, account_id):
        self._model.database().transaction()
        self._account_id = account_id
        self._model.setFilter(f"id={self._account_id}")
        self._mapper.toFirst()
        self._load_reconciled()
        self._data_model.filterBy("account_id", self._account_id)

    # Creates a new account. The row is written to the database immediately (inside a fresh transaction) so that
    # attributes added below already have a real account_id to refer to.
    def createNewRecord(self):
        self._model.database().transaction()
        new_record = self._model.record()
        new_record.setNull("id")
        new_record.setValue("name", '')
        new_record.setValue("currency_id", JalAsset.get_base_currency())
        new_record.setValue("active", 1)
        new_record.setValue("investing", 0)
        new_record.setValue("reconciled_on", 0)
        new_record.setValue("organization_id", PredefinedAgents.Empty)
        new_record.setValue("account_type", PredefinedAccountType.Cash)
        assert self._model.insertRows(0, 1)
        self._model.setRecord(0, new_record)
        if not self._model.submitAll():
            logging.fatal(self.tr("Failed to create new account: ") + self._model.lastError().text())
            self._model.database().rollback()
            return
        self._account_id = self._model.last_insert_id()
        self._model.setFilter(f"id={self._account_id}")
        self._mapper.toFirst()
        self._load_reconciled()
        self._data_model.filterBy("account_id", self._account_id)

    @Slot()
    def onAddData(self):
        idx = self.ui.DataTable.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self._data_model.index(0, 0)
        self._data_model.addElement(current_index)
        if self._data_model.submitAll():
            self._data_model.select()

    @Slot()
    def onRemoveData(self):
        idx = self.ui.DataTable.selectionModel().selection().indexes()
        if not idx:
            return
        if self._data_model.removeElement(idx[0]):
            self._data_model.submitAll()
            self._data_model.select()

    # Returns {datatype: (value, row)} of the attributes currently present in the details grid
    def _attributes(self) -> dict:
        model = self._data_model
        type_column, value_column = model.fieldIndex("datatype"), model.fieldIndex("value")
        attributes = {}
        for row in range(model.rowCount()):
            datatype = model.data(model.index(row, type_column), Qt.EditRole)
            try:
                attributes[int(datatype)] = (model.data(model.index(row, value_column), Qt.EditRole), row)
            except (TypeError, ValueError):
                continue
        return attributes

    def _warn(self, message: str) -> bool:
        QMessageBox().warning(self, self.tr("Incomplete data"), message, QMessageBox.Ok)
        return False

    # A wallet account is useless without the address and the chain it tracks, so the per-type mandatory set is
    # enforced here as well as in JalAccountCreator - imports bypass this dialog and the dialog bypasses the creator.
    def _validated_wallet(self) -> bool:
        attributes = self._attributes()
        for datatype in JalAccountCreator._MANDATORY_ATTRIBUTES.get(PredefinedAccountType.Wallet, []):
            if datatype not in attributes or not attributes[datatype][0]:
                return self._warn(self.tr("A wallet account requires attribute: ") + AccountData().get_name(datatype))
        try:
            chain = int(attributes[AccountData.Chain][0])
        except (TypeError, ValueError):
            return self._warn(self.tr("A wallet account requires a valid blockchain"))
        address, row = attributes[AccountData.Address]
        # The address is stored in the canonical form of its chain, so the entered value is normalized here and
        # written back into the grid before it is checked and submitted.
        address = normalize_address(chain, address.strip())
        self._data_model.setData(self._data_model.index(row, self._data_model.fieldIndex("value")), address)
        if not is_valid_address(chain, address):
            return self._warn(self.tr("This is not a valid address of the selected blockchain: ") + address)
        return True

    def validated(self):
        name = self._model.data(self._model.index(0, self._model.fieldIndex("name")), Qt.EditRole)
        if not name:
            return self._warn(self.tr("Account name can't be empty"))
        account_type = self._model.data(self._model.index(0, self._model.fieldIndex("account_type")), Qt.EditRole)
        try:
            account_type = int(account_type)
        except (TypeError, ValueError):
            account_type = PredefinedAccountType.Cash
        if account_type == PredefinedAccountType.Wallet:
            return self._validated_wallet()
        return True

    def accept(self) -> None:
        self._mapper.submit()  # AutoSubmit normally fires on focus-out; force it in case OK was reached otherwise
        if not self.validated():
            return
        # Grid models are OnManualSubmit - pending cell edits must be written out explicitly here. On failure the
        # dialog stays open with the transaction alive, so the user may correct the data or cancel (rolls back).
        for name, model in self._grid_models:
            if not model.submitAll():
                logging.fatal(name + self.tr(" submit failed: ") + model.lastError().text())
                return
        if not self._model.submitAll():
            logging.fatal(self.tr("Account submit failed: ") + self._model.lastError().text())
            return
        self._model.database().commit()
        self._model.invalidate_cache()
        super().accept()

    def reject(self) -> None:
        self._model.database().rollback()
        for _, model in reversed(self._grid_models):
            model.revertAll()
        self._model.revertAll()
        super().reject()
