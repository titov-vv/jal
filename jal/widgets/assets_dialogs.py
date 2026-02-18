import base64
from PySide6.QtCore import Signal, Slot, QPoint
from PySide6.QtWidgets import QAbstractItemView, QDialog, QHeaderView
from jal.ui.ui_asset_list_dlg import Ui_AssetsListDialog
from jal.db.settings import JalSettings
from jal.db.asset import JalAsset
from jal.db.asset_models import SymbolsListModel
from jal.constants import CmWidth, PredefinedAsset, AssetLocation


# ----------------------------------------------------------------------------------------------------------------------
class SymbolListDialog(QDialog):
    selection_done = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_AssetsListDialog()
        self.ui.setupUi(self)
        self._parent = parent
        self._type_id = None
        self._currency_id = None
        self._location_id = None
        self._search_text = ''
        self.selection_enabled = False
        self.model = SymbolsListModel(self)
        self.setup_ui()

        self.ui.AssetTypeCombo.currentIndexChanged.connect(self.subset_changed)
        self.ui.CurrencyCombo.currentIndexChanged.connect(self.subset_changed)
        self.ui.LocationCombo.currentIndexChanged.connect(self.subset_changed)
        self.ui.SearchString.textChanged.connect(self.search_changed)
        self.ui.DataView.doubleClicked.connect(self.OnDoubleClicked)

    def setup_ui(self):
        self.ui.DataView.setModel(self.model)
        self.ui.DataView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        PredefinedAsset().load2combo(self.ui.AssetTypeCombo)
        self.setViewBoldHeader()
        self.configureColumns()

        PredefinedAsset().load2combo(self.ui.AssetTypeCombo, with_empty=True)
        self.ui.CurrencyCombo.clear()
        self.ui.CurrencyCombo.addItem(self.tr(""), userData=None)
        for currency_id, symbol in sorted([(x.id(), x.symbol()) for x in JalAsset.get_currencies()], key=lambda x: x[1]):
            self.ui.CurrencyCombo.addItem(symbol, currency_id)
        AssetLocation().load2combo(self.ui.LocationCombo, with_empty=True)

    @Slot()
    def showEvent(self, event):
        super().showEvent(event)
        if self.selection_enabled:  # It works better here than in exec()
            current_index = self.ui.DataView.currentIndex().siblingAtColumn(self.model.fieldIndex("symbol"))  # Column #0 is hidden, so we scroll to column #1
            if current_index.isValid():
                self.ui.DataView.scrollTo(current_index, QAbstractItemView.PositionAtCenter)

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
        if enable_selection:
            item_index = self.model.locateItem(selected)
            self.ui.DataView.setCurrentIndex(item_index)
        res = super().exec()
        if res:
            self.selection_done.emit(self.selected_id)
        return res

    def setViewBoldHeader(self):
        font = self.ui.DataView.horizontalHeader().font()
        font.setBold(True)
        self.ui.DataView.horizontalHeader().setFont(font)

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
