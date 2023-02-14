import json
import logging
from pkg_resources import parse_version
from jal.data_import.statement import FOF, Statement, Statement_ImportError
from jal.constants import PredefinedCategory, PredefinedAsset
from jal.db.asset import JalAsset

JAL_STATEMENT_CLASS = "StatementOpenPortfolio"


MANDATORY = 0
LOADER = 1
# -----------------------------------------------------------------------------------------------------------------------
class StatementOpenPortfolio(Statement):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Investbook / IZI-Invest")
        self.icon_name = "open_portfolio.png"
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
            "transfers": (False, self._remove_section),
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
            if "id" not in asset:
                raise Statement_ImportError(self.tr("Asset without id: ") + asset)
            if "symbol" in asset:
                symbol = {"id": symbol_id, "asset": asset['id'], "symbol": asset['symbol'], "note": asset['exchange']}
                if asset['type'] != FOF.ASSET_MONEY:
                    symbol['currency'] = -JalAsset(data={'symbol': 'RUB', 'type_id': PredefinedAsset.Money},
                                                   search=True, create=False).id()
                self._data["symbols"].append(symbol)
                asset.pop("symbol")
                asset.pop("exchange")
                symbol_id += 1

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
        for trade in self._data[section]:
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
