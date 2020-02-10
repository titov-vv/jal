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
        query.prepare("SELECT d.timestamp, a.name, a.full_name, d.sum, d.sum_tax FROM dividends AS d "
                                "LEFT JOIN assets AS a ON a.id = d.asset_id "
                                "WHERE d.timestamp>=:begin AND d.timestamp<:end AND d.account_id=:account_id")
        query.bindValue(":begin", year_begin)
        query.bindValue(":end", year_end)
        query.bindValue(":account_id", account_id)
        query.exec_()

        sheet = wbk.add_sheet("Dividends", cell_overwrite_ok=True)
        row = 0
        while query.next():
            for column in range(query.record().count()):
                sheet.write(row, column, query.value(column))
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