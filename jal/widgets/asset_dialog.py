from PySide6.QtCore import Property
from PySide6.QtSql import QSqlTableModel, QSqlRelation, QSqlRelationalDelegate
from PySide6.QtWidgets import QDialog, QDataWidgetMapper
from jal.ui.ui_asset_dlg import Ui_AssetDialog
from jal.db.helpers import db_connection, load_icon
from jal.widgets.delegates import BoolDelegate
from jal.db.reference_models import AbstractReferenceListModel


class AssetDialog(QDialog, Ui_AssetDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self._asset_id = -1
        self._model = QSqlTableModel(parent=self, db=db_connection())
        self._model.setTable("assets")

        self._mapper = QDataWidgetMapper(self._model)
        self._mapper.setModel(self._model)
        self._mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)

        self._mapper.addMapping(self.NameEdit, self._model.fieldIndex("full_name"))
        self._mapper.addMapping(self.isinEdit, self._model.fieldIndex("isin"))
        self._mapper.addMapping(self.TypeCombo, self._model.fieldIndex("type_id"))

        self._symbols_model = SymbolsListModel("asset_tickers", self.SymbolsTable)
        self.SymbolsTable.setModel(self._symbols_model)

        self._model.select()
        self._symbols_model.select()
        self._symbols_model.configureView()

        self.AddSymbolButton.setIcon(load_icon("add.png"))
        self.RemoveSymbolButton.setIcon(load_icon("delete.png"))
        self.AddDataButton.setIcon(load_icon("add.png"))
        self.RemoveDataButton.setIcon(load_icon("delete.png"))

    def getSelectedId(self):
        return self._asset_id

    def setSelectedId(self, asset_id):
        self._asset_id = asset_id
        self._model.setFilter(f"id={self._asset_id}")
        self._mapper.toFirst()
        self._symbols_model.selectAsset(asset_id)

    selected_id = Property(str, getSelectedId, setSelectedId)


class SymbolsListModel(AbstractReferenceListModel):
    def __init__(self, table, parent_view):
        AbstractReferenceListModel.__init__(self, table, parent_view)
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
        self._default_values = {'description': '', 'currency_id': 1, 'quote_source': -1, 'active': 1}
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self.setRelation(self.fieldIndex("quote_source"), QSqlRelation("data_sources", "id", "name"))

    def configureView(self):
        super().configureView()
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("quote_source"), self._lookup_delegate)
        self._bool_delegate = BoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("active"), self._bool_delegate)

    def selectAsset(self, asset_id):
        self.setFilter(f"{self._table}.asset_id = {asset_id}")
