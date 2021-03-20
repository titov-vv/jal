import logging
import re
from datetime import datetime, timezone
from zipfile import ZipFile
import pandas

from jal.widgets.helpers import g_tr
from jal.db.update import JalDB
from jal.constants import Setup, DividendSubtype


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
                logging.error(g_tr('Uralsib', "Archive contains multiple files, only one is expected for import"))
                return False
            with zip_file.open(contents[0]) as r_file:
                self._statement = pandas.read_excel(io=r_file.read(), header=None, na_filter=False)
        if not self.validate():
            return False
        self.load_stock_deals()
        return True

    def validate(self):
        if self._statement[2][0] != self.Header:
            logging.error(g_tr('Uralsib', "Can't find Uralsib Capital report header"))
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

    def find_section_start(self, header, subheader, columns) -> (int, dict):
        header_found = False
        start_row = -1
        headers = {}
        for i, row in self._statement.iterrows():
            if not header_found and (row[0] == header):
                header_found = True
            if header_found and (row[0] == subheader):
                start_row = i + 3  # skip subheader and 2 rows of column headers
                for col in range(self._statement.shape[1]):  # Load section headers from next row
                    headers[self._statement[col][i+1]] = col
        column_indices = {column: headers.get(columns[column], -1) for column in columns}
        for idx in column_indices:
            if column_indices[idx] < 0:
                logging.error(g_tr('Uralsib', "Column not found: ") + idx)
                start_row = -1
        return start_row, column_indices

    def load_stock_deals(self):
        cnt = 0
        columns = {
            "number": "Номер сделки",
            "date": "Дата сделки",
            "time": "Время сделки",
            "isin": "ISIN",
            "B/S": "Вид сделки",
            "price": "Цена одной ЦБ",
            "qty": "Количество ЦБ, шт.",
            "amount": "Сумма сделки",
            "accrued_int": "НКД",
            "settlement": "Дата поставки, плановая",
            "fee_ex": "Комиссия ТС"
        }

        row, headers = self.find_section_start("СДЕЛКИ С ЦЕННЫМИ БУМАГАМИ",
                                               "Биржевые сделки с ценными бумагами в отчетном периоде", columns)
        if row < 0:
            return False
        asset_name = ''
        while row < self._statement.shape[0]:
            if self._statement[0][row] == '' and self._statement[0][row+1] == '':
                break
            if self._statement[0][row] == 'Итого по выпуску:' or self._statement[0][row] == '':
                row += 1
                continue
            try:
                deal_number = int(self._statement[0][row])
            except ValueError:
                asset_name = self._statement[0][row]
                row += 1
                continue

            asset_id = self._parent.findAssetID('', isin=self._statement[headers['isin']][row], name=asset_name)
            if self._statement[headers['B/S']][row] == 'Покупка':
                qty = self._statement[headers['qty']][row]
                bond_interest = -self._statement[headers['accrued_int']][row]
            elif self._statement[headers['B/S']][row] == 'Продажа':
                qty = -self._statement[headers['qty']][row]
                bond_interest = self._statement[headers['accrued_int']][row]
            else:
                row += 1
                logging.warning(g_tr('Uralsib', "Unknown trade type: ") + self._statement[headers['B/S']][row])
                continue

            price = self._statement[headers['price']][row]
            fee = self._statement[headers['fee_ex']][row]
            amount = self._statement[headers['amount']][row]
            if abs(abs(price * qty) - amount) >= Setup.CALC_TOLERANCE:
                price = abs(amount / qty)
            ts_string = self._statement[headers['date']][row] + ' ' + self._statement[headers['time']][row]
            timestamp = int(datetime.strptime(ts_string, "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            settlement = int(datetime.strptime(self._statement[headers['settlement']][row],
                                               "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            JalDB().add_trade(self._account_id, asset_id, timestamp, settlement, deal_number, qty, price, -fee)
            if bond_interest != 0:
                JalDB().add_dividend(DividendSubtype.BondInterest, timestamp, self._account_id, asset_id,
                                     bond_interest, "НКД", deal_number)
            cnt += 1
            row += 1
        logging.info(g_tr('Uralsib', "Trades loaded: ") + f"{cnt}")
