from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlTableModel
from jal.db.helpers import db_connection, executeSQL
from jal.widgets.helpers import g_tr
from jal.constants import BookAccount, PredefinedCategory
from jal.widgets.delegates import FloatDelegate, TimestampDelegate

#-----------------------------------------------------------------------------------------------------------------------
class ProfitLossReportModel(QSqlTableModel):
    def __init__(self, parent_view):
        self._columns = [("period", g_tr("Reports", "Period")),
                         ("transfer", g_tr("Reports", "In / Out")),
                         ("assets", g_tr("Reports", "Assets value")),
                         ("result", g_tr("Reports", "Total result")),
                         ("profit", g_tr("Reports", "Profit / Loss")),
                         ("dividend", g_tr("Reports", "Returns")),
                         ("tax_fee", g_tr("Reports", "Taxes & Fees"))]
        self._view = parent_view
        self._query = None
        self._ym_delegate = None
        self._float_delegate = None
        QSqlTableModel.__init__(self, parent=parent_view, db=db_connection())

    def setColumnNames(self):
        for column in self._columns:
            self.setHeaderData(self.fieldIndex(column[0]), Qt.Horizontal, column[1])

    def resetDelegates(self):
        for column in self._columns:
            self._view.setItemDelegateForColumn(self.fieldIndex(column[0]), None)

    def configureView(self):
        self._view.setModel(self)
        self.setColumnNames()
        self.resetDelegates()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._view.setColumnWidth(self.fieldIndex("period"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._ym_delegate = TimestampDelegate(display_format='%Y %B')
        self._view.setItemDelegateForColumn(self.fieldIndex("period"), self._ym_delegate)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._view.setItemDelegateForColumn(self.fieldIndex("transfer"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("assets"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("result"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("profit"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("dividend"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("tax_fee"), self._float_delegate)

    def prepare(self, begin, end, account_id, group_dates):
        if account_id == 0:
            raise ValueError(g_tr('Reports', "You should select account to create Profit/Loss report"))
        self._query = executeSQL(
            "WITH "
            "_months AS ("
            "SELECT DISTINCT(l.asset_id) AS asset_id, m.m_start AS month, MAX(q.timestamp) AS last_timestamp "
            "FROM ledger AS l "
            "LEFT JOIN "
            "(WITH RECURSIVE months(m_start) AS "
            "( "
            "  VALUES(CAST(strftime('%s', date(:begin, 'unixepoch', 'start of month')) AS INTEGER)) "
            "  UNION ALL "
            "  SELECT CAST(strftime('%s', date(m_start, 'unixepoch', '+1 month')) AS INTEGER) "
            "  FROM months "
            "  WHERE m_start < :end "
            ") "
            "SELECT m_start FROM months) AS m "
            "LEFT JOIN quotes AS q ON q.timestamp<=m.m_start AND q.asset_id=l.asset_id "
            "WHERE l.timestamp>=:begin AND l.timestamp<=:end AND l.account_id=:account_id "
            "GROUP BY m.m_start, l.asset_id "
            "ORDER BY m.m_start, l.asset_id ) "
            "SELECT DISTINCT(m.month) AS period, coalesce(t.transfer, 0) AS transfer, coalesce(a.assets, 0) AS assets, "
            "coalesce(p.result, 0) AS result, coalesce(o.profit, 0) AS profit, coalesce(d.dividend, 0) AS dividend, "
            "coalesce(f.tax_fee, 0) AS tax_fee "
            "FROM _months AS m "
            "LEFT JOIN ( "
            "  SELECT mt.month, SUM(-l.amount) AS transfer "
            "  FROM _months AS mt "
            "  LEFT JOIN ledger AS l ON mt.month = "
            "  CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) "
            "  AND mt.asset_id=l.asset_id "
            "  WHERE l.book_account=:book_transfers AND l.account_id=:account_id GROUP BY mt.month "
            ") AS t ON t.month = m.month "
            "LEFT JOIN ( "
            "  SELECT ma.month, SUM(l.amount*q.quote) AS assets "
            "  FROM _months AS ma "
            "  LEFT JOIN ledger AS l ON l.timestamp<=ma.month AND l.asset_id=ma.asset_id "
            "  LEFT JOIN quotes AS q ON ma.last_timestamp=q.timestamp AND ma.asset_id=q.asset_id "
            "  WHERE l.account_id =:account_id AND (l.book_account=:book_money OR l.book_account=:book_assets) "
            "  GROUP BY ma.month "
            ") AS a ON a.month = m.month "
            "LEFT JOIN ( "
            "  SELECT CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) AS month,"
            "  SUM(-l.amount) as result"
            "  FROM ledger AS l  "
            "  WHERE (l.book_account=:book_costs OR l.book_account=:book_incomes) AND l.account_id=:account_id "
            "  GROUP BY month "
            ") AS p ON p.month = m.month "
            "LEFT JOIN ( "
            "  SELECT CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) "
            "  AS INTEGER) AS month, SUM(-l.amount) as profit "
            "  FROM ledger AS l "
            "  WHERE (l.book_account=:book_costs OR l.book_account=:book_incomes) "
            "  AND category_id=:category_profit AND l.account_id=:account_id "
            "  GROUP BY month "
            ") AS o ON o.month = m.month "
            "LEFT JOIN ( "
            "  SELECT CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) "
            "  AS month, SUM(-l.amount) as dividend "
            "  FROM ledger AS l "
            "  WHERE (l.book_account=:book_costs OR l.book_account=:book_incomes) "
            "  AND (l.category_id=:category_dividend OR l.category_id=:category_interest) AND l.account_id=:account_id "
            "  GROUP BY month "
            ") AS d ON d.month = m.month "
            "LEFT JOIN ( "
            "  SELECT CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) "
            "  AS INTEGER) AS month, SUM(-l.amount) as tax_fee "
            "  FROM ledger AS l "
            "  WHERE l.book_account=:book_costs AND l.category_id<>:category_dividend "
            "AND l.category_id<>:category_interest AND l.account_id=:account_id "
            "  GROUP BY month "
            ") AS f ON f.month = m.month",
            [(":account_id", account_id), (":begin", begin), (":end", end),
             (":book_costs", BookAccount.Costs), (":book_incomes", BookAccount.Incomes),
             (":book_money", BookAccount.Money), (":book_assets", BookAccount.Assets),
             (":book_transfers", BookAccount.Transfers), (":category_profit", PredefinedCategory.Profit),
             (":category_dividend", PredefinedCategory.Dividends), (":category_interest", PredefinedCategory.Interest)],
            forward_only=False)
        self.setQuery(self._query)
        self.modelReset.emit()
