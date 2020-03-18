import datetime
import xlsxwriter
from constants import *
from PySide2.QtWidgets import QDialog, QFileDialog
from PySide2.QtCore import Property, Slot
from PySide2 import QtCore
from PySide2.QtSql import QSqlQuery
from UI.ui_deals_export_dlg import Ui_DealsExportDlg

# TODO Combine all reports into one function call and write different sheets in one file
# TODO optimize with lists of fields

class ReportParamsDialog(QDialog, Ui_DealsExportDlg):
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

    def getGroupByDates(self):
        if self.DateGroupCheckBox.isChecked():
            return True
        else:
            return False

    def getFilename(self):
        return self.Filename.text()

    def getAccount(self):
        return self.AccountWidget.account_id

    begin = Property(int, fget=getFrom)
    end = Property(int, fget=getTo)
    group_dates = Property(bool, fget=getGroupByDates)
    filename = Property(int, fget=getFilename)
    account = Property(int, fget=getAccount)

class Reports:
    def __init__(self, db, report_filename):
        self.db = db
        self. workbook = xlsxwriter.Workbook(filename=report_filename)

        title_cell = self.workbook.add_format({'bold': True,
                                               'text_wrap': True,
                                               'align': 'center',
                                               'valign': 'vcenter'})
        number_odd = self.workbook.add_format({'border': 1,
                                               'align': 'center',
                                               'valign': 'vcenter'})
        number_even = self.workbook.add_format({'border': 1,
                                                'align': 'center',
                                                'valign': 'vcenter',
                                                'bg_color': '#C0C0C0'})
        number2_odd = self.workbook.add_format({'num_format': '#,###,##0.00',
                                                'border': 1,
                                                'valign': 'vcenter'})
        number2_even = self.workbook.add_format({'num_format': '#,###,##0.00',
                                                 'border': 1,
                                                 'valign': 'vcenter',
                                                 'bg_color': '#C0C0C0'})
        number4_odd = self.workbook.add_format({'num_format': '0.0000',
                                                'border': 1})
        number4_even = self.workbook.add_format({'num_format': '0.0000',
                                                 'border': 1,
                                                 'bg_color': '#C0C0C0'})
        text_odd = self.workbook.add_format({'border': 1,
                                             'valign': 'vcenter'})
        text_even = self.workbook.add_format({'border': 1,
                                              'valign': 'vcenter',
                                              'bg_color': '#C0C0C0'})
        self.formats = {'title': title_cell,
                        'text_odd': text_odd, 'text_even': text_even,
                        'number_odd': number_odd, 'number_even': number_even,
                        'number_2_odd': number2_odd, 'number_2_even': number2_even,
                        'number_4_odd': number4_odd, 'number_4_even': number4_even}

    def save_deals(self, account_id, begin, end, group_dates):
        sheet = self.workbook.add_worksheet(name="Deals")

        query = QSqlQuery(self.db)
        if group_dates:
            query.prepare("SELECT asset, "
                          "strftime('%s', datetime(open_timestamp, 'unixepoch', 'start of day')) as open_timestamp, "
                          "strftime('%s', datetime(close_timestamp, 'unixepoch', 'start of day')) as close_timestamp, "
                          "SUM(open_price*qty)/SUM(qty) as open_price, SUM(close_price*qty)/SUM(qty) AS close_price, "
                          "SUM(qty) as qty, SUM(fee) as fee, SUM(profit) as profit, "
                          "coalesce(100*SUM(qty*(close_price-open_price)-fee)/SUM(qty*open_price), 0) AS rel_profit "
                          "FROM deals_ext "
                          "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end "
                          "GROUP BY asset, open_timestamp, close_timestamp "
                          "ORDER BY close_timestamp, open_timestamp")
        else:
            query.prepare("SELECT asset, open_timestamp, close_timestamp, open_price, close_price, "
                          "qty, fee, profit, rel_profit FROM deals_ext "
                          "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end")
        query.bindValue(":account_id", account_id)
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        assert query.exec_()

        sheet.merge_range(0, 0, 1, 0, "Asset", self.formats['title'])
        sheet.set_column(0, 0, 15)
        sheet.merge_range(0, 1, 0, 2, "Date", self.formats['title'])
        sheet.write(1, 1, "Open", self.formats['title'])
        sheet.write(1, 2, "Close", self.formats['title'])
        sheet.set_column(1, 2, 20)
        sheet.merge_range(0, 3, 0, 4, "Price", self.formats['title'])
        sheet.write(1, 3, "Open", self.formats['title'])
        sheet.write(1, 4, "Close", self.formats['title'])
        sheet.merge_range(0, 5, 1, 5, "Qty", self.formats['title'])
        sheet.merge_range(0, 6, 1, 6, "Fee", self.formats['title'])
        sheet.merge_range(0, 7, 1, 7, "Profit / Loss", self.formats['title'])
        sheet.set_column(3, 7, 10)
        sheet.merge_range(0, 8, 1, 8, "Profit / Loss, %", self.formats['title'])
        sheet.set_column(8, 8, 8)
        row = 2
        while query.next():
            if row % 2:
                even_odd = '_odd'
            else:
                even_odd = '_even'
            sheet.write(row, 0, query.value('asset'), self.formats['text' + even_odd])
            open = int(query.value("open_timestamp"))
            close = int(query.value("close_timestamp"))
            if group_dates:
                sheet.write(row, 1, datetime.datetime.fromtimestamp(open).strftime('%d.%m.%Y'),
                            self.formats['text' + even_odd])
                sheet.write(row, 2, datetime.datetime.fromtimestamp(close).strftime('%d.%m.%Y'),
                            self.formats['text' + even_odd])
            else:
                sheet.write(row, 1, datetime.datetime.fromtimestamp(open).strftime('%d.%m.%Y %H:%M:%S'),
                            self.formats['text' + even_odd])
                sheet.write(row, 2, datetime.datetime.fromtimestamp(close).strftime('%d.%m.%Y %H:%M:%S'),
                            self.formats['text' + even_odd])
            sheet.write(row, 3, float(query.value('open_price')), self.formats['number_4' + even_odd])
            sheet.write(row, 4, float(query.value('close_price')), self.formats['number_4' + even_odd])
            sheet.write(row, 5, float(query.value('qty')), self.formats['number' + even_odd])
            sheet.write(row, 6, float(query.value('fee')), self.formats['number_4' + even_odd])
            sheet.write(row, 7, float(query.value('profit')), self.formats['number_2' + even_odd])
            sheet.write(row, 8, float(query.value('rel_profit')), self.formats['number_2' + even_odd])
            row = row + 1

        self.workbook.close()

    def save_profit_loss(self, account_id, begin, end):
        sheet = self.workbook.add_worksheet(name="P&L")

        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM t_months")
        query.prepare("INSERT INTO t_months(asset_id, month, last_timestamp) "
                      "SELECT DISTINCT(l.asset_id) AS asset_id, m.m_start, MAX(q.timestamp) AS last_timestamp "
                      "FROM ledger AS l "
                      "LEFT JOIN "
                      "(WITH RECURSIVE months(m_start) AS "
                      "( "
                      "  VALUES(CAST(strftime('%s', date(:begin, 'unixepoch', 'start of month')) AS INTEGER)) "
                      "  UNION ALL "
                      "  SELECT CAST(strftime('%s', date(m_start, 'unixepoch', '+1 month')) AS INTEGER) "
                      "  FROM months "
                      "  WHERE m_start < :end "
                      ") "
                      "SELECT m_start FROM months) AS m "
                      "LEFT JOIN quotes AS q ON q.timestamp<=m.m_start AND q.asset_id=l.asset_id "
                      "WHERE l.timestamp>=:begin AND l.timestamp<=:end AND l.account_id=:account_id "
                      "GROUP BY m.m_start, l.asset_id "
                      "ORDER BY m.m_start, l.asset_id")
        query.bindValue(":account_id", account_id)
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        assert query.exec_()

        query.prepare("SELECT DISTINCT(m.month) AS period, coalesce(t.transfer, 0) AS transfer, coalesce(a.assets, 0) AS assets, "
                      "coalesce(p.result, 0) AS result, coalesce(o.profit, 0) AS profit, coalesce(d.dividend, 0) AS dividend, "
                      "coalesce(f.tax_fee, 0) AS tax_fee "
                      "FROM t_months AS m "
                      "LEFT JOIN ( "
                      "  SELECT mt.month, SUM(-l.amount) AS transfer "
                      "  FROM t_months AS mt "
                      "  LEFT JOIN ledger AS l ON mt.month = CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) AND mt.asset_id=l.asset_id "
                      "  WHERE l.book_account=:book_transfers AND l.account_id=:account_id GROUP BY mt.month "
                      ") AS t ON t.month = m.month "
                      "LEFT JOIN ( "
                      "  SELECT ma.month, SUM(l.amount*q.quote) AS assets "
                      "  FROM t_months AS ma "
                      "  LEFT JOIN ledger AS l ON l.timestamp<=ma.month AND l.asset_id=ma.asset_id "
                      "  LEFT JOIN quotes AS q ON ma.last_timestamp=q.timestamp AND ma.asset_id=q.asset_id "
                      "  WHERE l.account_id = 76 AND (l.book_account=:book_money OR l.book_account=:book_assets) "
                      "  GROUP BY ma.month "
                      ") AS a ON a.month = m.month "
                      "LEFT JOIN ( "
                      "  SELECT CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) AS month, SUM(-l.amount) as result "
                      "  FROM ledger AS l  "
                      "  WHERE (l.book_account=:book_costs OR l.book_account=:book_incomes) AND l.account_id=:account_id "
                      "  GROUP BY month "
                      ") AS p ON p.month = m.month "
                      "LEFT JOIN ( "
                      "  SELECT CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) AS month, SUM(-l.amount) as profit "
                      "  FROM ledger AS l "
                      "  WHERE (l.book_account=:book_costs OR l.book_account=:book_incomes) AND category_id=9 AND l.account_id=:account_id "
                      "  GROUP BY month "
                      ") AS o ON o.month = m.month "
                      "LEFT JOIN ( "
                      "  SELECT CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) AS month, SUM(-l.amount) as dividend "
                      "  FROM ledger AS l "
                      "  WHERE (l.book_account=:book_costs OR l.book_account=:book_incomes) AND (l.category_id=7 OR l.category_id=8) AND l.account_id=:account_id "
                      "  GROUP BY month "
                      ") AS d ON d.month = m.month "
                      "LEFT JOIN ( "
                      "  SELECT CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) AS month, SUM(-l.amount) as tax_fee "
                      "  FROM ledger AS l "
                      "  WHERE l.book_account=:book_costs AND l.category_id<>7 AND l.category_id<>8 AND l.account_id=:account_id "
                      "  GROUP BY month "
                      ") AS f ON f.month = m.month")
        query.bindValue(":account_id", account_id)
        query.bindValue(":book_costs", BOOK_ACCOUNT_COSTS)
        query.bindValue(":book_incomes", BOOK_ACCOUNT_INCOMES)
        query.bindValue(":book_money", BOOK_ACCOUNT_MONEY)
        query.bindValue(":book_assets", BOOK_ACCOUNT_ASSETS)
        query.bindValue(":book_transfers", BOOK_ACCOUNT_TRANSFERS)
        assert query.exec_()

        sheet.write(0, 0, "Period", self.formats['title'])
        sheet.write(0, 1, "In / Out", self.formats['title'])
        sheet.write(0, 2, "Assets value", self.formats['title'])
        sheet.write(0, 3, "Total result", self.formats['title'])
        sheet.write(0, 4, "Profit / Loss", self.formats['title'])
        sheet.write(0, 5, "Dividends, Coupons, Interest", self.formats['title'])
        sheet.write(0, 6, "Taxes & Fees", self.formats['title'])
        sheet.set_column(0, 6, 15)
        row = 1
        while query.next():
            if row % 2:
                even_odd = '_odd'
            else:
                even_odd = '_even'
            period = int(query.value("period"))
            sheet.write(row, 0, datetime.datetime.fromtimestamp(period).strftime('%Y %B'),
                        self.formats['text' + even_odd])
            sheet.write(row, 1, float(query.value("transfer")), self.formats['number_2' + even_odd])
            sheet.write(row, 2, float(query.value('assets')), self.formats['number_2' + even_odd])
            sheet.write(row, 3, float(query.value('result')), self.formats['number_2' + even_odd])
            sheet.write(row, 4, float(query.value('profit')), self.formats['number_2' + even_odd])
            sheet.write(row, 5, float(query.value('dividend')), self.formats['number_2' + even_odd])
            sheet.write(row, 6, float(query.value('tax_fee')), self.formats['number_2' + even_odd])
            row = row + 1

        self.workbook.close()

    def save_income_sending(self, begin, end):
        sheet = self.workbook.add_worksheet(name="Income & Spending")

        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM t_months")

        query.prepare("INSERT INTO t_months (month, asset_id, last_timestamp) "
                      "SELECT strftime('%s', datetime(timestamp, 'unixepoch', 'start of month') ) AS month, asset_id, MAX(timestamp) AS last_timestamp "
                      "FROM quotes AS q "
                      "LEFT JOIN assets AS a ON q.asset_id=a.id "
                      "WHERE a.type_id=:asset_money "
                      "GROUP BY month, asset_id")
        query.bindValue(":asset_money", ASSET_TYPE_MONEY)
        assert query.exec_()

        query.prepare("SELECT strftime('%s', datetime(t.timestamp, 'unixepoch', 'start of month') ) AS month_timestamp, "
                      "datetime(t.timestamp, 'unixepoch', 'start of month') AS month_date, a.name AS account, "
                      "c.name AS currency, coalesce(q.quote, 1) AS rate, s.name AS category, sum(-t.amount) AS turnover "
                      "FROM ledger AS t "
                      "LEFT JOIN accounts AS a ON t.account_id = a.id "
                      "LEFT JOIN assets AS c ON t.asset_id = c.id "
                      "LEFT JOIN categories AS s ON t.category_id = s.id "
                      "LEFT JOIN t_months AS d ON month_timestamp = d.month AND t.asset_id = d.asset_id "
                      "LEFT JOIN quotes AS q ON d.last_timestamp = q.timestamp AND d.asset_id = q.asset_id "
                      "WHERE (t.book_account=:book_costs OR t.book_account=:book_incomes) "
                      "AND t.timestamp>=:begin AND t.timestamp<=:end "
                      "GROUP BY month_timestamp, t.account_id, t.asset_id, t.category_id "
                      "ORDER BY currency, month_timestamp, category")
        query.bindValue(":book_costs", BOOK_ACCOUNT_COSTS)
        query.bindValue(":book_incomes", BOOK_ACCOUNT_INCOMES)
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        assert query.exec_()

        sheet.write(0, 0, "Period", self.formats['title'])
        sheet.write(0, 1, "Account", self.formats['title'])
        sheet.write(0, 2, "Currency", self.formats['title'])
        sheet.write(0, 3, "Currency rate", self.formats['title'])
        sheet.write(0, 4, "Category", self.formats['title'])
        sheet.write(0, 5, "Turnover", self.formats['title'])
        sheet.set_column(0, 7, 15)
        row = 1
        while query.next():
            if row % 2:
                even_odd = '_odd'
            else:
                even_odd = '_even'
            period = int(query.value("month_timestamp"))
            sheet.write(row, 0, datetime.datetime.fromtimestamp(period).strftime('%Y %B'),
                        self.formats['text' + even_odd])
            sheet.write(row, 1, query.value("account"), self.formats['text' + even_odd])
            sheet.write(row, 2, query.value('currency'), self.formats['text' + even_odd])
            sheet.write(row, 3, float(query.value('rate')), self.formats['number_2' + even_odd])
            sheet.write(row, 4, query.value('category'), self.formats['text' + even_odd])
            sheet.write(row, 5, float(query.value('turnover')), self.formats['number_2' + even_odd])
            row = row + 1

        self.workbook.close()