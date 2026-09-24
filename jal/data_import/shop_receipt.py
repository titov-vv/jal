import base64
import logging
import zipfile
import pandas as pd
from PySide6.QtCore import Qt, Slot, QAbstractTableModel, QT_TRANSLATE_NOOP
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHeaderView, QStyle, QStyledItemDelegate, QTableWidgetItem
from jal.constants import Setup
from jal.widgets.reference_selector import ReferenceSelectorWidget
from jal.widgets.delegates import draw_item_panel
from jal.widgets.helpers import (set_grids_metrics, set_date_formats, restore_columns, save_columns, ts2dt)
from jal.widgets.theme import Theme, Meaning
from jal.db.helpers import localize_decimal
from jal.db.peer import JalPeer
from jal.db.clock import local_zone
from jal.db.category import JalCategory
from jal.db.operations import LedgerTransaction, IncomeSpending
from jal.db.settings import JalSettings
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor
from jal.db.common_models import AccountListModel, PeerTreeModel, CategoryTreeModel, TagTreeModel
from jal.widgets.reference_dialogs import AccountListDialog, PeerListDialog, CategoryListDialog, TagsListDialog
from jal.ui.ui_receipt_import_dlg import Ui_ImportShopReceiptDlg
from jal.data_import.receipt_api.offline_receipt import ReceiptOffline, paper_lines
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS
from jal.data_import.receipt_pdf import pdf_receipt
from jal.data_import.receipt_inbox import JalrFile, Route, scan_inbox, move_done, route


RECEIPT_INBOX_SETTING = "ReceiptInboxFolder"

SettingsRegistry.register(SettingDescriptor(
    key=RECEIPT_INBOX_SETTING,
    page=QT_TRANSLATE_NOOP("Preferences", "Import"),
    label=QT_TRANSLATE_NOOP("Preferences", "Phone receipt inbox folder"),
    tooltip=QT_TRANSLATE_NOOP("Preferences",
                              "The folder the phone app's receipt files arrive in. An imported file is moved into "
                              "its 'done' subfolder.")))
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
            if col == 2:
                return self.tr("Tag")
            if col == 3:
                return self.tr("Amount")
        return None


class SlipLinesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._category_selector = None  # Need to prevent object deletion in a middle
        self._tag_selector = None

    def paint(self, painter, option, index):
        draw_item_panel(painter, option)
        selected = bool(option.state & QStyle.State_Selected)
        painter.save()
        pen = painter.pen()
        if selected:
            pen.setColor(option.palette.highlightedText().color())
            painter.setPen(pen)
        model = index.model()
        if index.column() == 0:
            text = model.data(index, Qt.DisplayRole)
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        if index.column() == 1:
            text = JalCategory(int(model.data(index, Qt.DisplayRole))).name()
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        elif index.column() == 3:
            amount = model.data(index, Qt.DisplayRole)
            if amount == 2 and not selected:
                pen.setColor(Theme.text(Meaning.MUTED))
                painter.setPen(pen)
            text = f"{amount:,.2f}"
            painter.drawText(option.rect, Qt.AlignRight | Qt.AlignVCenter, text)
        painter.setPen(pen)
        painter.restore()

    def createEditor(self, aParent, option, index):
        if index.column() == 1:
            self._category_selector = ReferenceSelectorWidget(aParent, validate=False)
            self._category_selector.setup_selector(CategoryTreeModel, CategoryListDialog, aParent)
            return self._category_selector
        if index.column() == 2:
            self._tag_selector = ReferenceSelectorWidget(aParent, validate=False)
            self._tag_selector.setup_selector(TagTreeModel, TagsListDialog, aParent)
            return self._tag_selector
        return None

    def setModelData(self, editor, model, index):
        if index.column() == 1:
            model.setData(index, editor.selected_id)
        if index.column() == 2:
            model.setData(index, editor.selected_id)

#-----------------------------------------------------------------------------------------------------------------------
class ImportReceiptDialog(QDialog):
    GEOMETRY_KEY = "DlgGeometry_ImportReceipt"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ImportShopReceiptDlg()
        self.ui.setupUi(self)
        set_grids_metrics(self)
        set_date_formats(self)
        self.ui.SlipDateTime.setTimeZone(local_zone())   # what a receipt states is a reading of the buyer's own clock
        self.ui.AccountEdit.setup_selector(AccountListModel, AccountListDialog, self)
        self.ui.PeerEdit.setup_selector(PeerTreeModel, PeerListDialog, self)
        self.model = None
        self.delegate = []
        self.slip_lines = None
        self.receipt_api = None
        self._inbox = []              # (JalrFile, Route) per row of InboxList
        self._inbox_file = ''         # path of the inbox file the loaded receipt came from

        # 'Clear' and 'Add' join the button box rather than sit next to it: neither ends the dialog - one throws the
        # loaded receipt away, the other writes an operation and leaves the window open for the next receipt - so
        # they are declared with the roles that say so and the style decides where they go relative to Close.
        self.add_operation_button = self.ui.DialogButtonBox.addButton(self.tr("Add"), QDialogButtonBox.ActionRole)
        self.clear_button = self.ui.DialogButtonBox.addButton(self.tr("Clear"), QDialogButtonBox.ResetRole)

        self.add_operation_button.clicked.connect(self.addOperation)
        self.clear_button.clicked.connect(self.clearSlipData)
        self.ui.DialogButtonBox.rejected.connect(self.close)
        self.ui.InboxLoadBtn.clicked.connect(self.loadInboxReceipt)
        self.ui.InboxRefreshBtn.clicked.connect(self.refreshInbox)
        self.ui.InboxSkipBtn.clicked.connect(self.skipInboxReceipt)
        self.ui.InboxList.itemDoubleClicked.connect(self.loadInboxReceipt)
        self.ui.InboxList.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ui.InboxList.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.refreshInbox()
        stored = JalSettings().getStr(self.GEOMETRY_KEY)
        if stored:
            self.restoreGeometry(base64.decodebytes(stored.encode('utf-8')))

    # Every exit (Close, window X, Esc) ends here; closeEvent() alone misses Esc
    def done(self, result):
        JalSettings().setValue(self.GEOMETRY_KEY, base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        self._save_lines_columns()
        super().done(result)

    # Without a loaded receipt the header has no sections, and saving it would wipe the stored widths
    def _save_lines_columns(self):
        if self.ui.LinesTableView.model() is not None:
            save_columns(self, Setup.COLUMNS_STATE_PREFIX)

    # -----------------------------------------------------------------------------------------------
    # Lists the receipt files that the phone app has delivered into the inbox folder
    @Slot()
    def refreshInbox(self):
        folder = JalSettings().getStr(RECEIPT_INBOX_SETTING)
        self._inbox = [(x, route(x)) for x in scan_inbox(folder)]
        if folder:
            self.ui.InboxFolderLbl.setText(folder)
        else:
            self.ui.InboxFolderLbl.setText(self.tr("Set the phone receipt inbox folder in Preferences"))
        self.ui.InboxList.setRowCount(len(self._inbox))
        for row, (receipt, receipt_route) in enumerate(self._inbox):
            captured = ts2dt(int(receipt.captured_at.timestamp()))
            self.ui.InboxList.setItem(row, 0, QTableWidgetItem(captured))
            self.ui.InboxList.setItem(row, 1, QTableWidgetItem(self._source_name(receipt.kind)))
            self.ui.InboxList.setItem(row, 2, QTableWidgetItem(self._route_text(receipt_route)))
        self.ui.InboxLoadBtn.setEnabled(bool(self._inbox))
        self.ui.InboxSkipBtn.setEnabled(bool(self._inbox))

    def _source_name(self, kind: str) -> str:
        names = {
            JalrFile.PAPER_SCAN: self.tr("Paper scan"),
            JalrFile.IMAGE_IMPORT: self.tr("Image"),
            JalrFile.PDF_IMPORT: self.tr("PDF")
        }
        return names[kind]

    def _route_text(self, receipt_route: Route) -> str:
        if receipt_route.kind == Route.PT_QR:
            qr = receipt_route.at_qr
            return self.tr("Portuguese QR") + f": NIF {qr.nif}, {localize_decimal(qr.total)}"
        if receipt_route.kind == Route.PT_ITEMS:
            qr = receipt_route.at_qr
            return self.tr("Portuguese QR and items") + f": NIF {qr.nif}, {localize_decimal(qr.total)}"
        if receipt_route.kind == Route.FNS:
            return self.tr("Russian QR")
        if receipt_route.kind == Route.PDF:
            return self.tr("PDF document")
        reasons = {
            Route.NO_CODE: self.tr("no QR code found"),
            Route.UNKNOWN_CODE: self.tr("QR code isn't recognized"),
            Route.DOCUMENT_TYPE: self.tr("document type isn't a sale or a return"),
            Route.DOCUMENT_STATUS: self.tr("document is annulled or not final")
        }
        return self.tr("Unsupported") + ": " + reasons[receipt_route.reason]

    @Slot()
    def loadInboxReceipt(self):
        row = self.ui.InboxList.currentRow()
        if row < 0 or row >= len(self._inbox):
            return
        receipt, receipt_route = self._inbox[row]
        if receipt_route.kind == Route.PT_QR:
            receipt_api = ReceiptOffline.from_at_qr(receipt_route.at_qr, receipt.captured_at)
        elif receipt_route.kind == Route.PT_ITEMS:
            lines = paper_lines(receipt, receipt_route.at_qr)
            receipt_api = ReceiptOffline.from_at_qr(receipt_route.at_qr, receipt.captured_at, lines)
        elif receipt_route.kind == Route.FNS:
            try:
                receipt_api = ReceiptRuFNS(qr_text=receipt_route.code)
            except ValueError as e:
                logging.warning(e)
                return
        elif receipt_route.kind == Route.PDF:
            try:
                data = receipt.pdf_bytes()
            except (OSError, KeyError, zipfile.BadZipFile) as e:
                logging.warning(self.tr("Receipt file can't be read") + f" ({receipt.name}): {e}")
                return
            receipt_api = pdf_receipt(data, receipt_route.at_qr, receipt.captured_at)
            if receipt_api is None:
                return
        else:
            logging.warning(self.tr("Receipt can't be imported") + f" ({receipt.name}): " +
                            self._route_text(receipt_route))
            return
        self.receipt_api = receipt_api
        self._inbox_file = receipt.path
        self.receipt_api.slip_load_ok.connect(self.slip_loaded)
        self.downloadSlipJSON()

    # A file that isn't to be imported leaves the inbox without an operation
    @Slot()
    def skipInboxReceipt(self):
        row = self.ui.InboxList.currentRow()
        if row < 0 or row >= len(self._inbox):
            return
        receipt, _ = self._inbox[row]
        if receipt.path == self._inbox_file:
            self.clearSlipData()
        try:
            move_done(receipt.path)
        except OSError as e:
            logging.warning(self.tr("Receipt file can't be moved out of the inbox") + f": {e}")
        self.refreshInbox()

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
        # Assign empty tags
        self.slip_lines['tag'] = None
        self.slip_lines = self.slip_lines[['name', 'category', 'tag', 'amount']]

        self.model = PandasLinesModel(self.slip_lines, self)
        self.ui.LinesTableView.setModel(self.model)

        self.delegate = SlipLinesDelegate(self.ui.LinesTableView)
        for column in range(self.model.columnCount()):
            if column == 0:
                self.ui.LinesTableView.horizontalHeader().setSectionResizeMode(column, QHeaderView.Stretch)
            elif column == 1:
                self.ui.LinesTableView.setColumnWidth(column, 200)
            else:
                self.ui.LinesTableView.setColumnWidth(column, 100)
            self.ui.LinesTableView.setItemDelegateForColumn(column, self.delegate)
        restore_columns(self.ui.LinesTableView, Setup.COLUMNS_STATE_PREFIX)   # a width the user has set outlives the next receipt
        self.ui.LinesTableView.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)   # a restored state may carry none
        self.ui.LinesTableView.show()

    def addOperation(self):
        if self.slip_lines is None:
            return
        if self.ui.AccountEdit.selected_id == 0:
            logging.warning(self.tr("Not possible to import receipt: no account set for import"))
            return
        if self.ui.PeerEdit.selected_id == 0:
            logging.warning(self.tr("Not possible to import receipt: can't import: no peer set for import"))
            return
        if self.slip_lines[self.slip_lines['category'] == 0].shape[0] != 0:
            logging.warning(self.tr("Not possible to import receipt: some categories are not set"))
            return

        number = self.receipt_api.number() if self.receipt_api is not None else ''
        if IncomeSpending.find_by_number(number):
            logging.warning(self.tr("Not possible to import receipt: it is imported already") + f" ({number})")
            self._finish_inbox_file()
            return

        details = []
        for index, row in self.slip_lines.iterrows():
            details.append({
                "category_id": row['category'],
                "tag_id": row['tag'],
                "amount": row['amount'],
                "note": row['name']
            })
        operation = {
            "timestamp": self.ui.SlipDateTime.dateTime().toSecsSinceEpoch(),
            "account_id": self.ui.AccountEdit.selected_id,
            "peer_id": self.ui.PeerEdit.selected_id,
            "number": number,
            "lines": details
        }
        LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, operation)
        JalPeer(self.ui.PeerEdit.selected_id).add_or_update_mapped_name(self.ui.SlipShopName.text(), )
        self._finish_inbox_file()
        self.clearSlipData()

    # The inbox file of a receipt that is in the ledger now leaves the inbox
    def _finish_inbox_file(self):
        if not self._inbox_file:
            return
        try:
            move_done(self._inbox_file)
        except OSError as e:
            logging.warning(self.tr("Receipt file can't be moved out of the inbox") + f": {e}")
        self._inbox_file = ''
        self.refreshInbox()

    # The inbox file of a receipt that is cleared stays in the inbox
    def clearSlipData(self):
        self.slip_lines = None
        self._inbox_file = ''
        self._save_lines_columns()
        self.ui.LinesTableView.setModel(None)
