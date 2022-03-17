from PySide6.QtWidgets import QDialog
from jal.ui.ui_asset_dlg import Ui_AssetDialog


class AssetDialog(QDialog, Ui_AssetDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
