import importlib   # it is used for delayed import in order to avoid circular reference in child classes
import json
import logging
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication

from jal.constants import Setup, PredefinedAsset
from jal.db.settings import JalSettings
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.category import JalCategory
from jal.db.helpers import day_begin
from jal.db.operations import AssetPayment
from jal.db.residence import wall_clock_reading

REPORT_METHOD = 0
REPORT_TEMPLATE = 1
# Wider than any gap between two wall clocks (the farthest apart are 26 hours), so a window widened by it can't miss
# an operation that belongs to the year on the clock of the report - see TaxReport.category_operations()
ZONE_SPAN = 2 * 24 * 60 * 60

class TaxReport:
    PORTUGAL = 0
    RUSSIA = 1
    countries = {
        PORTUGAL: {"name": "Portugal", "module": "jal.data_export.tax_reports.portugal", "class": "TaxesPortugal", "flag": "pt"},
        RUSSIA: {"name": "Россия", "module": "jal.data_export.tax_reports.russia", "class": "TaxesRussia", "flag": "ru"}
    }
    currency_name = ''  # The name of the currency for tax values calculation
    country_name = ''   # The name of the country for tax preparation
    # The zone whose wall clock this report counts its days and years on - the one of the jurisdiction the report is
    # filed in. Symmetric to Statement.source_timezone: a report names its own zone the way a statement names its
    # source's. An empty name leaves every stored timestamp read as it is.
    report_timezone = ''

    def __init__(self):
        self._currency_id = JalAsset.find({'symbol': self.currency_name, 'type_id': PredefinedAsset.Money}).id()
        if not self._currency_id:  # Zero value if no currency was found in DB for given currency symbol
            self.reports = {}
            logging.error(self.tr("Currency is not defined: ") + self.currency_name)
            return
        self.account = None           # Account for reporting
        self.account_currency = None  # Currency of the account for reporting
        self.year_begin = 0
        self.year_end = 0
        self.use_settlement = True
        self.one_currency_rate = False
        self._parameters = {}

    def tr(self, text):
        return QApplication.translate("TaxReport", text)

    # A moment of an operation as the jurisdiction of this report saw it - the single place where a stored timestamp
    # becomes a date of the report. Everything that is a moment goes through here, both what is printed and what
    # decides which year an operation belongs to. An exchange rate is deliberately not asked for on this clock: the
    # amounts it explains are converted in the ledger, on the stored moment, and a rate taken from a different day
    # would stop being the one those amounts were made of.
    def _moment(self, timestamp: int) -> int:
        if timestamp == day_begin(timestamp):
            return self._date(timestamp)   # a reading of exactly midnight carries no time of day - it is a date
        return wall_clock_reading(timestamp, self.report_timezone)

    # A calendar date of an operation - a settlement day, an ex-date, or a payment whose source gave the day without
    # saying when in it the payment happened, stored as the midnight it was given. Such a date carries no time of day
    # to re-read on another clock, and moving it could only turn it into a different date, so it is the same date in
    # every jurisdiction. Named for what it is, so that a date is never mistaken for a moment left unconverted.
    @staticmethod
    def _date(day: int) -> int:
        return day

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
        file_path = JalSettings.path(JalSettings.PATH_TAX_REPORT_TEMPLATE) + self.country_name + ".json"
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
        # The year is a half-open window [year_begin, year_end): 'year_end' is the FIRST second of the next year,
        # so an operation stamped at midnight on 1 January belongs to that next year and to no other.
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']
        if 'use_one_currency_rate' in kwargs:
            self.one_currency_rate = kwargs['use_one_currency_rate']
        if 'generate_modelo3' in kwargs:
            self.generate_modelo3 = kwargs['generate_modelo3']
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
        dividends = AssetPayment.get_list(self.account.id(), subtype=AssetPayment.Dividend)
        dividends += AssetPayment.get_list(self.account.id(), subtype=AssetPayment.StockDividend)
        dividends += AssetPayment.get_list(self.account.id(), subtype=AssetPayment.StockVesting)
        dividends = [x for x in dividends if self.year_begin <= self._moment(x.timestamp()) < self.year_end]
        return dividends

    # Returns operations of the given category that belong to the report's year. The database is asked for a wider
    # window than the year, because an operation stamped just outside it may well be inside it on the report's clock;
    # what is inside is then decided on that clock alone.
    def category_operations(self, category_id: int) -> list:
        operations = JalCategory(category_id).get_operations(self.year_begin - ZONE_SPAN, self.year_end + ZONE_SPAN)
        return [x for x in operations if self.year_begin <= self._moment(x.timestamp()) < self.year_end]

    # Returns a list of closed stock/ETF trades that should be included into the report for given year
    def trades_list(self, asset_type) -> list:
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() in asset_type]
        trades = [x for x in trades if self.year_begin <= self._date(x.close_operation().settlement()) < self.year_end]
        return trades
