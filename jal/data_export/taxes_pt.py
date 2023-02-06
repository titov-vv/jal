import logging
from datetime import datetime, timezone
from decimal import Decimal

from PySide6.QtWidgets import QApplication
from jal.constants import PredefinedAsset
from jal.db.operations import Dividend
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.country import JalCountry


class TaxesPortugal:
    def __init__(self):
        self._base_currency_name = 'EUR'
        self._base_currency_id = JalAsset(data={'symbol': self._base_currency_name, 'type_id': PredefinedAsset.Money},
                                          search=True, create=False).id()
        if not self._base_currency_id:
            self.reports = {}
            logging.error(self.tr("Currency is not defined: ") + self._base_currency_name)
            return
        self.account = None
        self.year_begin = 0
        self.year_end = 0
        self.use_settlement = True
        self._processed_trade_qty = {}  # It will handle {trade_id: qty} records to keep track of already processed qty
        self.reports = {
            "Дивиденды": self.prepare_dividends
            # "Акции": self.prepare_stocks_and_etf,
            # "Корп.события": self.prepare_corporate_actions,
            # "Комиссии": self.prepare_broker_fees,
            # "Проценты": self.prepare_broker_interest
        }

    def tr(self, text):
        return QApplication.translate("TaxesPortugal", text)

    def prepare_tax_report(self, year, account_id, **kwargs):
        tax_report = {}
        self.account = JalAccount(account_id)
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']
        for report in self.reports:
            tax_report[report] = self.reports[report]()
        return tax_report

    # ------------------------------------------------------------------------------------------------------------------
    # Create a totals row from provided list of dictionaries
    # it calculates sum for each field in fields and adds it to return dictionary
    def insert_totals(self, list_of_values, fields):
        if not list_of_values:
            return
        totals = {"report_template": "totals"}
        for field in fields:
            totals[field] = sum([x[field] for x in list_of_values if field in x])
        list_of_values.append(totals)

    def prepare_dividends(self):
        currency = JalAsset(self.account.currency())
        dividends_report = []
        dividends = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockDividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockVesting)
        dividends = [x for x in dividends if self.year_begin <= x.timestamp() <= self.year_end]  # Only in given range
        for dividend in dividends:
            amount = dividend.amount()
            rate = currency.quote(dividend.timestamp(), self._base_currency_id)[1]
            price = dividend.asset().quote(dividend.timestamp(), currency.id())[1]
            country = JalCountry(dividend.asset().country())
            tax_treaty = "Да" if country.has_tax_treaty() else "Нет"
            note = ''
            if dividend.subtype() == Dividend.StockDividend:
                if not price:
                    logging.error(self.tr("No price data for stock dividend: ") + f"{dividend}")
                    continue
                amount = amount * price
                note = "Дивиденд выплачен в натуральной форме (ценными бумагами)"
            if dividend.subtype() == Dividend.StockVesting:
                if not price:
                    logging.error(self.tr("No price data for stock vesting: ") + f"{dividend}")
                    continue
                amount = amount * price
                note = "Доход получен в натуральной форме (ценными бумагами)"
            amount_rub = amount * rate
            tax_rub = dividend.tax() * rate
            tax2pay = Decimal('0.13') * amount_rub
            if tax_treaty:
                if tax2pay > tax_rub:
                    tax2pay = tax2pay - tax_rub
                else:
                    tax2pay = Decimal('0.0')
            line = {
                'report_template': "dividend",
                'payment_date': dividend.timestamp(),
                'symbol': dividend.asset().symbol(currency.id()),
                'full_name': dividend.asset().name(),
                'isin': dividend.asset().isin(),
                'amount': amount,
                'tax': dividend.tax(),
                'rate': rate,
                'country': country.name(),
                'country_iso': country.iso_code(),
                'tax_treaty': tax_treaty,
                'amount_rub': round(amount_rub, 2),
                'tax_rub': round(tax_rub, 2),
                'tax2pay': round(tax2pay, 2),
                'note': note
            }
            dividends_report.append(line)
        self.insert_totals(dividends_report, ["amount", "amount_rub", "tax", "tax_rub", "tax2pay"])
        return dividends_report
