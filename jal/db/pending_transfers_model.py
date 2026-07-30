from __future__ import annotations
from decimal import Decimal
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QBrush
from PySide6.QtWidgets import QHeaderView
from jal.constants import CustomColor
from jal.db.tree_model import AbstractTreeItem, ReportTreeModel
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.helpers import localize_decimal, now_ts, day_end
from jal.db.operations import Transfer
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.delegates import GridLinesDelegate, FloatDelegate, TimestampDelegate


# ----------------------------------------------------------------------------------------------------------------------
# One unsettled transfer leg - a transfer that knows only one of its two ends ("money on the way").
#
# The list is flat: it is a worklist of things to settle, and every row is one leg, so there is nothing to group by
# that the columns don't already say.
class PendingLegTreeItem(AbstractTreeItem):
    def __init__(self, leg=None, parent=None, group=''):
        super().__init__(parent, group)
        if leg is None:
            self._data = {'timestamp': 0, 'from': '', 'to': '', 'asset': '', 'qty': Decimal('0'),
                          'value': Decimal('0'), 'suggestion': '', 'address': '', 'number': '', 'note': ''}
        else:
            self._data = leg.copy()

    # Only the invisible root accumulates here, and only the money in transit is worth totalling
    def _calculateGroupTotals(self, child_data):
        self._data['value'] += child_data['value']

    def _afterParentGroupUpdate(self, group_data):
        pass

    def details(self):
        return self._data

    def setGroupValue(self, value):
        if self._group:
            self._data[self._group] = value

    def getGroup(self):
        return (self._group, self._data[self._group]) if self._group else None


# ----------------------------------------------------------------------------------------------------------------------
# Lists every transfer leg that is still waiting for its counterpart. This is the safety net of the one-legged
# transfer model: without it an unsettled leg is a record nobody ever looks at again, and legs accumulate silently
# (which is the one new failure mode that model introduces).
#
# The list comes straight from 'transfers' (Transfer.pending_legs) and so needs no ledger rebuild to be current.
# Values are computed AT READ TIME from the quotes of the report date - nothing derived is stored.
#
# 'value' is the money that is IN TRANSIT, which is deliberately not the same as what the leg is worth:
#   * an outgoing leg has left its account and reached none, so its value belongs to no account, is invisible in
#     every per-account balance, and is counted here;
#   * an incoming leg has already arrived - it is counted in the account it landed on, and counting it again here
#     would double it, so it contributes zero. What it lacks is not a location but a cost basis, which stays zero
#     until the sending leg is found.
# The total is therefore the money genuinely in flight, while the list itself stays complete.
#
# The rows are of kinds that are settled in different ways, and each kind carries its own pale background so the
# list can be read as the few groups it is rather than as one undifferentiated worklist:
#   SENT     the money left and where it went is unknown - what the total above is made of
#   ARRIVED  it landed and where it came from is unknown - already counted, but at a cost basis of zero
#   BASIS    not pending at all: a settled cross-currency transfer whose destination lots opened at zero because
#            nothing ever stated their cost basis. Shown only on request (see updateView), because a zero may be
#            correct and only the user can tell - what matters is that it is possible to look.
class PendingTransfersModel(ReportTreeModel):
    SENT = 'sent'
    ARRIVED = 'arrived'
    BASIS = 'basis'
    _BACKGROUND = {SENT: CustomColor.PaleYellow, ARRIVED: CustomColor.PaleBlue, BASIS: CustomColor.PaleViolet}

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._grid_delegate = None
        self._float_delegate = None
        self._float2_delegate = None
        self._timestamp_delegate = None
        self._currency = 0
        self._currency_name = ''
        self._date = day_end(now_ts())
        self._with_basis_gaps = False
        self._settlement = TransferSettlement()
        bold_font = QFont()
        bold_font.setBold(True)
        italic_font = QFont()
        italic_font.setItalic(True)
        self._fonts = {'normal': None, 'bold': bold_font, 'italic': italic_font}
        self._columns = [{'name': self.tr("Date"), 'field': 'timestamp'},
                         {'name': self.tr("From"), 'field': 'from'},
                         {'name': self.tr("To"), 'field': 'to'},
                         {'name': self.tr("Asset"), 'field': 'asset'},
                         {'name': self.tr("Qty"), 'field': 'qty'},
                         {'name': self.tr("In transit, "), 'field': 'value'},
                         {'name': self.tr("Suggested"), 'field': 'suggestion'},
                         {'name': self.tr("Counterparty"), 'field': 'address'},
                         {'name': self.tr("Reference"), 'field': 'number'},
                         {'name': self.tr("Note"), 'field': 'note'}]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        value = super().headerData(section, orientation, role)
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == self.fieldIndex('value'):
            value += self._currency_name
        return value

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        details = index.internalPointer().details()
        if role == Qt.DisplayRole:
            return details[self._columns[index.column()]['field']]
        if role == Qt.FontRole:
            # An account the address resolved to is the one thing in the row that is an answer rather than a
            # question, so it says so wherever the rest of the row is set in the type of what is still unknown
            if index.column() == self.fieldIndex('suggestion') and details['suggestion']:
                return self._fonts['bold']
            return self._fonts.get(details.get('font', 'normal'), None)
        if role == Qt.BackgroundRole:
            return QBrush(self._BACKGROUND[details['kind']]) if details.get('kind') else None
        if role == Qt.ToolTipRole:
            return details.get('tooltip', None)
        return None

    def footerData(self, section, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == self.fieldIndex('timestamp'):
                return self.tr("Total in transit:")
            if section == self.fieldIndex('value'):
                return localize_decimal(self._root.details()['value'], precision=2)
        elif role == Qt.FontRole:
            return self._fonts['bold']
        elif role == Qt.TextAlignmentRole:
            if section == self.fieldIndex('value'):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def configureView(self):
        for field in [x['field'] for x in self._columns]:
            if field == 'note':
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.Stretch)
            else:
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.ResizeToContents)
        self._grid_delegate = GridLinesDelegate(self._view)
        self._timestamp_delegate = TimestampDelegate(display_format='%d/%m/%Y', parent=self._view)
        self._float_delegate = FloatDelegate(0, allow_tail=True, parent=self._view)
        # empty_zero: an arriving leg adds nothing to the money in transit, and a 0.00 there would read as "this leg
        # is worthless" rather than "this leg isn't in flight"
        self._float2_delegate = FloatDelegate(2, allow_tail=False, empty_zero=True, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex('timestamp'), self._timestamp_delegate)
        for field in ('from', 'to', 'asset', 'suggestion', 'address', 'number', 'note'):
            self._view.setItemDelegateForColumn(self.fieldIndex(field), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('qty'), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('value'), self._float2_delegate)
        self._view.footer().set_span(self.fieldIndex('timestamp'),
                                     [self.fieldIndex('timestamp'), self.fieldIndex('qty')])
        super().configureView()

    def updateView(self, currency_id, date, with_basis_gaps: bool = False):
        update = False
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = JalAsset(currency_id).symbol()
            update = True
        if self._date != date.endOfDay(Qt.UTC).toSecsSinceEpoch():
            self._date = date.endOfDay(Qt.UTC).toSecsSinceEpoch()
            update = True
        if self._with_basis_gaps != with_basis_gaps:
            self._with_basis_gaps = with_basis_gaps
            update = True
        if update:
            self.prepareData()

    # Turns one leg of Transfer.pending_legs() into a display record. The end that is missing is named rather than
    # left blank, so the row says what is unknown about it instead of looking like a transfer with a hole in it.
    def _leg_record(self, leg) -> dict:
        outgoing = leg['opart'] == Transfer.Outgoing
        unknown = self.tr("(unknown)")
        if outgoing:
            value = leg['qty'] * leg['asset'].quote(self._date, self._currency)[1]
            tooltip = self.tr("Sent, but the account it arrived at isn't known yet")
        else:
            value = Decimal('0')
            tooltip = self.tr("Arrived, but the account it was sent from isn't known yet. It is already counted in ") \
                      + leg['account'].name() + self.tr(", at a cost basis of zero until the transfer is settled.")
        # An address only resolves for the legs a chain fetched, and resolving it walks every account, so it is
        # asked about the legs that state one at all
        suggested = self._settlement.address_suggestion(leg['oid']) if leg['address'] else 0
        if suggested:
            tooltip += self.tr("\nThe address it names belongs to ") + JalAccount(suggested).name() \
                       + self.tr(" - assign that account to settle the transfer.")
        return {
            'oid': leg['oid'],
            'kind': self.SENT if outgoing else self.ARRIVED,
            'timestamp': leg['timestamp'],
            'from': leg['account'].name() if outgoing else unknown,
            'to': unknown if outgoing else leg['account'].name(),
            'asset': leg['asset'].symbol(currency=leg['account'].currency()),
            'qty': leg['qty'],
            'value': value,
            'suggestion': JalAccount(suggested).name() if suggested else '',
            'address': leg['address'] if leg['address'] else '',
            'number': leg['number'],
            'note': leg['note'],
            'font': 'normal' if outgoing else 'italic',
            'tooltip': tooltip
        }

    # Turns one transfer of Transfer.legs_without_cost_basis() into a display record. Both of its ends are known, so
    # nothing about it is in transit and it adds nothing to the total - what it is missing is what the asset cost.
    def _basis_record(self, leg) -> dict:
        return {
            'oid': leg['oid'],
            'kind': self.BASIS,
            'timestamp': leg['timestamp'],
            'from': leg['from_account'].name(),
            'to': leg['to_account'].name(),
            'asset': leg['asset'].symbol(currency=leg['to_account'].currency()),
            'qty': leg['qty'],
            'value': Decimal('0'),
            'suggestion': '',
            'address': '',
            'number': leg['number'],
            'note': leg['note'],
            'font': 'normal',
            'tooltip': self.tr("Settled, but the asset opened at a cost basis of zero in ")
                       + leg['to_account'].name()
                       + self.tr(": the two accounts are kept in different currencies and nothing stated what the "
                                 "asset had cost. A zero may be right - if it isn't, it is taxed as a gain when the "
                                 "asset is sold.")
        }

    def prepareData(self):
        self.beginResetModel()
        self._root = PendingLegTreeItem()
        for leg in Transfer.pending_legs(self._date):
            self._root.appendChild(PendingLegTreeItem(self._leg_record(leg)))
        if self._with_basis_gaps:
            for leg in Transfer.legs_without_cost_basis(self._date):
                self._root.appendChild(PendingLegTreeItem(self._basis_record(leg)))
        self.endResetModel()
        super().prepareData()

    # oid of the transfer the given row belongs to (0 for an invalid index) - the operation a settlement acts on
    def transfer_oid(self, index) -> int:
        if not index.isValid():
            return 0
        return index.internalPointer().details().get('oid', 0)

    # Which of the kinds above the given row is ('' for an invalid index) - what may be done to it depends on it
    def transfer_kind(self, index) -> str:
        if not index.isValid():
            return ''
        return index.internalPointer().details().get('kind', '')
