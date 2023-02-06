from PySide6.QtWidgets import QApplication
from jal.data_export.taxes_ru import TaxesRussia
from jal.data_export.taxes_pt import TaxesPortugal


class TaxReport:
    PORTUGAL = 0
    RUSSIA = 1
    countries = {
        PORTUGAL: "Portugal",
        RUSSIA: "Россия"
    }

    def __int__(self):
        pass

    def tr(self, text):
        return QApplication.translate("TaxReport", text)

    @staticmethod
    def create_report(country: int):
        if country == TaxReport.RUSSIA:
            return TaxesRussia()
        elif country == TaxReport.PORTUGAL:
            return TaxesPortugal()
        else:
            raise ValueError(f"Selected country item {country} has no country handler in tax report code")
