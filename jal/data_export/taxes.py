import importlib   # it is used for delayed import in order to avoid circular reference in child classes
import logging
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication

from jal.constants import PredefinedAsset
from jal.db.account import JalAccount
from jal.db.asset import JalAsset

REPORT_METHOD = 0
REPORT_TEMPLATE = 1

class TaxReport:
    PORTUGAL = 0
    RUSSIA = 1
    countries = {
        PORTUGAL: {"name": "Portugal", "module": "jal.data_export.tax_reports.portugal", "class": "TaxesPortugal"},
        RUSSIA: {"name": "Россия", "module": "jal.data_export.tax_reports.russia", "class": "TaxesRussia"}
    }
    currency_name = ''

    def __init__(self):
        self._currency_id = JalAsset(data={'symbol': self.currency_name, 'type_id': PredefinedAsset.Money},
                                      search=True, create=False).id()
        if not self._currency_id:  # Zero value if no currency was found in DB for given currency symbol
            self.reports = {}
            logging.error(self.tr("Currency is not defined: ") + self.currency_name)
            return
        self.account = None
        self.year_begin = 0
        self.year_end = 0
        self.use_settlement = True

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

    def prepare_tax_report(self, year, account_id, **kwargs):
        tax_report = {}
        self.account = JalAccount(account_id)
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']
        for report in self.reports:
            tax_report[report] = self.reports[report][REPORT_METHOD]()
        return tax_report
