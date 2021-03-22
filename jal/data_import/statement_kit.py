import logging
import re
from datetime import datetime, timezone
import pandas

from jal.widgets.helpers import g_tr
from jal.db.update import JalDB


# -----------------------------------------------------------------------------------------------------------------------
class KITFinance:
    Header = "КИТ Финанс (АО)"
    AccountPattern = "(?P<ACCOUNT>.*)-(.*)"
    PeriodPattern = "(?P<S>\d\d\.\d\d\.\d\d\d\d) - (?P<E>\d\d\.\d\d\.\d\d\d\d)"

    def __init__(self, parent, filename):
        self._parent = parent
        self._filename = filename
        self._statement = None
        self._account_id = 0

    def load(self):
        self._statement = pandas.read_excel(self._filename, header=None, na_filter=False)
        if not self.validate():
            return False
        # self.load_stock_deals()
        # self.load_cash_tranactions()
        return True

    def validate(self):
        if self._statement[4][0] != self.Header:
            logging.error(g_tr('KIT', "Can't find KIT Finance report header"))
            return False
        parts = re.match(self.AccountPattern, self._statement[5][5], re.IGNORECASE)
        if parts is None:
            logging.error(g_tr('KIT', "Can't parse KIT Finance account number"))
            return False
        account_name = parts.groupdict()['ACCOUNT']
        parts = re.match(self.PeriodPattern, self._statement[5][8], re.IGNORECASE)
        if parts is None:
            logging.error(g_tr('KIT', "Can't parse KIT Finance statement period"))
            return False
        statement_dates = parts.groupdict()
        report_start = int(datetime.strptime(statement_dates['S'], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
        if not self._parent.checkStatementPeriod(account_name, report_start):
            return False
        logging.info(g_tr('KIT', "Loading KIT Finance statement for account ") +
                     f"{account_name}: {statement_dates['S']} - {statement_dates['E']}")
        self._account_id = self._parent.findAccountID(account_name)
        return True