from PySide2.QtCore import Signal, Slot, Property
from PySide2.QtWidgets import QPushButton, QComboBox, QMenu
from PySide2.QtSql import QSqlTableModel
from jal.widgets.helpers import g_tr
from jal.db.helpers import db_connection, get_field_by_id_from_table
from jal.widgets.reference_dialogs import AccountListDialog

########################################################################################################################
#  UI Button to choose accounts
########################################################################################################################
class AccountButton(QPushButton):
    changed = Signal(int)

    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.p_account_id = 0

        self.Menu = QMenu(self)
        self.Menu.addAction(g_tr('AccountButton', "Choose account"), self.ChooseAccount)
        self.Menu.addAction(g_tr('AccountButton', "Any account"), self.ClearAccount)
        self.setMenu(self.Menu)

        self.dialog = AccountListDialog()
        self.setText(self.dialog.SelectedName)

    def getId(self):
        return self.p_account_id

    def setId(self, account_id):
        self.p_account_id = account_id
        self.setText(self.dialog.SelectedName)
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
