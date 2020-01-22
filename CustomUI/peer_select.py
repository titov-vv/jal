from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QPushButton, QAbstractItemView, QCompleter
from PySide2.QtSql import QSqlTableModel, QSqlQuery
from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from ui_peer_choice_dlg import Ui_PeerChoiceDlg

#TODO clean-up columns
class PeerChoiceDlg(QDialog, Ui_PeerChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.peer_id = 0
        self.last_parent = 0

        self.PeersList.doubleClicked.connect(self.OnDoubleClick)
        self.BackBtn.clicked.connect(self.OnBackClick)

    def Activate(self):
        self.PeersList.selectionModel().selectionChanged.connect(self.OnPeerChosen)

    def showEvent(self, arg__1):
        self.PeersList.model().setFilter("agents.pid=0")
        self.old_parent = 0

    @Slot()
    def OnPeerChosen(self, selected, deselected):
        idx = selected.indexes()
        selected_row = idx[0].row()
        self.peer_id = self.PeersList.model().record(selected_row).value(0)

    @Slot()
    def OnDoubleClick(self, index):
        selected_row = index.row()
        id = self.PeersList.model().record(selected_row).value(0)
        pid = self.PeersList.model().record(selected_row).value(1)
        self.last_parent = pid
        self.PeersList.model().setFilter(f"agents.pid={id}")

    @Slot()
    def OnBackClick(self):
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
        self.PeersList.model().setFilter(f"agents.pid={pid}")

class PeerSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_peer_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.name = QLineEdit()
        self.name.setText("Peer name")
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
        self.Model.setFilter(f"agents.id={id}")
        row_idx = self.Model.index(0, 0).row()
        name = self.Model.record(row_idx).value(2)
        self.name.setText(name)
        self.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    peer_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlTableModel(db=self.db)
        self.Model.setTable("agents")

        self.dialog.PeersList.setModel(self.Model)
        self.dialog.PeersList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.dialog.PeersList.setColumnHidden(self.Model.fieldIndex("pid"), True)
        self.dialog.PeersList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.Model.select()
        self.dialog.Activate()

        self.completer = QCompleter(self.Model)
        self.completer.setCompletionColumn(self.Model.fieldIndex("name"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec_()
        if res:
            self.peer_id = self.dialog.peer_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.peer_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)