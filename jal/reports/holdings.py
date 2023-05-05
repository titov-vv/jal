from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QDateTime
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QDialog
from jal.db.helpers import load_icon
from jal.ui.reports.ui_holdings_report import Ui_HoldingsWidget
from jal.reports.reports import Reports
from jal.db.asset import JalAsset
from jal.db.holdings_model import HoldingsModel
from jal.widgets.mdi import MdiWidget
from jal.db.tax_estimator import TaxEstimator
from jal.widgets.price_chart import ChartWindow
from jal.widgets.selection_dialog import SelectTagDialog

JAL_REPORT_CLASS = "HoldingsReport"


# ----------------------------------------------------------------------------------------------------------------------
class HoldingsReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Holdings")
        self.window_class = "HoldingsReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class HoldingsReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_HoldingsWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Holdings")

        # Add available groupings
        self.ui.GroupCombo.addItem(self.tr("Currency - Account"), "currency_id;account_id")
        self.ui.GroupCombo.addItem(self.tr("Asset"), "asset_id")
        self.ui.GroupCombo.addItem(self.tr("Country"), "country_id")
        self.ui.GroupCombo.addItem(self.tr("Tag"), "tag")
        self.ui.GroupCombo.addItem("None", "")

        self.holdings_model = HoldingsModel(self.ui.HoldingsTreeView)
        self.ui.HoldingsTreeView.setModel(self.holdings_model)
        self.ui.HoldingsTreeView.setContextMenuPolicy(Qt.CustomContextMenu)

        # Setup holdings parameters
        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)  # We use UTC everywhere so need to force TZ info
        self.ui.HoldingsDate.setDateTime(current_time)
        self.ui.HoldingsCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.HoldingsDate.dateChanged.connect(self.updateReport)
        self.ui.HoldingsCurrencyCombo.changed.connect(self.updateReport)
        self.ui.HoldingsTreeView.customContextMenuRequested.connect(self.onHoldingsContextMenu)
        self.ui.GroupCombo.currentIndexChanged.connect(self.updateReport)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.HoldingsTreeView.model()))

    @Slot()
    def updateReport(self):
        self.ui.HoldingsTreeView.model().updateView(currency_id = self.ui.HoldingsCurrencyCombo.selected_id,
                                                    date = self.ui.HoldingsDate.date(),
                                                    grouping = self.ui.GroupCombo.currentData())

    @Slot()
    def onHoldingsContextMenu(self, pos):
        index = self.ui.HoldingsTreeView.indexAt(pos)
        contextMenu = QMenu(self.ui.HoldingsTreeView)
        actionShowChart = QAction(icon=load_icon("chart.png"), text=self.tr("Show Price Chart"), parent=self.ui.HoldingsTreeView)
        actionShowChart.triggered.connect(partial(self.showPriceChart, index))
        contextMenu.addAction(actionShowChart)
        tax_submenu = contextMenu.addMenu(load_icon("tax.png"), self.tr("Estimate tax"))
        actionEstimateTaxPt = QAction(icon=load_icon("pt.png"), text=self.tr("Portugal"), parent=self.ui.HoldingsTreeView)
        actionEstimateTaxPt.triggered.connect(partial(self.estimateRussianTax, index, 'pt'))
        tax_submenu.addAction(actionEstimateTaxPt)
        actionEstimateTaxRu = QAction(icon=load_icon("ru.png"), text=self.tr("Russia"), parent=self.ui.HoldingsTreeView)
        actionEstimateTaxRu.triggered.connect(partial(self.estimateRussianTax, index, 'ru'))
        tax_submenu.addAction(actionEstimateTaxRu)
        contextMenu.addSeparator()
        actionSetTag = QAction(icon=load_icon("tag.png"), text=self.tr("Set asset tag"), parent=self.ui.HoldingsTreeView)
        actionSetTag.triggered.connect(partial(self.setTag, index))
        contextMenu.addAction(actionSetTag)
        contextMenu.addSeparator()
        actionExpandAll = QAction(text=self.tr("Expand all"),parent=self.ui.HoldingsTreeView)
        actionExpandAll.triggered.connect(self.ui.HoldingsTreeView.expandAll)
        contextMenu.addAction(actionExpandAll)
        actionCollapseAll = QAction(text=self.tr("Collapse all"), parent=self.ui.HoldingsTreeView)
        actionCollapseAll.triggered.connect(self.ui.HoldingsTreeView.collapseAll)
        contextMenu.addAction(actionCollapseAll)
        contextMenu.popup(self.ui.HoldingsTreeView.viewport().mapToGlobal(pos))

    @Slot()
    def showPriceChart(self, index):
        model = index.model()
        account, asset, currency, asset_qty = model.get_data_for_tax(index)
        self._parent.mdi_area().addSubWindow(ChartWindow(account, asset, currency, asset_qty))

    @Slot()
    def estimateRussianTax(self, index, country_code):
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
