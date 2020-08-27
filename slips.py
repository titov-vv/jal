import io
import re
from pyzbar import pyzbar
from PIL import Image

from PySide2.QtCore import QDateTime, QBuffer
from PySide2.QtWidgets import QApplication, QDialog, QFileDialog
from PySide2.QtGui import QImage, QClipboard
from CustomUI.helpers import g_tr
from UI.ui_slip_import_dlg import Ui_ImportSlipDlg


class ImportSlipDialog(QDialog, Ui_ImportSlipDlg):
    QR_pattern = "^t=(.*)&s=(.*)&fn=(.*)&i=(.*)&fp=(.*)&n=(.*)$"
    timestamp_patterns = ['yyyyMMddTHHmm', 'yyyyMMddTHHmmss', 'yyyy-MM-ddTHH:mm', 'yyyy-MM-ddTHH:mm:ss']

    def __init__(self, parent):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)

        self.LoadQRfromFileBtn.clicked.connect(self.loadQR)
        self.GetClipboardBtn.clicked.connect(self.readClipboardQR)

    def loadQR(self):
        qr_file, _filter = \
            QFileDialog.getOpenFileName(self, g_tr('ImportSlipDialog', "Select file with QR code"),
                                        ".", "JPEG images (*.jpg);;PNG images (*.png)")
        if qr_file:
            barcodes = pyzbar.decode(Image.open(qr_file), symbols=[pyzbar.ZBarSymbol.QRCODE])
            for barcode in barcodes:
                print(f"Found QR: {barcode.data.decode('utf-8')}")
                self.parseQRdata(barcode.data.decode('utf-8'))

    def readClipboardQR(self):
        clip = QApplication.clipboard()
        img = clip.image()
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        img.save(buffer, "BMP")
        pil_im = Image.open(io.BytesIO(buffer.data()))
        barcodes = pyzbar.decode(pil_im, symbols=[pyzbar.ZBarSymbol.QRCODE])
        for barcode in barcodes:
            print(f"Got QR: {barcode.data.decode('utf-8')}")
            self.parseQRdata(barcode.data.decode('utf-8'))

    def parseQRdata(self, data):
        parts = re.match(self.QR_pattern, data)
        for timestamp_pattern in self.timestamp_patterns:
            datetime = QDateTime.fromString(parts.group(1), timestamp_pattern)
            if datetime.isValid():
                self.SlipTimstamp.setDateTime(datetime)
        self.SlipAmount.setText(parts.group(2))
        self.FN.setText(parts.group(3))
        self.FD.setText(parts.group(4))
        self.FP.setText(parts.group(5))
        self.SlipType.setText(parts.group(6))