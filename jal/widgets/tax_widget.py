from functools import partial
from datetime import datetime, timezone
import logging
import traceback
import json

from PySide6.QtCore import Property, Slot, Signal, Qt, QDate, QCoreApplication
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication, QDialog, QListWidgetItem, QWidget, \
    QCheckBox, QComboBox, QLabel

from jal.ui.ui_tax_export_widget import Ui_TaxWidget
from jal.ui.ui_flow_export_widget import Ui_MoneyFlowWidget
from jal.ui.ui_merge_dialog import Ui_MergeFilesToolDialog
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import reading2d
from jal.widgets.icons import JalIcon
from jal.db.account import JalAccount
from jal.db.peer import JalPeer
from jal.db.settings import JalSettings, FolderFor
from jal.constants import PredefinedAgents
from jal.data_export.taxes import TaxReport, TaxReportStop, TaxReportCancelled
from jal.data_export.tax_parameters import TAX_TREATY
from jal.data_export.tax_options import OptionType, TR_CONTEXT
from jal.data_export.xlsx import XLSX
from jal.data_export.ru_ndfl3 import Ru_NDFL3


# ----------------------------------------------------------------------------------------------------------------------
# Export file types
class FileType:
    XLS = 0
    FORM = 1   # the tax form file of the jurisdiction


REPORT, FORM = "report", "form"   # what an option of the dialog belongs to


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
        self._derived = {}     # {jurisdiction: [periods]} each derives from the residence table for the year
        self._unticked = set()  # ids of the accounts the user unticked

        self._editors = {}     # {(jurisdiction, REPORT or FORM, key): editor} of every declared option
        self._rows = {}        # {jurisdiction: [widgets]} of its options, shown for it alone
        self.ui.Country.clear()
        for code, jurisdiction in TaxReport.jurisdictions.items():
            self.ui.Country.addItem(JalIcon.country_flag(code), jurisdiction['name'], code)
            self._build_options(code)
        self.ui.Country.currentIndexChanged.connect(self.OnCountryChange)
        self.ui.Year.valueChanged.connect(self.OnYearChange)
        self.ui.PeriodFrom.dateChanged.connect(self.OnPeriodChange)
        self.ui.PeriodTo.dateChanged.connect(self.OnPeriodChange)
        self.ui.Year.setValue(datetime.now().year - 1)   # Set previous year by default
        self.ui.XlsSelectBtn.pressed.connect(partial(self.OnFileBtn, FileType.XLS))
        self.ui.FormSelectBtn.pressed.connect(partial(self.OnFileBtn, FileType.FORM))
        self.ui.SaveButton.pressed.connect(self.SaveReport)
        self.ui.Country.setCurrentIndex(self.ui.Country.findData('ru'))
        self.OnYearChange(self.ui.Year.value())
        self._close_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._close_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._close_shortcut.activated.connect(self.close)

    # Builds the editors of the options a jurisdiction's report and form file declare
    def _build_options(self, code: str):
        self._rows[code] = []
        form = TaxReport.form_class(code)
        for option in TaxReport.report_class(code).options:
            self._add_option(self.ui.ReportOptionsLayout, self.ui.OptionsBox, code, REPORT, option)
        for option in ([] if form is None else form.options):
            self._add_option(self.ui.FormLayout, self.ui.FormGroup, code, FORM, option)

    # An option as the next row of a 3-column grid: a check box, or a label and a list; its comment under it
    def _add_option(self, layout, parent: QWidget, code: str, group: str, option):
        row = layout.rowCount() if layout.count() else 0   # an empty grid counts one row
        if option.type == OptionType.Choice:
            label, editor = QLabel(option.translated_label(), parent), QComboBox(parent)
            for value, text in option.translated_choices():
                editor.addItem(text, userData=value)
            editor.setCurrentIndex(max(editor.findData(option.default), 0))
            label.setBuddy(editor)
            layout.addWidget(label, row, 0)
            layout.addWidget(editor, row, 1, 1, 2)
            widgets = [label, editor]
        else:
            editor = QCheckBox(option.translated_label(), parent)
            editor.setChecked(option.default)
            layout.addWidget(editor, row, 0, 1, 3)
            widgets = [editor]
        if option.comment:
            widgets.append(QLabel(option.translated_comment(), parent))
            layout.addWidget(widgets[-1], row + 1, 0, 1, 3)
        self._editors[(code, group, option.key)] = editor
        self._rows[code] += widgets

    # {key: value} of the selected jurisdiction's options of a group
    def option_values(self, group: str) -> dict:
        return {key: editor.currentData() if isinstance(editor, QComboBox) else editor.isChecked()
                for (code, kind, key), editor in self._editors.items() if code == self.country and kind == group}

    # Shows the options of the selected jurisdiction and its form file, unticked; one without either shows no box
    def OnCountryChange(self, _index):
        form = TaxReport.form_class(self.country)
        for code, widgets in self._rows.items():
            for widget in widgets:
                widget.setVisible(code == self.country)
        self.ui.FormGroup.setVisible(form is not None)
        self.ui.FormGroup.setChecked(False)
        self.ui.FormFileName.clear()
        if form is not None:
            self.ui.FormGroup.setTitle(QCoreApplication.translate(TR_CONTEXT, form.title))
        self.ui.OptionsBox.setVisible(form is not None or bool(self._rows[self.country]))
        chain = [self.ui.XlsSelectBtn] + self._shown_editors(REPORT) + \
                [self.ui.FormGroup, self.ui.FormFileName, self.ui.FormSelectBtn] + self._shown_editors(FORM) + \
                [self.ui.SaveButton]
        for previous, following in zip(chain, chain[1:]):
            QWidget.setTabOrder(previous, following)
        self._propose_period()
        # A window of its own may follow the size of the country block it shows, a tab may not
        if self.isWindow():
            self.update()
            QApplication.processEvents()
            self.adjustSize()

    def _shown_editors(self, group: str) -> list:
        return [editor for (code, kind, _), editor in self._editors.items() if code == self.country and kind == group]

    def OnYearChange(self, _year):
        self._propose_period()

    # The period is held inside the year and reset to the first period the jurisdiction derives from the residence
    # table, or to the whole year
    def _propose_period(self):
        if self.country is None:
            return
        self._derived = {x: TaxReport.create_report(x).resident_periods(self.year) or [] for x in TaxReport.jurisdictions}
        periods = self._derived[self.country]
        begin, end = periods[0] if periods else TaxReport.year_window(self.year)
        first, last = QDate(self.year, 1, 1), QDate(self.year, 12, 31)
        for edit, moment in ((self.ui.PeriodFrom, begin), (self.ui.PeriodTo, end - 86400)):
            edit.blockSignals(True)
            edit.setDateRange(first, last)
            edit.setDate(self._day(moment))
            edit.blockSignals(False)
        self.OnPeriodChange()

    # Names the periods the jurisdiction derives, then those of any other jurisdiction that overlap the chosen period
    def _show_residence(self):
        periods = lambda spans: ", ".join(f"{reading2d(x)} - {reading2d(y - 1)}" for x, y in spans)
        lines = []
        if self._derived.get(self.country):
            lines += [self.tr("Resident by the residence table:"), periods(self._derived[self.country])]
        for code, spans in self._derived.items():
            overlap = [(x, y) for x, y in spans if x < self.period_end and self.period_begin < y]
            if code != self.country and overlap:
                lines.append(self.tr("Also resident in {country}: ").format(
                    country=TaxReport.jurisdictions[code]['name']) + periods(overlap))
        self.ui.ResidenceLbl.setText("\n".join(lines))
        self.ui.ResidenceLbl.setVisible(bool(lines))

    # Keeps From <= To, names the residences and lists the accounts with a tax event in the period, all ticked but those
    # the user unticked
    def OnPeriodChange(self, _date=None):
        self.ui.PeriodTo.setMinimumDate(self.ui.PeriodFrom.date())
        self.ui.PeriodFrom.setMaximumDate(self.ui.PeriodTo.date())
        self._show_residence()
        for i in range(self.ui.Accounts.count()):
            item = self.ui.Accounts.item(i)
            if item.checkState() == Qt.Unchecked:
                self._unticked.add(item.data(Qt.UserRole))
            else:
                self._unticked.discard(item.data(Qt.UserRole))
        self.ui.Accounts.clear()
        for account in JalAccount.get_taxable_accounts(self.period_begin, self.period_end):
            item = QListWidgetItem(account.name(), self.ui.Accounts)
            item.setData(Qt.UserRole, account.id())
            item.setCheckState(Qt.Unchecked if account.id() in self._unticked else Qt.Checked)

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
        elif type == FileType.FORM:
            form = TaxReport.form_class(self.country)
            file_filter, extension = form.file_type(self.year)
            selector = (QCoreApplication.translate(TR_CONTEXT, form.file_prompt),
                        QCoreApplication.translate(TR_CONTEXT, file_filter), extension, self.ui.FormFileName)
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

    @staticmethod
    def _midnight(day: QDate) -> int:
        return int(datetime(day.year(), day.month(), day.day(), tzinfo=timezone.utc).timestamp())

    @staticmethod
    def _day(timestamp: int) -> QDate:
        day = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return QDate(day.year, day.month, day.day)

    year = Property(int, fget=lambda self: self.ui.Year.value())
    period_begin = Property(int, fget=lambda self: self._midnight(self.ui.PeriodFrom.date()))
    period_end = Property(int, fget=lambda self: self._midnight(self.ui.PeriodTo.date().addDays(1)))   # half-open
    country = Property(str, fget=lambda self: self.ui.Country.currentData())
    xls_filename = Property(str, fget=lambda self: self.ui.XlsFileName.text())
    accounts = Property(list, fget=lambda self: [self.ui.Accounts.item(i).data(Qt.UserRole)
                                                 for i in range(self.ui.Accounts.count())
                                                 if self.ui.Accounts.item(i).checkState() == Qt.Checked])
    update_form = Property(bool, fget=lambda self: self.ui.FormGroup.isVisibleTo(self) and self.ui.FormGroup.isChecked())
    form_filename = Property(str, fget=lambda self: self.ui.FormFileName.text())

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
            return taxes.prepare_tax_report(self.year, self.accounts, period=(self.period_begin, self.period_end),
                                            progress=progress, **self.option_values(REPORT))
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
        if not self.accounts:
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
        parameters = taxes.sheet_parameters()
        parameters["period"] = f"{reading2d(taxes.period_begin)} - {reading2d(taxes.period_end - 1)}"
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

        if self.update_form:
            form = TaxReport.form_class(self.country)
            if form.needs_broker and not all(self._warn_missing_broker(x) for x in taxes.accounts):
                return
            filename = self.form_filename
            try:
                tax_forms = form(self.year, **self.option_values(FORM))
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
