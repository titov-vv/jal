import logging
from PySide6.QtCore import Qt, Signal, QRectF, QTimer, QThread
from PySide6.QtGui import QImage, QPen, QBrush
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsScene, QGraphicsView
try:
    from pyzbar import pyzbar
    from PySide6.QtMultimedia import QMediaDevices, QCamera, QMediaCaptureSession, QImageCapture
    from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
except ImportError:
    pass   # We should not be in this module as dependencies have been checked in main_window.py and calls are disabled


# ----------------------------------------------------------------------------------------------------------------------
# Helper class that will fire capture event form outside and trigger QR-recognition attempt.
# Otherwise, process crashes on Windows if timer is executed in the main thread.
class DetachedTimer(QThread):
    finished = Signal()         # This signal happens before exit of the thread
    triggered = Signal()        # This signal happens when timer timeouts

    # Init takes interval in milliseconds for the timer
    def __init__(self, interval):
        QThread.__init__(self)
        self.interval = interval

    def run(self):
        timer = QTimer()
        timer.timeout.connect(self.on_timer)
        timer.start(self.interval)
        super().run()           # This is required to start an event-loop and process timer signals inside the thread
        self.finished.emit()    # The thread is terminated externally by call to exit() or quit() methods

    def on_timer(self):
        self.triggered.emit()

# ----------------------------------------------------------------------------------------------------------------------
class QRScanner(QWidget):
    QR_SIZE = 0.75      # Size of rectangle for QR capture (used to display only currently)
    QR_SCAN_RATE = 100  # Delay in ms between QR captures
    decodedQR = Signal(str)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
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
        self.trigger = None

    def startScan(self):
        if len(QMediaDevices.videoInputs()) == 0:
            logging.warning(self.tr("There are no cameras available"))
            return

        self.processing = True   # disable any capture while camera is starting
        self.camera = QCamera(QMediaDevices.defaultVideoInput())
        self.captureSession = QMediaCaptureSession(self)
        self.imageCapture = QImageCapture(self.camera)
        self.captureSession.setCamera(self.camera)
        self.captureSession.setVideoOutput(self.viewfinder)
        self.captureSession.setImageCapture(self.imageCapture)

        self.camera.errorOccurred.connect(self.onCameraError)
        self.imageCapture.errorOccurred.connect(self.onCaptureError)
        self.imageCapture.imageCaptured.connect(self.onImageCaptured)
        self.viewfinder.nativeSizeChanged.connect(self.onVideoSizeChanged)

        self.camera.start()

        # Set up a timer to trigger image capture from camera from time to time
        self.trigger = DetachedTimer(self.QR_SCAN_RATE)
        self.trigger.finished.connect(self.trigger.deleteLater)
        self.trigger.triggered.connect(self.scanQR)
        self.trigger.start()

        self.processing = False
        self.started = True

    def stopScan(self):
        self.processing = True  # disable capture
        if self.started:
            self.trigger.exit(0)    # Stop the timer
        if self.camera is not None:
            self.camera.stop()

        self.camera = None
        self.captureSession = None
        self.imageCapture = None
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
        # cropped = qr_image.copy(self.calculate_center_square(qr_image).toRect())
        # crop works but somehow bytes array size differs from the cropped image size and code breaks
        qr_image.convertTo(QImage.Format_Grayscale8)
        data = (qr_image.bits().tobytes(), qr_image.width(), qr_image.height())
        barcodes = pyzbar.decode(data, symbols=[pyzbar.ZBarSymbol.QRCODE])
        if barcodes:
            qr_text = barcodes[0].data.decode('utf-8')
        else:
            qr_text = ''
        if qr_text:
            self.decodedQR.emit(qr_text)
