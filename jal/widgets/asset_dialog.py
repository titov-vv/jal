from PySide6.QtCore import Qt, Property
from PySide6.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation, QSqlRelationalDelegate
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QDataWidgetMapper, QHeaderView
from jal.ui.ui_asset_dlg import Ui_AssetDialog
from jal.db.helpers import db_connection, load_icon
from jal.widgets.delegates import BoolDelegate


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

        self._symbols_model = SymbolsModel(self.SymbolsTable, db_connection())
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


class SymbolsModel(QSqlRelationalTableModel):
    def __init__(self, parent_view, db):
        QSqlRelationalTableModel.__init__(self, parent=parent_view, db=db)
        self.setJoinMode(QSqlRelationalTableModel.LeftJoin)
        self.setTable("asset_tickers")
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.select()
        self._columns = [("id", ''), ("asset_id", ''), ("symbol", self.tr("Symbol")),
                         ("currency_id", self.tr("Currency")), ("description", self.tr("Description")),
                         ("quote_source", self.tr("Quotes")), ("active", self.tr("Act."))]
        self._view = parent_view
        self.deleted = []
        self._lookup_delegate = None
        self._bool_delegate = None
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self.setRelation(self.fieldIndex("quote_source"), QSqlRelation("data_sources", "id", "name"))

    def fieldIndex(self, field):
        column_data = [i for i, column in enumerate(self._columns) if column[0] == field]
        if len(column_data) > 0:
            return column_data[0]
        else:
            return -1

    def headerData(self, section, orientation=Qt.Horizontal, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._columns[section][1]
        return None

    def selectAsset(self, asset_id):
        self.setFilter(f"asset_tickers.asset_id = {asset_id}")

    def removeRow(self, row, parent=None):
        self.deleted.append(row)
        super().removeRow(row)

    def submitAll(self):
        result = super().submitAll()
        if result:
            self.deleted = []
        return result

    def revertAll(self):
        self.deleted = []
        super().revertAll()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.FontRole and (index.row() in self.deleted):
            font = QFont()
            font.setStrikeOut(True)
            return font
        return super().data(index, role)

    def configureView(self):
        self._view.setColumnHidden(0, True)
        self._view.setColumnHidden(1, True)
        self._view.setColumnWidth(2, 70)
        self._view.setColumnWidth(3, 70)
        self._view.setColumnWidth(4, 100)
        self._view.setColumnWidth(5, 70)
        self._view.setColumnWidth(6, 30)
        self._view.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("quote_source"), self._lookup_delegate)
        self._bool_delegate = BoolDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("active"), self._bool_delegate)
