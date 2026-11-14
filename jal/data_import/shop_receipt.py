import os
import base64
import logging
import zipfile
import pandas as pd
from datetime import datetime
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, Slot, QAbstractTableModel, QModelIndex, QRect, QT_TRANSLATE_NOOP
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QHeaderView, QLineEdit, QMessageBox, QStyle, \
    QTableWidgetItem
from jal.constants import Setup
from jal.widgets.reference_selector import ReferenceSelectorWidget
from jal.widgets.delegates import draw_item_panel, KbSafeItemDelegate
from jal.widgets.helpers import (set_grids_metrics, set_date_formats, restore_columns, save_columns, ts2dt)
from jal.widgets.theme import Theme, Meaning
from jal.db.helpers import localize_decimal
from jal.db.peer import JalPeer
from jal.db.receipt_memory import JalReceiptMemory
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.clock import local_zone
from jal.db.category import JalCategory
from jal.db.tag import JalTag
from jal.db.operations import LedgerTransaction, IncomeSpending
from jal.db.settings import JalSettings
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor
from jal.db.common_models import AccountListModel, PeerTreeModel, CategoryTreeModel, TagTreeModel
from jal.widgets.reference_dialogs import AccountListDialog, PeerListDialog, CategoryListDialog, TagsListDialog
from jal.ui.ui_receipt_import_dlg import Ui_ImportShopReceiptDlg
from jal.data_import.receipt_api.offline_receipt import ReceiptOffline, paper_lines, line_of_row
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS
from jal.data_import.receipt import LineTrust, Verdict, parse_card
from jal.data_import.receipt_pdf import layout_text, pdf_codes, pdf_receipt
from jal.data_import.receipt_inbox import JalrFile, Route, scan_inbox, move_done, route, wrap_pdf


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
    COLUMNS = ['name', 'category', 'tag', 'amount']     # of the view; the data has HIDDEN_COLUMNS after them
    # LineTrust, the rows of the scan the line was read from, the name the line was loaded with and how the line
    # was recalled from the shop's earlier receipts (JalReceiptMemory.EXACT or GUESS)
    HIDDEN_COLUMNS = ['trust', 'source', 'printed', 'memory']
    NAME, CATEGORY, TAG, AMOUNT, TRUST, SOURCE, PRINTED, MEMORY = range(8)

    # 'expected_total' is what the lines should add up to, None if nothing tells it
    def __init__(self, data, parent=None, expected_total=None):
        super().__init__(parent)
        self._data = data
        self._expected_total = expected_total

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return super().flags(index) | Qt.ItemIsEditable

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole or role == Qt.EditRole:
                return self._data.iloc[index.row(), index.column()]
            if role == Qt.ToolTipRole:
                texts = [self._trust_text(self.trust(index.row())), self._memory_text(index.row())]
                return "\n".join(x for x in texts if x) or None
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid():
            if role == Qt.EditRole:
                self._data.iloc[index.row(), index.column()] = value
                if index.column() == self.AMOUNT:     # an amount the user has set is nobody's reading any more
                    self._data.iloc[index.row(), self.TRUST] = ''
                else:                                 # nor is a line the user has changed a recalled one
                    self._data.iloc[index.row(), self.MEMORY] = ''
                self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), self.AMOUNT))
                return True
        return False

    # LineTrust of the line, '' for a line without a mark
    def trust(self, row: int) -> str:
        return self._data.iloc[row, self.TRUST]

    # How the line was recalled: JalReceiptMemory.EXACT, GUESS or '' for a line that wasn't
    def memory(self, row: int) -> str:
        return self._data.iat[row, self.MEMORY]

    def _memory_text(self, row: int):
        texts = {
            JalReceiptMemory.EXACT: self.tr("Remembered from the shop's earlier receipts, printed as"),
            JalReceiptMemory.GUESS: self.tr("A guess by a similar item of the shop's earlier receipts, check it; "
                                            "printed as")
        }
        text = texts.get(self.memory(row))
        return f"{text} '{self._data.iat[row, self.PRINTED]}'" if text else None

    # Gives the lines without a category what the shop's earlier receipts made of the same printed items
    def recall(self, memory: JalReceiptMemory):
        for row in range(self.rowCount()):
            if self._data.iat[row, self.CATEGORY] or not self._data.iat[row, self.PRINTED]:
                continue
            item, how = memory.find(self._data.iat[row, self.PRINTED])
            if item is None:
                continue
            if item['name']:
                self._data.iat[row, self.NAME] = item['name']
            self._data.iat[row, self.CATEGORY] = int(item['category_id'])
            self._data.iat[row, self.TAG] = int(item['tag_id']) if item['tag_id'] else None
            self._data.iat[row, self.MEMORY] = how
            self.dataChanged.emit(self.index(row, 0), self.index(row, self.AMOUNT))

    # Rows of the scan's 'ocr.lines' the line was read from, () for a line that has none
    def source(self, row: int) -> tuple:
        return self._data.iat[row, self.SOURCE]

    # What a line whose amount wasn't read must be for the lines to add up; None for any other line or without a
    # total to add up to
    def offered_amount(self, row: int):
        if self.trust(row) != LineTrust.MISSING or self._expected_total is None:
            return None
        return self._expected_total - sum(self._data['amount'], Decimal('0')) + self._data.iat[row, self.AMOUNT]

    def _trust_text(self, trust: str):
        texts = {
            LineTrust.PROVEN: self.tr("Reconciled: the lines add up to the receipt's total"),
            LineTrust.READ: self.tr("Read confidently, but the lines don't add up to the receipt's total"),
            LineTrust.UNRELIABLE: self.tr("Unreliable: read poorly or without a fiscal code to check against"),
            LineTrust.MISSING: self.tr("The amount wasn't read: set it, or delete the line")
        }
        return texts.get(trust)

    # Appends a line, an empty one by default, and returns its row
    def add_line(self, name: str = '', amount: Decimal = Decimal('0'), trust: str = '', source: tuple = ()) -> int:
        row = self.rowCount()
        self.beginInsertRows(QModelIndex(), row, row)
        self._data.loc[row] = pd.Series([name, 0, None, amount, trust, tuple(source), name, ''],
                                        index=self._data.columns, dtype=object)
        self.endInsertRows()
        return row

    # Gives the value to the lines that have none in the column (CATEGORY or TAG) yet
    def fill_empty(self, column: int, value: int):
        for row in range(self.rowCount()):
            if not self._data.iat[row, column]:
                self._data.iat[row, column] = value
                self.dataChanged.emit(self.index(row, column), self.index(row, column))

    def removeRows(self, row, count, parent=QModelIndex()):
        if row < 0 or count < 1 or row + count > self.rowCount():
            return False
        self.beginRemoveRows(parent, row, row + count - 1)
        self._data.drop(index=self._data.index[row:row + count], inplace=True)
        self._data.reset_index(drop=True, inplace=True)
        self.endRemoveRows()
        return True

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


class SlipLinesDelegate(KbSafeItemDelegate):
    TRUST_MEANING = {LineTrust.PROVEN: Meaning.POSITIVE, LineTrust.READ: Meaning.WARNING,
                     LineTrust.UNRELIABLE: Meaning.NEGATIVE, LineTrust.MISSING: Meaning.NEGATIVE}
    MEMORY_MEANING = {JalReceiptMemory.EXACT: Meaning.INFO, JalReceiptMemory.GUESS: Meaning.WARNING}
    MARK_WIDTH = 4

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
            rect = option.rect
            meaning = self.TRUST_MEANING.get(model.trust(index.row()))
            if meaning is not None:     # a bar in the colour of the line's trust, explained by the tooltip
                painter.fillRect(QRect(rect.left(), rect.top() + 2, self.MARK_WIDTH, rect.height() - 4),
                                 Theme.text(meaning))
            text = model.data(index, Qt.DisplayRole)
            painter.drawText(rect.adjusted(2 * self.MARK_WIDTH, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, text)
        if index.column() == 1:
            text = JalCategory(int(model.data(index, Qt.DisplayRole))).name()
            meaning = self.MEMORY_MEANING.get(model.memory(index.row()))
            if meaning is not None and not selected:     # a recalled category is told by its colour
                painter.setPen(Theme.text(meaning))
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        elif index.column() == 2:
            tag_id = model.data(index, Qt.DisplayRole)
            text = JalTag(int(tag_id)).name() if tag_id else ''
            painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        elif index.column() == 3:
            amount = model.data(index, Qt.DisplayRole)
            if amount == 2 and not selected:
                pen.setColor(Theme.text(Meaning.MUTED))
                painter.setPen(pen)
            text = "?" if model.trust(index.row()) == LineTrust.MISSING else f"{amount:,.2f}"
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
        return QLineEdit(aParent)

    def setEditorData(self, editor, index):
        if index.column() == PandasLinesModel.AMOUNT and index.model().offered_amount(index.row()) is not None:
            editor.setText(str(index.model().offered_amount(index.row())))     # taken with Enter, dropped with Esc
        elif index.column() in (PandasLinesModel.NAME, PandasLinesModel.AMOUNT):
            editor.setText(str(index.model().data(index, Qt.EditRole)))
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if index.column() == 0:
            model.setData(index, editor.text().strip())
        if index.column() == 1:
            model.setData(index, editor.selected_id)
        if index.column() == 2:
            model.setData(index, editor.selected_id)
        if index.column() == 3:     # text that isn't an amount leaves the line as it was
            try:
                amount = Decimal(editor.text().replace(' ', '').replace(',', '.'))
            except InvalidOperation:
                return
            if amount.is_finite():
                model.setData(index, amount)

#-----------------------------------------------------------------------------------------------------------------------
class ImportReceiptDialog(QDialog):
    GEOMETRY_KEY = "DlgGeometry_ImportReceipt"
    SPLITTER_KEY = "DlgSplitter_ImportReceipt"

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
        self._category_dialog = None  # built on the first click of AssignCategoryBtn
        self._tags_dialog = None      # built on the first click of AssignTagBtn
        self._inbox = []              # (JalrFile, Route) per row of InboxList
        self._inbox_file = ''         # path of the inbox file the loaded receipt came from
        self._scan = None             # JalrFile of the loaded receipt if it has page images
        self._scan_sign = Decimal('-1')     # of a line added from the scan: spent, or money back for a credit note
        self._scan_offers = False     # the rows of the scan's body that are no line are offered for adding

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
        self.ui.InboxAddPdfBtn.clicked.connect(self.addPdfReceipts)
        self.ui.InboxList.itemDoubleClicked.connect(self.loadInboxReceipt)
        self.ui.AddLineBtn.clicked.connect(self.addLine)
        self.ui.DeleteLineBtn.clicked.connect(self.deleteLine)
        self.ui.AssignCategoryBtn.clicked.connect(self.assignCategory)
        self.ui.AssignTagBtn.clicked.connect(self.assignTag)
        self.ui.ScanView.row_activated.connect(self.addScanRow)
        self.ui.PeerEdit.changed.connect(self._recall_lines)
        self.ui.ScanView.hide()
        self.ui.InboxList.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ui.InboxList.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.refreshInbox()
        self._show_verdict()
        stored = JalSettings().getStr(self.GEOMETRY_KEY)
        if stored:
            self.restoreGeometry(base64.decodebytes(stored.encode('utf-8')))
        stored = JalSettings().getStr(self.SPLITTER_KEY)
        if stored:
            self.ui.ScanSplitter.restoreState(base64.decodebytes(stored.encode('utf-8')))

    # Every exit (Close, window X, Esc) ends here; closeEvent() alone misses Esc
    def done(self, result):
        JalSettings().setValue(self.GEOMETRY_KEY, base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        JalSettings().setValue(self.SPLITTER_KEY,
                               base64.encodebytes(self.ui.ScanSplitter.saveState().data()).decode('utf-8'))
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
        self.ui.InboxAddPdfBtn.setEnabled(os.path.isdir(folder))

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
        if receipt_route.kind == Route.UNVERIFIED:
            if receipt_route.at_qr is None:
                return self.tr("Not verified, no fiscal code")
            qr = receipt_route.at_qr
            return self.tr("Not verified, Portuguese QR") + f": NIF {qr.nif}, {localize_decimal(qr.total)}"
        if receipt_route.kind == Route.FNS:
            return self.tr("Russian QR")
        if receipt_route.kind == Route.PDF:
            return self.tr("PDF document")
        reasons = {
            Route.NO_CODE: self.tr("no QR code found"),
            Route.UNKNOWN_CODE: self.tr("QR code isn't recognized"),
            Route.DOCUMENT_TYPE: self.tr("document type isn't a sale or a return"),
            Route.DOCUMENT_STATUS: self.tr("document is annulled or not final"),
            Route.NO_VALUE: self.tr("no money moved (signed total 0.00)")
        }
        return self.tr("Unsupported") + ": " + reasons[receipt_route.reason]

    @Slot()
    def loadInboxReceipt(self):
        row = self.ui.InboxList.currentRow()
        if row < 0 or row >= len(self._inbox):
            return
        receipt, receipt_route = self._inbox[row]
        text = receipt.ocr_texts
        proven = False
        if receipt_route.kind == Route.PT_QR:
            receipt_api = ReceiptOffline.from_at_qr(receipt_route.at_qr, receipt.captured_at, text=text)
        elif receipt_route.kind == Route.PT_ITEMS:
            lines, proven = paper_lines(receipt, receipt_route.at_qr)
            receipt_api = ReceiptOffline.from_at_qr(receipt_route.at_qr, receipt.captured_at, lines, text,
                                                    Verdict.RECONCILED if proven else Verdict.NOT_RECONCILED)
        elif receipt_route.kind == Route.UNVERIFIED:
            if QMessageBox().question(self, self.tr("Receipt without a usable fiscal code"),
                                      self.tr("The scan has no fiscal code that could be relied on, so nothing proves "
                                              "its lines. A rescan is recommended. Load it anyway?"),
                                      QMessageBox.Yes, QMessageBox.No) != QMessageBox.Yes:
                return
            lines, _ = paper_lines(receipt, receipt_route.at_qr)
            if receipt_route.at_qr is None:
                receipt_api = ReceiptOffline.unverified(receipt, lines)
            else:
                receipt_api = ReceiptOffline.from_at_qr(receipt_route.at_qr, receipt.captured_at, lines, text,
                                                        Verdict.NO_CODE)
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
            text = layout_text(data)
        else:
            logging.warning(self.tr("Receipt can't be imported") + f" ({receipt.name}): " +
                            self._route_text(receipt_route))
            return
        self._select_account_by_card(text, receipt_route.currency or receipt_api.currency())
        self.receipt_api = receipt_api
        self._inbox_file = receipt.path
        self._scan = receipt if receipt.image_names else None
        self._scan_sign = Decimal('1') if receipt_route.at_qr is not None and receipt_route.at_qr.is_return \
            else Decimal('-1')
        self._scan_offers = receipt_route.kind in (Route.PT_ITEMS, Route.UNVERIFIED) and not proven
        self.receipt_api.slip_load_ok.connect(self.slip_loaded)
        self.receipt_api.slip_load_failed.connect(self.slip_failed)
        self.downloadSlipJSON()

    # The account whose card the receipt prints; none without a match, so the last receipt's account isn't reused.
    # 'currency' is a code, any currency if empty
    def _select_account_by_card(self, text: list, currency: str):
        digits = parse_card(text)
        currency_id = next((x.id() for x in JalAsset.get_currencies() if x.symbol() == currency), 0) if currency else 0
        if not digits or (currency and not currency_id):     # a currency the ledger doesn't have holds no account
            self.ui.AccountEdit.selected_id = 0
            return
        self.ui.AccountEdit.selected_id = JalAccount.find_by_card(digits, currency_id).id()

    # PDF files of this computer join the inbox as the containers the phone would have made of them
    @Slot()
    def addPdfReceipts(self):
        folder = JalSettings().getStr(RECEIPT_INBOX_SETTING)
        names, _filter = QFileDialog.getOpenFileNames(self, self.tr("Select PDF receipts"), '',
                                                      self.tr("PDF files (*.pdf)"))
        added = ''
        for name in names:
            try:
                with open(name, 'rb') as pdf_file:
                    data = pdf_file.read()
                codes, pages = pdf_codes(data)
                if not pages:
                    logging.warning(self.tr("File isn't a readable PDF") + f": {name}")
                    continue
                captured_at = datetime.fromtimestamp(os.path.getmtime(name)).astimezone()
                added = wrap_pdf(folder, data, codes, pages, captured_at)
            except OSError as e:
                logging.warning(self.tr("PDF receipt can't be put into the inbox") + f" ({name}): {e}")
        self.refreshInbox()
        row = next((i for i, (receipt, _route) in enumerate(self._inbox) if receipt.path == added), -1)
        if row >= 0:
            self.ui.InboxList.setCurrentCell(row, 0)

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

    # The receipt loaded before isn't left on the form, where it would be added under the failed one's number
    @Slot(str)
    def slip_failed(self, reason: str):
        self.clearSlipData()
        self.receipt_api = None
        QMessageBox().warning(self, self.tr("Receipt wasn't loaded"), reason, QMessageBox.Ok)

    def parseJSON(self):
        self.slip_lines = pd.DataFrame(self.receipt_api.slip_lines())
        self.ui.SlipShopName.setText(self.receipt_api.shop_name())
        peer_id = JalPeer.get_id_by_mapped_name(self.ui.SlipShopName.text())
        self.ui.PeerEdit.selected_id = peer_id if peer_id is not None else 0   # the last receipt's peer isn't reused
        self.ui.SlipDateTime.setDateTime(self.receipt_api.datetime())
        self.ui.NoteEdit.clear()     # the last receipt's note isn't reused
        # A line may come with its category, the others get an empty one
        if 'category' in self.slip_lines:
            self.slip_lines['category'] = self.slip_lines['category'].fillna(0).astype(int)
        else:
            self.slip_lines['category'] = 0
        # Assign empty tags
        self.slip_lines['tag'] = None
        # A line may come with its trust, the others have no mark
        self.slip_lines['trust'] = self.slip_lines['trust'].fillna('') if 'trust' in self.slip_lines else ''
        # A line may come with the rows of the scan it was read from, the others have none
        sources = self.slip_lines['source'] if 'source' in self.slip_lines else [()] * len(self.slip_lines)
        self.slip_lines['source'] = [x if isinstance(x, tuple) else () for x in sources]
        self.slip_lines['printed'] = self.slip_lines['name']
        self.slip_lines['memory'] = ''
        self.slip_lines = self.slip_lines[PandasLinesModel.COLUMNS + PandasLinesModel.HIDDEN_COLUMNS]

        self.model = PandasLinesModel(self.slip_lines, self, self.receipt_api.total())
        self.ui.LinesTableView.setModel(self.model)
        self.ui.LinesTableView.selectionModel().currentRowChanged.connect(self._show_line_on_scan)
        self._show_scan()
        self._recall_lines()
        self.model.dataChanged.connect(self._show_totals)
        self.model.rowsInserted.connect(self._show_totals)
        self.model.rowsRemoved.connect(self._show_totals)
        self._show_verdict()

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

    # The banner, the total footer and the line buttons of the loaded receipt, or of none
    def _show_verdict(self):
        verdicts = {
            Verdict.RECONCILED: (self.tr("Reconciled automatically"), Meaning.POSITIVE),
            Verdict.NOT_RECONCILED: (self.tr("Not reconciled, check the lines"), Meaning.WARNING),
            Verdict.NO_CODE: (self.tr("No usable fiscal code, rescan recommended"), Meaning.NEGATIVE)
        }
        loaded = self.slip_lines is not None
        text, meaning = verdicts.get(self.receipt_api.verdict() if loaded else '', ('', None))
        self.ui.VerdictLbl.setText(text)
        self._color_label(self.ui.VerdictLbl, meaning)
        self.ui.AddLineBtn.setEnabled(loaded)
        self.ui.DeleteLineBtn.setEnabled(loaded)
        self.ui.AssignCategoryBtn.setEnabled(loaded)
        self.ui.AssignTagBtn.setEnabled(loaded)
        self._show_totals()

    def _color_label(self, label, meaning):
        palette = QPalette(self.palette())
        if meaning is not None:
            palette.setColor(QPalette.WindowText, Theme.text(meaning, palette.window().color()))
        label.setPalette(palette)

    # Amount the receipt's source says its lines add up to; None without a receipt or without such an amount
    def _expected_total(self):
        return self.receipt_api.total() if self.slip_lines is not None and self.receipt_api is not None else None

    def _lines_total(self) -> Decimal:
        return sum(self.slip_lines['amount'], Decimal('0'))

    # The sum of the lines against the total of the receipt, with a difference highlighted
    @Slot()
    def _show_totals(self):
        if self.slip_lines is None:
            self.ui.TotalsLbl.setText('')
            self.ui.DifferenceLbl.setText('')
            return
        total, expected = self._lines_total(), self._expected_total()
        text = self.tr("Lines") + f": {localize_decimal(total, 2)}"
        if expected is None:
            self.ui.TotalsLbl.setText(text)
            self.ui.DifferenceLbl.setText('')
            return
        self.ui.TotalsLbl.setText(text + "    " + self.tr("Receipt total") + f": {localize_decimal(expected, 2)}")
        self.ui.DifferenceLbl.setText(self.tr("Difference") + f": {localize_decimal(total - expected, 2)}")
        self._color_label(self.ui.DifferenceLbl, Meaning.NEGATIVE if total != expected else None)

    # Lines without a category get what the peer's earlier receipts made of the same items
    @Slot()
    def _recall_lines(self):
        if self.model is not None and self.slip_lines is not None and self.ui.PeerEdit.selected_id:
            self.model.recall(JalReceiptMemory(self.ui.PeerEdit.selected_id))

    # The page images of the loaded receipt beside its lines, with the body rows that are no line offered for adding
    def _show_scan(self):
        pages = self._scan.page_images() if self._scan is not None else []
        self.ui.ScanView.set_pages(pages)
        self.ui.ScanView.setVisible(self.ui.ScanView.has_pages())
        if self._scan is not None and self._scan_offers:
            boxes = self._scan.ocr_boxes
            self.ui.ScanView.offer_rows({i: boxes[i] for i in self._scan.unread_body_rows if boxes[i] is not None})

    # The rows the line was read from are marked on the scan
    @Slot(QModelIndex, QModelIndex)
    def _show_line_on_scan(self, current: QModelIndex, _previous: QModelIndex):
        if self._scan is None or self.model is None or not current.isValid():
            self.ui.ScanView.show_rows([])
            return
        boxes = self._scan.ocr_boxes
        rows = [boxes[i] for i in self.model.source(current.row()) if 0 <= i < len(boxes) and boxes[i] is not None]
        self.ui.ScanView.show_rows(rows)

    # A row of the scan that the phone read as no item becomes a line
    @Slot(int)
    def addScanRow(self, ocr_row: int):
        if self.model is None or self.slip_lines is None or self._scan is None:
            return
        texts = self._scan.ocr_texts
        if not 0 <= ocr_row < len(texts):
            return
        line = line_of_row(texts[ocr_row], self._scan_sign)
        row = self.model.add_line(line['name'], line['amount'], line['trust'], (ocr_row,))
        self.ui.ScanView.withdraw_row(ocr_row)
        self.ui.LinesTableView.setCurrentIndex(self.model.index(row, 0))

    @Slot()
    def addLine(self):
        if self.model is None or self.slip_lines is None:
            return
        index = self.model.index(self.model.add_line(), 0)
        self.ui.LinesTableView.setCurrentIndex(index)
        self.ui.LinesTableView.edit(index)

    @Slot()
    def deleteLine(self):
        index = self.ui.LinesTableView.currentIndex()
        if self.slip_lines is None or not index.isValid():
            return
        self.model.removeRows(index.row(), 1)

    # The category chosen in the categories dialog goes to the lines without a category
    @Slot()
    def assignCategory(self):
        if self.model is None or self.slip_lines is None:
            return
        if self._category_dialog is None:
            self._category_dialog = CategoryListDialog(self)
        if self._category_dialog.exec(enable_selection=True):
            self.model.fill_empty(PandasLinesModel.CATEGORY, self._category_dialog.selected_id)

    # The tag chosen in the tags dialog goes to the lines without a tag
    @Slot()
    def assignTag(self):
        if self.model is None or self.slip_lines is None:
            return
        if self._tags_dialog is None:
            self._tags_dialog = TagsListDialog(self)
        if self._tags_dialog.exec(enable_selection=True):
            self.model.fill_empty(PandasLinesModel.TAG, self._tags_dialog.selected_id)

    def addOperation(self):
        if self.slip_lines is None:
            return
        if self.slip_lines.empty:
            logging.warning(self.tr("Not possible to import receipt: it has no lines"))
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
        if (self.slip_lines['trust'] == LineTrust.MISSING).any():
            logging.warning(self.tr("Not possible to import receipt: some lines have no amount, set it or delete "
                                    "the line"))
            return

        number = self.receipt_api.number() if self.receipt_api is not None else ''
        if IncomeSpending.find_by_number(number):
            logging.warning(self.tr("Not possible to import receipt: it is imported already") + f" ({number})")
            self._finish_inbox_file()
            return

        expected = self._expected_total()
        if expected is not None and self._lines_total() != expected:
            difference = localize_decimal(self._lines_total() - expected, 2)
            if QMessageBox().question(self, self.tr("Lines don't add up"),
                                      self.tr("The lines differ from the receipt's total by") + f" {difference}. "
                                      + self.tr("Add the operation anyway?"),
                                      QMessageBox.Yes, QMessageBox.No) != QMessageBox.Yes:
                return

        details = []
        for index, row in self.slip_lines.iterrows():
            details.append({
                "category_id": row['category'],
                "tag_id": row['tag'] or None,     # a tag cleared in the editor is 0
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
        if self.ui.NoteEdit.text().strip():
            operation["note"] = self.ui.NoteEdit.text().strip()
        LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, operation)
        JalPeer(self.ui.PeerEdit.selected_id).add_or_update_mapped_name(self.ui.SlipShopName.text(), )
        memory = JalReceiptMemory(self.ui.PeerEdit.selected_id)
        for index, row in self.slip_lines.iterrows():
            if row['printed']:
                memory.remember(row['printed'], row['name'] if row['name'] != row['printed'] else '',
                                int(row['category']), row['tag'] or None)
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
        self._scan = None
        self.ui.ScanView.clear()
        self.ui.ScanView.hide()
        self.ui.NoteEdit.clear()
        self._save_lines_columns()
        self.ui.LinesTableView.setModel(None)
        self._show_verdict()
