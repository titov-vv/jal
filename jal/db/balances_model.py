from PySide6.QtCore import Qt, Slot, QAbstractTableModel, QDate
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QHeaderView
from jal.constants import Setup, CustomColor, BookAccount, PredefindedAccountType
from jal.db.helpers import executeSQL, readSQLrecord
from jal.db.db import JalDB
from jal.db.settings import JalSettings


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

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
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
                return PredefindedAccountType().get_name(self._data[row]['account_type'], default=self.tr("Total"))
        elif column == 1:
            return f"{self._data[row]['balance']:,.2f}" if self._data[row]['balance'] != 0 else ''
        elif column == 2:
            return self._data[row]['currency_name'] if self._data[row]['balance'] != 0 else ''
        elif column == 3:
            return f"{self._data[row]['balance_a']:,.2f}" if self._data[row]['balance_a'] != 0 else ''
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

    @Slot()
    def setCurrency(self, currency_id):
        if self._currency != currency_id:
            self._currency = currency_id
            self._currency_name = JalDB().get_asset_name(currency_id)
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
        JalDB().set_view_param("last_quotes", "timestamp", int, self._date)

        query = executeSQL(
            "WITH "
            "_last_dates AS (SELECT account_id AS ref_id, MAX(timestamp) AS timestamp "
            "FROM ledger WHERE timestamp <= :balances_timestamp GROUP BY ref_id) "
            "SELECT a.type_id AS account_type, l.account_id AS account, "
            "a.name AS account_name, a.currency_id AS currency, c.symbol AS currency_name, "
            "SUM(CASE WHEN l.book_account=:assets_book THEN l.amount*q.quote ELSE l.amount END) AS balance, "
            "SUM(CASE WHEN l.book_account=:assets_book THEN l.amount*coalesce(q.quote*r.quote/ra.quote, 0) "
            "ELSE l.amount*coalesce(r.quote/ra.quote, 0) END) AS balance_a, "
            "(d.timestamp - coalesce(a.reconciled_on, 0))/86400 AS unreconciled, "
            "a.active AS active "
            "FROM ledger AS l "
            "LEFT JOIN accounts AS a ON l.account_id = a.id "
            "LEFT JOIN assets_ext AS c ON c.id = a.currency_id AND c.currency_id = :base_currency "
            "LEFT JOIN last_quotes AS q ON l.asset_id = q.asset_id AND q.currency_id = a.currency_id "
            "LEFT JOIN last_quotes AS r ON a.currency_id = r.asset_id AND r.currency_id = :base_currency "
            "LEFT JOIN last_quotes AS ra ON ra.asset_id = :currency AND ra.currency_id = :base_currency "
            "LEFT JOIN _last_dates AS d ON l.account_id = d.ref_id "
            "WHERE (book_account=:money_book OR book_account=:assets_book OR book_account=:liabilities_book) "
            "AND l.timestamp <= :balances_timestamp "
            "GROUP BY l.account_id "
            "HAVING ABS(balance)>:tolerance "
            "ORDER BY account_type",
            [(":currency", self._currency), (":money_book", BookAccount.Money),
             (":assets_book", BookAccount.Assets), (":liabilities_book", BookAccount.Liabilities),
             (":balances_timestamp", self._date), (":tolerance", Setup.DISP_TOLERANCE),
             (":base_currency", JalSettings().getValue('BaseCurrency'))], forward_only=True)
        self._data = []
        current_type = 0
        field_names = list(map(query.record().fieldName, range(query.record().count()))) + ['level']
        while query.next():
            values = readSQLrecord(query, named=True)
            values['level'] = 0
            if self._active_only and (values['active'] == 0):
                continue
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
