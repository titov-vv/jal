import time, datetime, xlwt
from PySide2.QtSql import QSqlQuery

class TaxesRus:
    def __init__(self, db):
        self.db = db

    def save2file(self, taxes_file, year, account_id):
        year_begin = int(time.mktime(datetime.datetime.strptime(f"{year}", "%Y").timetuple()))
        year_end = int(time.mktime(datetime.datetime.strptime(f"{year+1}", "%Y").timetuple()))

        wbk = xlwt.Workbook()

        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM t_last_dates")
        query.prepare("INSERT INTO t_last_dates(ref_id, timestamp) "
                      "SELECT d.id AS ref_id, MAX(q.timestamp) AS timestamp "
                      "FROM dividends AS d "
                      "LEFT JOIN accounts AS a ON d.account_id=a.id "
                      "LEFT JOIN quotes AS q ON d.timestamp >= q.timestamp AND a.currency_id=q.asset_id "
                      "WHERE d.timestamp>=:begin AND d.timestamp<:end AND d.account_id=:account_id "
                      "GROUP BY d.id")
        query.bindValue(":begin", year_begin)
        query.bindValue(":end", year_end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()
        self.db.commit()
        query.prepare("SELECT d.id, d.timestamp, s.name, s.full_name, d.sum, d.sum_tax, q.quote AS rate_cbr "
                      #"datetime(d.timestamp, 'unixepoch', 'localtime') AS div_date, datetime(q.timestamp, 'unixepoch', 'localtime') AS q_date " 
                      "FROM dividends AS d "
                      "LEFT JOIN assets AS s ON s.id = d.asset_id "
                      "LEFT JOIN accounts AS a ON d.account_id = a.id "
                      "LEFT JOIN t_last_dates AS ld ON d.id=ld.ref_id "
                      "LEFT JOIN quotes AS q ON ld.timestamp=q.timestamp AND a.currency_id=q.asset_id "
                      "WHERE d.timestamp>=:begin AND d.timestamp<:end AND d.account_id=:account_id "
                      "ORDER BY d.timestamp")
        query.bindValue(":begin", year_begin)
        query.bindValue(":end", year_end)
        query.bindValue(":account_id", account_id)
        assert query.exec_()

        dividends_sheet = wbk.add_sheet("Dividends", cell_overwrite_ok=True)
        dividends_sheet.write(0, 0, "Дивиденды, полученные в отчетном периоде")
        dividends_sheet.write(1, 0, "Дата выплаты")
        dividends_sheet.write(1, 1, "Ценная бумага")
        dividends_sheet.write(1, 2, "Полное наименование")
        dividends_sheet.write(1, 3, "Курс USD/RUB на дату выплаты")
        dividends_sheet.write(1, 4, "Доход, USD")
        dividends_sheet.write(1, 5, "Доход, RUB")
        dividends_sheet.write(1, 6, "Налок упл., USD")
        dividends_sheet.write(1, 7, "Налог упл., RUB")
        dividends_sheet.write(1, 8, "Налок к уплате, RUB")
        row = 2
        while query.next():
            amount_usd = float(query.value(4))
            tax_usd = -float(query.value(5))
            rate = float(query.value(6))
            amount_rub = round(amount_usd * rate, 2)
            tax_us_rub = round(tax_usd * rate, 2)
            tax_ru_rub = round(0.13*amount_rub, 2)
            if tax_ru_rub > tax_us_rub:
                tax_ru_rub = tax_ru_rub - tax_us_rub
            else:
                tax_ru_rub = 0
            dividends_sheet.write(row, 0, datetime.datetime.fromtimestamp(query.value(1)).strftime('%d.%m.%Y'))
            dividends_sheet.write(row, 1, query.value(2))
            dividends_sheet.write(row, 2, query.value(3))
            dividends_sheet.write(row, 3, f"{rate:.2f}")
            dividends_sheet.write(row, 4, f"{amount_usd:.2f}")
            dividends_sheet.write(row, 5, f"{amount_rub:.2f}")
            dividends_sheet.write(row, 6, f"{tax_usd:.2f}")
            dividends_sheet.write(row, 7, f"{tax_us_rub:.2f}")
            dividends_sheet.write(row, 8, f"{tax_ru_rub:.2f}")
            row = row + 1

        query.prepare("SELECT a.name, d.qty, o.timestamp, o.settlement, o.price, o.fee, "
                      "c.timestamp, c.settlement, c.price, c.fee FROM deals AS d "
                      "LEFT JOIN sequence AS os ON os.id=d.open_sid "
                      "LEFT JOIN trades AS o ON os.operation_id=o.id "
                      "LEFT JOIN sequence AS cs ON cs.id=d.close_sid "
                      "LEFT JOIN trades AS c ON cs.operation_id=c.id "
                      "LEFT JOIN assets AS a ON d.asset_id=a.id "
                      "WHERE c.timestamp>=:begin AND c.timestamp<:end AND d.account_id=:account_id")
        query.bindValue(":begin", year_begin)
        query.bindValue(":end", year_end)
        query.bindValue(":account_id", account_id)
        query.exec_()

        sheet = wbk.add_sheet("Deals", cell_overwrite_ok=True)
        row = 0
        while query.next():
            for column in range(query.record().count()):
                sheet.write(row, column, query.value(column))
            row = row + 1

        wbk.save(taxes_file)