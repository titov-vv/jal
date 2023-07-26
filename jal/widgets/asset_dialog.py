import logging
from datetime import datetime
from decimal import Decimal
from PySide6.QtCore import Qt, Property, QDateTime, QTimeZone, QLocale
from PySide6.QtSql import QSqlRelation, QSqlRelationalDelegate
from PySide6.QtWidgets import QDialog, QDataWidgetMapper, QStyledItemDelegate, QComboBox, QLineEdit
from jal.ui.ui_asset_dlg import Ui_AssetDialog
from jal.constants import PredefinedAsset, AssetData, MarketDataFeed
from jal.db.helpers import load_icon, localize_decimal
from jal.widgets.delegates import DateTimeEditWithReset, BoolDelegate, ConstantLookupDelegate
from jal.db.reference_models import AbstractReferenceListModel
from jal.db.tag import JalTag
from jal.widgets.reference_selector import TagSelector


class AssetsListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("id", ''),
                         ("type_id", 'Asset type'),
                         ("full_name", self.tr("Asset name")),
                         ("isin", self.tr("ISIN")),
                         ("country_id", self.tr("Country")),
                         ("base_asset", self.tr("Base asset"))]


class AssetDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.ui = Ui_AssetDialog()
        self.ui.setupUi(self)
        self._asset_id = -1
        # Custom model to allow common submit errors handling and error message display
        self._model = AssetsListModel("assets", self)

        self._mapper = QDataWidgetMapper(self._model)
        self._mapper.setModel(self._model)
        self._mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)

        self._mapper.addMapping(self.ui.NameEdit, self._model.fieldIndex("full_name"))
        self._mapper.addMapping(self.ui.isinEdit, self._model.fieldIndex("isin"))
        self._mapper.addMapping(self.ui.TypeCombo, self._model.fieldIndex("type_id"))
        self._mapper.addMapping(self.ui.CountryCombo, self._model.fieldIndex("country_id"))
        self._mapper.addMapping(self.ui.BaseAssetSelector, self._model.fieldIndex("base_asset"))

        self._model.select()

        self._symbols_model = SymbolsListModel("asset_tickers", self.ui.SymbolsTable)
        self.ui.SymbolsTable.setModel(self._symbols_model)
        self._symbols_model.select()
        self._symbols_model.configureView()

        self._data_model = ExtraDataModel("asset_data", self.ui.DataTable)
        self.ui.DataTable.setModel(self._data_model)
        self._data_model.select()
        self._data_model.configureView()

        self.ui.AddSymbolButton.setIcon(load_icon("add.png"))
        self.ui.RemoveSymbolButton.setIcon(load_icon("delete.png"))
        self.ui.AddDataButton.setIcon(load_icon("add.png"))
        self.ui.RemoveDataButton.setIcon(load_icon("delete.png"))
        self.ui.OkButton.setIcon(load_icon("accept.png"))
        self.ui.CancelButton.setIcon(load_icon("cancel.png"))

        self.ui.TypeCombo.currentIndexChanged.connect(self.onTypeUpdate)
        self.ui.AddSymbolButton.clicked.connect(self.onAddSymbol)
        self.ui.RemoveSymbolButton.clicked.connect(self.onRemoveSymbol)
        self.ui.AddDataButton.clicked.connect(self.onAddData)
        self.ui.RemoveDataButton.clicked.connect(self.onRemoveData)

    def getSelectedId(self):
        return self._asset_id

    def setSelectedId(self, asset_id):
        self._asset_id = asset_id
        self._model.setFilter(f"id={self._asset_id}")
        self._mapper.toFirst()
        self._symbols_model.filterBy("asset_id", self._asset_id)
        self._data_model.filterBy("asset_id", self._asset_id)
        self.onTypeUpdate(0)   # need to update manually as it isn't triggered from mapper

    selected_id = Property(str, getSelectedId, setSelectedId)

    def createNewRecord(self):
        self._asset_id = 0
        self._model.setFilter(f"id={self._asset_id}")
        new_record = self._model.record()
        new_record.setNull("id")
        assert self._model.insertRows(0, 1)
        self._model.setRecord(0, new_record)
        self._mapper.toLast()
        self._symbols_model.filterBy("asset_id", self._asset_id)
        self._data_model.filterBy("asset_id", self._asset_id)

    def accept(self) -> None:
        self._model.database().transaction()
        try:
            if not self._model.submitAll():
                raise RuntimeError(self.tr("Asset submit failed: ") + self._model.lastError().text())
            asset_id = self._model.data(self._model.index(0, self._model.fieldIndex("id")))
            if asset_id is None:  # we just have saved new asset record and need last inserted id
                asset_id = self._model.last_insert_id()
            for model in [self._data_model, self._symbols_model]:
                for row in range(model.rowCount()):
                    model.setData(model.index(row, model.fieldIndex("asset_id")), asset_id)
                if not model.submitAll():
                    raise RuntimeError(self.tr("Asset details submit failed: ") + model.lastError().text())
        except Exception as e:
            self._model.database().rollback()
            logging.fatal(e)
            return
        self._asset_id = asset_id
        super().accept()

    def reject(self) -> None:
        for model in [self._data_model, self._symbols_model, self._model]:
            model.revertAll()
        super().reject()

    def onTypeUpdate(self, _index):
        if self.ui.TypeCombo.key == PredefinedAsset.Derivative:
            self.ui.BaseAssetSelector.setEnabled(True)
            self.ui.isinEdit.setEnabled(False)
        elif self.ui.TypeCombo.key == PredefinedAsset.Money or self.ui.TypeCombo.key == PredefinedAsset.Commodity:
            self.ui.BaseAssetSelector.setEnabled(False)
            self.ui.isinEdit.setEnabled(False)
        else:
            self.ui.BaseAssetSelector.setEnabled(False)
            self.ui.isinEdit.setEnabled(True)

    def onAddSymbol(self):
        idx = self.ui.SymbolsTable.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self._symbols_model.index(0, 0)
        self._symbols_model.addElement(current_index)

    def onRemoveSymbol(self):
        idx = self.ui.SymbolsTable.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self._symbols_model.index(0, 0)
        self._symbols_model.removeElement(current_index)

    def onAddData(self):
        idx = self.ui.DataTable.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self._data_model.index(0, 0)
        self._data_model.addElement(current_index)
    def onRemoveData(self):
        idx = self.ui.DataTable.selectionModel().selection().indexes()
        current_index = idx[0] if idx else self._data_model.index(0, 0)
        self._data_model.removeElement(current_index)


class SymbolsListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("id", ''),
                         ("asset_id", ''),
                         ("symbol", self.tr("Symbol")),
                         ("currency_id", self.tr("Currency")),
                         ("description", self.tr("Description")),
                         ("quote_source", self.tr("Quotes")),
                         ("active", self.tr("Act."))]
        self._default_name = "symbol"
        self._sort_by = "symbol"
        self._hidden = ["id", "asset_id"]
        self._stretch = "description"
        self._lookup_delegate = None
        self._bool_delegate = None
        self._constant_lookup_delegate = None
        self._default_values = {'description': '', 'currency_id': 1, 'quote_source': -1, 'active': 1}
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))

    def configureView(self):
        super().configureView()
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._constant_lookup_delegate = ConstantLookupDelegate(MarketDataFeed, self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("quote_source"), self._constant_lookup_delegate)
        self._bool_delegate = BoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("active"), self._bool_delegate)


# Delegate class that allows to choose data type in 'key_field' and edit data in 'value_field' (both are integer
# indices). Editors are created based on data type associated with 'key_field' via self.types dictionary
class DataDelegate(QStyledItemDelegate):    # Code doubles with pieces from delegates.py
    def __init__(self, key_field, value_field, parent=None):
        super().__init__(parent=parent)
        self._key = key_field
        self._value = value_field
        self.types = {
            AssetData.RegistrationCode: (self.tr("reg.code"), "str"),
            AssetData.ExpiryDate: (self.tr("expiry"), "date"),
            AssetData.PrincipalValue: (self.tr("principal"), "float"),
            AssetData.Tag: (self.tr("tag"), "tag")
        }

    def type(self, index):
        return self.types[index][0]

    def display_value(self, type_index, value):
        datatype = self.types[type_index][1]
        try:
            if datatype == "str":
                return value
            elif datatype == "date":
                return datetime.utcfromtimestamp(int(value)).strftime("%d/%m/%Y")
            elif datatype == "float":
                return f"{value:.2f}"
            elif datatype == "tag":
                return JalTag(int(value)).name()
            else:
                assert False, "Unknown data type of asset data"
        except ValueError:
            return ''

    def createEditor(self, aParent, option, index):
        if index.column() == self._key:
            editor = QComboBox(aParent)
            for idx in self.types:
                editor.addItem(self.types[idx][0], userData=idx)
        elif index.column() == self._value:
            type_idx = index.model().data(index.sibling(index.row(), self._key), role=Qt.EditRole)
            if self.types[type_idx][1] == "str" or self.types[type_idx][1] == "float":
                editor = QLineEdit(aParent)
            elif self.types[type_idx][1] == "date":
                editor = DateTimeEditWithReset(aParent)
                editor.setTimeSpec(Qt.UTC)
                editor.setDisplayFormat("dd/MM/yyyy")
            elif self.types[type_idx][1] == "tag":
                editor = TagSelector(aParent)
            else:
                assert False, f"Unknown data type '{self.types[type_idx][1]}' in DataDelegate.createEditor()"
        else:
            assert False, f"Delegate DataDelegate.createEditor() called for not-initialized column {index.column()}"
        return editor

    def setEditorData(self, editor, index):
        if index.column() == self._key:
            editor.setCurrentIndex(editor.findData(index.model().data(index, Qt.EditRole)))
        elif index.column() == self._value:
            type_idx = index.model().data(index.sibling(index.row(), self._key), role=Qt.EditRole)
            if self.types[type_idx][1] == "str":
                editor.setText(index.model().data(index, Qt.EditRole))
            elif self.types[type_idx][1] == "date":
                try:
                    timestamp = int(index.model().data(index, Qt.EditRole))
                    editor.setDateTime(QDateTime.fromSecsSinceEpoch(timestamp, QTimeZone(0)))
                except ValueError:
                    QStyledItemDelegate.setEditorData(self, editor, index)
            elif self.types[type_idx][1] == "float":
                try:
                    amount = Decimal(index.model().data(index, Qt.EditRole))
                except (ValueError, TypeError):
                    amount = Decimal('0')
                editor.setText(localize_decimal(amount))
            elif self.types[type_idx][1] == "tag":
                try:
                    tag_id = int(index.model().data(index, Qt.EditRole))
                except (ValueError, TypeError):
                    tag_id = 0
                editor.selected_id = tag_id
            else:
                assert False, f"Unknown data type '{self.types[type_idx][1]}' in DataDelegate.setEditorData()"
        else:
            assert False, f"Delegate DataDelegate.setEditorData() called for not-initialized column {index.column()}"

    def setModelData(self, editor, model, index):
        if index.column() == self._key:
            model.setData(index, editor.currentData())
            model.setData(index.sibling(index.row(), self._value), '')  # Reset data value on type change
        elif index.column() == self._value:
            type_idx = index.model().data(index.sibling(index.row(), self._key), role=Qt.EditRole)
            if self.types[type_idx][1] == "str":
                model.setData(index, editor.text())
            elif self.types[type_idx][1] == "date":
                timestamp = editor.dateTime().toSecsSinceEpoch()
                model.setData(index, str(timestamp))
            elif self.types[type_idx][1] == "float":
                value = QLocale().toDouble(editor.text())[0]
                model.setData(index, value)
            elif self.types[type_idx][1] == "tag":
                model.setData(index, str(editor.selected_id))
            else:
                assert False, f"Unknown data type '{self.types[type_idx][1]}' in DataDelegate.setModelData()"
        else:
            assert False, f"Delegate DataDelegate.setModelData() called for not-initialized column {index.column()}"


class ExtraDataModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        super().__init__(table=table, parent_view=parent_view)
        self._columns = [("id", ''),
                         ("asset_id", ''),
                         ("datatype", self.tr("Property")),
                         ("value", self.tr("Value"))]
        self._default_name = "datatype"
        self._sort_by = "datatype"
        self._hidden = ["id", "asset_id"]
        self._stretch = "value"
        self._data_delegate = None
        self._default_values = {'datatype': 1, 'value': ''}

    def configureView(self):
        super().configureView()
        self._data_delegate = DataDelegate(self.fieldIndex("datatype"), self.fieldIndex("value"), self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("datatype"), self._data_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("value"), self._data_delegate)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if index.column() == self.fieldIndex("datatype"):
                return self._data_delegate.type(super().data(index, role))
            elif index.column() == self.fieldIndex("value"):
                datatype = super().data(index.sibling(index.row(), self.fieldIndex("datatype")), role)
                return self._data_delegate.display_value(datatype, super().data(index, role))
        return super().data(index, role)
