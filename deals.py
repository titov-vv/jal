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

        sheet = workbook.add_worksheet(name="Deals")

        query = QSqlQuery(self.db)
        query.prepare("SELECT * FROM deals_ext")
        assert query.exec_()
        row = 0
        count = query.record().count()
        while query.next():
            for i in range(count):
                sheet.write(row, i, query.value(i))
            row = row + 1

        workbook.close()