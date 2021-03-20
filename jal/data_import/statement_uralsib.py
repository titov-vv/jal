import logging
import re
from datetime import datetime, timezone
from zipfile import ZipFile
import pandas

from jal.widgets.helpers import g_tr


# -----------------------------------------------------------------------------------------------------------------------
class UralsibCapital:
    Header = '  Брокер: ООО "УРАЛСИБ Брокер"'
    PeriodPattern = "  за период с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d)"

    def __init__(self, parent, filename):
        self._parent = parent
        self._filename = filename
        self._statement = None
        self._account_id = 0

    def load(self):
        with ZipFile(self._filename) as zip_file:
            contents = zip_file.namelist()
            if len(contents) != 1:
                logging.info(g_tr('Uralsib', "Archive contains multiple files, only one is expected for import"))
                return False
            with zip_file.open(contents[0]) as r_file:
                self._statement = pandas.read_excel(io=r_file.read(), header=None, na_filter=False)
        if not self.validate():
            return False
        self.load_stock_deals()

    def validate(self):
        if self._statement[2][0] != self.Header:
            logging.info(g_tr('Uralsib', "Can't find Uralsib Capital report header"))
            return False
        account_name = self._statement[2][7]
        parts = re.match(self.PeriodPattern, self._statement[2][2], re.IGNORECASE)
        if parts is None:
            logging.error(g_tr('Uralsib', "Can't parse Uralsib Capital statement period"))
            return False
        statement_dates = parts.groupdict()
        report_start = int(datetime.strptime(statement_dates['S'], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
        if not self._parent.checkStatementPeriod(account_name, report_start):
            return False
        logging.info(g_tr('Uralsib', "Load Uralsib Capital statement for account ") +
                     f"{account_name}: {statement_dates['S']} - {statement_dates['E']}")
        self._account_id = self._parent.findAccountID(account_name)
        return True

    def find_section_start(self, header, subheader, columns) -> dict:
        header_found = False
        headers = {}
        for i, row in self._statement.iterrows():
            if not header_found and (row[0] == header):
                header_found = True
            if header_found and (row[0] == subheader):
                for col in range(self._statement.shape[1]):  # Load section headers from next row
                    headers[self._statement[col][i+1]] = col
        column_indices = {column: headers.get(columns[column], -1) for column in columns}
        for idx in column_indices:
            if column_indices[idx] < 0:
                return {}
        return column_indices

    def load_stock_deals(self):
        columns = {
            "number": "Номер сделки",
            "date": "Дата сделки",
            "time": "Время сделки",
            "isin": "ISIN",
            "B/S": "Вид сделки",
            "price": "Цена одной ЦБ",
            "qty": "Количество ЦБ, шт.",
            "coupon": "НКД",
            "settlement": "Дата поставки, плановая",
            "fee_ex": "Комиссия ТС"
        }

        headers = self.find_section_start("СДЕЛКИ С ЦЕННЫМИ БУМАГАМИ",
                                          "Биржевые сделки с ценными бумагами в отчетном периоде", columns)
        print(f"Found {headers}")
