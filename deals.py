import datetime
import xlsxwriter
from PySide2.QtWidgets import QDialog, QFileDialog
from PySide2.QtCore import Property, Slot
from PySide2 import QtCore
from PySide2.QtSql import QSqlQuery
from UI.ui_deals_export_dlg import Ui_DealsExportDlg

class DealsExportDialog(QDialog, Ui_DealsExportDlg):
    def __init__(self, db):
        QDialog.__init__(self)
        self.setupUi(self)

        self.FileSelectBtn.setFixedWidth(self.FileSelectBtn.fontMetrics().width(" ... "))
        self.AccountWidget.init_DB(db)
        self.FileSelectBtn.pressed.connect(self.OnFileBtn)

        self.ToDate.setDate(QtCore.QDate.currentDate())

    @Slot()
    def OnFileBtn(self):
        filename = QFileDialog.getSaveFileName(self, self.tr("Save deals report to:"), ".", self.tr("Excel file (*.xlsx)"))
        if filename[0]:
            if filename[1] == self.tr("Excel file (*.xlsx)") and filename[0][-5:] != '.xlsx':
                self.Filename.setText(filename[0] + '.xlsx')
            else:
                self.Filename.setText(filename[0])

    def getFrom(self):
        return self.FromDate.dateTime().toSecsSinceEpoch()

    def getTo(self):
        return self.ToDate.dateTime().toSecsSinceEpoch()

    def getFilename(self):
        return self.Filename.text()

    def getAccount(self):
        return self.AccountWidget.account_id

    begin = Property(int, fget=getFrom)
    end = Property(int, fget=getTo)
    filename = Property(int, fget=getFilename)
    account = Property(int, fget=getAccount)

class Deals:
    def __init__(self, db):
        self.db = db

    def save2file(self, deals_file, account_id, begin, end):
        workbook = xlsxwriter.Workbook(filename=deals_file)

        title_cell = workbook.add_format({'bold': True,
                                          'text_wrap': True,
                                          'align': 'center',
                                          'valign': 'vcenter'})
        number_odd = workbook.add_format({'border': 1,
                                          'align': 'center',
                                          'valign': 'vcenter'})
        number_even = workbook.add_format({'border': 1,
                                           'align': 'center',
                                           'valign': 'vcenter',
                                           'bg_color': '#C0C0C0'})
        number2_odd = workbook.add_format({'num_format': '#,###,##0.00',
                                           'border': 1,
                                           'valign': 'vcenter'})
        number2_even = workbook.add_format({'num_format': '#,###,##0.00',
                                            'border': 1,
                                            'valign': 'vcenter',
                                            'bg_color': '#C0C0C0'})
        number4_odd = workbook.add_format({'num_format': '0.0000',
                                           'border': 1})
        number4_even = workbook.add_format({'num_format': '0.0000',
                                            'border': 1,
                                            'bg_color': '#C0C0C0'})
        text_odd = workbook.add_format({'border': 1,
                                        'valign': 'vcenter'})
        text_even = workbook.add_format({'border': 1,
                                         'valign': 'vcenter',
                                         'bg_color': '#C0C0C0'})
        formats = {'title': title_cell,
                   'text_odd': text_odd, 'text_even': text_even,
                   'number_odd': number_odd, 'number_even': number_even,
                   'number_2_odd': number2_odd, 'number_2_even': number2_even,
                   'number_4_odd': number4_odd, 'number_4_even': number4_even}

        sheet = workbook.add_worksheet(name="Deals")

        query = QSqlQuery(self.db)
        query.prepare("SELECT asset, open_timestamp, close_timestamp, open_price, close_price, "
                      "qty, fee, profit, rel_profit FROM deals_ext "
                      "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end")
        query.bindValue(":account_id", account_id)
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        assert query.exec_()

        sheet.merge_range(0, 0, 1, 0, "Asset", formats['title'])
        sheet.set_column(0, 0, 15)
        sheet.merge_range(0, 1, 0, 2, "Date", formats['title'])
        sheet.write(1, 1, "Open", formats['title'])
        sheet.write(1, 2, "Close", formats['title'])
        sheet.set_column(1, 2, 20)
        sheet.merge_range(0, 3, 0, 4, "Price", formats['title'])
        sheet.write(1, 3, "Open", formats['title'])
        sheet.write(1, 4, "Close", formats['title'])
        sheet.merge_range(0, 5, 1, 5, "Qty", formats['title'])
        sheet.merge_range(0, 6, 1, 6, "Fee", formats['title'])
        sheet.merge_range(0, 7, 1, 7, "Profit / Loss", formats['title'])
        sheet.set_column(3, 7, 10)
        sheet.merge_range(0, 8, 1, 8, "Profit / Loss, %", formats['title'])
        sheet.set_column(8, 8, 8)
        row = 2
        while query.next():
            if row % 2:
                even_odd = '_odd'
            else:
                even_odd = '_even'
            sheet.write(row, 0, query.value('asset'), formats['text' + even_odd])
            sheet.write(row, 1,
                        datetime.datetime.fromtimestamp(query.value("open_timestamp")).strftime('%d.%m.%Y %H:%M:%S'),
                        formats['text' + even_odd])
            sheet.write(row, 2,
                        datetime.datetime.fromtimestamp(query.value("close_timestamp")).strftime('%d.%m.%Y %H:%M:%S'),
                        formats['text' + even_odd])
            sheet.write(row, 3, float(query.value('open_price')), formats['number_4' + even_odd])
            sheet.write(row, 4, float(query.value('close_price')), formats['number_4' + even_odd])
            sheet.write(row, 5, float(query.value('qty')), formats['number' + even_odd])
            sheet.write(row, 6, float(query.value('fee')), formats['number_4' + even_odd])
            sheet.write(row, 7, float(query.value('profit')), formats['number_2' + even_odd])
            sheet.write(row, 8, float(query.value('rel_profit')), formats['number_2' + even_odd])
            row = row + 1

        workbook.close()