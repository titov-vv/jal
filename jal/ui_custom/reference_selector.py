from abc import ABC, abstractmethod

from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QCompleter

from jal.ui_custom.helpers import g_tr
import jal.ui_custom.reference_data as ui               # Full import due to "cyclic" reference
import jal.ui_custom.reference_dialogs as ui_dialogs


# To solve metaclass conflict
class SelectorMeta(type(ABC), type(QWidget)):
    pass


class AbstractReferenceSelector(ABC, QWidget, metaclass=SelectorMeta):
    changed = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.completer = None
        self.p_selected_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.name = QLineEdit()
        self.name.setText("")
        self.layout.addWidget(self.name)
        self.details = QLabel()
        self.details.setText("")
        self.details.setVisible(False)
        self.layout.addWidget(self.details)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width("XXXX"))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.setFocusProxy(self.name)

        self.button.clicked.connect(self.on_button_clicked)

        self.table = None
        self.selector_field = None
        self.details_field = None
        self.dialog = None

    def getId(self):
        return self.p_selected_id

    def setId(self, selected_id):
        if self.p_selected_id == selected_id:
            return
        self.p_selected_id = selected_id
        self.dialog.Model.setFilter(f"{self.table}.id={selected_id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        name = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex(self.selector_field))
        self.name.setText(name)
        if self.details_field:
            details = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex(self.details_field))
            self.details.setText(details)
        self.dialog.Model.setFilter("")

    selected_id = Property(int, getId, setId, notify=changed, user=True)

    def on_button_clicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec_(enable_selection=True)
        if res:
            self.selected_id = self.dialog.selected_id
            self.changed.emit()

    @abstractmethod
    def init_db(self, db):
        pass

    def init_db(self, table, selector_field, details_field=None):
        self.table = table
        self.selector_field = selector_field
        if details_field:
            self.name.setFixedWidth(self.name.fontMetrics().width("X") * 15)
            self.details_field = details_field
            self.details.setVisible(True)
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex(self.selector_field))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.on_completion)

    @Slot(QModelIndex)
    def on_completion(self, index):
        model = index.model()
        self.selected_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)
        self.changed.emit()

    def isCustom(self):
        return True

# ----------------------------------------------------------------------------------------------------------------------
class AccountSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)
        self.dialog = ui_dialogs.AccountsListDialog()

    def init_db(self, db):
        super().init_db("accounts", "name")


class AssetSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)
        self.dialog = ui_dialogs.AssetListDialog()

    def init_db(self, db):
        super().init_db("assets", "name", "full_name")


class PeerSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)
        self.dialog = ui_dialogs.PeerListDialog()

    def init_db(self, db):
        super().init_db("agents_ext", "name")


class CategorySelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)
        self.dialog = ui_dialogs.CategoryListDialog()

    def init_db(self, db):
        super().init_db("categories_ext", "name")


class TagSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db):
        self.dialog = ui.ReferenceDataDialog("tags",
                                             [("id", None, 0, None, None),
                                              ("tag", "Tag", -1, Qt.AscendingOrder, None)],
                                             title="Choose tag", search_field="tag")
        super().init_db("tags", "tag")
