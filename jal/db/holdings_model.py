from __future__ import annotations
import logging
from decimal import Decimal

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QHeaderView
from jal.constants import IconOwner, AccountStatus, PredefinedAccountType
from jal.db.clock import day_finish, local_reading, today_finish
from jal.db.helpers import now_ts
from jal.db.tree_model import AbstractTreeItem, ReportTreeModel
from jal.db.account import JalAccount
from jal.db.common_models import account_row_icon, account_tag_icon
from jal.db.asset import JalAsset
from jal.db.chain_balance import JalChainBalance
from jal.db.icon import JalIcons
from jal.db.operations import LedgerTransaction, Transfer, CorporateAction
from jal.db.receivable import JalReceivable
from jal.db.staking import JalStakingBox
from jal.net.chain_fetchers.protocols import protocol_name
from jal.widgets.delegates import GridLinesDelegate, FloatDelegate, TimestampDelegate, TaggedIconDelegate, TAG_ICON_ROLE
from jal.widgets.helpers import ts2d
from jal.widgets.theme import Theme, Meaning


# ----------------------------------------------------------------------------------------------------------------------
OLD_QUOTE_AGE = 7   # when mark line as italic for old quote
# ----------------------------------------------------------------------------------------------------------------------
class AssetTreeItem(AbstractTreeItem):
    def __init__(self, data=None, parent=None, group=''):
        super().__init__(parent, group)
        if data is None:
            self._data = {
                'header': '', 'currency_id': 0, 'currency': '', 'account_id': 0, 'account': '', 'asset_id': 0,
                'symbol_id': 0,
                'tag': '', 'account_tag_id': 0, 'account_tag': '',
                'status_id': AccountStatus.Active, 'status': '',
                'asset_is_currency': False, 'asset': '', 'asset_name': '', 'country_id': 0, 'country': '',
                'since': 0, 'qty': None, 'value_i': Decimal('0'), 'paid': Decimal('0'),
                'open_quote': None, 'quote': None, 'quote_ts': Decimal('0'), 'quote_a': Decimal('0'),
                'value': Decimal('0'), 'value_common': Decimal('0'), 'p/l': Decimal('0'), 'p/l%': Decimal('0'),
                'font': 'bold', 'quote_age': 0, 'chain_ts': 0, 'share': Decimal('0')
            }
            if self._group == 'asset_id':   # Asset grouping will calculate average price and total qty
                self._data['qty'] = self._data['open_quote'] = self._data['quote'] = Decimal('0')
        else:
            self._data = data.copy()
            self._data['value'] = self._data['quote'] * self._data['qty']
            self._data['value_common'] = self._data['quote_a'] * self._data['qty'] if self._data['quote_a'] else Decimal('0')
            self._data['p/l'] = self._data['quote'] * self._data['qty'] - self._data['value_i'] if not self._data['asset_is_currency'] else Decimal('0')
            self._data['p/l%'] = Decimal('100') * (self._data['quote'] * self._data['qty'] / self._data['value_i'] - 1) if self._data['value_i'] != Decimal('0') else Decimal('0')

    def _calculateGroupTotals(self, child_data):
        self._data['header'] = child_data.get(self._group.strip("_id"), '<none>')
        self._data['currency'] = child_data['currency']
        self._data['account'] = child_data['account']
        self._data['asset'] = child_data['asset']
        self._data['country'] = child_data['country']
        self._data['tag'] = child_data['tag']
        self._data['account_tag'] = child_data['account_tag']
        self._data['paid'] += child_data['paid']
        self._data['value'] += child_data['value']
        self._data['value_common'] += child_data['value_common']
        self._data['p/l'] += child_data['p/l']
        self._data['p/l%'] = Decimal('100') * self._data['p/l'] / (self._data['value'] - self._data['p/l']) if self._data['value'] != self._data['p/l'] else Decimal('0')
        if self._group == 'asset_id':    # Average price and total quantity calculation for asset groups
            if not child_data['asset_is_currency']:
                if not self._data['since'] or child_data['since'] < self._data['since']:
                    self._data['since'] = child_data['since']
                self._data['open_quote'] = (self._data['open_quote'] * self._data['qty'] + child_data['open_quote'] * child_data['qty']) / (self._data['qty'] + child_data['qty'])
                self._data['quote'] = child_data['quote']
            else:
                self._data['quote'] = self._data['open_quote'] = None
            self._data['qty'] += child_data['qty']
            self._data['asset_name'] = child_data['asset_name']
            self._data['symbol_id'] = child_data['symbol_id']

    def _afterParentGroupUpdate(self, group_data):
        self._data['share'] = Decimal('100') * self._data['value_common'] / group_data['value_common'] if group_data['value_common'] else Decimal('0')

    def details(self):
        return self._data

    # assigns group value if this tree item is a group item
    def setGroupValue(self, value):
        if self._group:
            self._data[self._group] = value

    def getGroup(self):
        if self._group:
            return self._group, self._data[self._group]
        else:
            return None

    # The group of background accounts opens folded: its subtotal is the whole of what a reader normally wants from
    # it, and the positions under it are the ones that were crowding this report out.
    def isFolded(self) -> bool:
        group = self.getGroup()
        return group is not None and group[0] == 'status_id' and group[1] == AccountStatus.Background

    # returns an element of tree that will provide right group parent for 'item' with given 'group_fields'
    def getGroupLeaf(self, group_fields: list, item: AssetTreeItem) -> AssetTreeItem:
        if group_fields:
            group_item = None
            group_name = group_fields[0]
            for child in self._children:
                if child.details()[group_name] == item.details()[group_name]:
                    group_item = child
            if group_item is None:
                group_item = AssetTreeItem(None, parent=self, group=group_name)
                group_item.setGroupValue(item.details()[group_name])
                self._children.append(group_item)
            return group_item.getGroupLeaf(group_fields[1:], item)
        else:
            return self

# ----------------------------------------------------------------------------------------------------------------------
class HoldingsModel(ReportTreeModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._grid_delegate = None
        self._header_delegate = None
        self._float_delegate = None
        self._float2_delegate = None
        self._float4_delegate = None
        self._profit_delegate = None
        self._date_delegate = None
        bold_font = QFont()
        bold_font.setBold(True)
        strikeout_font = QFont()
        strikeout_font.setStrikeOut(True)
        italic_font = QFont()
        italic_font.setItalic(True)
        self._fonts = {'normal': None, 'bold': bold_font, 'italic': italic_font, 'strikeout': strikeout_font}
        self._currency = 0
        self._min_status = AccountStatus.Background
        self._currency_name = ''
        self._date = today_finish()
        self._columns = [{'name': self.tr("Currency/Account/Asset"), 'field': 'header'},
                         {'name': self.tr("Asset Name"), 'field': 'asset_name'},
                         {'name': self.tr("Qty"), 'field': 'qty'},
                         {'name': self.tr("Since"), 'field': 'since'},
                         {'name': self.tr("Open"), 'field': 'open_quote'},
                         {'name': self.tr("Last"), 'field': 'quote'},
                         {'name': self.tr("Share, %"), 'field': 'share'},
                         {'name': self.tr("P/L, %"), 'field': 'p/l%'},
                         {'name': self.tr("P/L"), 'field': 'p/l'},
                         {'name': self.tr("Paid"), 'field': 'paid'},
                         {'name': self.tr("Value"), 'field': 'value'},
                         {'name': self.tr("Value, "), 'field': 'value_common'}]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        value = super().headerData(section, orientation, role)
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == self.fieldIndex('value_common'):
            value += self._currency_name
        return value

    def data(self, index, role=Qt.DisplayRole):
        assert index.column() in range(len(self._columns))
        try:
            if not index.isValid():
                return None
            item = index.internalPointer()
            if role == Qt.DisplayRole:
                return item.details().get(self._columns[index.column()]['field'], None)
            if role == Qt.FontRole:
                return self._fonts.get(item.details()['font'], None)
            if role == Qt.ToolTipRole:
                return self.data_tooltip(item.details())
            if role == Qt.DecorationRole and index.column() == self.fieldIndex('header'):
                return self.row_icon(item)
            if role == TAG_ICON_ROLE and index.column() == self.fieldIndex('header'):
                return self.row_tag_icon(item)
            return None
        except Exception as e:
            print(e)

    # What the first column of a row is a picture of. A leaf row is a holding of an asset and wears the logo of the
    # listing its ticker came from; a group row is whatever it groups by - an account, an asset or a currency - and
    # a group that stands for none of those (an asset's tag, a country) keeps the blank that holds the text in line.
    def row_icon(self, item):
        details = item.details()
        group = item.getGroup()
        if group is None or group[0] == 'asset_id':
            return JalIcons.decoration(IconOwner.Symbol, details.get('symbol_id', 0), JalIcons.grid_size())
        if group[0] == 'account_id':
            return account_row_icon(JalAccount(details.get('account_id', 0)))
        if group[0] == 'account_tag_id':
            return JalIcons.decoration(IconOwner.Tag, details.get('account_tag_id', 0), JalIcons.grid_size())
        if group[0] == 'currency_id':
            return JalIcons.decoration(IconOwner.Symbol, JalAsset(details.get('currency_id', 0)).listing_id(),
                                       JalIcons.grid_size())
        return JalIcons.spacer(JalIcons.grid_size())

    # The mark of the tag group an account was put in, drawn before the picture above. Only a row that stands for
    # one account carries it: a holding row under it would repeat the mark of its account on every line. And when
    # the report is already grouped BY that tag nothing carries it - the group row above says it once.
    def row_tag_icon(self, item):
        group = item.getGroup()
        if group is None or group[0] != 'account_id' or 'account_tag_id' in self._groups:
            return None
        return account_tag_icon(JalAccount(item.details().get('account_id', 0)))

    # Both lines say the same kind of thing - HOW OLD the numbers behind this row are - and a row may need either or
    # both. The quote line appears only for a stale quote, while the on-chain one appears whenever a quantity was
    # measured rather than booked: a balance read from a chain is a "now" value with no history behind it, so when it
    # was taken is part of reading the row rather than a warning about it.
    def data_tooltip(self, data):
        lines = []
        if data['quote_age'] > OLD_QUOTE_AGE:
            lines.append(self.tr("Last quote date: ") + ts2d(int(data['quote_ts'])))
        if data.get('chain_ts'):
            lines.append(self.tr("On-chain balance as of: ") + ts2d(int(data['chain_ts'])))
        return '\n'.join(lines) if lines else None

    def configureView(self):
        for field in [x['field'] for x in self._columns]:
            if field == 'asset_name':
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.Stretch)
            else:
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.ResizeToContents)
        self._grid_delegate = GridLinesDelegate(self._view)
        self._header_delegate = TaggedIconDelegate(self._view)
        self._date_delegate = TimestampDelegate(date_only=True, parent=self._view)
        self._float_delegate = FloatDelegate(0, allow_tail=True, parent=self._view)
        self._float2_delegate = FloatDelegate(2, allow_tail=False, parent=self._view)
        self._float4_delegate = FloatDelegate(4, allow_tail=False, parent=self._view)
        self._profit_delegate = FloatDelegate(2, allow_tail=False, colors=True, parent=self._view)
        delegates = {'header': self._header_delegate, 'asset_name': self._grid_delegate, 'qty': self._float_delegate,
                     'since': self._date_delegate, 'open_quote': self._float4_delegate, 'quote': self._float4_delegate,
                     'share': self._float2_delegate, 'p/l%': self._profit_delegate, 'p/l': self._profit_delegate,
                     'paid': self._float2_delegate, 'value': self._float2_delegate,
                     'value_common': self._float2_delegate}
        for field, delegate in delegates.items():
            if self.fieldIndex(field) >= 0:   # the account view leaves some of the columns out
                self._view.setItemDelegateForColumn(self.fieldIndex(field), delegate)
        super().configureView()

    # 'min_status' is the lowest AccountStatus the report reaches down to - a wider view is a lower bound
    def updateView(self, currency_id, date, grouping, min_status):
        update = False
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = JalAsset(currency_id).symbol()
            update = True
        if self._date != day_finish(date):
            self._date = day_finish(date)
            update = True
        if self._min_status != min_status:
            self._min_status = min_status
            update = True
        if self.setGrouping(grouping) or update:
            self.prepareData()

    # True when the context menu may offer the actions on a position for this row
    def is_position(self, index) -> bool:
        return True

    # Who owes what this row shows, '' unless it is a claim
    def claim_source(self, index) -> str:
        return ''

    def get_data_for_tax(self, index):
        if not index.isValid():
            return None
        data = index.internalPointer().details()
        return data['account_id'], data['asset_id'], data['currency_id'], data['qty']

    # Returns tuple of two values for open position in 'asset' for 'account' on given date 'end_ts':
    # 1st (int) - the earliest timestamp of open position
    # 2nd (Decimal) - the amount of payments that were accumulated for given asset
    def get_asset_history_payments(self, account: JalAccount, asset: JalAsset, end_ts: int) -> (int, Decimal):
        trades = account.open_trades_list(asset, end_ts)
        if len(trades) == 0:
            logging.warning(self.tr("Open position was expected but not found for (account-asset-date): ") + f"'{account.name()}' - {asset.symbol()} - {ts2d(end_ts)}")
            return end_ts, Decimal('0')
        since = min([x.acquired() for x in trades])
        amount = account.asset_payments_amount(asset, since, end_ts)
        for trade in trades:
            operation = trade.open_operation()
            if operation.type() == LedgerTransaction.Transfer:
                transfer_out = LedgerTransaction().get_operation(operation.type(), operation.id(), Transfer.Outgoing)
                if transfer_out.is_pending():
                    continue    # An arrival with no known source has no earlier position to take the history from
                since_new, amount_new = self.get_asset_history_payments(transfer_out.account(), asset, transfer_out.timestamp()-1)  # get position just before the transfer
            elif operation.type() == LedgerTransaction.CorporateAction and operation.subtype() == CorporateAction.Split:
                since_new, amount_new = self.get_asset_history_payments(operation.account(), asset, operation.timestamp()-1)  # get position just before the split
            else:
                continue
            since = min(since, since_new)
            amount += amount_new
        return since, amount

    # Text of the first column of a position row: whatever the grouping doesn't say already
    def _row_header(self, record: dict) -> str:
        all_fields = ['currency', 'account', 'asset']
        display_fields = [y for y in all_fields if y not in [x.strip("_id") for x in self._groups]]
        return ': '.join([record[x] for x in display_fields])

    # The positions and the money 'account' holds at the report date, one record per row
    def _account_records(self, account: JalAccount) -> list:
        account_status_names = AccountStatus()
        account_holdings = []
        assets = account.assets_list(self._date)
        rate = JalAsset(account.currency()).quote(self._date, self._currency)[1]
        for asset_data in assets:
            asset = asset_data['asset']
            quote_ts, quote = asset.quote(self._date, account.currency())
            quote_age = int((local_reading(now_ts()) - quote_ts) / 86400)
            since, payments_amount = self.get_asset_history_payments(account, asset, self._date)
            # What the chain holds beyond what the books do - see JalChainBalance.accrual(). Only 'qty' moves:
            # 'value_i' is what the position COST and no part of that cost belongs to the accrued quantity, so
            # computing the average purchase price from anything but the ledger quantity would dilute it by the
            # accrual (2.2% on the aToken this was measured against) and quietly restate the basis of a position
            # nobody traded. With 'qty' raised and 'value_i' untouched, AssetTreeItem's own
            # 'p/l = quote * qty - value_i' shows the accrual as unrealized profit by construction - which is
            # exactly what it is, and why this needs no column of its own.
            accrual = JalChainBalance().accrual(account.id(), asset.id(), asset_data['amount'], self._date)
            font = 'italic' if quote_age > OLD_QUOTE_AGE else 'normal'
            font = 'strikeout' if asset.days2expiration() < 0 else font
            expiry_header = self.tr("Exp:")
            expiry_text = f" [{expiry_header} {ts2d(asset.expiry())}]" if asset.expiry() else ''
            record = {
                "currency_id": account.currency(),                      # Fields 'x' and 'x_id' are used together for grouping
                "currency": JalAsset(account.currency()).symbol(),
                "account_id": account.id(),
                "account": account.name(),
                "asset_id": asset.id(),
                "asset": asset.symbol(currency=account.currency(), location=account.chain()),
                # The very listing that ticker came from, so the logo drawn beside it belongs to it
                "symbol_id": asset.listing_id(currency=account.currency(), location=account.chain()),
                "asset_name": asset.name() + expiry_text,
                "asset_is_currency": False,
                "country_id": asset.country().id(),
                "country": asset.country().name(),
                "tag": asset.tag().name() if asset.tag().name() else self.tr("N/A"),  # the ASSET tag
                "account_tag_id": account.tag().id(),           # the ACCOUNT's tag, unlike an asset 'tag' above
                "account_tag": account.tag().name() if account.tag().name() else self.tr("N/A"),
                "status_id": account.status(),
                "status": account_status_names.get_name(account.status()),
                "since": since,
                "qty": asset_data['amount'] + accrual['delta'],
                "value_i": asset_data['value'],
                "paid": payments_amount,
                "open_quote": asset_data['value'] / asset_data['amount'],
                "quote": quote,
                "quote_ts": quote_ts,
                "quote_a": rate * quote,
                "quote_age": quote_age,
                "chain_ts": accrual['measured'] if accrual['delta'] else 0,
                "share": Decimal('0'),
                "font": font
            }
            record['header'] = self._row_header(record)
            account_holdings.append(record)
        money = account.get_asset_amount(self._date, account.currency())
        if money:
            record = {
                "currency_id": account.currency(),
                "currency": JalAsset(account.currency()).symbol(),
                "account_id": account.id(),
                "account": account.name(),
                "asset_id": account.currency(),
                "asset": JalAsset(account.currency()).symbol(),
                "symbol_id": JalAsset(account.currency()).listing_id(),
                "asset_name": JalAsset(account.currency()).name(),
                "asset_is_currency": True,
                "country_id": JalAsset(account.currency()).country().id(),
                "country": JalAsset(account.currency()).country().name(),
                "tag": self.tr("Money"),
                "account_tag_id": account.tag().id(),           # the ACCOUNT's tag, unlike 'tag' above
                "account_tag": account.tag().name() if account.tag().name() else self.tr("N/A"),
                "status_id": account.status(),
                "status": account_status_names.get_name(account.status()),
                "since": 0,
                "qty": money,
                "value_i": Decimal('0'),
                "paid": Decimal('0'),
                "open_quote": None,
                "quote": Decimal('1'),
                "quote_ts": today_finish(),
                "quote_a": rate,
                "quote_age": 0,
                "share": Decimal('0'),
                "font": 'normal'
            }
            record['header'] = self._row_header(record)
            account_holdings.append(record)
        return account_holdings

    # The report tree for the current parameters of the model: _currency, _date, _min_status, _groups
    def _build_tree(self) -> AssetTreeItem:
        holdings = []
        # Hidden accounts are asked for explicitly, because a STAKING BOX is one: an asset staked into a container
        # has left the wallet and sits in the box, and leaving it out here would understate the portfolio by exactly
        # what is staked. Deposit boxes - the other hidden type - hold money and are not investing, so they stay out
        # through 'investing_only' as they always did.
        accounts = JalAccount.get_all_accounts(investing_only=True, min_status=self._min_status,
                                               include_hidden=True)
        for account in accounts:
            holdings += self._account_records(account)
        # Sort data with respect to groups before building the tree
        sort_names = [x.removesuffix("_id") for x in self._groups]
        if 'asset' in sort_names:
            sort_names.insert(sort_names.index('asset'), 'asset_is_currency')  # Need to put currency at the end
        else:
            sort_names += ['asset_is_currency', 'asset']   # Sort by asset name for any kind of grouping
        holdings = sorted(holdings, key=lambda x: tuple([x[key_name] for key_name in sort_names]))
        # Add data records to the report tree
        root = AssetTreeItem()
        for position in holdings:
            new_item = AssetTreeItem(position)
            leaf = root.getGroupLeaf(self._groups, new_item)
            leaf.appendChild(new_item)
        return root

    # Populate the report tree
    def prepareData(self):
        self.beginResetModel()
        self._root = self._build_tree()
        self.endResetModel()
        super().prepareData()


# ----------------------------------------------------------------------------------------------------------------------
# Root of the account view. Its rows don't add up to one figure - a staked position is outside the account's balance -
# so the model states the totals itself and the root keeps none.
class AccountHoldingsRoot(AssetTreeItem):
    def _calculateGroupTotals(self, child_data):
        pass


# ----------------------------------------------------------------------------------------------------------------------
# What one account holds at a date: its positions and money, what distributors owe it and what it has staked.
# The first total equals JalAccount.balance(). A staking box is an account of its own, so what is staked comes after it.
class AccountHoldingsModel(HoldingsModel):
    HELD, MONEY, CLAIM, STAKED = 'held', 'money', 'claim', 'staked'

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._account_id = 0
        self._has_positions = False
        self._columns = [x for x in self._columns if x['field'] not in ('share', 'paid')]
        self._columns[0] = {'name': self.tr("Asset"), 'field': 'header'}

    def showAccount(self, account_id: int, currency_id: int, date) -> None:
        self._account_id = account_id
        self._currency = currency_id
        self._currency_name = JalAsset(currency_id).symbol()
        self._date = day_finish(date)
        self.prepareData()

    # False when there is nothing beyond money, so the list would only repeat the balance
    def hasPositions(self) -> bool:
        return self._has_positions

    # Names of the wallets the shown account holds a stake for - empty unless it is a staking box
    def stakedFrom(self) -> list:
        if not self._account_id or JalAccount(self._account_id).account_type() != PredefinedAccountType.Staking:
            return []
        return [x.name() for x in JalStakingBox(self._account_id).source_accounts()]

    def is_position(self, index) -> bool:
        return index.internalPointer().details().get('kind') in (self.HELD, self.STAKED)

    def claim_source(self, index) -> str:
        return index.internalPointer().details().get('source', '')

    # A P/L exists for a position only, and a group or a total row shows nothing but its own figures
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.BackgroundRole and index.isValid() and index.internalPointer().details().get('kind') == self.STAKED:
            return QBrush(Theme.tint(Meaning.INFO))
        if role == Qt.DisplayRole and index.isValid():
            details = index.internalPointer().details()
            field = self._columns[index.column()]['field']
            if field in ('p/l', 'p/l%') and details.get('kind') != self.HELD:
                return None
            if field != 'header' and index.internalPointer().getGroup() is not None:
                return None
            if field == 'asset_name' and details.get('mark') and details.get('kind') != self.STAKED:
                return f"{details['asset_name']} · {details['mark']}"   # a staked row names its protocol already
        return super().data(index, role)

    def _row_header(self, record: dict) -> str:
        return record['asset']

    # A heading runs across the row, so its length doesn't set the width of the first column
    def prepareData(self):
        super().prepareData()
        for row in range(self._root.childrenCount()):
            if self._root.getChild(row).getGroup() is not None:
                self._view.setFirstColumnSpanned(row, QModelIndex(), True)

    # A row valued by a quote alone. 'asset_is_currency' is what leaves it without a P/L, as money is: what a claim or
    # a stake cost isn't part of what this list says about them.
    def _valued_record(self, kind: str, account: JalAccount, asset: JalAsset, name: str, qty: Decimal, since: int,
                       mark: str, chain_ts: int = 0) -> dict:
        wallet = JalAccount(self._account_id)
        quote_ts, quote = asset.quote(self._date, wallet.currency())
        rate = JalAsset(wallet.currency()).quote(self._date, self._currency)[1]
        symbol = asset.symbol(currency=account.currency(), location=account.chain())
        return {'kind': kind, 'mark': mark, 'currency_id': account.currency(), 'currency': JalAsset(account.currency()).symbol(),
                'account_id': account.id(), 'account': account.name(), 'asset_id': asset.id(), 'asset': symbol,
                'symbol_id': asset.listing_id(currency=account.currency(), location=account.chain()),
                'asset_name': name, 'asset_is_currency': True, 'country_id': asset.country().id(),
                'country': asset.country().name(), 'tag': asset.tag().name() if asset.tag().name() else self.tr("N/A"),
                'account_tag_id': account.tag().id(),
                'account_tag': account.tag().name() if account.tag().name() else self.tr("N/A"),
                'status_id': account.status(), 'status': '', 'since': since, 'qty': qty, 'value_i': Decimal('0'),
                'paid': Decimal('0'), 'open_quote': None, 'quote': quote, 'quote_ts': quote_ts, 'quote_a': rate * quote,
                'quote_age': int((local_reading(now_ts()) - quote_ts) / 86400), 'chain_ts': chain_ts,
                'share': Decimal('0'), 'font': 'normal', 'header': symbol}

    def _claim_records(self, account: JalAccount) -> list:
        records = []
        for claim in JalReceivable().claims(account.id(), self._date):
            asset = JalAsset(claim['asset_id'])
            payer = protocol_name(account.chain(), claim['source']) or claim['source']
            records.append(self._valued_record(self.CLAIM, account, asset, asset.name(), claim['amount'], 0, payer))
            records[-1]['source'] = claim['source']
        return records

    # A box belongs to every wallet it was filled from, so it may be listed under more than one of them
    def _staked_records(self, account: JalAccount) -> list:
        records = []
        for box in JalStakingBox.get_boxes(self._date):
            if account.id() not in [x.id() for x in box.source_accounts()]:
                continue
            name = ' · '.join([x for x in (box.name(), box.protocol()) if x])
            for holding in box.holdings(self._date):
                asset = holding['asset']
                accrual = JalChainBalance().accrual(box.id(), asset.id(), holding['amount'], self._date)
                records.append(self._valued_record(self.STAKED, box.account(), asset, name,
                                                   holding['amount'] + accrual['delta'], box.opened_at(),
                                                   box.protocol(), accrual['measured'] if accrual['delta'] else 0))
        return records

    @staticmethod
    def _total_row(name: str, value: Decimal, value_common: Decimal) -> AssetTreeItem:
        row = AssetTreeItem()
        row.details().update({'header': name, 'value': value, 'value_common': value_common, 'kind': 'total'})
        return row

    # The rows of 'records' under a heading of their own, added to 'root'
    @staticmethod
    def _append_section(root: AssetTreeItem, title: str, records: list) -> list:
        group = AssetTreeItem(None, group='section')
        group.setGroupValue(title)
        root.appendChild(group)
        rows = [AssetTreeItem(dict(x, section=title)) for x in records]
        for row in rows:
            group.appendChild(row)
        return rows

    def _build_tree(self) -> AssetTreeItem:
        root = AccountHoldingsRoot()
        self._has_positions = False
        if not self._account_id:
            return root
        account = JalAccount(self._account_id)
        records = sorted(self._account_records(account), key=lambda x: (x['asset_is_currency'], x['asset']))
        for record in records:
            record['kind'] = self.MONEY if record['asset_is_currency'] else self.HELD
            record['mark'] = JalAsset(record['asset_id']).protocol() if record['kind'] == self.HELD else ''
        rows = [AssetTreeItem(x) for x in records]
        for row in rows:
            root.appendChild(row)
        claims = self._claim_records(account)
        if claims:
            rows += self._append_section(root, self.tr("Claimable (earned, not yet paid)"), claims)
        value = sum([x.details()['value'] for x in rows], Decimal('0'))
        value_common = sum([x.details()['value_common'] for x in rows], Decimal('0'))
        root.appendChild(self._total_row(self.tr("On this account (equals Balance)"), value, value_common))
        staked = self._staked_records(account)
        if staked:
            title = self.tr("Staked from this account (separate accounts, not in Balance)")
            for row in self._append_section(root, title, staked):
                value += row.details()['value']
                value_common += row.details()['value_common']
            root.appendChild(self._total_row(self.tr("Including staked"), value, value_common))
        self._has_positions = any(x['kind'] == self.HELD for x in records) or bool(claims) or bool(staked)
        return root
