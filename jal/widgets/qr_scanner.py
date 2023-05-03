import logging
from PySide6.QtCore import Qt, Signal, QRectF, QTimer
from PySide6.QtGui import QImage, QPen, QBrush
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsScene, QGraphicsView
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
    QR_SIZE = 0.75      # Size of rectangle for QR capture (used to display only currently)
    QR_SCAN_RATE = 100  # Delay in ms between QR captures
    decodedQR = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.processing = False
        self.started = False
        self.rectangle = None

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

        self.camera = None
        self.captureSession = None
        self.imageCapture = None
        self.captureTimer = None

    def startScan(self):
        if self.started:
            return
        if len(QMediaDevices.videoInputs()) == 0:
            logging.warning(self.tr("There are no cameras available"))
            return
        if not dependency_present(['pyzbar']):
            logging.warning(self.tr("Package pyzbar not found for QR recognition."))
            return ''

        self.processing = True   # disable any capture while camera is starting
        self.camera = QCamera(QMediaDevices.defaultVideoInput())
        self.captureSession = QMediaCaptureSession(self)
        self.imageCapture = QImageCapture(self.camera)
        self.captureSession.setCamera(self.camera)
        self.captureSession.setVideoOutput(self.viewfinder)
        self.captureSession.setImageCapture(self.imageCapture)
        self.captureTimer = QTimer(self)

        self.camera.errorOccurred.connect(self.onCameraError)
        self.imageCapture.errorOccurred.connect(self.onCaptureError)
        self.imageCapture.imageCaptured.connect(self.onImageCaptured)
        self.viewfinder.nativeSizeChanged.connect(self.onVideoSizeChanged)
        self.captureTimer.timeout.connect(self.scanQR)

        self.camera.start()
        self.processing = False
        self.started = True
        self.captureTimer.start(self.QR_SCAN_RATE)

    def stopScan(self):
        if self.camera is None:
            return
        if not self.started:
            return
        self.processing = True  # disable capture
        self.captureTimer.stop()
        self.camera.stop()

        self.captureTimer.deleteLater()
        self.captureSession.deleteLater()
        self.imageCapture.deleteLater()
        self.camera.deleteLater()
        self.started = False

    def onVideoSizeChanged(self, _size):
        self.resizeEvent(None)

    # Take QImage or QRect (object with 'width' and 'height' properties and calculate position and size
    # of the square with side of self.QR_SIZE from minimum of height or width
    def calculate_center_square(self, img_rect) -> QRectF:
        a = self.QR_SIZE * min(img_rect.height(), img_rect.width())   # Size of square side
        x = (img_rect.width() - a) / 2         # Position of the square inside rectangle
        y = (img_rect.height() - a) / 2
        if type(img_rect) != QImage:   # if we have a bounding rectangle, not an image
            x += img_rect.left()       # then we need to shift our square inside this rectangle
            y += img_rect.top()
        return QRectF(x, y, a, a)

    def resizeEvent(self, event):
        bounds = self.scene.itemsBoundingRect()
        if bounds.width() <= 0 or bounds.height() <= 0:
            return    # do nothing if size is zero
        self.view.fitInView(bounds, Qt.KeepAspectRatio)
        if self.rectangle is not None:
            self.scene.removeItem(self.rectangle)
        pen = QPen(Qt.green)
        pen.setWidth(0)
        pen.setStyle(Qt.DashLine)
        self.rectangle = self.scene.addRect(self.calculate_center_square(bounds), pen)
        self.view.centerOn(0, 0)
        self.view.raise_()

    def onCaptureError(self, _id, error, error_str):
        self.processing = False
        self.onCameraError(error, error_str)

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
        cropped = qr_image.copy(self.calculate_center_square(qr_image).toRect())
        qr_text = decodeQR(cropped)
        if qr_text:
            self.decodedQR.emit(qr_text)
