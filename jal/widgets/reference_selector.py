from PySide6.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QToolButton, QCompleter
from PySide6.QtGui import QPalette
import jal.widgets.reference_dialogs as ui_dialogs
from jal.db.helpers import load_icon
from jal.constants import CustomColor


#-----------------------------------------------------------------------------------------------------------------------
class AbstractReferenceSelector(QWidget):
    changed = Signal()

    # If validate==True then widget will be highlighted for invalid values
    def __init__(self, parent=None, validate=True):
        super().__init__(parent=parent)
        self.completer = None
        self.p_selected_id = 0
        self._validate = validate

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)
        self.name = QLineEdit()
        self.name.setText("")
        self.layout.addWidget(self.name)
        self.details = QLabel()
        self.details.setText("")
        self.details.setVisible(False)
        self.layout.addWidget(self.details)
        self.button = QToolButton()
        self.button.setIcon(load_icon("meatballs.png"))
        self.layout.addWidget(self.button)
        self.clean_button = QToolButton()
        self.clean_button.setIcon(load_icon("broom.png"))
        self.layout.addWidget(self.clean_button)
        self.setLayout(self.layout)

        self.setFocusProxy(self.name)
        self._update_view()

        self.button.clicked.connect(self.on_button_clicked)
        self.clean_button.clicked.connect(self.on_clean_button_clicked)

        if self.details_field:
            self.name.setFixedWidth(self.name.fontMetrics().horizontalAdvance("X") * 15)
            self.details.setVisible(True)
        self.completer = QCompleter(self.dialog.model.completion_model)
        self.completer.setCompletionColumn(self.dialog.model.completion_model.fieldIndex(self.selector_field))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.on_completion)

    def get_id(self):
        return self.p_selected_id

    def set_id(self, selected_id: int):
        if self.p_selected_id == selected_id:
            return
        self.p_selected_id = selected_id
        self.name.setText(self.dialog.model.getFieldValue(selected_id, self.selector_field))
        if self.details_field:
            self.details.setText(self.dialog.model.getFieldValue(selected_id, self.details_field))
        self._update_view()

    selected_id = Property(int, get_id, set_id, notify=changed, user=True)

    def get_str_id(self) -> str:
        string_id = '' if self.get_id() is None else str(self.get_id())
        return string_id

    def set_str_id(self, string_id: str):
        new_id = int(string_id) if string_id else 0
        self.set_id(new_id)

    selected_id_str = Property(str, get_str_id, set_str_id, notify=changed)  # workaround for QTBUG-115144

    def setFilterValue(self, filter_value):
        self.dialog.setFilterValue(filter_value)

    def setValidation(self, validate):
        self._validate = validate
        self._update_view()

    def on_button_clicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec(enable_selection=True, selected=self.selected_id)
        if res:
            self.selected_id = self.dialog.selected_id
            self.changed.emit()

    def on_clean_button_clicked(self):
        self.selected_id = 0
        self.changed.emit()

    @Slot(QModelIndex)
    def on_completion(self, index):
        model = index.model()
        self.selected_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)
        self.changed.emit()

    # Highlights input field with red color if widget has invalid value
    def _update_view(self):
        if self._validate and not self.p_selected_id:
            p = QPalette()
            p.setColor(QPalette.Base, CustomColor.LightRed)
        else:
            p = self.style().standardPalette()
        self.name.setPalette(p)


# ----------------------------------------------------------------------------------------------------------------------
class AccountSelector(AbstractReferenceSelector):
    def __init__(self, parent=None, validate=True):
        self.table = "accounts"
        self.selector_field = "name"
        self.details_field = None
        self.dialog = ui_dialogs.AccountListDialog()
        super().__init__(parent=parent, validate=validate)


class AssetSelector(AbstractReferenceSelector):
    def __init__(self, parent=None, validate=True):
        self.table = "assets_ext"
        self.selector_field = "symbol"
        self.details_field = "full_name"
        self.dialog = ui_dialogs.AssetListDialog()
        super().__init__(parent=parent, validate=validate)


class PeerSelector(AbstractReferenceSelector):
    def __init__(self, parent=None, validate=True):
        self.table = "agents"
        self.selector_field = "name"
        self.details_field = None
        self.dialog = ui_dialogs.PeerListDialog(parent)
        super().__init__(parent=parent, validate=validate)


class CategorySelector(AbstractReferenceSelector):
    def __init__(self, parent=None, validate=True):
        self.table = "categories"
        self.selector_field = "name"
        self.details_field = None
        self.dialog = ui_dialogs.CategoryListDialog(parent)
        super().__init__(parent=parent, validate=validate)


class TagSelector(AbstractReferenceSelector):
    def __init__(self, parent=None, validate=True):
        self.table = "tags"
        self.selector_field = "tag"
        self.details_field = None
        self.dialog = ui_dialogs.TagsListDialog(parent)
        super().__init__(parent=parent, validate=validate)
