import logging
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, QDate
from jal.constants import AssetLocation, AssetData, BookAccount, PredefinedAsset, SymbolId
from jal.db.db import JalDB
from jal.db.helpers import format_decimal, year_begin, year_end, day_begin
from jal.db.country import JalCountry
from jal.db.tag import JalTag
from jal.widgets.helpers import ts2d
from jal.universal_cache import UniversalCache


# Helper function to convert db timestamp string into an integer and replace it as 0 if error happens
def db_timestamp2int(timestamp_string: str) -> int:
    try:
        timestamp = int(timestamp_string)
    except ValueError:
        timestamp = 0
    return timestamp


class JalAsset(JalDB):
    db_cache = UniversalCache()
    # Quotes already reported as missing, as the texts that were logged - see _report_missing_quote().
    # Emptied whenever quotes are stored, as that is the only thing that may turn a missing quote into a present one
    # and thus the only moment when a repeat of the message could carry new information.
    _missing_quotes = set()

    def __init__(self, asset_id: int = 0) -> None:
        super().__init__(cached=True)
        try:
            self._id = int(asset_id)
        except (TypeError, ValueError):
            self._id = 0
        self._data = self.db_cache.get_data(self._load_asset_data, (self._id,))  # Load asset data from cache or DB
        self._type = self._data.get('type_id', None)
        self._name = self._data.get('full_name', '')
        self._country = JalCountry(self._data.get('country_id', 0))
        self._expiry = int(self._data.get('data', {}).get(AssetData.ExpiryDate, 0))
        self._principal = self._data.get('data', {}).get(AssetData.PrincipalValue, '')
        self._principal = Decimal(self._principal) if self._principal else Decimal('0')
        self._coin_id = self._data.get('data', {}).get(AssetData.CoinGeckoId, '')
        # Anything unreadable is taken as "not rebasing": the flag adds quantity to a position, so the safe reading
        # of a value nobody can make sense of is the one that changes nothing.
        try:
            self._rebasing = int(self._data.get('data', {}).get(AssetData.Rebasing, 0)) != 0
        except (ValueError, TypeError):
            self._rebasing = False
        try:
            self._tag = JalTag(int(self._data.get('data', {}).get(AssetData.Tag, 0)))
        except (AttributeError, ValueError, TypeError):
            self._tag = JalTag(0)

    def _load_asset_data(self, asset_id: int) -> dict:
        asset_data = {}
        query = self._exec("SELECT * FROM assets WHERE id=:id", [(":id", asset_id)])
        if query.next():
            asset_data = self._read_record(query, named=True)
            asset_data['symbols'] = []
            asset_data['ID'] = {}  # Dictionary of various asset IDs linked to symbols
            # Ordered so that the listings answer in a stable order: tickers() hands out the first of them and
            # symbol() lists them, and neither may say something different from one run to the next
            symbols_query = self._exec("SELECT * FROM asset_symbol WHERE asset_id=:id ORDER BY id",
                                       [(":id", asset_data['id'])])
            while symbols_query.next():
                symbol = self._read_record(symbols_query, named=True)
                del symbol['asset_id']
                asset_data['symbols'].append(symbol)
                id_query = self._exec("SELECT id_type, id_value FROM symbol_ids WHERE symbol_id=:id ORDER BY id_type",
                                        [(":id", symbol['id'])])
                while id_query.next():
                    it_type, id_value = self._read_record(id_query)
                    asset_data['ID'][(symbol['id'], it_type)] = id_value
            extra_data = {}
            data_query = self._exec("SELECT datatype, value FROM asset_data WHERE asset_id=:id ORDER BY datatype",
                                    [(":id", asset_data['id'])])
            while data_query.next():
                datatype, value = self._read_record(data_query)
                extra_data[datatype] = value
            if extra_data:
                asset_data['data'] = extra_data
        return asset_data

    # returns a list of IDs of given type that are defined for this asset
    def _get_id(self, id_type: int) -> list:
        return [value for (key, value) in self._data['ID'].items() if key[1] == id_type]

    def invalidate_cache(self):
        self.db_cache.clear_cache()
        JalAsset._missing_quotes.clear()   # the data behind the reported misses is being re-read as well

    # JalAsset maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Creates a JalAsset object from a symbol id by resolving the owning asset (see also JalSymbol.asset())
    @classmethod
    def from_symbol(cls, symbol_id: int) -> "JalAsset":
        asset_id = cls._read("SELECT asset_id FROM asset_symbol WHERE id=:id", [(":id", symbol_id)])
        return cls(asset_id)

    def dump(self) -> dict:
        return self._data

    def id(self) -> int:
        return self._id

    def type(self) -> int:
        return self._type

    def name(self) -> str:
        return self._name

    # Returns the first identifier of given type found across any of the asset's symbols ('' if not present).
    # For an identifier scoped to a specific listing use JalSymbol.identifier().
    def symbol_id(self, id_type: int) -> str:
        matches = self._get_id(id_type)
        return matches[0] if matches else ''

    # Returns asset symbol for given currency or all symbols if no currency is given.
    # For a specific listing's symbol text use JalSymbol.symbol().
    #
    # A currency alone doesn't always name ONE listing: a blockchain token is a separate active listing per chain
    # (see add_symbol below), so an asset held on several chains has several active listings in one and the same
    # currency. 'location' picks the listing of one chain among them; a location the asset isn't listed on is
    # ignored rather than answered with an empty string, so an account whose chain says nothing about the asset
    # still gets the answer the currency alone gives.
    #
    # Whatever is left is answered by its TICKERS rather than by its listings, which is what keeps several listings
    # of one and the same ticker - a token held on three chains - from being run together into 'USDCUSDCUSDC', a
    # ticker that exists nowhere and reads as if it did. Several DIFFERENT tickers is a real ambiguity (one asset
    # renamed on one chain only, a security quoted under two names) and stays visible as the comma-separated list the
    # no-currency answer above has always been: the caller that needs one listing has to say which, and there is
    # nothing here that could pick for it.
    #
    # This never raises. Several active listings is a state add_symbol() creates on purpose, and this is asked from
    # logging, from tax report builders and from inside Qt model data() - places where an exception costs a download,
    # a document or the process, and where a ticker is being displayed rather than acted on. A caller that STORES
    # what it gets back has to ask tickers() instead and refuse an answer that names more than one.
    def symbol(self, currency: int = None, location: int = None) -> str:
        tickers = self.tickers(currency, location)
        if currency is not None and self._type != PredefinedAsset.Money and len(tickers) > 1:
            logging.warning(self.tr("Asset is listed under several tickers in one currency, "
                                    "the listing has to be named to get one of them: ") + f"{tickers}")
        return ','.join(tickers)   # return symbol or empty string

    # The distinct tickers of this asset's active listings, narrowed by currency and location exactly as symbol()
    # describes above - what symbol() answers with, before they are run together for display. More than one of them
    # is an ambiguity nothing here can resolve, so a caller that acts on the answer rather than showing it looks at
    # the list rather than at the text: a text naming two tickers is a display, and storing it would create a
    # listing under a ticker that exists nowhere.
    def tickers(self, currency: int = None, location: int = None) -> list:
        if not self._data:
            return []
        currency = None if self._type == PredefinedAsset.Money else currency  # Money have one unique symbol
        listings = [x for x in self._data['symbols'] if x['active'] == 1]
        if currency is not None:
            listings = [x for x in listings if x['currency_id'] == currency]
            if location and [x for x in listings if x['location_id'] == location]:
                listings = [x for x in listings if x['location_id'] == location]
        return list(dict.fromkeys(x['symbol'] for x in listings))   # de-duplicated, first listing first

    # Returns list of ids of asset's active symbols
    def active_symbol_ids(self) -> list:
        return [x['id'] for x in self._data.get('symbols', []) if x['active'] == 1]

    # A symbol/identifier write touches both this (asset-keyed) cache and the separate JalSymbol (symbol-keyed)
    # cache - e.g. add_symbol deactivates sibling symbols and add_identifier changes a symbol's identifiers.
    # JalSymbol can't be imported here (it imports JalAsset), so the global invalidation is used to clear every
    # JalDB cache at once (mirrors JalTag.replace_with); this asset's data is then reloaded for continued use.
    def _refresh_after_symbol_write(self) -> None:
        JalDB().invalidate_cache()
        self._data = self.db_cache.get_data(self._load_asset_data, (self._id,))

    # Adds a new symbol to the asset (or returns the existing one's id if it already exists).
    # Returns the id of the resulting asset_symbol row.
    def add_symbol(self, symbol: str, currency_id, location_id: int) -> int:
        # A traditional security is a single listing no matter which venue a statement happens to name (the exchange
        # is informational), so it is matched by (asset, symbol, currency) with the location ignored and the
        # first-seen location kept. A blockchain token is a genuinely separate listing per chain - keyed by its own
        # contract address - so for a chain location the match and the deactivation are scoped by location too, and a
        # new chain adds a second active symbol rather than replacing the existing one.
        on_chain = location_id in AssetLocation.BLOCKCHAINS
        scope = [(":asset_id", self._id), (":currency", currency_id)]
        location_clause = " AND location_id=:location_id" if on_chain else ""
        if on_chain:
            scope.append((":location_id", location_id))
        existing = self._read("SELECT id FROM asset_symbol "
                              "WHERE asset_id=:asset_id AND symbol=:symbol AND currency_id IS :currency" + location_clause,
                              scope + [(":symbol", symbol)], named=True)
        if existing is None:  # Deactivate the superseded symbol(s) and create a new one
            _ = self._exec("UPDATE asset_symbol SET active=0 "
                           "WHERE asset_id=:asset_id AND currency_id IS :currency" + location_clause, scope)
            query = self._exec(
                "INSERT INTO asset_symbol (asset_id, symbol, currency_id, location_id) "
                "VALUES (:asset_id, :symbol, :currency, :location_id)",
                [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id),
                 (":location_id", location_id)])
            new_id = query.lastInsertId() if query is not None else 0
        else:
            new_id = existing['id']
        self._refresh_after_symbol_write()  # add_symbol may deactivate sibling symbols - refresh JalSymbol cache too
        return new_id

    # Attaches an identifier of given type (see SymbolId) to a specific, caller-supplied symbol id.
    # Never guesses which symbol an identifier belongs to - the caller must know it already.
    def add_identifier(self, symbol_id: int, id_type: int, id_value: str) -> None:
        _ = self._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:symbol_id, :id_type, :id_value)",
                       [(":symbol_id", symbol_id), (":id_type", id_type), (":id_value", id_value)])
        self._refresh_after_symbol_write()  # identifiers are part of the JalSymbol cache too - refresh it

    # Adds identifier of given type to given symbol of the asset unless the symbol already has one.
    # An existing identifier is never overwritten - a mismatching new value is only reported as an error.
    def update_identifier(self, symbol_id: int, id_type: int, id_value: str) -> None:
        if not symbol_id:
            logging.error(self.tr("No exact symbol to link identifier with: ")
                          + f"{self.symbol()}: {id_type} = {id_value}")
            return
        existing = self._data['ID'].get((symbol_id, id_type), '')
        if existing:
            if existing != id_value:
                logging.error(self.tr("Unexpected attempt to update identifier for ")
                              + f"{self.symbol()}: {existing} -> {id_value}")
            return
        self.add_identifier(symbol_id, id_type, id_value)

    # Returns country object for the asset
    def country(self) -> JalCountry:
        return self._country

    def country_name(self) -> str:
        return self._country.name()

    # Returns tuple in form of (timestamp:int, quote:Decimal) that contains last found quotation in given currency.
    # Returns (timestamp, 1) if quotation is requested relative to itself
    # Returned timestamp might be less than given.
    # Returns (0, 0) if no quotation information present in db. Return value (timestamp, 0) is a valid quote
    def quote(self, timestamp: int, currency_id: int) -> tuple:
        if self._id == currency_id:
            return timestamp, Decimal('1')
        quote = self._read("SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id "
                           "AND currency_id=:currency_id AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                           [(":asset_id", self._id), (":currency_id", currency_id), (":timestamp", timestamp)])
        if quote is None:
            if self._type == PredefinedAsset.Money and currency_id != self.get_base_currency(timestamp):  # find a cross-rate
                rate1 = self.quote(timestamp, self.get_base_currency(timestamp))[1]
                rate2 = JalAsset(currency_id).quote(timestamp, self.get_base_currency(timestamp))[1]
                rate = 0 if rate2 == Decimal('0') else rate1 / rate2
                return timestamp, rate
            if self._type != PredefinedAsset.Money:
                cross_quote = self._cross_currency_quote(timestamp, currency_id)
                if cross_quote is not None:
                    return cross_quote
            self._report_missing_quote(timestamp, currency_id)
            return 0, Decimal('0')
        return int(quote[0]), Decimal(quote[1])

    # A non-Money asset is often quoted in one currency only while it may be held in an account denominated in
    # any other - crypto sources, for example.
    # The value is taken from the asset's own most recent quote in whatever currency it exists and converted with
    # the Money cross-rate of that currency. Without this the asset values at zero for every consumer - balances,
    # holdings and reports alike - whenever the account currency differs from the currency of the source.
    # Returns None when the asset has no quote at all, leaving the caller to report the miss.
    # Only ever called for a non-Money asset: currencies resolve through the base-currency cross-rate above, and
    # letting a currency in here could recurse endlessly between two currencies that quote each other.
    def _cross_currency_quote(self, timestamp: int, currency_id: int):
        quote = self._read("SELECT timestamp, quote, currency_id FROM quotes WHERE asset_id=:asset_id "
                           "AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                           [(":asset_id", self._id), (":timestamp", timestamp)])
        if quote is None:
            return None
        quote_timestamp, value, quote_currency = int(quote[0]), Decimal(quote[1]), int(quote[2])
        # The pivot is a currency, so this recursion always lands in the Money branch above and never comes back here
        rate = JalAsset(quote_currency).quote(timestamp, currency_id)[1]
        if rate == Decimal('0'):
            return None
        return quote_timestamp, value * rate

    # Reports a quote that is missing, once per asset, currency and date.
    # A single holdings or report calculation asks for the same quote hundreds of times, and repeating an identical
    # line that many times buries every other message in the log instead of telling the user anything new. What has
    # to be said is which asset needs a download, so it is said once and the log stays readable.
    # The asset is named by its ticker in the requested currency when it has one and by any of its tickers when it
    # doesn't: crypto is listed in USD only while the value of a portfolio is asked for in the base currency, so the
    # currency-scoped name of the asset that is missing its quotes is empty exactly when it is needed most.
    def _report_missing_quote(self, timestamp: int, currency_id: int) -> None:
        name = self.symbol(currency_id) or self.symbol() or self._name or f"id={self._id}"
        reported = f"{name} ({JalAsset(currency_id).symbol()}) {ts2d(timestamp)}"
        if reported in self._missing_quotes:
            return
        self._missing_quotes.add(reported)
        logging.warning(self.tr("There are no quote/rate for ") + reported)

    # Return a list of tuples (timestamp:int, quote:Decimal) of all quotes available for asset
    # for time interval begin-end
    # If adjust_splits is True then quotes will be corrected for each split
    def quotes(self, begin: int, end: int, currency_id: int, adjust_splits=False) -> list:
        quotes = []
        splits = {}  # Dictionary of timestamp:coefficient for splits
        if adjust_splits:  # Get all splits recorded for the asset and create and fill the dictionary
            query = self._exec("SELECT a.timestamp, a.qty AS x, r.qty AS y "
                               "FROM asset_actions AS a LEFT JOIN asset_action_results AS r ON a.oid=r.action_id "
                               "LEFT JOIN asset_symbol AS s ON a.symbol_id=s.id "
                               "WHERE s.asset_id=:asset_id AND a.type=:split ORDER BY a.timestamp",
                               [(":asset_id", self._id), (":split", 4)])  #FIXME 4->CorporateAction.Split
            while query.next():
                timestamp, x, y = self._read_record(query, cast=[int, Decimal, Decimal])
                splits[timestamp] = x / y
        query = self._exec(
            "SELECT timestamp, quote FROM quotes WHERE asset_id=:asset_id "
            "AND currency_id=:currency_id AND timestamp>=:begin AND timestamp<=:end ORDER BY timestamp",
            [(":asset_id", self._id), (":currency_id", currency_id), (":begin", begin), (":end", end)])
        while query.next():
            timestamp, quote = self._read_record(query, cast=[int, Decimal])
            quotes.append((timestamp, quote))
        quotes = [(t_q, q * math.prod([splits[t_s] for t_s in splits if day_begin(t_s) > t_q])) for t_q, q in quotes]
        return quotes

    # Returns the timestamp of the earliest ledger record of the asset, or of its earliest operation when the ledger
    # has none, or 0 if the asset was never operated at all.
    # A quote series is only of use from the moment the asset first appears, so this is the natural beginning of the
    # interval to download (see QuoteDownloader._adjust_start).
    # The fallback is what makes that beginning right for an asset the ledger doesn't cover - the ledger ends at its
    # frontier, and an asset acquired beyond it has no ledger record at all (see JalSymbol._symbols_beyond_ledger).
    # Without it such an asset would be downloaded from whatever date the user happened to ask for, which is the one
    # that leaves the operation blocking the ledger unpriced and the ledger stuck exactly where it was.
    def first_operation_timestamp(self) -> int:
        timestamp = self._read("SELECT MIN(timestamp) FROM ledger WHERE asset_id=:asset_id AND book_account=:book",
                               [(":asset_id", self._id), (":book", BookAccount.Assets)])
        if timestamp:
            return db_timestamp2int(timestamp)
        timestamp = self._read("SELECT MIN(o.timestamp) FROM (" + self._OPERATION_SYMBOLS + ") AS o "
                               "LEFT JOIN asset_symbol s ON s.id=o.symbol_id WHERE s.asset_id=:asset_id",
                               [(":asset_id", self._id)])
        return db_timestamp2int(timestamp) if timestamp else 0

    # Returns tuple (begin_timestamp: int, end_timestamp: int) that defines timestamp range for which quotations are
    # available in database for given currency
    def quotes_range(self, currency_id: int) -> tuple:
        try:
            begin, end = self._read("SELECT MIN(timestamp), MAX(timestamp) FROM quotes "
                                    "WHERE asset_id=:asset_id AND currency_id=:currency_id",
                                    [(":asset_id", self._id), (":currency_id", currency_id)])
        except TypeError:
            begin = end = 0
        begin = db_timestamp2int(begin)
        end = db_timestamp2int(end)
        return begin, end

    # Returns the location (see AssetLocation) of the symbol defined for given currency (currency_id can be None).
    # For a specific listing's location use JalSymbol.location().
    def location(self, currency_id: int) -> int:
        location_id = self._read("SELECT location_id FROM asset_symbol "
                                 "WHERE asset_id=:asset AND currency_id IS :currency",
                                 [(":asset", self._id), (":currency", currency_id)])
        return location_id

    # Returns a dict (ID-Name) of all available locations
    @classmethod
    def get_sources_list(cls) -> dict:
        return AssetLocation().get_all_names()

    # Set quotations for given currency_id. Quotations is a list of {'timestamp':int, 'quote':Decimal} values
    def set_quotes(self, quotations: list, currency_id: int) -> None:
        data = [x for x in quotations if x['timestamp'] is not None and x['quote'] is not None]  # Drop Nones
        if data:
            for quote in quotations:
                _ = self._exec("INSERT OR REPLACE INTO quotes (asset_id, currency_id, timestamp, quote) "
                               "VALUES(:asset_id, :currency_id, :timestamp, :quote)",
                               [(":asset_id", self._id), (":currency_id", currency_id),
                                (":timestamp", quote['timestamp']), (":quote", format_decimal(quote['quote']))])
            begin = min(data, key=lambda x: x['timestamp'])['timestamp']
            end = max(data, key=lambda x: x['timestamp'])['timestamp']
            self.commit()
            JalAsset._missing_quotes.clear()   # A quote that was reported as missing may be present now
            logging.info(self.tr("Quotations were updated: ") +
                         f"{self.symbol(currency_id)} ({JalAsset(currency_id).symbol()}) {ts2d(begin)} - {ts2d(end)}")

    # returns expiration timestamp
    def expiry(self) -> int:
        return self._expiry

    # Returns number of days before expiration (negative value if asset is expired)
    def days2expiration(self) -> int:
        if self._expiry == 0:
            return 0
        expiry_date = datetime.fromtimestamp(self._expiry, tz=timezone.utc)
        days_remaining = int((expiry_date - datetime.now(tz=timezone.utc)).total_seconds() / 86400)
        return days_remaining

    def principal(self) -> Decimal:
        return self._principal

    # CoinGecko id of this coin ('polkadot', 'algorand', ...) or '' if none is recorded. It is the identity of a
    # coin that has no contract address on a chain JAL supports (see AssetData.CoinGeckoId) and is what the crypto
    # quote source is keyed by in that case - llama_coin_keys() in the downloader.
    def coin_id(self) -> str:
        return self._coin_id

    # True for a rebasing receipt token - one whose on-chain balance grows with no transfer and no event behind it,
    # so that the ledger is structurally short of the real quantity (see AssetData.Rebasing). It is what decides
    # whether a balance is read from the chain and kept in 'chain_balances' at all: an asset that cannot grow gets no
    # row, which is what keeps that table free of zero deltas.
    def rebasing(self) -> bool:
        return self._rebasing

    def tag(self) -> JalTag:
        return self._tag

    def set_tag(self, tag_id: int) -> None:
        if self._tag.id() == tag_id:
            return
        _ = self._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                       "VALUES(:asset_id, :datatype, :expiry)",
                       [(":asset_id", self._id), (":datatype", AssetData.Tag), (":expiry", str(tag_id))])
        self._tag = JalTag(tag_id)
        self._data = self.db_cache.update_data(self._load_asset_data, (self._id,))  # Reload asset data from DB

    # Updates asset-level data fields with information provided in data dictionary. Per-symbol identifiers
    # (isin/reg_number/cusip) are NOT handled here - they belong to a listing and are written via JalSymbol.
    def update_data(self, data: dict) -> None:
        updaters = {
            'name': self._update_name,
            'country': self._update_country,
            'expiry': self._update_expiration,
            'principal': self._update_principal,
            'coin_id': self._update_coin_id
        }
        if not self._id:
            return
        for key in data:
            if data[key]:
                try:
                    updaters[key](data[key])
                except KeyError:  # No updater for this key is present
                    continue
        self._data = self.db_cache.update_data(self._load_asset_data, (self._id,))  # Reload asset data from DB

    # ------------------------------------------------------------------------------------------------------------------
    # Folds this asset into 'new_id', which is kept, and reports '' when it did or why it did not.
    #
    # Two records of ONE asset happen where a token's identity is a contract address and its ticker is only a label:
    # a coin renamed on one chain (Tether's 'USDT' became 'USD₮0' on Arbitrum) shares no ticker with the asset JAL
    # already holds, so the cross-chain prompt that would have offered the merge never fires and a second asset is
    # created - see Statement._resolve_cross_chain_token(). What the user then holds is one coin counted as two,
    # which no report adds up and no transfer settles across (a transfer moves ONE asset, see
    # TransferSettlement._refusal).
    #
    # What moves is what names the asset. Every operation references a LISTING (asset_symbol.id) rather than an
    # asset, so repointing the listings carries the whole history with them and nothing else has to be rewritten -
    # the trades, transfers, swaps and payments never learn that anything happened.
    #
    # The ledger and everything derived from it is DISCARDED instead of being moved, and the caller has to rebuild.
    # It cannot be kept: deleting the merged asset cascades away its ledger rows, which would leave the running
    # balances of every later row for that asset short of what it had, while the frontier went on claiming the ledger
    # was calculated up to today - a ledger that is silently incomplete rather than visibly absent. Dropping it takes
    # the frontier with it (it is MAX(ledger.timestamp)), so the next rebuild is a full one, exactly as after a
    # restore. This is what the operation tables' own triggers do for a much smaller change.
    #
    # Nothing already stated about the surviving asset is overwritten. Extra data and quotes it lacks are adopted
    # from the one being folded in - the merged asset may be the one whose price was downloaded - while a value the
    # survivor has is kept and a disagreement is reported rather than silently resolved.
    def replace_with(self, new_id: int) -> str:
        refusal = self.refusal_to_replace(new_id)
        if refusal:
            return refusal
        # Adopted first, while the rows still name this asset: a quote or a datatype the survivor already has stays
        # its own, so only what it is missing crosses over. The rest goes with the asset that is deleted.
        self._exec("UPDATE OR IGNORE asset_data SET asset_id=:new_id WHERE asset_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("UPDATE OR IGNORE quotes SET asset_id=:new_id WHERE asset_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("UPDATE asset_symbol SET asset_id=:new_id WHERE asset_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        # ON DELETE CASCADE takes the asset_data and quotes rows that did not cross over (the survivor stated them
        # already), and nothing that names a listing is reached: the listings belong to the other asset now.
        self._exec("DELETE FROM assets WHERE id=:old_id", [(":old_id", self._id)])
        for table in ("trades_closed", "trades_opened", "ledger_totals"):
            self._exec(f"DELETE FROM {table}")
        self._exec("DELETE FROM ledger", commit=True)
        logging.info(self.tr("Assets merged: ") + f"{self._name} -> {JalAsset(new_id).name()}")
        JalDB().invalidate_cache()   # listings moved, so both assets' and both symbols' cached rows are stale
        self._id = 0
        return ''

    # Why this asset cannot be folded into 'new_id', or '' when it can - the same answer replace_with() gives, asked
    # before anything is written, so a chooser can say what a merge would do instead of letting the user try it.
    def refusal_to_replace(self, new_id: int) -> str:
        if not self._id or not new_id:
            return self.tr("one of the assets doesn't exist")
        if self._id == new_id:
            return self.tr("an asset can't be merged into itself")
        target = JalAsset(new_id)
        if not target.name() and not target.tickers():
            return self.tr("the asset to merge into doesn't exist")
        # A currency is what accounts, quotes and the base currency are KEPT IN, not something operations hold, so
        # folding one into another rewrites what every balance is denominated in - a different operation from this
        # one, and not one to reach by way of a token that shares its ticker.
        if self._type == PredefinedAsset.Money or target.type() == PredefinedAsset.Money:
            return self.tr("a currency can't be merged")
        if self._type != target.type():
            return self.tr("the two are assets of different types")
        return ''

    def _update_name(self, new_name: str) -> None:
        if not self._name:
            _ = self._exec("UPDATE assets SET full_name=:new_name WHERE id=:id",
                           [(":new_name", new_name), (":id", self._id)])
            self._name = new_name

    def _update_country(self, new_code: str) -> None:
        if new_code.lower() != self._country.code().lower():
            new_country = JalCountry(data={'code': new_code.lower()}, search=True)
            if new_country.id():
                _ = self._exec("UPDATE assets SET country_id=:new_country_id WHERE id=:asset_id",
                               [(":new_country_id", new_country.id()), (":asset_id", self._id)])
                self._country_id = new_country.id()
                logging.info(self.tr("Country updated for ")
                             + f"{self.symbol()}: {self._country.name()} -> {new_country.name()}")

    def _update_expiration(self, new_expiration: int) -> None:
        _ = self._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                       "VALUES(:asset_id, :datatype, :expiry)",
                       [(":asset_id", self._id), (":datatype", AssetData.ExpiryDate), (":expiry", str(new_expiration))])
        self._expiry = new_expiration

    # Records the CoinGecko id of this coin (see AssetData.CoinGeckoId). Unlike a name or a country it is
    # overwritten when a new value is given: it is not descriptive data but the key a price is downloaded by, so a
    # correction has to take effect.
    def _update_coin_id(self, coin_id: str) -> None:
        if self._type != PredefinedAsset.Crypto:
            return
        _ = self._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                       "VALUES(:asset_id, :datatype, :coin_id)",
                       [(":asset_id", self._id), (":datatype", AssetData.CoinGeckoId), (":coin_id", coin_id)])
        self._coin_id = coin_id

    def _update_principal(self, principal: str) -> None:
        if self._type != PredefinedAsset.Bond:
            return
        try:
            principal = Decimal(principal)
        except InvalidOperation:
            return
        if principal > Decimal('0'):
            _ = self._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                           "VALUES(:asset_id, :datatype, :principal)",
                           [(":asset_id", self._id), (":datatype", AssetData.PrincipalValue),
                            (":principal", str(principal))])

    # Searches for an asset matching the given heuristic data (isin -> reg_number -> symbol(+type+expiry) -> name,
    # in that priority order) and returns a JalAsset for it (whose .id() is 0 if nothing was found).
    @classmethod
    def find(cls, data: dict) -> "JalAsset":
        data = dict(data)   # don't pollute caller's dict with the defaults below
        for key in ('isin', 'name', 'country', 'symbol', 'reg_number', 'cusip'):
            data.setdefault(key, '')
        return cls(cls._find_asset(data))

    @classmethod
    def _find_asset(cls, data: dict) -> int:
        aid = None
        if data['isin']:
            query = cls._exec("SELECT s.asset_id, s.symbol FROM symbol_ids i LEFT JOIN asset_symbol s ON s.id=i.symbol_id WHERE id_type=:datatype AND id_value=:isin",
                               [(":datatype", SymbolId.ISIN), (":isin", data['isin'])])
            while query.next():
                aid, symbol = cls._read_record(query, cast=[int, str])
                if data['symbol'] and data['symbol'] == symbol:  # Try to match by ISIN and symbol first
                    return aid
            if aid is not None:
                return aid
            # Unknown ISIN - fall through to the remaining criteria (callers like _match_asset_symbol
            # guard against ISIN conflicts themselves after the match)
        if data['reg_number']:
            aid = cls._read("SELECT s.asset_id FROM symbol_ids i LEFT JOIN asset_symbol s ON s.id=i.symbol_id WHERE id_type=:datatype AND id_value=:reg_code",
                            [(":datatype", SymbolId.REG_CODE), (":reg_code", data['reg_number'])], check_unique=True)
            if aid is not None:
                return aid
        if data['cusip']:
            aid = cls._read("SELECT s.asset_id FROM symbol_ids i LEFT JOIN asset_symbol s ON s.id=i.symbol_id WHERE id_type=:datatype AND id_value=:cusip",
                            [(":datatype", SymbolId.CUSIP), (":cusip", data['cusip'])], check_unique=True)
            if aid is not None:
                return aid
        if data['symbol']:
            symbols = cls._read_to_list("SELECT s.asset_id, a.type_id, d.value AS expiry FROM asset_symbol s "
                                         "LEFT JOIN assets a ON s.asset_id=a.id "
                                         "LEFT JOIN asset_data d ON s.asset_id=d.asset_id AND d.datatype=:datatype "
                                         "WHERE s.symbol=:symbol COLLATE NOCASE",
                                         [(":datatype", AssetData.ExpiryDate), (":symbol", data['symbol'])], named=True)
            if 'type' in data:
                if 'expiry' in data:
                    def expiry_match(x):  # asset_data values are stored as strings while statement provides int timestamp
                        try:
                            return int(x['expiry']) == int(data['expiry'])
                        except (TypeError, ValueError):
                            return False
                    symbols = list(filter(lambda x: x['type_id'] == data['type'] and expiry_match(x), symbols))
                else:
                    symbols = list(filter(lambda x: x['type_id'] == data['type'], symbols))
            # The ticker has to point at one unambiguous ASSET - not at one row. An asset routinely carries the same
            # ticker in several listings: a security quoted on two venues, or a coin listed both on the chain it is
            # native to and on another chain that holds a wrapped form of it (TRX on Tron and on Ethereum). Those
            # rows all name the same asset, so they are no ambiguity at all; counting them made the second listing
            # look like a conflict and left the asset unmatched - and an import answers an unmatched asset by
            # creating one, so the ledger ended up with two assets for a coin it already had, positions split
            # between them and the two ends of one on-chain transfer no longer recognizable as the same movement.
            # Rows of genuinely different assets are still a conflict and still leave the ticker unresolved.
            asset_ids = {x['asset_id'] for x in symbols}
            if len(asset_ids) == 1:
                aid = asset_ids.pop()
            if aid is not None:
                return aid
        if data['name']:
            aid = cls._read("SELECT id FROM assets WHERE full_name=:name COLLATE NOCASE", [(":name", data['name'])])
        if aid is None:
            return 0
        else:
            return aid

    # Returns the ids of crypto assets that carry an active listing with the given ticker (case-insensitive). Used to
    # spot a possible cross-chain duplicate when a fetched token has no contract-address match but reuses a ticker
    # that a known crypto asset already uses - matching by ticker alone is never safe (tickers are attacker-chosen),
    # so the caller only offers these as candidates for a user-confirmed merge.
    @classmethod
    def get_crypto_assets_by_symbol(cls, symbol: str) -> list:
        asset_ids = []
        query = cls._exec("SELECT DISTINCT s.asset_id FROM asset_symbol s LEFT JOIN assets a ON a.id=s.asset_id "
                          "WHERE s.symbol=:symbol COLLATE NOCASE AND a.type_id=:crypto AND s.active=1",
                          [(":symbol", symbol), (":crypto", PredefinedAsset.Crypto)])
        while query is not None and query.next():
            asset_ids.append(cls._read_record(query, cast=[int]))
        return asset_ids

    # Every crypto asset there is, together with the ticker of an active listing and its name, ordered by name.
    #
    # A ticker match is a good SUGGESTION and a poor filter: a coin renamed on one chain (Tether's 'USDT' is called
    # 'USD₮0' on Arbitrum) shares no ticker with the asset that already holds it, and offering only ticker matches
    # left the user with nothing to merge into and no way to say so. This is what the chooser searches instead.
    @classmethod
    def get_crypto_assets(cls) -> list:
        assets = []
        query = cls._exec("SELECT a.id, a.full_name, "
                          "(SELECT s.symbol FROM asset_symbol s WHERE s.asset_id=a.id AND s.active=1 "
                          "ORDER BY s.id LIMIT 1) AS symbol "
                          "FROM assets a WHERE a.type_id=:crypto ORDER BY a.full_name COLLATE NOCASE",
                          [(":crypto", PredefinedAsset.Crypto)])
        while query is not None and query.next():
            record = cls._read_record(query, named=True)
            assets.append({'id': int(record['id']), 'name': record['full_name'], 'symbol': record['symbol']})
        return assets

    # Method returns a list of JalAsset objects that describe all assets defined in ledger
    @classmethod
    def get_assets(cls) -> list:
        assets = []
        query = cls._exec("SELECT id FROM assets")
        while query.next():
            asset_id = cls._read_record(query, cast=[int])
            assets.append(JalAsset(asset_id))
        return assets

    # Method returns a list of JalAsset objects that describe currencies defined in ledger
    @classmethod
    def get_currencies(cls) -> list:
        currencies = []
        query = cls._exec("SELECT id FROM currencies")
        while query.next():
            currencies.append(JalAsset(super(JalAsset, JalAsset)._read_record(query, cast=[int])))
        return currencies

    # Returns id of the base currency that was in effect for given timestamp or current base currency (for now) if
    # timestamp isn't given
    @classmethod
    def get_base_currency(cls, timestamp: int=None) -> int:
        if timestamp is None:
            timestamp = QDate.currentDate().startOfDay(Qt.UTC).toSecsSinceEpoch()
        base_id = cls._read("SELECT currency_id FROM base_currency WHERE since_timestamp<=:timestamp "
                            "ORDER BY since_timestamp DESC LIMIT 1", [(":timestamp", timestamp)])
        try:
            base_id = int(base_id)
        except TypeError:
            base_id = 0
        return base_id

    # Return a list of (timestamp, currency_id) tuples that represent currency valid currency IDs that were in force
    # after between beginning_of_the_year(begin) and end_of_the_year(end) timestamps.
    # Begin and end of year it required to cover full tax year.
    @classmethod
    def get_base_currency_history(cls, begin: int, end: int) -> list:
        history = [(year_begin(begin), cls.get_base_currency(year_begin(begin)))]
        query = cls._exec("SELECT since_timestamp, currency_id FROM base_currency "
                          "WHERE since_timestamp>:begin AND since_timestamp<=:end ORDER BY since_timestamp",
                          [(":begin", year_begin(begin)), (":end", year_end(end))])
        while query.next():
            history.append(cls._read_record(query, cast=[int, int]))
        return history


# ----------------------------------------------------------------------------------------------------------------------
# Stages a brand-new asset (assets row + symbol(s) + identifiers) before it becomes a real JalAsset.
# Deliberately NOT a JalAsset subclass: JalAsset carries a shared, class-level cache keyed by asset id
# (db_cache / class_cache()), and touching that cache mid-assembly would risk handing an incomplete asset
# to unrelated code that just does JalAsset(id) for some other purpose. This class talks to the DB directly
# and only ever creates a real, cacheable JalAsset once commit() is called.
class JalAssetCreator(JalDB):
    def __init__(self, type_id: int, name: str, country: str = '') -> None:
        super().__init__(cached=False)
        query = self._exec(
            "INSERT INTO assets (type_id, full_name, country_id) "
            "VALUES (:type, :full_name, coalesce((SELECT id FROM countries WHERE code=:country), 0))",
            [(":type", type_id), (":full_name", name), (":country", country)])
        self._id = query.lastInsertId() if query is not None else 0

    def id(self) -> int:
        return self._id

    # Returns the id of the newly created asset_symbol row.
    def add_symbol(self, symbol: str, currency_id, location_id: int) -> int:
        query = self._exec(
            "INSERT INTO asset_symbol (asset_id, symbol, currency_id, location_id) "
            "VALUES (:asset_id, :symbol, :currency, :location_id)",
            [(":asset_id", self._id), (":symbol", symbol), (":currency", currency_id),
             (":location_id", location_id)])
        return query.lastInsertId() if query is not None else 0

    # Attaches an identifier to a specific symbol id (obtained from add_symbol() above) - never guesses.
    def add_identifier(self, symbol_id: int, id_type: int, id_value: str) -> None:
        self._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:symbol_id, :id_type, :id_value)",
                   [(":symbol_id", symbol_id), (":id_type", id_type), (":id_value", id_value)])

    # Finalizes staging and returns a normal, cacheable JalAsset for subsequent use.
    def commit(self) -> JalAsset:
        return JalAsset(self._id)
