from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QAbstractItemView, QCompleter, QHeaderView
from PySide2.QtSql import QSqlRelationalTableModel, QSqlRelation, QSqlRelationalDelegate, QSqlTableModel
from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from ui_active_choice_dlg import Ui_ActiveChoiceDlg

class ActiveChoiceDlg(QDialog, Ui_ActiveChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.active_id = 0
        self.type_id = 0

        self.ActiveTypeCombo.currentIndexChanged.connect(self.OnTypeChange)
        self.ActivesList.doubleClicked.connect(self.OnDoubleClick)
        self.AddActiveBtn.clicked.connect(self.OnAdd)
        self.RemoveActiveBtn.clicked.connect(self.OnRemove)

    @Slot()
    def OnTypeChange(self, list_id):
        model = self.ActiveTypeCombo.model()
        self.type_id = model.data(model.index(list_id, model.fieldIndex("id")))
        self.setActiveFilter()

    def setActiveFilter(self):
        active_filter = ""
        if self.type_id:
            active_filter = f"actives.type_id={self.type_id}"
        self.ActivesList.model().setFilter(active_filter)

    @Slot()
    def OnActiveChosen(self, selected, deselected):
        idx = selected.indexes()
        selected_row = idx[0].row()
        self.active_id = self.ActivesList.model().record(selected_row).value(0)

    @Slot()
    def OnDoubleClick(self, index):
        self.accept()

    @Slot()
    def OnAdd(self):
        assert self.ActivesList.model().insertRows(0, 1)

    @Slot()
    def OnRemove(self):
        idx = self.ActivesList.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.ActivesList.model().removeRow(selected_row)

class ActiveSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_active_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.symbol = QLineEdit()
        self.symbol.setText("Ticker")
        self.symbol.setFixedWidth(self.symbol.fontMetrics().width("XXXXXXXXXXXX") * 1.5)
        self.layout.addWidget(self.symbol)
        self.full_name = QLabel()
        self.full_name.setText("Full security name")
        self.layout.addWidget(self.full_name)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.button.clicked.connect(self.OnButtonClicked)

        self.dialog = ActiveChoiceDlg()

    def getId(self):
        return self.p_active_id

    def setId(self, id):
        if (self.p_active_id == id):
            return
        self.p_active_id = id
        self.Model.setFilter(f"actives.id={id}")
        row_idx = self.Model.index(0, 0).row()
        symbol = self.Model.record(row_idx).value(1)
        full_name = self.Model.record(row_idx).value(3)
        self.symbol.setText(symbol)
        self.full_name.setText(full_name)
        self.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    active_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlRelationalTableModel(db=self.db)
        self.Model.setTable("actives")
        self.Model.setEditStrategy(QSqlTableModel.OnRowChange)
        self.Model.setJoinMode(QSqlRelationalTableModel.LeftJoin)   # to work correctly with NULL values in SrcId
        type_idx = self.Model.fieldIndex("type_id")
        self.Model.setRelation(type_idx, QSqlRelation("active_types", "id", "name"))
        data_src_id = self.Model.fieldIndex("src_id")
        self.Model.setRelation(data_src_id, QSqlRelation("data_sources", "id", "name"))
        self.Model.setHeaderData(self.Model.fieldIndex("name"), Qt.Horizontal, "Symbol")
        self.Model.setHeaderData(self.Model.fieldIndex("type_id"), Qt.Horizontal, "Type")
        self.Model.setHeaderData(self.Model.fieldIndex("full_name"), Qt.Horizontal, "Name")
        self.Model.setHeaderData(self.Model.fieldIndex("isin"), Qt.Horizontal, "ISIN")
        self.Model.setHeaderData(self.Model.fieldIndex("web_id"), Qt.Horizontal, "WebID")
        self.Model.setHeaderData(self.Model.fieldIndex("src_id"), Qt.Horizontal, "Data source")

        self.dialog.ActivesList.setModel(self.Model)
        self.dialog.ActivesList.setItemDelegate(ActiveDelegate(self.dialog.ActivesList))
        self.dialog.ActivesList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.dialog.ActivesList.setColumnHidden(self.Model.fieldIndex("type_id"), True)
        self.dialog.ActivesList.horizontalHeader().setSectionResizeMode(self.Model.fieldIndex("full_name"), QHeaderView.Stretch)
        font = self.dialog.ActivesList.horizontalHeader().font()
        font.setBold(True)
        self.dialog.ActivesList.horizontalHeader().setFont(font)

        self.dialog.ActiveTypeCombo.setModel(self.Model.relationModel(type_idx))
        self.dialog.ActiveTypeCombo.setModelColumn(self.Model.relationModel(type_idx).fieldIndex("name"))

        self.dialog.ActivesList.selectionModel().selectionChanged.connect(self.dialog.OnActiveChosen)
        self.Model.select()

        self.completer = QCompleter(self.Model)
        self.completer.setCompletionColumn(self.Model.fieldIndex("name"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.symbol.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.symbol.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setActiveFilter()
        res = self.dialog.exec_()
        if res:
            self.active_id = self.dialog.active_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.active_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)

class ActiveDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)