import pandas as pd
from PySide2.QtWidgets import QFileDialog, QHeaderView
from PySide2.QtCore import QObject, Signal, QAbstractTableModel
from PySide2.QtSql import QSqlTableModel
from jal.constants import BookAccount, PredefinedAsset, PredefinedCategory
from jal.widgets.view_delegate import *
from jal.db.helpers import db_connection, executeSQL, readSQLrecord
from jal.ui_custom.helpers import g_tr
from jal.reports.helpers import XLSX


TREE_LEVEL_SEPARATOR = chr(127)


class ReportType:
    IncomeSpending = 1
    ProfitLoss = 2
    Deals = 3
    ByCategory = 4


#-----------------------------------------------------------------------------------------------------------------------
class PandasModel(QAbstractTableModel):
    CATEGORY_INTEND = "  "

    def __init__(self, data):
        QAbstractTableModel.__init__(self)
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1] + 1    # +1 as extra leftmost column serves as a category header

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                if index.column() == 0:
                    row_header = str(self._data.index[index.row()])
                    level = row_header.count(TREE_LEVEL_SEPARATOR)
                    if level > 0:
                        row_header = row_header.rsplit(TREE_LEVEL_SEPARATOR, 1)[1]
                    for i in range(level):
                        row_header = self.CATEGORY_INTEND + row_header
                    return row_header
                else:
                    return self._data.iloc[index.row(), index.column() - 1]
        return None

    def headerData(self, col, orientation, role=Qt.DisplayRole):
        if (orientation == Qt.Horizontal and role == Qt.DisplayRole):
            if col == 0:        # Leftmost column serves as a category header
                return None
            if col == self._data.shape[1]:   # Rightmost total header
                return str(self._data.columns[col-1][1])
            col_date = datetime(year=int(self._data.columns[col-1][1]), month=int(self._data.columns[col-1][2]), day=1)
            return col_date.strftime("%Y %b")
        return None


#-----------------------------------------------------------------------------------------------------------------------
class ProfitLossReportModel(QSqlTableModel):
    def __init__(self, query, parent_view):
        self._columns = [("period", g_tr("Reports", "Period")),
                         ("transfer", g_tr("Reports", "In / Out")),
                         ("assets", g_tr("Reports", "Assets value")),
                         ("result", g_tr("Reports", "Total result")),
                         ("profit", g_tr("Reports", "Profit / Loss")),
                         ("dividend", g_tr("Reports", "Returns")),
                         ("tax_fee", g_tr("Reports", "Taxes & Fees"))]
        self._view = parent_view
        self._ym_delegate = None
        self._float_delegate = None
        QSqlTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setQuery(query)

    def setColumnNames(self):
        for column in self._columns:
            self.setHeaderData(self.fieldIndex(column[0]), Qt.Horizontal, column[1])

    def configureView(self):
        self._view.setModel(self)
        self.setColumnNames()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._view.setColumnWidth(self.fieldIndex("period"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._ym_delegate = ReportsYearMonthDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("period"), self._ym_delegate)
        self._float_delegate = ReportsFloat2Delegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("transfer"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("assets"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("result"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("profit"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("dividend"), self._float_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("tax_fee"), self._float_delegate)


#-----------------------------------------------------------------------------------------------------------------------
class DealsReportModel(QSqlTableModel):
    def __init__(self, query, parent_view):
        self._columns = [("asset", g_tr("Reports", "Asset")),
                         ("open_timestamp", g_tr("Reports", "Open Date")),
                         ("close_timestamp", g_tr("Reports", "Close Date")),
                         ("open_price", g_tr("Reports", "Open Price")),
                         ("close_price", g_tr("Reports", "Close Price")),
                         ("qty", g_tr("Reports", "Qty")),
                         ("corp_action", g_tr("Reports", "Note"))]
        self._view = parent_view
        self._timestamp_delegate = None
        self._float_delegate = None
        self._float2_delegate = None
        self._float4_delegate = None
        self._profit_delegate = None
        self._ca_delegate = None
        QSqlTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setQuery(query)

    def setColumnNames(self):
        for column in self._columns:
            self.setHeaderData(self.fieldIndex(column[0]), Qt.Horizontal, column[1])

    def configureView(self):
        self._view.setModel(self)
        self.setColumnNames()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._view.setColumnWidth(self.fieldIndex("asset"), 300)
        self._view.setColumnWidth(self.fieldIndex("corp_action"), 200)
        self._view.setColumnWidth(self.fieldIndex("open_timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("close_timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._timestamp_delegate = ReportsTimestampDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("open_timestamp"), self._timestamp_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("close_timestamp"), self._timestamp_delegate)
        self._float_delegate = ReportsFloat2Delegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("qty"), self._float_delegate)
        self._float2_delegate = ReportsFloat2Delegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("fee"), self._float2_delegate)
        self._float4_delegate = ReportsFloat2Delegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("open_price"), self._float4_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("close_price"), self._float4_delegate)
        self._profit_delegate = ReportsProfitDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("profit"), self._profit_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("rel_profit"), self._profit_delegate)
        self._ca_delegate = ReportsCorpActionDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("corp_action"), self._ca_delegate)


#-----------------------------------------------------------------------------------------------------------------------
class CategoryReportModel(QSqlTableModel):
    def __init__(self, query, parent_view):
        self._columns = [("timestamp", g_tr("Reports", "Timestamp")),
                         ("account", g_tr("Reports", "Account")),
                         ("name", g_tr("Reports", "Peer Name")),
                         ("sum", g_tr("Reports", "Amount")),
                         ("note", g_tr("Reports", "Note"))]
        self._view = parent_view
        self._timestamp_delegate = None
        self._float_delegate = None
        QSqlTableModel.__init__(self, parent=parent_view, db=db_connection())
        self.setQuery(query)

    def setColumnNames(self):
        for column in self._columns:
            self.setHeaderData(self.fieldIndex(column[0]), Qt.Horizontal, column[1])

    def configureView(self):
        self._view.setModel(self)
        self.setColumnNames()
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._view.horizontalHeader().setSectionResizeMode(self.fieldIndex("note"), QHeaderView.Stretch)
        self._view.setColumnWidth(self.fieldIndex("account"), 200)
        self._view.setColumnWidth(self.fieldIndex("name"), 200)
        self._view.setColumnWidth(self.fieldIndex("sum"), 200)
        self._view.setColumnWidth(self.fieldIndex("timestamp"),
                                  self._view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self._timestamp_delegate = ReportsTimestampDelegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("timestamp"), self._timestamp_delegate)
        self._float_delegate = ReportsFloat2Delegate()
        self._view.setItemDelegateForColumn(self.fieldIndex("sum"), self._float_delegate)


#-----------------------------------------------------------------------------------------------------------------------
PREPARE_REPORT_QUERY = 0
SHOW_REPORT = 1

class Reports(QObject):
    report_failure = Signal(str)

    def __init__(self, report_table_view):
        super().__init__()

        self.table_view = report_table_view
        self.delegates = []
        self.current_report = None
        self.query = None
        self.dataframe = None
        self.model = None

        self.reports = {
            ReportType.IncomeSpending: (self.prepareIncomeSpendingReport,
                                        self.showPandasReport),
            ReportType.ProfitLoss: (self.prepareProfitLossReport,
                                    self.showProfitLossReport),
            ReportType.Deals: (self.prepareDealsReport,
                               self.showDealsReport),
            ReportType.ByCategory: (self.prepareCategoryReport,
                                    self.showByCategoryReport)
        }

    def runReport(self, report_type, begin=0, end=0, account_id=0, group_dates=0):
        if self.reports[report_type][PREPARE_REPORT_QUERY](begin, end, account_id, group_dates):
            self.reports[report_type][SHOW_REPORT]()

    def showProfitLossReport(self):
        self.model = ProfitLossReportModel(self.query, self.table_view)
        self.model.configureView()
        self.model.select()

    def showDealsReport(self):
        self.model = DealsReportModel(self.query, self.table_view)
        self.model.configureView()
        self.model.select()

    def showByCategoryReport(self):
        self.model = CategoryReportModel(self.query, self.table_view)
        self.model.configureView()
        self.model.select()

    def showPandasReport(self):
        self.model = PandasModel(self.dataframe)
        self.table_view.setModel(self.model)
        self.delegates = []
        for column in range(self.model.columnCount()):
            if column == 0:
                self.table_view.setColumnWidth(column, 300)
            else:
                self.table_view.setColumnWidth(column, 100)
            self.delegates.append(ReportsPandasDelegate(self.table_view))
            self.table_view.setItemDelegateForColumn(column, self.delegates[-1])
        font = self.table_view.horizontalHeader().font()
        font.setBold(True)
        self.table_view.horizontalHeader().setFont(font)
        self.table_view.show()

    def saveReport(self):
        filename, filter = QFileDialog.getSaveFileName(None, g_tr('Reports', "Save report to:"),
                                                       ".", g_tr('Reports', "Excel files (*.xlsx)"))
        if filename:
            if filter == g_tr('Reports', "Excel files (*.xlsx)") and filename[-5:] != '.xlsx':
                filename = filename + '.xlsx'
        else:
            return

        report = XLSX(filename)
        sheet = report.add_report_sheet(g_tr('Reports', "Report"))

        model = self.table_view.model()
        headers = {}
        for col in range(model.columnCount()):
            headers[col] = (model.headerData(col, Qt.Horizontal), report.formats.ColumnHeader())
        report.write_row(sheet, 0, headers)

        for row in range(model.rowCount()):
            data_row = {}
            for col in range(model.columnCount()):
                data_row[col] = (model.data(model.index(row, col)), report.formats.Text(row))
            report.write_row(sheet, row+1, data_row)

        report.save()

    def prepareIncomeSpendingReport(self, begin, end, account_id, group_dates):
        _ = executeSQL("DELETE FROM t_months")
        _ = executeSQL("DELETE FROM t_pivot")
        _ = executeSQL("INSERT INTO t_months (month, asset_id, last_timestamp) "
                       "SELECT strftime('%s', datetime(timestamp, 'unixepoch', 'start of month') ) "
                       "AS month, asset_id, MAX(timestamp) AS last_timestamp "
                       "FROM quotes AS q "
                       "LEFT JOIN assets AS a ON q.asset_id=a.id "
                       "WHERE a.type_id=:asset_money "
                       "GROUP BY month, asset_id",
                       [(":asset_money", PredefinedAsset.Money)])
        _ = executeSQL(
            "INSERT INTO t_pivot (row_key, col_key, value) "
            "SELECT strftime('%s', datetime(t.timestamp, 'unixepoch', 'start of month') ) AS row_key, "
            "t.category_id AS col_key, sum(-t.amount * coalesce(q.quote, 1)) AS value "
            "FROM ledger AS t "
            "LEFT JOIN t_months AS d ON row_key = d.month AND t.asset_id = d.asset_id "
            "LEFT JOIN quotes AS q ON d.last_timestamp = q.timestamp AND t.asset_id = q.asset_id "
            "WHERE (t.book_account=:book_costs OR t.book_account=:book_incomes) "
            "AND t.timestamp>=:begin AND t.timestamp<=:end "
            "GROUP BY row_key, col_key",
            [(":book_costs", BookAccount.Costs), (":book_incomes", BookAccount.Incomes),
             (":begin", begin), (":end", end)], commit=True)
        self.query = executeSQL("SELECT c.id AS id, c.level AS level, c.path AS category, "
                                "strftime('%Y', datetime(p.row_key, 'unixepoch')) AS year, "
                                "strftime('%m', datetime(p.row_key, 'unixepoch')) AS month, p.value AS value "
                                "FROM categories_tree AS c "
                                "LEFT JOIN t_pivot AS p ON p.col_key=c.id "
                                "ORDER BY c.path, year, month")
        table = []
        while self.query.next():
            record = readSQLrecord(self.query, named=True)
            turnover = record['value'] if record['value'] != '' else 0
            table.append({
                'category': record['category'],
                'Y': record['year'],
                'M': record['month'],
                'turnover': turnover
            })
        data = pd.DataFrame(table)
        data = pd.pivot_table(data, index=['category'], columns=['Y', 'M'], values=['turnover'],
                              aggfunc=sum, fill_value=0.0, margins=True, margins_name=g_tr('Reports', "TOTAL"))
        if data.columns[0][1] == '':   # if some categories have no data and we have null 1st column
            data = data.drop(columns=[data.columns[0]])
        # Calculate sub-totals from bottom to top
        totals = {}
        prev_level = 0
        for index, row in data[::-1].iterrows():
            if index == g_tr('Reports', "TOTAL"):
                continue
            level = index.count(TREE_LEVEL_SEPARATOR)
            if level > prev_level:
                totals[level] = row['turnover']
                prev_level = level
            elif level == prev_level:
                try:
                    totals[level] = totals[level] + row['turnover']
                except KeyError:
                    totals[level] = row['turnover']
            elif level < prev_level:
                try:
                    totals[level] = totals[level] + totals[prev_level] + row['turnover']
                except KeyError:
                    totals[level] = totals[prev_level] + row['turnover']
                sub_total = totals.pop(prev_level, None)
                data.loc[index, :] = sub_total.values
                prev_level = level
        self.dataframe = data
        return True

    def prepareDealsReport(self, begin, end, account_id, group_dates):
        if account_id == 0:
            self.report_failure.emit(g_tr('Reports', "You should select account to create Deals report"))
            return False
        if group_dates == 1:
            self.query = executeSQL(
                               "SELECT asset, "
                               "strftime('%s', datetime(open_timestamp, 'unixepoch', 'start of day')) as open_timestamp, "
                               "strftime('%s', datetime(close_timestamp, 'unixepoch', 'start of day')) as close_timestamp, "
                               "SUM(open_price*qty)/SUM(qty) as open_price, SUM(close_price*qty)/SUM(qty) AS close_price, "
                               "SUM(qty) as qty, SUM(fee) as fee, SUM(profit) as profit, "
                               "coalesce(100*SUM(qty*(close_price-open_price)-fee)/SUM(qty*open_price), 0) AS rel_profit "
                               "FROM deals_ext "
                               "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end "
                               "GROUP BY asset, open_timestamp, close_timestamp "
                               "ORDER BY close_timestamp, open_timestamp",
                               [(":account_id", account_id), (":begin", begin), (":end", end)], forward_only=False)
        else:
            self.query = executeSQL("SELECT asset, open_timestamp, close_timestamp, open_price, close_price, "
                                    "qty, fee, profit, rel_profit, corp_action FROM deals_ext "
                                    "WHERE account_id=:account_id AND close_timestamp>=:begin AND close_timestamp<=:end "
                                    "ORDER BY close_timestamp, open_timestamp",
                                    [(":account_id", account_id), (":begin", begin), (":end", end)], forward_only=False)
        return True

    def prepareProfitLossReport(self, begin, end, account_id, group_dates):
        if account_id == 0:
            self.report_failure.emit(g_tr('Reports', "You should select account to create Profit/Loss report"))
            return False
        _ = executeSQL("DELETE FROM t_months")
        _ = executeSQL("INSERT INTO t_months(asset_id, month, last_timestamp) "
                       "SELECT DISTINCT(l.asset_id) AS asset_id, m.m_start, MAX(q.timestamp) AS last_timestamp "
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
                       "ORDER BY m.m_start, l.asset_id",
                       [(":account_id", account_id), (":begin", begin), (":end", end)], commit=True)
        self.query = executeSQL(
            "SELECT DISTINCT(m.month) AS period, coalesce(t.transfer, 0) AS transfer, coalesce(a.assets, 0) AS assets, "
            "coalesce(p.result, 0) AS result, coalesce(o.profit, 0) AS profit, coalesce(d.dividend, 0) AS dividend, "
            "coalesce(f.tax_fee, 0) AS tax_fee "
            "FROM t_months AS m "
            "LEFT JOIN ( "
            "  SELECT mt.month, SUM(-l.amount) AS transfer "
            "  FROM t_months AS mt "
            "  LEFT JOIN ledger AS l ON mt.month = "
            "  CAST(strftime('%s', date(l.timestamp, 'unixepoch', 'start of month')) AS INTEGER) "
            "  AND mt.asset_id=l.asset_id "
            "  WHERE l.book_account=:book_transfers AND l.account_id=:account_id GROUP BY mt.month "
            ") AS t ON t.month = m.month "
            "LEFT JOIN ( "
            "  SELECT ma.month, SUM(l.amount*q.quote) AS assets "
            "  FROM t_months AS ma "
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
            "  WHERE l.book_account=:book_costs AND l.category_id<>7 AND l.category_id<>8 AND l.account_id=:account_id "
            "  GROUP BY month "
            ") AS f ON f.month = m.month",
            [(":account_id", account_id), (":book_costs", BookAccount.Costs), (":book_incomes", BookAccount.Incomes),
             (":book_money", BookAccount.Money), (":book_assets", BookAccount.Assets),
             (":book_transfers", BookAccount.Transfers), (":category_profit", PredefinedCategory.Profit),
             (":category_dividend", PredefinedCategory.Dividends), (":category_interest", PredefinedCategory.Interest)],
                           forward_only=False)
        return True

    def prepareCategoryReport(self, begin, end, category_id, group_dates):
        if category_id == 0:
            self.report_failure.emit(g_tr('Reports', "You should select category to create By Category report"))
            return False
        self.query = executeSQL("SELECT a.timestamp, ac.name AS account, p.name, d.sum, d.note "
                                "FROM actions AS a "
                                "LEFT JOIN action_details AS d ON d.pid=a.id "
                                "LEFT JOIN agents AS p ON p.id=a.peer_id "
                                "LEFT JOIN accounts AS ac ON ac.id=a.account_id "
                                "WHERE a.timestamp>=:begin AND a.timestamp<=:end "
                                "AND d.category_id=:category_id",
                                [(":category_id", category_id), (":begin", begin), (":end", end)], forward_only=False)
        return True
