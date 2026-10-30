from functools import partial

from PySide6.QtCore import Qt, Slot, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from jal.ui.reports.ui_portfolio_report import Ui_PortfolioWidget
from jal.reports.reports import Reports
from jal.constants import AccountStatus
from jal.db.clock import now_dt
from jal.db.asset import JalAsset
from jal.db.holdings_model import HoldingsModel
from jal.widgets.mdi import MdiWidget
from jal.widgets.holdings_menu import HoldingsMenu
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
        self.holdings_menu = HoldingsMenu(self.ui.PortfolioTreeView, self.ui.PortfolioDate.date, self._add_window)
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

    def _add_window(self, *args, **kwargs):
        return self._parent.mdi_area().addWindow(*args, **kwargs)

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
            self.holdings_menu.add_actions(contextMenu, index)
        actionExpandAll = QAction(text=self.tr("Expand all"),parent=self.ui.PortfolioTreeView)
        actionExpandAll.triggered.connect(self.ui.PortfolioTreeView.expandAll)
        contextMenu.addAction(actionExpandAll)
        actionCollapseAll = QAction(text=self.tr("Collapse all"), parent=self.ui.PortfolioTreeView)
        actionCollapseAll.triggered.connect(self.ui.PortfolioTreeView.collapseAll)
        contextMenu.addAction(actionCollapseAll)
        for level in range(2, len(self.holdings_model.grouping()) + 1):   # level 1 is "Collapse all"
            actionLevel = QAction(text=self.tr("Expand to level {}").format(level), parent=self.ui.PortfolioTreeView)
            actionLevel.triggered.connect(partial(self.expandToLevel, level))
            contextMenu.addAction(actionLevel)
        contextMenu.popup(self.ui.PortfolioTreeView.viewport().mapToGlobal(pos))

    # Leaves exactly 'level' levels of group rows visible
    @Slot()
    def expandToLevel(self, level: int):
        self.ui.PortfolioTreeView.collapseAll()
        self.ui.PortfolioTreeView.expandToDepth(level - 2)
