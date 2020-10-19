import time
from datetime import datetime
import xlsxwriter
import logging
from reports.helpers import xslxFormat, xlsxWriteRow
from CustomUI.helpers import g_tr
from DB.helpers import executeSQL, readSQLrecord
from PySide2.QtWidgets import QDialog, QFileDialog
from PySide2.QtCore import Property, Slot
from UI.ui_tax_export_dlg import Ui_TaxExportDlg


#-----------------------------------------------------------------------------------------------------------------------
class TaxExportDialog(QDialog, Ui_TaxExportDlg):
    def __init__(self, parent, db):
        QDialog.__init__(self)
        self.setupUi(self)

        self.AccountWidget.init_db(db)
        self.FileSelectBtn.pressed.connect(self.OnFileBtn)

        # center dialog with respect to parent window
        x = parent.x() + parent.width()/2 - self.width()/2
        y = parent.y() + parent.height()/2 - self.height()/2
        self.setGeometry(x, y, self.width(), self.height())

    @Slot()
    def OnFileBtn(self):
        filename = QFileDialog.getSaveFileName(self, g_tr('TaxExportDialog', "Save tax reports to:"),
                                               ".", g_tr('TaxExportDialog', "Excel files (*.xlsx)"))
        if filename[0]:
            if filename[1] == g_tr('TaxExportDialog', "Excel files (*.xlsx)") and filename[0][-5:] != '.xlsx':
                self.Filename.setText(filename[0] + '.xlsx')
            else:
                self.Filename.setText(filename[0])

    def getYear(self):
        return self.Year.value()

    def getFilename(self):
        return self.Filename.text()

    def getAccount(self):
        return self.AccountWidget.selected_id

    year = Property(int, fget=getYear)
    filename = Property(int, fget=getFilename)
    account = Property(int, fget=getAccount)


#-----------------------------------------------------------------------------------------------------------------------
class TaxesRus:
    def __init__(self, db):
        self.db = db
        self.reports = {
            "Дивиденды": self.prepare_dividends,
            "Сделки": self.prepare_trades,
            "Комиссии": self.prepare_broker_fees,
            "Корп.события": self.prepare_corporate_actions
        }
        self.bool_text = {
            0: 'Нет',
            1: 'Да'
        }

    def showTaxesDialog(self, parent):
        dialog = TaxExportDialog(parent, self.db)
        if dialog.exec_():
            self.save2file(dialog.filename, dialog.year, dialog.account)

    def save2file(self, taxes_file, year, account_id):
        year_begin = int(time.mktime(datetime.strptime(f"{year}", "%Y").timetuple()))
        year_end = int(time.mktime(datetime.strptime(f"{year + 1}", "%Y").timetuple()))

        workbook = xlsxwriter.Workbook(filename=taxes_file)
        formats = xslxFormat(workbook)

        for report in self.reports:
            sheet = workbook.add_worksheet(name=report)
            self.reports[report](sheet, account_id, year_begin, year_end, formats)
        try:
            workbook.close()
        except:
            logging.error(g_tr('TaxesRus', "Can't write tax report into file ") + f"'{taxes_file}'")

    def add_report_header(self, sheet, formats, title):
        sheet.write(0, 0, title, formats.Bold())
        sheet.write(2, 0, "Документ-основание:")
        sheet.write(3, 0, "Период:")
        sheet.write(4, 0, "ФИО:")
        sheet.write(5, 0, "Номер счета:")

    def prepare_dividends(self, sheet, account_id, begin, end, formats):
        self.add_report_header(sheet, formats, "Отчет по дивидендам, полученным в отчетном периоде")
        _ = executeSQL(self.db, "DELETE FROM t_last_dates")
        _ = executeSQL(self.db,
                       "INSERT INTO t_last_dates(ref_id, timestamp) "
                       "SELECT d.id AS ref_id, MAX(q.timestamp) AS timestamp "
                       "FROM dividends AS d "
                       "LEFT JOIN accounts AS a ON d.account_id=a.id "
                       "LEFT JOIN quotes AS q ON d.timestamp >= q.timestamp AND a.currency_id=q.asset_id "
                       "WHERE d.timestamp>=:begin AND d.timestamp<:end AND d.account_id=:account_id "
                       "GROUP BY d.id", [(":begin", begin), (":end", end), (":account_id", account_id)])
        self.db.commit()

        header_row = {
            0: ("Дата выплаты", formats.ColumnHeader(), 10, 0, 0),
            1: ("Ценная бумага", formats.ColumnHeader(), 8, 0, 0),
            2: ("Полное наименование", formats.ColumnHeader(), 50, 0, 0),
            3: ("Курс USD/RUB на дату выплаты", formats.ColumnHeader(), 16, 0, 0),
            4: ("Доход, USD", formats.ColumnHeader(), 12, 0, 0),
            5: ("Доход, RUB", formats.ColumnHeader(), 12, 0, 0),
            6: ("Налог упл., USD", formats.ColumnHeader(), 12, 0, 0),
            7: ("Налог упл., RUB", formats.ColumnHeader(), 12, 0, 0),
            8: ("Налок к уплате, RUB", formats.ColumnHeader(), 12, 0, 0),
            9: ("Страна", formats.ColumnHeader(), 20, 0, 0),
            10: ("СОИДН", formats.ColumnHeader(), 7, 0, 0)
        }
        xlsxWriteRow(sheet, 7, header_row, 30)
        for column in range(len(header_row)):  # Put column numbers for reference
            header_row[column] = (f"({column + 1})", formats.ColumnHeader())
        xlsxWriteRow(sheet, 8, header_row)

        query = executeSQL(self.db,
                           "SELECT d.timestamp AS payment_date, s.name AS symbol, s.full_name AS full_name, "
                           "d.sum AS amount, d.sum_tax AS tax_amount, q.quote AS rate_cbr , "
                           "c.name AS country, c.tax_treaty AS tax_treaty "
                           "FROM dividends AS d "
                           "LEFT JOIN assets AS s ON s.id = d.asset_id "
                           "LEFT JOIN accounts AS a ON d.account_id = a.id "
                           "LEFT JOIN countries AS c ON d.tax_country_id = c.id "
                           "LEFT JOIN t_last_dates AS ld ON d.id=ld.ref_id "
                           "LEFT JOIN quotes AS q ON ld.timestamp=q.timestamp AND a.currency_id=q.asset_id "
                           "WHERE d.timestamp>=:begin AND d.timestamp<:end AND d.account_id=:account_id "
                           "ORDER BY d.timestamp",
                           [(":begin", begin), (":end", end), (":account_id", account_id)])
        row = 9
        amount_rub_sum = 0
        amount_usd_sum = 0
        tax_usd_sum = 0
        tax_us_rub_sum = 0
        tax_ru_rub_sum = 0
        while query.next():
            payment_date, symbol, full_name, amount_usd, tax_usd, rate, country, tax_treaty = readSQLrecord(query)
            amount_rub = round(amount_usd * rate, 2)
            tax_us_rub = round(-tax_usd * rate, 2)
            tax_ru_rub = round(0.13 * amount_rub, 2)
            if tax_treaty:
                if tax_ru_rub > tax_us_rub:
                    tax_ru_rub = tax_ru_rub - tax_us_rub
                else:
                    tax_ru_rub = 0
            xlsxWriteRow(sheet, row, {
                0: (datetime.fromtimestamp(payment_date).strftime('%d.%m.%Y'), formats.Text(row)),
                1: (symbol, formats.Text(row)),
                2: (full_name, formats.Text(row)),
                3: (rate, formats.Number(row, 4)),
                4: (amount_usd, formats.Number(row, 2)),
                5: (amount_rub, formats.Number(row, 2)),
                6: (-tax_usd, formats.Number(row, 2)),
                7: (tax_us_rub, formats.Number(row, 2)),
                8: (tax_ru_rub, formats.Number(row, 2)),
                9: (country, formats.Text(row)),
                10: (self.bool_text[tax_treaty], formats.Text(row))
            })
            amount_usd_sum += amount_usd
            amount_rub_sum += amount_rub
            tax_usd_sum += -tax_usd
            tax_us_rub_sum += tax_us_rub
            tax_ru_rub_sum += tax_ru_rub
            row += 1
        xlsxWriteRow(sheet, row, {
            3: ("ИТОГО", formats.ColumnFooter()),
            4: (amount_usd_sum, formats.ColumnFooter()),
            5: (amount_rub_sum, formats.ColumnFooter()),
            6: (tax_usd_sum, formats.ColumnFooter()),
            7: (tax_us_rub_sum, formats.ColumnFooter()),
            8: (tax_ru_rub_sum, formats.ColumnFooter())
        })

    def prepare_trades(self, sheet, account_id, begin, end, formats):
        self.add_report_header(sheet, formats, "Отчет по сделкам с ценными бумагами, завершённым в отчетном периоде")
        _ = executeSQL(self.db, "DELETE FROM t_last_dates")
        _ = executeSQL(self.db,
                       "INSERT INTO t_last_dates(ref_id, timestamp) "
                       "SELECT ref_id, MAX(q.timestamp) AS timestamp "
                       "FROM (SELECT o.timestamp AS ref_id "
                       "FROM deals AS d "
                       "LEFT JOIN sequence AS os ON os.id=d.open_sid "
                       "LEFT JOIN trades AS o ON os.operation_id=o.id "
                       "WHERE o.timestamp<:end AND d.account_id=:account_id "
                       "UNION "
                       "SELECT c.timestamp AS ref_id "
                       "FROM deals AS d "
                       "LEFT JOIN sequence AS cs ON cs.id=d.close_sid "
                       "LEFT JOIN trades AS c ON cs.operation_id=c.id "
                       "WHERE c.timestamp<:end AND d.account_id=:account_id "
                       "UNION "
                       "SELECT o.settlement AS ref_id "
                       "FROM deals AS d "
                       "LEFT JOIN sequence AS os ON os.id=d.open_sid "
                       "LEFT JOIN trades AS o ON os.operation_id=o.id "
                       "WHERE o.timestamp<:end AND d.account_id=:account_id "
                       "UNION "
                       "SELECT c.settlement AS ref_id "
                       "FROM deals AS d "
                       "LEFT JOIN sequence AS cs ON cs.id=d.close_sid "
                       "LEFT JOIN trades AS c ON cs.operation_id=c.id "
                       "WHERE c.timestamp<:end AND d.account_id=:account_id "
                       "ORDER BY ref_id) "
                       "LEFT JOIN accounts AS a ON a.id = :account_id "
                       "LEFT JOIN quotes AS q ON ref_id >= q.timestamp AND a.currency_id=q.asset_id "
                       "GROUP BY ref_id",
                       [(":begin", begin), (":end", end), (":account_id", account_id)])
        self.db.commit()

        header_row = {
            0: ("Ценная бумага", formats.ColumnHeader(), 8, 0, 0),
            1: ("Кол-во", formats.ColumnHeader(), 8, 0, 0),
            2: ("Тип сделки", formats.ColumnHeader(), 8, 0, 0),
            3: ("Дата сделки", formats.ColumnHeader(), 10, 0, 0),
            4: ("Курс USD/RUB на дату сделки", formats.ColumnHeader(), 9, 0, 0),
            5: ("Дата поставки", formats.ColumnHeader(), 10, 0, 0),
            6: ("Курс USD/RUB на дату поставки", formats.ColumnHeader(), 9, 0, 0),
            7: ("Цена, USD", formats.ColumnHeader(), 12, 0, 0),
            8: ("Сумма сделки, USD", formats.ColumnHeader(), 12, 0, 0),
            9: ("Сумма сделки, RUB", formats.ColumnHeader(), 12, 0, 0),
            10: ("Комиссия, USD", formats.ColumnHeader(), 12, 0, 0),
            11: ("Комиссия, RUB", formats.ColumnHeader(), 9, 0, 0),
            12: ("Доход, RUB", formats.ColumnHeader(), 12, 0, 0),
            13: ("Расход, RUB", formats.ColumnHeader(), 12, 0, 0),
            14: ("Финансовый результат, RUB", formats.ColumnHeader(), 12, 0, 0)
        }
        xlsxWriteRow(sheet, 7, header_row, 60)
        for column in range(len(header_row)):  # Put column numbers for reference
            header_row[column] = (f"({column + 1})", formats.ColumnHeader())
        xlsxWriteRow(sheet, 8, header_row)

        # Take all actions without conversion
        query = executeSQL(self.db,
                           "SELECT s.name AS symbol, d.qty AS qty, "
                           "o.timestamp AS o_date, qo.quote AS o_rate, o.settlement AS os_date, "
                           "qos.quote AS os_rate, o.price AS o_price, o.fee AS o_fee, "
                           "c.timestamp AS c_date, qc.quote AS c_rate, c.settlement AS cs_date, "
                           "qcs.quote AS cs_rate, c.price AS c_price, c.fee AS c_fee, "
                           "coalesce(ao.type, ac.type, 0) AS corp_action_type "
                           "FROM deals AS d "
                           "LEFT JOIN sequence AS os ON os.id=d.open_sid "
                           "LEFT JOIN trades AS o ON os.operation_id=o.id "
                           "LEFT JOIN sequence AS cs ON cs.id=d.close_sid "
                           "LEFT JOIN trades AS c ON cs.operation_id=c.id "
                           "LEFT JOIN assets AS s ON o.asset_id=s.id "
                           "LEFT JOIN accounts AS a ON a.id = :account_id "
                           "LEFT JOIN t_last_dates AS ldo ON o.timestamp=ldo.ref_id "
                           "LEFT JOIN quotes AS qo ON ldo.timestamp=qo.timestamp AND a.currency_id=qo.asset_id "
                           "LEFT JOIN t_last_dates AS ldos ON o.settlement=ldos.ref_id "
                           "LEFT JOIN quotes AS qos ON ldos.timestamp=qos.timestamp AND a.currency_id=qos.asset_id "
                           "LEFT JOIN t_last_dates AS ldc ON c.timestamp=ldc.ref_id "
                           "LEFT JOIN quotes AS qc ON ldc.timestamp=qc.timestamp AND a.currency_id=qc.asset_id "
                           "LEFT JOIN t_last_dates AS ldcs ON c.settlement=ldcs.ref_id "
                           "LEFT JOIN quotes AS qcs ON ldcs.timestamp=qcs.timestamp AND a.currency_id=qcs.asset_id "
                           "LEFT JOIN corp_actions AS ao ON ao.id=o.corp_action_id "
                           "LEFT JOIN corp_actions AS ac ON ac.id=c.corp_action_id "
                           "WHERE c.timestamp>=:begin AND c.timestamp<:end "
                           "AND d.account_id=:account_id AND corp_action_type != 1 "
                           "ORDER BY o.timestamp, c.timestamp",
                           [(":begin", begin), (":end", end), (":account_id", account_id)])
        start_row = 9
        data_row = 0
        income_sum = 0.0
        spending_sum = 0.0
        profit_sum = 0.0
        while query.next():
            symbol, qty, o_date, o_fee_rate, os_date, o_rate, o_price, o_fee_usd, \
                c_date, c_fee_rate, cs_date, c_rate, c_price, c_fee_usd, corp_action_type = readSQLrecord(query)
            row = start_row + (data_row * 2)
            o_amount_usd = round(o_price * qty, 2)
            o_amount_rub = round(o_amount_usd * o_rate, 2)
            c_amount_usd = round(c_price * qty, 2)
            c_amount_rub = round(c_amount_usd * c_rate, 2)
            o_fee_rub = round(o_fee_usd * o_fee_rate, 2)
            c_fee_rub = round(c_fee_usd * c_fee_rate, 2)
            income = c_amount_rub
            spending = o_amount_rub + o_fee_rub + c_fee_rub
            xlsxWriteRow(sheet, row, {
                0: (symbol, formats.Text(data_row), 0, 0, 1),
                1: (float(qty), formats.Number(data_row, 0, True), 0, 0, 1),
                2: ("Покупка", formats.Text(data_row)),
                3: (datetime.fromtimestamp(o_date).strftime('%d.%m.%Y'), formats.Text(data_row)),
                4: (o_fee_rate, formats.Number(data_row, 4)),
                5: (datetime.fromtimestamp(os_date).strftime('%d.%m.%Y'), formats.Text(data_row)),
                6: (o_rate, formats.Number(data_row, 4)),
                7: (o_price, formats.Number(data_row, 6)),
                8: (o_amount_usd, formats.Number(data_row, 2)),
                9: (o_amount_rub, formats.Number(data_row, 2)),
                10: (o_fee_usd, formats.Number(data_row, 6)),
                11: (o_fee_rub, formats.Number(data_row, 2)),
                12: (income, formats.Number(data_row, 2), 0, 0, 1),
                13: (spending, formats.Number(data_row, 2), 0, 0, 1),
                14: (income - spending, formats.Number(data_row, 2), 0, 0, 1)
            })
            xlsxWriteRow(sheet, row + 1, {
                2: ("Продажа", formats.Text(data_row)),
                3: (datetime.fromtimestamp(c_date).strftime('%d.%m.%Y'), formats.Text(data_row)),
                4: (c_fee_rate, formats.Number(data_row, 4)),
                5: (datetime.fromtimestamp(cs_date).strftime('%d.%m.%Y'), formats.Text(data_row)),
                6: (c_rate, formats.Number(data_row, 4)),
                7: (c_price, formats.Number(data_row, 6)),
                8: (c_amount_usd, formats.Number(data_row, 2)),
                9: (c_amount_rub, formats.Number(data_row, 2)),
                10: (c_fee_usd, formats.Number(data_row, 6)),
                11: (c_fee_rub, formats.Number(data_row, 2))
            })
            income_sum += income
            spending_sum += spending
            profit_sum += income - spending
            data_row = data_row + 1
        row = start_row + (data_row * 2)
        xlsxWriteRow(sheet, row, {
            11: ("ИТОГО", formats.ColumnFooter()),
            12: (income_sum, formats.ColumnFooter()),
            13: (spending_sum, formats.ColumnFooter()),
            14: (profit_sum, formats.ColumnFooter())
        })

    def prepare_broker_fees(self, sheet, account_id, begin, end, formats):
        self.add_report_header(sheet, formats, "Отчет по комиссиям, уплаченным брокеру в отчетном периоде")

        _ = executeSQL(self.db, "DELETE FROM t_last_dates")
        _ = executeSQL(self.db,
                       "INSERT INTO t_last_dates(ref_id, timestamp) "
                       "SELECT a.id AS ref_id, MAX(q.timestamp) AS timestamp "
                       "FROM actions AS a "
                       "LEFT JOIN accounts AS c ON c.id = :account_id "
                       "LEFT JOIN quotes AS q ON a.timestamp >= q.timestamp AND c.currency_id=q.asset_id "
                       "LEFT JOIN action_details AS d ON d.pid=a.id "
                       "WHERE a.timestamp>=:begin AND a.timestamp<:end "
                       "AND a.account_id=:account_id AND d.note LIKE '%MONTHLY%' "
                       "GROUP BY a.id",
                       [(":begin", begin), (":end", end), (":account_id", account_id)])
        self.db.commit()

        header_row = {
            0: ("Описание", formats.ColumnHeader(), 50, 0, 0),
            1: ("Сумма, USD", formats.ColumnHeader(), 8, 0, 0),
            2: ("Дата оплаты", formats.ColumnHeader(), 10, 0, 0),
            3: ("Курс USD/RUB на дату оплаты", formats.ColumnHeader(), 10, 0, 0),
            4: ("Сумма, RUB", formats.ColumnHeader(), 10, 0, 0)
        }
        xlsxWriteRow(sheet, 7, header_row, 60)
        for column in range(len(header_row)):  # Put column numbers for reference
            header_row[column] = (f"({column + 1})", formats.ColumnHeader())
        xlsxWriteRow(sheet, 8, header_row)

        query = executeSQL(self.db,
                           "SELECT a.timestamp AS payment_date, d.sum AS amount, d.note AS note, q.quote AS rate_cbr "
                           "FROM actions AS a "
                           "LEFT JOIN action_details AS d ON d.pid=a.id "
                           "LEFT JOIN accounts AS c ON c.id = :account_id "
                           "LEFT JOIN t_last_dates AS ld ON a.id=ld.ref_id "
                           "LEFT JOIN quotes AS q ON ld.timestamp=q.timestamp AND c.currency_id=q.asset_id "
                           "WHERE a.timestamp>=:begin AND a.timestamp<:end "
                           "AND a.account_id=:account_id AND d.note LIKE '%MONTHLY%' ",
                           [(":begin", begin), (":end", end), (":account_id", account_id)])
        row = 9
        amount_rub_sum = 0
        while query.next():
            payment_date, amount, note, rate = readSQLrecord(query)
            amount_rub = round(-amount * rate, 2)
            xlsxWriteRow(sheet, row, {
                0: (note, formats.Text(row)),
                1: (-amount, formats.Number(row, 2)),
                2: (datetime.fromtimestamp(payment_date).strftime('%d.%m.%Y'), formats.Text(row)),
                3: (rate, formats.Number(row, 4)),
                4: (amount_rub, formats.Number(row, 2))
            })
            amount_rub_sum += amount_rub
            row += 1
        sheet.write(row, 3, "ИТОГО", formats.ColumnFooter())
        sheet.write(row, 4, amount_rub_sum, formats.ColumnFooter())

    def prepare_corporate_actions(self, sheet, _account_id, _begin, _end, formats):
        self.add_report_header(sheet, formats, "Corporate actions report")
        # TODO put here report on stock conversions
