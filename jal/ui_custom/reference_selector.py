from abc import ABC, abstractmethod

from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QCompleter
import jal.ui_custom.reference_dialogs as ui_dialogs

#-----------------------------------------------------------------------------------------------------------------------
# To solve metaclass conflict
class SelectorMeta(type(ABC), type(QWidget)):
    pass

#-----------------------------------------------------------------------------------------------------------------------
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

        if self.details_field:
            self.name.setFixedWidth(self.name.fontMetrics().width("X") * 15)
            self.details.setVisible(True)
        self.completer = QCompleter(self.dialog.model)
        self.completer.setCompletionColumn(self.dialog.model.fieldIndex(self.selector_field))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.on_completion)

    def getId(self):
        return self.p_selected_id

    def setId(self, selected_id):
        if self.p_selected_id == selected_id:
            return
        self.p_selected_id = selected_id
        self.dialog.model.setFilter(f"{self.table}.id={selected_id}")
        row_idx = self.dialog.model.index(0, 0).row()
        name = self.dialog.model.record(row_idx).value(self.dialog.model.fieldIndex(self.selector_field))
        self.name.setText(name)
        if self.details_field:
            details = self.dialog.model.record(row_idx).value(self.dialog.model.fieldIndex(self.details_field))
            self.details.setText(details)
        self.dialog.model.setFilter("")

    selected_id = Property(int, getId, setId, notify=changed, user=True)

    def on_button_clicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec_(enable_selection=True)
        if res:
            self.selected_id = self.dialog.selected_id
            self.changed.emit()

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
        self.table = "accounts"
        self.selector_field = "name"
        self.details_field = None
        self.dialog = ui_dialogs.AccountListDialog()
        AbstractReferenceSelector.__init__(self, parent)

class AssetSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        self.table = "assets"
        self.selector_field = "name"
        self.details_field = "full_name"
        self.dialog = ui_dialogs.AssetListDialog()
        AbstractReferenceSelector.__init__(self, parent)

class PeerSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        self.table = "agents_ext"
        self.selector_field = "name"
        self.details_field = None
        self.dialog = ui_dialogs.PeerListDialog()
        AbstractReferenceSelector.__init__(self, parent)

class CategorySelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        self.table = "categories_ext"
        self.selector_field = "name"
        self.details_field = None
        self.dialog = ui_dialogs.CategoryListDialog()
        AbstractReferenceSelector.__init__(self, parent)

class TagSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        self.table = "tags"
        self.selector_field = "tag"
        self.details_field = None
        self.dialog = ui_dialogs.TagsListDialog()
        AbstractReferenceSelector.__init__(self, parent)
