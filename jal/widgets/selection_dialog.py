from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from jal.constants import Setup
from jal.ui.ui_select_reference_dlg import Ui_SelectReferenceDlg
from jal.widgets.reference_selector import CategorySelector
from jal.widgets.reference_selector import TagSelector


#-----------------------------------------------------------------------------------------------------------------------
# Common base GUI dialog class for selector dialogs. Takes window title and label comment to describe selection
class SelectReferenceDialog(QDialog, Ui_SelectReferenceDlg):
    def __init__(self, title, description):
        QDialog.__init__(self)
        self.setupUi(self)
        self.selected_id = 0
        self.setWindowTitle(title)
        self.DescriptionLabel.setText(description)
        # center dialog with respect to main application window
        parent = None
        for widget in QApplication.topLevelWidgets():           # TODO - repeating code - move to dedicated routine
            if widget.objectName() == Setup.MAIN_WND_NAME:
                parent = widget
        if parent:
            x = parent.x() + parent.width() / 2 - self.width() / 2
            y = parent.y() + parent.height() / 2 - self.height() / 2
            self.setGeometry(x, y, self.width(), self.height())

    @Slot()
    def closeEvent(self, event):
        if self.selected_id == 0:
            QMessageBox().warning(None, self.tr("No selection"), self.tr("You should select something"), QMessageBox.Ok)
            event.ignore()
            return
        self.setResult(QDialog.Accepted)
        event.accept()


#-----------------------------------------------------------------------------------------------------------------------
# Dialog for category selection
# Constructor takes description to show and default_category for initial choice
class SelectCategoryDialog(SelectReferenceDialog):
    def __init__(self, description, default_category=0):
        SelectReferenceDialog.__init__(self, self.tr("Please select category"), description)
        self.CategoryWidget = CategorySelector(self.SelectorFrame)
        self.FrameLayout.addWidget(self.CategoryWidget)
        self.selected_id = default_category
        if self.selected_id:
            self.CategoryWidget.selected_id = self.selected_id

    @Slot()
    def closeEvent(self, event):
        self.selected_id = self.CategoryWidget.selected_id
        super().closeEvent(event)


#-----------------------------------------------------------------------------------------------------------------------
# Dialog for tag selection
# Constructor takes description to show and default_tag for initial choice
class SelectTagDialog(SelectReferenceDialog):
    def __init__(self, description, default_tag=0):
        SelectReferenceDialog.__init__(self, self.tr("Please select tag"), description)
        self.TagWidget = TagSelector(self.SelectorFrame)
        self.FrameLayout.addWidget(self.TagWidget)
        self.selected_id = default_tag
        if self.selected_id:
            self.TagWidget.selected_id = self.selected_id

    @Slot()
    def closeEvent(self, event):
        self.selected_id = self.TagWidget.selected_id
        super().closeEvent(event)
