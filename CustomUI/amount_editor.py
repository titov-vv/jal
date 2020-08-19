from PySide2.QtWidgets import QLineEdit
from PySide2.QtGui import QDoubleValidator

class AmountEdit(QLineEdit):
    def __init__(self, parent=None):
        QLineEdit.__init__(self, parent)
        self.p_value = 0.0
        self.setFixedWidth(self.fontMetrics().width("  8,888,888,888.88"))
        self.setValidator(QDoubleValidator(decimals=8))
