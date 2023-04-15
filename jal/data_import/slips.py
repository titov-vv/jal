import time
import json
import logging
import pandas as pd
from urllib.parse import parse_qs
from PySide6.QtCore import Qt, Slot, QDateTime, QAbstractTableModel
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QHeaderView, QStyledItemDelegate
from jal.widgets.reference_selector import CategorySelector, TagSelector
from jal.constants import CustomColor
from jal.widgets.helpers import dependency_present, decodeQR
from jal.db.peer import JalPeer
from jal.db.category import JalCategory
from jal.db.operations import LedgerTransaction
from jal.data_import.slips_tax import SlipsTaxAPI
from jal.ui.ui_slip_import_dlg import Ui_ImportSlipDlg
from jal.data_import.category_recognizer import recognize_categories


#-----------------------------------------------------------------------------------------------------------------------
# Custom model to display and edit slip lines
class PandasLinesModel(QAbstractTableModel):
    def __init__(self, data, parent=None):
        super().__init__(parent)
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
        super().__init__(parent=parent)

    def paint(self, painter, option, index):
        painter.save()
        pen = painter.pen()
        model = index.model()
        if index.column() == 0:
            text = model.data(index, Qt.DisplayRole)
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        if index.column() == 1:
            text = JalCategory(int(model.data(index, Qt.DisplayRole))).name()
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
class ImportSlipDialog(QDialog):
    OPERATION_PURCHASE = 1
    OPERATION_RETURN = 2

    timestamp_patterns = ['yyyyMMddTHHmm', 'yyyyMMddTHHmmss', 'yyyy-MM-ddTHH:mm', 'yyyy-MM-ddTHH:mm:ss']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ImportSlipDlg()
        self.ui.setupUi(self)
        self.initUi()
        self.model = None
        self.delegate = []

        self.ui.CameraGroup.setVisible(False)

        self.QR_data = ''
        self.slip_json = None
        self.slip_lines = None

        self.slipsAPI = SlipsTaxAPI(self)
        self.tensor_flow_present = dependency_present(['tensorflow'])

        self.ui.LoadQRfromFileBtn.clicked.connect(self.loadFileQR)
        self.ui.GetQRfromClipboardBtn.clicked.connect(self.readClipboardQR)
        self.ui.GetQRfromCameraBtn.clicked.connect(self.readCameraQR)
        self.ui.StopCameraBtn.clicked.connect(self.closeCamera)
        self.ui.ScannerQR.decodedQR.connect(self.onCameraQR)
        self.ui.GetSlipBtn.clicked.connect(self.downloadSlipJSON)
        self.ui.LoadJSONfromFileBtn.clicked.connect(self.loadFileSlipJSON)
        self.ui.AddOperationBtn.clicked.connect(self.addOperation)
        self.ui.ClearBtn.clicked.connect(self.clearSlipData)
        self.ui.AssignCategoryBtn.clicked.connect(self.recognizeCategories)

        self.ui.AssignCategoryBtn.setEnabled(self.tensor_flow_present)

    def closeEvent(self, arg__1):
        self.ui.ScannerQR.stopScan()
        self.accept()

    def initUi(self):
        self.ui.SlipAmount.setText('')
        self.ui.FN.setText('')
        self.ui.FD.setText('')
        self.ui.FP.setText('')
        self.ui.SlipType.setCurrentIndex(0)

    #------------------------------------------------------------------------------------------
    # Loads graphics file and tries to read QR-code from it.
    @Slot()
    def loadFileQR(self):
        self.initUi()
        qr_file, _filter = \
            QFileDialog.getOpenFileName(self, self.tr("Select file with QR code"),
                                        ".", "JPEG images (*.jpg);;PNG images (*.png);;BMP images (*.bmp)")
        if qr_file:
            self.QR_data = decodeQR(QImage(qr_file))
            if self.QR_data:
                self.parseQRdata()
            else:
                logging.warning(self.tr("No QR codes were found in file"))

    # ------------------------------------------------------------------------------------------
    # Gets image from clipboard and tries to read QR-code from it.
    @Slot()
    def readClipboardQR(self):
        self.initUi()
        self.QR_data = decodeQR(QApplication.clipboard().image())
        if self.QR_data:
            self.parseQRdata()
        else:
            logging.warning(self.tr("No QR codes found in clipboard"))

    @Slot()
    def readCameraQR(self):
        self.initUi()
        self.ui.CameraGroup.setVisible(True)
        self.ui.SlipDataGroup.setVisible(False)
        self.ui.ScannerQR.startScan()

    @Slot()
    def closeCamera(self):
        self.ui.ScannerQR.stopScan()
        self.ui.CameraGroup.setVisible(False)
        self.ui.SlipDataGroup.setVisible(True)

    @Slot()
    def onCameraQR(self, decoded_qr):
        self.QR_data = decoded_qr
        self.closeCamera()
        self.parseQRdata()

    #-----------------------------------------------------------------------------------------------
    # Check if text in self.QR_data matches with self.QR_pattern
    # Then it downloads the slip if match found. Otherwise, shows warning message but allows to proceed
    @Slot()
    def parseQRdata(self):
        logging.info(self.tr("QR: " + self.QR_data))
        params = parse_qs(self.QR_data)
        try:
            for timestamp_pattern in self.timestamp_patterns:
                datetime = QDateTime.fromString(params['t'][0], timestamp_pattern)
                datetime.setTimeSpec(Qt.UTC)
                if datetime.isValid():
                    self.ui.SlipTimstamp.setDateTime(datetime)
            self.ui.SlipAmount.setText(params['s'][0])
            self.ui.FN.setText(params['fn'][0])
            self.ui.FD.setText(params['i'][0])
            self.ui.FP.setText(params['fp'][0])
            self.ui.SlipType.setCurrentIndex(int(params['n'][0]) - 1)
        except KeyError:
            logging.warning(self.tr("QR available but pattern isn't recognized: " + self.QR_data))
            return
        self.downloadSlipJSON()

    def downloadSlipJSON(self):
        timestamp = self.ui.SlipTimstamp.dateTime().toSecsSinceEpoch()

        attempt = 0
        while True:
            result = self.slipsAPI.get_slip(timestamp, float(self.ui.SlipAmount.text()), self.ui.FN.text(),
                                            self.ui.FD.text(), self.ui.FP.text(), self.ui.SlipType.currentIndex() + 1)
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
            shop_name = self.ui.SlipShopName.setText(slip['user'])
        if (not shop_name) and ('userInn' in slip):
            shop_name = self.slipsAPI.get_shop_name_by_inn(slip['userInn'])
        self.ui.SlipShopName.setText(shop_name)

        peer_id = JalPeer.get_id_by_mapped_name(self.ui.SlipShopName.text())
        if peer_id is not None:
            self.ui.PeerEdit.selected_id = peer_id

        try:
            self.slip_lines = pd.DataFrame(slip['items'])
        except:
            return

        # Get date from timestamp
        if 'dateTime' in slip:
            slip_datetime = QDateTime.fromSecsSinceEpoch(int(slip['dateTime']))
            slip_datetime.setTimeSpec(Qt.UTC)
            self.ui.SlipDateTime.setDateTime(slip_datetime)

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

        self.model = PandasLinesModel(self.slip_lines, self)
        self.ui.LinesTableView.setModel(self.model)

        self.delegate = SlipLinesDelegate(self.ui.LinesTableView)
        for column in range(self.model.columnCount()):
            if column == 0:
                self.ui.LinesTableView.horizontalHeader().setSectionResizeMode(column, QHeaderView.Stretch)
            elif column == 1:
                self.ui.LinesTableView.setColumnWidth(column, 200)
            elif column == 2:
                self.ui.LinesTableView.setColumnHidden(column, True)
            else:
                self.ui.LinesTableView.setColumnWidth(column, 100)
            self.ui.LinesTableView.setItemDelegateForColumn(column, self.delegate)
        font = self.ui.LinesTableView.horizontalHeader().font()
        font.setBold(True)
        self.ui.LinesTableView.horizontalHeader().setFont(font)
        self.ui.LinesTableView.show()
        self.recognizeCategories()

    def addOperation(self):
        if self.ui.AccountEdit.selected_id == 0:
            logging.warning(self.tr("Not possible to import slip: no account set for import"))
            return
        if self.ui.PeerEdit.selected_id == 0:
            logging.warning(self.tr("Not possible to import slip: can't import: no peer set for import"))
            return
        if self.slip_lines[self.slip_lines['category'] == 0].shape[0] != 0:
            logging.warning(self.tr("Not possible to import slip: some categories are not set"))
            return

        details = []
        for index, row in self.slip_lines.iterrows():
            details.append({
                "category_id": row['category'],
                "tag_id": row['tag'],
                "amount": row['sum'],
                "note": row['name']
            })
            JalCategory(row['category']).add_or_update_mapped_name(row['name'])
        operation = {
            "timestamp": self.ui.SlipDateTime.dateTime().toSecsSinceEpoch(),
            "account_id": self.ui.AccountEdit.selected_id,
            "peer_id": self.ui.PeerEdit.selected_id,
            "lines": details
        }
        LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, operation)
        JalPeer(self.ui.PeerEdit.selected_id).add_or_update_mapped_name(self.ui.SlipShopName.text(), )
        self.clearSlipData()

    def clearSlipData(self):
        self.QR_data = ''
        self.slip_json = None
        self.slip_lines = None
        self.ui.LinesTableView.setModel(None)

        self.initUi()

    @Slot()
    def recognizeCategories(self):
        if not self.tensor_flow_present:
            logging.warning(self.tr("Categories are not recognized: Tensorflow is not found"))
            return
        self.slip_lines['category'], self.slip_lines['confidence'] = \
            recognize_categories(self.slip_lines['name'].tolist())
        self.model.dataChanged.emit(None, None)  # refresh full view
