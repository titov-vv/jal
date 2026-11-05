from functools import partial
from datetime import datetime
import logging
import traceback
import json

from PySide6.QtCore import Property, Slot, Signal, Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication, QDialog

from jal.ui.ui_tax_export_widget import Ui_TaxWidget
from jal.ui.ui_flow_export_widget import Ui_MoneyFlowWidget
from jal.ui.ui_merge_dialog import Ui_MergeFilesToolDialog
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import reading2d
from jal.widgets.icons import JalIcon
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.db.settings import JalSettings, FolderFor
from jal.constants import PredefinedAgents
from jal.data_export.taxes import TaxReport, TaxReportStop, TaxReportCancelled
from jal.data_export.tax_parameters import TAX_TREATY
from jal.data_export.xlsx import XLSX
from jal.data_export.ru_ndfl3 import Ru_NDFL3
from jal.data_export.irs_modelo3 import IRS_Modelo3


# ----------------------------------------------------------------------------------------------------------------------
# Export file types
class FileType:
    XLS = 0
    RU_Declaration_DE = 1
    PT_Modelo3_XML = 2


# ----------------------------------------------------------------------------------------------------------------------
class TaxWidget(MdiWidget):
    show_progress = Signal(bool)          # a report starts or ends, for the main window's progress bar
    update_progress = Signal(float)       # percent of the report done
    update_progress_text = Signal(str)    # the bar's text, with %p% for the percent

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_TaxWidget()
        self.ui.setupUi(self)
        self._report = None    # the report being prepared, see _prepare()

        self._option_boxes = {'pt': self.ui.PtBox, 'ru': self.ui.RuBox}
        self.ui.Country.clear()
        for code, jurisdiction in TaxReport.jurisdictions.items():
            self.ui.Country.addItem(JalIcon.country_flag(code), jurisdiction['name'], code)
        self.ui.Country.currentIndexChanged.connect(self.OnCountryChange)
        self.ui.Year.valueChanged.connect(self.OnYearChange)
        self.ui.Year.setValue(datetime.now().year - 1)   # Set previous year by default
        self.ui.XlsSelectBtn.pressed.connect(partial(self.OnFileBtn, FileType.XLS))
        self.ui.Ndfl3SelectBtn.pressed.connect(partial(self.OnFileBtn, FileType.RU_Declaration_DE))
        self.ui.IRS_Modelo3SelectBtn.pressed.connect(partial(self.OnFileBtn, FileType.PT_Modelo3_XML))
        self.ui.SaveButton.pressed.connect(self.SaveReport)
        self.ui.Country.setCurrentIndex(self.ui.Country.findData('ru'))
        self.OnYearChange(self.ui.Year.value())
        self._close_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._close_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._close_shortcut.activated.connect(self.close)

    # Shows the option box of the selected jurisdiction; one without options shows none
    def OnCountryChange(self, _index):
        for code, box in self._option_boxes.items():
            box.setVisible(code == self.country)
        # A window of its own may follow the size of the country block it shows, a tab may not
        if self.isWindow():
            self.update()
            QApplication.processEvents()
            self.adjustSize()

    # Load account combobox with account names relevant for the given year
    def OnYearChange(self, year):
        self.ui.Account.clear()
        accounts = JalAccount.get_taxable_accounts(year)
        for account in accounts:
            self.ui.Account.addItem(account.name(), account.id())

    # Displays tax widget in a given window area, its progress on 'main_window' if given.
    # It is implemented as a separate static method in order to prevent unexpected object deletion
    @staticmethod
    def showInWindowArea(parent_area, main_window=None):
        widget = TaxWidget()
        if main_window is not None:
            widget.show_progress.connect(main_window.onToggleProgressDisplay)
            widget.update_progress.connect(main_window.onUpdatePorgressDisplay)
            widget.update_progress_text.connect(main_window.onUpdateProgressText)
            main_window.CancelButton.clicked.connect(widget.on_cancel)
        parent_area.addWindow(widget, floating=True)

    @Slot()
    def OnFileBtn(self, type):
        if type == FileType.XLS:
            selector = (self.tr("Save tax reports to:"), self.tr("Excel files (*.xlsx)"), '.xlsx', self.ui.XlsFileName)
        elif type == FileType.RU_Declaration_DE:
            last_digit = self.year % 10
            selector = (self.tr("Save tax form to:"), self.tr(f"Tax form (*.de{last_digit})"), f".de{last_digit}", self.ui.Ndfl3FileName)
        elif type == FileType.PT_Modelo3_XML:
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
    country = Property(str, fget=lambda self: self.ui.Country.currentData())
    xls_filename = Property(str, fget=lambda self: self.ui.XlsFileName.text())
    account = Property(int, fget=lambda self: self.ui.Account.currentData())
    update_ndfl3 = Property(bool, fget=lambda self: self.ui.Ndfl3Group.isChecked())
    ndfl3_filename = Property(str, fget=lambda self: self.ui.Ndfl3FileName.text())
    ndfl3_broker_as_income = Property(bool, fget=lambda self: self.ui.Ru_IncomeSourceBroker.isChecked())
    ndfl3_dividends_only = Property(bool, fget=lambda self: self.ui.Ru_DividendsOnly.isChecked())
    use_one_rate = Property(bool, fget=lambda self: self.ui.Pt_OneCurrencyRate.isChecked())
    update_modelo3 = Property(bool, fget=lambda self: self.ui.IRS_Modelo3Group.isChecked())
    modelo3_filename = Property(str, fget=lambda self: self.ui.IRS_Modelo3Filename.text())
    no_settlement = Property(bool, fget=lambda self: self.ui.Ru_NoSettlement.isChecked())

    # The report with a busy cursor and the progress shown; the window is disabled meanwhile, as the main window
    # disables itself, since the events processed during the replay would let a second report start beside it
    def _prepare(self, taxes) -> dict:
        def progress(percent: float, text: str):
            self.update_progress_text.emit(text)
            self.update_progress.emit(percent)
            QApplication.processEvents()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.setEnabled(False)
        self._report = taxes
        self.show_progress.emit(True)
        try:
            return taxes.prepare_tax_report(self.year, self.account, use_one_currency_rate=self.use_one_rate,
                                            use_settlement=(not self.no_settlement), progress=progress)
        finally:
            self.show_progress.emit(False)
            self._report = None
            self.setEnabled(True)
            QApplication.restoreOverrideCursor()

    @Slot()
    def on_cancel(self):
        if self._report is not None:
            self._report.cancel()

    # A floating window may be closed by the window manager while disabled; it stays while its report runs
    @Slot()
    def closeEvent(self, event):
        if self._report is not None:
            event.ignore()
            return
        super().closeEvent(event)

    def _warn_missing_broker(self, account: JalAccount) -> bool:
        broker_id = account.organization()
        broker_name = JalPeer(broker_id).name() if broker_id else ''
        if broker_id and broker_id != PredefinedAgents.Empty and broker_name and broker_name.strip():
            return True
        warning = self.tr("Selected account isn't bound to a broker or broker name isn't set. "
                          "Tax form export may be incomplete.")
        logging.warning(warning)
        reply = QMessageBox().warning(self, self.tr("Warning"), warning, QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)
        return reply == QMessageBox.Ok

    # The report was made with parameters missing or not reviewed for its year; the Summary sheet says the same
    def _warn_parameters(self, parameters):
        if parameters.value(TAX_TREATY) is None:
            message = self.tr("There are no tax parameters for {year}: no tax treaty is assumed and no tax is "
                              "estimated").format(year=self.year)
        elif parameters.unreviewed():
            message = self.tr("The tax parameters (treaties, base rates) were last reviewed for {reviewed}; {year} "
                              "uses the latest values known - check them against the law").format(
                reviewed=parameters.reviewed_through(), year=self.year)
        else:
            return
        logging.warning(message)
        QMessageBox().warning(self, self.tr("Tax parameters"), message, QMessageBox.Ok)

    @Slot()
    def SaveReport(self):
        if not self.account:
            QMessageBox().warning(self, self.tr("Data are incomplete"),
                                  self.tr("You haven't selected an account for tax report"), QMessageBox.Ok)
            return
        taxes = TaxReport.create_report(self.country)
        try:
            tax_report = self._prepare(taxes)
        except TaxReportCancelled:
            logging.warning(self.tr("Interrupted by user"))
            return
        except TaxReportStop as stop:
            if stop.replay:
                message = self.tr("The tax replay of the lots stopped, correct the operation and save the report "
                                  "again:") + "\n" + stop.replay
                logging.error(message)
                QMessageBox().warning(self, self.tr("Tax replay stopped"), message, QMessageBox.Ok)
            if stop.missing:
                missing = "\n".join(f"{symbol} - {reading2d(timestamp)}" for symbol, timestamp in stop.missing)
                message = self.tr("The report needs these quotes or official currency rates, add them and save it again:") + "\n" + missing
                logging.error(message)
                QMessageBox().warning(self, self.tr("Quotes are missing"), message, QMessageBox.Ok)
            if stop.no_country:
                message = self.tr("The report needs the country of these assets, set it and save the report again:") + \
                          "\n" + "\n".join(stop.no_country)
                logging.error(message)
                QMessageBox().warning(self, self.tr("Countries are missing"), message, QMessageBox.Ok)
            return
        if not tax_report:
            logging.warning(self.tr("Tax report is empty"))
            return

        reports_xls = XLSX(self.xls_filename)
        parameters = {
            "period": f"{reading2d(taxes.year_begin)} - {reading2d(taxes.year_end - 1)}",
            "account": f"{taxes.account.number()} ({JalAsset(taxes.account.currency()).symbol()})",
            "account_name": taxes.account.name(),
            "currency": JalAsset(taxes.account.currency()).symbol(),
            "broker_name": JalPeer(taxes.account.organization()).name(),
            "broker_iso_country": taxes.account.country().iso_code()
        }
        for section in tax_report:
            reports_xls.output_data(tax_report[section], taxes.report_template(section), parameters,
                                    headers=taxes.section_headers(section))
        if reports_xls.save():
            logging.info(self.tr("Excel tax report was saved to file ") + f"'{self.xls_filename}'")
        if taxes.rates_warnings:
            lines = [f"{pair}: {reading2d(quoted)} - {reading2d(latest)}" for (pair, quoted), latest in sorted(taxes.rates_warnings.items())]
            message = self.tr("Official currency rates look missing in the database; these operations were converted "
                              "at an older rate (pair: rate date - latest operation):") + "\n" + "\n".join(lines) + \
                      "\n" + self.tr("Download the rates and save the report again.")
            logging.warning(message)
            QMessageBox().warning(self, self.tr("Currency rates are not up to date"), message, QMessageBox.Ok)
        self._warn_parameters(taxes.parameters)
        if taxes.short_warnings:
            message = self.tr("The report doesn't handle a short of these assets across the end of a year, check them "
                              "by hand:") + "\n" + "\n".join(taxes.short_warnings)
            logging.warning(message)
            QMessageBox().warning(self, self.tr("Shorts not handled"), message, QMessageBox.Ok)

        if self.update_ndfl3 or self.update_modelo3:
            if self.update_ndfl3 and not self._warn_missing_broker(taxes.account):
                return
            tax_forms = None
            try:
                if self.update_ndfl3:
                    tax_forms = Ru_NDFL3(self.year, broker_as_income=self.ndfl3_broker_as_income, only_dividends=self.ndfl3_dividends_only)
                    filename = self.ndfl3_filename
                if self.update_modelo3:
                    tax_forms = IRS_Modelo3(self.year)
                    filename = self.modelo3_filename
                tax_forms.update_taxes(tax_report, parameters)
            except ValueError as e:   # no form template or no code for the year
                logging.error(str(e))
                return
            try:
                tax_forms.save(filename)
                logging.info(self.tr("Tax report saved to file ") + f"'{filename}'")
            except:
                logging.error(self.tr("Can't write tax form into file ") + f"'{filename}'" +
                              f"\n{traceback.format_exc()}")


# ----------------------------------------------------------------------------------------------------------------------
class MoneyFlowWidget(MdiWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MoneyFlowWidget()
        self.ui.setupUi(self)

        self.ui.Year.setValue(datetime.now().year - 1)  # Set previous year by default
        self.ui.XlsSelectBtn.pressed.connect(self.OnFileBtn)
        self.ui.SaveButton.pressed.connect(self.SaveReport)

    # Displays money flow widget in a given window area.
    # It is implemented as a separate static method in order to prevent unexpected object deletion
    @staticmethod
    def showInWindowArea(parent_area):
        parent_area.addWindow(MoneyFlowWidget(parent_area), floating=True)

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
        taxes_flow = TaxReport.create_flow_report('ru')
        flow_report = taxes_flow.prepare_flow_report(self.year)

        reports_xls = XLSX(self.xls_filename)
        parameters = {
            "period": f"{reading2d(taxes_flow.year_begin)} - {reading2d(taxes_flow.year_end - 1)}"
        }
        reports_xls.output_data(flow_report, "tax_rus_flow.json", parameters)
        if reports_xls.save():
            logging.info(self.tr("Excel money flow report was saved to file ") + f"'{self.xls_filename}'")
            self.close()


# ----------------------------------------------------------------------------------------------------------------------
class TaxMergeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MergeFilesToolDialog()
        self.ui.setupUi(self)

        self.ui.AddBtn.setIcon(JalIcon[JalIcon.ADD])
        self.ui.RemoveBtn.setIcon(JalIcon[JalIcon.REMOVE])

        self.ui.AddBtn.clicked.connect(self.OnAdd)
        self.ui.RemoveBtn.clicked.connect(self.OnRemove)
        self.ui.OutputSelectBtn.clicked.connect(self.OnOutputSelect)

    # Add file name into the list of merged files
    @Slot()
    def OnAdd(self):
        filename = QFileDialog.getOpenFileName(self, self.tr("Select tax file to merge"),
                                                      '', self.tr("Declaration files (*.de5)"))
        if filename[0]:
            self.ui.InputFilesList.addItem(filename[0])

    # Removes currently selected filename from the list of merged files
    @Slot()
    def OnRemove(self):
        item = self.ui.InputFilesList.currentItem()
        if item is not None:
            self.ui.InputFilesList.takeItem(self.ui.InputFilesList.row(item))

    # Select a file to store a merged data
    @Slot()
    def OnOutputSelect(self):
        filename = QFileDialog.getSaveFileName(self, self.tr("Select file to save merged result"),
                                                     '', self.tr("Declaration files (*.de5)"))
        if filename[0]:
            self.ui.OutputFileName.setText(filename[0])

    @Slot()
    def accept(self):
        input_files = [self.ui.InputFilesList.item(i).text() for i in range(self.ui.InputFilesList.count())]
        output_file = self.ui.OutputFileName.text()
        try:
            merged_data = Ru_NDFL3.merge_de5(input_files)
            with open(output_file, 'w', encoding='utf-8') as out:
                json.dump(merged_data, out, ensure_ascii=False, indent=2)
            logging.info(self.tr("de5 files merged successfully: ") + output_file)
        except Exception as err:
            QMessageBox().warning(self, self.tr("Merge de5"), str(err), QMessageBox.Ok)
        super().accept()
