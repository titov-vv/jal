import logging

from PySide2.QtCore import QObject, Signal, Slot
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QDialog, QFileDialog, QMessageBox
from jal.db.helpers import db_connection, executeSQL, readSQL, account_last_date

from jal.widgets.helpers import g_tr
from jal.constants import PredefinedAsset
from jal.ui.ui_add_asset_dlg import Ui_AddAssetDialog
from jal.ui.ui_select_account_dlg import Ui_SelectAccountDlg
from jal.db.update import JalDB
from jal.data_import.statement_quik import Quik
from jal.data_import.statement_ibkr import IBKR
from jal.data_import.statement_uralsib import UralsibCapital
from jal.data_import.statement_kit import KITFinance


# -----------------------------------------------------------------------------------------------------------------------
class AddAssetDialog(QDialog, Ui_AddAssetDialog):
    def __init__(self, parent, symbol, isin='', name=''):
        QDialog.__init__(self)
        self.setupUi(self)
        self.asset_id = None

        self.SymbolEdit.setText(symbol)
        self.isinEdit.setText(isin)
        self.NameEdit.setText(name)

        self.type_model = QSqlTableModel(db=db_connection())
        self.type_model.setTable('asset_types')
        self.type_model.select()
        self.TypeCombo.setModel(self.type_model)
        self.TypeCombo.setModelColumn(1)

        self.data_src_model = QSqlTableModel(db=db_connection())
        self.data_src_model.setTable('data_sources')
        self.data_src_model.select()
        self.DataSrcCombo.setModel(self.data_src_model)
        self.DataSrcCombo.setModelColumn(1)

        # center dialog with respect to parent window
        x = parent.x() + parent.width() / 2 - self.width() / 2
        y = parent.y() + parent.height() / 2 - self.height() / 2
        self.setGeometry(x, y, self.width(), self.height())

    def accept(self):
        self.asset_id = JalDB().add_asset(self.SymbolEdit.text(), self.NameEdit.text(),
                                          self.type_model.record(self.TypeCombo.currentIndex()).value("id"),
                                          self.isinEdit.text(),
                                          self.data_src_model.record(self.DataSrcCombo.currentIndex()).value("id"))
        super().accept()


# -----------------------------------------------------------------------------------------------------------------------
class SelectAccountDialog(QDialog, Ui_SelectAccountDlg):
    def __init__(self, parent, description, current_account, recent_account=None):
        QDialog.__init__(self)
        self.setupUi(self)
        self.account_id = recent_account
        self.current_account = current_account

        self.DescriptionLbl.setText(description)
        if self.account_id:
            self.AccountWidget.selected_id = self.account_id

        # center dialog with respect to parent window
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

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
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
        return Quik(self, filename).load()

    def loadIBFlex(self, filename):
        return IBKR(self, filename).load()

    def loadUralsibCapital(self, filename):
        return UralsibCapital(self, filename).load()

    def loadKITFinance(self, filename):
        return KITFinance(self, filename).load()

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

    # Searches for account_id by account number and optional currency
    # Returns: account_id or None if no account was found
    def findAccountID(self, accountNumber, accountCurrency=''):
        if accountCurrency:
            account_id = readSQL("SELECT a.id FROM accounts AS a "
                                 "LEFT JOIN assets AS c ON c.id=a.currency_id "
                                 "WHERE a.number=:account_number AND c.name=:currency_name",
                                 [(":account_number", accountNumber), (":currency_name", accountCurrency)])
        else:
            account_id = readSQL("SELECT a.id FROM accounts AS a "
                                 "LEFT JOIN assets AS c ON c.id=a.currency_id "
                                 "WHERE a.number=:account_number", [(":account_number", accountNumber)])
        if account_id is None:
            logging.error(g_tr('StatementLoader', "Account not found: ") + f"{accountNumber} ({accountCurrency})")
        return account_id

    # Searches for asset_id in database and returns its ID
    # 1. if ISIN is give tries to find by ISIN.
    # 2. If found by ISIN - checks symbol and updates it if function is called with another symbol
    # 3. If not found by ISIN or ISIN is not given - tries to find by symbol only
    # 4. If asset is not found - shows dialog for new asset creation.
    # Returns: asset_id or None if new asset creation failed
    def findAssetID(self, symbol, isin='', name='', reg_code='', dialog_new=True):   #TODO this function became too complex -> move to JalDB() class and simplify
        if isin:
            asset_id = readSQL("SELECT id FROM assets WHERE isin=:isin", [(":isin", isin)])
            if asset_id is not None:
                db_symbol = readSQL("SELECT name FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
                if (symbol != '') and (db_symbol != symbol):
                    _ = executeSQL("UPDATE assets SET name=:symbol WHERE id=:asset_id",
                                   [(":symbol", symbol), (":asset_id", asset_id)])
                    # Show warning if symbol was changed not due known bankruptcy or new issue pattern
                    if (db_symbol != symbol + 'D') and (db_symbol + 'D' != symbol) \
                            and (db_symbol != symbol + 'Q') and (db_symbol + 'Q' != symbol):
                        logging.warning(
                            g_tr('StatementLoader', "Symbol updated for ISIN ") + f"{isin}: {db_symbol} -> {symbol}")
                return asset_id
        if reg_code:
            asset_id = readSQL("SELECT asset_id FROM asset_reg_id WHERE reg_code=:reg_code", [(":reg_code", reg_code)])
            return asset_id
        asset_id = readSQL("SELECT id FROM assets WHERE name=:symbol", [(":symbol", symbol)])
        if asset_id is not None:
            # Check why symbol was not found by ISIN
            asset_type = readSQL("SELECT type_id FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
            if (asset_type == PredefinedAsset.Money) \
                    or (asset_type == PredefinedAsset.Commodity) \
                    or (asset_type == PredefinedAsset.Derivative):
                return asset_id  # It is ok not to have ISIN
            db_isin = readSQL("SELECT isin FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
            if db_isin == '':  # Update ISIN if it was absent in DB
                _ = executeSQL("UPDATE assets SET isin=:isin WHERE id=:asset_id",
                               [(":isin", isin), (":asset_id", asset_id)])
                logging.info(g_tr('StatementLoader', "ISIN updated for ") + f"{symbol}: {isin}")
            else:
                logging.warning(g_tr('StatementLoader', "ISIN mismatch for ") + f"{symbol}: {isin} != {db_isin}")
        elif dialog_new:
            dialog = AddAssetDialog(self.parent, symbol, isin=isin, name=name)
            dialog.exec_()
            asset_id = dialog.asset_id
        return asset_id

    # returns bank id assigned for the account or asks for assignment if field is empty
    def getAccountBank(self, account_id):
        bank_id = readSQL("SELECT organization_id FROM accounts WHERE id=:account_id",
                          [(":account_id", account_id)])
        if bank_id == '':
            raise RuntimeError("Broker isn't defined for Investment account")
        return bank_id

    def selectAccount(self, text, account_id, recent_account_id=0):
        dialog = SelectAccountDialog(self.parent, text, account_id, recent_account=recent_account_id)
        if dialog.exec_() != QDialog.Accepted:
            return 0
        else:
            return dialog.account_id
