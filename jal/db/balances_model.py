from decimal import Decimal

from PySide6.QtCore import Qt, Slot, QAbstractTableModel, QDate
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QHeaderView
from jal.constants import CustomColor, PredefinedAccountType
from jal.db.asset import JalAsset
from jal.db.account import JalAccount
from jal.widgets.delegates import FloatDelegate


class BalancesModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._data = []
        self._currency = 0
        self._currency_name = ''
        self._active_only = True
        self._date = QDate.currentDate().endOfDay(Qt.UTC).toSecsSinceEpoch()
        self._columns = [self.tr("Account"), self.tr("Balance"), " ", self.tr("Balance, ")]
        self._float_delegate = None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            col_name = self._columns[section] + self._currency_name if section == 3 else self._columns[section]
            return col_name
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self.data_text(index.row(), index.column())
        if role == Qt.FontRole:
            return self.data_font(index.row(), index.column())
        if role == Qt.BackgroundRole:
            return self.data_background(index.row(), index.column(), self._view.isEnabled())
        if role == Qt.TextAlignmentRole:
            if index.column() == 0 or index.column() == 2:
                return int(Qt.AlignLeft)
            else:
                return int(Qt.AlignRight)
        return None

    def data_text(self, row, column):
        if column == 0:
            if self._data[row]['level'] == 0:
                return self._data[row]['account_name']
            else:
                return PredefinedAccountType().get_name(self._data[row]['account_type'], default=self.tr("Total"))
        elif column == 1:
            return self._data[row]['balance']
        elif column == 2:
            return self._data[row]['currency_name'] if self._data[row]['balance'] != 0 else ''
        elif column == 3:
            return self._data[row]['balance_a']
        else:
            assert False

    def data_font(self, row, column):
        if self._data[row]['level'] > 0:
            font = QFont()
            font.setBold(True)
            return font
        if column == 0 and not self._data[row]['active']:
            font = QFont()
            font.setItalic(True)
            return font

    def data_background(self, row, column, enabled=True):
        factor = 100 if enabled else 125
        if column == 3:
            if self._data[row]['unreconciled'] > 15:
                return QBrush(CustomColor.LightRed.lighter(factor))
            if self._data[row]['unreconciled'] > 7:
                return QBrush(CustomColor.LightYellow.lighter(factor))

    def configureView(self):
        self._view.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(len(self._columns))[1:]:
            self._view.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._float_delegate = FloatDelegate(2, allow_tail=False, empty_zero=True, parent=self._view)
        self._view.setItemDelegateForColumn(1, self._float_delegate)
        self._view.setItemDelegateForColumn(3, self._float_delegate)

    @Slot()
    def setCurrency(self, currency_id):
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = JalAsset(currency_id).symbol()
            self.calculateBalances()

    @Slot()
    def setDate(self, new_date):
        if self._date != new_date.endOfDay(Qt.UTC).toSecsSinceEpoch():
            self._date = new_date.endOfDay(Qt.UTC).toSecsSinceEpoch()
            self.calculateBalances()

    @Slot()
    def toggleActive(self, state):
        if state == 0:
            self._active_only = True
        else:
            self._active_only = False
        self.calculateBalances()

    def getAccountId(self, row):
        return self._data[row]['account']

    def update(self):
        self.calculateBalances()

    # Populate table balances with data calculated for given parameters of model: _currency, _date, _active_only
    def calculateBalances(self):
        balances = []
        accounts = JalAccount.get_all_accounts(active_only=self._active_only)
        for account in accounts:
            value = value_adjusted = Decimal('0')
            assets = account.assets_list(self._date)
            rate = JalAsset(account.currency()).quote(self._date, self._currency)[1]
            for asset_data in assets:
                asset = asset_data['asset']
                asset_value = asset_data['amount'] * asset.quote(self._date, account.currency())[1]
                value += asset_value
                value_adjusted += asset_value * rate
            money = account.get_asset_amount(self._date, account.currency())
            value += money
            value_adjusted += money * rate
            if value != Decimal('0'):
                balances.append({
                    "account_type": account.type(),
                    "account": account.id(),
                    "account_name": account.name(),
                    "currency": account.currency(),
                    "currency_name": JalAsset(account.currency()).symbol(),
                    "balance": value,
                    "balance_a": value_adjusted,
                    "unreconciled": (account.last_operation_date() - account.reconciled_at())/86400,
                    "active": account.is_active()
                })
        balances = sorted(balances, key=lambda x: (x['account_type'], x['account_name']))
        self._data = []
        field_names = ["account_type", "account", "account_name", "currency", "currency_name", "balance", "balance_a",
                       "unreconciled", "active", "level"]
        current_type = 0
        for values in balances:
            values['level'] = 0
            if values['account_type'] != current_type:
                if current_type != 0:
                    sub_total = sum([row['balance_a'] for row in self._data if row['account_type'] == current_type])
                    self._data.append(dict(zip(field_names, [current_type, 0, '', 0, '', 0, sub_total, 0, 1, 1])))
                current_type = values['account_type']
            self._data.append(values)
        if current_type != 0:
            sub_total = sum([row['balance_a'] for row in self._data if row['account_type'] == current_type])
            self._data.append(dict(zip(field_names, [current_type, 0, '', 0, '', 0, sub_total, 0, 1, 1])))
        total_sum = sum([row['balance_a'] for row in self._data if row['level'] == 0])
        self._data.append(dict(zip(field_names, [0, 0, '', 0, '', 0, total_sum, 0, 1, 2])))
        self.modelReset.emit()
