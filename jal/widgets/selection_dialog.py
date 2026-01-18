from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QMessageBox
from jal.ui.ui_select_reference_dlg import Ui_SelectReferenceDlg
from jal.widgets.helpers import center_window
from jal.widgets.reference_selector import ReferenceSelectorWidget

#-----------------------------------------------------------------------------------------------------------------------
# Common base GUI dialog class for selector dialogs. Takes window title and label comment to describe selection
class SelectReferenceDialog(QDialog):
    def __init__(self, parent=None, title='', description='', model=None, dialog=None):
        super().__init__(parent=parent)
        self.ui = Ui_SelectReferenceDlg()
        self.ui.setupUi(self)
        self.selected_id = 0
        self.setWindowTitle(title)
        self.ui.DescriptionLabel.setText(description)
        center_window(self)
        self._selection_widget_model = model
        self._selection_widget_dialog = dialog
        self._selection_widget = ReferenceSelectorWidget(self.ui.SelectorFrame)
        self._selection_widget.setup_selector(self._selection_widget_model, self._selection_widget_dialog)
        self.ui.FrameLayout.addWidget(self._selection_widget)
        self._selection_widget.selected_id = self.selected_id = 0

    @Slot()
    def closeEvent(self, event):
        self.selected_id = self._selection_widget.selected_id
        if self.selected_id == 0:
            QMessageBox().warning(None, self.tr("No selection"), self.tr("You should select something"), QMessageBox.Ok)
            event.ignore()
            return
        self.setResult(QDialog.Accepted)
        event.accept()
