from __future__ import annotations
from decimal import Decimal

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QHeaderView
from jal.constants import IconOwner, AccountStatus
from jal.db.helpers import localize_decimal
from jal.db.tree_model import AbstractTreeItem, ReportTreeModel
from jal.db.settings import JalSettings
from jal.db.clock import day_finish, today_finish
from jal.db.asset import JalAsset
from jal.db.account import JalAccount
from jal.db.common_models import account_row_icon, account_tag_icon
from jal.db.icon import JalIcons
from jal.widgets.delegates import GridLinesDelegate, FloatDelegate, TaggedIconDelegate, TAG_ICON_ROLE
from jal.widgets.icons import JalIcon
from jal.widgets.theme import Theme, Meaning


# ----------------------------------------------------------------------------------------------------------------------
class AccountTreeItem(AbstractTreeItem):
    def __init__(self, data=None, parent=None, group=''):
        super().__init__(parent, group)
        if data is None:
            self._data = {
                "group": '', "group_icon": JalIcon.NONE, "subgroup": '', "subgroup_icon": JalIcon.NONE,
                "icon_id": JalIcon.NONE, "folded": False, "tag_name": '', "account": 0, "account_name": '',
                "currency": 0, "currency_name": '', "value": Decimal('0'), "value_common": Decimal('0'),
                "credit_limit": Decimal('0'), "reconciled": 0, "status": AccountStatus.Active, "font": "bold"
            }
        else:
            self._data = data.copy()

    # A group row is named by the very field the tree was grouped on, and wears the glyph its children carry for
    # that field - so the same code names the background row, the account types beside it and the account types
    # nested inside it.
    def _calculateGroupTotals(self, child_data):
        if self._group:
            self._data['account_name'] = child_data[self._group]
            self._data['icon_id'] = child_data[self._group + '_icon']
            self._data['folded'] = child_data['folded'] and self._group == 'group'
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

    # The background group opens folded.
    def isFolded(self) -> bool:
        return self.isGroup() and self._data['folded']

    def getGroupLeaf(self, group_fields: list, item: AccountTreeItem) -> AccountTreeItem:  # FIXME: similar code in Holdings model - need to combine and simplify
        if group_fields:
            group_item = None
            group_name = group_fields[0]
            # A row with nothing to say at this level does not take it. That is what lets the background bucket be
            # grouped one level deeper than the account types beside it, without every other account gaining an
            # empty row of its own.
            if item.details()[group_name] == '':
                return self.getGroupLeaf(group_fields[1:], item)
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
        self._name_delegate = None
        self._float_delegate = None
        self._view = parent_view
        self._data = []
        self._currency = 0
        self._currency_name = ''
        self._min_status = JalSettings().getValue("BalancesMinAccountStatus", AccountStatus.Background)
        self._use_credit = JalSettings().getValue("UseAccountCreditLimit", True)
        self._group_by_tag = JalSettings().getValue("GroupBalancesByTag", False)
        self._date = today_finish()
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
            if role == Qt.DecorationRole and index.column() == self.fieldIndex('account_name'):
                # Two kinds of picture in one column, which is what the indentation of a tree already separates:
                # a group row is an account TYPE and wears the glyph of that type, while the accounts under it are
                # particular institutions and wear whatever logo they carry (a blank of the same size if none).
                if item.isGroup():
                    return JalIcon[item.details().get('icon_id', JalIcon.NONE)]
                return account_row_icon(JalAccount(item.details().get('account', 0)))
            # The mark of the tag group an account was put in, drawn before the icon above. A group row stands for
            # the type and is not in any tag group of its own.
            if role == TAG_ICON_ROLE and index.column() == self.fieldIndex('account_name'):
                if item.isGroup():
                    return None
                return account_tag_icon(JalAccount(item.details().get('account', 0)))
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
        shade = Theme.fill if enabled else Theme.tint
        if unreconciled > 15:
            return QBrush(shade(Meaning.NEGATIVE))
        if unreconciled > 7:
            return QBrush(shade(Meaning.WARNING))
        return None

    def configureView(self):
        for field in [x['field'] for x in self._columns]:
            if field == 'account_name':
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.Stretch)
            else:
                self._view.header().setSectionResizeMode(self.fieldIndex(field), QHeaderView.ResizeToContents)
        self._grid_delegate = GridLinesDelegate(self._view)
        self._name_delegate = TaggedIconDelegate(self._view)
        self._float_delegate = FloatDelegate(2, allow_tail=False, empty_zero=True, parent=self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex('account_name'), self._name_delegate)
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
        if self._date != day_finish(new_date):
            self._date = day_finish(new_date)
            self.prepareData()

    # The lowest AccountStatus this view shows - a wider view is simply a lower bound (see AccountStatus)
    @Slot()
    def setMinStatus(self, min_status: int):
        self._min_status = int(min_status)
        JalSettings().setValue("BalancesMinAccountStatus", self._min_status)
        self.prepareData()

    def minStatus(self) -> int:
        return self._min_status

    @Slot()
    def useCreditLimits(self, state: bool):
        self._use_credit = state
        JalSettings().setValue("UseAccountCreditLimit", state)
        self.prepareData()

    @Slot()
    def groupByTag(self, state: bool):
        self._group_by_tag = state
        JalSettings().setValue("GroupBalancesByTag", state)
        self.prepareData()

    # What orders the groups, and the accounts inside each of them. The background group comes after every type
    # group whatever its name, because it is a summary and not one more kind of account. With clustering on, the tag
    # comes first inside a group, so accounts that share one gather together and their marks form an unbroken run
    # down the column - which is what the mark is for. Untagged accounts make a cluster of their own, at the top,
    # because '' precedes every tag name.
    def _sort_key(self, balance: dict):
        if self._group_by_tag:
            return balance['folded'], balance['group'], balance['subgroup'], balance['tag_name'], balance['account_name']
        return balance['folded'], balance['group'], balance['subgroup'], balance['account_name']

    def getAccountId(self, index):
        if not index.isValid():
            return 0
        return index.internalPointer().details().get('account', 0)

    def update(self):
        self.prepareData()

    # Populate table balances with data calculated for given parameters of model: _currency, _date, _min_status
    def prepareData(self):
        self.beginResetModel()
        # Two levels of grouping to reflect account types and background accounts.
        self.setGrouping("group;subgroup")
        balances = []
        # Deposit boxes are asked for explicitly: they are accounts of a hidden type, so they are excluded by
        # default, but the money in an open deposit is part of the balance sheet and gets its own type group here.
        accounts = JalAccount.get_all_accounts(min_status=self._min_status, include_hidden=True)
        for account in accounts:
            value = account.balance(self._date)
            rate = JalAsset(account.currency()).quote(self._date, self._currency)[1]
            if value != Decimal('0'):
                foreground = account.is_foreground()
                balances.append({
                    "group": account.type_name() if foreground else self.tr("Background"),
                    "group_icon": account.type_icon() if foreground else JalIcon.LIST,
                    "subgroup": '' if foreground else account.type_name(),
                    "subgroup_icon": JalIcon.NONE if foreground else account.type_icon(),
                    "folded": not foreground,
                    "tag_name": account.tag().name(),
                    "account": account.id(),
                    "account_name": account.name(),
                    "currency": account.currency(),
                    "currency_name": JalAsset(account.currency()).symbol(),
                    "value": value + account.credit_limit() if self._use_credit else value,
                    "value_common": value * rate,
                    "credit_limit": account.credit_limit(),
                    "unreconciled": (account.last_operation_date() - account.reconciled_at())/86400,
                    "status": account.status(),
                    "font": 'normal' if foreground else 'italic'
                })
        # Sort data items and add them into the tree in right order
        balances = sorted(balances, key=self._sort_key)
        self._root = AccountTreeItem()
        for position in balances:
            new_item = AccountTreeItem(position)
            leaf = self._root.getGroupLeaf(self._groups, new_item)
            leaf.appendChild(new_item)
        self.endResetModel()
        super().prepareData()
