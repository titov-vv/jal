import logging
import importlib
from collections import defaultdict

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog
from jal.data_import.statement_quik import Quik
from jal.data_import.statement import Statement_ImportError


# -----------------------------------------------------------------------------------------------------------------------
class StatementLoader(QObject):
    load_completed = Signal(int, defaultdict)
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
                'name': self.tr("Interactive Brokers XML"),
                'filter': "IBKR flex-query (*.xml)",
                'icon': "ibkr.png",
                'module': "statement_ibkr",
                'loader_class': "StatementIBKR"
            },
            {
                'name': self.tr("Uralsib Broker"),
                'filter': "Uralsib statement (*.zip)",
                'icon': "uralsib.ico",
                'module': "statement_uralsib",
                'loader_class': "StatementUKFU"
            },
            {
                'name': self.tr("KIT Finance"),
                'filter': "KIT Finance statement (*.xlsx)",
                'icon': 'kit.png',
                'module': "statement_kit",
                'loader_class': "StatementKIT"
            },
            {
                'name': self.tr("PSB Broker"),
                'filter': "PSB broker statement (*.xlsx *.xls)",
                'icon': 'psb.ico',
                'module': "statement_psb",
                'loader_class': "StatementPSB"
            },
            {
                'name': self.tr("Open Broker"),
                'filter': "Open Broker statement (*.xml)",
                'icon': 'openbroker.ico',
                'module': "statement_openbroker",
                'loader_class': "StatementOpenBroker"
            }
        ]

    # method is called directly from menu so it contains QAction that was triggered
    def load(self, action):
        statement_loader = self.sources[action.data()]
        statement_file, active_filter = QFileDialog.getOpenFileName(None, self.tr("Select statement file to import"),
                                                                    ".", statement_loader['filter'])
        if not statement_file:
            return
        try:
            module = importlib.import_module(f"jal.data_import.{statement_loader['module']}")
        except ModuleNotFoundError:
            logging.error(self.tr("Statement loader module not found: ") + statement_loader['module'])
            return
        class_instance = getattr(module, statement_loader['loader_class'])
        statement = class_instance()
        try:
            statement.load(statement_file)
            statement.validate_format()
            statement.match_db_ids(verbal=False)
            totals = statement.import_into_db()
        except Statement_ImportError as e:
            logging.error(self.tr("Import failed: ") + str(e))
            self.load_failed.emit()
            return
        self.load_completed.emit(statement.period()[1], totals)

    def loadQuikHtml(self, filename):
        return Quik(filename).load()
