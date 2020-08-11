from datetime import datetime
from PySide2.QtWidgets import QDialog
from PySide2 import QtCore
from UI.ui_rebuild_window import Ui_ReBuildDialog


class RebuildDialog(QDialog, Ui_ReBuildDialog):
    def __init__(self, parent, frontier):
        QDialog.__init__(self)
        self.setupUi(self)

        self.LastRadioButton.toggle()
        self.frontier = frontier
        frontier_text = datetime.fromtimestamp(frontier).strftime('%d/%m/%Y')
        self.FrontierDateLabel.setText(frontier_text)
        self.CustomDateEdit.setDate(QtCore.QDate.currentDate())

        # center dialog with respect to parent window
        x = parent.x() + parent.width()/2 - self.width()/2
        y = parent.y() + parent.height()/2 - self.height()/2
        self.setGeometry(x, y, self.width(), self.height())

    def getTimestamp(self):
        if self.LastRadioButton.isChecked():
            return self.frontier
        elif self.DateRadionButton.isChecked():
            return self.CustomDateEdit.dateTime().toSecsSinceEpoch()
        else:  # self.AllRadioButton.isChecked()
            return 0
