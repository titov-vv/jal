from __future__ import annotations
from decimal import Decimal

from PySide6.QtCore import Qt, Slot, QDate
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QHeaderView
from jal.constants import CustomColor
from jal.db.helpers import localize_decimal
from jal.db.tree_model import AbstractTreeItem, ReportTreeModel
from jal.db.settings import JalSettings
from jal.db.asset import JalAsset
from jal.db.account import JalAccount
from jal.db.deposit import JalDeposit
from jal.widgets.delegates import GridLinesDelegate, FloatDelegate
from jal.widgets.icons import JalIcon


# ----------------------------------------------------------------------------------------------------------------------
class AccountTreeItem(AbstractTreeItem):
    def __init__(self, data=None, parent=None, group=''):
        super().__init__(parent, group)
        if data is None:
            self._data = {
                "account_tag": '', "icon_id": JalIcon.NONE, "account": 0, "account_name": '', "currency": 0, "currency_name": '',
                "value": Decimal('0'), "value_common": Decimal('0'), "credit_limit": Decimal('0'), "reconciled": 0, "active": 1, "font": "bold"
            }
        else:
            self._data = data.copy()

    def _calculateGroupTotals(self, child_data):
        self._data['account_name'] = child_data['account_tag']
        self._data['icon_id'] = child_data['icon_id']
        self._data['value_common'] += child_data['value_common']

    def _afterParentGroupUpdate(self, group_data):
        pass

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

    def getGroupLeaf(self, group_fields: list, item: AccountTreeItem) -> AccountTreeItem:  # FIXME: similar code in Holdings model - need to combine and simplify
        if group_fields:
            group_item = None
            group_name = group_fields[0]
            for child in self._children:
                if child.details()[group_name] == item.details()[group_name]:
                    group_item = child
            if group_item is None:
                group_item = AccountTreeItem(None, parent=self, group=group_name)
                group_item.setGroupValue(item.details()[group_name])
                self._children.append(group_item)
            return group_item.getGroupLeaf(group_fields[1:], item)
        else:
            return self


# ----------------------------------------------------------------------------------------------------------------------
class BalancesModel(ReportTreeModel):
    ACCOUNT_ROLE = Qt.UserRole

    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._grid_delegate = None
        self._float_delegate = None
        self._view = parent_view
        self._data = []
        self._currency = 0
        self._currency_name = ''
        self._active_only = not JalSettings().getValue("ShowInactiveAccountBalances", False)
        self._use_credit = JalSettings().getValue("UseAccountCreditLimit", True)
        self._date = QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch()
        self.bold_font = QFont()
        self.bold_font.setBold(True)
        self.italic_font = QFont()
        self.italic_font.setItalic(True)
        self._fonts = {'normal': None, 'bold': self.bold_font, 'italic': self.italic_font}
        self._columns = [
            {'name': self.tr("Account"), 'field': 'account_name'},
            {'name': self.tr("Balance"), 'field': 'value'},
            {'name': self.tr(" "), 'field': 'currency_name'},
            {'name': self.tr("Balance, "), 'field': 'value_common'}
        ]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        value = super().headerData(section, orientation, role)
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == self.fieldIndex('value_common'):
            value += self._currency_name
        return value

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        assert index.column() in range(len(self._columns))
        try:
            item = index.internalPointer()
            if role == Qt.DisplayRole:
                return item.details().get(self._columns[index.column()]['field'], None)
            if role == Qt.FontRole:
                return self._fonts.get(item.details()['font'], None)
            if role == Qt.BackgroundRole and index.column() == self.fieldIndex('value'):
                return self.data_background(item.details().get('unreconciled', 0), self._view.isEnabled())
            if role == Qt.DecorationRole and item.isGroup() and index.column() == self.fieldIndex('account_name'):
                return JalIcon[item.details().get('icon_id', JalIcon.NONE)]
            if self._use_credit and index.column() == self.fieldIndex('value') and item.details()['credit_limit']:
                if role == Qt.DecorationRole:
                    return JalIcon[JalIcon.WITH_CREDIT]
                if role == Qt.ToolTipRole:
                    return self.tr("Credit limit: ") + localize_decimal(item.details()['credit_limit']) + " " + item.details()['currency_name']
            if role == self.ACCOUNT_ROLE:
                return item.details().get('account', 0)
            return None
        except Exception as e:
            print(e)

    def footerData(self, section, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == self.fieldIndex('account_name'):
                return self.tr("Total:")
            elif section == self.fieldIndex('value_common'):
                totals_data = self._root.details()
                return localize_decimal(totals_data[self._columns[section]['field']], precision=2)
        if role == Qt.FontRole:
            return self.bold_font
        if role == Qt.TextAlignmentRole:
            if section == self.fieldIndex('value_common'):
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        if role == Qt.DecorationRole and section == self.fieldIndex('account_name'):
            return JalIcon[JalIcon.TOTAL]
        return None

    def data_background(self, unreconciled, enabled=True):
        factor = 100 if enabled else 125
        if unreconciled > 15:
            return QBrush(CustomColor.LightRed.lighter(factor))
        if unreconciled > 7:
            return QBrush(CustomColor.LightYellow.lighter(factor))
        return None

    def configureView(self):
        for field in [x['field'] for x in self._columns]:
            if field == 'account_name':
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.Stretch)
            else:
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.ResizeToContents)
        self._grid_delegate = GridLinesDelegate(self._view)
        self._float_delegate = FloatDelegate(2, allow_tail=False, empty_zero=True, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex('account_name'), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('currency_name'), self._grid_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('value'), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex('value_common'), self._float_delegate)
        self._view.footer().set_span(self.fieldIndex('account_name'), [self.fieldIndex('account_name'), self.fieldIndex('value')])
        self._view.footer().set_span(self.fieldIndex('value_common'), [self.fieldIndex('currency_name'), self.fieldIndex('value_common')])
        super().configureView()

    @Slot()
    def setCurrency(self, currency_id):
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = JalAsset(currency_id).symbol()
            self.prepareData()

    @Slot()
    def setDate(self, new_date):
        if self._date != new_date.endOfDay(Qt.UTC).toSecsSinceEpoch():
            self._date = new_date.endOfDay(Qt.UTC).toSecsSinceEpoch()
            self.prepareData()

    @Slot()
    def showInactiveAccounts(self, state: bool):
        self._active_only = not state
        JalSettings().setValue("ShowInactiveAccountBalances", state)
        self.prepareData()

    @Slot()
    def useCreditLimits(self, state: bool):
        self._use_credit = state
        JalSettings().setValue("UseAccountCreditLimit", state)
        self.prepareData()

    def getAccountId(self, index):
        if not index.isValid():
            return 0
        return index.internalPointer().details().get('account', 0)

    def update(self):
        self.prepareData()

    # Populate table balances with data calculated for given parameters of model: _currency, _date, _active_only
    def prepareData(self):
        self.beginResetModel()
        self.setGrouping("account_tag")
        balances = []
        accounts = JalAccount.get_all_accounts(active_only=self._active_only)
        for account in accounts:
            value = account.balance(self._date)
            rate = JalAsset(account.currency()).quote(self._date, self._currency)[1]
            if value != Decimal('0'):
                balances.append({
                    "account_tag": account.tag().name() if account.tag().name() else self.tr("Without tag"),
                    "icon_id": account.tag().icon(),
                    "account": account.id(),
                    "account_name": account.name(),
                    "currency": account.currency(),
                    "currency_name": JalAsset(account.currency()).symbol(),
                    "value": value + account.credit_limit() if self._use_credit else value,
                    "value_common": value * rate,
                    "credit_limit": account.credit_limit(),
                    "unreconciled": (account.last_operation_date() - account.reconciled_at())/86400,
                    "active": account.is_active(),
                    "font": 'normal' if account.is_active() else 'italic'
                })
        for deposit in JalDeposit.get_term_deposits(self._date):
            rate = deposit.currency().quote(self._date, self._currency)[1]
            balances.append({
                "account_tag": self.tr("Term deposits"),
                "icon_id": JalIcon.DEPOSIT_ACCOUNT,
                "account": 0,
                "account_name": deposit.name(),
                "currency": deposit.currency(),
                "currency_name": deposit.currency().symbol(),
                "value": deposit.balance(self._date),
                "value_common": deposit.balance(self._date) * rate,
                "credit_limit": Decimal('0'),
                "unreconciled": 0,
                "active": 1,
                "font": 'normal'
            })
        # Sort data items and add them into the tree in right order
        balances = sorted(balances, key=lambda x: (x['account_tag'], x['account_name']))
        self._root = AccountTreeItem()
        for position in balances:
            new_item = AccountTreeItem(position)
            leaf = self._root.getGroupLeaf(self._groups, new_item)
            leaf.appendChild(new_item)
        self.endResetModel()
        super().prepareData()
