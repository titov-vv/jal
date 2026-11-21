from functools import partial

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QInputDialog

from jal.db.asset import JalAsset
from jal.db.chain_balance import JalChainBalance
from jal.db.clock import day_finish
from jal.db.common_models import TagTreeModel
from jal.db.country import JalCountry
from jal.widgets.accrual_chart import AccrualChartWindow, ReceivableChartWindow
from jal.widgets.icons import JalIcon
from jal.widgets.position_details import PositionDetails
from jal.widgets.reference_dialogs import TagsListDialog
from jal.widgets.selection_dialog import SelectReferenceDialog


# ----------------------------------------------------------------------------------------------------------------------
# What a context menu offers on a row of a holdings list. 'date' answers the date of the list as a QDate and
# 'add_window' shows a window the way TabbedWindowArea.addWindow() does.
class HoldingsMenu(QObject):
    def __init__(self, view, date, add_window):
        super().__init__(view)
        self._view = view
        self._date = date
        self._add_window = add_window

    # Adds to 'menu' what the row at 'index' allows, nothing if it allows nothing
    def add_actions(self, menu, index) -> None:
        model = index.model()
        source = model.claim_source(index)
        if source:
            action = QAction(icon=JalIcon[JalIcon.CHART], text=self.tr("Show claim history"), parent=self._view)
            action.triggered.connect(partial(self.showClaimHistory, index, source))
            menu.addAction(action)
            return
        if not model.is_position(index):
            return
        actionDetails = QAction(icon=JalIcon[JalIcon.CHART], text=self.tr("Position details…"), parent=self._view)
        actionDetails.triggered.connect(partial(self.showPositionDetails, index))
        menu.addAction(actionDetails)
        # Offered beside the position details: one draws what a unit is worth, the other how many units appeared
        # with no operation behind them - only for positions whose balance is read from a chain.
        if self._has_accrual_history(index):
            actionAccrual = QAction(icon=JalIcon[JalIcon.CHART], text=self.tr("Show Accrual Chart"), parent=self._view)
            actionAccrual.triggered.connect(partial(self.showAccrualChart, index))
            menu.addAction(actionAccrual)
        menu.addSeparator()
        if model.get_data_for_tax(index)[1]:   # a group row names no asset
            actionSetTag = QAction(icon=JalIcon[JalIcon.TAG], text=self.tr("Set asset tag"), parent=self._view)
            actionSetTag.triggered.connect(partial(self.setTag, index))
            menu.addAction(actionSetTag)
            actionSetCountry = QAction(text=self.tr("Set asset country"), parent=self._view)
            actionSetCountry.triggered.connect(partial(self.setCountry, index))
            menu.addAction(actionSetCountry)
            menu.addSeparator()

    @Slot()
    def showPositionDetails(self, index):
        account, asset, currency, _qty = index.model().get_data_for_tax(index)
        self._add_window(PositionDetails(account, asset, currency, day_finish(self._date())), floating=True,
                         size=(1100, 560))

    # True when this row's position has been measured on chain more than once - anything less has no line to draw
    def _has_accrual_history(self, index) -> bool:
        account, asset, _currency, _qty = index.model().get_data_for_tax(index)
        return len(JalChainBalance().history(account, asset)) > 1

    @Slot()
    def showAccrualChart(self, index):
        account, asset, _currency, _qty = index.model().get_data_for_tax(index)
        self._add_window(AccrualChartWindow(account, asset), floating=True)

    @Slot()
    def showClaimHistory(self, index, source):
        account, asset, _currency, _qty = index.model().get_data_for_tax(index)
        self._add_window(ReceivableChartWindow(account, asset, source), floating=True)

    @Slot()
    def setTag(self, index):
        model = index.model()
        _account, asset_id, currency, _qty = model.get_data_for_tax(index)
        asset = JalAsset(asset_id)
        dialog = SelectReferenceDialog(self._view, self.tr("Please select tag"),
                                       self.tr("Select tag for {} ({}): ").format(asset.symbol(currency or None), asset.name()),
                                       TagTreeModel, TagsListDialog)
        if dialog.exec() != QDialog.Accepted:
            return
        asset.set_tag(dialog.selected_id)
        model.prepareData()   # the tag is a grouping of the report

    @Slot()
    def setCountry(self, index):
        model = index.model()
        _account, asset_id, currency, _qty = model.get_data_for_tax(index)
        asset = JalAsset(asset_id)
        countries = JalCountry.names()
        current = list(countries).index(asset.country().id()) if asset.country().id() in countries else 0
        name, accepted = QInputDialog.getItem(self._view, self.tr("Please select country"),
                                              self.tr("Select country for {} ({}): ").format(asset.symbol(currency or None), asset.name()),
                                              list(countries.values()), current, False)
        if not accepted:
            return
        asset.set_country(list(countries)[list(countries.values()).index(name)])
        model.prepareData()   # the country is a grouping of the report
