from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QDateTime, QDate
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QDialog, QMessageBox
from jal.db.helpers import load_icon
from jal.ui.reports.ui_portfolio_report import Ui_PortfolioWidget
from jal.reports.reports import Reports
from jal.db.asset import JalAsset
from jal.db.holdings_model import HoldingsModel
from jal.widgets.mdi import MdiWidget
from jal.db.tax_estimator import TaxEstimator
from jal.widgets.price_chart import ChartWindow
from jal.widgets.selection_dialog import SelectTagDialog

JAL_REPORT_CLASS = "AssetPortfolioReport"


# ----------------------------------------------------------------------------------------------------------------------
class AssetPortfolioReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Asset portfolio")
        self.window_class = "PortfolioReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class PortfolioReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_PortfolioWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Asset Portfolio")

        # Add available groupings
        self.ui.GroupCombo.addItem(self.tr("Currency - Account"), "currency_id;account_id")
        self.ui.GroupCombo.addItem(self.tr("Asset"), "asset_id")
        self.ui.GroupCombo.addItem(self.tr("Country"), "country_id")
        self.ui.GroupCombo.addItem(self.tr("Tag"), "tag")
        self.ui.GroupCombo.addItem("None", "")

        self.holdings_model = HoldingsModel(self.ui.PortfolioTreeView)
        self.ui.PortfolioTreeView.setModel(self.holdings_model)
        self.ui.PortfolioTreeView.setContextMenuPolicy(Qt.CustomContextMenu)

        # Setup holdings parameters
        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)  # We use UTC everywhere so need to force TZ info
        self.ui.PortfolioDate.setDateTime(current_time)
        self.ui.PortfolioCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.PortfolioDate.dateChanged.connect(self.updateReport)
        self.ui.PortfolioCurrencyCombo.changed.connect(self.updateReport)
        self.ui.PortfolioTreeView.customContextMenuRequested.connect(self.onHoldingsContextMenu)
        self.ui.GroupCombo.currentIndexChanged.connect(self.updateReport)
        self.ui.ShowInactiveAccounts.toggled.connect(self.updateReport)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.PortfolioTreeView.model()))

    @Slot()
    def updateReport(self):
        self.ui.PortfolioTreeView.model().updateView(currency_id = self.ui.PortfolioCurrencyCombo.selected_id,
                                                     date = self.ui.PortfolioDate.date(),
                                                     grouping = self.ui.GroupCombo.currentData(),
                                                     show_inactive = self.ui.ShowInactiveAccounts.isChecked())

    @Slot()
    def onHoldingsContextMenu(self, pos):
        index = self.ui.PortfolioTreeView.indexAt(pos)
        contextMenu = QMenu(self.ui.PortfolioTreeView)
        actionShowChart = QAction(icon=load_icon("chart.png"), text=self.tr("Show Price Chart"), parent=self.ui.PortfolioTreeView)
        actionShowChart.triggered.connect(partial(self.showPriceChart, index))
        contextMenu.addAction(actionShowChart)
        tax_submenu = contextMenu.addMenu(load_icon("tax.png"), self.tr("Estimate tax"))
        actionEstimateTaxPt = QAction(icon=load_icon("pt.png"), text=self.tr("Portugal"), parent=self.ui.PortfolioTreeView)
        actionEstimateTaxPt.triggered.connect(partial(self.estimateRussianTax, index, 'pt'))
        tax_submenu.addAction(actionEstimateTaxPt)
        actionEstimateTaxRu = QAction(icon=load_icon("ru.png"), text=self.tr("Russia"), parent=self.ui.PortfolioTreeView)
        actionEstimateTaxRu.triggered.connect(partial(self.estimateRussianTax, index, 'ru'))
        tax_submenu.addAction(actionEstimateTaxRu)
        contextMenu.addSeparator()
        actionSetTag = QAction(icon=load_icon("tag.png"), text=self.tr("Set asset tag"), parent=self.ui.PortfolioTreeView)
        actionSetTag.triggered.connect(partial(self.setTag, index))
        contextMenu.addAction(actionSetTag)
        contextMenu.addSeparator()
        actionExpandAll = QAction(text=self.tr("Expand all"),parent=self.ui.PortfolioTreeView)
        actionExpandAll.triggered.connect(self.ui.PortfolioTreeView.expandAll)
        contextMenu.addAction(actionExpandAll)
        actionCollapseAll = QAction(text=self.tr("Collapse all"), parent=self.ui.PortfolioTreeView)
        actionCollapseAll.triggered.connect(self.ui.PortfolioTreeView.collapseAll)
        contextMenu.addAction(actionCollapseAll)
        contextMenu.popup(self.ui.PortfolioTreeView.viewport().mapToGlobal(pos))

    @Slot()
    def showPriceChart(self, index):
        model = index.model()
        account, asset, currency, asset_qty = model.get_data_for_tax(index)
        self._parent.mdi_area().addSubWindow(ChartWindow(account, asset, currency, asset_qty))

    @Slot()
    def estimateRussianTax(self, index, country_code):
        if self.ui.PortfolioDate.date() != QDate().currentDate():
            QMessageBox().warning(self, self.tr("Warning"), self.tr("Tax estimation is possible for today only. Please correct date of the report"), QMessageBox.Ok)
            return
        model = index.model()
        account, asset, currency, asset_qty = model.get_data_for_tax(index)
        self._parent.mdi_area().addSubWindow(TaxEstimator(country_code, account, asset, asset_qty), size=(1000, 300))

    @Slot()
    def setTag(self, index):
        model = index.model()
        account, asset_id, currency, asset_qty = model.get_data_for_tax(index)
        asset = JalAsset(asset_id)
        dialog = SelectTagDialog(
            parent=self, description=self.tr("Select tag for {} ({}): ").format(asset.symbol(currency),asset.name()))
        if dialog.exec() != QDialog.Accepted:
            return
        asset.set_tag(dialog.selected_id)
