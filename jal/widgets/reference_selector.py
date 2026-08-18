from PySide6.QtCore import Qt, Signal, Property, Slot, QEvent, QModelIndex
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLineEdit, QLabel, QToolButton
from PySide6.QtGui import QPalette
from jal.widgets.icons import JalIcon
from jal.widgets.helpers import layout_step
from jal.widgets.theme import Theme, Meaning


#-----------------------------------------------------------------------------------------------------------------------
class ReferenceSelectorWidget(QWidget):
    changed = Signal()

    # If validate==True then widget will be highlighted for invalid values
    def __init__(self, parent=None, validate=True):
        super().__init__(parent=parent)
        self.completer = None
        self.p_selected_id = 0
        self._validate = validate
        self._model = None
        self._dialog_params = {}
        self._dialog = None
        self._dialog_class = None
        self._dialog_parent = None
        self._dialog_args = {}

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        # A tight, style-derived gap for this in-field cluster
        self.layout.setSpacing(max(1, layout_step(self) // 2))
        self.name = QLineEdit()
        self.name.setText("")
        self.layout.addWidget(self.name)
        self.details = QLabel()
        self.details.setText("")
        self.details.setVisible(False)
        self.layout.addWidget(self.details)
        self.button = QToolButton()
        self.button.setIcon(JalIcon[JalIcon.DETAILS])
        self.button.setAutoRaise(True)  # flat until hovered
        self.layout.addWidget(self.button)
        self.clean_button = QToolButton()
        self.clean_button.setIcon(JalIcon[JalIcon.CLEAN])
        self.clean_button.setAutoRaise(True)
        self.layout.addWidget(self.clean_button)
        self.setLayout(self.layout)

        self.setFocusProxy(self.name)
        self._update_view()

        self.button.clicked.connect(self.on_button_clicked)
        self.clean_button.clicked.connect(self.on_clean_button_clicked)

    # Sets relations of the widget:
    # model_class - class of the data model to get values from. It fills the text field and its completer, and is
    #               built right here: the completer has to be bound before the user may type into the field, and the
    #               name of an already selected item is asked for as soon as an operation is displayed.
    # dialog_class - class of the dialog that the "..." button opens for selection. It must expose a
    #                'dialog_requested' slot and emit 'selection_done' on completion. Unlike the model it is NOT
    #                built here but on the first click of that button - every operation tab and every reference
    #                dialog owns several selectors, so otherwise the application will build several dozen fully
    #                populated modal dialogs at start-up that the user may never open.
    # parent - parent object of the dialog. The model is owned by this widget instead, so that it is released with
    #          it: a selector created as a cell editor is transient, and a model outliving it would pile up unused
    #          copies on the view for as long as the view is alive.
    # model_args, dialog_args - extra keyword arguments for the respective constructor
    def setup_selector(self, model_class, dialog_class, parent=None, model_args=None, dialog_args=None):
        self._model = model_class(self, **(model_args or {}))
        self._model.bind_completer(self.name, self.on_completion)
        self._dialog_class = dialog_class
        self._dialog_parent = parent
        self._dialog_args = dialog_args or {}

    # The data model the widget displays values from - for a caller that needs to narrow it down, see setup_selector()
    def model(self):
        return self._model

    # The selection dialog, built on first use. Kept afterwards, so it holds its geometry, filters and search text
    # between openings exactly as the eagerly created one did.
    def selection_dialog(self):
        assert self._dialog_class is not None, f"Selection dialog is not set for {self.__class__.__name__}"
        if self._dialog is None:
            self._dialog = self._dialog_class(self._dialog_parent, **self._dialog_args)
            self._dialog.selection_done.connect(self.selection_done)
        return self._dialog

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

    def set_dialog_params(self, dialog_params):
        self._dialog_params = dialog_params

    def setValidation(self, validate):
        self._validate = validate
        self._update_view()

    def on_button_clicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.selection_dialog().dialog_requested(self.selected_id, ref_point, self._dialog_params)

    @Slot(int)
    def selection_done(self, selected_id):
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

    # Highlights input field with red color if widget has invalid value.
    def _update_view(self):
        palette = QPalette(QApplication.palette(self.name))
        if self._validate and not self.p_selected_id:
            palette.setColor(QPalette.Base, Theme.fill(Meaning.NEGATIVE))
        self.name.setPalette(palette)

    # A theme switch replaces the palette this widget derived its own from, so the derivation has to be redone
    def changeEvent(self, event):
        if event.type() == QEvent.ApplicationPaletteChange:
            self._update_view()
        super().changeEvent(event)
