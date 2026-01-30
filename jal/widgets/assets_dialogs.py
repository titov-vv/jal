import base64
import logging
from PySide6.QtCore import Signal, Slot, QPoint
from PySide6.QtWidgets import QAbstractItemView, QDialog, QMessageBox, QHeaderView
from jal.ui.ui_asset_list_dlg import Ui_AssetsListDialog
from jal.db.settings import JalSettings
from jal.db.asset_models import SymbolsListModel
from jal.constants import PredefinedAsset, CmWidth


# ----------------------------------------------------------------------------------------------------------------------
class SymbolListDialog(QDialog):
    selection_done = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_AssetsListDialog()
        self.ui.setupUi(self)
        self._parent = parent
        self.model = SymbolsListModel(self)
        self.setup_ui()

    def setup_ui(self):
        self.ui.DataView.setModel(self.model)
        self.ui.DataView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        PredefinedAsset().load2combo(self.ui.AssetTypeCombo)
        self.setViewBoldHeader()
        self.configureColumns()

    @Slot()
    def closeEvent(self, event):
        JalSettings().setValue('DlgGeometry_' + self.windowTitle(), base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        JalSettings().setValue('DlgViewState_' + self.windowTitle(), base64.encodebytes(self.ui.DataView.horizontalHeader().saveState().data()).decode('utf-8'))
        if self.ui.CommitBtn.isEnabled():    # There are uncommitted changed in a table
            if QMessageBox().warning(self, self.tr("Confirmation"),
                                     self.tr("You have uncommitted changes. Do you want to close?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                event.ignore()
                return
            else:
                self.model.revertAll()
        event.accept()

    @Slot(int, QPoint)
    def dialog_requested(self, selected_id: int, position: QPoint):
        self.setGeometry(position.x(), position.y(), self.width(), self.height())
        self.exec(enable_selection=True, selected=selected_id)

    def exec(self, enable_selection=False, selected=0):
        # self.selection_enabled = enable_selection
        # if enable_selection:
        #     self.locateItem(selected)
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

    # def locateItem(self, item_id):
    #     type_id = self.model.getGroupId(item_id)
    #     if type_id == 0:
    #         return
    #     self.ui.GroupCombo.setCurrentIndex(type_id-1)
    #     item_idx = self.model.locateItem(item_id, use_filter=self._filter_text)
    #     self.ui.DataView.setCurrentIndex(item_idx)