from functools import partial
from datetime import datetime
import logging
import traceback

from PySide6.QtCore import Property, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication

from jal.ui.ui_tax_export_widget import Ui_TaxWidget
from jal.ui.ui_flow_export_widget import Ui_MoneyFlowWidget
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import ts2d, dt2ts
from jal.widgets.icons import JalIcon
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.db.settings import JalSettings, FolderFor
from jal.data_export.taxes import TaxReport
from jal.data_export.taxes_flow import TaxesFlowRus
from jal.data_export.xlsx import XLSX
from jal.data_export.dlsg import DLSG
from jal.data_export.irs_modelo3 import IRS_Modelo3


class TaxWidget(MdiWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_TaxWidget()
        self.ui.setupUi(self)

        self.ui.Country.clear()
        for x in TaxReport.countries:
            self.ui.Country.addItem(JalIcon.country_flag(TaxReport.countries[x]['flag']), TaxReport.countries[x]['name'])
        self.ui.Country.currentIndexChanged.connect(self.OnCountryChange)
        self.ui.Year.valueChanged.connect(self.OnYearChange)
        self.ui.Year.setValue(datetime.now().year - 1)   # Set previous year by default
        self.ui.XlsSelectBtn.pressed.connect(partial(self.OnFileBtn, 'XLS'))
        self.ui.DlsgSelectBtn.pressed.connect(partial(self.OnFileBtn, 'DLSG'))
        self.ui.IRS_Modelo3SelectBtn.pressed.connect(partial(self.OnFileBtn, 'XML'))
        self.ui.SaveButton.pressed.connect(self.SaveReport)
        self.ui.Country.setCurrentIndex(TaxReport.RUSSIA)

    def OnCountryChange(self, item_id):
        if item_id == TaxReport.PORTUGAL:
            self.ui.RuBox.setVisible(False)
            self.ui.PtBox.setVisible(True)
        elif item_id == TaxReport.RUSSIA:
            self.ui.RuBox.setVisible(True)
            self.ui.PtBox.setVisible(False)
        else:
            raise ValueError("Selected item has no country handler in code")
        # Refresh and adjust MDI-window size
        if not self.parent() is None:
            self.parent().update()
            QApplication.processEvents()
            if not self.parent().isMaximized():  # Prevent size-change of maximized MDI
                self.parent().adjustSize()

    # Load account combobox with account names relevant for the given year
    def OnYearChange(self, year):
        self.ui.Account.clear()
        accounts = JalAccount.get_taxable_accounts(dt2ts(datetime(year, 1, 1)))
        for account in accounts:
            self.ui.Account.addItem(account.name(), account.id())

    # Displays tax widget in a given MDI area.
    # It is implemented as a separate static method in order to prevent unexpected object deletion
    @staticmethod
    def showInMDI(parent_mdi):
        parent_mdi.addSubWindow(TaxWidget(), maximized=False)

    @Slot()
    def OnFileBtn(self, type):
        if type == 'XLS':
            selector = (self.tr("Save tax reports to:"), self.tr("Excel files (*.xlsx)"), '.xlsx', self.ui.XlsFileName)
        elif type == 'DLSG':
            last_digit = self.year % 10
            selector = (self.tr("Save tax form to:"), self.tr(f"Tax form (*.dc{last_digit})"),
                        f".dc{last_digit}", self.ui.DlsgFileName)
        elif type == 'XML':
            selector = (self.tr("Save IRS Modelo 3 tax data to:"), self.tr("XML files (*.xml)"), '.xml', self.ui.IRS_Modelo3Filename)
        else:
            raise ValueError
        folder = JalSettings().getRecentFolder(FolderFor.Report, '.')
        filename = QFileDialog.getSaveFileName(self, selector[0], folder, selector[1])
        if filename[0]:
            if filename[1] == selector[1] and filename[0][-len(selector[2]):] != selector[2]:
                selector[3].setText(filename[0] + selector[2])
            else:
                selector[3].setText(filename[0])
            JalSettings().setRecentFolder(FolderFor.Report, filename[0])

    year = Property(int, fget=lambda self: self.ui.Year.value())
    xls_filename = Property(str, fget=lambda self: self.ui.XlsFileName.text())
    account = Property(int, fget=lambda self: self.ui.Account.currentData())
    update_dlsg = Property(bool, fget=lambda self: self.ui.DlsgGroup.isChecked())
    dlsg_filename = Property(str, fget=lambda self: self.ui.DlsgFileName.text())
    dlsg_broker_as_income = Property(bool, fget=lambda self: self.ui.DlsgIncomeSourceBroker.isChecked())
    dlsg_dividends_only = Property(bool, fget=lambda self: self.ui.DlsgDividendsOnly.isChecked())
    use_one_rate = Property(bool, fget=lambda self: self.ui.Pt_OneCurrencyRate.isChecked())
    update_modelo3 = Property(bool, fget=lambda self: self.ui.IRS_Modelo3Group.isChecked())
    modelo3_filename = Property(str, fget=lambda self: self.ui.IRS_Modelo3Filename.text())
    no_settlement = Property(bool, fget=lambda self: self.ui.NoSettlement.isChecked())

    @Slot()
    def SaveReport(self):
        if not self.account:
            QMessageBox().warning(self, self.tr("Data are incomplete"),
                                  self.tr("You haven't selected an account for tax report"), QMessageBox.Ok)
            return
        taxes = TaxReport.create_report(self.ui.Country.currentIndex())

        tax_report = taxes.prepare_tax_report(self.year, self.account,
                                              use_one_currency_rate=self.use_one_rate,
                                              use_settlement=(not self.no_settlement))
        if not tax_report:
            logging.warning(self.tr("Tax report is empty"))
            return

        reports_xls = XLSX(self.xls_filename)
        parameters = {
            "period": f"{ts2d(taxes.year_begin)} - {ts2d(taxes.year_end - 1)}",
            "account": f"{taxes.account.number()} ({JalAsset(taxes.account.currency()).symbol()})",
            "currency": JalAsset(taxes.account.currency()).symbol(),
            "broker_name": JalPeer(taxes.account.organization()).name(),
            "broker_iso_country": taxes.account.country().iso_code()
        }
        for section in tax_report:
            reports_xls.output_data(tax_report[section], taxes.report_template(section), parameters)
        reports_xls.save()
        logging.info(self.tr("Tax report was saved to file ") + f"'{self.xls_filename}'")

        if self.update_dlsg or self.update_modelo3:
            tax_forms = None
            if self.update_dlsg:
                tax_forms = DLSG(self.year, broker_as_income=self.dlsg_broker_as_income, only_dividends=self.dlsg_dividends_only)
                filename = self.dlsg_filename
            if self.update_modelo3:
                tax_forms = IRS_Modelo3()
                filename = self.modelo3_filename
            tax_forms.update_taxes(tax_report, parameters)
            try:
                tax_forms.save(filename)
                logging.info(self.tr("Tax report saved to file ") + f"'{filename}'")
            except:
                logging.error(self.tr("Can't write tax form into file ") + f"'{filename}'" +
                              f"\n{traceback.format_exc()}")


class MoneyFlowWidget(MdiWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MoneyFlowWidget()
        self.ui.setupUi(self)

        self.ui.Year.setValue(datetime.now().year - 1)  # Set previous year by default
        self.ui.XlsSelectBtn.pressed.connect(self.OnFileBtn)
        self.ui.SaveButton.pressed.connect(self.SaveReport)

    # Displays tax widget in a given MDI area.
    # It is implemented as a separate static method in order to prevent unexpected object deletion
    @staticmethod
    def showInMDI(parent_mdi):
        parent_mdi.addSubWindow(MoneyFlowWidget(parent_mdi), maximized=False)

    @Slot()
    def OnFileBtn(self):
        selector = (self.tr("Save money flow report to:"), self.tr("Excel files (*.xlsx)"), '.xlsx', self.ui.XlsFileName)
        folder = JalSettings().getRecentFolder(FolderFor.Report, '.')
        filename = QFileDialog.getSaveFileName(self, selector[0], folder, selector[1])
        if filename[0]:
            if filename[1] == selector[1] and filename[0][-len(selector[2]):] != selector[2]:
                selector[3].setText(filename[0] + selector[2])
            else:
                selector[3].setText(filename[0])
            JalSettings().setRecentFolder(FolderFor.Report, filename[0])

    def getYear(self):
        return self.ui.Year.value()

    def getXlsFilename(self):
        return self.ui.XlsFileName.text()

    year = Property(int, fget=getYear)
    xls_filename = Property(str, fget=getXlsFilename)

    @Slot()
    def SaveReport(self):
        taxes_flow = TaxesFlowRus()
        flow_report = taxes_flow.prepare_flow_report(self.year)

        reports_xls = XLSX(self.xls_filename)
        parameters = {
            "period": f"{ts2d(taxes_flow.year_begin)} - {ts2d(taxes_flow.year_end - 1)}"
        }
        reports_xls.output_data(flow_report, "tax_rus_flow.json", parameters)
        reports_xls.save()

        logging.info(self.tr("Money flow report saved to file ") + f"'{self.xls_filename}'")
        self.close()
