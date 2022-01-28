import os
import logging
import importlib

from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import Qt, QObject
from jal.constants import Setup
from jal.db.helpers import get_app_path
from jal.data_export.xlsx import XLSX


class Reports(QObject):
    def __init__(self, parent, MdiArea):
        super().__init__()
        self.parent = parent
        self.mdi = MdiArea

        self.items = []
        self.loadReportsList()

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
            self.items.append({'name': report.name, 'module': module, 'window_class': report.window_class})
            logging.debug(f"Report class '{report_class_name}' providing '{report.name}' report has been loaded")
        self.items = sorted(self.items, key=lambda item: item['name'])

    # method is called directly from menu, so it contains QAction that was triggered
    def show(self, action):
        report_loader = self.items[action.data()]
        module = report_loader['module']
        class_instance = getattr(module, report_loader['window_class'])
        report = class_instance(self.mdi)
        self.mdi.addSubWindow(report, maximized=True)

    # FIXME This method is deprecated as now reports are independent and may not have QTableView member
    # The plan is to move this method into XLSX class itself with report data as an input
    # Probably reports should provide some kind of json intermediate output that will be formatted into a table
    def saveReport(self):
        filename, filter = QFileDialog.getSaveFileName(None, self.tr("Save report to:"),
                                                       ".", self.tr("Excel files (*.xlsx)"))
        if filename:
            if filter == self.tr("Excel files (*.xlsx)") and filename[-5:] != '.xlsx':
                filename = filename + '.xlsx'
        else:
            return

        report = XLSX(filename)
        # sheet = report.add_report_sheet(self.tr("Report"))
        #
        # model = self.table_view.model()
        # headers = {}
        # for col in range(model.columnCount()):
        #     headers[col] = (model.headerData(col, Qt.Horizontal), report.formats.ColumnHeader())
        # report.write_row(sheet, 0, headers)
        #
        # for row in range(model.rowCount()):
        #     data_row = {}
        #     for col in range(model.columnCount()):
        #         data_row[col] = (model.data(model.index(row, col)), report.formats.Text(row))
        #     report.write_row(sheet, row+1, data_row)

        report.save()
