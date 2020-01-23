from constants import *
from datetime import datetime
from PySide2.QtCore import Qt, Signal, Property, Slot
from PySide2.QtSql import QSqlRelationalDelegate
from PySide2.QtWidgets import QWidget

def formatFloatLong(value):
    if (abs(value - round(value, 2)) >= CALC_TOLERANCE):
        text = str(value)
    else:
        text = f"{value:.2f}"
    return text

class OptionGroup(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.ButtonsList = []
        self.selected_btn = 0

    def getSelection(self):
        return self.selected_btn

    def setSelection(self, selection):
        self.selected_btn = 0
        for button in self.ButtonsList:
            if button[1] == selection:
                button[0].setChecked(True)
                self.selected_btn = selection

    @Signal
    def selection_changed(self):
        pass

    Selection = Property(int, getSelection, setSelection, notify=selection_changed, user=True)

    def addButton(self, button, id):
        self.ButtonsList.append([button, id])
        button.toggled.connect(self.OnButtonToggle)

#    @Slot
    def OnButtonToggle(self, checked):
        if checked:
            src = self.sender()
            for button in self.ButtonsList:
                if button[0] == src:
                    self.selected_btn = button[1]


class TradeSqlDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def setEditorData(self, editor, index):
        if (index.column() == 1) or (index.column() == 2):  # timestamp & settlement columns
            editor.setDateTime(datetime.fromtimestamp(index.model().data(index, Qt.EditRole)))
        elif (index.column() >= 7) and (index.column() <= 11): # price, qty, coupon, fees
            editor.setText(formatFloatLong(index.model().data(index, Qt.EditRole)))
        else:
            QSqlRelationalDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if (index.column() == 1) or (index.column() == 2):  # timestamp & settlement columns
            timestamp = editor.dateTime().toSecsSinceEpoch()
            model.setData(index, timestamp)
        else:
            QSqlRelationalDelegate.setModelData(self, editor, model, index)