import base64
import logging
from PySide6.QtCore import Qt, Signal, Slot, QPoint
from PySide6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QMenu, QMessageBox
from jal.ui.ui_asset_list_dlg import Ui_AssetsListDialog
from jal.db.settings import JalSettings
from jal.db.asset import JalAsset
from jal.db.asset_models import SymbolsListModel
from jal.db.ledger import Ledger
from jal.db.symbol import JalSymbol
from jal.constants import CmWidth, PredefinedAsset, AssetLocation
from jal.widgets.delegates import ConstantLookupDelegate
from jal.widgets.icons import JalIcon
from jal.widgets.helpers import set_tables_row_height


# ----------------------------------------------------------------------------------------------------------------------
class SymbolListDialog(QDialog):
    selection_done = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_AssetsListDialog()
        self.ui.setupUi(self)
        set_tables_row_height(self)
        self._parent = parent
        self._type_id = None
        self._currency_id = None
        self._location_id = None
        self._search_text = ''
        self.selection_enabled = False
        self.model = SymbolsListModel(self)
        self.setup_ui()

        self.ui.AddBtn.setIcon(JalIcon[JalIcon.ADD])
        self.ui.EditBtn.setIcon(JalIcon[JalIcon.DETAILS])
        self.ui.RemoveBtn.setIcon(JalIcon[JalIcon.REMOVE])

        self.ui.AssetTypeCombo.currentIndexChanged.connect(self.subset_changed)
        self.ui.CurrencyCombo.currentIndexChanged.connect(self.subset_changed)
        self.ui.LocationCombo.currentIndexChanged.connect(self.subset_changed)
        self.ui.SearchString.textChanged.connect(self.search_changed)
        self.ui.DataView.doubleClicked.connect(self.OnDoubleClicked)
        self.ui.DataView.selectionModel().selectionChanged.connect(self.onRowSelected)
        self.ui.DialogButtonBox.accepted.connect(self.onDialogAccept)
        self.ui.DialogButtonBox.rejected.connect(self.onDialogReject)
        self.ui.AddBtn.clicked.connect(self.onAdd)
        self.ui.EditBtn.clicked.connect(self.onEdit)
        self.ui.RemoveBtn.clicked.connect(self.onRemove)
        self.ui.DataView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.DataView.customContextMenuRequested.connect(self.onContextMenu)

    def setup_ui(self):
        self.ui.DataView.setModel(self.model)
        self.ui.DataView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        PredefinedAsset().load2combo(self.ui.AssetTypeCombo)
        self.configureColumns()

        PredefinedAsset().load2combo(self.ui.AssetTypeCombo, with_empty=True)
        self.ui.CurrencyCombo.clear()
        self.ui.CurrencyCombo.addItem('', userData=None)
        for currency_id, symbol in sorted([(x.id(), x.symbol()) for x in JalAsset.get_currencies()], key=lambda x: x[1]):
            self.ui.CurrencyCombo.addItem(symbol, currency_id)
        AssetLocation().load2combo(self.ui.LocationCombo, with_empty=True)
        self._location_delegate = ConstantLookupDelegate(AssetLocation, self.ui.DataView)
        self.ui.DataView.setItemDelegateForColumn(self.model.fieldIndex("location_id"), self._location_delegate)

    @Slot()
    def showEvent(self, event):
        super().showEvent(event)
        if self.selection_enabled:  # It works better here than in exec()
            current_index = self.ui.DataView.currentIndex().siblingAtColumn(self.model.fieldIndex("symbol"))  # Column #0 is hidden, so we scroll to column #1
            if current_index.isValid():
                self.ui.DataView.scrollTo(current_index, QAbstractItemView.PositionAtCenter)

    # The dialog does two jobs: it manages the symbol list, where the only thing left to do is close it, and it
    # picks a symbol for someone else, where it has an answer to return. The button box says which one is running.
    def _setup_dialog_buttons(self):
        if self.selection_enabled:
            self.ui.DialogButtonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        else:
            self.ui.DialogButtonBox.setStandardButtons(QDialogButtonBox.Close)
        self._update_accept_button()

    # There is nothing to return until a row is picked, so OK stays unavailable rather than accepting an empty answer
    def _update_accept_button(self):
        accept_button = self.ui.DialogButtonBox.button(QDialogButtonBox.Ok)
        if accept_button is not None:
            accept_button.setEnabled(self.ui.DataView.currentIndex().isValid())

    @Slot()
    def onRowSelected(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            self.selected_id = self.model.getId(idx[0])
            self.p_selected_name = self.model.getName(idx[0])
        self._update_accept_button()

    # Both exits go through close() rather than accept()/reject(): closeEvent() is what stores the window geometry
    # and the column layout, and QDialog.accept() would hide the dialog without ever sending a close event.
    @Slot()
    def onDialogAccept(self):
        self.setResult(QDialog.Accepted)
        self.close()

    @Slot()
    def onDialogReject(self):
        self.setResult(QDialog.Rejected)
        self.close()

    @Slot()
    def closeEvent(self, event):
        JalSettings().setValue('DlgGeometry_' + self.windowTitle(), base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        JalSettings().setValue('DlgViewState_' + self.windowTitle(), base64.encodebytes(self.ui.DataView.horizontalHeader().saveState().data()).decode('utf-8'))
                # event.ignore()
        event.accept()

    @Slot(int, QPoint)
    def dialog_requested(self, selected_id: int, position: QPoint, params: dict):
        self.setGeometry(position.x(), position.y(), self.width(), self.height())
        self.set_parameters(params)
        self.exec(enable_selection=True, selected=selected_id)

    def exec(self, enable_selection=False, selected=0):
        self.selection_enabled = enable_selection
        self._setup_dialog_buttons()
        if enable_selection:
            item_index = self.model.locateItem(selected)
            self.ui.DataView.setCurrentIndex(item_index)
        res = super().exec()
        if res:
            self.selection_done.emit(self.selected_id)
        return res

    def configureColumns(self):
        specs = self.model.column_meta()
        for col, spec in enumerate(specs):
            if spec.hide:
                self.ui.DataView.setColumnHidden(col, True)
            if spec.width:
                if spec.width == CmWidth.WIDTH_STRETCH:
                    self.ui.DataView.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
                else:
                    self.ui.DataView.setColumnWidth(col, spec.width)

    @Slot()
    def onAdd(self):
        # Deferred import to break a real circular import: this module -> symbol_dialog -> reference_dialogs
        # (for TagsListDialog) -> this module (for SymbolListDialog). A module-level import here fails because
        # SymbolListDialog isn't defined yet when reference_dialogs is pulled in mid-load.
        # TODO - refactor code to remove deferred import
        from jal.widgets.symbol_dialog import SymbolDialog
        dialog = SymbolDialog(self)
        dialog.createNewRecord()
        if dialog.exec() == QDialog.Accepted:
            self.setFilter()

    @Slot()
    def onEdit(self):
        idx = self.ui.DataView.currentIndex()
        if not idx.isValid():
            return
        asset_id = self.model.record(idx.row()).value('asset_id')
        # Deferred import to break a real circular import: this module -> symbol_dialog -> reference_dialogs
        # (for TagsListDialog) -> this module (for SymbolListDialog). A module-level import here fails because
        # SymbolListDialog isn't defined yet when reference_dialogs is pulled in mid-load.
        # TODO - refactor code to remove deferred import
        from jal.widgets.symbol_dialog import SymbolDialog
        dialog = SymbolDialog(self)
        dialog.setSelectedId(asset_id)
        if dialog.exec() == QDialog.Accepted:
            self.setFilter()

    @Slot()
    def onRemove(self):
        idx = self.ui.DataView.currentIndex()
        if not idx.isValid():
            return
        symbol_id = self.model.getId(idx)
        symbol = self.model.getName(idx)
        if self.model.is_last_symbol(symbol_id):
            asset_name = self.model.getValueDetails(symbol_id)
            question = self.tr(f"'{symbol}' is the last symbol of asset '{asset_name}'. Removing it will also remove the asset "
                               "itself together with its full transaction history. Continue?")
        else:
            question = self.tr(f"Remove symbol '{symbol}'?")
        if QMessageBox().warning(self, self.tr("Confirmation"), question, QMessageBox.Yes, QMessageBox.No) != QMessageBox.Yes:
            return
        if self.model.remove_symbol(symbol_id):
            self.setFilter()

    @Slot(QPoint)
    def onContextMenu(self, position):
        index = self.ui.DataView.indexAt(position)
        if not index.isValid() or self.selection_enabled:
            return   # while the dialog is being used to PICK a symbol, acting on one is not what a click means
        self.ui.DataView.setCurrentIndex(index)
        menu = QMenu(self.ui.DataView)
        menu.addAction(self.tr("Merge asset into..."), self.onMergeAsset)
        menu.popup(self.ui.DataView.viewport().mapToGlobal(position))

    # Declares that the asset behind the chosen listing and the asset behind another one are one and the same thing,
    # and folds the first into the second.
    #
    # It is offered on a LISTING because that is what this dialog lists, and it is a listing that shows the problem:
    # a coin whose ticker was changed on one chain is fetched as an asset of its own (see
    # Statement._resolve_cross_chain_token), so what the user sees is two rows that they know are one coin. Nothing
    # can tell that from the data - the two contract addresses are genuinely different tokens as far as any chain is
    # concerned - so it stays an assertion the user makes, like naming the account at a transfer's missing end.
    @Slot()
    def onMergeAsset(self):
        index = self.ui.DataView.currentIndex()
        if not index.isValid():
            return
        merged = JalSymbol(self.model.getId(index)).asset()
        selector = SymbolListDialog(self)
        if selector.exec(enable_selection=True) != QDialog.Accepted:
            return
        survivor = JalSymbol(selector.selected_id).asset()
        refusal = merged.refusal_to_replace(survivor.id())
        if refusal:
            QMessageBox().warning(self, self.tr("Assets are not merged"), refusal)
            return
        # Everything the merged asset was is renamed rather than deleted, but the ledger is dropped and has to be
        # recalculated - so the user is told what it costs before it happens rather than after
        question = self.tr("'{}' will become part of '{}': its symbols, quotes and whole history move over and the "
                           "asset itself is removed. The ledger will be rebuilt. Continue?").format(merged.name(),
                                                                                                    survivor.name())
        if QMessageBox().warning(self, self.tr("Confirmation"), question,
                                 QMessageBox.Yes, QMessageBox.No) != QMessageBox.Yes:
            return
        merged_name = merged.name()
        refusal = merged.replace_with(survivor.id())
        if refusal:
            QMessageBox().warning(self, self.tr("Assets are not merged"), refusal)
            return
        logging.info(self.tr("Asset '") + merged_name + self.tr("' was merged into '") + survivor.name() + "'")
        # Rebuilt here and now rather than left for the next start: replace_with() drops the ledger, and until it is
        # recalculated every report is empty - which looks like the merge destroyed the history it in fact moved.
        # From scratch and without asking again, because the whole ledger is what is gone and the cost was the
        # question already answered above.
        Ledger().rebuild(from_timestamp=0)
        self.setFilter()

    @Slot()
    def OnDoubleClicked(self, index):
        self.selected_id = self.model.getId(index)
        self.p_selected_name = self.model.getName(index)
        if self.selection_enabled:
            self.setResult(QDialog.Accepted)
            self.close()

    # This method is called from ReferenceSelector to provide additional parameters from the selector widget.
    def set_parameters(self, params):
        self._currency_id = params.get('currency_id', None)
        if self._currency_id:
            idx = self.ui.CurrencyCombo.findData(self._currency_id)
            if idx >= 0:
                self.ui.CurrencyCombo.setCurrentIndex(idx)
        self.setFilter()

    @Slot()
    def subset_changed(self):
        self._type_id = self.ui.AssetTypeCombo.currentData()
        self._currency_id = self.ui.CurrencyCombo.currentData()
        self._location_id = self.ui.LocationCombo.currentData()
        self.setFilter()

    @Slot()
    def search_changed(self):
        self._search_text = self.ui.SearchString.text()
        self.setFilter()

    def setFilter(self):
        self.model.setFilter(asset_type=self._type_id, currency_id=self._currency_id, location_id=self._location_id, text=self._search_text)
