from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton
from PySide2.QtSql import QSqlRelationalTableModel, QSqlRelation
from PySide2.QtCore import Signal, Property
from ui_account_choice_dlg import Ui_AccountChoiceDlg

class AccountChoiceDlg(QDialog, Ui_AccountChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)

        self.AccountTypeCombo.currentIndexChanged.connect(self.OnApplyFilter)

    def OnApplyFilter(self, list_id):
        model = self.AccountTypeCombo.model()
        id = model.data(model.index(list_id, 0))  # 0 is a field number for "id"
        self.AccountsList.model().setFilter(f"accounts.type_id={id}")

class AccountSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.acc_id = 0

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

        self.dialog = AccountChoiceDlg()

    def getId(self):
        return self.acc_id

    def setId(self, id):
        self.acc_id = id
        self.symbol.setText("ID: {}".format(id))

    @Signal
    def account_id_changed(self):
        pass

    account_id = Property(int, getId, setId)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlRelationalTableModel(db=self.db)
        self.Model.setTable("accounts")
        type_idx = self.Model.fieldIndex("type_id")
        self.Model.setRelation(type_idx, QSqlRelation("account_types", "id", "name"))
        currency_id = self.Model.fieldIndex("currency_id")
        self.Model.setRelation(currency_id, QSqlRelation("actives", "id", "name"))
        org_id = self.Model.fieldIndex("organization_id")
        self.Model.setRelation(org_id, QSqlRelation("agents", "id", "name"))

        self.dialog.AccountsList.setModel(self.Model)
        self.dialog.AccountsList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.dialog.AccountTypeCombo.setModel(self.Model.relationModel(type_idx))
        self.dialog.AccountTypeCombo.setModelColumn(self.Model.relationModel(type_idx).fieldIndex("name"))
        self.Model.select()

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.symbol.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.exec_()