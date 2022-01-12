import logging
import importlib

from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import Qt, QObject
from data_export.helpers import XLSX
from jal.reports.profit_loss import ProfitLossReportModel


class JalReports(QObject):
    def __init__(self, parent, MdiArea):
        super().__init__()
        self.parent = parent
        self.mdi = MdiArea
        self.items = [
            # 'name' - Title string to display in main menu
            # 'module' - module name inside 'jal/reports' that contains descendant of ReportWidget class
            # 'window_class' - class name that is derived from ReportWidget class
            {
                'name': self.tr("Holdings"),
                'module': 'holdings',
                'window_class': 'HoldingsReport'
            },
            {
                'name': self.tr("Income/Spending"),
                'module': 'income_spending',
                'window_class': 'IncomeSpendingReport'
            },
            {
                'name': self.tr("P&L by Account"),
                'module': 'profit_loss',
                'window_class': 'ProfitLossReport'
            },
            {
                'name': self.tr("Deals by Account"),
                'module': 'deals',
                'window_class': 'DealsReport'
            },
            {
                'name': self.tr("Operations by Category"),
                'module': 'category',
                'window_class': 'CategoryReport'
            },
            {
                'name': self.tr("Other"),
                'module': 'reports_widget',
                'window_class': 'ReportsWidget'
            }
        ]

    # method is called directly from menu, so it contains QAction that was triggered
    def show(self, action):
        report_loader = self.items[action.data()]
        try:
            module = importlib.import_module(f"jal.reports.{report_loader['module']}")
        except ModuleNotFoundError:
            logging.error(self.tr("Report module not found: ") + report_loader['module'])
            return
        class_instance = getattr(module, report_loader['window_class'])
        report = class_instance(self.mdi)
        self.mdi.addSubWindow(report, maximized=True)

#-----------------------------------------------------------------------------------------------------------------------
class Reports(QObject):
    def __init__(self, report_table_view):
        super().__init__()

        self.table_view = report_table_view
        self.model = None

    def runReport(self, report_type, begin=0, end=0, account_id=0, group_dates=0):
        pass

    def saveReport(self):
        filename, filter = QFileDialog.getSaveFileName(None, self.tr("Save report to:"),
                                                       ".", self.tr("Excel files (*.xlsx)"))
        if filename:
            if filter == self.tr("Excel files (*.xlsx)") and filename[-5:] != '.xlsx':
                filename = filename + '.xlsx'
        else:
            return

        report = XLSX(filename)
        sheet = report.add_report_sheet(self.tr("Report"))

        model = self.table_view.model()
        headers = {}
        for col in range(model.columnCount()):
            headers[col] = (model.headerData(col, Qt.Horizontal), report.formats.ColumnHeader())
        report.write_row(sheet, 0, headers)

        for row in range(model.rowCount()):
            data_row = {}
            for col in range(model.columnCount()):
                data_row[col] = (model.data(model.index(row, col)), report.formats.Text(row))
            report.write_row(sheet, row+1, data_row)

        report.save()
