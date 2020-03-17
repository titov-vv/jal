from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QPushButton, QCompleter, QHeaderView
from PySide2.QtSql import QSqlTableModel
from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from UI.ui_tag_choice import Ui_TagChoiceDlg

class TagChoiceDlg(QDialog, Ui_TagChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.tag_id = 0
        self.search_text = ""

        self.SearchString.textChanged.connect(self.OnSearchChange)
        self.AddTagBtn.clicked.connect(self.OnAdd)
        self.RemoveTagBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlTableModel(db=self.db)
        self.Model.setTable("tags")
        self.Model.setSort(self.Model.fieldIndex("tag"), Qt.AscendingOrder)
        self.Model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.Model.setHeaderData(self.Model.fieldIndex("tag"), Qt.Horizontal, "Tag")

        self.TagsList.setModel(self.Model)
        self.TagsList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.TagsList.horizontalHeader().setSectionResizeMode(self.Model.fieldIndex("tag"), QHeaderView.Stretch)
        font = self.TagsList.horizontalHeader().font()
        font.setBold(True)
        self.TagsList.horizontalHeader().setFont(font)

        self.TagsList.selectionModel().selectionChanged.connect(self.OnTagChosen)
        self.Model.dataChanged.connect(self.OnDataChanged)
        self.Model.select()

    @Slot()
    def OnDataChanged(self):
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnAdd(self):
        assert self.Model.insertRows(0, 1)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.TagsList.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.Model.removeRow(selected_row)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.Model.submitAll():
            print(self.tr("Action submit failed: "), self.Model.lastError().text())
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.Model.revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    def setFilter(self):
        if self.search_text:
            self.TagsList.model().setFilter(f"tag LIKE '%{self.search_text}%'")
        else:
            self.TagsList.model().setFilter("")

    @Slot()
    def OnTagChosen(self, selected, deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            self.tag_id = self.TagsList.model().record(selected_row).value(0)

    @Slot()
    def OnSearchChange(self):
        self.search_text = self.SearchString.text()
        self.setFilter()

class TagSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_tag_id = 0

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
        self.dialog = TagChoiceDlg()

    def getId(self):
        return self.p_tag_id

    def setId(self, id):
        if (self.p_tag_id == id):
            return
        self.p_tag_id = id
        self.dialog.Model.setFilter(f"id={id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        name = self.dialog.Model.record(row_idx).value(1)
        self.name.setText(name)
        self.dialog.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    tag_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.dialog.init_DB(db)
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex("tag"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()
        res = self.dialog.exec_()
        if res:
            self.tag_id = self.dialog.tag_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.tag_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)