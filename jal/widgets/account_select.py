from PySide6.QtCore import Signal, Slot, Property
from PySide6.QtWidgets import QDialog, QWidget, QPushButton, QComboBox, QMenu, QHBoxLayout, QCheckBox, QMessageBox, QLabel
from jal.db.db import JalModel
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.widgets.helpers import center_window
from jal.widgets.reference_dialogs import AccountListDialog
from jal.ui.ui_select_account_dlg import Ui_SelectAccountDlg


########################################################################################################################
#  UI Button to choose accounts
########################################################################################################################
class AccountButton(QPushButton):
    changed = Signal(int)

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.p_account_id = 0

        self.Menu = QMenu(self)
        self.Menu.addAction(self.tr("Choose account"), self.ChooseAccount)
        self.Menu.addAction(self.tr("Any account"), self.ClearAccount)
        self.setMenu(self.Menu)

        self.dialog = AccountListDialog()
        self.setText(self.dialog.SelectedName)

    def get_id(self):
        return self.p_account_id

    def set_id(self, account_id):
        self.p_account_id = account_id
        if self.p_account_id:
            self.setText(JalAccount(account_id).name())
        else:
            self.setText(self.tr("ANY"))
        self.changed.emit(self.p_account_id)

    account_id = Property(int, get_id, set_id, notify=changed)

    def ChooseAccount(self):
        ref_point = self.mapToGlobal(self.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()
        res = self.dialog.exec(enable_selection=True)
        if res:
            self.account_id = self.dialog.selected_id

    def ClearAccount(self):
        self.account_id = 0


#-----------------------------------------------------------------------------------------------------------------------
# This class displays a symbol of account currency in a label.
# The account is set using 'account_id' property that may be mapped to the database column
class AccountCurrencyLabel(QLabel):
    EMPTY = "---"

    def __init__(self, parent):
        super().__init__(parent=parent)
        self._account_id = 0
        self.setText(self.EMPTY)

    def get_id(self) -> str:
        return str(self._account_id)

    def set_id(self, account_id: str):
        self._account_id = int(account_id) if account_id else 0
        if self._account_id:
            self.setText(JalAsset(JalAccount(self._account_id).currency()).symbol())
        else:
            self.setText(self.EMPTY)

    account_id = Property(str, fget=get_id, fset=set_id, user=True)   # Property has string value as workaround for QTBUG-115144

#-----------------------------------------------------------------------------------------------------------------------
# Dialog for account selection
# Constructor takes description to show and recent_account for default choice.
# Selected account won't be equal to current_account
class SelectAccountDialog(QDialog):
    def __init__(self, description, current_account, recent_account=None):
        super().__init__()
        self.ui = Ui_SelectAccountDlg()
        self.ui.setupUi(self)
        self.account_id = recent_account
        self.store_account = False
        self.current_account = current_account

        self.ui.DescriptionLbl.setText(description)
        if self.account_id:
            self.ui.AccountWidget.selected_id = self.account_id
        center_window(self)

    @Slot()
    def closeEvent(self, event):
        self.account_id = self.ui.AccountWidget.selected_id
        self.store_account = self.ui.ReuseAccount.isChecked()
        if self.ui.AccountWidget.selected_id == 0:
            QMessageBox().warning(None, self.tr("No selection"), self.tr("Invalid account selected"), QMessageBox.Ok)
            event.ignore()
            return

        if self.ui.AccountWidget.selected_id == self.current_account:
            QMessageBox().warning(None, self.tr("No selection"), self.tr("Please select different account"),
                                  QMessageBox.Ok)
            event.ignore()
            return

        self.setResult(QDialog.Accepted)
        event.accept()


# ----------------------------------------------------------------------------------------------------------------------
class CurrencyComboBox(QComboBox):
    changed = Signal(int)

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.p_selected_id = 0
        self.model = None
        self.activated.connect(self.OnUserSelection)

        self.model = JalModel(self, "currencies")
        self.model.select()
        self.setModel(self.model)
        self.setModelColumn(self.model.fieldIndex("symbol"))

    def get_id(self):
        return self.p_selected_id

    def set_id(self, new_id):
        if self.p_selected_id == new_id:
            return
        self.p_selected_id = new_id
        name = JalAsset(self.p_selected_id).symbol()
        if self.currentIndex() == self.findText(name):
            return
        self.setCurrentIndex(self.findText(name))

    selected_id = Property(int, get_id, set_id, notify=changed, user=True)

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
    name_updated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._id = 0

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.null_flag = QCheckBox(parent)
        self.null_flag.setChecked(False)
        self.null_flag.setText(self.tr("Currency"))
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

    def get_id(self) -> int:
        return self._id if self._id else None

    def set_id(self, new_value: int):
        if self._id == new_value:
            return
        self._id = new_value
        self.updateView()
        name = JalAsset(self._id).symbol()
        self.name_updated.emit('' if name is None else name)

    currency_id = Property(int, get_id, set_id, notify=changed, user=True)
    
    def get_str_id(self) -> str:
        string_id = '' if self.get_id() is None else str(self.get_id())
        return string_id

    def set_str_id(self, string_id: str):
        new_id = int(string_id) if string_id else 0
        self.set_id(new_id)
    
    currency_id_str = Property(str, get_str_id, set_str_id, notify=changed)  # workaround for QTBUG-115144

    def updateView(self):
        has_value = True if self._id else False
        if has_value:
            self.currency.selected_id = self._id
        self.null_flag.setChecked(has_value)
        self.currency.setEnabled(has_value)

    @Slot()
    def onClick(self):
        if self.null_flag.isChecked():
            if self.currency.selected_id == 0:
                self.currency.selected_id = JalAsset.get_base_currency()
            self.currency_id = self.currency.selected_id
        else:
            self.currency_id = 0
        self.changed.emit()

    @Slot()
    def onCurrencyChange(self, _id):
        self.currency_id = self.currency.selected_id
        self.changed.emit()
