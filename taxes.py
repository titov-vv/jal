import time, datetime, xlwt
from PySide2.QtSql import QSqlQuery

class TaxesRus:
    def __init__(self, db):
        self.db = db

    def save2file(self, taxes_file, year, account_id):
        year_begin = int(time.mktime(datetime.datetime.strptime(f"{year}", "%Y").timetuple()))
        year_end = int(time.mktime(datetime.datetime.strptime(f"{year+1}", "%Y").timetuple()))

        dividends_query = QSqlQuery(self.db)
        dividends_query.prepare("SELECT d.timestamp, a.name, a.full_name, d.sum, d.sum_tax FROM dividends AS d "
                                "LEFT JOIN assets AS a ON a.id = d.asset_id "
                                "WHERE d.timestamp>=:start AND d.timestamp<:end AND d.account_id=:account_id")
        dividends_query.bindValue(":start", year_begin)
        dividends_query.bindValue(":end", year_end)
        dividends_query.bindValue(":account_id", account_id)
        dividends_query.exec_()

        wbk = xlwt.Workbook()
        sheet = wbk.add_sheet("Dividends", cell_overwrite_ok=True)
        row = 0
        while dividends_query.next():
            for column in range(dividends_query.record().count()):
                sheet.write(row, column, dividends_query.value(column))
            row = row + 1
        wbk.save(taxes_file)