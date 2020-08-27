from pyzbar import pyzbar
from PIL import Image

from PySide2.QtWidgets import QDialog, QFileDialog
from CustomUI.helpers import g_tr
from UI.ui_slip_import_dlg import Ui_ImportSlipDlg

class ImportSlipDialog(QDialog, Ui_ImportSlipDlg):
    def __init__(self, parent):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)

        self.LoadQRfromFileBtn.clicked.connect(self.loadQR)

    def loadQR(self):
        qr_file, _filter = \
            QFileDialog.getOpenFileName(None, g_tr('ImportSlipDialog', "Select file with QR code"),
                                        ".", "JPEG images (*.jpg);;PNG images (*.png)")
        if qr_file:
            barcodes = pyzbar.decode(Image.open(qr_file), symbols=[pyzbar.ZBarSymbol.QRCODE])
            for barcode in barcodes:
                print(f"Found: {barcode.type} code {barcode.data.decode('utf-8')}")
