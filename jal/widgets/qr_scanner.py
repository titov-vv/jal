import io
import logging
from PySide6.QtCore import Qt, Signal, QBuffer, QRectF
from PySide6.QtGui import QImage, QPen, QBrush
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsScene, QGraphicsView
from PySide6.QtMultimedia import QMediaDevices, QCamera, QMediaCaptureSession, QImageCapture
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

try:
    from pyzbar import pyzbar
    from PIL import Image, UnidentifiedImageError
except ImportError:
    pass   # We should not be in this module as dependencies have been checked in main_window.py and calls are disabled


# ----------------------------------------------------------------------------------------------------------------------
class QRScanner(QWidget):
    QR_SIZE = 0.75   # Size of rectangle for QR capture
    readyForCapture = Signal(bool)
    decodedQR = Signal(str)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.processing = False
        self.rectangle = None

        self.setMinimumHeight(405)
        self.layout = QVBoxLayout()
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
        if len(QMediaDevices.videoInputs()) == 0:
            logging.warning(self.tr("There are no cameras available"))
            return

        self.processing = True   # disable any capture while camera is starting
        self.camera = QCamera(QMediaDevices.defaultVideoInput())
        self.captureSession = QMediaCaptureSession()
        self.imageCapture = QImageCapture(self.camera)
        self.captureSession.setCamera(self.camera)
        self.captureSession.setVideoOutput(self.viewfinder)
        self.captureSession.setImageCapture(self.imageCapture)

        self.camera.errorOccurred.connect(self.onCameraError)
        self.readyForCapture.connect(self.onReadyForCapture)
        self.imageCapture.errorOccurred.connect(self.onCaptureError)
        self.imageCapture.readyForCaptureChanged.connect(self.onReadyForCapture)
        self.imageCapture.imageCaptured.connect(self.onImageCaptured)
        self.viewfinder.nativeSizeChanged.connect(self.onVideoSizeChanged)

        self.camera.start()
        self.processing = False
        self.readyForCapture.emit(self.imageCapture.isReadyForCapture())

    def stopScan(self):
        if self.camera is None:
            return
        self.processing = True   # disable capture
        self.camera.stop()

        self.camera = None
        self.captureSession = None
        self.imageCapture = None
        self.captureTimer = None

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

    def onReadyForCapture(self, ready: bool):
        if ready and not self.processing:
            self.imageCapture.capture()
            self.processing = True

    def onImageCaptured(self, _id: int, img: QImage):
        self.decodeQR(img)
        self.processing = False
        if self.imageCapture is not None:
            self.readyForCapture.emit(self.imageCapture.isReadyForCapture())

    def decodeQR(self, qr_image: QImage):
        cropped = qr_image.copy(self.calculate_center_square(qr_image).toRect())
        # TODO: the same code is present in slips.py -> move to one place
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        cropped.save(buffer, "BMP")
        try:
            pillow_image = Image.open(io.BytesIO(buffer.data()))
        except UnidentifiedImageError:
            print("Image format isn't supported")
            return
        barcodes = pyzbar.decode(pillow_image, symbols=[pyzbar.ZBarSymbol.QRCODE])
        if barcodes:
            self.decodedQR.emit(barcodes[0].data.decode('utf-8'))
