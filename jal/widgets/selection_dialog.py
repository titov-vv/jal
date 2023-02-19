from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from jal.constants import Setup
from jal.ui.ui_select_category_dlg import Ui_SelectCategoryDlg
from jal.ui.ui_select_tag_dlg import Ui_SelectTagDlg

#-----------------------------------------------------------------------------------------------------------------------
# Dialog for tag selection
# Constructor takes description to show and default_tag for initial choice
class SelectTagDialog(QDialog, Ui_SelectTagDlg):
    def __init__(self, description, default_tag=None):
        QDialog.__init__(self)
        self.setupUi(self)
        self.tag_id = default_tag
        self.store_account = False
        self.DescriptionLbl.setText(description)
        if self.tag_id:
            self.TagWidget.selected_id = self.tag_id
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
        self.tag_id = self.TagWidget.selected_id
        if self.TagWidget.selected_id == 0:
            QMessageBox().warning(None, self.tr("No selection"), self.tr("Invalid tag selected"), QMessageBox.Ok)
            event.ignore()
            return
        self.setResult(QDialog.Accepted)
        event.accept()


#-----------------------------------------------------------------------------------------------------------------------
# Dialog for category selection
# Constructor takes description to show and default_category for initial choice
class SelectCategoryDialog(QDialog, Ui_SelectCategoryDlg):
    def __init__(self, description, default_category=None):
        QDialog.__init__(self)
        self.setupUi(self)
        self.category_id = default_category
        self.store_account = False
        self.DescriptionLbl.setText(description)
        if self.category_id:
            self.CategoryWidget.selected_id = self.category_id
        # center dialog with respect to main application window
        parent = None
        for widget in QApplication.topLevelWidgets():  # TODO - repeating code - move to dedicated routine
            if widget.objectName() == Setup.MAIN_WND_NAME:
                parent = widget
        if parent:
            x = parent.x() + parent.width() / 2 - self.width() / 2
            y = parent.y() + parent.height() / 2 - self.height() / 2
            self.setGeometry(x, y, self.width(), self.height())

    @Slot()
    def closeEvent(self, event):
        self.category_id = self.CategoryWidget.selected_id
        if self.CategoryWidget.selected_id == 0:
            QMessageBox().warning(None, self.tr("No selection"), self.tr("Invalid category selected"), QMessageBox.Ok)
            event.ignore()
            return
        self.setResult(QDialog.Accepted)
        event.accept()
