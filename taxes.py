import time
import datetime
import xlsxwriter
from PySide2.QtSql import QSqlQuery


class TaxesRus:
    def __init__(self, db):
        self.db = db

    def save2file(self, taxes_file, year, account_id):
        year_begin = int(time.mktime(datetime.datetime.strptime(f"{year}", "%Y").timetuple()))
        year_end = int(time.mktime(datetime.datetime.strptime(f"{year+1}", "%Y").timetuple()))

        workbook = xlsxwriter.Workbook(filename=taxes_file)
        title_format = workbook.add_format({'bold': True,
                                            'bg_color': '#808080'})  # 'gray'
        column_header_format = workbook.add_format({'bold': True,
                                                    'text_wrap': True,
                                                    'align': 'center',
                                                    'valign': 'vcenter',
                                                    'bg_color': '#808080',
                                                    'border': 1})
        number_format = workbook.add_format({'num_format': '# ### ##0.00',
                                             'border': 1})
        rate_format = workbook.add_format({'num_format': '0.0000',
                                           'border': 1})
        text_format = workbook.add_format({'border': 1})

        formats = {'title': title_format,
                   'headers': column_header_format,
                   'text': text_format,
                   'number': number_format,
                   'number_long': rate_format}

        self.prepare_dividends(workbook, account_id, year_begin, year_end, formats)
        self.prepare_trades(workbook, account_id, year_begin, year_end, formats)
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

        query.prepare("SELECT d.id, d.timestamp, s.name, s.full_name, d.sum, d.sum_tax, q.quote AS rate_cbr "
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
        sheet.merge_range(0, 0, 0, 8, "Дивиденды, полученные в отчетном периоде", formats['title'])
        sheet.set_row(1, 30)
        sheet.write(1, 0, "Дата выплаты", formats['header'])
        sheet.set_column(0, 0, 10)
        sheet.write(1, 1, "Ценная бумага", formats['header'])
        sheet.set_column(1, 1, 8)
        sheet.write(1, 2, "Полное наименование", formats['header'])
        sheet.set_column(2, 2, 50)
        sheet.write(1, 3, "Курс USD/RUB на дату выплаты", formats['header'])
        sheet.set_column(3, 3, 16)
        sheet.write(1, 4, "Доход, USD", formats['header'])
        sheet.write(1, 5, "Доход, RUB", formats['header'])
        sheet.write(1, 6, "Налок упл., USD", formats['header'])
        sheet.write(1, 7, "Налог упл., RUB", formats['header'])
        sheet.write(1, 8, "Налок к уплате, RUB", formats['header'])
        sheet.set_column(4, 8, 12)
        row = 2
        amount_rub_sum = 0
        amount_usd_sum = 0
        tax_usd_sum = 0
        tax_us_rub_sum = 0
        tax_ru_rub_sum = 0
        while query.next():
            amount_usd = float(query.value(4))
            tax_usd = -float(query.value(5))
            rate = float(query.value(6))
            amount_rub = round(amount_usd * rate, 2)
            tax_us_rub = round(tax_usd * rate, 2)
            tax_ru_rub = round(0.13 * amount_rub, 2)
            if tax_ru_rub > tax_us_rub:
                tax_ru_rub = tax_ru_rub - tax_us_rub
            else:
                tax_ru_rub = 0
            sheet.write(row, 0, datetime.datetime.fromtimestamp(query.value(1)).strftime('%d.%m.%Y'), formats['text'])
            sheet.write(row, 1, query.value(2), formats['text'])
            sheet.write(row, 2, query.value(3), formats['text'])
            sheet.write(row, 3, rate, formats['number_long'])
            sheet.write(row, 4, amount_usd, formats['number'])
            sheet.write(row, 5, amount_rub, formats['number'])
            sheet.write(row, 6, tax_usd, formats['number'])
            sheet.write(row, 7, tax_us_rub, formats['number'])
            sheet.write(row, 8, tax_ru_rub, formats['number'])
            amount_usd_sum += amount_usd
            amount_rub_sum += amount_rub
            tax_usd_sum += tax_usd
            tax_us_rub_sum += tax_us_rub
            tax_ru_rub_sum += tax_ru_rub
            row = row + 1
        sheet.write(row, 4, amount_usd_sum, formats['number'])
        sheet.write(row, 5, amount_rub_sum, formats['number'])
        sheet.write(row, 6, tax_usd_sum, formats['number'])
        sheet.write(row, 7, tax_us_rub_sum, formats['number'])
        sheet.write(row, 8, tax_ru_rub_sum, formats['number'])

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
                      "WHERE o.timestamp>=:begin AND o.timestamp<:end AND d.account_id=:account_id "
                      "UNION "
                      "SELECT c.timestamp AS ref_id "
                      "FROM deals AS d "
                      "LEFT JOIN sequence AS cs ON cs.id=d.close_sid "
                      "LEFT JOIN trades AS c ON cs.operation_id=c.id "
                      "WHERE c.timestamp>=:begin AND c.timestamp<:end AND d.account_id=:account_id "
                      "UNION "
                      "SELECT o.settlement AS ref_id "
                      "FROM deals AS d "
                      "LEFT JOIN sequence AS os ON os.id=d.open_sid "
                      "LEFT JOIN trades AS o ON os.operation_id=o.id "
                      "WHERE o.timestamp>=:begin AND o.timestamp<:end AND d.account_id=:account_id "
                      "UNION "
                      "SELECT c.settlement AS ref_id "
                      "FROM deals AS d "
                      "LEFT JOIN sequence AS cs ON cs.id=d.close_sid "
                      "LEFT JOIN trades AS c ON cs.operation_id=c.id "
                      "WHERE c.timestamp>=:begin AND c.timestamp<:end AND d.account_id=:account_id "
                      "ORDER BY ref_id) "
                      "LEFT JOIN accounts AS a ON a.id = :account_id "
                      "LEFT JOIN quotes AS q ON ref_id >= q.timestamp AND a.currency_id=q.asset_id "
                      "GROUP BY ref_id")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        self.db.commit()

        query.prepare("SELECT a.name, d.qty, o.timestamp, o.settlement, o.price, o.fee, "
                      "c.timestamp, c.settlement, c.price, c.fee FROM deals AS d "
                      "LEFT JOIN sequence AS os ON os.id=d.open_sid "
                      "LEFT JOIN trades AS o ON os.operation_id=o.id "
                      "LEFT JOIN sequence AS cs ON cs.id=d.close_sid "
                      "LEFT JOIN trades AS c ON cs.operation_id=c.id "
                      "LEFT JOIN assets AS a ON d.asset_id=a.id "
                      "WHERE c.timestamp>=:begin AND c.timestamp<:end AND d.account_id=:account_id")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        query.exec_()

        sheet = workbook.add_worksheet(name="Deals")
        sheet.merge_range(0, 0, 0, 8, "Дивиденды, полученные в отчетном периоде", formats['title'])
        sheet.set_row(1, 30)
        row = 2
        while query.next():
            for column in range(query.record().count()):
                sheet.write(row, column, query.value(column))
            row = row + 1

    def prepare_corporate_actions(self, workbook, account_id, begin, end, formats):
        sheet = workbook.add_worksheet(name="Corp.Actions")