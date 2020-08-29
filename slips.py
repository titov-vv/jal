import io
import re
import json
import logging
import pandas as pd
from pyzbar import pyzbar
from PIL import Image

from PySide2.QtCore import Qt, Slot, Signal, QDateTime, QBuffer, QThread, QAbstractTableModel
from PySide2.QtWidgets import QApplication, QDialog, QFileDialog, QHeaderView
# This QCamera staff ran good on Windows but didn't fly on Linux from the box until 'cheese' installation
from PySide2.QtMultimedia import QCameraInfo, QCamera, QCameraImageCapture, QVideoFrame
from CustomUI.helpers import g_tr
from slips_tax import SlipsTaxAPI
from view_delegate import SlipLinesPandasDelegate
from mapper_delegate import CategoryDelegate
from UI.ui_slip_import_dlg import Ui_ImportSlipDlg


#-----------------------------------------------------------------------------------------------------------------------
# Custom model to display and edit slip lines
class PandasLinesModel(QAbstractTableModel):
    def __init__(self, data, db):
        QAbstractTableModel.__init__(self)
        self._data = data
        self._db = db

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return super().flags(index) | Qt.ItemIsEditable

    def database(self):
        return self._db

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parnet=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                return self._data.iloc[index.row(), index.column()]
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid():
            if role == Qt.EditRole:
                self._data.iloc[index.row(), index.column()] = value
                self.dataChanged.emit(index, index)
                return True

    def headerData(self, col, orientation, role=Qt.DisplayRole):
        if (orientation == Qt.Horizontal and role == Qt.DisplayRole):
            if col == 0:
                return g_tr('PandasLinesModel', "Product name")
            if col == 1:
                return g_tr('PandasLinesModel', "Category")
            if col == 2:
                return g_tr('PandasLinesModel', "Amount")
        return None


#-----------------------------------------------------------------------------------------------------------------------
class ImportSlipDialog(QDialog, Ui_ImportSlipDlg):
    qr_data_available = Signal(str)
    qr_data_validated = Signal()
    json_data_available = Signal()

    QR_pattern = "^t=(.*)&s=(.*)&fn=(.*)&i=(.*)&fp=(.*)&n=(.*)$"
    timestamp_patterns = ['yyyyMMddTHHmm', 'yyyyMMddTHHmmss', 'yyyy-MM-ddTHH:mm', 'yyyy-MM-ddTHH:mm:ss']

    def __init__(self, parent, db):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)
        self.initUi()
        self.db=db
        self.model = None
        self.delegates = []

        self.CameraGroup.setVisible(False)
        self.cameraActive = False
        self.camera = None
        self.img_capture = None

        self.QR_data = ''
        self.slip_json = None

        self.slipsAPI = SlipsTaxAPI(self.db)
        self.AccountEdit.init_db(self.db)
        self.PeerEdit.init_db(self.db)

        self.qr_data_available.connect(self.parseQRdata)
        self.LoadQRfromFileBtn.clicked.connect(self.loadFileQR)
        self.GetQRfromClipboardBtn.clicked.connect(self.readClipboardQR)
        self.GetQRfromCameraBtn.clicked.connect(self.readCameraQR)
        self.StopCameraBtn.clicked.connect(self.closeCamera)
        self.GetSlipBtn.clicked.connect(self.downloadSlipJSON)
        self.LoadJSONfromFileBtn.clicked.connect(self.loadFileSlipJSON)
        self.AddOperationBtn.clicked.connect(self.addOperation)

    def closeEvent(self, arg__1):
        if self.cameraActive:
            self.closeCamera()

    def initUi(self):
        self.GetSlipBtn.setEnabled(False)
        self.SlipAmount.setText('')
        self.FN.setText('')
        self.FD.setText('')
        self.FP.setText('')
        self.SlipType.setText('')

    #------------------------------------------------------------------------------------------
    # Loads graphics file and tries to read QR-code from it.
    # Assignes self.QR_data after successful read and emit signal qr_data_available
    @Slot()
    def loadFileQR(self):
        self.initUi()
        qr_file, _filter = \
            QFileDialog.getOpenFileName(self, g_tr('ImportSlipDialog', "Select file with QR code"),
                                        ".", "JPEG images (*.jpg);;PNG images (*.png)")
        if qr_file:
            barcodes = pyzbar.decode(Image.open(qr_file), symbols=[pyzbar.ZBarSymbol.QRCODE])
            if barcodes:
                self.qr_data_available.emit(barcodes[0].data.decode('utf-8'))
            else:
                logging.warning('ImportSlipDialog', "No QR codes were found in file")

    #------------------------------------------------------------------------------------------
    # Qt operates with QImage class while pyzbar need PIL.Image as input
    # So, we first need to save QImage into the buffer and then read PIL.Image out from buffer
    # Returns: True if QR found, False if no QR found
    # Emits: qr_data_available(str: qr_data) if QR found
    def readImageQR(self, image):
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        image.save(buffer, "BMP")
        pillow_image = Image.open(io.BytesIO(buffer.data()))
        barcodes = pyzbar.decode(pillow_image, symbols=[pyzbar.ZBarSymbol.QRCODE])
        if barcodes:
            self.qr_data_available.emit(barcodes[0].data.decode('utf-8'))
            return True
        else:
            return False

    @Slot()
    def readClipboardQR(self):
        self.initUi()
        if not self.readImageQR(QApplication.clipboard().image()):
            logging.warning('ImportSlipDialog', "No QR codes found in clipboard")

    @Slot()
    def readCameraQR(self):
        self.initUi()
        if len(QCameraInfo.availableCameras()) == 0:
            logging.warning(g_tr('ImportSlipDialog', "There are no cameras available"))
            return
        self.cameraActive = True
        self.CameraGroup.setVisible(True)
        self.SlipDataGroup.setVisible(False)

        camera_info = QCameraInfo.defaultCamera()
        logging.info(g_tr('ImportSlipDialog', "Read QR with camera: " + camera_info.deviceName()))
        self.camera = QCamera(camera_info)
        self.camera.errorOccurred.connect(self.onCameraError)
        self.img_capture = QCameraImageCapture(self.camera)
        self.img_capture.setCaptureDestination(QCameraImageCapture.CaptureToBuffer)
        self.img_capture.setBufferFormat(QVideoFrame.Format_RGB32)
        self.img_capture.error.connect(self.onCameraCaptureError)
        self.img_capture.readyForCaptureChanged.connect(self.onReadyForCapture)
        self.img_capture.imageAvailable.connect(self.onCameraImageReady)
        self.camera.setViewfinder(self.Viewfinder)
        self.camera.setCaptureMode(QCamera.CaptureStillImage)
        self.camera.start()

    @Slot()
    def closeCamera(self):
        self.camera.stop()
        self.camera.unload()
        self.CameraGroup.setVisible(False)
        self.SlipDataGroup.setVisible(True)
        self.img_capture = None
        self.camera = None
        self.cameraActive = False

    @Slot()
    def onCameraError(self, error):
        logging.error(g_tr('ImportSlipDialog', "Camera error: " + str(error) + " / " + self.camera.errorString()))

    @Slot()
    def onCameraCaptureError(self, _id, error, msg):
        logging.error(g_tr('ImportSlipDialog', "Camera error: " + str(error) + " / " + msg))

    #----------------------------------------------------------------------
    # This event happens once upon camera start - it triggers first capture
    # Consequent captures will be initiated after image processing in self.onCameraImageReady
    @Slot()
    def onReadyForCapture(self):
        self.camera.searchAndLock()
        self.img_capture.capture()
        self.camera.unlock()

    #----------------------------------------------------------------------
    # Try to decode QR from captured frame
    # Close camera if decoded successfully otherwise try to capture again
    def onCameraImageReady(self, _id, captured_image):
        if self.readImageQR(captured_image.image()):
            self.closeCamera()
        else:
            QThread.sleep(1)
            self.camera.searchAndLock()
            self.img_capture.capture()
            self.camera.unlock()

    #-----------------------------------------------------------------------------------------------
    # Check if available QR data matches with self.QR_pattern
    # Emits qr_data_validated if match found. Otherwise shows warning message but allows to proceed
    @Slot()
    def parseQRdata(self, qr_data):
        self.QR_data = qr_data
        self.GetSlipBtn.setEnabled(True)

        logging.info(g_tr('ImportSlipDialog', "QR: " +self.QR_data))
        parts = re.match(self.QR_pattern, qr_data)
        if not parts:
            logging.warning(g_tr('ImportSlipDialog', "QR available but pattern isn't recognized: " + self.QR_data))
        for timestamp_pattern in self.timestamp_patterns:
            datetime = QDateTime.fromString(parts.group(1), timestamp_pattern)
            if datetime.isValid():
                self.SlipTimstamp.setDateTime(datetime)
        self.SlipAmount.setText(parts.group(2))
        self.FN.setText(parts.group(3))
        self.FD.setText(parts.group(4))
        self.FP.setText(parts.group(5))
        self.SlipType.setText(parts.group(6))
        self.qr_data_validated.emit()

    def downloadSlipJSON(self):
        timestamp = self.SlipTimstamp.dateTime().toSecsSinceEpoch()
        self.slip_json = self.slipsAPI.get_slip(timestamp, float(self.SlipAmount.text()), self.FN.text(),
                                                self.FD.text(), self.FP.text(), self.SlipType.text())
        if self.slip_json:
            self.parseJSON()

    @Slot()
    def loadFileSlipJSON(self):
        json_file, _filter = \
            QFileDialog.getOpenFileName(self, g_tr('ImportSlipDialog', "Select file with slip JSON data"),
                                        ".", "JSON files (*.json)")
        if json_file:
            with open(json_file) as f:
                self.slip_json = json.load(f)
            self.parseJSON()

    def parseJSON(self):
        # Slip data might be in a root element or in ticket/document/receipt
        if 'ticket' in self.slip_json:
            sub = self.slip_json['ticket']
            if 'document' in sub:
                sub = sub['document']
                if 'receipt' in sub:
                    slip = sub['receipt']
                else:
                    logging.error(g_tr('ImportSlipDialog', "Can't find 'receipt' tag  in json 'document'"))
                    return
            else:
                logging.error(g_tr('ImportSlipDialog', "Can't find 'document' tag  in json 'ticket'"))
                return
        else:
            slip = self.slip_json

        # Shop name may be present or only INN may be there
        if 'user' in slip:
            self.SlipShopName.setText(slip['user'])
        else:
            if 'userInn' in slip:
                self.SlipShopName.setText(self.slipsAPI.get_shop_name_by_inn(slip['userInn']))
        try:
            lines = pd.DataFrame(slip['items'])
        except:
            return

        # Get date from timestamp
        if 'dateTime' in slip:
            slip_datetime = QDateTime()
            slip_datetime.setSecsSinceEpoch(int(slip['dateTime']))
            self.SlipDateTime.setDateTime(slip_datetime)

        # Convert price to roubles
        lines['price'] = lines['price'] / 100
        lines['sum'] = -lines['sum'] / 100
        lines['category'] = 0
        lines = lines[['name', 'category', 'sum']]

        self.model = PandasLinesModel(lines, self.db)
        self.LinesTableView.setModel(self.model)

        self.delegates = []
        for column in range(self.model.columnCount()):
            if column == 0:
                self.LinesTableView.horizontalHeader().setSectionResizeMode(column, QHeaderView.Stretch)
                self.delegates.append(SlipLinesPandasDelegate(self.LinesTableView))
                self.LinesTableView.setItemDelegateForColumn(column, self.delegates[-1])
            elif column == 1:
                self.LinesTableView.setColumnWidth(column, 200)
                self.delegates.append(CategoryDelegate(self.LinesTableView))
                self.LinesTableView.setItemDelegateForColumn(column, self.delegates[-1])
            else:
                self.LinesTableView.setColumnWidth(column, 100)
                self.delegates.append(SlipLinesPandasDelegate(self.LinesTableView))
                self.LinesTableView.setItemDelegateForColumn(column, self.delegates[-1])
        font = self.LinesTableView.horizontalHeader().font()
        font.setBold(True)
        self.LinesTableView.horizontalHeader().setFont(font)
        self.LinesTableView.show()
        self.aaa = lines

    def addOperation(self):
        print(self.aaa)