import importlib   # it is used for delayed import in order to avoid circular reference in child classes
import os
import json
import logging
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication

from jal.constants import Setup, PredefinedAsset
from jal.db.helpers import get_app_path
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, Dividend

REPORT_METHOD = 0
REPORT_TEMPLATE = 1

class TaxReport:
    PORTUGAL = 0
    RUSSIA = 1
    countries = {
        PORTUGAL: {"name": "Portugal", "module": "jal.data_export.tax_reports.portugal", "class": "TaxesPortugal", "icon": "pt.png"},
        RUSSIA: {"name": "Россия", "module": "jal.data_export.tax_reports.russia", "class": "TaxesRussia", "icon": "ru.png"}
    }
    currency_name = ''  # The name of the currency for tax values calculation
    country_name = ''   # The name of the country for tax preparation

    def __init__(self):
        self._currency_id = JalAsset(data={'symbol': self.currency_name, 'type_id': PredefinedAsset.Money},
                                      search=True, create=False).id()
        if not self._currency_id:  # Zero value if no currency was found in DB for given currency symbol
            self.reports = {}
            logging.error(self.tr("Currency is not defined: ") + self.currency_name)
            return
        self.account = None           # Account for reporting
        self.account_currency = None  # Currency of the account for reporting
        self.year_begin = 0
        self.year_end = 0
        self.use_settlement = True
        self._parameters = {}

    def tr(self, text):
        return QApplication.translate("TaxReport", text)

    @staticmethod
    def create_report(country: int):
        try:
            report_data = TaxReport.countries[country]
        except KeyError:
            raise ValueError(f"Selected country item {country} has no country handler in tax report code")
        module = importlib.import_module(report_data['module'])
        try:
            class_instance = getattr(module, report_data['class'])
        except AttributeError:
            raise ValueError(f"Tax report class '{report_data['class']}' can't be loaded")
        return class_instance()

    def report_template(self, report_name):
        if report_name not in self.reports:
            logging.warning(self.tr("No report template found for section: ") + report_name)
            return ""
        else:
            return self.reports[report_name][REPORT_TEMPLATE]

    # Loads report parameters for given year into self._parameters
    def load_parameters(self, year: int):
        year_key = str(year)
        file_path = get_app_path() + Setup.EXPORT_PATH + os.sep + Setup.TAX_REPORT_PATH + os.sep + self.country_name + ".json"
        try:
            with open(file_path, 'r', encoding='utf-8') as json_file:
                parameters = json.load(json_file)
        except Exception as e:
            logging.error(self.tr("Can't load tax report parameters from file ") + f"'{file_path}' ({type(e).__name__} {e})")
            return
        if year_key not in parameters:
            logging.warning(self.tr("There are no parameters found for tax report year: ") + year_key)
            return
        self._parameters = parameters[year_key]

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

    def prepare_tax_report(self, year: int, account_id: int, **kwargs) -> dict:
        tax_report = {}
        self.account = JalAccount(account_id)
        self.account_currency = JalAsset(self.account.currency())
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']
        self.load_parameters(year)
        for report in self.reports:
            tax_report[report] = self.reports[report][REPORT_METHOD]()
        return tax_report

    # Check if 2-letter country code present in tax treaty parameter of current report
    def has_tax_treaty_with(self, country_code: str) -> bool:
        if Setup.TAX_TREATY_PARAM not in self._parameters:
            logging.warning(self.tr("There are no information about tax treaty in tax report parameters"))
            return False
        if country_code in self._parameters[Setup.TAX_TREATY_PARAM]:
            return True
        else:
            return False

    # Returns a list of dividends that should be included into the report for given year
    def dividends_list(self) -> list:
        dividends = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockDividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockVesting)
        dividends = [x for x in dividends if self.year_begin <= x.timestamp() <= self.year_end]
        return dividends

    # Returns a list of closed stock/ETF trades that should be included into the report for given year
    def shares_trades_list(self) -> list:
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() in [PredefinedAsset.Stock, PredefinedAsset.ETF]]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade or (
                x.open_operation().type() == LedgerTransaction.Dividend and (
                x.open_operation().subtype() == Dividend.StockDividend or
                x.open_operation().subtype() == Dividend.StockVesting))]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        return trades

    def derivatives_trades_list(self) -> list:
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Derivative]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        return trades

    def bonds_trades_list(self) -> list:
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Bond]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        return trades
