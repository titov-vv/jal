from decimal import Decimal
from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QDateTime, QAbstractTableModel
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMessageBox

from jal.constants import AssetLocation
from jal.db.asset import JalAsset
from jal.db.helpers import localize_decimal
from jal.db.operations import LedgerTransaction
from jal.db.staking import JalStakingBox
from jal.reports.reports import Reports
from jal.ui.reports.ui_staking_report import Ui_StakingReportWidget
from jal.widgets.delegates import FloatDelegate, TimestampDelegate
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "StakingReport"


# ----------------------------------------------------------------------------------------------------------------------
# What was staked and is still held somewhere else at the report date, one row per asset in a box.
#
# A row per (box, asset) rather than per box: a container normally holds the one coin it was made for, but nothing
# says it must, and folding two coins into one row would have to state a quantity that means nothing. What a box IS
# stays one thing - the details below, and closing it, act on the whole box whichever of its rows is selected.
class StakingListModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Name"), self.tr("Protocol"), self.tr("Blockchain"), self.tr("Asset"),
                         self.tr("Quantity"), self.tr("Value"), self.tr("Staked since"), self.tr("Address")]
        self._timestamp = 0
        self._currency_id = 0
        self._show_closed = False
        self._view = parent_view
        self._data = []
        self._float_delegate = None
        self._qty_delegate = None
        self._timestamp_delegate = None
        self._value_total = Decimal('0')

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def headerWidth(self, section):
        return self._view.horizontalHeader().sectionSize(section)

    def data(self, index, role=Qt.DisplayRole, field=''):
        if role == Qt.DisplayRole:
            return self.data_text(self._data[index.row()], index.column())
        if role == Qt.FontRole and not self._data[index.row()]['box'].is_active():
            font = QFont()
            font.setItalic(True)   # a closed position is shown as past, exactly as a deactivated account is
            return font
        return None

    def data_text(self, record: dict, column: int):
        box = record['box']
        if column == 0:
            return box.name()
        if column == 1:
            return box.protocol()
        if column == 2:
            return AssetLocation().get_name(box.chain()) if box.chain() else ''
        if column == 3:
            if record['asset'] is None:
                return ''
            # Asked for the box's own currency and chain: a coin held on several chains is one asset with a listing
            # per chain, and asking without them answers with every ticker it has run together
            return record['asset'].symbol(currency=box.currency().id(), location=box.chain())
        if column == 4:
            return record['amount']
        if column == 5:
            return record['value']
        if column == 6:
            return box.opened_at()
        if column == 7:
            return box.address()
        return ''

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 0:
                return self.tr("Total")
            if section == 5:
                return localize_decimal(self._value_total, precision=2)
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter if section in (4, 5) else Qt.AlignLeft | Qt.AlignVCenter
        return None

    # The box shown in a given row, or None if the row doesn't point at one
    def box(self, index) -> JalStakingBox:
        if not index.isValid() or index.row() >= len(self._data):
            return None
        return self._data[index.row()]['box']

    def updateView(self, timestamp=None, currency_id=None, show_closed=None):
        if timestamp is not None:
            self._timestamp = timestamp
        if currency_id is not None:
            self._currency_id = currency_id
        if show_closed is not None:
            self._show_closed = show_closed
        self.prepareData()
        self.configureView()

    def prepareData(self):
        self.beginResetModel()
        self._data = []
        boxes = JalStakingBox.all_boxes() if self._show_closed else JalStakingBox.get_boxes(self._timestamp)
        for box in boxes:
            holdings = box.holdings(self._timestamp)
            if not holdings:
                # Only reachable with closed positions shown - a box that holds nothing is what a finished stake
                # leaves behind, and it is listed so that what WAS staked can still be found
                self._data.append({'box': box, 'asset': None, 'amount': Decimal('0'), 'value': Decimal('0')})
                continue
            for holding in holdings:
                rate = holding['asset'].quote(self._timestamp, self._currency_id)[1]
                self._data.append({'box': box, 'asset': holding['asset'], 'amount': holding['amount'],
                                   'value': holding['amount'] * rate})
        self._value_total = sum([x['value'] for x in self._data], Decimal('0'))
        self.endResetModel()

    def configureView(self):
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        # A staked quantity keeps its tail: coins are held to 18 decimals and rounding one to two would show a
        # position of 0.00 for anything small enough
        self._qty_delegate = FloatDelegate(2, allow_tail=True)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._timestamp_delegate = TimestampDelegate(display_format='%d/%m/%Y')
        self._view.setItemDelegateForColumn(4, self._qty_delegate)
        self._view.setItemDelegateForColumn(5, self._float_delegate)
        self._view.setItemDelegateForColumn(6, self._timestamp_delegate)
        self._view.setColumnWidth(0, 200)
        self._view.setColumnWidth(1, 160)
        self._view.setColumnWidth(2, 100)
        self._view.setColumnWidth(3, 80)
        self._view.setColumnWidth(4, 140)
        self._view.setColumnWidth(5, 120)
        self._view.setColumnWidth(6, self._view.fontMetrics().horizontalAdvance("00/00/0000") * 1.1)
        self._view.setColumnWidth(7, 300)


# ----------------------------------------------------------------------------------------------------------------------
# Everything that went into and out of one staked position, with the quantity it left behind after each step
class StakingDetailsModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Date/Time"), self.tr("Operation"), self.tr("Asset"), self.tr("Quantity"),
                         self.tr("Balance")]
        self._view = parent_view
        self._data = []
        self._timestamp = 0
        self._currency_id = None      # of the box being shown - a ticker is asked for per currency and chain
        self._chain = None
        self._qty_delegate = None
        self._timestamp_delegate = None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        record = self._data[index.row()]
        if index.column() == 0:
            return record['timestamp']
        if index.column() == 1:
            return record['operation']
        if index.column() == 2:
            return record['asset'].symbol(currency=self._currency_id, location=self._chain)
        if index.column() == 3:
            return record['amount']
        if index.column() == 4:
            return record['balance']
        return ''

    def setBox(self, box: JalStakingBox, timestamp: int):
        self.beginResetModel()
        self._timestamp = timestamp
        self._data = []
        self._currency_id = box.currency().id() if box is not None else None
        self._chain = box.chain() if box is not None else None
        if box is not None:
            for record in box.details(timestamp):
                record['operation'] = self._operation_name(record['otype'], record['oid'])
                self._data.append(record)
        self.endResetModel()
        self.configureView()

    # Name of the operation a ledger row came from. An operation that was deleted since the ledger was built has
    # nothing to name it, and a details table must not raise over that.
    @staticmethod
    def _operation_name(otype: int, oid: int) -> str:
        try:
            return LedgerTransaction().get_operation(otype, oid).name()
        except (IndexError, ValueError):
            return ''

    def configureView(self):
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._qty_delegate = FloatDelegate(2, allow_tail=True)
        self._timestamp_delegate = TimestampDelegate()
        self._view.setItemDelegateForColumn(0, self._timestamp_delegate)
        self._view.setItemDelegateForColumn(3, self._qty_delegate)
        self._view.setItemDelegateForColumn(4, self._qty_delegate)
        self._view.setColumnWidth(0, self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.25)
        self._view.setColumnWidth(1, 200)
        self._view.setColumnWidth(2, 80)
        self._view.setColumnWidth(3, 140)
        self._view.setColumnWidth(4, 140)


# ----------------------------------------------------------------------------------------------------------------------
class StakingReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Staked positions")
        self.window_class = "StakingReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
# What the wallet has staked and where. A staked position is a box - an account of a hidden type holding the asset
# on behalf of the wallet it left - and it is filled by settling the transfer legs a stake and an unstake are: see
# jal/db/staking.py and the unsettled transfers report, which is where a position is created.
#
# There is deliberately no "what it earned" column. Staking yield is booked on the WALLET the coins return to, as a
# StakingReward payment, and nothing records which position produced it - a wallet may stake into several at once.
# A zero there would be a claim, not a gap, so the report states what it knows: what is held, since when, by whom.
class StakingReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_StakingReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("Staked positions")

        self.boxes_model = StakingListModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.boxes_model)
        self.details_model = StakingDetailsModel(self.ui.DetailsTableView)
        self.ui.DetailsTableView.setModel(self.details_model)

        current_time = QDateTime.currentDateTime()
        current_time.setTimeSpec(Qt.UTC)   # We use UTC everywhere so need to force TZ info
        self.ui.ReportDate.setDateTime(current_time)
        self.ui.ReportCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportDate.dateChanged.connect(self.updateReport)
        self.ui.ReportCurrencyCombo.changed.connect(self.updateReport)
        self.ui.ClosedCheck.stateChanged.connect(self.updateReport)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onBoxSelected)
        self.ui.CloseButton.pressed.connect(self.closePosition)
        self.ui.SaveButton.pressed.connect(
            partial(self._parent.save_report, self.name, self.ui.ReportTableView.model()))

    # The list is a read of what the ledger booked on the boxes, so a settlement made anywhere else leaves it stale.
    # The main window calls this on every open report after a ledger rebuild (MdiWidget.refresh).
    def refresh(self):
        self.updateReport()

    def _timestamp(self) -> int:
        return self.ui.ReportDate.date().endOfDay(Qt.UTC).toSecsSinceEpoch()

    # The position the actions apply to, or None when nothing is selected
    def _selected(self) -> JalStakingBox:
        indexes = self.ui.ReportTableView.selectionModel().selectedRows()
        return self.boxes_model.box(indexes[0]) if indexes else None

    @Slot()
    def updateReport(self):
        self.boxes_model.updateView(timestamp=self._timestamp(),
                                    currency_id=self.ui.ReportCurrencyCombo.selected_id,
                                    show_closed=self.ui.ClosedCheck.isChecked())
        self.details_model.setBox(self._selected(), self._timestamp())

    @Slot()
    def onBoxSelected(self, _selected=None, _deselected=None):
        self.details_model.setBox(self._selected(), self._timestamp())

    # Closes an emptied position, which is what takes it out of every default view. It refuses a box that still
    # holds something: the coins would stay in it and simply stop being listed, which is how a staked position gets
    # lost. Unstaking is not done here - it happens on the chain and reaches JAL as the transfer that settles back.
    @Slot()
    def closePosition(self):
        box = self._selected()
        if box is None:
            return
        holdings = box.holdings(self._timestamp())
        if holdings:
            held = ', '.join(f"{localize_decimal(x['amount'])} {x['asset'].symbol()}" for x in holdings)
            QMessageBox().warning(self, self.name,
                                  self.tr("This position still holds ") + held
                                  + self.tr(". It can only be closed once what is in it has been unstaked and the "
                                            "transfer back has been settled."))
            return
        if QMessageBox().question(self, self.name,
                                  self.tr("Close this position?\n\nEverything it recorded stays in place - it "
                                          "simply stops being listed as staked.")) != QMessageBox.Yes:
            return
        box.close()
        self.updateReport()
