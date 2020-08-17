from PySide2.QtCore import Signal, Property
from PySide2.QtWidgets import QWidget


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

    def addButton(self, button, linked_id):
        self.ButtonsList.append([button, linked_id])
        button.toggled.connect(self.OnButtonToggle)

    #    @Slot
    def OnButtonToggle(self, checked):
        if checked:
            src = self.sender()
            for button in self.ButtonsList:
                if button[0] == src:
                    self.selected_btn = button[1]
