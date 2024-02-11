from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QHeaderView
from jal.constants import CustomColor, PredefinedAccountType
from jal.db.helpers import now_ts, day_end
from jal.db.tree_model import AbstractTreeItem, ReportTreeModel
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, Transfer, CorporateAction
from jal.widgets.delegates import GridLinesDelegate, FloatDelegate, TimestampDelegate
from jal.widgets.helpers import ts2d

# ----------------------------------------------------------------------------------------------------------------------
class AssetTreeItem(AbstractTreeItem):
    def __init__(self, data=None, parent=None, group=''):
        super().__init__(parent, group)
        if data is None:
            self._data = {
                'currency_id': 0, 'currency': '', 'account_id': 0, 'account': '', 'asset_id': 0, 'tag': '',
                'asset_is_currency': False, 'asset': '', 'asset_name': '', 'country_id': 0, 'country': '', 'expiry': 0,
                'since': 0, 'qty': Decimal('0'), 'value_i': Decimal('0'), 'payments': Decimal('0'),
                'quote': Decimal('0'), 'quote_ts': Decimal('0'), 'quote_a': Decimal('0')
            }
        else:
            self._data = data.copy()
        self._data['share'] = Decimal('0')
        self._data['value'] = self._data['quote'] * self._data['qty']
        self._data['value_a'] = self._data['quote_a'] * self._data['qty'] if self._data['quote_a'] else Decimal('0')
        self._data['profit'] = self._data['quote'] * self._data['qty'] - self._data['value_i'] if not self._data['asset_is_currency'] else Decimal('0')
        self._data['profit_rel'] = Decimal('100') * (self._data['quote'] * self._data['qty'] / self._data['value_i'] - 1) if self._data['value_i'] != Decimal('0') else Decimal('0')

    def _calculateGroupTotals(self, child_data):
        self._data['currency'] = child_data['currency']
        self._data['account'] = child_data['account']
        self._data['asset'] = child_data['asset']
        self._data['country'] = child_data['country']
        self._data['tag'] = child_data['tag']
        self._data['payments'] += child_data['payments']
        self._data['value'] += child_data['value']
        self._data['value_a'] += child_data['value_a']
        self._data['profit'] += child_data['profit']
        self._data['profit_rel'] = Decimal('100') * self._data['profit'] / (self._data['value'] - self._data['profit']) if self._data['value'] != self._data['profit'] else Decimal('0')

    def _afterParentGroupUpdate(self, group_data):
        self._data['share'] = Decimal('100') * self._data['value_a'] / group_data['value_a'] if group_data['value_a'] else Decimal('0')

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
        self._bold_font = QFont()
        self._bold_font.setBold(True)
        self._strikeout_font = QFont()
        self._strikeout_font.setStrikeOut(True)
        self._italic_font = QFont()
        self._italic_font.setItalic(True)
        self._currency = 0
        self._only_active_accounts = True
        self._currency_name = ''
        self._date = day_end(now_ts())
        self._columns = [{'name': self.tr("Currency/Account/Asset")},  # 'field' key isn't used as model isn't query based
                         {'name': self.tr("Asset Name")},
                         {'name': self.tr("Qty")},
                         {'name': self.tr("Since")},
                         {'name': self.tr("Open")},
                         {'name': self.tr("Last")},
                         {'name': self.tr("Share, %")},
                         {'name': self.tr("P/L, %")},
                         {'name': self.tr("P/L")},
                         {'name': self.tr("Paid")},
                         {'name': self.tr("Value")},
                         {'name': self.tr("Value, ")}]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        value = super().headerData(section, orientation, role)
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == 11:
            value += self._currency_name
        return value

    def data(self, index, role=Qt.DisplayRole):
        assert index.column() in range(len(self._columns))
        try:
            if not index.isValid():
                return None
            item = index.internalPointer()
            if role == Qt.DisplayRole:
                return self.data_text(item, index.column())
            if role == Qt.FontRole:
                return self.data_font(item, index.column())
            if role == Qt.BackgroundRole:
                return self.data_background(item, self._view.isEnabled())
            if role == Qt.ToolTipRole:
                return self.data_tooltip(item.details(), index.column())
            return None
        except Exception as e:
            print(e)

    def data0(self, item, data):
        if item.isGroup():
            group, value = item.getGroup()
            return data[group.strip("_id")]
        else:
            all_fields = ['currency', 'account', 'asset']
            display_fields = [y for y in all_fields if y not in [x.strip("_id") for x in self._groups]]
            return ': '.join([data[x] for x in display_fields])

    def data1(self, data):
        expiry_text = ""
        if data['expiry']:
            expiry_header = self.tr("Exp:")
            expiry_text = f" [{expiry_header} {ts2d(int(data['expiry']))}]"
        return data['asset_name'] + expiry_text

    def data_text(self, item, column):
        data = item.details()
        if column == 0:
            return self.data0(item, data)
        if column == 1:
            return self.data1(data)
        if column == 2:
            return data['qty']
        if column == 3:
            return data['since']
        if column == 4:
            if data['qty'] != Decimal('0') and data['value_i'] != Decimal('0'):
                return data['value_i'] / data['qty']
            else:
                return Decimal('NaN')
        if column == 5:
            return data['quote']
        if column == 6:
            return data['share']
        if column == 7:
            return data['profit_rel']
        if column == 8:
            return data['profit']
        if column == 9:
            return data['payments']
        if column == 10:
            return data['value']
        if column == 11:
            return data['value_a']

    def data_tooltip(self, data, column):
        if 5 <= column <= 10:
            quote_date = datetime.utcfromtimestamp(int(data['quote_ts']))
            quote_age = int((datetime.utcnow() - quote_date).total_seconds() / 86400)
            if quote_age > 7:
                return self.tr("Last quote date: ") + ts2d(int(data['quote_ts']))
        return ''

    def data_font(self, item, column):
        data = item.details()
        if item.isGroup():
            return self._bold_font
        else:
            if column == 1 and data['expiry']:
                expiry_date = datetime.utcfromtimestamp(int(data['expiry']))
                days_remaining = int((expiry_date - datetime.utcnow()).total_seconds() / 86400)
                if days_remaining <= 10:
                    if days_remaining < 0:
                        return self._strikeout_font
                    else:
                        return self._italic_font
            if column >= 5 and column <= 10:
                quote_date = datetime.utcfromtimestamp(int(data['quote_ts']))
                quote_age = int((datetime.utcnow()- quote_date).total_seconds() / 86400)
                if quote_age > 7:
                    return self._italic_font

    def data_background(self, item, enabled=True):
        factor = 100 if enabled else 125
        if item.isGroup():
            group, value = item.getGroup()
            if group == "currency_id":
                return QBrush(CustomColor.LightPurple.lighter(factor))
            if group == "account_id":
                return QBrush(CustomColor.LightBlue.lighter(factor))

    def configureView(self):
        self._view.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._view.header().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(len(self._columns))[2:]:
            self._view.header().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._grid_delegate = GridLinesDelegate(self._view)
        self._date_delegate = TimestampDelegate(display_format='%d/%m/%Y', parent=self._view)
        self._float_delegate = FloatDelegate(0, allow_tail=True, parent=self._view)
        self._float2_delegate = FloatDelegate(2, allow_tail=False, parent=self._view)
        self._float4_delegate = FloatDelegate(4, allow_tail=False, parent=self._view)
        self._profit_delegate = FloatDelegate(2, allow_tail=False, colors=True, parent=self._view)
        self._view.setItemDelegateForColumn(0, self._grid_delegate)
        self._view.setItemDelegateForColumn(1, self._grid_delegate)
        self._view.setItemDelegateForColumn(2, self._float_delegate)
        self._view.setItemDelegateForColumn(3, self._date_delegate)
        self._view.setItemDelegateForColumn(4, self._float4_delegate)
        self._view.setItemDelegateForColumn(5, self._float4_delegate)
        self._view.setItemDelegateForColumn(6, self._float2_delegate)
        self._view.setItemDelegateForColumn(7, self._profit_delegate)
        self._view.setItemDelegateForColumn(8, self._profit_delegate)
        self._view.setItemDelegateForColumn(9, self._float2_delegate)
        self._view.setItemDelegateForColumn(10, self._float2_delegate)
        self._view.setItemDelegateForColumn(11, self._float2_delegate)
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
    # 2nd (Decimal) = 0 (not implemented - the amount of payments that were accumulated for given asset)
    def get_asset_history_payments(self, account: JalAccount, asset: JalAsset, end_ts: int) -> (int, Decimal):
        trades = account.open_trades_list(asset, end_ts)
        since = min([x['operation'].timestamp() for x in trades])
        amount = account.asset_payments_amount(asset, since, end_ts)
        for trade in trades:
            operation = trade['operation']
            if operation.type() == LedgerTransaction.Transfer:
                transfer_out = LedgerTransaction().get_operation(operation.type(), operation.id(), Transfer.Outgoing)
                since_new, amount_new = self.get_asset_history_payments(transfer_out.account(), asset, transfer_out.timestamp()-1)  # get position just before the transfer
            elif operation.type() == LedgerTransaction.CorporateAction and operation.subtype() == CorporateAction.Split:
                since_new, amount_new = self.get_asset_history_payments(account, asset, operation.timestamp()-1)  # get position just before the split
            else:
                continue
            since = min(since, since_new)
            amount += amount_new
        return since, amount

    # Populate table 'holdings' with data calculated for given parameters of model: _currency, _date,
    def prepareData(self):
        holdings = []
        accounts = JalAccount.get_all_accounts(account_type=PredefinedAccountType.Investment, active_only=self._only_active_accounts)
        for account in accounts:
            account_holdings = []
            assets = account.assets_list(self._date)
            rate = JalAsset(account.currency()).quote(self._date, self._currency)[1]
            for asset_data in assets:
                asset = asset_data['asset']
                quote_ts, quote = asset.quote(self._date, account.currency())
                since, payments_amount = self.get_asset_history_payments(account, asset, self._date)
                record = {
                    "currency_id": account.currency(),
                    "currency": JalAsset(account.currency()).symbol(),
                    "account_id": account.id(),
                    "account": account.name(),
                    "asset_id": asset.id(),
                    "asset_is_currency": False,
                    "asset": asset.symbol(currency=account.currency()),
                    "asset_name": asset.name(),
                    "country_id": asset.country().id(),
                    "country": asset.country().name(),
                    "tag": asset.tag().name() if asset.tag().name() else self.tr("N/A"),
                    "expiry": asset.expiry(),
                    "since": since,
                    "qty": asset_data['amount'],
                    "value_i": asset_data['value'],
                    "payments": payments_amount,
                    "quote": quote,
                    "quote_ts": quote_ts,
                    "quote_a": rate * quote
                }
                account_holdings.append(record)
            money = account.get_asset_amount(self._date, account.currency())
            if money:
                account_holdings.append({
                    "currency_id": account.currency(),
                    "currency": JalAsset(account.currency()).symbol(),
                    "account_id": account.id(),
                    "account": account.name(),
                    "asset_id": account.currency(),
                    "asset_is_currency": True,
                    "asset": JalAsset(account.currency()).symbol(),
                    "asset_name": JalAsset(account.currency()).name(),
                    "country_id": JalAsset(account.currency()).country().id(),
                    "country": JalAsset(account.currency()).country().name(),
                    "tag": self.tr("Money"),
                    "expiry": 0,
                    "since": 0,
                    "qty": money,
                    "value_i": Decimal('0'),
                    "payments": Decimal('0'),
                    "quote": Decimal('1'),
                    "quote_ts": day_end(now_ts()),
                    "quote_a": rate
                })
            holdings += account_holdings
        sort_names = [x.removesuffix("_id") for x in self._groups]
        if 'asset' in sort_names:
            sort_names.insert(sort_names.index('asset'), 'asset_is_currency')  # Need to put currency at the end
        else:
            sort_names += ['asset_is_currency', 'asset']   # Sort by asset name for any kind of grouping
        holdings = sorted(holdings, key=lambda x: tuple([x[key_name] for key_name in sort_names]))

        self._root = AssetTreeItem()
        for position in holdings:
            new_item = AssetTreeItem(position)
            leaf = self._root.getGroupLeaf(self._groups, new_item)
            leaf.appendChild(new_item)
        super().prepareData()
