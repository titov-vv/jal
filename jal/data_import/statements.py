import importlib
from PySide2.QtCore import QObject, Signal
from PySide2.QtWidgets import QFileDialog
from jal.widgets.helpers import g_tr
from jal.data_import.statement_quik import Quik


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
            }
        ]

    # method is called directly from menu so it contains QAction that was triggered
    def load(self, action):
        statement_loader = self.sources[action.data()]
        statement_file, active_filter = QFileDialog.getOpenFileName(None, g_tr('StatementLoader',
                                                                               "Select statement file to import"),
                                                                    ".", statement_loader['filter'])
        if not statement_file:
            return
        module = importlib.import_module(f"jal.data_import.{statement_loader['module']}")
        class_instance = getattr(module, statement_loader['loader_class'])
        statement = class_instance()
        statement.load(statement_file)
        statement.match_db_ids(verbal=False)
        statement.import_into_db()
        self.load_completed.emit()  # emit self.load_completed.emit()  if failed

    def loadQuikHtml(self, filename):
        return Quik(filename).load()
