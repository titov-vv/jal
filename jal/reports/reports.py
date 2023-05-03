import os
import logging
import importlib

from PySide6.QtWidgets import QFileDialog
from PySide6.QtCore import QObject
from jal.constants import Setup
from jal.db.helpers import get_app_path
from jal.db.settings import JalSettings, FolderFor
from jal.data_export.xlsx import XLSX


class Reports(QObject):
    def __init__(self, parent, MdiArea):
        super().__init__()
        self.parent = parent
        self._mdi = MdiArea

        self.items = []
        self.loadReportsList()

    def mdi_area(self):
        return self._mdi

    def loadReportsList(self):
        reports_folder = get_app_path() + Setup.REPORT_PATH
        report_modules = [filename[:-3] for filename in os.listdir(reports_folder) if filename.endswith(".py")]
        for module_name in report_modules:
            logging.debug(f"Trying to load report module: {module_name}")
            module = importlib.import_module(f"jal.reports.{module_name}")
            try:
                report_class_name = getattr(module, "JAL_REPORT_CLASS")
            except AttributeError:
                continue
            try:
                class_instance = getattr(module, report_class_name)
            except AttributeError:
                logging.error(self.tr("Report class can't be loaded: ") + report_class_name)
                continue
            report = class_instance()
            group = report.group if hasattr(report, "group") else ''
            self.items.append({'group': group, 'name': report.name,
                               'module': module, 'window_class': report.window_class})
            logging.debug(f"Report class '{report_class_name}' providing '{report.name}' report has been loaded")
        self.items = sorted(self.items, key=lambda item: item['name'])

    # method is called directly from menu, so it contains QAction that was triggered
    def show(self, action):
        report_loader = self.items[action.data()]
        module = report_loader['module']
        class_instance = getattr(module, report_loader['window_class'])
        report = class_instance(self)
        self._mdi.addSubWindow(report, maximized=True)

    def show_report(self, window_class, settings, maximized=False):
        report = [x for x in self.items if x['window_class'] == window_class]
        if len(report) != 1:
            logging.warning(self.tr("Report not found for window class: ") + window_class)
            return
        report_loader = report[0]
        module = report_loader['module']
        class_instance = getattr(module, report_loader['window_class'])
        report = class_instance(self, settings)
        self._mdi.addSubWindow(report, maximized=maximized)

    # Save report content from the model to xls-file chosen by the user
    def save_report(self, name, model):
        folder = JalSettings().getRecentFolder(FolderFor.Report, '.')
        filename, filter = QFileDialog.getSaveFileName(self._mdi, self.tr("Save report to:"),
                                                       folder, self.tr("Excel files (*.xlsx)"))
        if filename:
            if filter == self.tr("Excel files (*.xlsx)") and filename[-5:] != '.xlsx':
                filename = filename + '.xlsx'
        else:
            return
        JalSettings().setRecentFolder(FolderFor.Report, filename)
        report = XLSX(filename)
        report.output_model(name, model)
        report.save()
        logging.info(self.tr("Report was saved to file ") + f"'{filename}'")
