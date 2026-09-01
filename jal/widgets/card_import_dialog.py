import base64

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Slot
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableView, QDialogButtonBox, QHeaderView

from jal.constants import Setup
from jal.db.common_models import PeerTreeModel, CategoryTreeModel
from jal.db.helpers import localize_decimal
from jal.db.settings import JalSettings
from jal.widgets.delegates import LookupSelectorDelegate
from jal.widgets.helpers import center_window, restore_columns, save_columns, set_grids_metrics, ts2dt
from jal.widgets.reference_dialogs import PeerListDialog, CategoryListDialog


# ----------------------------------------------------------------------------------------------------------------------
# One row per card purchase the statement reports, with what the matcher proposed for it and what the user decides.
# 'peer' and 'category' start empty: a merchant string as the acquirer sent it is not a peer of this ledger, and
# a merchant code the acquirer sent is not a spending category, so neither can be filled in without the user.
# A statement that has no merchant code at all (Revolut) leaves that column empty.
class CardOperationsModel(QAbstractTableModel):
    DATE, MERCHANT, MCC, AMOUNT, STORED, IMPORT, PEER, CATEGORY, DESCRIPTION = range(9)

    def __init__(self, rows: list, proposal: list, parent=None):
        super().__init__(parent)
        # 'Date' rather than 'Time (UTC)': every moment in JAL is shown on the local clock, and a purchase can
        # only be compared with the one the user typed in if both are read on the same one.
        self._headers = [self.tr("Date"), self.tr("Merchant"), self.tr("Merchant category"), self.tr("Amount"),
                         self.tr("In database"), self.tr("Import"), self.tr("Peer"), self.tr("Category"),
                         self.tr("Description")]
        self._rows = []
        for row, match in zip(rows, proposal):
            self._rows.append({
                'row': row, 'match': match,
                # A purchase that is in the database already is proposed as 'don't import'; everything else as 'do'.
                'import': match is None, 'peer': 0, 'category': 0, 'description': row['merchant']
            })

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

    def flags(self, index):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == self.IMPORT:
            return flags | Qt.ItemIsUserCheckable
        if index.column() in (self.PEER, self.CATEGORY, self.DESCRIPTION):
            # A row that isn't imported needs nothing filled in, so its editors stay shut
            return (flags | Qt.ItemIsEditable) if self._rows[index.row()]['import'] else flags
        return flags

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        record = self._rows[index.row()]
        column = index.column()
        if role == Qt.CheckStateRole and column == self.IMPORT:
            return Qt.Checked if record['import'] else Qt.Unchecked
        if role in (Qt.DisplayRole, Qt.EditRole):
            if column == self.DATE:
                return ts2dt(record['row']['timestamp'])
            if column == self.MERCHANT:
                return record['row']['merchant']
            if column == self.MCC:
                return record['row']['merchant_category']
            if column == self.AMOUNT:
                return localize_decimal(record['row']['amount'], precision=2)
            if column == self.STORED:
                return self._stored_text(record['match'])
            if column == self.PEER:
                return record['peer']
            if column == self.CATEGORY:
                return record['category']
            if column == self.DESCRIPTION:
                return record['description']
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        record = self._rows[index.row()]
        if role == Qt.CheckStateRole and index.column() == self.IMPORT:
            record['import'] = Qt.CheckState(value) == Qt.Checked
            # The row's editors open or close with the checkbox, so the whole row is repainted
            self.dataChanged.emit(index.sibling(index.row(), 0),
                                  index.sibling(index.row(), self.columnCount() - 1))
            return True
        if role == Qt.EditRole:
            if index.column() == self.PEER:
                record['peer'] = value if value else 0
            elif index.column() == self.CATEGORY:
                record['category'] = value if value else 0
            elif index.column() == self.DESCRIPTION:
                record['description'] = str(value)
            else:
                return False
            self.dataChanged.emit(index, index)
            return True
        return False

    def _stored_text(self, match) -> str:
        if match is None:
            return ''
        return f"{ts2dt(match['timestamp'])} {match['peer'] or ''} {localize_decimal(match['amount'], precision=2)}"

    # True when every row that is going to be imported knows its peer and its category
    def is_complete(self) -> bool:
        return all(x['peer'] and x['category'] for x in self._rows if x['import'])

    def decisions(self) -> list:
        return [{'import': x['import'], 'peer': x['peer'], 'category': x['category'],
                 'description': x['description']} for x in self._rows]


# ----------------------------------------------------------------------------------------------------------------------
# Confirms what a statement adds to the card purchases the ledger already holds. Used by Trading 212 and Revolut,
# which name themselves through 'title'.
#
# Most of those purchases are typed by hand on the day they happen, so the statement mostly repeats what is there -
# but nothing identifies a purchase on both sides (see CardMatcher), so the pairing is a resemblance and stays the
# user's to confirm. Accepting a wrong pairing loses a purchase; rejecting a right one stores it twice.
class CardImportDialog(QDialog):
    GEOMETRY_KEY = "DlgGeometry_CardImport"
    # Peer, category and description hold nothing until the user fills them in, so their content gives them no
    # width at all - and they are the columns the typing happens in, with a full selector (a field with a
    # completer and two buttons) opening inside the cell. They are sized by the text they are meant to hold.
    TYPED_COLUMN_CHARS = 22

    def __init__(self, rows: list, proposal: list, parent=None, title: str = ''):
        super().__init__(parent)
        self.setWindowTitle(title if title else self.tr("Card purchases"))
        self.resize(1100, 500)
        self._model = CardOperationsModel(rows, proposal, self)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Purchases that are in the database already are unticked. Tick a purchase "
                                        "to import it and give it a peer and a category:"), self))
        self._view = QTableView(self)
        self._view.setObjectName("CardOperationsView")   # the name its stored column layout is keyed by
        self._view.setModel(self._model)
        self._view.setAlternatingRowColors(True)
        self._view.verticalHeader().setVisible(False)
        self._view.setItemDelegateForColumn(
            CardOperationsModel.PEER, LookupSelectorDelegate(self._view, PeerTreeModel, PeerListDialog, self))
        self._view.setItemDelegateForColumn(
            CardOperationsModel.CATEGORY, LookupSelectorDelegate(self._view, CategoryTreeModel, CategoryListDialog, self))
        layout.addWidget(self._view)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self._buttons.accepted.connect(self.onDialogAccept)
        self._buttons.rejected.connect(self.onDialogReject)
        layout.addWidget(self._buttons)

        set_grids_metrics(self)
        self._configure_columns()
        self._restore_geometry()
        self._model.dataChanged.connect(self.updateButtons)
        self.updateButtons()

    # Default widths that suit the data, then whatever the user dragged them to in an earlier session.
    def _configure_columns(self):
        header = self._view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self._view.resizeColumnsToContents()
        typed_width = self._view.fontMetrics().horizontalAdvance('0') * self.TYPED_COLUMN_CHARS
        for column in (CardOperationsModel.PEER, CardOperationsModel.CATEGORY, CardOperationsModel.DESCRIPTION):
            header.resizeSection(column, max(header.sectionSize(column), typed_width))
        restore_columns(self._view, Setup.COLUMNS_STATE_PREFIX)

    # The size the user left the dialog at, or - the first time - one that shows the whole table without a
    # horizontal scroll bar, capped at the screen it opens on so that a wide table can't push it off the desktop.
    def _restore_geometry(self):
        stored = JalSettings().getStr(self.GEOMETRY_KEY)
        if stored:
            self.restoreGeometry(base64.decodebytes(stored.encode('utf-8')))
            return
        self.layout().activate()   # the viewport has no width of its own until the layout has been applied
        around_the_table = self.width() - self._view.viewport().width()
        available = self.screen().availableGeometry()
        self.resize(min(self._view.horizontalHeader().length() + around_the_table,
                        int(available.width() * 0.9)), self.height())
        center_window(self)

    @Slot()
    def updateButtons(self):
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(self._model.is_complete())

    # Both exits go through close() rather than accept()/reject(): closeEvent() is what stores the window geometry
    # and the column layout, and QDialog.accept() would hide the dialog without ever sending a close event.
    @Slot()
    def onDialogAccept(self):
        self.setResult(QDialog.Accepted)
        self.close()

    @Slot()
    def onDialogReject(self):
        self.setResult(QDialog.Rejected)
        self.close()

    @Slot()
    def closeEvent(self, event):
        JalSettings().setValue(self.GEOMETRY_KEY, base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        save_columns(self, Setup.COLUMNS_STATE_PREFIX)
        event.accept()   # deliberately not QDialog.closeEvent(), which would reject the dialog on the way out

    def decisions(self) -> list:
        return self._model.decisions()
