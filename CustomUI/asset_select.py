from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QCompleter

from CustomUI.reference_data import ReferenceDataDialog, ReferenceLookupDelegate
from constants import *


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

        self.dialog = None

    def getId(self):
        return self.p_asset_id

    def setId(self, asset_id):
        if self.p_asset_id == asset_id:
            return
        self.p_asset_id = asset_id
        self.dialog.Model.setFilter(f"assets.id={asset_id}")   # TODO: Check carefully
        row_idx = self.dialog.Model.index(0, 0).row()
        symbol = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex("name"))
        full_name = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex("full_name"))
        self.symbol.setText(symbol)
        self.full_name.setText(full_name)
        self.dialog.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    asset_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.dialog = ReferenceDataDialog(db, "assets",
                                          [("id", None, 0, None, None),
                                           ("name", "Symbol", None, Qt.AscendingOrder, None),
                                           ("type_id", None, 0, None, None),
                                           ("full_name", "Name", -1, None, None),
                                           ("isin", "ISIN", None, None, None),
                                           ("web_id", "WebID", None, None, None),
                                           ("src_id", "Data source", None, None, ReferenceLookupDelegate)],
                                          title="Assets", search_field="full_name",
                                          relations=[("type_id", "asset_types", "id", "name", "Asset type:"),
                                                     ("src_id", "data_sources", "id", "name", None)])
        self.dialog.type_id = 0
        self.dialog.setFilter()
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex("name"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.symbol.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.symbol.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()
        res = self.dialog.exec_()
        if res:
            self.asset_id = self.dialog.selected_id

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
        self.dialog = None

    def getId(self):
        return self.p_asset_id

    def setId(self, asset_id):
        if self.p_asset_id == asset_id:
            return
        self.p_asset_id = asset_id
        self.dialog.Model.setFilter(f"assets.id={asset_id}")    # TODO: check carefully
        row_idx = self.dialog.Model.index(0, 0).row()
        symbol = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex("name"))
        self.symbol.setText(symbol)
        self.dialog.Model.setFilter(f"type_id={ASSET_TYPE_MONEY}")   # TODO: check carefully
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    asset_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.dialog = ReferenceDataDialog(db, "assets",
                                          [("id", None, 0, None, None),
                                           ("name", "Symbol", None, Qt.AscendingOrder, None),
                                           ("type_id", None, 0, None, None),
                                           ("full_name", "Name", -1, None, None),
                                           ("isin", "ISIN", None, None, None),
                                           ("web_id", "WebID", None, None, None),
                                           ("src_id", "Data source", None, None, ReferenceLookupDelegate)],
                                          title="Assets", search_field="full_name",
                                          relations=[("type_id", "asset_types", "id", "name", "Asset type:"),
                                                     ("src_id", "data_sources", "id", "name", None)])
        self.dialog.group_id = ASSET_TYPE_MONEY   # TODO: Check carefully
        self.dialog.setFilter()
        self.dialog.GroupCombo.setEnabled(False)  # TODO: Check carefully
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
            self.asset_id = self.dialog.selected_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.asset_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)
