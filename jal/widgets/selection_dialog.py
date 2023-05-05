from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QMessageBox
from jal.ui.ui_select_reference_dlg import Ui_SelectReferenceDlg
from jal.widgets.helpers import center_window
from jal.widgets.reference_selector import PeerSelector
from jal.widgets.reference_selector import CategorySelector
from jal.widgets.reference_selector import TagSelector


#-----------------------------------------------------------------------------------------------------------------------
# Common base GUI dialog class for selector dialogs. Takes window title and label comment to describe selection
class SelectReferenceDialog(QDialog):
    def __init__(self, parent=None, title='', description=''):
        super().__init__(parent=parent)
        self.ui = Ui_SelectReferenceDlg()
        self.ui.setupUi(self)
        self.selected_id = 0
        self.setWindowTitle(title)
        self.ui.DescriptionLabel.setText(description)
        center_window(self)

    @Slot()
    def closeEvent(self, event):
        if self.selected_id == 0:
            QMessageBox().warning(None, self.tr("No selection"), self.tr("You should select something"), QMessageBox.Ok)
            event.ignore()
            return
        self.setResult(QDialog.Accepted)
        event.accept()


#-----------------------------------------------------------------------------------------------------------------------
# Dialog for peer selection
# Constructor takes description to show and default_peer for initial choice
class SelectPeerDialog(SelectReferenceDialog):
    def __init__(self, description, default_peer=0):
        super().__init__(title=self.tr("Please select peer"), description=description)
        self.PeerWidget = PeerSelector(self.ui.SelectorFrame)
        self.ui.FrameLayout.addWidget(self.PeerWidget)
        self.PeerWidget.selected_id = self.selected_id = default_peer

    @Slot()
    def closeEvent(self, event):
        self.selected_id = self.PeerWidget.selected_id
        super().closeEvent(event)
        
        
#-----------------------------------------------------------------------------------------------------------------------
# Dialog for category selection
# Constructor takes description to show and default_category for initial choice
class SelectCategoryDialog(SelectReferenceDialog):
    def __init__(self, parent=None, description='', default_category=0):
        super().__init__(parent, title=self.tr("Please select category"), description=description)
        self.CategoryWidget = CategorySelector(self.ui.SelectorFrame)
        self.ui.FrameLayout.addWidget(self.CategoryWidget)
        self.CategoryWidget.selected_id = self.selected_id = default_category

    @Slot()
    def closeEvent(self, event):
        self.selected_id = self.CategoryWidget.selected_id
        super().closeEvent(event)


#-----------------------------------------------------------------------------------------------------------------------
# Dialog for tag selection
# Constructor takes description to show and default_tag for initial choice
class SelectTagDialog(SelectReferenceDialog):
    def __init__(self, parent=None, description='', default_tag=0):
        super().__init__(parent, title=self.tr("Please select tag"), description=description)
        self.TagWidget = TagSelector(self.ui.SelectorFrame)
        self.ui.FrameLayout.addWidget(self.TagWidget)
        self.TagWidget.selected_id = self.selected_id = default_tag

    @Slot()
    def closeEvent(self, event):
        self.selected_id = self.TagWidget.selected_id
        super().closeEvent(event)
