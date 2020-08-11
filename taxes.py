import time
import datetime
import xlsxwriter
from PySide2.QtWidgets import QDialog, QFileDialog
from PySide2.QtCore import Property, Slot
from PySide2.QtSql import QSqlQuery
from UI.ui_tax_export_dlg import Ui_TaxExportDlg


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
        filename = QFileDialog.getSaveFileName(self, self.tr("Save tax forms to:"), ".", self.tr("Excel file (*.xlsx)"))
        if filename[0]:
            if filename[1] == self.tr("Excel file (*.xlsx)") and filename[0][-5:] != '.xlsx':
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


class TaxesRus:
    def __init__(self, db):
        self.db = db

    def save2file(self, taxes_file, year, account_id):
        year_begin = int(time.mktime(datetime.datetime.strptime(f"{year}", "%Y").timetuple()))
        year_end = int(time.mktime(datetime.datetime.strptime(f"{year + 1}", "%Y").timetuple()))

        workbook = xlsxwriter.Workbook(filename=taxes_file)
        title_cell = workbook.add_format({'bold': True})
        column_header_cell = workbook.add_format({'bold': True,
                                                  'text_wrap': True,
                                                  'align': 'center',
                                                  'valign': 'vcenter',
                                                  'bg_color': '#808080',
                                                  'font_color': '#FFFFFF',
                                                  'border': 1})
        column_header_num_cell = workbook.add_format({'bold': True,
                                                      'num_format': '#,###,##0.00',
                                                      'bg_color': '#808080',
                                                      'font_color': '#FFFFFF',
                                                      'border': 1})
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
        number6_odd = workbook.add_format({'num_format': '0.000000',
                                           'border': 1})
        number6_even = workbook.add_format({'num_format': '0.000000',
                                            'border': 1,
                                            'bg_color': '#C0C0C0'})
        text_odd = workbook.add_format({'border': 1,
                                        'valign': 'vcenter'})
        text_even = workbook.add_format({'border': 1,
                                         'valign': 'vcenter',
                                         'bg_color': '#C0C0C0'})

        formats = {'title': title_cell,
                   'header': column_header_cell,
                   'header_number': column_header_num_cell,
                   'text_odd': text_odd,                'text_even': text_even,
                   'number_odd': number_odd,            'number_even': number_even,
                   'number_2_odd': number2_odd,         'number_2_even': number2_even,
                   'number_4_odd': number4_odd,         'number_4_even': number4_even,
                   'number_6_odd': number6_odd,         'number_6_even': number6_even}

        self.prepare_dividends(workbook, account_id, year_begin, year_end, formats)
        self.prepare_trades(workbook, account_id, year_begin, year_end, formats)
        self.prepare_broker_fees(workbook, account_id, year_begin, year_end, formats)
        self.prepare_corporate_actions(workbook, account_id, year_begin, year_end, formats)

        workbook.close()

    def prepare_dividends(self, workbook, account_id, begin, end, formats):
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM t_last_dates")
        assert query.exec_()

        query.prepare("INSERT INTO t_last_dates(ref_id, timestamp) "
                      "SELECT d.id AS ref_id, MAX(q.timestamp) AS timestamp "
                      "FROM dividends AS d "
                      "LEFT JOIN accounts AS a ON d.account_id=a.id "
                      "LEFT JOIN quotes AS q ON d.timestamp >= q.timestamp AND a.currency_id=q.asset_id "
                      "WHERE d.timestamp>=:begin AND d.timestamp<:end AND d.account_id=:account_id "
                      "GROUP BY d.id")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        self.db.commit()

        query.prepare("SELECT d.id, d.timestamp AS payment_date, s.name AS symbol, s.full_name AS full_name, "
                      "d.sum AS amount, d.sum_tax AS tax_amount, q.quote AS rate_cbr "
                      # "datetime(d.timestamp, 'unixepoch', 'localtime') AS div_date " 
                      "FROM dividends AS d "
                      "LEFT JOIN assets AS s ON s.id = d.asset_id "
                      "LEFT JOIN accounts AS a ON d.account_id = a.id "
                      "LEFT JOIN t_last_dates AS ld ON d.id=ld.ref_id "
                      "LEFT JOIN quotes AS q ON ld.timestamp=q.timestamp AND a.currency_id=q.asset_id "
                      "WHERE d.timestamp>=:begin AND d.timestamp<:end AND d.account_id=:account_id "
                      "ORDER BY d.timestamp")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()

        sheet = workbook.add_worksheet(name="Dividends")
        sheet.write(0, 0, "Отчет по дивидендам, полученным в отчетном периоде", formats['title'])
        sheet.write(2, 0, "Документ-основание:")
        sheet.write(3, 0, "Период:")
        sheet.write(4, 0, "ФИО:")
        sheet.write(5, 0, "Номер счета:")
        sheet.set_row(7, 30)
        sheet.write(7, 0, "Дата выплаты", formats['header'])
        sheet.set_column(0, 0, 10)
        sheet.write(7, 1, "Ценная бумага", formats['header'])
        sheet.set_column(1, 1, 8)
        sheet.write(7, 2, "Полное наименование", formats['header'])
        sheet.set_column(2, 2, 50)
        sheet.write(7, 3, "Курс USD/RUB на дату выплаты", formats['header'])
        sheet.set_column(3, 3, 16)
        sheet.write(7, 4, "Доход, USD", formats['header'])
        sheet.write(7, 5, "Доход, RUB", formats['header'])
        sheet.write(7, 6, "Налок упл., USD", formats['header'])
        sheet.write(7, 7, "Налог упл., RUB", formats['header'])
        sheet.write(7, 8, "Налок к уплате, RUB", formats['header'])
        sheet.set_column(4, 8, 12)
        for col in range(9):
            sheet.write(8, col, f"({col + 1})", formats['header'])  # Put column numbers for reference
        row = 9
        amount_rub_sum = 0
        amount_usd_sum = 0
        tax_usd_sum = 0
        tax_us_rub_sum = 0
        tax_ru_rub_sum = 0
        while query.next():
            if row % 2:
                even_odd = '_odd'
            else:
                even_odd = '_even'
            amount_usd = float(query.value('amount'))
            tax_usd = -float(query.value('tax_amount'))
            rate = float(query.value('rate_cbr'))
            amount_rub = round(amount_usd * rate, 2)
            tax_us_rub = round(tax_usd * rate, 2)
            tax_ru_rub = round(0.13 * amount_rub, 2)
            if tax_ru_rub > tax_us_rub:
                tax_ru_rub = tax_ru_rub - tax_us_rub
            else:
                tax_ru_rub = 0
            sheet.write(row, 0, datetime.datetime.fromtimestamp(query.value('payment_date')).strftime('%d.%m.%Y'),
                        formats['text' + even_odd])
            sheet.write(row, 1, query.value('symbol'), formats['text' + even_odd])
            sheet.write(row, 2, query.value('full_name'), formats['text' + even_odd])
            sheet.write(row, 3, rate, formats['number_4' + even_odd])
            sheet.write(row, 4, amount_usd, formats['number_2' + even_odd])
            sheet.write(row, 5, amount_rub, formats['number_2' + even_odd])
            sheet.write(row, 6, tax_usd, formats['number_2' + even_odd])
            sheet.write(row, 7, tax_us_rub, formats['number_2' + even_odd])
            sheet.write(row, 8, tax_ru_rub, formats['number_2' + even_odd])
            amount_usd_sum += amount_usd
            amount_rub_sum += amount_rub
            tax_usd_sum += tax_usd
            tax_us_rub_sum += tax_us_rub
            tax_ru_rub_sum += tax_ru_rub
            row = row + 1
        sheet.write(row, 3, "ИТОГО", formats['header_number'])
        sheet.write(row, 4, amount_usd_sum, formats['header_number'])
        sheet.write(row, 5, amount_rub_sum, formats['header_number'])
        sheet.write(row, 6, tax_usd_sum, formats['header_number'])
        sheet.write(row, 7, tax_us_rub_sum, formats['header_number'])
        sheet.write(row, 8, tax_ru_rub_sum, formats['header_number'])

    def prepare_trades(self, workbook, account_id, begin, end, formats):
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM t_last_dates")
        assert query.exec_()

        query.prepare("INSERT INTO t_last_dates(ref_id, timestamp) "
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
                      "GROUP BY ref_id")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        self.db.commit()

        # Take all actions without conversion
        query.prepare("SELECT s.name AS symbol, d.qty AS qty, "
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
                      "ORDER BY o.timestamp, c.timestamp")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()

        sheet = workbook.add_worksheet(name="Deals")
        sheet.write(0, 0, "Отчет по сделкам с ценными бумагами, завершённым в отчетном периоде", formats['title'])
        sheet.write(2, 0, "Документ-основание:")
        sheet.write(4, 0, "Период:")
        sheet.write(5, 0, "ФИО:")
        sheet.write(6, 0, "Номер счета:")
        sheet.set_row(8, 60)
        sheet.write(8, 0, "Ценная бумага", formats['header'])
        sheet.set_column(0, 2, 8)
        sheet.write(8, 1, "Кол-во", formats['header'])
        sheet.write(8, 2, "Тип сделки", formats['header'])
        sheet.set_column(3, 3, 10)
        sheet.write(8, 3, "Дата сделки", formats['header'])
        sheet.set_column(4, 4, 9)
        sheet.write(8, 4, "Курс USD/RUB на дату сделки", formats['header'])
        sheet.set_column(5, 5, 10)
        sheet.write(8, 5, "Дата поставки", formats['header'])
        sheet.set_column(6, 6, 9)
        sheet.write(8, 6, "Курс USD/RUB на дату поставки", formats['header'])
        sheet.set_column(7, 10, 12)
        sheet.write(8, 7, "Цена, USD", formats['header'])
        sheet.write(8, 8, "Сумма сделки, USD", formats['header'])
        sheet.write(8, 9, "Сумма сделки, RUB", formats['header'])
        sheet.write(8, 10, "Комиссия, USD", formats['header'])
        sheet.set_column(11, 11, 9)
        sheet.write(8, 11, "Комиссия, RUB", formats['header'])
        sheet.set_column(12, 14, 12)
        sheet.write(8, 12, "Доход, RUB", formats['header'])
        sheet.write(8, 13, "Расход, RUB", formats['header'])
        sheet.write(8, 14, "Финансовый результат, RUB", formats['header'])
        for col in range(15):
            sheet.write(9, col, f"({col + 1})", formats['header'])  # Put column numbers for reference
        start_row = 10
        data_row = 0
        income_sum = 0
        spending_sum = 0
        profit_sum = 0
        while query.next():
            row = start_row + (data_row * 2)
            if data_row % 2:
                even_odd = '_odd'
            else:
                even_odd = '_even'
            qty = float(query.value("qty"))
            o_price = float(query.value("o_price"))
            o_rate = float(query.value("os_rate"))
            c_price = float(query.value("c_price"))
            c_rate = float(query.value("cs_rate"))
            o_amount_usd = round(o_price * qty, 2)
            o_amount_rub = round(o_amount_usd * o_rate, 2)
            c_amount_usd = round(c_price * qty, 2)
            c_amount_rub = round(c_amount_usd * c_rate, 2)
            o_fee_usd = float(query.value("o_fee"))
            o_fee_rate = float(query.value("o_rate"))
            o_fee_rub = round(o_fee_usd * o_fee_rate, 2)
            c_fee_usd = float(query.value("c_fee"))
            c_fee_rate = float(query.value("c_rate"))
            c_fee_rub = round(c_fee_usd * c_fee_rate, 2)
            income = c_amount_rub
            spending = o_amount_rub + o_fee_rub + c_fee_rub

            sheet.merge_range(row, 0, row + 1, 0, query.value("symbol"), formats['text' + even_odd])
            sheet.merge_range(row, 1, row + 1, 1, qty, formats['number' + even_odd])
            sheet.write(row, 2, "Покупка", formats['text' + even_odd])
            sheet.write(row + 1, 2, "Продажа", formats['text' + even_odd])
            sheet.write(row, 3, datetime.datetime.fromtimestamp(query.value("o_date")).strftime('%d.%m.%Y'),
                        formats['text' + even_odd])
            sheet.write(row + 1, 3, datetime.datetime.fromtimestamp(query.value("c_date")).strftime('%d.%m.%Y'),
                        formats['text' + even_odd])
            sheet.write(row, 4, o_fee_rate, formats['number_4' + even_odd])
            sheet.write(row + 1, 4, c_fee_rate, formats['number_4' + even_odd])
            sheet.write(row, 5, datetime.datetime.fromtimestamp(query.value("os_date")).strftime('%d.%m.%Y'),
                        formats['text' + even_odd])
            sheet.write(row + 1, 5, datetime.datetime.fromtimestamp(query.value("cs_date")).strftime('%d.%m.%Y'),
                        formats['text' + even_odd])
            sheet.write(row, 6, o_rate, formats['number_4' + even_odd])
            sheet.write(row + 1, 6, c_rate, formats['number_4' + even_odd])
            sheet.write(row, 7, o_price, formats['number_6' + even_odd])
            sheet.write(row + 1, 7, c_price, formats['number_6' + even_odd])
            sheet.write(row, 8, o_amount_usd, formats['number_2' + even_odd])
            sheet.write(row + 1, 8, c_amount_usd, formats['number_2' + even_odd])
            sheet.write(row, 9, o_amount_rub, formats['number_2' + even_odd])
            sheet.write(row + 1, 9, c_amount_rub, formats['number_2' + even_odd])
            sheet.write(row, 10, o_fee_usd, formats['number_6' + even_odd])
            sheet.write(row + 1, 10, c_fee_usd, formats['number_6' + even_odd])
            sheet.write(row, 11, o_fee_rub, formats['number_2' + even_odd])
            sheet.write(row + 1, 11, c_fee_rub, formats['number_2' + even_odd])
            sheet.merge_range(row, 12, row + 1, 12, income, formats['number_2' + even_odd])
            sheet.merge_range(row, 13, row + 1, 13, spending, formats['number_2' + even_odd])
            sheet.merge_range(row, 14, row + 1, 14, income - spending, formats['number_2' + even_odd])
            income_sum += income
            spending_sum += spending
            profit_sum += income - spending
            data_row = data_row + 1
        row = start_row + (data_row * 2)
        sheet.write(row, 11, "ИТОГО", formats['header_number'])
        sheet.write(row, 12, income_sum, formats['header_number'])
        sheet.write(row, 13, spending_sum, formats['header_number'])
        sheet.write(row, 14, profit_sum, formats['header_number'])

    def prepare_broker_fees(self, workbook, account_id, begin, end, formats):
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM t_last_dates")
        assert query.exec_()

        query.prepare("INSERT INTO t_last_dates(ref_id, timestamp) "
                      "SELECT a.id AS ref_id, MAX(q.timestamp) AS timestamp "
                      "FROM actions AS a "
                      "LEFT JOIN accounts AS c ON c.id = :account_id "
                      "LEFT JOIN quotes AS q ON a.timestamp >= q.timestamp AND c.currency_id=q.asset_id "
                      "LEFT JOIN action_details AS d ON d.pid=a.id "
                      "WHERE a.timestamp>=:begin AND a.timestamp<:end "
                      "AND a.account_id=:account_id AND d.note LIKE '%MONTHLY%' "
                      "GROUP BY a.id")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        self.db.commit()

        query.prepare("SELECT a.timestamp AS payment_date, d.sum AS amount, d.note AS note, q.quote AS rate_cbr "
                      "FROM actions AS a "
                      "LEFT JOIN action_details AS d ON d.pid=a.id "
                      "LEFT JOIN accounts AS c ON c.id = :account_id "
                      "LEFT JOIN t_last_dates AS ld ON a.id=ld.ref_id "
                      "LEFT JOIN quotes AS q ON ld.timestamp=q.timestamp AND c.currency_id=q.asset_id "
                      "WHERE a.timestamp>=:begin AND a.timestamp<:end "
                      "AND a.account_id=:account_id AND d.note LIKE '%MONTHLY%' ")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()

        sheet = workbook.add_worksheet(name="Fees")
        sheet.write(0, 0, "Отчет по комиссиям, уплаченным брокеру в отчетном периоде", formats['title'])
        sheet.write(2, 0, "Документ-основание:")
        sheet.write(3, 0, "Период:")
        sheet.write(4, 0, "ФИО:")
        sheet.write(5, 0, "Номер счета:")
        sheet.set_row(7, 60)
        sheet.write(7, 0, "Описание", formats['header'])
        sheet.set_column(0, 0, 50)
        sheet.write(7, 1, "Сумма, USD", formats['header'])
        sheet.set_column(1, 1, 8)
        sheet.write(7, 2, "Дата оплаты", formats['header'])
        sheet.set_column(2, 2, 10)
        sheet.write(7, 3, "Курс USD/RUB на дату оплаты", formats['header'])
        sheet.set_column(3, 3, 10)
        sheet.write(7, 4, "Сумма, RUB", formats['header'])
        sheet.set_column(4, 4, 10)
        for col in range(5):
            sheet.write(8, col, f"({col + 1})", formats['header'])  # Put column numbers for reference
        row = 9
        amount_rub_sum = 0
        while query.next():
            if row % 2:
                even_odd = '_odd'
            else:
                even_odd = '_even'
            amount_usd = -float(query.value('amount'))
            rate = float(query.value('rate_cbr'))
            amount_rub = round(amount_usd * rate, 2)
            sheet.write(row, 0, query.value('note'), formats['text' + even_odd])
            sheet.write(row, 1, amount_usd, formats['number_2' + even_odd])
            sheet.write(row, 2, datetime.datetime.fromtimestamp(query.value('payment_date')).strftime('%d.%m.%Y'),
                        formats['text' + even_odd])
            sheet.write(row, 3, rate, formats['number_4' + even_odd])
            sheet.write(row, 4, amount_rub, formats['number_2' + even_odd])
            amount_rub_sum += amount_rub
            row = row + 1
        sheet.write(row, 3, "ИТОГО", formats['header_number'])
        sheet.write(row, 4, amount_rub_sum, formats['header_number'])

    def prepare_corporate_actions(self, workbook, _account_id, _begin, _end, _formats):
        _query = QSqlQuery(self.db)
        _sheet = workbook.add_worksheet(name="Corp.Actions")
        # TODO put here report on stock conversions
