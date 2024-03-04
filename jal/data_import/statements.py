import logging
import importlib
import os
from collections import defaultdict

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog
from jal.constants import Setup
from jal.db.settings import JalSettings, FolderFor
from jal.data_import.statement import Statement_ImportError, Statement_Capabilities


# ----------------------------------------------------------------------------------------------------------------------
class Statements(QObject):
    load_completed = Signal(int, defaultdict)
    load_failed = Signal()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.items = []
        self.loadStatementsList()

    def loadStatementsList(self):
        statements_folder = JalSettings.path(JalSettings.PATH_APP) + Setup.IMPORT_PATH + os.sep + Setup.STATEMENT_PATH
        statement_modules = [filename[:-3] for filename in os.listdir(statements_folder) if filename.endswith(".py")]
        for module_name in statement_modules:
            logging.debug(f"Trying to load statement module: {module_name}")
            try:
                module = importlib.import_module(f"jal.data_import.broker_statements.{module_name}")
            except ImportError:
                logging.error(self.tr("Statement module can't be imported: ") + module_name)
                continue
            try:
                statement_class_name = getattr(module, "JAL_STATEMENT_CLASS")
            except AttributeError:
                continue
            try:
                class_instance = getattr(module, statement_class_name)
            except AttributeError:
                logging.error(self.tr("Statement class can't be loaded: ") + statement_class_name)
                continue
            statement = class_instance()
            self.items.append({
                'name': statement.name,
                'module': module,
                'loader_class': statement_class_name,
                'icon': statement.icon_name,
                'filename_filter': statement.filename_filter
            })
            logging.debug(f"Class '{statement_class_name}' providing '{statement.name}' statement has been loaded")
        self.items = sorted(self.items, key=lambda item: item['name'])

    # method is called directly from menu, so it contains QAction that was triggered
    def load(self, action):
        statement_loader = self.items[action.data()]
        folder = JalSettings().getRecentFolder(FolderFor.Statement, '.')
        statement_files, active_filter = QFileDialog.getOpenFileNames(None, self.tr("Select statement files to import"),
                                                                      folder, statement_loader['filename_filter'])
        if not statement_files:
            return
        JalSettings().setRecentFolder(FolderFor.Statement, statement_files[0])

        module = statement_loader['module']
        class_instance = getattr(module, statement_loader['loader_class'])
        if len(statement_files) > 1:
            if not Statement_Capabilities.MULTIPLE_LOAD in class_instance.capabilities():
                logging.warning(statement_loader['name'] +
                                self.tr(" - module doesn't support multiple statements load."))
                return
            statement_files = class_instance.order_statements(statement_files)
        if not statement_files:
            return
        for statement_file in statement_files:
            statement = class_instance()
            try:
                statement.load(statement_file)
                logging.info(self.tr("Statement file loaded successfully"))
                statement.validate_format()
                statement.match_db_ids()
                logging.info(self.tr("Importing statement into database..."))
                totals = statement.import_into_db()
                logging.info(self.tr("Statement import completed successfully"))
            except Statement_ImportError as e:
                logging.error(self.tr("Import failed: ") + str(e))
                self.load_failed.emit()
                return
        self.load_completed.emit(statement.period()[1], totals)
