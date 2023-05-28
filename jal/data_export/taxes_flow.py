from datetime import datetime, timezone
from decimal import Decimal

from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.data_export.dlsg import DLSG


class TaxesFlowRus:
    def __init__(self):
        self.year_begin = 0
        self.year_end = 0
        self.flows = {}

    def get_account_values(self, account, date):
        values = []
        assets = account.assets_list(date)
        assets_value = Decimal('0')
        for asset_data in assets:
            assets_value += asset_data['amount'] * asset_data['asset'].quote(date, account.currency())[1]
        if assets_value != Decimal('0'):
            values.append({'account': account.id(), 'currency': JalAsset(account.currency()).symbol(),
                           'is_currency': False, 'value': assets_value})
        money = account.get_asset_amount(date, account.currency())
        if money != Decimal('0'):
            values.append({'account': account.id(),'currency': JalAsset(account.currency()).symbol(),
                           'is_currency': True, 'value': money})
        return values

    def prepare_flow_report(self, year):
        self.flows = {}
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())

        accounts = JalAccount.get_all_accounts(active_only=False)
        # collect data for start and end of the period
        values_begin = []
        values_end = []
        for account in accounts:
            if account.country().code() == 'xx' or account.country().code() == 'ru':
                continue
            values_begin += self.get_account_values(account, self.year_begin)
            values_end += self.get_account_values(account, self.year_end)
        values_begin = sorted(values_begin, key=lambda x: (JalAccount(account_id=x['account']).number(), x['is_currency'], x['currency']))
        values_end = sorted(values_end, key=lambda x: (JalAccount(account_id=x['account']).number(), x['is_currency'], x['currency']))
        for item in values_begin:
            self.append_flow_values(item, "begin")
        for item in values_end:
            self.append_flow_values(item, "end")

        # collect money and assets ins/outs
        flows = [
            {'type': JalAccount.MONEY_FLOW, 'direction': 'in'},
            {'type': JalAccount.MONEY_FLOW, 'direction': 'out'},
            {'type': JalAccount.ASSETS_FLOW, 'direction': 'in'},
            {'type': JalAccount.ASSETS_FLOW, 'direction': 'out'}
        ]
        for account in accounts:
            if account.country().code() == 'xx' or account.country().code() == 'ru':
                continue
            for flow in flows:
                value = account.get_flow(self.year_begin, self.year_end, flow['type'], flow['direction'])
                if value != Decimal('0'):
                    values = {'account': account.id(), 'currency': JalAsset(account.currency()).symbol(),
                              'is_currency': (flow['type'] == JalAccount.MONEY_FLOW), 'value': value}
                    self.append_flow_values(values, flow['direction'])

        report = []
        for account_id in self.flows:
            for currency in self.flows[account_id]:
                account = JalAccount(account_id=account_id)
                record = self.flows[account_id][currency]
                row = {'report_template': "account_lines",
                       'account': account.number(),
                       'account_name': account.name(),
                       'currency': f"{currency} ({record['code']})",
                       'money': "Денежные средства",
                       'assets': "Финансовые активы"}
                for dtype in ['money', 'assets']:
                    for key in ['begin', 'in', 'out', 'end']:
                        param = f"{dtype}_{key}"
                        try:
                            row[param] = record[dtype][key] / Decimal('1000')
                        except KeyError:
                            row[param] = Decimal('0')
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
