from constants import *
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide2.QtCore import Signal, Property
from PySide2.QtGui import QPalette


class TradeAction(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.db = None
        self.p_type = 0

        self.layout = QHBoxLayout()
        self.label = QLabel()
        self.label.setText("")
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        self.palette = QPalette()

    def init_db(self, db):
        self.db = db

    def getType(self):
        return self.p_type

    def setType(self, trade_type):
        # if (self.p_type == type):
        #     return
        self.p_type = trade_type

        if self.p_type:
            self.label.setText("CORP.ACTION")
            self.palette.setColor(self.label.foregroundRole(), DARK_BLUE_COLOR)
            self.label.setPalette(self.palette)
        else:
            self.label.setText("TRADE")
            self.palette.setColor(self.label.foregroundRole(), DARK_GREEN_COLOR)
            self.label.setPalette(self.palette)
        #         else:
        #             self.label.setText("SELL")
        #             self.palette.setColor(self.label.foregroundRole(), DARK_RED_COLOR)
        #             self.label.setPalette(self.palette)
        # else:
        #     self.label.setText("UNKNOWN")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    corp_action_type = Property(int, getType, setType, notify=changed, user=True)

    def isCustom(self):
        return True
