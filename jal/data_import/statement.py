import json

import sys
import logging
from datetime import datetime, timezone
from decimal import Decimal
from copy import deepcopy
from collections import defaultdict

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox
from jal.constants import Setup, AssetLocation, PredefinedAsset, PredefinedAgents, SymbolId
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import normalize_address, JalTokenBlacklist
from jal.db.operations import LedgerTransaction, AssetPayment, CorporateAction
from jal.widgets.helpers import ts2d
from jal.widgets.account_select import SelectAccountDialog
from jal.widgets.token_select import SelectTokenActionDialog
from jal.net.moex import MOEX


# JAL Statement Format - internal JSON representation of a statement that parsers produce
# and Statement.import_into_db() consumes.
# Symbols are nested inside asset records (JSF.SYMBOLS is the per-asset list key) and carry
# their own identifiers (isin/reg_number/cusip), matching the DB layout where identifiers
# belong to symbols. Asset-wide attributes (expiry, principal) stay on the asset record.
class JSF:
    PERIOD = "period"
    ACCOUNTS = "accounts"
    ASSETS = "assets"
    SYMBOLS = "symbols"     # not a top-level section: the list of symbol records inside an asset record
    DB_IDS = "db_ids"       # optional: statement id -> jal db id matches per domain, consumed into the id map on load
    TRADES = "trades"
    TRANSFERS = "transfers"
    SWAPS = "swaps"
    BRIDGES = "bridges"     # each record is the SENDING leg of a cross-chain move (a pending half-bridge)
    CONVERSIONS = "conversions"   # basis-preserving same-account exchange (wrap, lending supply/withdraw, staking)
    CORP_ACTIONS = "corporate_actions"
    ASSET_PAYMENTS = "asset_payments"
    INCOME_SPENDING = "income_spending"

    ASSET_MONEY = "money"
    ASSET_STOCK = "stock"
    ASSET_ADR = "adr"
    ASSET_ETF = "etf"
    ASSET_BOND = "bond"
    ASSET_FUTURES = "futures"
    ASSET_OPTION = "option"
    ASSET_WARRANT = "warrant"
    ASSET_RIGHTS = "right"
    ASSET_CRYPTO = "crypto"
    ASSET_CFD = "cfd"
    ASSET_MLP = "mlp"
    ASSET_COMMODITY = "commodity"

    ACTION_MERGER = "merger"
    ACTION_SPLIT = "split"
    ACTION_SPINOFF = "spin-off"
    ACTION_SYMBOL_CHANGE = "symbol_change"
    ACTION_BOND_MATURITY = "bond_maturity"    # Isn't used in reality as will be put as ordinary sell operation
    ACTION_DELISTING = "delisting"
    ACTION_RIGHTS_ISSUE = "rights_issue"      # Not in use as doesn't create any financial consequences

    PAYMENT_DIVIDEND = "dividend"
    PAYMENT_INTEREST = "interest"
    PAYMENT_STOCK_DIVIDEND = "stock_dividend"
    PAYMENT_STOCK_VESTING = 'stock_vesting'
    PAYMENT_AMORTIZATION = 'bond_amortization'
    PAYMENT_FEE = 'fee'
    PAYMENT_GAS_FEE = 'gas_fee'                 # gas burned by a transaction that moved nothing
    PAYMENT_STAKING_REWARD = 'staking_reward'   # coins received for staking (or as lending interest)

    def __init__(self):
        pass

    @staticmethod
    def convert_predefined_asset_type(asset_type):
        asset_types = {
            PredefinedAsset.Stock: JSF.ASSET_STOCK,
            PredefinedAsset.Bond: JSF.ASSET_BOND,
            PredefinedAsset.ETF: JSF.ASSET_ETF,
            PredefinedAsset.Derivative: JSF.ASSET_FUTURES,
            PredefinedAsset.Commodity: JSF.ASSET_COMMODITY
        }
        return asset_types[asset_type]


class Statement_ImportError(Exception):
    pass

# Possible statement module capabilities
class Statement_Capabilities:
    MULTIPLE_LOAD = 1


# -----------------------------------------------------------------------------------------------------------------------
class Statement(QObject):   # derived from QObject to have proper string translation
    RU_PRICE_TOLERANCE = 1e-4   # TODO Probably need to switch imports to Decimal and remove it

    currency_substitutions = {}
    # Outcomes of the cross-chain token prompt (see _resolve_cross_chain_token): merge into an existing asset,
    # create a brand-new asset, or discard (blacklist) the token.
    TOKEN_MERGE, TOKEN_CREATE_NEW, TOKEN_DISCARD = 1, 2, 3
    ID_KEYS = ['isin', 'reg_number', 'cusip']   # security identifiers that symbol records may carry
    _identifier_types = {'isin': SymbolId.ISIN, 'reg_number': SymbolId.REG_CODE, 'cusip': SymbolId.CUSIP}
    _asset_types = {
        JSF.ASSET_MONEY: PredefinedAsset.Money,
        JSF.ASSET_STOCK: PredefinedAsset.Stock,
        JSF.ASSET_ADR: PredefinedAsset.Stock,
        JSF.ASSET_ETF: PredefinedAsset.ETF,
        JSF.ASSET_BOND: PredefinedAsset.Bond,
        JSF.ASSET_FUTURES: PredefinedAsset.Derivative,
        JSF.ASSET_OPTION: PredefinedAsset.Derivative,
        JSF.ASSET_WARRANT: PredefinedAsset.Derivative,
        JSF.ASSET_CFD: PredefinedAsset.Derivative,
        JSF.ASSET_CRYPTO: PredefinedAsset.Crypto,
        JSF.ASSET_MLP: PredefinedAsset.Stock
    }
    _corp_actions = {
        JSF.ACTION_MERGER: CorporateAction.Merger,
        JSF.ACTION_SPLIT: CorporateAction.Split,
        JSF.ACTION_SPINOFF: CorporateAction.SpinOff,
        JSF.ACTION_SYMBOL_CHANGE: CorporateAction.SymbolChange,
        JSF.ACTION_DELISTING: CorporateAction.Delisting
    }
    _sources = {
        'NYSE': AssetLocation.NYSE_EXCHANGE,
        'ARCA': AssetLocation.NYSE_EXCHANGE,
        'NASDAQ': AssetLocation.NASDAQ_EXCHANGE,
        'US': AssetLocation.NYSE_EXCHANGE,
        'TSE': AssetLocation.TMX_EXCHANGE,
        'SBF': AssetLocation.EURONEXT_EXCHANGE,
        'AMEX': AssetLocation.NYSE_EXCHANGE,
        'MOEX': AssetLocation.MOEX_EXCHANGE,
        'COIN': AssetLocation.ETH_BLOCKCHAIN,   # stub - crypto isn't really implemented yet
        'BVME': AssetLocation.MILAN_EXCHANGE,
        'BVME.ETF': AssetLocation.MILAN_EXCHANGE,
        'WSE': AssetLocation.WSE_EXCHANGE
    }

    def __init__(self):
        super().__init__()
        self._data = {}
        # Maps statement-local ids onto JAL db ids, per id domain. Filled by match_db_ids() for
        # elements that already exist in the db and by import_into_db() for newly created ones.
        # Statement data itself is never mutated by matching/import - a dump of self._data always
        # shows exactly what the producer built.
        self._id_map = {}
        self._reset_id_map()
        self._previous_accounts = {}
        self._last_selected_account = None
        # The interactive cross-chain token prompt can't run under pytest; tests set the desired outcome here as a
        # (action, target_asset_id) tuple. The default never merges or discards silently - it creates a new asset.
        self._token_action_for_tests = (Statement.TOKEN_CREATE_NEW, 0)
        self._section_loaders = {
            JSF.PERIOD: self._check_period,
            JSF.ASSETS: self._import_assets,
            JSF.ACCOUNTS: self._import_accounts,
            JSF.INCOME_SPENDING: self._import_imcomes_and_spendings,
            JSF.TRANSFERS: self._import_transfers,
            JSF.TRADES: self._import_trades,
            JSF.SWAPS: self._import_swaps,
            JSF.BRIDGES: self._import_bridges,
            JSF.CONVERSIONS: self._import_conversions,
            JSF.ASSET_PAYMENTS: self._import_asset_payments,
            JSF.CORP_ACTIONS: self._import_corporate_actions
        }

    def _reset_id_map(self):
        self._id_map = {JSF.ACCOUNTS: {}, JSF.ASSETS: {}, JSF.SYMBOLS: {}, JSF.ASSET_PAYMENTS: {}}

    # Returns db id that was matched for given statement id in 'domain' (0 if not matched)
    def mapped_id(self, domain: str, statement_id: int) -> int:
        return self._id_map[domain].get(statement_id, 0)

    # Registers a statement id -> db id match in 'domain'
    def set_mapped_id(self, domain: str, statement_id: int, db_id: int) -> None:
        self._id_map[domain][statement_id] = db_id

    # Returns the statement id assigned to a db payment with given oid (reserves a new one on
    # first call). Producers use it to reference existing db payments (e.g. tax updates for
    # dividends that were imported earlier) - the reserved id stays stable within the statement.
    def statement_payment_id(self, db_oid: int) -> int:
        for statement_id, oid in self._id_map[JSF.ASSET_PAYMENTS].items():
            if oid == db_oid:
                return statement_id
        statement_id = self._next_id(JSF.ASSET_PAYMENTS)
        self.set_mapped_id(JSF.ASSET_PAYMENTS, statement_id, db_oid)
        return statement_id

    # If 'debug_info' is given as parameter it is saved in JAL main directory text file appened with timestamp
    def save_debug_info(self, **kwargs):
        if 'debug_info' in kwargs:
            dump_name = JalSettings.path(JalSettings.PATH_APP) + Setup.STATEMENT_DUMP + datetime.now().strftime("%y-%m-%d_%H-%M-%S") + ".txt"
            try:
                with open(dump_name, 'w') as dump_file:
                    dump_file.write(f"JAL statement dump, {datetime.now().strftime('%y/%m/%d %H:%M:%S')}\n")
                    dump_file.write("----------------------------------------------------------------\n")
                    dump_file.write(str(kwargs['debug_info']))
                logging.warning(self.tr("Debug information is saved in ") + dump_name)
            except Exception as e:
                logging.error(self.tr("Failed to write statement dump into: ") + dump_name + ": " + str(e))

    # Returns a specific capabilities that is supported by some statement modules
    @staticmethod
    def capabilities() -> set:
        return set()

    # returns tuple (start_timestamp, end_timestamp)
    def period(self):
        if JSF.PERIOD in self._data:
            return self._data[JSF.PERIOD][0], self._data[JSF.PERIOD][1]
        else:
            return 0, 0

    # returns timestamp that is equal to the last second of initial timestamp
    def _end_of_date(self, timestamp) -> int:   #FIXME - something similar is in helpers.py -> refactor
        end_of_day = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(hour=23, minute=59, second=59)
        return int(end_of_day.replace(tzinfo=timezone.utc).timestamp())

    # Finds an account in jal database and returns its id
    def _map_db_account(self, account_id: int) -> int:
        account = [x for x in self._data[JSF.ACCOUNTS] if x["id"] == account_id][0]
        currency_symbol = self._single_symbol_record_of(account['currency'])['symbol']
        db_currency = JalAsset.find({'symbol': currency_symbol, 'type': PredefinedAsset.Money}).id()
        db_account = JalAccount.find({'number': account['number'], 'currency': db_currency}).id()
        return db_account

    # Finds an asset in jal database by statement symbol reference and returns its id
    def _map_db_asset_by_symbol(self, symbol_id: int) -> int:
        symbol = self._symbol(symbol_id)
        db_asset = JalAsset.find({'isin': symbol.get('isin', ''), 'symbol': symbol['symbol']}).id()
        return db_asset

    # Loads JSON statement format from file defined by 'filename'
    def load(self, filename: str) -> None:
        self._data = {}
        self._reset_id_map()
        try:
            with open(filename, 'r', encoding='utf-8') as statement_file:
                try:
                    self._data = json.load(statement_file)
                except json.JSONDecodeError:
                    logging.error(self.tr("Failed to read JSON from file: ") + filename)
        except Exception as err:
            raise Statement_ImportError(self.tr("Failed to read file: ") + str(err))
        # Statements that reference elements already existing in jal db carry those matches in an
        # optional 'db_ids' section (JSON keys are strings - convert back to int)
        for domain, matches in self._data.pop(JSF.DB_IDS, {}).items():
            if domain not in self._id_map:
                logging.warning(self.tr("Unsupported db_ids domain: ") + domain)
                continue
            for statement_id, db_id in matches.items():
                self.set_mapped_id(domain, int(statement_id), db_id)
        unsupported_sections = [x for x in self._data if x not in self._section_loaders]
        if unsupported_sections:
            for section in unsupported_sections:
                self._data.pop(section)
            logging.warning(self.tr("Some sections are not supported: ") + f"{unsupported_sections}")

    # Checks that statement elements that are already present in jal database and fills self._id_map
    # with statement id -> db id matches. self._data is not modified.
    def match_db_ids(self):
        self._match_currencies()
        self._match_assets()
        self._match_accounts()

    def _match_currencies(self):
        for asset in self._data[JSF.ASSETS]:
            if asset['type'] != JSF.ASSET_MONEY or self.mapped_id(JSF.ASSETS, asset['id']):
                continue
            symbol = self._single_symbol_record_of(asset['id'])
            asset_id = JalAsset.find({'symbol': symbol['symbol'], 'type': self._asset_types[asset['type']]}).id()
            if asset_id:
                self.set_mapped_id(JSF.ASSETS, asset['id'], asset_id)

    # Returns the first non-empty value of 'key' among symbol records of the asset ('' if none)
    def _asset_identifier(self, asset: dict, key: str) -> str:
        for symbol in asset[JSF.SYMBOLS]:
            if symbol.get(key):
                return symbol[key]
        return ''

    # Matches a symbol record that carries a contract address ('address' + 'location', produced by the chain
    # fetchers) against the database. The address is the only trustworthy identity of a token: its ticker and its
    # name are chosen by whoever deployed the contract, so anyone may publish a token calling itself 'USDC'.
    # Returns the db asset id or 0 when the token isn't known yet.
    @staticmethod
    def _match_by_address(symbol: dict) -> int:
        id_type = AssetLocation.address_id_of(symbol['location'])
        if id_type is None:
            return 0
        address = normalize_address(symbol['location'], symbol['address'])
        db_symbol = JalSymbol.find_by_identifier(id_type, address)
        return db_symbol.asset().id() if db_symbol.id() else 0

    # Matches non-money assets against the db: by isin first, then by reg_number/cusip, then by
    # symbol ticker (with identifier mismatch guards)
    def _match_assets(self):
        # A copy of the list is iterated because a 'discard' outcome of the cross-chain token prompt removes the
        # asset record (and the operations referencing it) from self._data while the loop is still running.
        for asset in list(self._data[JSF.ASSETS]):
            if asset['type'] == JSF.ASSET_MONEY or self.mapped_id(JSF.ASSETS, asset['id']):
                continue
            # A token is matched by contract address and by nothing else. The ticker fallback further down must
            # never run for it: tickers are attacker-controlled on a blockchain, so matching by one would merge a
            # freshly deployed token calling itself 'USDC' into the real USDC asset and its position.
            addressed = [s for s in asset[JSF.SYMBOLS] if s.get('address') and s.get('location')]
            if addressed:
                for symbol in addressed:
                    asset_id = self._match_by_address(symbol)
                    if asset_id:
                        self.set_mapped_id(JSF.ASSETS, asset['id'], asset_id)
                        break
                if not self.mapped_id(JSF.ASSETS, asset['id']):
                    self._resolve_cross_chain_token(asset, addressed)
                continue
            isin = self._asset_identifier(asset, 'isin')
            reg_number = self._asset_identifier(asset, 'reg_number')
            cusip = self._asset_identifier(asset, 'cusip')
            if isin:
                asset_id = JalAsset.find({'isin': isin}).id()
                if asset_id:
                    self.set_mapped_id(JSF.ASSETS, asset['id'], asset_id)
                    continue
            search = {}
            if reg_number:
                search['reg_number'] = reg_number
            if cusip:
                search['cusip'] = cusip
            if search:
                asset_id = JalAsset.find(search).id()
                if asset_id:
                    self.set_mapped_id(JSF.ASSETS, asset['id'], asset_id)
                    continue
            for symbol in asset[JSF.SYMBOLS]:
                search_data = {'symbol': symbol['symbol'], 'type': self._asset_types[asset['type']]}
                if isin:
                    search_data['isin'] = isin
                if 'expiry' in asset:
                    search_data['expiry'] = asset['expiry']
                db_asset = JalAsset.find(search_data)
                db_id = db_asset.id()
                if db_id:
                    if db_asset.symbol_id(SymbolId.ISIN) and isin and db_asset.symbol_id(SymbolId.ISIN) != isin:
                        continue  # verify that we don't have ISIN mismatch
                    if db_asset.symbol_id(SymbolId.REG_CODE) and reg_number and db_asset.symbol_id(SymbolId.REG_CODE) != reg_number:
                        continue  # verify that we don't have reg.number mismatch
                    if db_asset.symbol_id(SymbolId.CUSIP) and cusip and db_asset.symbol_id(SymbolId.CUSIP) != cusip:
                        continue  # verify that we don't have CUSIP mismatch
                    self.set_mapped_id(JSF.ASSETS, asset['id'], db_id)
                    break

    # An addressed token (chain fetcher output) reached this point without a contract-address match. If a known
    # crypto asset already uses its ticker, the two may be the same token on different chains (e.g. USDT on Ethereum
    # and on Tron) or two unrelated coins reusing a ticker - only the user can tell, so they are asked once per new
    # token. Every outcome records an address identifier (merge/create -> _import_assets writes this chain's address)
    # or a blacklist row (discard), so the same token resolves automatically on later imports - no curated registry.
    def _resolve_cross_chain_token(self, asset: dict, addressed: list) -> None:
        candidates = self._crypto_ticker_candidates(addressed)
        if not candidates:
            return   # nothing shares the ticker - _import_assets simply stages a new asset carrying the address
        action, target = self.select_token_action(asset, addressed, candidates)
        if action == self.TOKEN_MERGE and target:
            self.set_mapped_id(JSF.ASSETS, asset['id'], target)
        elif action == self.TOKEN_DISCARD:
            self._discard_token(asset, addressed)
        # TOKEN_CREATE_NEW (and a merge without a target): leave unmapped so a new asset is created on import

    # Returns the ids of existing crypto assets whose active listing shares a ticker with any of the token's symbols.
    def _crypto_ticker_candidates(self, addressed: list) -> list:
        candidates = []
        for symbol in addressed:
            for asset_id in JalAsset.get_crypto_assets_by_symbol(symbol['symbol']):
                if asset_id not in candidates:
                    candidates.append(asset_id)
        return candidates

    # Asks the user whether an unmatched addressed token should merge into an existing crypto asset, become a new
    # asset, or be discarded. Returns (action, target_asset_id); target is only meaningful for a merge.
    def select_token_action(self, asset: dict, addressed: list, candidates: list) -> tuple:
        if "pytest" in sys.modules:
            return self._token_action_for_tests
        token = addressed[0]
        options = [(asset_id, self._candidate_label(asset_id)) for asset_id in candidates]
        dialog = SelectTokenActionDialog(asset.get('name', ''), token['symbol'],
                                         AssetLocation().get_name(token['location']), token['address'], options)
        if dialog.exec() != QDialog.Accepted:
            return self.TOKEN_CREATE_NEW, 0   # closing the dialog never silently merges or discards
        mapping = {SelectTokenActionDialog.Merge: self.TOKEN_MERGE,
                   SelectTokenActionDialog.CreateNew: self.TOKEN_CREATE_NEW,
                   SelectTokenActionDialog.Discard: self.TOKEN_DISCARD}
        return mapping[dialog.action], dialog.target_asset_id

    # Human-readable description of a merge candidate: its name and the chains it is already listed on.
    def _candidate_label(self, asset_id: int) -> str:
        asset = JalAsset(asset_id)
        chains = []
        for symbol_id in asset.active_symbol_ids():
            chain = AssetLocation().get_name(JalSymbol(symbol_id).location())
            if chain and chain not in chains:
                chains.append(chain)
        name = asset.name() or asset.symbol()
        return f"{name} [{', '.join(chains)}]" if chains else name

    # Discards a token the user doesn't want: its address is blacklisted (so future fetches skip it silently) and the
    # asset together with every operation referencing it is removed from this statement - an operation involving a
    # discarded token (a swap leg, a transfer) can't be imported without it.
    def _discard_token(self, asset: dict, addressed: list) -> None:
        for symbol in addressed:
            JalTokenBlacklist.add(symbol['location'], symbol['address'], name_hint=symbol.get('symbol', ''), auto=False)
        discarded = {symbol['id'] for symbol in asset[JSF.SYMBOLS]}
        self._drop_operations_referencing(discarded)
        self._data[JSF.ASSETS] = [a for a in self._data[JSF.ASSETS] if a['id'] != asset['id']]

    # Removes every operation that references any of the given symbol ids from all operation sections.
    def _drop_operations_referencing(self, symbol_ids: set) -> None:
        for section in (JSF.TRANSFERS, JSF.SWAPS, JSF.BRIDGES, JSF.CONVERSIONS, JSF.ASSET_PAYMENTS,
                        JSF.TRADES, JSF.CORP_ACTIONS):
            if section not in self._data:
                continue
            self._data[section] = [operation for operation in self._data[section]
                                   if not (self._operation_symbol_ids(section, operation) & symbol_ids)]

    # Returns the set of symbol ids referenced by an operation of the given section.
    @staticmethod
    def _operation_symbol_ids(section: str, operation: dict) -> set:
        symbol_ids = set()
        if section == JSF.TRANSFERS:
            symbol_ids.update(operation.get('symbol', []))
            if operation.get('fee_symbol') is not None:
                symbol_ids.add(operation['fee_symbol'])
        elif section in (JSF.SWAPS, JSF.CONVERSIONS):
            symbol_ids.update([operation['out_symbol'], operation['in_symbol']])
            if operation.get('fee_symbol') is not None:
                symbol_ids.add(operation['fee_symbol'])
        elif section == JSF.BRIDGES:      # a half carries a single 'symbol' (what it sent) plus an optional fee
            symbol_ids.add(operation['symbol'])
            if operation.get('fee_symbol') is not None:
                symbol_ids.add(operation['fee_symbol'])
        elif section in (JSF.ASSET_PAYMENTS, JSF.TRADES):
            symbol_ids.add(operation['symbol'])
        elif section == JSF.CORP_ACTIONS:
            symbol_ids.add(operation['symbol'])
            symbol_ids.update(item['symbol'] for item in operation.get('outcome', []))
        return symbol_ids

    # Matches accounts by number+currency (or via user dialog when producer requested it)
    def _match_accounts(self):
        for account in self._data[JSF.ACCOUNTS]:
            if self.mapped_id(JSF.ACCOUNTS, account['id']):
                continue
            if 'selection_text' in account:
                account_id = self.select_account(account['selection_text'], 0, self._last_selected_account)
            else:
                account_data = account.copy()
                account_data['currency'] = self.mapped_id(JSF.ASSETS, account['currency'])
                account_id = JalAccount.find(account_data).id()
            if account_id:
                self.set_mapped_id(JSF.ACCOUNTS, account['id'], account_id)

    def validate_format(self):
        if not isinstance(self._data, dict):
            raise Statement_ImportError(self.tr("Statement is not a valid JSF document"))
        for section, content in self._data.items():
            if section == JSF.PERIOD:
                if not (isinstance(content, list) and len(content) == 2):
                    raise Statement_ImportError(self.tr("Statement period is invalid"))
                continue
            if not isinstance(content, list) or any(not isinstance(x, dict) or 'id' not in x for x in content):
                raise Statement_ImportError(self.tr("Invalid statement section: ") + section)
        for asset in self._data.get(JSF.ASSETS, []):
            if 'type' not in asset or not isinstance(asset.get(JSF.SYMBOLS), list):
                raise Statement_ImportError(self.tr("Invalid asset record: ") + f"{asset}")

    # Store content of JSON statement into database (inside one db transaction - a failure in the
    # middle of the import leaves no partial data behind).
    # Returns a dict of dict with amounts:
    # { account_1: { asset_1: X, asset_2: Y, ...}, account_2: { asset_N: Z, ...}, ... }
    def import_into_db(self):
        db = JalDB()
        db.start_transaction()
        try:
            for section in self._section_loaders:
                if section in self._data:
                    self._section_loaders[section](self._data[section])
        except Exception:
            db.rollback_transaction()
            JalAsset.db_cache.clear_cache()   # Caches may reference rolled back rows
            JalAccount.db_cache.clear_cache()
            raise
        db.commit_transaction()

        totals = defaultdict(dict)
        for account in self._data[JSF.ACCOUNTS]:
            if 'cash_end' in account:
                account_id = self.mapped_id(JSF.ACCOUNTS, account['id'])
                currency_id = self.mapped_id(JSF.ASSETS, account['currency'])
                totals[account_id][currency_id] = account['cash_end']
        return totals

    def _check_period(self, period):
        if len(period) != 2:
            raise Statement_ImportError(self.tr("Statement period is invalid"))
        if JSF.ACCOUNTS not in self._data:
            return
        for account in self._data[JSF.ACCOUNTS]:
            account_id = self.mapped_id(JSF.ACCOUNTS, account['id'])
            if account_id:  # Checks if report is after last transaction recorded for account.
                jal_account = JalAccount(account_id)
                if period[0] < jal_account.last_operation_date():
                    if QMessageBox().warning(None, self.tr("Confirmation"),
                                             self.tr("Statement period starts before last recorded operation for the account ")
                                             + f'"{jal_account.name()}"\n' + self.tr("Continue import?"),
                                             QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                        raise Statement_ImportError(self.tr("Statement import was cancelled"))

    # Creates/updates assets together with their symbols and identifiers.
    # Symbols are added in statement id order (i.e. in the order the producer discovered them,
    # across all assets) so that db ids of new asset_symbol rows don't depend on asset grouping.
    def _import_assets(self, assets):
        for asset in assets:
            db_id = self.mapped_id(JSF.ASSETS, asset['id'])
            if db_id:
                db_asset = JalAsset(db_id)
                db_asset.update_data({k: asset[k] for k in ('name', 'country', 'expiry', 'principal') if k in asset})
            else:
                asset_type = self._asset_types[asset['type']]
                db_asset = JalAssetCreator(asset_type, asset.get('name', ''), asset.get('country', '')).commit()
                if not db_asset.id():
                    raise Statement_ImportError(self.tr("Can't create asset: ") + f"{asset}")
                self.set_mapped_id(JSF.ASSETS, asset['id'], db_asset.id())
                db_asset.update_data({k: asset[k] for k in ('expiry', 'principal') if k in asset})
        symbols = [(asset, symbol) for asset in assets for symbol in asset[JSF.SYMBOLS]]
        for asset, symbol in sorted(symbols, key=lambda x: x[1]['id']):
            db_asset = JalAsset(self.mapped_id(JSF.ASSETS, asset['id']))
            if asset['type'] == JSF.ASSET_MONEY:
                currency = db_asset.id()   # Money symbols are denominated in their own asset
                location = AssetLocation.BANK_ACCOUNT
            else:
                currency = self.mapped_id(JSF.ASSETS, symbol['currency'])
                if not currency:
                    raise Statement_ImportError(self.tr("Unmatched currency for symbol: ") + f"{symbol}")
                # A chain fetcher states the location outright; a broker statement names a trading venue that
                # is looked up in the table of known sources.
                location = symbol['location'] if symbol.get('location') else \
                    self._sources.get(symbol.get('note', ''), AssetLocation.UNDEFINED)
            symbol_id = db_asset.add_symbol(symbol['symbol'], currency, location_id=location)
            self.set_mapped_id(JSF.SYMBOLS, symbol['id'], symbol_id)
            for key in self.ID_KEYS:
                if symbol.get(key):
                    db_asset.update_identifier(symbol_id, self._identifier_types[key], symbol[key])
            # The contract address is stored under the identifier type of its own chain, so that the token stays
            # findable by address later - by the next fetch and by the quote downloader alike
            if symbol.get('address'):
                address_id = AssetLocation.address_id_of(location)
                if address_id is not None:
                    db_asset.update_identifier(symbol_id, address_id,
                                               normalize_address(location, symbol['address']))

    def _import_accounts(self, accounts):
        for account in accounts:
            if self.mapped_id(JSF.ACCOUNTS, account['id']):
                continue
            currency_id = self.mapped_id(JSF.ASSETS, account['currency'])
            if not currency_id:
                raise Statement_ImportError(self.tr("Unmatched currency for account: ") + f"{account}")
            account_data = account.copy()
            account_data['investing'] = 1
            account_data['currency'] = currency_id
            new_account = JalAccount.find(account_data)
            if not new_account.id():
                new_account = JalAccountCreator(
                    currency_id=account_data['currency'], number=account_data['number'],
                    name=account_data.get('name', ''), investing=account_data['investing'],
                    organization=account_data.get('organization', PredefinedAgents.Empty),
                    country=account_data.get('country', ''),
                    precision=account_data.get('precision', Setup.DEFAULT_ACCOUNT_PRECISION)
                ).commit()
            if new_account.id():
                self.set_mapped_id(JSF.ACCOUNTS, account['id'], new_account.id())
            else:
                raise Statement_ImportError(self.tr("Can't create account: ") + f"{account}")

    def _import_imcomes_and_spendings(self, actions):
        for action in actions:
            operation = deepcopy(action)
            operation['account_id'] = self.mapped_id(JSF.ACCOUNTS, operation.pop('account'))
            if not operation['account_id']:
                raise Statement_ImportError(self.tr("Unmatched account for income/spending: ") + f"{action}")
            operation['peer_id'] = operation.pop('peer')   # peers are always direct db references
            if operation['peer_id'] == 0:
                operation['peer_id'] = JalAccount(operation['account_id']).organization()
            for line in operation['lines']:
                line['category_id'] = line.pop('category')   # categories are always direct db references
                if line['category_id'] <= 0:
                    raise Statement_ImportError(self.tr("Invalid category for income/spending: ") + f"{action}")
                line['note'] = line.pop('description')
            LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, operation)

    def _import_transfers(self, transfers):
        for transfer in transfers:
            operation = deepcopy(transfer)
            accounts = []
            for account in operation['account']:
                account_id = self.mapped_id(JSF.ACCOUNTS, account) if account else 0
                if account and not account_id:
                    raise Statement_ImportError(self.tr("Unmatched account for transfer: ") + f"{transfer}")
                accounts.append(account_id)
            symbols = []
            for symbol in operation['symbol']:
                symbol_id = self.mapped_id(JSF.SYMBOLS, symbol)
                if not symbol_id:
                    raise Statement_ImportError(self.tr("Unmatched symbol for transfer: ") + f"{transfer}")
                symbols.append(symbol_id)
            asset_ids = [self.mapped_id(JSF.ASSETS, self._symbol_asset(x)['id']) for x in operation['symbol']]
            asset_types = [JalAsset(x).type() for x in asset_ids]
            if asset_types[0] != asset_types[1]:
                raise Statement_ImportError(self.tr("Impossible to convert asset type in transfer: ") + f"{transfer}")
            if accounts[0] == 0 or accounts[1] == 0:
                text = ''
                pair_account = 1
                if accounts[0] == 0:  # Deposit
                    # For an asset transfer the quantity is carried by 'withdrawal' on both legs; 'deposit' holds the
                    # cost basis in the destination currency (0 when unknown, e.g. from a chain fetcher). So the
                    # amount arriving is the withdrawn quantity - only a money transfer, which may convert currency,
                    # shows the distinct 'deposit' amount.
                    arriving = operation['deposit'] if asset_types[1] == PredefinedAsset.Money else operation['withdrawal']
                    text = self.tr("Deposit of ") + f"{arriving:.2f} " + \
                           f"{JalAsset(asset_ids[1]).symbol()} @{ts2d(operation['timestamp'])}\n" + \
                           self.tr("Select account to withdraw from:")
                    pair_account = accounts[1]
                if accounts[1] == 0:  # Withdrawal
                    text = self.tr("Withdrawal of ") + f"{operation['withdrawal']:.2f} " + \
                           f"{JalAsset(asset_ids[0]).symbol()} @{ts2d(operation['timestamp'])}\n" + \
                           self.tr("Select account to deposit to:")
                    pair_account = accounts[0]
                try:
                    chosen_account = self._previous_accounts[JalAccount(pair_account).currency()]
                except KeyError:
                    chosen_account = self.select_account(text, pair_account, self._last_selected_account)
                if chosen_account == 0:
                    raise Statement_ImportError(self.tr("Account not selected"))
                self._last_selected_account = chosen_account
                if accounts[0] == 0:
                    accounts[0] = chosen_account
                if accounts[1] == 0:
                    accounts[1] = chosen_account
            if asset_types[0] != PredefinedAsset.Money:
                operation['symbol_id'] = symbols[0]
            operation.pop('symbol')
            # A fee paid in an asset rather than in the money of the fee account - on-chain gas, which is burned
            # in the native coin of the chain and may differ from the asset being transferred.
            if 'fee_symbol' in operation:
                fee_symbol_id = self.mapped_id(JSF.SYMBOLS, operation.pop('fee_symbol'))
                if not fee_symbol_id:
                    raise Statement_ImportError(self.tr("Unmatched fee symbol for transfer: ") + f"{transfer}")
                operation['fee_symbol_id'] = fee_symbol_id
            if 'description' in operation:
                operation['note'] = operation.pop('description')
            operation['withdrawal_timestamp'] = operation['deposit_timestamp'] = operation.pop('timestamp')
            operation['withdrawal_account'] = accounts[0]
            operation['deposit_account'] = accounts[1]
            operation['fee_account'] = accounts[2]
            operation.pop('account')
            if abs(operation['fee']) < 1e-10:  # FIXME  Need to refactor this module for decimal usage
                operation.pop('fee_account')
                operation.pop('fee')
                operation.pop('fee_symbol_id', None)   # A zero fee has no asset to be paid in either
            LedgerTransaction.create_new(LedgerTransaction.Transfer, operation)

    def _import_trades(self, trades):
        for trade in trades:
            operation = deepcopy(trade)
            operation['account_id'] = self.mapped_id(JSF.ACCOUNTS, operation.pop('account'))
            if not operation['account_id']:
                raise Statement_ImportError(self.tr("Unmatched account for trade: ") + f"{trade}")
            operation['symbol_id'] = self.mapped_id(JSF.SYMBOLS, operation.pop('symbol'))
            if not operation['symbol_id']:
                raise Statement_ImportError(self.tr("Unmatched symbol for trade: ") + f"{trade}")
            operation['qty'] = operation.pop('quantity')
            if 'cancelled' in operation and operation['cancelled']:
                del operation['cancelled']          # Remove extra data
                operation['qty'] = -operation['qty']    # Change side as cancellation is an opposite operation
                oid = LedgerTransaction().find_operation(LedgerTransaction.Trade, operation)
                if oid:
                    LedgerTransaction.get_operation(LedgerTransaction.Trade, oid).delete()
                continue
            LedgerTransaction.create_new(LedgerTransaction.Trade, operation)

    def _import_swaps(self, swaps):
        for swap in swaps:
            operation = deepcopy(swap)
            operation['account_id'] = self.mapped_id(JSF.ACCOUNTS, operation.pop('account'))
            if not operation['account_id']:
                raise Statement_ImportError(self.tr("Unmatched account for swap: ") + f"{swap}")
            operation['out_symbol_id'] = self.mapped_id(JSF.SYMBOLS, operation.pop('out_symbol'))
            operation['in_symbol_id'] = self.mapped_id(JSF.SYMBOLS, operation.pop('in_symbol'))
            if not operation['out_symbol_id'] or not operation['in_symbol_id']:
                raise Statement_ImportError(self.tr("Unmatched symbol for swap: ") + f"{swap}")
            if operation.get('fee_symbol') is not None:
                operation['fee_symbol_id'] = self.mapped_id(JSF.SYMBOLS, operation.pop('fee_symbol'))
            else:
                operation.pop('fee_symbol', None)
            if 'description' in operation:
                operation['note'] = operation.pop('description')
            LedgerTransaction.create_new(LedgerTransaction.Swap, operation)

    # Imports the SENDING leg of a cross-chain move as a pending half-bridge: its receiving leg stays NULL until the
    # user adopts the arriving transfer into it (BridgeMatcher), which also decides whether the pair is a bridge or an
    # asset-changing cross-chain swap. Only this leg is ever produced by a fetcher - an arriving asset can't be
    # recognized as belonging to a cross-chain move, so it is imported as a plain transfer.
    def _import_bridges(self, bridges):
        for bridge in bridges:
            source = deepcopy(bridge)
            account_id = self.mapped_id(JSF.ACCOUNTS, source.pop('account'))
            if not account_id:
                raise Statement_ImportError(self.tr("Unmatched account for bridge: ") + f"{bridge}")
            symbol_id = self.mapped_id(JSF.SYMBOLS, source.pop('symbol'))
            if not symbol_id:
                raise Statement_ImportError(self.tr("Unmatched symbol for bridge: ") + f"{bridge}")
            operation = {'out_timestamp': source['timestamp'], 'out_account_id': account_id,
                         'out_symbol_id': symbol_id, 'out_qty': source['qty'],
                         'out_tx_hash': source.get('tx_hash', '')}
            if source.get('fee_symbol') is not None:
                operation['fee_symbol_id'] = self.mapped_id(JSF.SYMBOLS, source['fee_symbol'])
                operation['fee_qty'] = source['fee_qty']
            if source.get('description'):
                operation['note'] = source['description']
            LedgerTransaction.create_new(LedgerTransaction.Bridge, operation)

    # Imports a basis-preserving exchange of one asset into another on the same account (a wrap, a lending
    # supply/withdrawal, liquid staking). Its record has the same shape as a same-chain swap - the difference is
    # entirely in how the ledger treats it, so it is a section of its own rather than a flag on a swap.
    def _import_conversions(self, conversions):
        for conversion in conversions:
            operation = deepcopy(conversion)
            operation['account_id'] = self.mapped_id(JSF.ACCOUNTS, operation.pop('account'))
            if not operation['account_id']:
                raise Statement_ImportError(self.tr("Unmatched account for conversion: ") + f"{conversion}")
            operation['out_symbol_id'] = self.mapped_id(JSF.SYMBOLS, operation.pop('out_symbol'))
            operation['in_symbol_id'] = self.mapped_id(JSF.SYMBOLS, operation.pop('in_symbol'))
            if not operation['out_symbol_id'] or not operation['in_symbol_id']:
                raise Statement_ImportError(self.tr("Unmatched symbol for conversion: ") + f"{conversion}")
            if operation.get('fee_symbol') is not None:
                operation['fee_symbol_id'] = self.mapped_id(JSF.SYMBOLS, operation.pop('fee_symbol'))
            else:
                operation.pop('fee_symbol', None)
            if 'description' in operation:
                operation['note'] = operation.pop('description')
            LedgerTransaction.create_new(LedgerTransaction.Conversion, operation)

    def _import_asset_payments(self, payments):
        for payment in payments:
            operation = deepcopy(payment)
            operation['account_id'] = self.mapped_id(JSF.ACCOUNTS, operation.pop('account'))
            if not operation['account_id']:
                raise Statement_ImportError(self.tr("Unmatched account for payment: ") + f"{payment}")
            symbol = operation.pop('symbol')
            operation['symbol_id'] = self.mapped_id(JSF.SYMBOLS, symbol)
            if not operation['symbol_id']:
                raise Statement_ImportError(self.tr("Unmatched symbol for payment: ") + f"{payment}")
            operation['note'] = operation.pop('description')
            if 'price' in operation:
                asset_id = self.mapped_id(JSF.ASSETS, self._symbol_asset(symbol)['id'])
                JalAsset(asset_id).set_quotes(
                    [{'timestamp': operation['timestamp'], 'quote': Decimal(operation.pop('price'))}],
                    JalAccount(operation['account_id']).currency())
            db_payment_id = self.mapped_id(JSF.ASSET_PAYMENTS, payment['id'])
            if operation['type'] == JSF.PAYMENT_DIVIDEND:
                if db_payment_id:  # Dividend exists, only tax to be updated
                    dividend = LedgerTransaction.get_operation(LedgerTransaction.AssetPayment, db_payment_id)
                    dividend.update_tax(operation['tax'])
                else:
                    operation['type'] = AssetPayment.Dividend
                    LedgerTransaction.create_new(LedgerTransaction.AssetPayment, operation)
            elif operation['type'] == JSF.PAYMENT_INTEREST:
                operation['type'] = AssetPayment.BondInterest
                LedgerTransaction.create_new(LedgerTransaction.AssetPayment, operation)
            elif operation['type'] == JSF.PAYMENT_AMORTIZATION:
                operation['type'] = AssetPayment.BondAmortization
                LedgerTransaction.create_new(LedgerTransaction.AssetPayment, operation)
            elif operation['type'] == JSF.PAYMENT_STOCK_DIVIDEND:
                if db_payment_id:  # Dividend exists, only tax to be updated
                    dividend = LedgerTransaction.get_operation(LedgerTransaction.AssetPayment, db_payment_id)
                    dividend.update_tax(operation['tax'])
                else:
                    operation['type'] = AssetPayment.StockDividend
                    LedgerTransaction.create_new(LedgerTransaction.AssetPayment, operation)
            elif operation['type'] == JSF.PAYMENT_STOCK_VESTING:
                operation['type'] = AssetPayment.StockVesting
                LedgerTransaction.create_new(LedgerTransaction.AssetPayment, operation)
            elif operation['type'] == JSF.PAYMENT_FEE:
                operation['type'] = AssetPayment.Fee
                LedgerTransaction.create_new(LedgerTransaction.AssetPayment, operation)
            elif operation['type'] == JSF.PAYMENT_GAS_FEE:
                operation['type'] = AssetPayment.GasFee
                LedgerTransaction.create_new(LedgerTransaction.AssetPayment, operation)
            elif operation['type'] == JSF.PAYMENT_STAKING_REWARD:
                operation['type'] = AssetPayment.StakingReward
                LedgerTransaction.create_new(LedgerTransaction.AssetPayment, operation)
            else:
                raise Statement_ImportError(self.tr("Unsupported payment type: ") + f"{payment}")

    def _import_corporate_actions(self, actions):
        for action in actions:
            operation = deepcopy(action)
            operation['account_id'] = self.mapped_id(JSF.ACCOUNTS, operation.pop('account'))
            if not operation['account_id']:
                raise Statement_ImportError(self.tr("Unmatched account for corporate action: ") + f"{action}")
            operation['symbol_id'] = self.mapped_id(JSF.SYMBOLS, operation.pop('symbol'))
            if not operation['symbol_id']:
                raise Statement_ImportError(self.tr("Unmatched symbol for corporate action: ") + f"{action}")
            operation['qty'] = operation.pop('quantity')
            operation['note'] = operation.pop('description')
            for item in operation['outcome']:
                item['symbol_id'] = self.mapped_id(JSF.SYMBOLS, item.pop('symbol'))
                if not item['symbol_id']:
                    raise Statement_ImportError(self.tr("Unmatched symbol for corporate action: ") + f"{action}")
                item['qty'] = item.pop('quantity')
                item['value_share'] = item.pop('share')
            try:
                operation['type'] = self._corp_actions[operation.pop('type')]
            except KeyError:
                raise Statement_ImportError(self.tr("Unsupported corporate action: ") + f"{action}")
            LedgerTransaction.create_new(LedgerTransaction.CorporateAction, operation)

    def select_account(self, text, account_id, recent_account_id=0):
        if "pytest" in sys.modules:
            return 1    # Always return 1st account if we are in testing mode
        dialog = SelectAccountDialog(text, account_id, recent_account=recent_account_id)
        if dialog.exec() != QDialog.Accepted:
            return 0
        else:
            if dialog.store_account:
                self._previous_accounts[JalAccount(dialog.account_id).currency()] = dialog.account_id
            return dialog.account_id

    def _find_account_id(self, number, currency):
        try:
            code = self.currency_substitutions[currency]
        except KeyError:
            code = currency
        currency_id = self.currency_id(code)
        match = [x for x in self._data[JSF.ACCOUNTS] if 'number' in x and x['number'] == number and x['currency'] == currency_id]
        if match:
            if len(match) == 1:
                return match[0]['id']
            else:
                raise Statement_ImportError(self.tr("Multiple accounts found: ") + f"{number}/{currency}")
        new_id = self._next_id(JSF.ACCOUNTS)
        new_account = {"id": new_id, "number": number, 'currency': currency_id}
        self._data[JSF.ACCOUNTS].append(new_account)
        return new_id

    # Returns the next free element id for given section (also skips ids that were reserved in
    # self._id_map for db-matched elements that aren't put into self._data)
    def _next_id(self, section: str) -> int:
        ids = [x['id'] for x in self._data.get(section, [])]
        ids += list(self._id_map.get(section, {}).keys())
        return max([0] + ids) + 1

    # Returns the next free symbol record id (symbol ids are unique across all assets)
    def _next_symbol_id(self) -> int:
        ids = [s['id'] for a in self._data.get(JSF.ASSETS, []) for s in a[JSF.SYMBOLS]]
        ids += list(self._id_map.get(JSF.SYMBOLS, {}).keys())
        return max([0] + ids) + 1

    # Returns asset dictionary by asset id
    def _asset(self, asset_id) -> dict:
        asset = self._find_in_list(self._data[JSF.ASSETS], 'id', asset_id)
        if asset is None:
            raise Statement_ImportError(self.tr("Asset id not found") + f"{asset_id}")
        return asset

    # Returns symbol dictionary by symbol id (symbols are nested inside asset records)
    def _symbol(self, symbol_id) -> dict:
        for asset in self._data[JSF.ASSETS]:
            for symbol in asset[JSF.SYMBOLS]:
                if symbol['id'] == symbol_id:
                    return symbol
        raise Statement_ImportError(self.tr("Symbol id not found: ") + f"{symbol_id}")

    # Returns the asset dictionary that owns symbol record with given id
    def _symbol_asset(self, symbol_id) -> dict:
        for asset in self._data[JSF.ASSETS]:
            for symbol in asset[JSF.SYMBOLS]:
                if symbol['id'] == symbol_id:
                    return asset
        raise Statement_ImportError(self.tr("Symbol id not found: ") + f"{symbol_id}")

    # Returns the asset dictionary that has a symbol with 'key' identifier equal to 'value' (None if not found)
    def _asset_by_identifier(self, key: str, value) -> dict | None:
        matches = [a for a in self._data[JSF.ASSETS] if any(s.get(key) == value for s in a[JSF.SYMBOLS])]
        if matches:
            if len(matches) == 1:
                return matches[0]
            else:
                raise Statement_ImportError(self.tr("Multiple match for ") + f"'{key}'='{value}': {matches}")
        return None

    # Helper function that takes list of dictionaries and returns one element where key=value
    # exception is raised if multiple elements found
    # Returns None if nothing was found in the list
    def _find_in_list(self, data_list, key, value) -> dict | None:
        filtered = [x for x in data_list if key in x and x[key] == value]
        if filtered:
            if len(filtered) == 1:
                return filtered[0]
            else:
                raise Statement_ImportError(self.tr("Multiple match for ") + f"'{key}'='{value}': {filtered}")
        return None

    # Method finds currency in current statement data. New currency is created if no currency was found.
    # Returns currency id
    def currency_id(self, currency_symbol) -> int:
        match = [x for x in self._data[JSF.ASSETS] if x['type'] == JSF.ASSET_MONEY
                 and any(s['symbol'] == currency_symbol for s in x[JSF.SYMBOLS])]
        if match:
            if len(match) == 1:
                return match[0]['id']
            else:
                raise Statement_ImportError(self.tr("Multiple currency match for ") + f"{currency_symbol}")
        else:
            asset_id = self._next_id(JSF.ASSETS)
            symbol = {"id": self._next_symbol_id(), "symbol": currency_symbol}
            self._data[JSF.ASSETS].append(
                {"id": asset_id, "type": JSF.ASSET_MONEY, "name": currency_symbol, JSF.SYMBOLS: [symbol]})
            return asset_id

    # Returns the single symbol record that belongs to given asset. Operations must
    # reference an exact symbol, so multiple candidates are a hard failure.
    def _single_symbol_record_of(self, asset_id) -> dict:
        symbols = self._asset(asset_id)[JSF.SYMBOLS]
        if len(symbols) != 1:
            raise Statement_ImportError(self.tr("Can't find exact symbol for asset: ") + f"{asset_id}: {symbols}")
        return symbols[0]

    # Returns the id of the single symbol record that belongs to given asset
    def _single_symbol_of(self, asset_id) -> int:
        return self._single_symbol_record_of(asset_id)['id']

    # Same as currency_id() but returns the id of the currency symbol record, not the money asset
    def currency_symbol_id(self, currency_symbol) -> int:
        return self._single_symbol_of(self.currency_id(currency_symbol))

    # Method finds asset in current statement data. New asset is created if no asset was found.
    # Returns asset id
    def asset_id(self, asset_info) -> int:
        asset = None
        asset_info = {k: v for k, v in asset_info.items() if v}  # drop keys with empty values
        for key in self.ID_KEYS:
            if asset is None and key in asset_info:
                asset = self._asset_by_identifier(key, asset_info[key])
        has_code = any(asset_info.get(key, '') for key in self.ID_KEYS)
        if not has_code and asset is None and 'symbol' in asset_info:
            symbols = [(a, s) for a in self._data[JSF.ASSETS] for s in a[JSF.SYMBOLS]
                       if s['symbol'] == asset_info['symbol']]
            if len(symbols) > 1:
                raise Statement_ImportError(
                    self.tr("Multiple match for ") + f"'symbol'='{asset_info['symbol']}': {symbols}")
            if symbols:
                asset = symbols[0][0]
        if asset is None and asset_info.get('search_offline', False):   # If allowed fetch asset data from database
            db_asset = JalAsset.find(asset_info)
            if db_asset.id():
                symbol = {'id': self._next_symbol_id(), 'symbol': db_asset.symbol(asset_info['currency']),
                          'currency': asset_info['currency']}
                if db_asset.symbol_id(SymbolId.ISIN):
                    symbol['isin'] = db_asset.symbol_id(SymbolId.ISIN)
                self._uppend_keys_from(symbol, asset_info, ['reg_number', 'cusip'])
                asset = {'id': self._next_id(JSF.ASSETS), 'type': JSF.convert_predefined_asset_type(db_asset.type()),
                         'name': db_asset.name(), JSF.SYMBOLS: [symbol]}
                self._data[JSF.ASSETS].append(asset)
                self.set_mapped_id(JSF.ASSETS, asset['id'], db_asset.id())
                return asset['id']
        if asset is None and 'search_online' in asset_info:
            if asset_info['search_online'] == "MOEX":
                search_data = {}
                self._uppend_keys_from(search_data, asset_info, ['isin', 'reg_number'])
                if 'symbol' in asset_info:
                    search_data['name'] = asset_info['symbol']   # Search as by name as it is more flexible
                symbol = MOEX().find_asset(**search_data)
                if not symbol and 'symbol' in asset_info:
                    symbol = asset_info['symbol']
                currency = asset_info['currency'] if 'currency' in asset_info else None  # Keep currency
                moex_asset = MOEX().asset_info(symbol=symbol)
                if not moex_asset:
                    raise Statement_ImportError(self.tr("Can't find asset on moex.com: ") + f"'{asset_info}'")
                try:
                    moex_asset['type'] = JSF.convert_predefined_asset_type(moex_asset['type'])
                except KeyError:
                    raise Statement_ImportError(self.tr("Unsupported asset type from moex.com: ") + f"'{moex_asset}'")
                moex_asset['currency'] = JalAsset.get_base_currency() if currency is None else currency
                moex_asset['note'] = "MOEX"
                return self.asset_id(moex_asset)  # Call itself once again to cross-check downloaded data
            else:
                Statement_ImportError(self.tr("Unknown online search source: ") + asset_info['search_online'])
        if asset is None:
            if asset_info.get('should_exist', False):
                raise Statement_ImportError(self.tr("Can't locate asset in statement data: ") + f"'{asset_info}'")
            asset = {"id": self._next_id(JSF.ASSETS)}
            self._uppend_keys_from(asset, asset_info, ['type', 'name', 'country', 'expiry', 'principal'])
            asset[JSF.SYMBOLS] = []
            self._data[JSF.ASSETS].append(asset)
            if 'symbol' in asset_info:
                symbol = {"id": self._next_symbol_id()}
                self._uppend_keys_from(symbol, asset_info, ['symbol', 'currency', 'note'] + self.ID_KEYS)
                asset[JSF.SYMBOLS].append(symbol)
        else:
            if 'type' in asset and asset['type'] != JSF.ASSET_MONEY:
                self.update_asset_data(asset['id'], asset_info)
        return asset['id']

    # Method finds/creates asset in current statement data (same as asset_id()) and pins the exact
    # symbol record that matches asset_info. Returns symbol id.
    # Operations must reference an exact symbol, so any ambiguity here is a hard failure.
    def symbol_id(self, asset_info) -> int:
        asset_id = self.asset_id(asset_info)
        symbols = self._asset(asset_id)[JSF.SYMBOLS]
        if len(symbols) == 1:  # Exactly one symbol exists for the asset - no ambiguity possible
            return symbols[0]['id']
        if asset_info.get('symbol'):
            symbols = [x for x in symbols if x['symbol'] == asset_info['symbol']]
        if asset_info.get('currency'):
            symbols = [x for x in symbols if 'currency' not in x or x['currency'] == asset_info['currency']]
        if len(symbols) != 1:
            raise Statement_ImportError(self.tr("Can't resolve an exact symbol for: ") + f"'{asset_info}': {symbols}")
        return symbols[0]['id']

    # takes key from keys one by one and copies it from src to dst if it exists in src
    def _uppend_keys_from(self, dst, src, keys):
        for key in keys:
            if key in src:
                dst[key] = src[key]

    def update_asset_data(self, asset_id, asset_info):
        asset = self._find_in_list(self._data[JSF.ASSETS], "id", asset_id)
        self._uppend_keys_from(asset, asset_info, ['name', 'country', 'expiry', 'principal'])
        # Identifiers describe the security, not the listing - every symbol of the asset carries
        # them (existing values are never overwritten)
        for symbol in asset[JSF.SYMBOLS]:
            self._uppend_keys_from(symbol, asset_info, self.ID_KEYS)
        # Add new asset symbol if information provided
        if 'symbol' in asset_info:
            symbol_exists = False
            for symbol in asset[JSF.SYMBOLS]:
                if symbol['symbol'] == asset_info['symbol'] and (
                        'currency' not in asset_info or symbol.get('currency') == asset_info['currency']):
                    symbol_exists = True
            if not symbol_exists:
                new_symbol = {"id": self._next_symbol_id()}
                self._uppend_keys_from(new_symbol, asset_info, ['symbol', 'currency', 'note', 'alt_symbol'] + self.ID_KEYS)
                for sibling in asset[JSF.SYMBOLS]:   # inherit security identifiers already known for the asset
                    self._uppend_keys_from(new_symbol, sibling, self.ID_KEYS)
                asset[JSF.SYMBOLS].append(new_symbol)

    # Removes asset and all links to it from self._data (operations link assets via symbol records)
    def remove_asset(self, asset_id):
        asset = self._asset(asset_id)
        for symbol in asset[JSF.SYMBOLS]:
            self._delete_with_id("symbol", symbol['id'])
        self._data[JSF.ASSETS].remove(asset)
        self._id_map[JSF.ASSETS].pop(asset_id, None)

    # Deletes operation if it's 'tag_name' key matches 'value'
    def _delete_with_id(self, tag_name, value):
        operation_sections = [JSF.TRADES, JSF.TRANSFERS, JSF.SWAPS, JSF.BRIDGES, JSF.CONVERSIONS, JSF.CORP_ACTIONS,
                              JSF.ASSET_PAYMENTS, JSF.INCOME_SPENDING]
        for section in operation_sections:
            if section in self._data:
                self._data[section] = [x for x in self._data[section] if not self._key_match(x, tag_name, value)]

    # returns True if dictionary 'element' has 'key' that matches 'value' or is a list with 'value'
    def _key_match(self, element, key, value):
        for tag in element:
            if tag == key:
                if type(element[tag]) == list:
                    for x in element[tag]:
                        if x == value:
                            return True
                else:
                    if element[tag] == value:
                        return True
        return False

    # Removes all keys listed in extra_keys_list from operation_dict
    def drop_extra_fields(self, operation_dict, extra_keys_list):
        for key in extra_keys_list:
            if key in operation_dict:
                del operation_dict[key]
