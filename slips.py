import io
import re
import logging
# below needed for QR recognition
from pyzbar import pyzbar
from PIL import Image

from PySide2.QtCore import QDateTime, QBuffer, QThread
from PySide2.QtWidgets import QApplication, QDialog, QFileDialog
# This QCamera staff ran good on Windows but didn't fly on Linux from the box until 'cheese' installation
from PySide2.QtMultimedia import QCameraInfo, QCamera, QCameraImageCapture, QVideoFrame
from PySide2.QtMultimediaWidgets import QCameraViewfinder
from CustomUI.helpers import g_tr
from UI.ui_slip_import_dlg import Ui_ImportSlipDlg


class ImportSlipDialog(QDialog, Ui_ImportSlipDlg):
    QR_pattern = "^t=(.*)&s=(.*)&fn=(.*)&i=(.*)&fp=(.*)&n=(.*)$"
    timestamp_patterns = ['yyyyMMddTHHmm', 'yyyyMMddTHHmmss', 'yyyy-MM-ddTHH:mm', 'yyyy-MM-ddTHH:mm:ss']

    def __init__(self, parent):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)

        self.LoadQRfromFileBtn.clicked.connect(self.loadQR)
        self.GetQRfromClipboardBtn.clicked.connect(self.readClipboardQR)
        self.GetQRfromCameraBtn.clicked.connect(self.readCameraQR)

        self.cam = None
        self.capture = None
        self.viewfinder = None

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

    def log_error(self):
        logging.info("Cam error")

    def processCaptureImage(self, id, preview):
        print(f"captured #{id}")

    def processSavedImage(self, id, name):
        print(f"saved #{id} at {name}")

    def readyForCapture(self):
        print("capture ready")
        self.capture.capture()

    def processBufferedImage(self, id, frame):
        print("img ready")
        img = frame.image()
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        img.save(buffer, "BMP")
        pil_im = Image.open(io.BytesIO(buffer.data()))
        barcodes = pyzbar.decode(pil_im, symbols=[pyzbar.ZBarSymbol.QRCODE])
        if barcodes:
            print(f"Got QR: {barcodes[0].data.decode('utf-8')}")
            self.parseQRdata(barcodes[0].data.decode('utf-8'))
            self.cam.stop()
        else:
            QThread.sleep(1)
            self.capture.capture()

    def CaptureError(self, id, error, msg):
        print(f"capture error: {msg}")

    def readCameraQR(self):
        camera_info = QCameraInfo.defaultCamera()
        self.cam = QCamera(camera_info)
        self.cam.errorOccurred.connect(self.log_error)
        self.capture = QCameraImageCapture(self.cam)

        self.viewfinder = QCameraViewfinder()
        self.viewfinder.show()
        self.cam.setViewfinder(self.viewfinder)

        self.capture.imageCaptured.connect(self.processCaptureImage)
        self.capture.imageSaved.connect(self.processSavedImage)
        self.capture.imageAvailable.connect(self.processBufferedImage)
        self.capture.readyForCaptureChanged.connect(self.readyForCapture)
        self.capture.error.connect(self.CaptureError)

        self.capture.setCaptureDestination(QCameraImageCapture.CaptureToBuffer)
        self.capture.setBufferFormat(QVideoFrame.Format_RGB32)
        self.cam.setCaptureMode(QCamera.CaptureStillImage)
        self.cam.start()

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
