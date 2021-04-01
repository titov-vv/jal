import logging
import pandas
from datetime import datetime, timezone

from jal.widgets.helpers import g_tr
from jal.db.update import JalDB

class IBKR_obsolete():
    def __init__(self, filename):
        self._filename = filename
        self._account = ''

    def load(self):
        # Read first table with account details
        try:
            data = pandas.read_html(self._filename, match='Account Capabilities')
        except:
            logging.error(g_tr('IBKR', "Can't read statement file"))
            return False
        if len(data) != 1:
            logging.error(g_tr('IBKR', "Can't get account details from the statement"))
            return False
        for i, row in data[0].iterrows():
            if row[0] == 'Account':
                self._account = row[1]
        if self._account == '':
            logging.error(g_tr('IBKR', "Can't get account number from the statement"))
            return False

        # Read Trades table
        try:
            data = pandas.read_html(self._filename, match='Date/Time', attrs = {'id': 'summaryDetailTable'})
        except:
            logging.error(g_tr('IBKR', "Can't read Trades table from statement file"))
            return False
        if len(data) != 1:
            logging.error(g_tr('IBKR', "Can't get Trades table from the statement"))
            return False
        statement = data[0]
        statement = statement[statement['Symbol'].notna()]

        account_id = None
        for i, row in statement.iterrows():
            if row[0] == 'Forex':  # We reached end of Stock trades
                break
            if row[0].startswith('Total') or row[0] == 'Stocks' or row[0] == 'Symbol':  # Skip totals and headers
                continue
            if row[0] == row[1]:  # it's a currency header - match account
                account_id = JalDB().get_account_id(self._account, row[0])
                continue
            if account_id is None:  # no reason to check further if we don't have valid account here
                continue
            asset_id = JalDB().get_asset_id(row[0])
            if asset_id is None:
                logging.warning(g_tr('IBKR', "Unknown asset ") + f"'{row[0]}'")
                continue
            timestamp = int(datetime.strptime(row[1], "%Y-%m-%d, %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            settlement = int(datetime.strptime(row[1][:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
            number = f"{i}"
            qty = float(row[2])
            price = float(row[3])
            fee = float(row[6])
            JalDB().add_trade(account_id, asset_id, timestamp, settlement, number, qty, price, fee)
        logging.info(g_tr('IBKR', "Load IBKR Activity statement completed"))
        return True
