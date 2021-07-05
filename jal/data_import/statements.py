from PySide2.QtCore import QObject, Signal
from PySide2.QtWidgets import QFileDialog, QMessageBox

from jal.widgets.helpers import g_tr
from jal.data_import.statement_quik import Quik
from jal.data_import.statement_ibkr import StatementIBKR
from jal.data_import.statement_ibkr_old import IBKR_obsolete
from jal.data_import.statement_uralsib import StatementUKFU
from jal.data_import.statement_kit import StatementKIT
from jal.data_import.statement_psb import StatementPSB


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
                'name': g_tr('StatementLoader', "PSB Broker"),
                'filter': "PSB broker statement (*.xlsx *.xls)",
                'loader': self.loadPSB,
                'icon': 'psb.ico'
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
        statement = StatementIBKR()
        statement.load(filename)
        statement.match_db_ids(verbal=False)
        statement.import_into_db()
        return True

    def loadUralsibCapital(self, filename):
        statement = StatementUKFU()
        statement.load(filename)
        statement.match_db_ids(verbal=False)
        statement.import_into_db()
        return True

    def loadKITFinance(self, filename):
        statement = StatementKIT()
        statement.load(filename)
        statement.match_db_ids(verbal=False)
        statement.import_into_db()
        return True

    def loadPSB(self, filename):
        statement = StatementPSB()
        statement.load(filename)
        statement.match_db_ids(verbal=False)
        statement.import_into_db()
        return True

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
