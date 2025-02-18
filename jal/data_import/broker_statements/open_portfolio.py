import re
import json
import logging
from pkg_resources import parse_version
from jal.data_import.statement import FOF, Statement, Statement_ImportError
from jal.constants import PredefinedCategory

JAL_STATEMENT_CLASS = "StatementOpenPortfolio"


MANDATORY = 0
LOADER = 1
# -----------------------------------------------------------------------------------------------------------------------
class StatementOpenPortfolio(Statement):
    COMMODITY_SYMBOLS = ['GLD', 'SLV']
    CURRENCY_CONVERSION = "MOEX_FX"

    def __init__(self):
        super().__init__()
        self.name = self.tr("Investbook / IZI-Invest")
        self.icon_name = "pof.png"
        self.filename_filter = self.tr("Open portfolio (*.json)")

        self._sections = {   # (Mandatory=True/False, Loader)
            "version": (True, self._validate_version),
            "start": (True, self._skip_section),
            "end": (True, self._get_period),
            "generated": (False, self._remove_section),
            "generated-by": (False, self._remove_section),
            "assets": (True, self._load_assets),
            "accounts": (True, self._tweak_accounts),
            "cash-balances": (False, self._remove_section),
            "transfers": (False, self._remove_section),  # should be removed before 'trades' as jal uses the same name
            "payments": (False, self._remove_section),
            "trades": (False, self._load_trades),
            "cash-flows": (False, self._load_income_spending)
        }

    def load(self, filename: str) -> None:
        self._data = {}
        try:
            with open(filename, 'r', encoding='utf-8') as exchange_file:
                try:
                    self._data = json.load(exchange_file)
                except json.JSONDecodeError:
                    logging.error(self.tr("Failed to read JSON from file: ") + filename)
        except Exception as err:
            raise Statement_ImportError(self.tr("Failed to read file: ") + str(err))
        for section in self._sections:
            if section in self._data:
                self._sections[section][LOADER](section)
            else:
                if self._sections[section][MANDATORY]:
                    raise Statement_ImportError(self.tr("Mandatory section is missing: ") + str(section))
        self.strip_unused_data()

    def _skip_section(self, section):
        pass # do nothing

    def _remove_section(self, section):
        self._data.pop(section)

    def _validate_version(self, section):
        version = self._data[section]
        if parse_version(version) > parse_version("1.1.0"):
            raise Statement_ImportError(self.tr("Unsupported version of open portfolio format: ") + version)
        self._data.pop(section)

    def _get_period(self, _section):
        self._data[FOF.PERIOD] = [self._data["start"], self._data["end"]]
        self._data.pop("start")
        self._data.pop("end")

    def _load_assets(self, section):
        symbol_id = 1
        self._data["symbols"] = []
        self._data["assets_data"] = []
        for asset in self._data[section]:
            if "id" not in asset or "type" not in asset:
                raise Statement_ImportError(self.tr("Incomplete asset data: ") + asset)
            if "symbol" in asset:
                if asset['type'] == "fx-contract":
                    self._transform_fx_contract(asset)
                symbol = {"id": symbol_id, "asset": asset['id'], "symbol": asset['symbol'], "note": asset['exchange']}
                if asset['type'] != FOF.ASSET_MONEY:
                    symbol['currency'] = self.currency_id('RUB')
                self._data["symbols"].append(symbol)
                asset.pop("symbol")
                asset.pop("exchange")
                symbol_id += 1
            else:
                logging.warning(self.tr("Asset without symbol was skipped: ") + asset)

    # Corrects asset data for fx-contract: it is either transformed into commodity (for gold, silver), or
    # converted into simple currency (that will be tracked for an account)
    def _transform_fx_contract(self, asset: dict):
        parts = re.match(r"^(?P<dst>\w{3})(?P<src>\w{3})_(?P<set>TO[D|M])$", asset['name'], re.IGNORECASE)
        if parts is None:
            raise Statement_ImportError(self.tr("Can't parse fx-contract name ") + f'{asset}')
        contract = parts.groupdict()
        if len(contract) != 3:
            raise Statement_ImportError(self.tr("FX-contract description incomplete ") + f'{asset}')
        if contract['src'] != 'RUB':
            raise Statement_ImportError(self.tr("Can't import fx-contract with base currency not RUB"))
        if contract['dst'] in self.COMMODITY_SYMBOLS:
            asset['type'] = FOF.ASSET_COMMODITY
        else:
            asset['type'] = self.CURRENCY_CONVERSION
            asset['symbol'] = asset['name'] = contract['dst']
            asset['exchange'] = ''
            asset['TOM'] = True if contract['set'] == 'TOM' else False

    # Account section is mainly the same as internal JAL format, but some fields should be renamed and re-assigned.
    def _tweak_accounts(self, section):
        account_number = 1
        for account in self._data[section]:
            currency = [x for x in self._data["symbols"] if x["symbol"] == account["valuation-currency"]][0]
            account['currency'] = currency['asset']
            if "number" not in account:
                account["number"] = self.tr("Imported #") + str(account_number)
                account_number += 1
            account.pop("valuation-currency")
            account.pop("valuation")

    def _load_trades(self, section):
        self._data[FOF.TRANSFERS] = []  # Add section for transfers between accounts
        for trade in self._data[section]:
            asset = self._asset(trade['asset'])
            if asset['type'] == self.CURRENCY_CONVERSION:
                new_id = max([0] + [x['id'] for x in self._data[FOF.TRANSFERS]]) + 1
                account = self._find_in_list(self._data[FOF.ACCOUNTS], 'id', trade['account'])
                currency_symbol = self._find_in_list(self._data[FOF.SYMBOLS], 'asset', asset['id'])
                account_from = self._find_account_id(account['number'], trade['currency'])
                account_to = self._find_account_id(account['number'], currency_symbol['symbol'])
                account_fee = self._find_account_id(account['number'], trade['fee-currency'])
                transfer = {"id": new_id, "account": [account_from, account_to, account_fee], "number": trade['trade-id'],
                            "asset": [self.currency_id('RUB'), self.currency_id(currency_symbol['symbol'])],
                            "timestamp": trade['timestamp'],
                            "withdrawal": abs(trade['summa']), "deposit": abs(trade['count']), "fee": abs(trade['fee']),
                            "description": trade['description']}
                self._data[FOF.TRANSFERS].append(transfer)
            else:  # Create trade
                trade["number"] = trade["trade-id"]
                trade["quantity"] = trade["count"]
                trade["note"] = trade["description"]
                if "settlement" not in trade:
                    trade["settlement"] = 0  # TODO Check, probably need to put "timestamp" instead
                trade.pop("trade-id")
                trade.pop("count")
                trade.pop("description")
                trade.pop("summa")
                trade.pop("accrued-interest")  # FIXME - should be loaded as asset payment
                trade.pop("currency")
                trade.pop("fee-currency")

    def _load_income_spending(self, section):
        categories = {
            'fee': PredefinedCategory.Fees,
            'other': PredefinedCategory.Income
        }
        for operation in self._data[section]:
            operation["peer"] = 0
            try:
                category = -categories[operation["type"]]
            except KeyError:
                category = -PredefinedCategory.Income
            operation["lines"] = [{"amount": operation["amount"], "category": category,
                                   "description": operation["description"]}]
            operation.pop("flow-id")
            operation.pop("currency")  # FIXME - need to check that currency is valid for the account
            operation.pop("amount")
            operation.pop("description")
            operation.pop("type")
        self._data["income_spending"] = self._data[section]
        self._data.pop(section)

        # Drop any unused data that shouldn't be in output json
    def strip_unused_data(self):
        fx_conversions = [x['id'] for x in self._data[FOF.ASSETS] if x['type'] == self.CURRENCY_CONVERSION]
        for asset_id in fx_conversions:
            self.remove_asset(asset_id)
