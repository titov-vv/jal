import io
import time
import json
import logging
import pandas as pd
from urllib.parse import parse_qs
from PySide6.QtWidgets import QStyledItemDelegate
from jal.widgets.reference_selector import CategorySelector, TagSelector
from jal.constants import CustomColor
from jal.db.helpers import get_category_name
try:
    from pyzbar import pyzbar
    from PIL import Image, UnidentifiedImageError
except ImportError:
    pass   # We should not be in this module as dependencies have been checked in main_window.py and calls are disabled


from PySide6.QtCore import Qt, Slot, Signal, QDateTime, QBuffer, QThread, QAbstractTableModel
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QHeaderView
from jal.widgets.helpers import dependency_present
from jal.db.helpers import executeSQL, readSQL
from jal.data_import.slips_tax import SlipsTaxAPI
from jal.ui.ui_slip_import_dlg import Ui_ImportSlipDlg
from jal.data_import.category_recognizer import recognize_categories


#-----------------------------------------------------------------------------------------------------------------------
# Custom model to display and edit slip lines
class PandasLinesModel(QAbstractTableModel):
    def __init__(self, data):
        QAbstractTableModel.__init__(self)
        self._data = data

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return super().flags(index) | Qt.ItemIsEditable

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
        return False

    def headerData(self, col, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if col == 0:
                return self.tr("Product name")
            if col == 1:
                return self.tr("Category")
            if col == 3:
                return self.tr("Tag")
            if col == 4:
                return self.tr("Amount")
        return None


class SlipLinesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()
        pen = painter.pen()
        model = index.model()
        if index.column() == 0:
            text = model.data(index, Qt.DisplayRole)
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        if index.column() == 1:
            text = get_category_name(int(model.data(index, Qt.DisplayRole)))
            confidence = model.data(index.siblingAtColumn(2), Qt.DisplayRole)
            if confidence > 0.75:
                painter.fillRect(option.rect, CustomColor.LightGreen)
            elif confidence > 0.5:
                painter.fillRect(option.rect, CustomColor.LightYellow)
            else:
                painter.fillRect(option.rect, CustomColor.LightRed)
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        elif index.column() == 4:
            amount = model.data(index, Qt.DisplayRole)
            if amount == 2:
                pen.setColor(CustomColor.Grey)
                painter.setPen(pen)
            text = f"{amount:,.2f}"
            painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
        painter.setPen(pen)
        painter.restore()

    def createEditor(self, aParent, option, index):
        if index.column() == 1:
            category_selector = CategorySelector(aParent)
            return category_selector
        if index.column() == 3:
            tag_selector = TagSelector(aParent)
            return tag_selector

    def setModelData(self, editor, model, index):
        if index.column() == 1:
            model.setData(index, editor.selected_id)
            model.setData(index.siblingAtColumn(2), 1) # set confidence level to 1
        if index.column() == 3:
            model.setData(index, editor.selected_id)


#-----------------------------------------------------------------------------------------------------------------------
class ImportSlipDialog(QDialog, Ui_ImportSlipDlg):
    qr_data_available = Signal(str)
    qr_data_validated = Signal()
    qr_data_loaded = Signal()

    OPERATION_PURCHASE = 1
    OPERATION_RETURN = 2

    timestamp_patterns = ['yyyyMMddTHHmm', 'yyyyMMddTHHmmss', 'yyyy-MM-ddTHH:mm', 'yyyy-MM-ddTHH:mm:ss']

    def __init__(self, parent):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)
        self.initUi()
        self.model = None
        self.delegate = []

        self.CameraGroup.setVisible(False)

        self.QR_data = ''
        self.slip_json = None
        self.slip_lines = None

        self.slipsAPI = SlipsTaxAPI()
        self.tensor_flow_present = dependency_present(['tensorflow'])

        self.qr_data_available.connect(self.parseQRdata)
        self.qr_data_validated.connect(self.downloadSlipJSON)
        self.qr_data_loaded.connect(self.recognizeCategories)
        self.LoadQRfromFileBtn.clicked.connect(self.loadFileQR)
        self.GetQRfromClipboardBtn.clicked.connect(self.readClipboardQR)
        self.GetQRfromCameraBtn.clicked.connect(self.readCameraQR)
        self.StopCameraBtn.clicked.connect(self.closeCamera)
        self.ScannerQR.decodedQR.connect(self.onCameraQR)
        self.GetSlipBtn.clicked.connect(self.downloadSlipJSON)
        self.LoadJSONfromFileBtn.clicked.connect(self.loadFileSlipJSON)
        self.AddOperationBtn.clicked.connect(self.addOperation)
        self.ClearBtn.clicked.connect(self.clearSlipData)
        self.AssignCategoryBtn.clicked.connect(self.recognizeCategories)

        self.AssignCategoryBtn.setEnabled(self.tensor_flow_present)

    def closeEvent(self, arg__1):
        self.ScannerQR.stopScan()
        self.accept()

    def initUi(self):
        self.SlipAmount.setText('')
        self.FN.setText('')
        self.FD.setText('')
        self.FP.setText('')
        self.SlipType.setCurrentIndex(0)

    #------------------------------------------------------------------------------------------
    # Loads graphics file and tries to read QR-code from it.
    # Assignes self.QR_data after successful read and emit signal qr_data_available
    @Slot()
    def loadFileQR(self):
        self.initUi()
        qr_file, _filter = \
            QFileDialog.getOpenFileName(self, self.tr("Select file with QR code"),
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
        buffer = QBuffer()   # TODO: the same code is present in qr_scanner.py -> move to one place
        buffer.open(QBuffer.ReadWrite)
        image.save(buffer, "BMP")
        try:
            pillow_image = Image.open(io.BytesIO(buffer.data()))
        except UnidentifiedImageError:
            logging.warning(self.tr("Image format isn't supported"))
            return False
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
            logging.warning(self.tr("No QR codes found in clipboard"))

    @Slot()
    def readCameraQR(self):
        self.initUi()
        self.CameraGroup.setVisible(True)
        self.SlipDataGroup.setVisible(False)
        self.ScannerQR.startScan()

    @Slot()
    def closeCamera(self):
        self.ScannerQR.stopScan()
        self.CameraGroup.setVisible(False)
        self.SlipDataGroup.setVisible(True)

    @Slot()
    def onCameraQR(self, decoded_qr):
        self.closeCamera()
        self.qr_data_available.emit(decoded_qr)

    #-----------------------------------------------------------------------------------------------
    # Check if available QR data matches with self.QR_pattern
    # Emits qr_data_validated if match found. Otherwise shows warning message but allows to proceed
    @Slot()
    def parseQRdata(self, qr_data):
        self.QR_data = qr_data

        logging.info(self.tr("QR: " + self.QR_data))
        params = parse_qs(self.QR_data)
        try:
            for timestamp_pattern in self.timestamp_patterns:
                datetime = QDateTime.fromString(params['t'][0], timestamp_pattern)
                datetime.setTimeSpec(Qt.UTC)
                if datetime.isValid():
                    self.SlipTimstamp.setDateTime(datetime)
            self.SlipAmount.setText(params['s'][0])
            self.FN.setText(params['fn'][0])
            self.FD.setText(params['i'][0])
            self.FP.setText(params['fp'][0])
            self.SlipType.setCurrentIndex(int(params['n'][0]) - 1)
        except KeyError:
            logging.warning(self.tr("QR available but pattern isn't recognized: " + self.QR_data))
            return
        self.qr_data_validated.emit()

    def downloadSlipJSON(self):
        timestamp = self.SlipTimstamp.dateTime().toSecsSinceEpoch()

        attempt = 0
        while True:
            result = self.slipsAPI.get_slip(timestamp, float(self.SlipAmount.text()), self.FN.text(),
                                            self.FD.text(), self.FP.text(), self.SlipType.currentIndex() + 1)
            if result != SlipsTaxAPI.Pending:
                break
            if attempt > 5:
                logging.warning(self.tr("Max retry count exceeded."))
                break
            attempt += 1
            time.sleep(0.5) # wait half a second before next attempt

        if result == SlipsTaxAPI.Success:
            self.slip_json = self.slipsAPI.slip_json
            self.parseJSON()

    @Slot()
    def loadFileSlipJSON(self):
        json_file, _filter = \
            QFileDialog.getOpenFileName(self, self.tr("Select file with slip JSON data"),
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
                    logging.error(self.tr("Can't find 'receipt' tag in json 'document'"))
                    return
            else:
                logging.error(self.tr("Can't find 'document' tag in json 'ticket'"))
                return
        else:
            slip = self.slip_json

        # Get operation type
        operation = 0
        if 'operationType' in slip:
            operation = int(slip['operationType'])
        else:
            logging.error(self.tr("Can't find 'operationType' tag in json 'ticket'"))
            return
        # Get shop name
        shop_name = ''
        if 'user' in slip:
            shop_name = self.SlipShopName.setText(slip['user'])
        if (not shop_name) and ('userInn' in slip):
            shop_name = self.slipsAPI.get_shop_name_by_inn(slip['userInn'])
        self.SlipShopName.setText(shop_name)

        peer_id = self.match_shop_name(self.SlipShopName.text())
        if peer_id is not None:
            self.PeerEdit.selected_id = peer_id

        try:
            self.slip_lines = pd.DataFrame(slip['items'])
        except:
            return

        # Get date from timestamp
        if 'dateTime' in slip:
            slip_datetime = QDateTime.fromSecsSinceEpoch(int(slip['dateTime']))
            slip_datetime.setTimeSpec(Qt.UTC)
            self.SlipDateTime.setDateTime(slip_datetime)

        # Convert price to roubles
        self.slip_lines['price'] = self.slip_lines['price'] / 100
        if operation == self.OPERATION_PURCHASE:
            self.slip_lines['sum'] = -self.slip_lines['sum'] / 100
        elif operation == self.OPERATION_RETURN:
            self.slip_lines['sum'] = self.slip_lines['sum'] / 100
        else:
            logging.error(self.tr("Unknown operation type ") + f"{operation}")
            return
        # Use quantity if it differs from 1 unit value
        self.slip_lines.loc[self.slip_lines['quantity'] != 1, 'name'] = \
            self.slip_lines.agg('{0[name]} ({0[quantity]:g} x {0[price]:.2f})'.format, axis=1)
        # Assign empty category
        self.slip_lines['category'] = 0
        self.slip_lines['confidence'] = 1
        # Assign empty tags
        self.slip_lines['tag'] = None
        self.slip_lines = self.slip_lines[['name', 'category', 'confidence', 'tag', 'sum']]

        self.model = PandasLinesModel(self.slip_lines)
        self.LinesTableView.setModel(self.model)

        self.delegate = SlipLinesDelegate(self.LinesTableView)
        for column in range(self.model.columnCount()):
            if column == 0:
                self.LinesTableView.horizontalHeader().setSectionResizeMode(column, QHeaderView.Stretch)
            elif column == 1:
                self.LinesTableView.setColumnWidth(column, 200)
            elif column == 2:
                self.LinesTableView.setColumnHidden(column, True)
            else:
                self.LinesTableView.setColumnWidth(column, 100)
            self.LinesTableView.setItemDelegateForColumn(column, self.delegate)
        font = self.LinesTableView.horizontalHeader().font()
        font.setBold(True)
        self.LinesTableView.horizontalHeader().setFont(font)
        self.LinesTableView.show()
        self.qr_data_loaded.emit()

    def addOperation(self):
        if self.AccountEdit.selected_id == 0:
            logging.warning(self.tr("Not possible to import slip: no account set for import"))
            return
        if self.PeerEdit.selected_id == 0:
            logging.warning(self.tr("Not possible to import slip: can't import: no peer set for import"))
            return
        if self.slip_lines[self.slip_lines['category'] == 0].shape[0] != 0:
            logging.warning(self.tr("Not possible to import slip: some categories are not set"))
            return

        query = executeSQL("INSERT INTO actions (timestamp, account_id, peer_id) "
                           "VALUES (:timestamp, :account_id, :peer_id)",
                           [(":timestamp", self.SlipDateTime.dateTime().toSecsSinceEpoch()),
                            (":account_id", self.AccountEdit.selected_id),
                            (":peer_id", self.PeerEdit.selected_id)])
        pid = query.lastInsertId()
        # update mappings
        _ = executeSQL("INSERT INTO map_peer (value, mapped_to) VALUES (:peer_name, :peer_id)",
                       [(":peer_name", self.SlipShopName.text()), (":peer_id", self.PeerEdit.selected_id)])

        for index, row in self.slip_lines.iterrows():
            _ = executeSQL("INSERT INTO action_details (pid, category_id, tag_id, amount, note) "
                           "VALUES (:pid, :category_id, :tag_id, :amount, :note)",
                           [(":pid", pid), (":category_id", row['category']), (":tag_id", row['tag']),
                            (":amount", row['sum']), (":note", row['name'])])
            # update mappings
            _ = executeSQL("INSERT INTO map_category (value, mapped_to) VALUES (:item_name, :category_id)",
                           [(":item_name", row['name']), (":category_id", row['category'])], commit=True)
        self.clearSlipData()

    def clearSlipData(self):
        self.QR_data = ''
        self.slip_json = None
        self.slip_lines = None
        self.LinesTableView.setModel(None)

        self.initUi()

    def match_shop_name(self, shop_name):
        return readSQL("SELECT mapped_to FROM map_peer WHERE value=:shop_name",
                       [(":shop_name", shop_name)])

    @Slot()
    def recognizeCategories(self):
        if not self.tensor_flow_present:
            return
        self.slip_lines['category'], self.slip_lines['confidence'] = \
            recognize_categories(self.slip_lines['name'].tolist())
        self.model.dataChanged.emit(None, None)  # refresh full view