from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QPushButton, QAbstractItemView, QCompleter, QHeaderView
from PySide2.QtSql import QSqlTableModel, QSqlQuery
from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from ui_peer_choice_dlg import Ui_PeerChoiceDlg

class PeerChoiceDlg(QDialog, Ui_PeerChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.peer_id = 0
        self.last_parent = 0
        self.old_parent = 0
        self.parent = 0
        self.search_text = ""

        self.PeersList.doubleClicked.connect(self.OnDoubleClick)
        self.SearchString.textChanged.connect(self.OnSearchChange)
        self.BackBtn.clicked.connect(self.OnBackClick)
        self.AddPeerBtn.clicked.connect(self.OnAdd)
        self.RemovePeerBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlTableModel(db=self.db)
        self.Model.setTable("agents")
        self.Model.setSort(self.Model.fieldIndex("name"), Qt.AscendingOrder)
        self.Model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.Model.setHeaderData(self.Model.fieldIndex("name"), Qt.Horizontal, "Name")
        self.Model.setHeaderData(self.Model.fieldIndex("location"), Qt.Horizontal, "Location")

        self.PeersList.setModel(self.Model)
        self.PeersList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.PeersList.setColumnHidden(self.Model.fieldIndex("pid"), True)
        self.PeersList.horizontalHeader().setSectionResizeMode(self.Model.fieldIndex("name"), QHeaderView.Stretch)
        font = self.PeersList.horizontalHeader().font()
        font.setBold(True)
        self.PeersList.horizontalHeader().setFont(font)

        self.PeersList.selectionModel().selectionChanged.connect(self.OnPeerChosen)
        self.Model.dataChanged.connect(self.OnDataChanged)
        self.Model.select()

    @Slot()
    def OnPeerChosen(self, selected, deselected):
        idx = selected.indexes()
        selected_row = idx[0].row()
        self.peer_id = self.PeersList.model().record(selected_row).value(0)

    @Slot()
    def OnSearchChange(self):
        self.search_text = self.SearchString.text()
        self.setFilter()

    @Slot()
    def OnDoubleClick(self, index):
        selected_row = index.row()
        self.parent = self.PeersList.model().record(selected_row).value(0)
        self.last_parent = self.PeersList.model().record(selected_row).value(1)
        if self.search_text:
            self.SearchString.setText("")   # it will also call self.setFilter()
        else:
            self.setFilter()

    def setFilter(self):
        if self.search_text:
            self.PeersList.model().setFilter(f"name LIKE '%{self.search_text}%'")
        else:
            self.PeersList.model().setFilter(f"agents.pid={self.parent}")

    @Slot()
    def OnBackClick(self):
        if self.search_text:  # list filtered by search string
            return
        query = QSqlQuery(self.PeersList.model().database())
        query.prepare("SELECT a2.pid FROM agents AS a1 LEFT JOIN agents AS a2 ON a1.pid=a2.id WHERE a1.id = :current_id")
        id = self.PeersList.model().record(0).value(0)
        if id == None:
            pid = self.last_parent
        else:
            query.bindValue(":current_id", id)
            query.exec_()
            query.next()
            pid = query.value(0)
            if pid == '':
                pid = 0
        self.parent = pid
        self.setFilter()

    @Slot()
    def OnDataChanged(self):
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnAdd(self):
        new_record = self.PeersList.model().record()
        new_record.setValue(1, self.parent)  # set current parent
        assert self.PeersList.model().insertRows(0, 1)
        self.PeersList.model().setRecord(0, new_record)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.PeersList.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.PeersList.model().removeRow(selected_row)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.PeersList.model().submitAll():
            print(self.tr("Action submit failed: "), self.PeersList.model().lastError().text())
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.PeersList.model().revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

class PeerSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_peer_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.name = QLineEdit()
        self.name.setText("")
        self.layout.addWidget(self.name)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.button.clicked.connect(self.OnButtonClicked)

        self.dialog = PeerChoiceDlg()

    def getId(self):
        return self.p_peer_id

    def setId(self, id):
        if (self.p_peer_id == id):
            return
        self.p_peer_id = id
        self.dialog.Model.setFilter(f"agents.id={id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        name = self.dialog.Model.record(row_idx).value(2)
        self.name.setText(name)
        self.dialog.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    peer_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.dialog.init_DB(db)
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex("name"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()
        res = self.dialog.exec_()
        if res:
            self.peer_id = self.dialog.peer_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.peer_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)