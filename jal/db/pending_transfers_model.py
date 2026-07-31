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
from jal.db.operations import Bridge, Transfer
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
#   BRIDGE   a cross-chain send whose arrival is still awaited: the same money in flight, recorded as a pending
#            half-bridge rather than as a transfer leg because the fetcher recognized the contract it went into.
#            It is listed here for exactly that reason - which of the two a movement became is an accident of the
#            protocol registry, and a worklist that showed only one of them would answer "what money of mine is in
#            flight" with a number that leaves the other out. It settles differently, though (BridgeMatcher, from
#            the Operations list), so it is a kind of its own rather than a leg among the others.
#   BASIS    not pending at all: a settled cross-currency transfer whose destination lots opened at zero because
#            nothing ever stated their cost basis. Shown only on request (see updateView), because a zero may be
#            correct and only the user can tell - what matters is that it is possible to look.
#   POISONING an arrival from an address minted to be mistaken for one of the user's own - an address-poisoning
#            attack, waiting to be copied out of the history in place of the real address. It is not a leg awaiting
#            its other end at all: nobody sent it, so nothing will ever settle it.
#   AIRDROP  an arrival of an asset the wallet has never otherwise dealt in - which is what something pushed in
#            uninvited looks like, though a first genuine acquisition looks the same until the second one happens.
#            A paler shade than the one above, because that is a suspicion and the one above is not.
class PendingTransfersModel(ReportTreeModel):
    SENT = 'sent'
    ARRIVED = 'arrived'
    BRIDGE = 'bridge'
    BASIS = 'basis'
    POISONING = 'poisoning'
    AIRDROP = 'airdrop'
    _BACKGROUND = {SENT: CustomColor.PaleYellow, ARRIVED: CustomColor.PaleBlue, BRIDGE: CustomColor.PaleGreen,
                   BASIS: CustomColor.PaleViolet, POISONING: CustomColor.PaleRed, AIRDROP: CustomColor.PaleOrange}
    # The kinds an arriving leg may turn out to be instead of a plain arrival - what the report colours differently
    UNSOLICITED = {TransferSettlement.POISONING: POISONING, TransferSettlement.AIRDROP: AIRDROP}

    # The columns a filter looks through: the ones that hold a name, a reference or free text. A filter over the
    # numbers would be a different feature (and a misleading one - '100' would match a quantity of 1002.5).
    # 'action' is among them on purpose - "show me everything that only needs an account named" is the question a
    # worklist of this length is most often asked.
    _FILTERED = ('from', 'to', 'asset', 'action', 'suggestion', 'address', 'number', 'note')

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
        self._filter = ''
        # Every row the report could show, read from the database and kept: filtering and sorting only choose
        # which of them are shown and in what order, and rebuilding the list for that would re-read three tables
        # and re-run the per-leg hints (address_suggestion, dust_hint, duplicate_asset_hint) on every keystroke.
        # None means "not read yet, or read for parameters that no longer apply" - see updateView().
        self._records = None
        self._sort_field = 'timestamp'
        self._sort_order = Qt.AscendingOrder
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
                         {'name': self.tr("Action"), 'field': 'action'},
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
        for field in ('from', 'to', 'asset', 'action', 'suggestion', 'address', 'number', 'note'):
            self._view.setItemDelegateForColumn(self.fieldIndex(field), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('qty'), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('value'), self._float2_delegate)
        self._view.footer().set_span(self.fieldIndex('timestamp'),
                                     [self.fieldIndex('timestamp'), self.fieldIndex('qty')])
        super().configureView()

    # Reloads the list when what it is shown for has changed. 'update' asks for the reload anyway: settling a leg
    # changes the DATA under parameters that stayed exactly the same, and without it the settled row is still listed.
    #
    # Two kinds of change are told apart here. Date, currency and the basis-gap switch change WHICH rows exist and
    # what they are worth, so they discard the rows that were read; the filter only changes which of the rows
    # already in hand are shown, and re-reading the database for it would be work done for nothing.
    def updateView(self, currency_id, date, with_basis_gaps: bool = False, filter_text: str = '',
                   update: bool = False):
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
            self._records = None
        filter_text = filter_text.strip().lower()
        if self._filter != filter_text:
            self._filter = filter_text
            update = True
        if update:
            self.prepareData()

    # Re-orders the list by the column the user clicked. The rows are already in memory, so this only rebuilds the
    # tree out of them - see _records.
    def sort(self, column: int, order=Qt.AscendingOrder):
        if not 0 <= column < len(self._columns):
            return
        field = self._columns[column]['field']
        if (field, order) == (self._sort_field, self._sort_order):
            return
        self._sort_field, self._sort_order = field, order
        if self._records is None:
            return   # nothing has been read yet (the view sets its indicator before the first updateView) - the
                     # order is remembered and the first read applies it, rather than reading for parameters
                     # nobody has stated yet
        self.prepareData()

    # The rows to show, in the order to show them in.
    #
    # The three sources this list is made of are three different tables, each already ordered by itself - and
    # appending them one after another laid three date sequences on top of each other, which put every pending
    # half-bridge below every transfer leg whatever the dates were. The two ends of one movement are what this
    # report exists to bring together, and they could not even be near each other. So the rows are merged and
    # ordered as ONE list, by date until the user asks for something else.
    #
    # The timestamp is the tie-breaker under every other sort, and the oid under that: without them rows that
    # agree on the sorted column (the same asset, the same account, an empty note) would come out in whatever
    # order the tables happened to be read in, and would move around between two identical reloads.
    def _shown(self) -> list:
        rows = [record for record in self._records if self._matches(record)]
        rows.sort(key=lambda record: (record[self._sort_field], record['timestamp'], record['oid']),
                  reverse=(self._sort_order == Qt.DescendingOrder))
        return rows

    # Whether a row survives the filter. It is a plain case-insensitive substring, looked for in any of the columns
    # that hold text - the point is to narrow a long worklist down to one asset, one account or one protocol, and
    # anything cleverer would have to be explained to be used.
    def _matches(self, record: dict) -> bool:
        if not self._filter:
            return True
        return any(self._filter in str(record[field]).lower() for field in self._FILTERED)

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
        # A leg that has a whole counterpart which only disagrees about WHAT was moved is the one shape of unsettled
        # leg that no settlement can ever reach, because the two assets are the obstacle rather than the missing end
        duplicate = self._settlement.duplicate_asset_hint(leg['oid'])
        if duplicate:
            tooltip += self.tr("\nOne transaction moved this exact quantity as ") \
                       + Transfer.leg_symbol(leg) + self.tr(" and as ") + duplicate['other_asset'].symbol() \
                       + self.tr(", which is one movement recorded under two assets. If they are the same coin, "
                                 "merge them in the Assets dialog and the two legs settle by themselves.")
        # An arrival nobody sent is not waiting for anything, and saying so is the point: it would otherwise sit in
        # this worklist for ever, and the address it names is the very thing the attack wants copied out of it.
        kind = self.SENT if outgoing else self.ARRIVED
        unsolicited = None if outgoing else self._settlement.dust_hint(leg['oid'])
        if unsolicited:
            kind = self.UNSOLICITED[unsolicited['kind']]
            tooltip = self._unsolicited_tooltip(unsolicited, leg)
        return {
            'oid': leg['oid'],
            'kind': kind,
            'timestamp': leg['timestamp'],
            'from': leg['account'].name() if outgoing else unknown,
            'to': unknown if outgoing else leg['account'].name(),
            'asset': Transfer.leg_symbol(leg),
            'qty': leg['qty'],
            'value': value,
            'action': self._leg_action(kind, suggested, duplicate),
            'suggestion': JalAccount(suggested).name() if suggested else '',
            'address': leg['address'] if leg['address'] else '',
            'number': leg['number'],
            'note': leg['note'],
            'font': 'normal' if outgoing else 'italic',
            'tooltip': tooltip
        }

    # Which of the report's actions this leg is waiting for, named as the button that performs it.
    #
    # The worklist offers six buttons and the row itself never said which of them applied - the knowledge was in the
    # tooltips and in the user's head, and picking wrong means being refused by a dialog rather than being told. It
    # costs nothing to say: the three hints this answer is made of (dust_hint, address_suggestion,
    # duplicate_asset_hint) are already asked for above, to build the rest of the row.
    #
    # The order is the order of certainty, and it is the same one the row's kind follows. An arrival nobody sent
    # isn't waiting for a counterpart at all, so it comes first; then an address that resolves to an account of the
    # user's, which is a fact about where the money went rather than a guess; then two legs that a single
    # transaction recorded under two assets, which no settlement can pair until the assets are merged. What is left
    # needs a counterpart chosen by hand, and Match is where that is done - including through the conversions
    # (Swap, Bridge) that start from the same pair.
    def _leg_action(self, kind: str, suggested: int, duplicate) -> str:
        if kind in (self.POISONING, self.AIRDROP):
            return self.tr("Dust")
        if suggested:
            return self.tr("Assign...")
        if duplicate:
            return self.tr("Merge the assets")
        return self.tr("Match...")

    # What a row says about an arrival nobody asked for. The poisoning wording names the account being impersonated
    # and warns about the address rather than the money: the amount is trivial by design, and the loss the attack is
    # after happens later, when the address is copied out of the history into a real transfer.
    def _unsolicited_tooltip(self, unsolicited: dict, leg) -> str:
        if unsolicited['kind'] == TransferSettlement.POISONING:
            return self.tr("ADDRESS POISONING. It came from an address built to be mistaken for the one of ") \
                   + unsolicited['impersonated'].name() \
                   + self.tr(" - the two match at both ends, which is what you see when an address is abbreviated. "
                             "Never copy this address out of your history: money sent to it is gone. Nobody is "
                             "waiting to be paired with this, so write it off with Dust.")
        return self.tr("Nothing else in this wallet has ever dealt in ") + Transfer.leg_symbol(leg) \
               + self.tr(" - this arrival is the only operation in it, which is what an unsolicited airdrop looks "
                         "like. If it is one, write it off with Dust; if you really acquired it, settle it as usual.")

    # Turns one pending half-bridge of Bridge.pending_halves() into a display record. It is a send like any other in
    # this list - the asset left and reached nothing - so it counts towards the money in transit the same way.
    def _bridge_record(self, half) -> dict:
        return {
            'oid': half['oid'],
            'kind': self.BRIDGE,
            'timestamp': half['timestamp'],
            'from': half['account'].name(),
            'to': self.tr("(unknown)"),
            'asset': half['symbol'].symbol(),
            'qty': half['qty'],
            'value': half['qty'] * half['asset'].quote(self._date, self._currency)[1],
            # Not one of this report's buttons: a half-bridge is already recorded as a crossing, so what it waits
            # for is its arrival rather than a settlement - named here as the menu entry that completes it
            'action': self.tr("Match cross-chain legs..."),
            'suggestion': '',
            'address': '',
            'number': half['number'],
            'note': half['note'],
            'font': 'normal',
            'tooltip': self.tr("Sent across chains, and what arrived for it isn't known yet. This one is already "
                               "recorded as a bridge, so it is completed from the Operations list: right-click it "
                               "there and choose 'Match cross-chain legs...'.")
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
            'asset': leg['symbol'].symbol(),
            'qty': leg['qty'],
            'value': Decimal('0'),
            # This row is settled and no action of this report applies to it - it is listed to be looked at, and
            # saying so is better than an empty cell, which would read as "the answer isn't known"
            'action': self.tr("Check the cost basis"),
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
        if self._records is None:
            self._records = [self._leg_record(leg) for leg in Transfer.pending_legs(self._date)]
            self._records += [self._bridge_record(half) for half in Bridge.pending_halves(self._date)]
            if self._with_basis_gaps:
                self._records += [self._basis_record(leg) for leg in Transfer.legs_without_cost_basis(self._date)]
        self.beginResetModel()
        self._root = PendingLegTreeItem()
        # The total in the footer is accumulated as the rows are added, so it follows the filter - it says what is
        # in transit among the rows that are shown, which is the question a filtered list is asking.
        for record in self._shown():
            self._root.appendChild(PendingLegTreeItem(record))
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
