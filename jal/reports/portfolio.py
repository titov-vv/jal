from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QDate
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QDialog, QMessageBox
from jal.ui.reports.ui_portfolio_report import Ui_PortfolioWidget
from jal.reports.reports import Reports
from jal.constants import AccountStatus
from jal.db.clock import day_finish, now_dt
from jal.db.asset import JalAsset
from jal.db.holdings_model import HoldingsModel
from jal.widgets.mdi import MdiWidget
from jal.db.tax_estimator import TaxEstimator
from jal.db.common_models import TagTreeModel
from jal.widgets.icons import JalIcon
from jal.db.chain_balance import JalChainBalance
from jal.widgets.accrual_chart import AccrualChartWindow
from jal.widgets.price_chart import ChartWindow
from jal.widgets.selection_dialog import SelectReferenceDialog
from jal.widgets.reference_dialogs import TagsListDialog
from jal.widgets.helpers import set_grids_metrics

JAL_REPORT_CLASS = "AssetPortfolioReport"


# ----------------------------------------------------------------------------------------------------------------------
class AssetPortfolioReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Asset &portfolio")
        self.window_class = "PortfolioReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class PortfolioReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_PortfolioWidget()
        self.ui.setupUi(self)
        set_grids_metrics(self)
        self._parent = parent
        self.name = self.tr("Asset portfolio")

        # Add available groupings
        self.ui.GroupCombo.addItem(self.tr("Currency - Account"), "currency_id;account_id")
        self.ui.GroupCombo.addItem(self.tr("Currency - Asset"), "currency_id;asset_id")
        self.ui.GroupCombo.addItem(self.tr("Asset"), "asset_id")
        self.ui.GroupCombo.addItem(self.tr("Country"), "country_id")
        self.ui.GroupCombo.addItem(self.tr("Country - Asset"), "country_id;asset_id")
        self.ui.GroupCombo.addItem(self.tr("Tag"), "tag")
        self.ui.GroupCombo.addItem(self.tr("Account tag - Account"), "account_tag_id;account_id")
        self.ui.GroupCombo.addItem(self.tr("Status - Account"), "status_id;account_id")
        self.ui.GroupCombo.addItem(self.tr("Status - Currency - Account"), "status_id;currency_id;account_id")
        self.ui.GroupCombo.addItem("None", "")

        # How deep into AccountStatus the report reaches. The views nest, so this is one choice and not a set of
        # switches: each entry shows a status and everything above it.
        for min_status, name in AccountStatus().visibility_names().items():
            self.ui.AccountsCombo.addItem(name, min_status)

        self.ui.AccountsCombo.setCurrentIndex(self.ui.AccountsCombo.findData(AccountStatus.Background))
        self.ui.GroupCombo.setCurrentIndex(self.ui.GroupCombo.findData("status_id;currency_id;account_id"))

        self.holdings_model = HoldingsModel(self.ui.PortfolioTreeView)
        self.ui.PortfolioTreeView.setModel(self.holdings_model)
        self.ui.PortfolioTreeView.setContextMenuPolicy(Qt.CustomContextMenu)
        # A folded group the reader opens stays open through the rebuilds a ledger update triggers
        self.ui.PortfolioTreeView.expanded.connect(partial(self.holdings_model.setGroupExpanded, expanded=True))
        self.ui.PortfolioTreeView.collapsed.connect(partial(self.holdings_model.setGroupExpanded, expanded=False))

        # Setup holdings parameters
        self.ui.PortfolioDate.setDate(now_dt().date())
        self.ui.PortfolioCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.PortfolioDate.dateChanged.connect(self.updateReport)
        self.ui.PortfolioCurrencyCombo.changed.connect(self.updateReport)
        self.ui.PortfolioTreeView.customContextMenuRequested.connect(self.onHoldingsContextMenu)
        self.ui.GroupCombo.currentIndexChanged.connect(self.updateReport)
        self.ui.AccountsCombo.currentIndexChanged.connect(self.updateReport)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.PortfolioTreeView.model()))

    @Slot()
    def updateReport(self):
        self.ui.PortfolioTreeView.model().updateView(currency_id = self.ui.PortfolioCurrencyCombo.selected_id,
                                                     date = self.ui.PortfolioDate.date(),
                                                     grouping = self.ui.GroupCombo.currentData(),
                                                     min_status = self.ui.AccountsCombo.currentData())

    @Slot()
    def onHoldingsContextMenu(self, pos):
        index = self.ui.PortfolioTreeView.indexAt(pos)
        contextMenu = QMenu(self.ui.PortfolioTreeView)
        if index.isValid():
            actionShowChart = QAction(icon=JalIcon[JalIcon.CHART], text=self.tr("Show Price Chart"), parent=self.ui.PortfolioTreeView)
            actionShowChart.triggered.connect(partial(self.showPriceChart, index))
            contextMenu.addAction(actionShowChart)
            # Offered beside the price chart because they are the two independent halves of what a position did: one
            # draws what a unit is worth, the other how many units appeared with no operation behind them. It is
            # shown only where there is something to draw - i.e. for the handful of positions whose balance is read
            # from a chain at all.
            if self._has_accrual_history(index):
                actionAccrual = QAction(icon=JalIcon[JalIcon.CHART], text=self.tr("Show Accrual Chart"),
                                        parent=self.ui.PortfolioTreeView)
                actionAccrual.triggered.connect(partial(self.showAccrualChart, index))
                contextMenu.addAction(actionAccrual)
            tax_submenu = contextMenu.addMenu(JalIcon[JalIcon.TAX], self.tr("Estimate tax"))
            actionEstimateTaxPt = QAction(icon=JalIcon.country_flag('pt'), text=self.tr("Portugal"), parent=self.ui.PortfolioTreeView)
            actionEstimateTaxPt.triggered.connect(partial(self.estimateSaleTax, index, 'pt'))
            tax_submenu.addAction(actionEstimateTaxPt)
            actionEstimateTaxRu = QAction(icon=JalIcon.country_flag('ru'), text=self.tr("Russia"), parent=self.ui.PortfolioTreeView)
            actionEstimateTaxRu.triggered.connect(partial(self.estimateSaleTax, index, 'ru'))
            tax_submenu.addAction(actionEstimateTaxRu)
            contextMenu.addSeparator()
            actionSetTag = QAction(icon=JalIcon[JalIcon.TAG], text=self.tr("Set asset tag"), parent=self.ui.PortfolioTreeView)
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
        self._parent.mdi_area().addWindow(ChartWindow(account, asset, currency, day_finish(self.ui.PortfolioDate.date())), floating=True)

    # True when this row's position has been measured on chain more than once - anything less has no line to draw
    def _has_accrual_history(self, index) -> bool:
        account, asset, _currency, _qty = index.model().get_data_for_tax(index)
        return len(JalChainBalance().history(account, asset)) > 1

    @Slot()
    def showAccrualChart(self, index):
        account, asset, _currency, _qty = index.model().get_data_for_tax(index)
        self._parent.mdi_area().addWindow(AccrualChartWindow(account, asset), floating=True)

    @Slot()
    def estimateSaleTax(self, index, country_code):
        if self.ui.PortfolioDate.date() != QDate().currentDate():
            QMessageBox().warning(self, self.tr("Warning"), self.tr("Tax estimation is possible for today only. Please correct date of the report"), QMessageBox.Ok)
            return
        model = index.model()
        account, asset, currency, asset_qty = model.get_data_for_tax(index)
        self._parent.mdi_area().addWindow(TaxEstimator(country_code, account, asset, asset_qty), floating=True, size=(1000, 300))

    @Slot()
    def setTag(self, index):
        model = index.model()
        account, asset_id, currency, asset_qty = model.get_data_for_tax(index)
        asset = JalAsset(asset_id)
        dialog = SelectReferenceDialog(self, self.tr("Please select tag"),
                                       self.tr("Select tag for {} ({}): ").format(asset.symbol(currency),asset.name()),
                                       TagTreeModel, TagsListDialog)
        if dialog.exec() != QDialog.Accepted:
            return
        asset.set_tag(dialog.selected_id)
