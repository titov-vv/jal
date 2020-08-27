from PySide2.QtWidgets import QDialog

from UI.ui_slip_import_dlg import Ui_ImportSlipDlg

class ImportSlipDialog(QDialog, Ui_ImportSlipDlg):
    def __init__(self, parent):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)
