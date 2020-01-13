from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QPushButton, QAbstractItemView, QMenu
from PySide2.QtSql import QSqlRelationalTableModel, QSqlRelation
from PySide2.QtCore import Signal, Property, Slot
from ui_account_choice_dlg import Ui_AccountChoiceDlg

#TODO clean-up columns
class AccountChoiceDlg(QDialog, Ui_AccountChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.account_id = 0

    def getAccountName(self):
        if self.account_id == 0:
            return "ALL"
        else:
            return self.p_account_name

    def setAccountName(self, id):
        pass

    @Signal
    def account_name_changed(self):
        pass

    AccountName = Property(str, getAccountName, setAccountName, notify=account_name_changed)

    def Activate(self):
        self.AccountTypeCombo.currentIndexChanged.connect(self.OnApplyFilter)
        self.AccountsList.selectionModel().selectionChanged.connect(self.OnAccountChosen)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlRelationalTableModel(db=self.db)
        self.Model.setTable("accounts")
        self.Model.setJoinMode(QSqlRelationalTableModel.LeftJoin)   # to work correctly with NULL values in OrgId
        type_idx = self.Model.fieldIndex("type_id")
        self.Model.setRelation(type_idx, QSqlRelation("account_types", "id", "name"))
        currency_id = self.Model.fieldIndex("currency_id")
        self.Model.setRelation(currency_id, QSqlRelation("actives", "id", "name"))
        org_id = self.Model.fieldIndex("organization_id")
        self.Model.setRelation(org_id, QSqlRelation("agents", "id", "name"))

        self.AccountsList.setModel(self.Model)
        self.AccountsList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.AccountsList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.AccountTypeCombo.setModel(self.Model.relationModel(type_idx))
        self.AccountTypeCombo.setModelColumn(self.Model.relationModel(type_idx).fieldIndex("name"))
        self.Model.select()
        self.Activate()

#TODO: Make filter for inactive accounts
    @Slot()
    def OnApplyFilter(self, list_id):
        model = self.AccountTypeCombo.model()
        id = model.data(model.index(list_id, 0))  # 0 is a field number for "id"
        self.AccountsList.model().setFilter(f"accounts.type_id={id}")

    @Slot()
    def OnAccountChosen(self, selected, deselected):
        idx = selected.indexes()
        selected_row = idx[0].row()
        self.account_id = self.AccountsList.model().record(selected_row).value(0)
        self.p_account_name = self.AccountsList.model().record(selected_row).value(2)

class AccountButton(QPushButton):
    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.p_account_id = 0
        self.setText("ALL")

        self.Menu = QMenu()
        self.Menu.addAction('Choose account', self.ChooseAccount)
        self.Menu.addAction('Any account', self.ClearAccount)
        self.setMenu(self.Menu)

        #self.clicked.connect(self.OnButtonClicked)
        self.dialog = AccountChoiceDlg()

    def getId(self):
        return self.p_account_id

    def setId(self, id):
        self.p_account_id = id

    @Signal
    def account_id_changed(self):
        pass

    account_id = Property(int, getId, setId, notify=account_id_changed)

    @Signal
    def account_id_changed(self):
        pass

    def init_DB(self, db):
        self.dialog.init_DB(db)
        self.setText(self.dialog.AccountName)

    def ChooseAccount(self):
        ref_point = self.mapToGlobal(self.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec_()
        if res:
            self.account_id = self.dialog.account_id
            self.setText(self.dialog.AccountName)
            self.clicked.emit()

    def ClearAccount(self):
        self.account_id = 0
        self.setText("ALL")
        self.clicked.emit()

#TODO: Add autocomplete feature
class AccountSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_account_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.name = QLineEdit()
        self.name.setText("Account name")
        self.layout.addWidget(self.name)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.button.clicked.connect(self.OnButtonClicked)

        self.dialog = AccountChoiceDlg()

    def getId(self):
        return self.p_account_id

    def setId(self, id):
        self.p_account_id = id
        self.dialog.Model.setFilter(f"accounts.id={id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        account_name = self.dialog.Model.record(row_idx).value(2)
        self.name.setText(account_name)
        self.dialog.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    account_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.dialog.init_DB(db)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec_()
        if res:
            self.account_id = self.dialog.account_id
