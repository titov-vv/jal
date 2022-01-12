from PySide6.QtCore import Slot, Signal
from PySide6.QtWidgets import QWidget


# ----------------------------------------------------------------------------------------------------------------------
# Base class that is used for any other widget which should be displayed in JAL MainWindow MDI area
class MdiWidget(QWidget):
    onClose = Signal(QWidget)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

    @Slot()
    def closeEvent(self, event):
        self.onClose.emit(self.parent())
        super().closeEvent(event)

    def refresh(self):
        pass
