import importlib   # it is used for delayed import in order to avoid circular reference in child classes
from PySide6.QtWidgets import QApplication


class TaxReport:
    PORTUGAL = 0
    RUSSIA = 1
    countries = {
        PORTUGAL: {"name": "Portugal", "module": "jal.data_export.tax_reports.portugal", "class": "TaxesPortugal"},
        RUSSIA: {"name": "Россия", "module": "jal.data_export.tax_reports.russia", "class": "TaxesRussia"}
    }

    def __int__(self):
        pass

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
