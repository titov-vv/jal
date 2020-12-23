from PySide2.QtCore import Qt, Signal, Slot, Property
from PySide2.QtWidgets import QPushButton, QComboBox, QMenu
from PySide2.QtSql import QSqlTableModel
from jal.ui_custom.helpers import g_tr
from jal.db.helpers import  get_account_name, get_field_by_id_from_table

from jal.ui_custom.reference_data import ReferenceDataDialog, ReferenceBoolDelegate, \
    ReferenceLookupDelegate, ReferenceTimestampDelegate


########################################################################################################################
#  UI Button to choose accounts
########################################################################################################################
class AccountButton(QPushButton):
    changed = Signal(int)

    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.db = None
        self.p_account_id = 0
        self.setText(g_tr('AccountButton', "ANY"))

        self.Menu = QMenu(self)
        self.Menu.addAction(g_tr('AccountButton', "Choose account"), self.ChooseAccount)
        self.Menu.addAction(g_tr('AccountButton', "Any account"), self.ClearAccount)
        self.setMenu(self.Menu)

        self.dialog = None

    def getId(self):
        return self.p_account_id

    def setId(self, account_id):
        self.p_account_id = account_id
        if self.p_account_id:
            self.setText(get_account_name(self.db, account_id))
        else:
            self.setText(g_tr('AccountButton', "ANY"))
        self.changed.emit(self.p_account_id)

    account_id = Property(int, getId, setId, notify=changed)

    def init_db(self, db):
        self.db = db
        self.dialog = ReferenceDataDialog(db, "accounts",
                            [("id", None, 0, None, None),
                             ("name", g_tr('AccountButton', "Name"), -1, Qt.AscendingOrder, None),
                             ("type_id", None, 0, None, None),
                             ("currency_id", g_tr('AccountButton', "Currency"), None, None, ReferenceLookupDelegate),
                             ("active", g_tr('AccountButton', "Act."), 32, None, ReferenceBoolDelegate),
                             ("number", g_tr('AccountButton', "Account #"), None, None, None),
                             ("reconciled_on", g_tr('AccountButton', "Reconciled @"), self.fontMetrics().width("00/00/0000 00:00:00") * 1.1,
                              None, ReferenceTimestampDelegate),
                             ("organization_id", g_tr('AccountButton', "Bank"), None, None, ReferenceLookupDelegate)],
                            title=g_tr('AccountButton', "Accounts"),
                            search_field="full_name",
                            toggle=("active", g_tr('AccountButton', "Show inactive")),
                            relations=[("type_id", "account_types", "id", "name", g_tr('AccountButton', "Account type:")),
                                       ("currency_id", "currencies", "id", "name", None),
                                       ("organization_id", "agents", "id", "name", None)])
        self.setText(self.dialog.SelectedName)

    def ChooseAccount(self):
        ref_point = self.mapToGlobal(self.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()
        res = self.dialog.exec_(enable_selection=True)
        if res:
            self.account_id = self.dialog.selected_id

    def ClearAccount(self):
        self.account_id = 0


class ComboBoxDB(QComboBox):
    changed = Signal(int)

    def __init__(self, parent):
        QComboBox.__init__(self, parent)
        self.p_selected_id = 0
        self.model = None
        self.table_name = ''
        self.field_name = ''
        self.activated.connect(self.OnUserSelection)

    def isCustom(self):
        return True

    def getId(self):
        return self.p_selected_id

    def setId(self, new_id):
        if self.p_selected_id == new_id:
            return
        self.p_selected_id = new_id
        name = get_field_by_id_from_table(self.model.database(),self.table_name, self.field_name, self.p_selected_id)
        if self.currentIndex() == self.findText(name):
            return
        self.setCurrentIndex(self.findText(name))

    selected_id = Property(int, getId, setId, notify=changed, user=True)

    def getName(self):
        return self.model.record(self.currentIndex()).value(self.field_name)

    selected_name = Property(str, getName, None)

    def init_db(self, db, default_id=None):
        self.table_name =  self.property('table_name')
        self.field_name = self.property('field_name')

        self.model = QSqlTableModel(db=db)
        self.model.setTable(self.table_name)
        self.model.select()
        self.setModel(self.model)
        self.setModelColumn(self.model.fieldIndex(self.field_name))

        if default_id is not None:
            self.selected_id = default_id
            self.changed.emit(self.selected_id)

    @Slot()
    def OnUserSelection(self, _selected_index):
        self.selected_id = self.model.record(self.currentIndex()).value("id")
        self.changed.emit(self.selected_id)
