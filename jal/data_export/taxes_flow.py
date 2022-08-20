from datetime import datetime, timezone
from decimal import Decimal

from jal.constants import BookAccount
from jal.db.operations import LedgerTransaction
from jal.db.helpers import readSQLrecord, executeSQL
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.data_export.dlsg import DLSG


COUNTRY_NA_ID = 0
COUNTRY_RUSSIA_ID = 1

class TaxesFlowRus:
    def __init__(self):
        self.year_begin = 0
        self.year_end = 0
        self.flows = {}

    def prepare_flow_report(self, year):
        self.flows = {}
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())

        # collect data for period start
        accounts = JalAccount.get_all_accounts(active_only=False)
        values = []
        for account in accounts:
            if account.country() == COUNTRY_NA_ID or account.country() == COUNTRY_RUSSIA_ID:
                continue
            assets = account.assets_list(self.year_begin)
            assets_value = Decimal('0')
            for asset_data in assets:
                assets_value += asset_data['amount'] * asset_data['asset'].quote(self.year_begin, account.currency())[1]
            if assets_value != Decimal('0'):
                values.append({
                    'account': account.number(),
                    'currency': JalAsset(account.currency()).symbol(),
                    'is_currency': False,
                    'value': assets_value
                })
            money = account.get_asset_amount(self.year_begin, account.currency())
            if money != Decimal('0'):
                values.append({
                    'account': account.number(),
                    'currency': JalAsset(account.currency()).symbol(),
                    'is_currency': True,
                    'value': money
                })
        values = sorted(values, key=lambda x: (x['account'], x['is_currency'], x['currency']))
        for item in values:
            self.append_flow_values(item, "begin")

        # collect data for period end
        JalDB().set_view_param("last_quotes", "timestamp", int, self.year_end)
        JalDB().set_view_param("last_assets", "timestamp", int, self.year_end)
        query = executeSQL(
            "SELECT a.number AS account, c.symbol AS currency, h.currency_id=h.asset_id AS is_currency, "
            "SUM(h.qty*h.quote) AS value "
            "FROM last_assets h "
            "LEFT JOIN accounts a ON h.account_id=a.id "
            "LEFT JOIN currencies c ON h.currency_id=c.id "
            "WHERE h.qty != 0 AND a.country_id > 1 "
            "GROUP BY account, currency, is_currency "
            "ORDER BY account, is_currency, currency")
        while query.next():
            values = readSQLrecord(query, named=True)
            self.append_flow_values(values, "end")

        # collect money ins/outs
        query = executeSQL("SELECT a.number AS account, c.symbol AS currency, 1 AS is_currency, SUM(l.amount) AS value "
                           "FROM accounts a "
                           "LEFT JOIN currencies c ON a.currency_id=c.id "
                           "LEFT JOIN ledger l ON l.account_id=a.id AND (l.book_account=:money OR l.book_account=:debt) "
                           "AND l.timestamp>=:begin AND l.timestamp<=:end "
                           "WHERE a.country_id>1 AND l.amount>0 "
                           "GROUP BY l.account_id", [(":money", BookAccount.Money), (":debt", BookAccount.Liabilities),
                                                     (":begin", self.year_begin), (":end", self.year_end)])
        while query.next():
            values = readSQLrecord(query, named=True)
            self.append_flow_values(values, "in")
        query = executeSQL("SELECT a.number AS account, c.symbol AS currency, 1 AS is_currency, SUM(-l.amount) AS value "
                           "FROM accounts a "
                           "LEFT JOIN currencies c ON a.currency_id=c.id "
                           "LEFT JOIN ledger l ON l.account_id=a.id AND (l.book_account=:money OR l.book_account=:debt) "
                           "AND l.timestamp>=:begin AND l.timestamp<=:end "
                           "WHERE a.country_id>1 AND l.amount<0 "
                           "GROUP BY l.account_id", [(":money", BookAccount.Money), (":debt", BookAccount.Liabilities),
                                                     (":begin", self.year_begin), (":end", self.year_end)])
        while query.next():
            values = readSQLrecord(query, named=True)
            self.append_flow_values(values, "out")

        # collect assets ins/outs
        query = executeSQL("SELECT a.number AS account, c.symbol AS currency, 0 AS is_currency, SUM(l.value) AS value "
                           "FROM accounts a "
                           "LEFT JOIN currencies c ON a.currency_id=c.id "
                           "LEFT JOIN ledger l ON l.account_id=a.id AND l.book_account=:assets AND l.op_type!=:ca "
                           "AND l.timestamp>=:begin AND l.timestamp<=:end "
                           "WHERE a.country_id>1 AND l.value>0 "
                           "GROUP BY l.account_id",
                           [(":assets", BookAccount.Assets), (":ca", LedgerTransaction.CorporateAction),
                            (":begin", self.year_begin), (":end", self.year_end)])
        while query.next():
            values = readSQLrecord(query, named=True)
            self.append_flow_values(values, "in")
        query = executeSQL("SELECT a.number AS account, c.symbol AS currency, 0 AS is_currency, SUM(-l.value) AS value "
                           "FROM accounts a "
                           "LEFT JOIN currencies c ON a.currency_id=c.id "
                           "LEFT JOIN ledger l ON l.account_id=a.id AND l.book_account=:assets AND l.op_type!=:ca "
                           "AND l.timestamp>=:begin AND l.timestamp<=:end "
                           "WHERE a.country_id>1 AND l.value<0 "
                           "GROUP BY l.account_id",
                           [(":assets", BookAccount.Assets), (":ca", LedgerTransaction.CorporateAction),
                            (":begin", self.year_begin), (":end", self.year_end)])
        while query.next():
            values = readSQLrecord(query, named=True)
            self.append_flow_values(values, "out")

        report = []
        for account in self.flows:
            for currency in self.flows[account]:
                record = self.flows[account][currency]
                row = {'report_template': "account_lines",
                       'account': account,
                       'currency': f"{currency} ({record['code']})",
                       'money': "Денежные средства",
                       'assets': "Финансовые активы"}
                for dtype in ['money', 'assets']:
                    for key in ['begin', 'in', 'out', 'end']:
                        param = f"{dtype}_{key}"
                        try:
                            row[param] = float(record[dtype][key]) / 1000.0   ######
                        except KeyError:
                            row[param] = 0.0
                report.append(row)
        return report

    # values are dictionary with keys {'account', 'currency', 'is_currency', 'value'}
    # this method puts it into self.flows array that has another structure:
    # { account: {currency: {0: {'value+suffix': X.XX}}, 1: {'value+suffix': SUM(X.XX)} } } }
    def append_flow_values(self, values, name):
        account = values['account']
        try:
            f_account = self.flows[account]
        except KeyError:
            f_account = self.flows[account] = {}
        currency = values['currency']
        try:
            f_currency = f_account[currency]
        except KeyError:
            try:
                currency_code = DLSG.currencies[currency]['code']
            except KeyError:
                currency_code = 'XXX'  # currency code isn't known
            f_currency = f_account[currency] = {'money': {}, 'assets': {}, 'code': currency_code}
        if values['is_currency'] == 0:
            try:
                f_currency['assets'][name] += values['value']
            except KeyError:
                f_currency['assets'][name] = values['value']
        else:                 # addition isn't required below as there should be only one value for money
            f_currency['money'][name] = values['value']
