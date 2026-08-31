from decimal import Decimal
from functools import partial

from PySide6.QtCore import Qt, Slot, QObject, QAbstractTableModel
from PySide6.QtGui import QFont
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMessageBox, QMenu

from jal.constants import AssetLocation, IconOwner, Setup
from jal.db.clock import day_finish, now_dt
from jal.db.asset import JalAsset
from jal.db.icon import JalIcons
from jal.db.account import JalAccount
from jal.db.chain_balance import JalChainBalance
from jal.db.common_models import account_row_icon
from jal.db.helpers import localize_decimal
from jal.db.operations import LedgerTransaction
from jal.db.receivable import JalReceivable
from jal.db.staking import JalStakingBox
from jal.net.chain_fetchers.protocols import protocol_name
from jal.reports.reports import Reports
from jal.ui.reports.ui_staking_report import Ui_StakingReportWidget
from jal.widgets.delegates import FloatDelegate, TimestampDelegate
from jal.widgets.icons import JalIcon, chain_icon
from jal.widgets.account_dialog import AccountDialog
from jal.widgets.accrual_chart import AccrualChartWindow, ReceivableChartWindow
from jal.widgets.mdi import MdiWidget
from jal.widgets.helpers import set_grids_metrics, restore_columns

JAL_REPORT_CLASS = "StakingReport"


# ----------------------------------------------------------------------------------------------------------------------
# What was staked and is still held somewhere else at the report date, one row per asset in a box - and, beside it,
# what a distributor owes a wallet and hasn't paid yet.
#
# A row per (box, asset) rather than per box: a container normally holds the one coin it was made for, but nothing
# says it must, and folding two coins into one row would have to state a quantity that means nothing. What a box IS
# stays one thing - the details below, and closing it, act on the whole box whichever of its rows is selected.
#
# A CLAIMABLE REWARD is listed here too, one row per (wallet, asset, distributor), because it is the same kind of
# thing the 'Accrued' column already exists for: value that has been earned and not yet received.
class StakingListModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Name"), self.tr("Protocol"), self.tr("Blockchain"), self.tr("Asset"),
                         self.tr("Quantity"), self.tr("Accrued"), self.tr("Value"), self.tr("Staked since"),
                         self.tr("Address")]
        self._timestamp = 0
        self._currency_id = 0
        self._show_closed = False
        self._view = parent_view
        self._data = []
        self._float_delegate = None
        self._qty_delegate = None
        self._timestamp_delegate = None
        self._accrued_delegate = None
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
        if role == Qt.FontRole and not self._data[index.row()]['active']:
            font = QFont()
            font.setItalic(True)   # a closed position is shown as past, exactly as a deactivated account is
            return font
        if role == Qt.DecorationRole and index.column() == 0:
            return account_row_icon(JalAccount(self._data[index.row()]['account_id']))
        if role == Qt.DecorationRole and index.column() == 2:
            icon = chain_icon(self._data[index.row()]['chain'])  # The chain is named and marked in the same cell, the way a wallet account is everywhere else.
            return icon if not icon.isNull() else None
        if role == Qt.DecorationRole and index.column() == 3:
            return self._asset_icon(self._data[index.row()])
        return None

    # The logo of the listing the Asset column names - the same listing data_text() takes the ticker from, asked
    # for by the row's own currency and chain
    def _asset_icon(self, record: dict):
        if record['asset'] is None:
            return JalIcons.spacer(JalIcons.grid_size())
        listing = record['asset'].listing_id(currency=record['currency_id'], location=record['chain'])
        return JalIcons.decoration(IconOwner.Symbol, listing, JalIcons.grid_size())

    def data_text(self, record: dict, column: int):
        if column == 0:
            return record['name']
        if column == 1:
            return record['protocol']
        if column == 2:
            return AssetLocation().get_name(record['chain']) if record['chain'] else ''
        if column == 3:
            if record['asset'] is None:
                return ''
            # Asked for the row's own currency and chain: a coin held on several chains is one asset with a listing
            # per chain, and asking without them answers with every ticker it has run together
            return record['asset'].symbol(currency=record['currency_id'], location=record['chain'])
        if column == 4:
            return record['amount']
        if column == 5:
            # Unlike the Asset Portfolio, this report DOES get a column of its own for the accrual, and the reason is
            # what the report is for. jal/db/staking.py and this module both state, deliberately, that JAL cannot say
            # what a given box earned: yield reaches the wallet and nothing records which container produced it, so
            # any per-box figure would be a guess. A live chain balance minus the booked principal IS that figure,
            # measured instead of guessed - so here it is the subject of the report rather than a rarity that would
            # leave the column empty on every other row. A claimable reward is the same column's other half: it too
            # is earned and unpaid, and the only difference is that it waits at a distributor instead of in a box.
            return record['accrued']
        if column == 6:
            return record['value']
        if column == 7:
            return record['since']
        if column == 8:
            return record['address']
        return ''

    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 0:
                return self.tr("Total")
            if section == 6:
                return localize_decimal(self._value_total, precision=2)
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter if section in (4, 5, 6) else Qt.AlignLeft | Qt.AlignVCenter
        return None

    # The box shown in a given row, or None if the row doesn't point at one
    def box(self, index) -> JalStakingBox:
        record = self.record(index)
        return record['box'] if record else None

    # The account a row belongs to: the box itself for a staked position, the wallet that is owed for a claim.
    def account(self, index) -> int:
        record = self.record(index)
        if record is None:
            return 0
        return record['box'].id() if record['box'] is not None else record['account_id']

    # The whole row behind an index, for a caller that needs the asset too and not only the box it sits in
    def record(self, index) -> dict:
        if not index.isValid() or index.row() >= len(self._data):
            return None
        return self._data[index.row()]

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
                self._data.append(self._box_row(box, None, Decimal('0'), Decimal('0'), Decimal('0')))
                continue
            for holding in holdings:
                rate = holding['asset'].quote(self._timestamp, self._currency_id)[1]
                # 'amount' stays the booked principal and the accrual is shown beside it rather than folded into it,
                # so the two can be told apart - which is the whole point here. The VALUE is of both together,
                # because that is what the position is worth and what the total at the bottom has to add up to.
                accrued = JalChainBalance().accrual(box.id(), holding['asset'].id(), holding['amount'],
                                                    self._timestamp)['delta']
                self._data.append(self._box_row(box, holding['asset'], holding['amount'], accrued,
                                                (holding['amount'] + accrued) * rate))
        self._data += self._claim_rows()
        self._value_total = sum([x['value'] for x in self._data], Decimal('0'))
        self.endResetModel()

    # One row of a staked position. Everything the columns need is taken off the box HERE rather than when the row is
    # drawn, so that a claimable-reward row - which has no box - can fill the same fields from somewhere else.
    @staticmethod
    def _box_row(box: JalStakingBox, asset, amount: Decimal, accrued: Decimal, value: Decimal) -> dict:
        return {'box': box, 'name': box.name(), 'protocol': box.protocol(), 'chain': box.chain(),
                'currency_id': box.currency().id(), 'address': box.address(), 'since': box.opened_at(),
                'active': box.is_active(), 'asset': asset, 'amount': amount, 'accrued': accrued, 'value': value,
                'source': '', 'account_id': box.id()}

    # What the distributors owe, one row per (wallet, asset, distributor).
    #
    # There is no principal to show and no date to show it from: a reward was never deposited anywhere, so 'Quantity'
    # is zero (the column blanks it) and 'Staked since' is empty. The Address column names the DISTRIBUTOR, which is
    # what a row of this kind is identified by and what tells two of them paying the same token apart.
    #
    # 'Show closed' doesn't filter these: a claim isn't open or closed, it is owed or it isn't, and one that has been
    # paid simply stops being listed.
    def _claim_rows(self) -> list:
        rows = []
        receivables = JalReceivable()
        for account_id in receivables.accounts_with_claims(self._timestamp):
            account = JalAccount(account_id)
            for claim in receivables.claims(account_id, self._timestamp):
                asset = JalAsset(claim['asset_id'])
                rate = asset.quote(self._timestamp, self._currency_id)[1]
                # The protocol is named where it is known and the bare contract shown where it isn't - a row must
                # always say who owes the money, and an unregistered distributor is still an address one can look up.
                name = protocol_name(account.chain(), claim['source']) or claim['source']
                rows.append({'box': None, 'name': account.name(), 'protocol': name, 'chain': account.chain(),
                             'currency_id': account.currency(), 'address': claim['source'], 'since': 0,
                             'active': True, 'asset': asset, 'amount': Decimal('0'), 'accrued': claim['amount'],
                             'value': claim['amount'] * rate, 'source': claim['source'], 'account_id': account_id})
        return rows

    def configureView(self):
        # A staked quantity keeps its tail: coins are held to 18 decimals and rounding one to two would show a
        # position of 0.00 for anything small enough. 'empty_zero' is what leaves the column blank on a
        # claimable-reward row instead: a reward has no staked principal at all, and a literal 0.00 there would read
        # as a position that has been emptied.
        self._qty_delegate = FloatDelegate(2, allow_tail=True, empty_zero=True)
        self._accrued_delegate = FloatDelegate(2, allow_tail=True)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._timestamp_delegate = TimestampDelegate(date_only=True)
        self._view.setItemDelegateForColumn(4, self._qty_delegate)
        # The accrual keeps its tail for the same reason the quantity does, and more so: it is a small fraction of
        # the position (0.07 HYPE on 11.9, 0.15 SOL on 5.9), so two decimals would round most of it out of sight.
        self._view.setItemDelegateForColumn(5, self._accrued_delegate)
        self._view.setItemDelegateForColumn(6, self._float_delegate)
        self._view.setItemDelegateForColumn(7, self._timestamp_delegate)
        self._view.setColumnWidth(0, 200)
        self._view.setColumnWidth(1, 160)
        self._view.setColumnWidth(2, 100)
        self._view.setColumnWidth(3, 80)
        self._view.setColumnWidth(4, 140)
        self._view.setColumnWidth(5, 140)
        self._view.setColumnWidth(6, 120)
        self._view.setColumnWidth(7, self._view.fontMetrics().horizontalAdvance("00/00/0000") * 1.1)
        self._view.setColumnWidth(8, 300)
        restore_columns(self._view, Setup.COLUMNS_STATE_PREFIX)


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
        if role == Qt.DecorationRole and index.column() == 2:
            listing = self._data[index.row()]['asset'].listing_id(currency=self._currency_id, location=self._chain)
            return JalIcons.decoration(IconOwner.Symbol, listing, JalIcons.grid_size())
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
        restore_columns(self._view, Setup.COLUMNS_STATE_PREFIX)


# ----------------------------------------------------------------------------------------------------------------------
class StakingReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("&Staked positions")
        self.window_class = "StakingReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
# What the wallet has staked and where. A staked position is a box - an account of a hidden type holding the asset
# on behalf of the wallet it left - and it is filled by settling the transfer legs a stake and an unstake are: see
# jal/db/staking.py and the unsettled transfers report, which is where a position is created.
#
# 'Accrued' is what the position has earned and NOT yet been paid - the difference between what the chain says the
# container holds and what the books say was put into it. It is filled in only for the venues whose balance JAL can
# actually read (see jal/net/chain_balances.py); elsewhere it is zero, which here means "not measured" rather than
# "earned nothing".
#
# It is deliberately NOT the same thing as what a position has PAID OUT. Realized staking yield is booked on the
# WALLET the coins return to, as a StakingReward payment, and nothing records which container produced it - a wallet
# may stake into several at once, so a per-box figure for it would still be a guess. What this column shows is the
# unrealized part, which is measurable exactly because it is still sitting in the container.
class StakingReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_StakingReportWidget()
        self.ui.setupUi(self)
        set_grids_metrics(self)
        self._parent = parent
        self.name = self.tr("Staked positions")

        self.boxes_model = StakingListModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.boxes_model)
        self.details_model = StakingDetailsModel(self.ui.DetailsTableView)
        self.ui.DetailsTableView.setModel(self.details_model)

        self.ui.ReportDate.setDate(now_dt().date())
        self.ui.ReportCurrencyCombo.setIndex(JalAsset.get_base_currency())

        self.connect_signals_and_slots()
        self.updateReport()

    def connect_signals_and_slots(self):
        self.ui.ReportDate.dateChanged.connect(self.updateReport)
        self.ui.ReportCurrencyCombo.changed.connect(self.updateReport)
        self.ui.ClosedCheck.stateChanged.connect(self.updateReport)
        self.ui.ReportTableView.selectionModel().selectionChanged.connect(self.onBoxSelected)
        self.ui.ReportTableView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.ReportTableView.customContextMenuRequested.connect(self.onPositionContextMenu)
        self.ui.CloseButton.pressed.connect(self.closePosition)
        self.ui.SaveButton.pressed.connect(
            partial(self._parent.save_report, self.name, self.ui.ReportTableView.model()))

    # The list is a read of what the ledger booked on the boxes, so a settlement made anywhere else leaves it stale.
    # The main window calls this on every open report after a ledger rebuild (MdiWidget.refresh).
    def refresh(self):
        self.updateReport()

    def _timestamp(self) -> int:
        return day_finish(self.ui.ReportDate.date())

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

    # The 'Accrued' column says what a position has earned right now; this draws how it got there. Both series are
    # left behind by the ordinary quotes update - the box's by 'chain_balances', the claim's by 'receivables' - so
    # either chart costs no extra request and exists whether or not anyone opens it.
    @Slot()
    def onPositionContextMenu(self, pos):
        index = self.ui.ReportTableView.indexAt(pos)
        if not index.isValid():
            return
        record = self.boxes_model.record(index)
        if record is None:
            return
        menu = QMenu(self.ui.ReportTableView)
        # A chart is of one asset, so it is offered where the row names one - an emptied box, which is listed with
        # 'Show closed' and holds nothing, still has a name to correct.
        if record['box'] is None:
            if record['asset'] is None:
                return
            action = QAction(icon=JalIcon[JalIcon.CHART], text=self.tr("Show claim history"),
                             parent=self.ui.ReportTableView)
            action.triggered.connect(partial(self.showClaimHistory, self.boxes_model.account(index),
                                             record['asset'].id(), record['source']))
            menu.addAction(action)
        else:
            if record['asset'] is not None:
                action = QAction(icon=JalIcon[JalIcon.CHART], text=self.tr("Show accrual chart"),
                                 parent=self.ui.ReportTableView)
                action.triggered.connect(partial(self.showAccrualChart, record['box'].id(), record['asset'].id()))
                menu.addAction(action)
            action = QAction(icon=JalIcon[JalIcon.DETAILS], text=self.tr("Rename position..."),
                             parent=self.ui.ReportTableView)
            action.triggered.connect(partial(self.renamePosition, record['box'].id()))
            menu.addAction(action)
        menu.popup(self.ui.ReportTableView.viewport().mapToGlobal(pos))

    # The name and the icon of a staked position, and nothing else about the account behind it (see
    # AccountDialog.edit_name_only). A box is created from a pending transfer leg and named after the protocol the
    # import recognized, so the name it ends up with is a guess that the user is the only one able to correct - and
    # this list, where a box is named, is the only place that guess is ever seen.
    @Slot()
    def renamePosition(self, box_id):
        dialog = AccountDialog(self)
        dialog.setSelectedId(box_id)
        dialog.edit_name_only(self.tr("Staked position"))
        if dialog.exec() == QDialog.Accepted:
            self.updateReport()

    @Slot()
    def showAccrualChart(self, account_id, asset_id):
        self._parent.mdi_area().addWindow(AccrualChartWindow(account_id, asset_id), floating=True)

    @Slot()
    def showClaimHistory(self, account_id, asset_id, source):
        self._parent.mdi_area().addWindow(ReceivableChartWindow(account_id, asset_id, source), floating=True)

    @Slot()
    def onBoxSelected(self, _selected=None, _deselected=None):
        self.details_model.setBox(self._selected(), self._timestamp())

    # Closes an emptied position, which is what takes it out of every default view. It refuses a box that still
    # holds something: the coins would stay in it and simply stop being listed, which is how a staked position gets
    # lost. Unstaking is not done here - it happens on the chain and reaches JAL as the transfer that settles back.
    @Slot()
    def closePosition(self):
        # None means nothing is selected, or a claimable reward is - and a claim is not a position that can be
        # closed. It ends when it is paid, and the next update writes it down as zero.
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
