import base64
import logging
from PySide6.QtCore import Signal, Slot, QPoint
from PySide6.QtWidgets import QAbstractItemView, QDialog, QMessageBox
from jal.ui.ui_asset_list_dlg import Ui_AssetsListDialog
from jal.db.settings import JalSettings
from jal.db.asset_models import SymbolsListModel
from jal.constants import PredefinedAsset


# ----------------------------------------------------------------------------------------------------------------------
class SymbolListDialog(QDialog):
    selection_done = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_AssetsListDialog()
        self.ui.setupUi(self)
        self._parent = parent
        self.model = SymbolsListModel(self)
        self.ui.DataView.setModel(self.model)
        self.ui.DataView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        PredefinedAsset().load2combo(self.ui.AssetTypeCombo)

    @Slot()
    def closeEvent(self, event):
        JalSettings().setValue('DlgGeometry_' + self.dialog_window_name, base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        JalSettings().setValue('DlgViewState_' + self.dialog_window_name, base64.encodebytes(self._view_header.saveState().data()).decode('utf-8'))
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

    # def locateItem(self, item_id):
    #     type_id = self.model.getGroupId(item_id)
    #     if type_id == 0:
    #         return
    #     self.ui.GroupCombo.setCurrentIndex(type_id-1)
    #     item_idx = self.model.locateItem(item_id, use_filter=self._filter_text)
    #     self.ui.DataView.setCurrentIndex(item_idx)