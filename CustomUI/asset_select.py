import logging

from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide2.QtSql import QSqlRelationalTableModel, QSqlRelation, QSqlRelationalDelegate, QSqlTableModel
from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QCompleter, QHeaderView

from UI.ui_asset_choice_dlg import Ui_AssetChoiceDlg
from constants import *


class AssetChoiceDlg(QDialog, Ui_AssetChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.db = None
        self.Model = None
        self.asset_id = 0
        self.type_id = 0

        self.AssetTypeCombo.currentIndexChanged.connect(self.OnTypeChange)
        self.AddAssetBtn.clicked.connect(self.OnAdd)
        self.RemoveAssetBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlRelationalTableModel(db=self.db)
        self.Model.setTable("assets")
        self.Model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.Model.setJoinMode(QSqlRelationalTableModel.LeftJoin)  # to work correctly with NULL values in SrcId
        type_idx = self.Model.fieldIndex("type_id")
        self.Model.setRelation(type_idx, QSqlRelation("asset_types", "id", "name"))
        data_src_id = self.Model.fieldIndex("src_id")
        self.Model.setRelation(data_src_id, QSqlRelation("data_sources", "id", "name"))
        self.Model.setHeaderData(self.Model.fieldIndex("name"), Qt.Horizontal, "Symbol")
        self.Model.setHeaderData(self.Model.fieldIndex("type_id"), Qt.Horizontal, "Type")
        self.Model.setHeaderData(self.Model.fieldIndex("full_name"), Qt.Horizontal, "Name")
        self.Model.setHeaderData(self.Model.fieldIndex("isin"), Qt.Horizontal, "ISIN")
        self.Model.setHeaderData(self.Model.fieldIndex("web_id"), Qt.Horizontal, "WebID")
        self.Model.setHeaderData(self.Model.fieldIndex("src_id"), Qt.Horizontal, "Data source")

        self.AssetsList.setModel(self.Model)
        self.AssetsList.setItemDelegate(ActiveDelegate(self.AssetsList))
        self.AssetsList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.AssetsList.setColumnHidden(self.Model.fieldIndex("type_id"), True)
        self.AssetsList.horizontalHeader().setSectionResizeMode(self.Model.fieldIndex("full_name"), QHeaderView.Stretch)
        font = self.AssetsList.horizontalHeader().font()
        font.setBold(True)
        self.AssetsList.horizontalHeader().setFont(font)

        self.AssetTypeCombo.setModel(self.Model.relationModel(type_idx))
        self.AssetTypeCombo.setModelColumn(self.Model.relationModel(type_idx).fieldIndex("name"))

        self.AssetsList.selectionModel().selectionChanged.connect(self.OnActiveChosen)
        self.Model.dataChanged.connect(self.OnDataChanged)
        self.Model.select()

    @Slot()
    def OnTypeChange(self, list_id):
        model = self.AssetTypeCombo.model()
        self.type_id = model.data(model.index(list_id, model.fieldIndex("id")))
        self.setActiveFilter()

    def setActiveFilter(self):
        asset_filter = ""
        if self.type_id:
            asset_filter = f"assets.type_id={self.type_id}"
        self.AssetsList.model().setFilter(asset_filter)

    @Slot()
    def OnActiveChosen(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            self.asset_id = self.AssetsList.model().record(selected_row).value(0)

    @Slot()
    def OnDataChanged(self):
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnAdd(self):
        new_record = self.AssetsList.model().record()
        new_record.setValue(2, self.type_id)  # set current type
        assert self.AssetsList.model().insertRows(0, 1)
        self.AssetsList.model().setRecord(0, new_record)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.AssetsList.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.AssetsList.model().removeRow(selected_row)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.AssetsList.model().submitAll():
            logging.fatal(self.tr("Action submit failed: ") + self.AssetsList.model().lastError().text())
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.AssetsList.model().revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)


######################################################################################################################
# The class itself is empty but it activates editors to use lookup tables
######################################################################################################################
class ActiveDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)


######################################################################################################################
# Full fledged selector for assets
######################################################################################################################
class AssetSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.completer = None
        self.p_asset_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.symbol = QLineEdit()
        self.symbol.setText("")
        self.symbol.setFixedWidth(self.symbol.fontMetrics().width("XXXXXXXXXXXX") * 1.5)
        self.layout.addWidget(self.symbol)
        self.full_name = QLabel()
        self.full_name.setText("Full security name")
        self.layout.addWidget(self.full_name)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.setFocusProxy(self.symbol)

        self.button.clicked.connect(self.OnButtonClicked)

        self.dialog = AssetChoiceDlg()

    def getId(self):
        return self.p_asset_id

    def setId(self, asset_id):
        if self.p_asset_id == asset_id:
            return
        self.p_asset_id = asset_id
        self.dialog.Model.setFilter(f"assets.id={asset_id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        symbol = self.dialog.Model.record(row_idx).value(1)
        full_name = self.dialog.Model.record(row_idx).value(3)
        self.symbol.setText(symbol)
        self.full_name.setText(full_name)
        self.dialog.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    asset_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.dialog.init_DB(db)
        self.dialog.type_id = 0
        self.dialog.setActiveFilter()
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex("name"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.symbol.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.symbol.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setActiveFilter()
        res = self.dialog.exec_()
        if res:
            self.asset_id = self.dialog.asset_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.asset_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)


######################################################################################################################
# More compact selector to choose currency only
######################################################################################################################
class CurrencySelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.completer = None
        self.p_asset_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.symbol = QLineEdit()
        self.symbol.setText("")
        self.layout.addWidget(self.symbol)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.button.clicked.connect(self.OnButtonClicked)
        self.dialog = AssetChoiceDlg()

    def getId(self):
        return self.p_asset_id

    def setId(self, asset_id):
        if self.p_asset_id == asset_id:
            return
        self.p_asset_id = asset_id
        self.dialog.Model.setFilter(f"assets.id={asset_id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        symbol = self.dialog.Model.record(row_idx).value(1)
        self.symbol.setText(symbol)
        self.dialog.Model.setFilter(f"type_id={ASSET_TYPE_MONEY}")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    asset_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.dialog.init_DB(db)
        self.dialog.type_id = ASSET_TYPE_MONEY
        self.dialog.setActiveFilter()
        self.dialog.AssetTypeCombo.setEnabled(False)
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex("name"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.symbol.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.symbol.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec_()
        if res:
            self.asset_id = self.dialog.asset_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.asset_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)
