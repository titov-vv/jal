from enum import Enum, auto
from PySide2.QtWidgets import QFileDialog, QMessageBox
from PySide2.QtCore import Qt, QObject
from jal.widgets.helpers import g_tr
from jal.reports.helpers import XLSX
from jal.reports.income_spending_report import IncomeSpendingReport
from jal.reports.p_and_l_report import ProfitLossReportModel
from jal.reports.deals_report import DealsReportModel
from jal.reports.category_report import CategoryReportModel


#-----------------------------------------------------------------------------------------------------------------------
class ReportType(Enum):
    IncomeSpending = auto()
    ProfitLoss = auto()
    Deals = auto()
    ByCategory = auto()


#-----------------------------------------------------------------------------------------------------------------------
class Reports(QObject):
    def __init__(self, report_table_view, report_tree_view):
        super().__init__()

        self.table_view = report_table_view
        self.tree_view = report_tree_view
        self.model = None

    def runReport(self, report_type, begin=0, end=0, account_id=0, group_dates=0):
        if report_type == ReportType.IncomeSpending:
            self.model = IncomeSpendingReport(self.tree_view)
            self.tree_view.setModel(self.model)
            self.tree_view.setVisible(True)
            self.table_view.setVisible(False)
        elif report_type == ReportType.ProfitLoss:
            self.model = ProfitLossReportModel(self.table_view)
            self.table_view.setModel(self.model)
            self.tree_view.setVisible(False)
            self.table_view.setVisible(True)
        elif report_type == ReportType.Deals:
            self.model = DealsReportModel(self.table_view)
            self.table_view.setModel(self.model)
            self.tree_view.setVisible(False)
            self.table_view.setVisible(True)
        elif report_type == ReportType.ByCategory:
            self.model = CategoryReportModel(self.table_view)
            self.table_view.setModel(self.model)
            self.tree_view.setVisible(False)
            self.table_view.setVisible(True)
        else:
            assert False

        try:
            self.model.prepare(begin, end, account_id, group_dates)
        except ValueError as e:
            QMessageBox().warning(None, g_tr('Reports', "Report creation error"), str(e), QMessageBox.Ok)
            return
        self.model.configureView()

    def saveReport(self):
        filename, filter = QFileDialog.getSaveFileName(None, g_tr('Reports', "Save report to:"),
                                                       ".", g_tr('Reports', "Excel files (*.xlsx)"))
        if filename:
            if filter == g_tr('Reports', "Excel files (*.xlsx)") and filename[-5:] != '.xlsx':
                filename = filename + '.xlsx'
        else:
            return

        report = XLSX(filename)
        sheet = report.add_report_sheet(g_tr('Reports', "Report"))

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

