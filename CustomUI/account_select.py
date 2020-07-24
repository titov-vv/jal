from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QMenu, QCompleter

from CustomUI.reference_data import ReferenceDataDialog, ReferenceBoolDelegate, \
    ReferenceLookupDelegate, ReferenceTimestampDelegate


########################################################################################################################
#  UI Button to choose accounts
########################################################################################################################
class AccountButton(QPushButton):
    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.p_account_id = 0
        self.setText("ANY")

        self.Menu = QMenu()
        self.Menu.addAction('Choose account', self.ChooseAccount)
        self.Menu.addAction('Any account', self.ClearAccount)
        self.setMenu(self.Menu)

        self.dialog = None

    def getId(self):
        return self.p_account_id

    def setId(self, account_id):
        self.p_account_id = account_id

    @Signal
    def account_id_changed(self):
        pass

    account_id = Property(int, getId, setId, notify=account_id_changed)

    @Signal
    def account_id_changed(self):
        pass

    def init_DB(self, db):
        self.dialog = ReferenceDataDialog(db, "accounts",
                            [("id", None, 0, None, None),
                             ("name", "Name", -1, Qt.AscendingOrder, None),
                             ("type_id", None, 0, None, None),
                             ("currency_id", "Currency", None, None, ReferenceLookupDelegate),
                             ("active", "Act", 32, None, ReferenceBoolDelegate),
                             ("number", "Account #", None, None, None),
                             ("reconciled_on", "Reconciled @", self.fontMetrics().width("00/00/0000 00:00:00") * 1.1,
                              None, ReferenceTimestampDelegate),
                             ("organization_id", "Bank", None, None, ReferenceLookupDelegate)],
                            title="Assets", search_field="full_name", toggle=("active", "Show inactive"),
                            relations=[("type_id", "account_types", "id", "name", "Account type:"),
                                       ("currency_id", "currencies", "id", "name", None),
                                       ("organization_id", "agents", "id", "name", None)])
        self.setText(self.dialog.SelectedName)

    def ChooseAccount(self):
        ref_point = self.mapToGlobal(self.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()
        res = self.dialog.exec_()
        if res:
            self.account_id = self.dialog.selected_id
            self.setText(self.dialog.SelectedName)
            self.clicked.emit()

    def ClearAccount(self):
        self.account_id = 0
        self.setText("ANY")
        self.clicked.emit()


########################################################################################################################
#  Custom UI account Editor
########################################################################################################################
class AccountSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_account_id = 0
        self.completer = None

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.name = QLineEdit()
        self.name.setText("")
        self.layout.addWidget(self.name)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.setFocusProxy(self.name)

        self.button.clicked.connect(self.OnButtonClicked)

        self.dialog = None

    def getId(self):
        return self.p_account_id

    def setId(self, account_id):
        if self.p_account_id == account_id:
            return
        self.p_account_id = account_id
        self.dialog.Model.setFilter(f"accounts.id={account_id}")  # TODO: check carefully
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
        self.dialog = ReferenceDataDialog(db, "accounts",
                            [("id", None, 0, None, None),
                             ("name", "Name", -1, Qt.AscendingOrder, None),
                             ("type_id", None, 0, None, None),
                             ("currency_id", "Currency", None, None, ReferenceLookupDelegate),
                             ("active", "Act", 32, None, ReferenceBoolDelegate),
                             ("number", "Account #", None, None, None),
                             ("reconciled_on", "Reconciled @", self.fontMetrics().width("00/00/0000 00:00:00") * 1.1,
                              None, ReferenceTimestampDelegate),
                             ("organization_id", "Bank", None, None, ReferenceLookupDelegate)],
                            title="Assets", search_field="full_name", toggle=("active", "Show inactive"),
                            relations=[("type_id", "account_types", "id", "name", "Account type:"),
                                       ("currency_id", "currencies", "id", "name", None),
                                       ("organization_id", "agents", "id", "name", None)])
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex("name"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()
        res = self.dialog.exec_()
        if res:
            self.account_id = self.dialog.selected_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.account_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)
