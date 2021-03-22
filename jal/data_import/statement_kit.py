import logging
import re
from datetime import datetime, timezone
import pandas

from jal.widgets.helpers import g_tr
from jal.db.update import JalDB


# -----------------------------------------------------------------------------------------------------------------------
class KITFinance:
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
        print(self._statement)
        return True