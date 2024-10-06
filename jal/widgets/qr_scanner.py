import logging
from PySide6.QtCore import Qt, Slot, Signal, QRectF, QTimer, QMetaObject
from PySide6.QtGui import QImage, QPen, QBrush
from PySide6.QtWidgets import QApplication, QDialog, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QSpacerItem, \
    QGraphicsScene, QGraphicsView, QLabel, QSizePolicy, QPushButton, QFileDialog, QInputDialog
from jal.widgets.helpers import dependency_present, decodeQR
try:
    from pyzbar import pyzbar
except ImportError:
    pass  # pyzbar import will be checked separately
try:
    from PySide6.QtMultimedia import QMediaDevices, QCamera, QMediaCaptureSession, QImageCapture
    from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
except ImportError:
    pass   # We should not be in this module as dependencies have been checked in main_window.py and calls are disabled

# ----------------------------------------------------------------------------------------------------------------------
class QRScanner(QWidget):
    TYPE_QR = 1
    TYPE_ITF = 2
    QR_SIZE = 0.75      # Size of rectangle for QR capture (used to display only currently) or ITF width
    ITF_SIZE = 0.2      # Size of ITF height area for capture
    QR_SCAN_RATE = 100  # Delay in ms between QR captures
    decodedQR = Signal(str)

    def __init__(self, parent=None, code_type=TYPE_QR):
        super().__init__(parent=parent)
        self.processing = False
        self.started = False
        self.rectangle = None
        self.code_type = pyzbar.ZBarSymbol.I25 if code_type == self.TYPE_ITF else pyzbar.ZBarSymbol.QRCODE

        self.setMinimumHeight(405)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QBrush(Qt.black))
        self.view = QGraphicsView(self.scene)
        self.viewfinder = QGraphicsVideoItem()
        self.scene.addItem(self.viewfinder)
        self.layout.addWidget(self.view)
        self.setLayout(self.layout)

        self.camera = QCamera(QMediaDevices.defaultVideoInput(), parent=self)
        self.captureSession = QMediaCaptureSession(self)
        self.imageCapture = QImageCapture(self)
        self.captureSession.setCamera(self.camera)
        self.captureSession.setVideoOutput(self.viewfinder)
        self.captureSession.setImageCapture(self.imageCapture)
        self.captureTimer = QTimer(self)

        self.camera.errorOccurred.connect(self.onCameraError)
        self.imageCapture.errorOccurred.connect(self.onCaptureError)
        self.imageCapture.imageCaptured.connect(self.onImageCaptured)
        self.viewfinder.nativeSizeChanged.connect(self.onVideoSizeChanged)
        self.captureTimer.timeout.connect(self.scanQR)

    def start(self):   # Start scanning process
        if self.started:
            return
        if len(QMediaDevices.videoInputs()) == 0:
            logging.warning(self.tr("There are no cameras available"))
            return
        if not dependency_present(['pyzbar']):
            logging.warning(self.tr("Package pyzbar not found for QR recognition."))
            return ''
        self.processing = True   # disable any capture while camera is starting
        self.camera.start()
        self.processing = False
        self.started = True
        self.captureTimer.start(self.QR_SCAN_RATE)

    def stop(self):   # Stop scanning process
        if not self.started:
            return
        self.processing = True  # disable capture
        self.captureTimer.stop()
        self.camera.stop()
        self.started = False

    def onVideoSizeChanged(self, _size):
        self.resizeEvent(None)

    # Take QImage or QRect (object with 'width' and 'height' properties and calculate position and size
    # of the square with side of self.QR_SIZE from minimum of height or width for QR code type
    # or the rectangle of QR_SIZE x ITF_SIZE for ITF code type
    def calculate_scan_area(self, img_rect) -> QRectF:
        min_side = min(img_rect.height(), img_rect.width())
        h = self.QR_SIZE * min_side    # Square side or code width
        w = self.ITF_SIZE * min_side if self.code_type == pyzbar.ZBarSymbol.I25 else h  # Code height
        x = (img_rect.width() - w) / 2         # Position of the square inside rectangle
        y = (img_rect.height() - h) / 2
        if type(img_rect) != QImage:   # if we have a bounding rectangle, not an image
            x += img_rect.left()       # then we need to shift our square inside this rectangle
            y += img_rect.top()
        return QRectF(x, y, w, h)

    def resizeEvent(self, event):
        bounds = self.scene.itemsBoundingRect()
        if bounds.width() <= 0 or bounds.height() <= 0:
            return    # do nothing if size is zero
        self.view.fitInView(bounds, Qt.KeepAspectRatio)
        if self.rectangle is not None:
            self.scene.removeItem(self.rectangle)
        pen = QPen(Qt.red) if self.code_type == pyzbar.ZBarSymbol.I25 else QPen(Qt.green)
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        self.rectangle = self.scene.addRect(self.calculate_scan_area(bounds), pen)
        self.view.centerOn(0, 0)
        self.view.raise_()

    def onCaptureError(self, _id, error, error_str):
        self.processing = False
        logging.error(self.tr("Capture error: " + str(error) + " / " + error_str))

    def onCameraError(self, error, error_str):
        logging.error(self.tr("Camera error: " + str(error) + " / " + error_str))

    def scanQR(self):
        if self.imageCapture is None:
            return
        if self.processing:
            return
        if self.imageCapture.isReadyForCapture():
            self.imageCapture.capture()
            self.processing = True

    def onImageCaptured(self, _id: int, img: QImage):
        self.decodeQR(img)
        self.processing = False

    def decodeQR(self, qr_image: QImage):
        cropped = qr_image.copy(self.calculate_scan_area(qr_image).toRect())
        qr_text = decodeQR(cropped, code_type=self.code_type)
        if qr_text:
            self.decodedQR.emit(qr_text)


# ----------------------------------------------------------------------------------------------------------------------
# Implements bar-code scanner window.
# Safe usage is by simple call to ScanDialog.execute_scan() class method - it will return scanned data and ensure that camera is released for next scans
class ScanDialog(QDialog):
    def __init__(self, parent=None, code_type=QRScanner.TYPE_QR, message=''):
        super().__init__(parent)
        self.data = ''
        self.code_type = code_type
        self.running = False
        self.resize(700, 450)
        self.setWindowTitle(self.tr("Barcode scanner"))
        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.hint_label = QLabel(message, parent=self)
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.verticalLayout.addWidget(self.hint_label)

        self.scanner = QRScanner(self, self.code_type)
        self.scanner.decodedQR.connect(self.barcode_scanned)
        scanner_size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scanner_size_policy.setHeightForWidth(self.scanner.sizePolicy().hasHeightForWidth())
        self.scanner.setSizePolicy(scanner_size_policy)
        self.verticalLayout.addWidget(self.scanner)
        self.ButtonFrame = QFrame(self)
        self.horizontalLayout = QHBoxLayout(self.ButtonFrame)
        self.horizontalLayout.setSpacing(2)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.readQR_button = QPushButton(self.ButtonFrame, text=self.tr("Load image from file"))
        self.pasteQR_button = QPushButton(self.ButtonFrame, text=self.tr("Get image from clipboard"))
        self.enterText_button = QPushButton(self.ButtonFrame, text=self.tr("Input data manually"))
        self.close_button = QPushButton(self.ButtonFrame, text=self.tr("Close"))
        self.h_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout.addWidget(self.readQR_button)
        self.horizontalLayout.addWidget(self.pasteQR_button)
        self.horizontalLayout.addWidget(self.enterText_button)
        self.horizontalLayout.addItem(self.h_spacer)
        self.horizontalLayout.addWidget(self.close_button)
        self.verticalLayout.addWidget(self.ButtonFrame)
        self.readQR_button.clicked.connect(self.load_qr_image_file)
        self.pasteQR_button.clicked.connect(self.paste_qr_image)
        self.enterText_button.clicked.connect(self.enter_qr_data)
        self.close_button.clicked.connect(self.close)

    @classmethod
    # Performs bar/QR code scan (code type is chosen by code_type parameter).
    # You may specify parent window and custom scanner window title
    # Returns scanned value or None if scan was cancelled.
    def execute_scan(cls, parent=None, code_type=QRScanner.TYPE_QR, message='') -> str:
        scanner = cls(parent=parent, message=message, code_type=code_type)
        if scanner.exec() != QDialog.Accepted:
            return None
        code_data = scanner.data
        scanner = None  # Release scanner to make camera available for next scan
        return code_data

    @Slot()
    def showEvent(self, event):
        super().showEvent(event)
        if self.running:
            return
        self.running = True
        # Call slot via queued connection, so it's called from the UI thread after the window has been shown
        QMetaObject().invokeMethod(self, "start_scan", Qt.ConnectionType.QueuedConnection)

    @Slot()
    def closeEvent(self, event):
        # Direct call self.scanner.stopScan() crashes application with segmentation violation
        QMetaObject().invokeMethod(self, "stop_scan", Qt.ConnectionType.QueuedConnection)

    @Slot()
    def start_scan(self):
        self.scanner.start()

    @Slot()
    def stop_scan(self):
        self.scanner.stop()

    @Slot()
    def barcode_scanned(self, decoded_data):
        # Direct call self.scanner.stopScan() crashes application with segmentation violation
        QMetaObject().invokeMethod(self, "stop_scan", Qt.ConnectionType.QueuedConnection)
        self.data = decoded_data
        self.accept()

    #------------------------------------------------------------------------------------------
    # Loads graphics file and tries to read QR-code from it.
    @Slot()
    def load_qr_image_file(self):
        qr_file, _filter = \
            QFileDialog.getOpenFileName(self, self.tr("Select file with QR code"),
                                        ".", "JPEG images (*.jpg);;PNG images (*.png);;BMP images (*.bmp)")
        if qr_file:
            self.data = decodeQR(QImage(qr_file), code_type=self.code_type)
            if self.data:
                self.accept()
            else:
                logging.warning(self.tr("No QR codes were found in file"))

    # ------------------------------------------------------------------------------------------
    # Gets image from clipboard and tries to read QR-code from it.
    @Slot()
    def paste_qr_image(self):
        self.data = decodeQR(QApplication.clipboard().image(), code_type=self.code_type)
        if self.data:
            self.accept()
        else:
            logging.warning(self.tr("No QR codes found in clipboard"))

    @Slot()
    def enter_qr_data(self):
        self.data, result = QInputDialog.getText(None, self.tr("Input code data manually"), self.tr("Data:"))
        if not result:
            return
        self.accept()
