from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QPushButton, QCompleter, QHeaderView
from PySide2.QtSql import QSqlTableModel, QSqlRelationalDelegate, QSqlQuery
from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex, QEvent
from UI.ui_category_choice import Ui_CategoryChoiceDlg

class CategoryChoiceDlg(QDialog, Ui_CategoryChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.category_id = 0
        self.last_parent = 0
        self.parent = 0
        self.search_text = ""

        self.CategoriesList.clicked.connect(self.OnClicked)
        self.SearchString.textChanged.connect(self.OnSearchChange)
        self.UpBtn.clicked.connect(self.OnUpClick)
        self.AddCategoryBtn.clicked.connect(self.OnAdd)
        self.RemoveCategoryBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlTableModel(db=self.db)
        self.Model.setTable("categories_ext")
        self.Model.setSort(self.Model.fieldIndex("name"), Qt.AscendingOrder)
        self.Model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.Model.setHeaderData(self.Model.fieldIndex("id"), Qt.Horizontal, "")
        self.Model.setHeaderData(self.Model.fieldIndex("name"), Qt.Horizontal, "Name")
        self.Model.setHeaderData(self.Model.fieldIndex("often"), Qt.Horizontal, "Often")
        self.Model.setHeaderData(self.Model.fieldIndex("special"), Qt.Horizontal, "Special")

        self.CategoriesList.setModel(self.Model)
        self.CategoriesList.setItemDelegate(CategoryDelegate(self.CategoriesList))
        self.CategoriesList.setColumnWidth(self.Model.fieldIndex("id"), 16)
        self.CategoriesList.setColumnHidden(self.Model.fieldIndex("pid"), True)
        self.CategoriesList.setColumnHidden(self.Model.fieldIndex("children_count"), True)
        self.CategoriesList.horizontalHeader().setSectionResizeMode(self.Model.fieldIndex("name"), QHeaderView.Stretch)
        font = self.CategoriesList.horizontalHeader().font()
        font.setBold(True)
        self.CategoriesList.horizontalHeader().setFont(font)

        self.CategoriesList.selectionModel().selectionChanged.connect(self.OnCategoryChosen)
        self.Model.dataChanged.connect(self.OnDataChanged)
        self.Model.select()

    @Slot()
    def OnCategoryChosen(self, selected, deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            self.category_id = self.CategoriesList.model().record(selected_row).value(0)

    @Slot()
    def OnSearchChange(self):
        self.search_text = self.SearchString.text()
        self.setFilter()

    @Slot()
    def OnClicked(self, index):
        if index.column() == 0:
            selected_row = index.row()
            self.parent = self.CategoriesList.model().record(selected_row).value(0)
            self.last_parent = self.CategoriesList.model().record(selected_row).value(1)
            if self.search_text:
                self.SearchString.setText("")   # it will also call self.setFilter()
            else:
                self.setFilter()

    def setFilter(self):
        if self.search_text:
            self.CategoriesList.model().setFilter(f"name LIKE '%{self.search_text}%'")
        else:
            self.CategoriesList.model().setFilter(f"pid={self.parent}")

    @Slot()
    def OnUpClick(self):
        if self.search_text:  # list filtered by search string
            return
        query = QSqlQuery(self.CategoriesList.model().database())
        query.prepare("SELECT c2.pid FROM categories AS c1 LEFT JOIN categories AS c2 ON c1.pid=c2.id WHERE c1.id = :current_id")
        id = self.CategoriesList.model().record(0).value(0)
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
        new_record = self.CategoriesList.model().record()
        new_record.setValue(1, self.parent)  # set current parent
        assert self.CategoriesList.model().insertRows(0, 1)
        self.CategoriesList.model().setRecord(0, new_record)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.CategoriesList.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.CategoriesList.model().removeRow(selected_row)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.CategoriesList.model().submitAll():
            print(self.tr("Action submit failed: "), self.CategoriesList.model().lastError().text())
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.CategoriesList.model().revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

class CategorySelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_category_id = 0

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
        self.dialog = CategoryChoiceDlg()

    def getId(self):
        return self.p_category_id

    def setId(self, id):
        if (self.p_category_id == id):
            return
        self.p_category_id = id
        self.dialog.Model.setFilter(f"id={id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        name = self.dialog.Model.record(row_idx).value(2)
        self.name.setText(name)
        self.dialog.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    category_id = Property(int, getId, setId, notify=changed, user=True)

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
            self.category_id = self.dialog.category_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.category_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)


####################################################################################################################3
# Delegate to display custom editors
####################################################################################################################3
class CategoryDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        if (index.column() == 0):
            painter.save()
            model = index.model()
            children_count = model.data(model.index(index.row(), 5), Qt.DisplayRole)
            text = ""
            if children_count:
                text = "+"
            painter.drawText(option.rect, Qt.AlignHCenter, text)
            painter.restore()
        # Paint '*' for special and often categories or nothing for other
        elif (index.column() == 3) or (index.column() == 4):  # 'often' and 'special' columns
            painter.save()
            model = index.model()
            status = model.data(index, Qt.DisplayRole)
            if status:
                text = " * "
            else:
                text = ""
            painter.drawText(option.rect, Qt.AlignHCenter, text)
            painter.restore()
        else:
            QSqlRelationalDelegate.paint(self, painter, option, index)

    def editorEvent(self, event, model, option, index):
        if (index.column() != 3) and (index.column() != 4):
            return False
        # Only for 'often' and 'special' column
        if event.type() == QEvent.MouseButtonPress:
            if model.data(index, Qt.DisplayRole):   # Toggle value - from 1 to 0 and from 0 to 1
                model.setData(index, 0)
            else:
                model.setData(index, 1)
        return True
    #
    # def createEditor(self, aParent, option, index):
    #     if index.column() != 3:
    #         return QSqlRelationalDelegate.createEditor(self, aParent, option, index)
    #
    #     currency_selector = CurrencySelector(aParent)
    #     currency_selector.init_DB(index.model().database())
    #     return currency_selector
    #
    # def setModelData(self, editor, model, index):
    #     if index.column() != 3:
    #         return QSqlRelationalDelegate.setModelData(self, editor, model, index)
    #     model.setData(index, editor.active_id)