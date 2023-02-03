from datetime import datetime, timezone

from PySide6.QtWidgets import QApplication
from jal.db.account import JalAccount


class TaxesPortugal:
    def __init__(self):
        self.account = None
        self.year_begin = 0
        self.year_end = 0
        self.use_settlement = True

    def tr(self, text):
        return QApplication.translate("TaxesPortugal", text)

    def prepare_tax_report(self, year, account_id, **kwargs):
        tax_report = {}
        self.account = JalAccount(account_id)
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']
        return tax_report
