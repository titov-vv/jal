from datetime import datetime
from PySide2.QtWidgets import (QDialog)
from PySide2 import QtCore
from UI.ui_rebuild_window import Ui_ReBuildDialog

class RebuildDialog(QDialog, Ui_ReBuildDialog):
    def __init__(self, frontier):
        QDialog.__init__(self)
        self.setupUi(self)

        self.LastRadioButton.toggle()
        self.frontier = frontier
        frontier_text = datetime.fromtimestamp(frontier).strftime('%d/%m/%Y')
        self.FrontierDateLabel.setText(frontier_text)
        self.CustomDateEdit.setDateTime(QtCore.QDateTime.currentDateTime())
        self.CustomDateEdit.setCalendarPopup(True)
        self.CustomDateEdit.setDisplayFormat("dd/MM/yyyy")

    def getTimestamp(self):
        if self.LastRadioButton.isChecked():
            return self.frontier
        elif self.DateRadionButton.isChecked():
            return self.CustomDateEdit.dateTime().toSecsSinceEpoch()
        else: # self.AllRadioButton.isChecked()
            return 0