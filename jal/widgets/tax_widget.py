from functools import partial
from datetime import datetime
import logging

from PySide6.QtCore import Property, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox
from jal.ui.ui_tax_export_widget import Ui_TaxWidget
from jal.ui.ui_flow_export_widget import Ui_MoneyFlowWidget
from jal.widgets.mdi import MdiWidget
from jal.data_export.taxes import TaxesRus
from jal.data_export.taxes_flow import TaxesFlowRus
from jal.data_export.xlsx import XLSX
from jal.data_export.dlsg import DLSG


class TaxWidget(MdiWidget, Ui_TaxWidget):
    def __init__(self):
        MdiWidget.__init__(self)
        self.setupUi(self)

        self.Year.setValue(datetime.now().year - 1)   # Set previous year by default
        self.XlsSelectBtn.pressed.connect(partial(self.OnFileBtn, 'XLS'))
        self.DlsgSelectBtn.pressed.connect(partial(self.OnFileBtn, 'DLSG'))
        self.SaveButton.pressed.connect(self.SaveReport)

    @Slot()
    def OnFileBtn(self, type):
        if type == 'XLS':
            selector = (self.tr("Save tax reports to:"), self.tr("Excel files (*.xlsx)"), '.xlsx', self.XlsFileName)
        elif type == 'DLSG':
            last_digit = self.year % 10
            selector = (self.tr("Save tax form to:"), self.tr(f"Tax form (*.dc{last_digit})"),
                        f".dc{last_digit}", self.DlsgFileName)
        else:
            raise ValueError
        filename = QFileDialog.getSaveFileName(self, selector[0], ".", selector[1])
        if filename[0]:
            if filename[1] == selector[1] and filename[0][-len(selector[2]):] != selector[2]:
                selector[3].setText(filename[0] + selector[2])
            else:
                selector[3].setText(filename[0])

    def getYear(self):
        return self.Year.value()

    def getXlsFilename(self):
        return self.XlsFileName.text()

    def getAccount(self):
        return self.AccountWidget.selected_id

    def getDlsgState(self):
        return self.DlsgGroup.isChecked()

    def getDslgFilename(self):
        return self.DlsgFileName.text()

    def getBrokerAsIncomeName(self):
        return self.IncomeSourceBroker.isChecked()

    def getDividendsOnly(self):
        return self.DividendsOnly.isChecked()

    def getNoSettlement(self):
        return self.NoSettlement.isChecked()

    year = Property(int, fget=getYear)
    xls_filename = Property(str, fget=getXlsFilename)
    account = Property(int, fget=getAccount)
    update_dlsg = Property(bool, fget=getDlsgState)
    dlsg_filename = Property(str, fget=getDslgFilename)
    dlsg_broker_as_income = Property(bool, fget=getBrokerAsIncomeName)
    dlsg_dividends_only = Property(bool, fget=getDividendsOnly)
    no_settelement = Property(bool, fget=getNoSettlement)

    @Slot()
    def SaveReport(self):
        if not self.account:
            QMessageBox().warning(self, self.tr("Data are incomplete"),
                                  self.tr("You haven't selected an account for tax report"), QMessageBox.Ok)
            return
        taxes = TaxesRus()
        tax_report = taxes.prepare_tax_report(self.year, self.account, use_settlement=(not self.no_settelement))

        reports_xls = XLSX(self.xls_filename)
        templates = {
            "Дивиденды": "tax_rus_dividends.json",
            "Акции": "tax_rus_trades.json",
            "Облигации": "tax_rus_bonds.json",
            "ПФИ": "tax_rus_derivatives.json",
            "Криптовалюты": "tax_rus_crypto.json",
            "Корп.события": "tax_rus_corporate_actions.json",
            "Комиссии": "tax_rus_fees.json",
            "Проценты": "tax_rus_interests.json"
        }
        parameters = {
            "period": f"{datetime.utcfromtimestamp(taxes.year_begin).strftime('%d.%m.%Y')}"
                      f" - {datetime.utcfromtimestamp(taxes.year_end - 1).strftime('%d.%m.%Y')}",
            "account": f"{taxes.account_number} ({taxes.account_currency})",
            "currency": taxes.account_currency,
            "broker_name": taxes.broker_name,
            "broker_iso_country": taxes.broker_iso_cc
        }
        for section in tax_report:
            if section not in templates:
                continue
            reports_xls.output_data(tax_report[section], templates[section], parameters)
        reports_xls.save()

        logging.info(self.tr("Tax report saved to file ") + f"'{self.xls_filename}'")

        if self.update_dlsg:
            tax_forms = DLSG(self.year, broker_as_income=self.dlsg_broker_as_income,
                             only_dividends=self.dlsg_dividends_only)
            tax_forms.update_taxes(tax_report, parameters)
            try:
                tax_forms.save(self.dlsg_filename)
            except:
                logging.error(self.tr("Can't write tax form into file ") + f"'{self.dlsg_filename}'")


class MoneyFlowWidget(MdiWidget, Ui_MoneyFlowWidget):
    def __init__(self):
        MdiWidget.__init__(self)
        self.setupUi(self)

        self.Year.setValue(datetime.now().year - 1)  # Set previous year by default
        self.XlsSelectBtn.pressed.connect(self.OnFileBtn)
        self.SaveButton.pressed.connect(self.SaveReport)

    @Slot()
    def OnFileBtn(self):
        selector = (self.tr("Save money flow report to:"), self.tr("Excel files (*.xlsx)"), '.xlsx', self.XlsFileName)
        filename = QFileDialog.getSaveFileName(self, selector[0], ".", selector[1])
        if filename[0]:
            if filename[1] == selector[1] and filename[0][-len(selector[2]):] != selector[2]:
                selector[3].setText(filename[0] + selector[2])
            else:
                selector[3].setText(filename[0])

    def getYear(self):
        return self.Year.value()

    def getXlsFilename(self):
        return self.XlsFileName.text()

    year = Property(int, fget=getYear)
    xls_filename = Property(str, fget=getXlsFilename)

    @Slot()
    def SaveReport(self):
        taxes_flow = TaxesFlowRus()
        flow_report = taxes_flow.prepare_flow_report(self.year)

        reports_xls = XLSX(self.xls_filename)
        parameters = {
            "period": f"{datetime.utcfromtimestamp(taxes_flow.year_begin).strftime('%d.%m.%Y')}"
                      f" - {datetime.utcfromtimestamp(taxes_flow.year_end - 1).strftime('%d.%m.%Y')}"
        }
        reports_xls.output_data(flow_report, "tax_rus_flow.json", parameters)
        reports_xls.save()

        logging.info(self.tr("Money flow report saved to file ") + f"'{self.xls_filename}'")
        self.close()
