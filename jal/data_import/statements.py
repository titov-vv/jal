from PySide2.QtCore import QObject, Signal, Slot
from PySide2.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from jal.db.helpers import readSQL, account_last_date

from jal.constants import Setup
from jal.widgets.helpers import g_tr
from jal.ui.ui_select_account_dlg import Ui_SelectAccountDlg
from jal.data_import.statement_quik import Quik
from jal.data_import.statement_ibkr import IBKR
from jal.data_import.statement_ibkr_old import IBKR_obsolete
from jal.data_import.statement_uralsib import UralsibCapital
from jal.data_import.statement_kit import KITFinance


# TODO make common ancestor for statement loader classes but not StatementLoader (to prevent extra objects creation)
# -----------------------------------------------------------------------------------------------------------------------
class SelectAccountDialog(QDialog, Ui_SelectAccountDlg):
    def __init__(self, description, current_account, recent_account=None):
        QDialog.__init__(self)
        self.setupUi(self)
        self.account_id = recent_account
        self.current_account = current_account

        self.DescriptionLbl.setText(description)
        if self.account_id:
            self.AccountWidget.selected_id = self.account_id

        # center dialog with respect to main application window
        parent = None
        for widget in QApplication.topLevelWidgets():
            if widget.objectName() == Setup.MAIN_WND_NAME:
                parent = widget
        if parent:
            x = parent.x() + parent.width() / 2 - self.width() / 2
            y = parent.y() + parent.height() / 2 - self.height() / 2
            self.setGeometry(x, y, self.width(), self.height())

    @Slot()
    def closeEvent(self, event):
        self.account_id = self.AccountWidget.selected_id
        if self.AccountWidget.selected_id == 0:
            QMessageBox().warning(None, g_tr('ReferenceDataDialog', "No selection"),
                                  g_tr('ReferenceDataDialog', "Invalid account selected"),
                                  QMessageBox.Ok)
            event.ignore()
            return

        if self.AccountWidget.selected_id == self.current_account:
            QMessageBox().warning(None, g_tr('ReferenceDataDialog', "No selection"),
                                  g_tr('ReferenceDataDialog', "Please select different account"),
                                  QMessageBox.Ok)
            event.ignore()
            return

        self.setResult(QDialog.Accepted)
        event.accept()


# -----------------------------------------------------------------------------------------------------------------------
class StatementLoader(QObject):
    load_completed = Signal()
    load_failed = Signal()

    def __init__(self):
        super().__init__()
        self.sources = [
            {
                'name': g_tr('StatementLoader', "Quik HTML"),
                'filter': "Quik HTML-report (*.htm)",
                'loader': self.loadQuikHtml,
                'icon': "quik.ico"
            },
            {
                'name': g_tr('StatementLoader', "Interactive Brokers XML"),
                'filter': "IBKR flex-query (*.xml)",
                'loader': self.loadIBFlex,
                'icon': "ibkr.png"
            },
            {
                'name': g_tr('StatementLoader', "Uralsib Broker"),
                'filter': "Uralsib statement (*.zip)",
                'loader': self.loadUralsibCapital,
                'icon': "uralsib.ico"
            },
            {
                'name': g_tr('StatementLoader', "KIT Finance"),
                'filter': "KIT Finance statement (*.xlsx)",
                'loader': self.loadKITFinance,
                'icon': 'kit.png'
            },
            {
                'name': g_tr('StatementLoader', "IBKR Activity HTML"),
                'filter': "IBKR Activity statement (*.html)",
                'loader': self.loadIBActivityStatement,
                'icon': 'cancel.png'
            }
        ]

    # method is called directly from menu so it contains QAction that was triggered
    def load(self, action):
        loader_id = action.data()
        statement_file, active_filter = QFileDialog.getOpenFileName(None, g_tr('StatementLoader',
                                                                               "Select statement file to import"),
                                                                    ".", self.sources[loader_id]['filter'])
        if statement_file:
            result = self.sources[loader_id]['loader'](statement_file)
            if result:
                self.load_completed.emit()
            else:
                self.load_failed.emit()

    def loadQuikHtml(self, filename):
        return Quik(filename).load()

    def loadIBFlex(self, filename):
        return IBKR(self, filename).load()

    def loadUralsibCapital(self, filename):
        return UralsibCapital(self, filename).load()

    def loadKITFinance(self, filename):
        return KITFinance(self, filename).load()

    def loadIBActivityStatement(self, filename):
        if QMessageBox().warning(None,
                                 g_tr('StatementLoader', "Confirmation"),
                                 g_tr('StatementLoader',
                                      "This is an obsolete routine for specific cases of old reports import.\n"
                                      "Use it with extra care if you understand what you are doing.\n"
                                      "Otherwise please use 'Interactive Brokers XML' import.\n"
                                      "Continue?"),
                                 QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
            return False
        return IBKR_obsolete(filename).load()

    # Checks if report is after last transaction recorded for account.
    # Otherwise asks for confirmation and returns False if import is cancelled
    def checkStatementPeriod(self, account_number, start_date) -> bool:
        if start_date < account_last_date(account_number):
            if QMessageBox().warning(None,
                                     g_tr('StatementLoader', "Confirmation"),
                                     g_tr('StatementLoader',
                                          "Statement period starts before last recorded operation for the account. Continue import?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                return False
        return True

    # returns bank id assigned for the account or asks for assignment if field is empty
    def getAccountBank(self, account_id):
        bank_id = readSQL("SELECT organization_id FROM accounts WHERE id=:account_id",
                          [(":account_id", account_id)])
        if bank_id == '':
            raise RuntimeError("Broker isn't defined for Investment account")
        return bank_id

    def selectAccount(self, text, account_id, recent_account_id=0):
        dialog = SelectAccountDialog(text, account_id, recent_account=recent_account_id)
        if dialog.exec_() != QDialog.Accepted:
            return 0
        else:
            return dialog.account_id
