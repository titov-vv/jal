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
        number2_format = workbook.add_format({'num_format': '# ### ##0.00',
                                              'border': 1})
        number4_format = workbook.add_format({'num_format': '0.0000',
                                              'border': 1})
        number6_format = workbook.add_format({'num_format': '0.000000',
                                              'border': 1})
        number_center_format = workbook.add_format({'num_format': '# ### ##0',
                                                    'border': 1,
                                                    'align': 'center',
                                                    'valign': 'vcenter'})
        number2_center_format = workbook.add_format({'num_format': '# ### ##0.00',
                                                     'border': 1,
                                                     'align': 'right',
                                                     'valign': 'vcenter'})
        text_centered_format = workbook.add_format({'border': 1,
                                                    'align': 'left',
                                                    'valign': 'vcenter'})
        text_format = workbook.add_format({'border': 1})

        formats = {'title': title_format,
                   'header': column_header_format,
                   'text': text_format,
                   'text_center': text_centered_format,
                   'number_2': number2_format,
                   'number_4': number4_format,
                   'number_6': number6_format,
                   'number_center': number_center_format,
                   'number_2_center': number2_center_format}

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
            sheet.write(row, 3, rate, formats['number_4'])
            sheet.write(row, 4, amount_usd, formats['number_2'])
            sheet.write(row, 5, amount_rub, formats['number_2'])
            sheet.write(row, 6, tax_usd, formats['number_2'])
            sheet.write(row, 7, tax_us_rub, formats['number_2'])
            sheet.write(row, 8, tax_ru_rub, formats['number_2'])
            amount_usd_sum += amount_usd
            amount_rub_sum += amount_rub
            tax_usd_sum += tax_usd
            tax_us_rub_sum += tax_us_rub
            tax_ru_rub_sum += tax_ru_rub
            row = row + 1
        sheet.write(row, 4, amount_usd_sum, formats['number_2'])
        sheet.write(row, 5, amount_rub_sum, formats['number_2'])
        sheet.write(row, 6, tax_usd_sum, formats['number_2'])
        sheet.write(row, 7, tax_us_rub_sum, formats['number_2'])
        sheet.write(row, 8, tax_ru_rub_sum, formats['number_2'])

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

        query.prepare("SELECT s.name AS symbol, d.qty AS qty, "
                      "o.timestamp AS o_date, qo.quote AS o_rate, o.settlement AS os_date, qos.quote AS os_rate, "
                      "o.price AS o_price, o.fee AS o_fee, "
                      "c.timestamp AS c_date, qc.quote AS c_rate, c.settlement AS cs_date, qcs.quote AS cs_rate, "
                      "c.price AS c_price, c.fee AS c_fee "
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
                      "WHERE c.timestamp>=:begin AND c.timestamp<:end AND d.account_id=:account_id "
                      "ORDER BY o.timestamp, c.timestamp")
        query.bindValue(":begin", begin)
        query.bindValue(":end", end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()

        sheet = workbook.add_worksheet(name="Deals")
        sheet.merge_range(0, 0, 0, 8, "Сделки с ценными бумагами, завершённые в отчетном периоде", formats['title'])
        sheet.set_row(1, 30)
        sheet.write(1, 0, "Ценная бумага", formats['header'])
        sheet.write(1, 1, "Кол-во", formats['header'])
        sheet.write(1, 2, "Тип сделки", formats['header'])
        sheet.write(1, 3, "Дата сделки", formats['header'])
        sheet.write(1, 4, "Курс USD/RUB на дату сделки", formats['header'])
        sheet.write(1, 5, "Дата поставки", formats['header'])
        sheet.write(1, 6, "Курс USD/RUB на дату поставки", formats['header'])
        sheet.write(1, 7, "Цена, USD", formats['header'])
        sheet.write(1, 8, "Сумма сделки, USD", formats['header'])
        sheet.write(1, 9, "Сумма сделки, RUB", formats['header'])
        sheet.write(1, 10, "Комиссия, USD", formats['header'])
        sheet.write(1, 11, "Комиссия, RUB", formats['header'])
        sheet.write(1, 12, "Доход, RUB", formats['header'])
        sheet.write(1, 13, "Расход, RUB", formats['header'])
        sheet.write(1, 14, "Финансовый результат, RUB", formats['header'])
        start_row = 2
        data_row = 0
        income_sum = 0
        spending_sum = 0
        profit_sum = 0
        while query.next():
            row = start_row + (data_row * 2)
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

            sheet.merge_range(row, 0, row+1, 0, query.value("symbol"), formats['text_center'])
            sheet.merge_range(row, 1, row+1, 1, qty, formats['number_center'])
            sheet.write(row, 2, "Покупка", formats['text'])
            sheet.write(row+1, 2, "Продажа", formats['text'])
            sheet.write(row, 3, datetime.datetime.fromtimestamp(query.value("o_date")).strftime('%d.%m.%Y'),
                        formats['text'])
            sheet.write(row+1, 3, datetime.datetime.fromtimestamp(query.value("c_date")).strftime('%d.%m.%Y'),
                        formats['text'])
            sheet.write(row, 4, o_fee_rate, formats['number_4'])
            sheet.write(row+1, 4, c_fee_rate, formats['number_4'])
            sheet.write(row, 5, datetime.datetime.fromtimestamp(query.value("os_date")).strftime('%d.%m.%Y'),
                        formats['text'])
            sheet.write(row + 1, 5, datetime.datetime.fromtimestamp(query.value("cs_date")).strftime('%d.%m.%Y'),
                        formats['text'])
            sheet.write(row, 6, o_rate, formats['number_4'])
            sheet.write(row + 1, 6, c_rate, formats['number_4'])
            sheet.write(row, 7, o_price, formats['number_6'])
            sheet.write(row + 1, 7, c_price, formats['number_6'])
            sheet.write(row, 8, o_amount_usd, formats['number_2'])
            sheet.write(row + 1, 8, c_amount_usd, formats['number_2'])
            sheet.write(row, 9, o_amount_rub, formats['number_2'])
            sheet.write(row + 1, 9, c_amount_rub, formats['number_2'])
            sheet.write(row, 10, o_fee_usd, formats['number_6'])
            sheet.write(row + 1, 10, c_fee_usd, formats['number_6'])
            sheet.write(row, 11, o_fee_rub, formats['number_2'])
            sheet.write(row + 1, 11, c_fee_rub, formats['number_2'])
            sheet.merge_range(row, 12, row + 1, 12, income, formats['number_2_center'])
            sheet.merge_range(row, 13, row + 1, 13, spending, formats['number_2_center'])
            sheet.merge_range(row, 14, row + 1, 14, income - spending, formats['number_2_center'])
            income_sum += income
            spending_sum += spending
            profit_sum += income - spending
            data_row = data_row + 1
        row = start_row + (data_row * 2)
        sheet.write(row, 12, income_sum, formats['number_2'])
        sheet.write(row, 13, spending_sum, formats['number_2'])
        sheet.write(row, 14, profit_sum, formats['number_2'])

    def prepare_corporate_actions(self, workbook, account_id, begin, end, formats):
        sheet = workbook.add_worksheet(name="Corp.Actions")