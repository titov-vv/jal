from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QPushButton, QCompleter, QHeaderView
from PySide2.QtSql import QSqlTableModel, QSqlRelationalDelegate, QSqlQuery
from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from UI.ui_peer_choice_dlg import Ui_PeerChoiceDlg

class PeerChoiceDlg(QDialog, Ui_PeerChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.peer_id = 0
        self.last_parent = 0
        self.parent = 0
        self.search_text = ""

        self.PeersList.clicked.connect(self.OnClicked)
        self.SearchString.textChanged.connect(self.OnSearchChange)
        self.UpBtn.clicked.connect(self.OnUpClick)
        self.AddPeerBtn.clicked.connect(self.OnAdd)
        self.RemovePeerBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlTableModel(db=self.db)
        self.Model.setTable("agents_ext")
        self.Model.setSort(self.Model.fieldIndex("name"), Qt.AscendingOrder)
        self.Model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.Model.setHeaderData(self.Model.fieldIndex("id"), Qt.Horizontal, "")
        self.Model.setHeaderData(self.Model.fieldIndex("name"), Qt.Horizontal, "Name")
        self.Model.setHeaderData(self.Model.fieldIndex("location"), Qt.Horizontal, "Location")
        self.Model.setHeaderData(self.Model.fieldIndex("actions_count"), Qt.Horizontal, "Docs count")

        self.PeersList.setModel(self.Model)
        self.PeersList.setItemDelegate(PeerDelegate(self.PeersList))
        self.PeersList.setColumnWidth(self.Model.fieldIndex("id"), 16)
        self.PeersList.setColumnHidden(self.Model.fieldIndex("pid"), True)
        self.PeersList.setColumnHidden(self.Model.fieldIndex("children_count"), True)
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
        if idx:
            selected_row = idx[0].row()
            self.peer_id = self.PeersList.model().record(selected_row).value(0)

    @Slot()
    def OnSearchChange(self):
        self.search_text = self.SearchString.text()
        self.setFilter()

    @Slot()
    def OnClicked(self, index):
        if index.column() == 0:
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
            self.PeersList.model().setFilter(f"pid={self.parent}")

    @Slot()
    def OnUpClick(self):
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

        self.setFocusProxy(self.name)

        self.button.clicked.connect(self.OnButtonClicked)
        self.dialog = PeerChoiceDlg()

    def getId(self):
        return self.p_peer_id

    def setId(self, id):
        if (self.p_peer_id == id):
            return
        self.p_peer_id = id
        self.dialog.Model.setFilter(f"id={id}")
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

####################################################################################################################3
# Delegate to display custom fields
####################################################################################################################3
class PeerDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        if (index.column() == 0):
            painter.save()
            model = index.model()
            children_count = model.data(model.index(index.row(), 4), Qt.DisplayRole)
            text = ""
            if children_count:
                text = "+"
            painter.drawText(option.rect, Qt.AlignHCenter, text)
            painter.restore()
        # to align number to the right
        elif (index.column() == 5):
            painter.save()
            model = index.model()
            docs_count = model.data(index, Qt.DisplayRole)
            painter.drawText(option.rect, Qt.AlignRight, f"{docs_count} ")
            painter.restore()
        else:
            QSqlRelationalDelegate.paint(self, painter, option, index)