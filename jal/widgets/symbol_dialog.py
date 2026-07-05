import logging
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, Slot, QDateTime, QTimeZone, QLocale
from PySide6.QtSql import QSqlRelation, QSqlRelationalDelegate
from PySide6.QtWidgets import QDialog, QDataWidgetMapper, QStyledItemDelegate, QComboBox, QLineEdit, QMessageBox, QHeaderView
from jal.ui.ui_symbol_edit_dlg import Ui_SymbolDialog
from jal.constants import PredefinedAsset, AssetData, SymbolId, AssetLocation
from jal.db.helpers import localize_decimal, db_row2dict
from jal.db.asset_models import AssetRecordModel, AssetSymbolsModel, SymbolIdentifiersModel, AssetDataModel
from jal.db.common_models import TagTreeModel
from jal.widgets.delegates import DateTimeEditWithReset, BoolDelegate, ConstantLookupDelegate
from jal.widgets.icons import JalIcon
from jal.widgets.reference_selector import ReferenceSelectorWidget
from jal.widgets.reference_dialogs import TagsListDialog


# ----------------------------------------------------------------------------------------------------------------------
# Compound delegate for the 'asset_data' grid: column 'datatype' picks an AssetData attribute, column 'value' shows
# an editor that depends on the type registered for the currently selected attribute (str/int/float/date/tag).
class AssetAttributeDelegate(QStyledItemDelegate):
    def __init__(self, key_column, value_column, tag_model, tag_dialog, parent=None):
        super().__init__(parent=parent)
        self._key = key_column
        self._value = value_column
        self._types = AssetData()
        self._tag_model = tag_model
        self._tag_dialog = tag_dialog

    def _value_type(self, index):
        type_idx = index.model().data(index.sibling(index.row(), self._key), role=Qt.EditRole)
        return self._types.get_type(type_idx)

    def createEditor(self, aParent, option, index):
        if index.column() == self._key:
            editor = QComboBox(aParent)
            self._types.load2combo(editor)
            return editor
        assert index.column() == self._value, "AssetAttributeDelegate is bound to an unexpected column"
        datatype_of = self._value_type(index)
        if datatype_of in ("str", "int", "float"):
            return QLineEdit(aParent)
        elif datatype_of == "date":
            editor = DateTimeEditWithReset(aParent)
            editor.setTimeSpec(Qt.UTC)
            editor.setDisplayFormat("dd/MM/yyyy")
            return editor
        elif datatype_of == "tag":
            editor = ReferenceSelectorWidget(aParent, validate=False)
            editor.setup_selector(self._tag_model, self._tag_dialog)
            return editor
        else:
            assert False, f"Unknown asset attribute type '{datatype_of}'"

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
        elif datatype_of == "date":
            try:
                editor.setDateTime(QDateTime.fromSecsSinceEpoch(int(raw), QTimeZone(0)))
            except (TypeError, ValueError):
                QStyledItemDelegate.setEditorData(self, editor, index)
        elif datatype_of == "tag":
            try:
                editor.selected_id = int(raw)
            except (TypeError, ValueError):
                editor.selected_id = 0
        else:
            assert False, f"Unknown asset attribute type '{datatype_of}'"

    def setModelData(self, editor, model, index):
        if index.column() == self._key:
            model.setData(index, editor.currentData())
            model.setData(index.sibling(index.row(), self._value), '')  # Reset value on type change
            return
        datatype_of = self._value_type(index)
        if datatype_of == "str":
            model.setData(index, editor.text())
        elif datatype_of == "int":
            model.setData(index, str(QLocale().toInt(editor.text())[0]))
        elif datatype_of == "float":
            model.setData(index, str(QLocale().toDouble(editor.text())[0]))
        elif datatype_of == "date":
            model.setData(index, str(editor.dateTime().toSecsSinceEpoch()))
        elif datatype_of == "tag":
            model.setData(index, str(editor.selected_id))
        else:
            assert False, f"Unknown asset attribute type '{datatype_of}'"


# ----------------------------------------------------------------------------------------------------------------------
# Dialog to create/edit a single asset together with its symbols (asset_symbol), per-symbol identifiers (asset_id)
# and asset-level attributes (asset_data). Called from SymbolListDialog for 'Add' and 'Edit' actions.
#
# Because identifiers are attached to a symbol (not to the asset), a new symbol has to receive a real database id
# before identifiers can be added to it. To keep this workable, the whole edit session runs inside a single database
# transaction: the asset row (and every subsequent symbol/identifier/attribute row) is written to the database as
# soon as it is created, so child rows always know their real parent id. 'OK' commits the transaction, 'Cancel'
# (or closing the dialog) rolls it all back - so nothing is persisted unless the user confirms.
class SymbolDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_SymbolDialog()
        self.ui.setupUi(self)
        self._asset_id = 0
        self._current_symbol_id = 0

        self._model = AssetRecordModel(self)
        self._mapper = QDataWidgetMapper(self._model)
        self._mapper.setModel(self._model)
        self._mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self._mapper.addMapping(self.ui.NameEdit, self._model.fieldIndex("full_name"))
        self._mapper.addMapping(self.ui.TypeCombo, self._model.fieldIndex("type_id"))
        self._mapper.addMapping(self.ui.CountryCombo, self._model.fieldIndex("country_id"))
        self._model.select()

        self._symbols_model = AssetSymbolsModel(self)
        self.ui.SymbolsTable.setModel(self._symbols_model)
        self._symbols_model.select()
        self._configure_symbols_view()

        self._id_model = SymbolIdentifiersModel(self)
        self.ui.IdentifiersTable.setModel(self._id_model)
        self._id_model.select()
        self._configure_identifiers_view()

        self._tag_model = TagTreeModel(self)
        self._tag_dialog = TagsListDialog(self)
        self._data_model = AssetDataModel(self)
        self.ui.DataTable.setModel(self._data_model)
        self._data_model.select()
        self._configure_data_view()

        self.ui.AddSymbolButton.setIcon(JalIcon[JalIcon.ADD])
        self.ui.RemoveSymbolButton.setIcon(JalIcon[JalIcon.REMOVE])
        self.ui.AddIdButton.setIcon(JalIcon[JalIcon.ADD])
        self.ui.RemoveIdButton.setIcon(JalIcon[JalIcon.REMOVE])
        self.ui.AddDataButton.setIcon(JalIcon[JalIcon.ADD])
        self.ui.RemoveDataButton.setIcon(JalIcon[JalIcon.REMOVE])
        self.ui.OkButton.setIcon(JalIcon[JalIcon.OK])
        self.ui.CancelButton.setIcon(JalIcon[JalIcon.CANCEL])

        self.ui.SymbolsTable.selectionModel().selectionChanged.connect(self.onSymbolSelected)
        self.ui.AddSymbolButton.clicked.connect(self.onAddSymbol)
        self.ui.RemoveSymbolButton.clicked.connect(self.onRemoveSymbol)
        self.ui.AddIdButton.clicked.connect(self.onAddIdentifier)
        self.ui.RemoveIdButton.clicked.connect(self.onRemoveIdentifier)
        self.ui.AddDataButton.clicked.connect(self.onAddData)
        self.ui.RemoveDataButton.clicked.connect(self.onRemoveData)

    def _configure_symbols_view(self):
        model = self._symbols_model
        view = self.ui.SymbolsTable
        view.setColumnHidden(model.fieldIndex("id"), True)
        view.setColumnHidden(model.fieldIndex("asset_id"), True)
        view.setColumnHidden(model.fieldIndex("icon"), True)
        view.horizontalHeader().setSectionResizeMode(model.fieldIndex("symbol"), QHeaderView.Stretch)
        model.setRelation(model.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self._currency_delegate = QSqlRelationalDelegate(view)
        view.setItemDelegateForColumn(model.fieldIndex("currency_id"), self._currency_delegate)
        self._location_delegate = ConstantLookupDelegate(AssetLocation, view)
        view.setItemDelegateForColumn(model.fieldIndex("location_id"), self._location_delegate)
        self._active_delegate = BoolDelegate(view)
        view.setItemDelegateForColumn(model.fieldIndex("active"), self._active_delegate)

    def _configure_identifiers_view(self):
        model = self._id_model
        view = self.ui.IdentifiersTable
        view.setColumnHidden(model.fieldIndex("id"), True)
        view.setColumnHidden(model.fieldIndex("symbol_id"), True)
        view.horizontalHeader().setSectionResizeMode(model.fieldIndex("id_value"), QHeaderView.Stretch)
        self._idtype_delegate = ConstantLookupDelegate(SymbolId, view)
        view.setItemDelegateForColumn(model.fieldIndex("id_type"), self._idtype_delegate)

    def _configure_data_view(self):
        model = self._data_model
        view = self.ui.DataTable
        view.setColumnHidden(model.fieldIndex("id"), True)
        view.setColumnHidden(model.fieldIndex("asset_id"), True)
        view.horizontalHeader().setSectionResizeMode(model.fieldIndex("value"), QHeaderView.Stretch)
        self._attribute_delegate = AssetAttributeDelegate(model.fieldIndex("datatype"), model.fieldIndex("value"),
                                                           self._tag_model, self._tag_dialog, view)
        view.setItemDelegateForColumn(model.fieldIndex("datatype"), self._attribute_delegate)
        view.setItemDelegateForColumn(model.fieldIndex("value"), self._attribute_delegate)

    def getSelectedId(self):
        return self._asset_id

    # Opens the dialog to edit an existing asset. Starts a database transaction that is committed on OK / rolled
    # back on Cancel (see class docstring for why this is needed for the asset -> symbol -> identifier hierarchy).
    def setSelectedId(self, asset_id):
        self._model.database().transaction()
        self._asset_id = asset_id
        self._model.setFilter(f"id={self._asset_id}")
        self._mapper.toFirst()
        self._symbols_model.filterBy("asset_id", self._asset_id)
        self._data_model.filterBy("asset_id", self._asset_id)
        self._id_model.setFilter("1=0")
        self._current_symbol_id = 0
        if self._symbols_model.rowCount() > 0:
            self.ui.SymbolsTable.selectRow(0)

    # Creates a new asset. The row is written to the database immediately (inside a fresh transaction) so that
    # symbols added below already have a real asset_id to refer to.
    def createNewRecord(self):
        self._model.database().transaction()
        new_record = self._model.record()
        new_record.setNull("id")
        new_record.setValue("type_id", PredefinedAsset.Stock)
        new_record.setValue("full_name", '')
        new_record.setValue("country_id", 0)
        assert self._model.insertRows(0, 1)
        self._model.setRecord(0, new_record)
        if not self._model.submitAll():
            logging.fatal(self.tr("Failed to create new asset: ") + self._model.lastError().text())
            self._model.database().rollback()
            return
        self._asset_id = self._model.last_insert_id()
        self._model.setFilter(f"id={self._asset_id}")
        self._mapper.toFirst()
        self._symbols_model.filterBy("asset_id", self._asset_id)
        self._data_model.filterBy("asset_id", self._asset_id)
        self._id_model.setFilter("1=0")
        self._current_symbol_id = 0

    @Slot()
    def onSymbolSelected(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            self._select_symbol(self._symbols_model.getId(idx[0]))
        else:
            self._select_symbol(0)

    # Sets the symbol whose identifiers are shown in the Identifiers table. This is called both from the
    # SymbolsTable selection signal and directly after Add/Remove, since submitAll()/select() calls tend to
    # clear the view's selection (and with it, any pending selectionChanged signal) as a side effect.
    def _select_symbol(self, symbol_id):
        self._current_symbol_id = symbol_id if symbol_id else 0
        if self._current_symbol_id:
            self._id_model.filterBy("symbol_id", self._current_symbol_id)
        else:
            self._id_model.setFilter("1=0")

    @Slot()
    def onAddSymbol(self):
        idx = self.ui.SymbolsTable.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self._symbols_model.index(0, 0)
        self._symbols_model.addElement(current_index)
        if not self._symbols_model.submitAll():
            logging.fatal(self.tr("Failed to add symbol: ") + self._symbols_model.lastError().text())
            return
        self._symbols_model.select()  # re-fetch so the new row gets its real (server-assigned) id
        new_symbol_id = self._symbols_model.id_of_last_added()
        new_index = self._symbols_model.locateItem(new_symbol_id)  # table is sorted by symbol, not append order
        self.ui.SymbolsTable.setCurrentIndex(new_index)
        self.ui.SymbolsTable.selectRow(new_index.row())
        self._select_symbol(new_symbol_id)

    @Slot()
    def onRemoveSymbol(self):
        idx = self.ui.SymbolsTable.selectionModel().selection().indexes()
        if not idx:
            return
        if self._symbols_model.removeElement(idx[0]):
            self._symbols_model.submitAll()
            self._symbols_model.select()
            self._select_symbol(0)

    @Slot()
    def onAddIdentifier(self):
        if not self._current_symbol_id:
            QMessageBox().information(self, self.tr("No symbol selected"),
                                      self.tr("Please select a symbol to add an identifier to it"), QMessageBox.Ok)
            return
        idx = self.ui.IdentifiersTable.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self._id_model.index(0, 0)
        self._id_model.addElement(current_index)
        if self._id_model.submitAll():
            self._id_model.select()

    @Slot()
    def onRemoveIdentifier(self):
        idx = self.ui.IdentifiersTable.selectionModel().selection().indexes()
        if not idx:
            return
        if self._id_model.removeElement(idx[0]):
            self._id_model.submitAll()
            self._id_model.select()

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

    def validated(self):
        active_count = 0
        for row in range(self._symbols_model.rowCount()):
            if self._symbols_model.row_is_deleted(row):
                continue
            fields = db_row2dict(self._symbols_model, row)
            active_count += fields['active']
        if not active_count:
            QMessageBox().warning(self, self.tr("Incomplete data"),
                                  self.tr("Can't save asset without active symbols"), QMessageBox.Ok)
            return False
        return True

    def accept(self) -> None:
        self._mapper.submit()  # AutoSubmit normally fires on focus-out; force it in case OK was reached otherwise
        if not self.validated():
            return
        if not self._model.submitAll():
            logging.fatal(self.tr("Asset submit failed: ") + self._model.lastError().text())
            return
        self._model.database().commit()
        super().accept()

    def reject(self) -> None:
        self._model.database().rollback()
        for model in (self._data_model, self._id_model, self._symbols_model, self._model):
            model.revertAll()
        super().reject()