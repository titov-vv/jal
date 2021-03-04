from PySide2.QtCore import Qt, Signal, Slot, Property
from PySide2.QtWidgets import QPushButton, QComboBox, QMenu
from PySide2.QtSql import QSqlTableModel
from jal.constants import ColumnWidth
from jal.ui_custom.helpers import g_tr
from jal.db.helpers import db_connection, get_account_name, get_field_by_id_from_table
from jal.ui_custom.reference_data import ReferenceDataDialog, ReferenceBoolDelegate, \
    ReferenceLookupDelegate, ReferenceTimestampDelegate
from jal.ui_custom.reference_selector import AbstractReferenceSelector


# ----------------------------------------------------------------------------------------------------------------------
class AccountsListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "accounts",
                                     [("id", None, 0, None, None),
                                      ("name", g_tr('AccountButton', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                                      ("type_id", None, 0, None, None),
                                      ("currency_id", g_tr('AccountButton', "Currency"), None, None, ReferenceLookupDelegate),
                                      ("active", g_tr('AccountButton', "Act."), 32, None, ReferenceBoolDelegate),
                                      ("number", g_tr('AccountButton', "Account #"), None, None, None),
                                      ("reconciled_on", g_tr('AccountButton', "Reconciled @"), ColumnWidth.FOR_DATETIME, None, ReferenceTimestampDelegate),
                                      ("organization_id", g_tr('AccountButton', "Bank"), None, None, ReferenceLookupDelegate)],
                                     title=g_tr('AccountsListDialog', "Accounts"),
                                     search_field="full_name",
                                     toggle=("active", g_tr('AccountButton', "Show inactive")),
                                     relations=[("type_id", "account_types", "id", "name",
                                                 g_tr('AccountButton', "Account type:")),
                                                ("currency_id", "currencies", "id", "name", None),
                                                ("organization_id", "agents", "id", "name", None)])


# ----------------------------------------------------------------------------------------------------------------------
class AccountSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)
        self.dialog = AccountsListDialog()

    def init_db(self, db):
        super().init_db("accounts", "name")

########################################################################################################################
#  UI Button to choose accounts
########################################################################################################################
class AccountButton(QPushButton):
    changed = Signal(int)

    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.p_account_id = 0
        self.setText(g_tr('AccountButton', "ANY"))

        self.Menu = QMenu(self)
        self.Menu.addAction(g_tr('AccountButton', "Choose account"), self.ChooseAccount)
        self.Menu.addAction(g_tr('AccountButton', "Any account"), self.ClearAccount)
        self.setMenu(self.Menu)

        self.dialog = AccountsListDialog()
        self.setText(self.dialog.SelectedName)

    def getId(self):
        return self.p_account_id

    def setId(self, account_id):
        self.p_account_id = account_id
        if self.p_account_id:
            self.setText(get_account_name(account_id))
        else:
            self.setText(g_tr('AccountButton', "ANY"))
        self.changed.emit(self.p_account_id)

    account_id = Property(int, getId, setId, notify=changed)

    def ChooseAccount(self):
        ref_point = self.mapToGlobal(self.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()
        res = self.dialog.exec_(enable_selection=True)
        if res:
            self.account_id = self.dialog.selected_id

    def ClearAccount(self):
        self.account_id = 0


class CurrencyComboBox(QComboBox):
    changed = Signal(int)

    def __init__(self, parent):
        QComboBox.__init__(self, parent)
        self.p_selected_id = 0
        self.model = None
        self.table_name = 'currencies'
        self.field_name = 'name'
        self.activated.connect(self.OnUserSelection)

        self.model = QSqlTableModel(db=db_connection())
        self.model.setTable(self.table_name)
        self.model.select()
        self.setModel(self.model)
        self.setModelColumn(self.model.fieldIndex(self.field_name))

    def isCustom(self):
        return True

    def getId(self):
        return self.p_selected_id

    def setId(self, new_id):
        if self.p_selected_id == new_id:
            return
        self.p_selected_id = new_id
        name = get_field_by_id_from_table(self.table_name, self.field_name, self.p_selected_id)
        if self.currentIndex() == self.findText(name):
            return
        self.setCurrentIndex(self.findText(name))

    selected_id = Property(int, getId, setId, notify=changed, user=True)

    def setIndex(self, index):
        if index is not None:
            self.selected_id = index
            self.changed.emit(self.selected_id)

    @Slot()
    def OnUserSelection(self, _selected_index):
        self.selected_id = self.model.record(self.currentIndex()).value("id")
        self.changed.emit(self.selected_id)
