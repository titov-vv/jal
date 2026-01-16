from PySide6.QtCore import Qt, Signal, Property, Slot, QModelIndex, QPoint
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QToolButton
from PySide6.QtGui import QPalette
from jal.widgets.icons import JalIcon
from jal.constants import CustomColor


#-----------------------------------------------------------------------------------------------------------------------
class ReferenceSelectorWidget(QWidget):
    changed = Signal()
    open_dialog = Signal(int, QPoint)

    # If validate==True then widget will be highlighted for invalid values
    def __init__(self, parent=None, validate=True):
        super().__init__(parent=parent)
        self.completer = None
        self.p_selected_id = 0
        self._validate = validate
        self._model = None

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
        self.button.setIcon(JalIcon[JalIcon.DETAILS])
        self.layout.addWidget(self.button)
        self.clean_button = QToolButton()
        self.clean_button.setIcon(JalIcon[JalIcon.CLEAN])
        self.layout.addWidget(self.clean_button)
        self.setLayout(self.layout)

        self.setFocusProxy(self.name)
        self._update_view()

        self.button.clicked.connect(self.on_button_clicked)
        self.clean_button.clicked.connect(self.on_clean_button_clicked)

    # Sets relations of the widget:
    # model - data model to get values from
    # selection_dialog - is used for items selection, it must expose 'on_dialog_request' slot and emit 'selection_done' signal on completion
    def setup_selector(self, model, selection_dialog=None):
        self._model = model
        self._model.bind_completer(self.name, self.on_completion)
        if selection_dialog:
            self.open_dialog.connect(selection_dialog.on_dialog_request)
            selection_dialog.selection_done.connect(self.on_selection)

    def get_id(self):
        return self.p_selected_id

    def set_id(self, selected_id: int):
        if self.p_selected_id == selected_id:
            return
        self.p_selected_id = selected_id
        self.set_labels_text(selected_id)
        self._update_view()

    selected_id = Property(int, get_id, set_id, notify=changed, user=True)

    def get_str_id(self) -> str:
        string_id = '' if self.get_id() is None else str(self.get_id())
        return string_id

    def set_str_id(self, string_id: str):
        new_id = int(string_id) if string_id else 0
        self.set_id(new_id)

    selected_id_str = Property(str, get_str_id, set_str_id, notify=changed)  # workaround for QTBUG-115144

    def set_labels_text(self, item_id):
        assert not self._model is None, f"Model is not set for {self.__class__.__name__}"
        self.name.setText(self._model.getValue(item_id))
        details_text = self._model.getValueDetails(item_id)
        if details_text:
            self.details.setVisible(True)
            self.details.setText(details_text)
        else:
            self.details.setVisible(False)

    def setFilterValue(self, filter_value):
        pass
        # self.dialog.setFilterValue(filter_value)   # FIXME - it seems to be used from one of special delegates

    def setValidation(self, validate):
        self._validate = validate
        self._update_view()

    def on_button_clicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.open_dialog.emit(self.selected_id, ref_point)

    @Slot(int)
    def on_selection(self, selected_id):
        self.selected_id = selected_id
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
