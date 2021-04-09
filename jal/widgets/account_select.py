from PySide2.QtCore import Signal, Slot, Property
from PySide2.QtWidgets import QWidget, QPushButton, QComboBox, QMenu, QHBoxLayout, QCheckBox
from PySide2.QtSql import QSqlQuery, QSqlTableModel
from jal.constants import PredefinedAsset
from jal.widgets.helpers import g_tr
from jal.db.update import JalDB
from jal.db.settings import JalSettings
from jal.db.helpers import db_connection, readSQL
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
        if self.p_account_id:
            self.setText(JalDB().get_account_name(account_id))
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


# ----------------------------------------------------------------------------------------------------------------------
class CurrencyComboBox(QComboBox):
    changed = Signal(int)

    def __init__(self, parent):
        QComboBox.__init__(self, parent)
        self.p_selected_id = 0
        self.model = None
        self.activated.connect(self.OnUserSelection)

        self.query = QSqlQuery(db=db_connection())
        self.query.prepare(f"SELECT id, name FROM assets WHERE type_id={PredefinedAsset.Money}")
        self.query.exec_()
        self.model = QSqlTableModel(db=db_connection())
        self.model.setQuery(self.query)
        self.model.select()
        self.setModel(self.model)
        self.setModelColumn(self.model.fieldIndex("name"))

    def isCustom(self):
        return True

    def getId(self):
        return self.p_selected_id

    def setId(self, new_id):
        if self.p_selected_id == new_id:
            return
        self.p_selected_id = new_id
        name = readSQL("SELECT name FROM currencies WHERE id = :id", [(":id", self.p_selected_id)])
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


# ----------------------------------------------------------------------------------------------------------------------
class OptionalCurrencyComboBox(QWidget):
    changed = Signal()
    updated = Signal(str)

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.p_value = ''
        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.null_flag = QCheckBox(parent)
        self.null_flag.setChecked(False)
        self.null_flag.setText('Optional currency')
        self.layout.addWidget(self.null_flag)
        self.currency = CurrencyComboBox(parent)
        self.currency.setEnabled(False)
        self.layout.addWidget(self.currency)
        self.setLayout(self.layout)

        self.setFocusProxy(self.null_flag)
        self.null_flag.clicked.connect(self.onClick)
        self.currency.changed.connect(self.onCurrencyChange)

    def setText(self, text):
        self.null_flag.setText(text)

    def getId(self):
        if self.p_value:
            return self.p_value
        else:
            return None

    def setId(self, new_value):
        if self.p_value == new_value:
            return
        self.p_value = new_value
        self.updateView()
        name = JalDB().get_asset_name(self.p_value)
        self.updated.emit(name)

    currency_id = Property(str, getId, setId, notify=changed, user=True)

    def updateView(self):
        has_value = True if self.p_value else False
        if has_value:
            self.currency.selected_id = int(self.p_value)
        self.null_flag.setChecked(has_value)
        self.currency.setEnabled(has_value)

    @Slot()
    def onClick(self):
        if self.null_flag.isChecked():
            if self.currency.selected_id == 0:
                self.currency.selected_id = JalSettings().getValue('BaseCurrency')
            self.currency_id = str(self.currency.selected_id)
        else:
            self.currency_id = ''
        self.changed.emit()

    @Slot()
    def onCurrencyChange(self, _id):
        self.currency_id = str(self.currency.selected_id)
        self.changed.emit()
