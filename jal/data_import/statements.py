import importlib
from PySide2.QtCore import QObject, Signal
from PySide2.QtWidgets import QFileDialog, QMessageBox
from jal.widgets.helpers import g_tr
from jal.data_import.statement_quik import Quik
from jal.data_import.statement_ibkr_old import IBKR_obsolete


# -----------------------------------------------------------------------------------------------------------------------
class StatementLoader(QObject):
    load_completed = Signal()
    load_failed = Signal()

    def __init__(self):
        super().__init__()
        self.sources = [
            # 'name' - Title string to displain in main menu
            # 'icon' - Optional icon to display in main menu
            # 'filter' - file filter to apply in QFileDialog for file selection
            # 'module' - module name inside 'jal/data_import' that contains descendant of Statement class for import
            # 'loader_class' - class name that is derived from Statement class
            # 'loader' - method to load some obsolete statements
            {
                'name': g_tr('StatementLoader', "Quik HTML"),
                'filter': "Quik HTML-report (*.htm)",
                'loader': self.loadQuikHtml,
                'icon': "quik.ico"
            },
            {
                'name': g_tr('StatementLoader', "Interactive Brokers XML"),
                'filter': "IBKR flex-query (*.xml)",
                'icon': "ibkr.png",
                'module': "statement_ibkr",
                'loader_class': "StatementIBKR"
            },
            {
                'name': g_tr('StatementLoader', "Uralsib Broker"),
                'filter': "Uralsib statement (*.zip)",
                'icon': "uralsib.ico",
                'module': "statement_uralsib",
                'loader_class': "StatementUKFU"
            },
            {
                'name': g_tr('StatementLoader', "KIT Finance"),
                'filter': "KIT Finance statement (*.xlsx)",
                'icon': 'kit.png',
                'module': "statement_kit",
                'loader_class': "StatementKIT"
            },
            {
                'name': g_tr('StatementLoader', "PSB Broker"),
                'filter': "PSB broker statement (*.xlsx *.xls)",
                'icon': 'psb.ico',
                'module': "statement_psb",
                'loader_class': "StatementPSB"
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
            if 'loader' in self.sources[loader_id]:
                result = self.sources[loader_id]['loader'](statement_file)  # TODO: This branch is for obsolete methods
                if result:
                    self.load_completed.emit()
                else:
                    self.load_failed.emit()

            module = importlib.import_module(f"jal.data_import.{self.sources[loader_id]['module']}")
            class_instance = getattr(module, self.sources[loader_id]['loader_class'])
            statement = class_instance()
            statement.load(statement_file)
            statement.match_db_ids(verbal=False)
            statement.import_into_db()
            self.load_completed.emit()

    def loadQuikHtml(self, filename):
        return Quik(filename).load()

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
