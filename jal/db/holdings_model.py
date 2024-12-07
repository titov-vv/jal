from __future__ import annotations
import logging
from datetime import datetime, timezone
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHeaderView
from jal.db.helpers import now_ts, day_end
from jal.db.tree_model import AbstractTreeItem, ReportTreeModel
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, Transfer, CorporateAction
from jal.widgets.delegates import GridLinesDelegate, FloatDelegate, TimestampDelegate
from jal.widgets.helpers import ts2d


# ----------------------------------------------------------------------------------------------------------------------
OLD_QUOTE_AGE = 7   # when mark line as italic for old quote
# ----------------------------------------------------------------------------------------------------------------------
class AssetTreeItem(AbstractTreeItem):
    def __init__(self, data=None, parent=None, group=''):
        super().__init__(parent, group)
        if data is None:
            self._data = {
                'header': '', 'currency_id': 0, 'currency': '', 'account_id': 0, 'account': '', 'asset_id': 0,
                'tag': '', 'asset_is_currency': False, 'asset': '', 'asset_name': '', 'country_id': 0, 'country': '',
                'since': 0, 'qty': None, 'value_i': Decimal('0'), 'paid': Decimal('0'),
                'open_quote': None, 'quote': None, 'quote_ts': Decimal('0'), 'quote_a': Decimal('0'),
                'value': Decimal('0'), 'value_common': Decimal('0'), 'p/l': Decimal('0'), 'p/l%': Decimal('0'),
                'font': 'bold', 'quote_age': 0, 'share': Decimal('0')
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
        self._only_active_accounts = True
        self._currency_name = ''
        self._date = day_end(now_ts())
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
            return None
        except Exception as e:
            print(e)

    def data_tooltip(self, data):
        if data['quote_age'] > OLD_QUOTE_AGE:
            return self.tr("Last quote date: ") + ts2d(int(data['quote_ts']))
        return None

    def configureView(self):
        for field in [x['field'] for x in self._columns]:
            if field == 'asset_name':
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.Stretch)
            else:
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.ResizeToContents)
        self._grid_delegate = GridLinesDelegate(self._view)
        self._date_delegate = TimestampDelegate(display_format='%d/%m/%Y', parent=self._view)
        self._float_delegate = FloatDelegate(0, allow_tail=True, parent=self._view)
        self._float2_delegate = FloatDelegate(2, allow_tail=False, parent=self._view)
        self._float4_delegate = FloatDelegate(4, allow_tail=False, parent=self._view)
        self._profit_delegate = FloatDelegate(2, allow_tail=False, colors=True, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex('header'), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('asset_name'), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('qty'), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('since'), self._date_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('open_quote'), self._float4_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('quote'), self._float4_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('share'), self._float2_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('p/l%'), self._profit_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('p/l'), self._profit_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('paid'), self._float2_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('value'), self._float2_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('value_common'), self._float2_delegate)
        super().configureView()

    def updateView(self, currency_id, date, grouping, show_inactive):
        update = False
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = JalAsset(currency_id).symbol()
            update = True
        if self._date != date.endOfDay(Qt.UTC).toSecsSinceEpoch():
            self._date = date.endOfDay(Qt.UTC).toSecsSinceEpoch()
            update = True
        if self._only_active_accounts == show_inactive:  # The logic is reversed inside the report
            self._only_active_accounts = not self._only_active_accounts
            update = True
        if self.setGrouping(grouping) or update:
            self.prepareData()

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
        since = min([x.open_operation().timestamp() for x in trades])
        amount = account.asset_payments_amount(asset, since, end_ts)
        for trade in trades:
            operation = trade.open_operation()
            if operation.type() == LedgerTransaction.Transfer:
                transfer_out = LedgerTransaction().get_operation(operation.type(), operation.id(), Transfer.Outgoing)
                since_new, amount_new = self.get_asset_history_payments(transfer_out.account(), asset, transfer_out.timestamp()-1)  # get position just before the transfer
            elif operation.type() == LedgerTransaction.CorporateAction and operation.subtype() == CorporateAction.Split:
                since_new, amount_new = self.get_asset_history_payments(operation.account(), asset, operation.timestamp()-1)  # get position just before the split
            else:
                continue
            since = min(since, since_new)
            amount += amount_new
        return since, amount

    # Populate table 'holdings' with data calculated for given parameters of model: _currency, _date,
    def prepareData(self):
        self.beginResetModel()
        holdings = []
        accounts = JalAccount.get_all_accounts(investing_only=True, active_only=self._only_active_accounts)
        for account in accounts:
            account_holdings = []
            assets = account.assets_list(self._date)
            rate = JalAsset(account.currency()).quote(self._date, self._currency)[1]
            all_fields = ['currency', 'account', 'asset']
            display_fields = [y for y in all_fields if y not in [x.strip("_id") for x in self._groups]]
            for asset_data in assets:
                asset = asset_data['asset']
                quote_ts, quote = asset.quote(self._date, account.currency())
                quote_age = int((datetime.now(tz=timezone.utc) - datetime.fromtimestamp(quote_ts, tz=timezone.utc)).total_seconds() / 86400)
                since, payments_amount = self.get_asset_history_payments(account, asset, self._date)
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
                    "asset": asset.symbol(currency=account.currency()),
                    "asset_name": asset.name() + expiry_text,
                    "asset_is_currency": False,
                    "country_id": asset.country().id(),
                    "country": asset.country().name(),
                    "tag": asset.tag().name() if asset.tag().name() else self.tr("N/A"),
                    "since": since,
                    "qty": asset_data['amount'],
                    "value_i": asset_data['value'],
                    "paid": payments_amount,
                    "open_quote": asset_data['value'] / asset_data['amount'],
                    "quote": quote,
                    "quote_ts": quote_ts,
                    "quote_a": rate * quote,
                    "quote_age": quote_age,
                    "share": Decimal('0'),
                    "font": font
                }
                record['header'] = ': '.join([record[x] for x in display_fields])
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
                    "asset_name": JalAsset(account.currency()).name(),
                    "asset_is_currency": True,
                    "country_id": JalAsset(account.currency()).country().id(),
                    "country": JalAsset(account.currency()).country().name(),
                    "tag": self.tr("Money"),
                    "since": 0,
                    "qty": money,
                    "value_i": Decimal('0'),
                    "paid": Decimal('0'),
                    "open_quote": None,
                    "quote": Decimal('1'),
                    "quote_ts": day_end(now_ts()),
                    "quote_a": rate,
                    "quote_age": 0,
                    "share": Decimal('0'),
                    "font": 'normal'
                }
                record['header'] = ': '.join([record[x] for x in display_fields])
                account_holdings.append(record)
            holdings += account_holdings
        # Sort data with respect to groups before building the tree
        sort_names = [x.removesuffix("_id") for x in self._groups]
        if 'asset' in sort_names:
            sort_names.insert(sort_names.index('asset'), 'asset_is_currency')  # Need to put currency at the end
        else:
            sort_names += ['asset_is_currency', 'asset']   # Sort by asset name for any kind of grouping
        holdings = sorted(holdings, key=lambda x: tuple([x[key_name] for key_name in sort_names]))
        # Add data records to the report tree
        self._root = AssetTreeItem()
        for position in holdings:
            new_item = AssetTreeItem(position)
            leaf = self._root.getGroupLeaf(self._groups, new_item)
            leaf.appendChild(new_item)
        self.endResetModel()
        super().prepareData()
