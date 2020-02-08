from constants import *
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide2.QtSql import QSqlQuery
from PySide2.QtCore import Signal, Property
from PySide2.QtGui import QPalette

class TradeAction(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_trade_id = 0

        self.layout = QHBoxLayout()
        self.label = QLabel()
        self.label.setText("")
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        self.palette = QPalette()

    def init_DB(self, db):
        self.db = db

    def getId(self):
        return self.p_trade_id

    def setId(self, id):
        if (self.p_trade_id == id):
            return
        self.p_trade_id = id
        query = QSqlQuery(self.db)
        query.prepare("SELECT corp_action_id, qty, a.type, a.note FROM trades AS t "
                      "LEFT JOIN corp_actions AS a ON t.corp_action_id = a.id  WHERE t.id=:trade_id")
        query.bindValue(":trade_id", id)
        assert query.exec_()
        if query.next():
            qty = query.value(1)
            corp_action_type = query.value(2)
            if corp_action_type:
                self.label.setText("CORP.ACTION")
                self.palette.setColor(self.label.foregroundRole(), DARK_BLUE_COLOR)
                self.label.setPalette(self.palette)
            else:
                if qty>0:
                    self.label.setText("BUY")
                    self.palette.setColor(self.label.foregroundRole(), DARK_GREEN_COLOR)
                    self.label.setPalette(self.palette)
                else:
                    self.label.setText("SELL")
                    self.palette.setColor(self.label.foregroundRole(), DARK_RED_COLOR)
                    self.label.setPalette(self.palette)
        else:
            self.label.setText("ERROR")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    account_id = Property(int, getId, setId, notify=changed, user=True)


