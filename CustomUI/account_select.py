from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton
from PySide2.QtSql import QSqlTableModel
from ui_account_choice_dlg import Ui_AccountChoiceDlg

class AccountChoiceDlg(QDialog, Ui_AccountChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)

class AccountSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.symbol = QLineEdit()
        self.symbol.setText("Ticker")
        self.layout.addWidget(self.symbol)
        self.full_name = QLabel()
        self.full_name.setText("Full security name")
        self.layout.addWidget(self.full_name)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.button.clicked.connect(self.OnButtonClicked)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlTableModel(db=self.db)
        self.Model.setTable("accounts")

    def OnButtonClicked(self):
        dialog = AccountChoiceDlg()
        dialog.exec_()