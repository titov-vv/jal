import logging
import pandas as pd
from decimal import Decimal
from PySide6.QtCore import Qt, Slot, QAbstractTableModel, QDateTime, QDate, QTime, QLocale
from PySide6.QtWidgets import QDialog, QHeaderView, QStyledItemDelegate, QLineEdit, QComboBox
from jal.widgets.reference_selector import CategorySelector, TagSelector
from jal.widgets.delegates import DateTimeEditWithReset
from jal.constants import CustomColor
from jal.widgets.helpers import dependency_present
from jal.db.helpers import localize_decimal, delocalize_decimal
from jal.db.peer import JalPeer
from jal.db.category import JalCategory
from jal.db.operations import LedgerTransaction
from jal.widgets.qr_scanner import ScanDialog
from jal.ui.ui_receipt_import_dlg import Ui_ImportShopReceiptDlg
from jal.data_import.category_recognizer import recognize_categories
from jal.data_import.receipt_api.receipts import ReceiptAPIFactory


DEFAULT_DATA_ROLE = Qt.UserRole + 1
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

    def columnCount(self, parent=None):
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
        self._category_selector = None  # Need to prevent object deletion in a middle
        self._tag_selector = None

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
            self._category_selector = CategorySelector(aParent, validate=False)
            return self._category_selector
        if index.column() == 3:
            self._tag_selector = TagSelector(aParent, validate=False)
            return self._tag_selector

    def setModelData(self, editor, model, index):
        if index.column() == 1:
            model.setData(index, editor.selected_id)
            model.setData(index.siblingAtColumn(2), 1) # set confidence level to 1
        if index.column() == 3:
            model.setData(index, editor.selected_id)

#-----------------------------------------------------------------------------------------------------------------------
# Delegate class that shows parameter editor according to its type
class ParameterDelegate(QStyledItemDelegate):    # Code doubles with pieces from delegates.py
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def createEditor(self, aParent, option, index):
        default_data = index.model().data(index, DEFAULT_DATA_ROLE)
        data_type = type(default_data)
        if data_type == str or data_type == int or data_type == Decimal:
            editor = QLineEdit(aParent)
        elif data_type == QDateTime or data_type == QDate:
            editor = DateTimeEditWithReset(aParent)
            editor.setTimeSpec(Qt.UTC)
            if data_type == QDate:
                editor.setDisplayFormat("dd/MM/yyyy")
            else:
                editor.setDisplayFormat("dd/MM/yyyy hh:mm")
        elif data_type == dict:
            editor = QComboBox(aParent)
            for idx in default_data:
                editor.addItem(default_data[idx], userData=idx)
        else:
            assert False, f"Delegate ParameterDelegate.createEditor() called for unsupported type {data_type}"
        return editor

    def setEditorData(self, editor, index):
        default_data = index.model().data(index, DEFAULT_DATA_ROLE)
        data_type = type(default_data)
        if data_type == str or data_type == int:
            editor.setText(str(index.model().data(index, Qt.EditRole)))
        elif data_type == Decimal:
            editor.setText(localize_decimal(index.model().data(index, Qt.EditRole)))
        elif data_type == QDateTime:
            editor.setDateTime(index.model().data(index, Qt.EditRole))
        elif data_type == QDate:
            editor.setDateTime(QDateTime(index.model().data(index, Qt.EditRole), QTime()))
        elif data_type == dict:
            editor.setCurrentIndex(editor.findData(index.model().data(index, Qt.EditRole)))
        else:
            assert False, f"Delegate ParameterDelegate.setEditorData() called for unsupported type {data_type}"
        return editor

    def setModelData(self, editor, model, index):
        default_data = index.model().data(index, DEFAULT_DATA_ROLE)
        data_type = type(default_data)
        if data_type == str:
            model.setData(index, editor.text())
        elif data_type == int:
            model.setData(index, QLocale().toInt(editor.text())[0])
        elif data_type == QDate:
            model.setData(index, editor.date())
        elif data_type == QDateTime:
            model.setData(index, editor.dateTime())
        elif data_type == Decimal:
            model.setData(index, delocalize_decimal(editor.text()))
        elif data_type == dict:
            model.setData(index, editor.currentData())
        else:
            assert False, f"Delegate ParameterDelegate.setModelData() called for unsupported type {data_type}"

#-----------------------------------------------------------------------------------------------------------------------
# Custom model to display and edit slip lines
class ParamsModel(QAbstractTableModel):
    def __init__(self, params_list: dict, parent=None):
        super().__init__(parent)
        self._params = params_list
        self._values = [(lambda x : x if type(x) != dict else next(iter(x)))(y) for y in self._params.values()]

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return super().flags(index) | Qt.ItemIsEditable

    def rowCount(self, parent=None):
        return len(self._params)

    def columnCount(self, parent=None):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            value = self._values[index.row()]
            default_value = list(self._params.values())[index.row()]
            if role == Qt.DisplayRole:
                if type(default_value) == Decimal:
                    return str(value)
                elif type(default_value) == dict:
                    return default_value[value]
                else:
                    return value
            elif role == Qt.EditRole:
                return value
            elif role == DEFAULT_DATA_ROLE:
                return default_value
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid():
            if role == Qt.EditRole:
                self._values[index.row()] = value
                self.dataChanged.emit(index, index)
                return True
        return False

    def headerData(self, row, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return list(self._params)[row]
        return None

    def params(self) -> dict:
        return dict(zip(self._params, self._values))


#-----------------------------------------------------------------------------------------------------------------------
class ImportReceiptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ImportShopReceiptDlg()
        self.ui.setupUi(self)
        self.model = None
        self.delegate = []
        self.params_model = None
        self._parameter_delegate = ParameterDelegate(self.ui.ReceiptParametersList)
        self.slip_lines = None
        self.receipt_api = None
        self.tensor_flow_present = dependency_present(['tensorflow'])

        self.ui.ScanReceiptQR.clicked.connect(self.processReceiptQR)
        self.ui.DownloadReceiptBtn.clicked.connect(self.processReceiptParams)
        self.ui.AddOperationBtn.clicked.connect(self.addOperation)
        self.ui.ClearBtn.clicked.connect(self.clearSlipData)
        self.ui.AssignCategoryBtn.clicked.connect(self.recognizeCategories)
        self.ui.ReceiptAPICombo.currentIndexChanged.connect(self.change_api)

        self.ui.ReceiptAPICombo.clear()
        for idx, name in ReceiptAPIFactory().supported_names.items():
            self.ui.ReceiptAPICombo.addItem(name, idx)

        self.ui.AssignCategoryBtn.setEnabled(self.tensor_flow_present)

    # -----------------------------------------------------------------------------------------------
    @Slot()
    def change_api(self, index):
        if index < 0:
            return
        api_type = self.ui.ReceiptAPICombo.currentData()
        self.params_model = ParamsModel(ReceiptAPIFactory().get_api_parameters(api_type))
        self.ui.ReceiptParametersList.setModel(self.params_model)
        self.ui.ReceiptParametersList.setItemDelegateForColumn(0, self._parameter_delegate)

    #-----------------------------------------------------------------------------------------------
    # Then it downloads the slip if match found. Otherwise, shows warning message but allows to proceed
    @Slot()
    def processReceiptQR(self):
        qr_data = ScanDialog.execute_scan(parent=self, message=self.tr("Please scan main QR code from the receipt"))
        if qr_data is None:
            return
        logging.info(self.tr("QR: " + qr_data))
        try:
            self.receipt_api = ReceiptAPIFactory().get_api_for_qr(qr_data)
        except ValueError as e:
            logging.warning(e)
            return
        self.receipt_api.slip_load_ok.connect(self.slip_loaded)
        self.downloadSlipJSON()

    @Slot()
    def processReceiptParams(self):
        api_type = self.ui.ReceiptAPICombo.currentData()
        try:
            self.receipt_api = ReceiptAPIFactory().get_api_with_params(api_type, self.params_model.params())
        except ValueError as e:
            logging.warning(e)
            return
        self.receipt_api.slip_load_ok.connect(self.slip_loaded)
        self.downloadSlipJSON()

    def downloadSlipJSON(self):
        if self.receipt_api is None:
            return
        if not self.receipt_api.activate_session():
            return
        self.receipt_api.query_slip()

    def slip_loaded(self):
        self.parseJSON()

    def parseJSON(self):
        self.slip_lines = pd.DataFrame(self.receipt_api.slip_lines())
        self.ui.SlipShopName.setText(self.receipt_api.shop_name())
        peer_id = JalPeer.get_id_by_mapped_name(self.ui.SlipShopName.text())
        if peer_id is not None:
            self.ui.PeerEdit.selected_id = peer_id
        self.ui.SlipDateTime.setDateTime(self.receipt_api.datetime())
        # Assign empty category
        self.slip_lines['category'] = 0
        self.slip_lines['confidence'] = 1
        # Assign empty tags
        self.slip_lines['tag'] = None
        self.slip_lines = self.slip_lines[['name', 'category', 'confidence', 'tag', 'amount']]

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
            logging.warning(self.tr("Not possible to import receipt: no account set for import"))
            return
        if self.ui.PeerEdit.selected_id == 0:
            logging.warning(self.tr("Not possible to import receipt: can't import: no peer set for import"))
            return
        if self.slip_lines[self.slip_lines['category'] == 0].shape[0] != 0:
            logging.warning(self.tr("Not possible to import receipt: some categories are not set"))
            return

        details = []
        for index, row in self.slip_lines.iterrows():
            details.append({
                "category_id": row['category'],
                "tag_id": row['tag'],
                "amount": row['amount'],
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
        self.slip_lines = None
        self.ui.LinesTableView.setModel(None)

    @Slot()
    def recognizeCategories(self):
        if not self.tensor_flow_present:
            logging.warning(self.tr("Categories are not recognized: Tensorflow is not found"))
            return
        self.slip_lines['category'], self.slip_lines['confidence'] = \
            recognize_categories(self.slip_lines['name'].tolist())
        self.model.dataChanged.emit(None, None)  # refresh full view
