import logging
import xml.etree.ElementTree as xml_tree
from datetime import datetime, timedelta, timezone
from jal.widgets.helpers import timestamp_range, dependency_present
from decimal import Decimal
from io import StringIO, BytesIO

import pandas as pd
from pandas.errors import ParserError
import re
import json
from PySide6.QtCore import Qt, QObject, Signal, Slot, QDate
from PySide6.QtWidgets import QApplication, QDialog, QListWidgetItem

from jal.ui.ui_update_quotes_window import Ui_UpdateQuotesDlg
from jal.constants import AssetLocation, PredefinedAsset, SymbolId
from jal.db.asset import JalAsset
from jal.db.helpers import day_begin
from jal.db.symbol import JalSymbol
from jal.net.web_request import WebRequest
from jal.net.moex import MOEX
try:
    from pypdf import PdfReader
    from pypdf.errors import PdfStreamError
except ImportError:
    pass  # PDF files won't be downloaded without dependency

DATA_SOURCE_ROLE = Qt.UserRole + 1

SECONDS_IN_DAY = 86400

# ===================================================================================================================
# Crypto quotes from DeFiLlama (coins.llama.fi) - free and keyless.
# Locations that are priced by this source. They are quoted in USD only, so a single (asset, USD) series is stored
# for a crypto asset no matter which currency its listings or accounts are denominated in - see download_asset_prices().
BLOCKCHAIN_LOCATIONS = AssetLocation.BLOCKCHAINS

# The API identifies a token as '{chain}:{contract_address}' - this maps a location to the chain name that the API
# uses. The identifier that carries the contract address on each chain comes from AssetLocation.address_id_of(),
# which is the single definition shared with the statement importer and the chain fetchers.
_LLAMA_CHAIN_NAMES = {
    AssetLocation.ETH_BLOCKCHAIN: 'ethereum',
    AssetLocation.ARB_BLOCKCHAIN: 'arbitrum',
    AssetLocation.SOL_BLOCKCHAIN: 'solana',
    AssetLocation.TRX_BLOCKCHAIN: 'tron',
    AssetLocation.HL_BLOCKCHAIN: 'hyperliquid'
}

# Native coin of each chain, used for a listing that has no contract address. Mind that a listing on Arbitrum with
# no address is bridged ETH (the gas token of that chain) and not the ARB token - the latter is a contract and thus
# resolved via _LLAMA_CHAINS above. Bitcoin has no token contracts at all and is always native.
_LLAMA_NATIVE_COINS = {
    AssetLocation.ETH_BLOCKCHAIN: "coingecko:ethereum",
    AssetLocation.ARB_BLOCKCHAIN: "coingecko:ethereum",
    AssetLocation.BTC_BLOCKCHAIN: "coingecko:bitcoin",
    AssetLocation.SOL_BLOCKCHAIN: "coingecko:solana",
    AssetLocation.TRX_BLOCKCHAIN: "coingecko:tron"
}

# Number of daily points requested in one '/chart' call. Verified 2026-07-18: a span of 500 is served but 1000 is
# rejected, so longer intervals are downloaded in several chunks with some headroom left.
_LLAMA_MAX_SPAN = 365

# How far the API may look around a requested point to find a price. A wide window may repeat the same price for
# several days for a thinly traded token, which is still preferable to having no quote at all.
_LLAMA_SEARCH_WIDTH = '4h'

# Prices that the API reports with a lower confidence are dropped instead of being stored as a valid quote
_LLAMA_MIN_CONFIDENCE = Decimal('0.7')


# Every DeFiLlama coin key worth trying for a given listing, in the order they should be tried; empty if the
# listing doesn't belong to a supported blockchain.
#
# A listing normally has exactly one key. Hyperliquid is the exception: the API indexes it inconsistently - most of
# its tokens answer to their HyperEVM contract address (UBTC, USOL, USDT0, ...) while a few - among them USDC, and
# HYPE which has no EVM deployment at all - answer only to the HyperCore token id. Neither form covers the chain on
# its own, so a Hyperliquid symbol carries both identifiers and both keys are offered. The EVM address goes first
# as it is the form that resolves for the majority of tokens.
def llama_coin_keys(symbol: JalSymbol) -> list:
    chain = _LLAMA_CHAIN_NAMES.get(symbol.location(), '')
    keys = []
    if chain:
        if symbol.location() == AssetLocation.HL_BLOCKCHAIN:
            evm_address = symbol.identifier(SymbolId.HL_EVM_ADDRESS)
            if evm_address:
                keys.append(f"{chain}:{evm_address}")
        address = symbol.identifier(AssetLocation.address_id_of(symbol.location()))
        if address:
            keys.append(f"{chain}:{address}")
    if not keys:
        native = _LLAMA_NATIVE_COINS.get(symbol.location(), '')
        if native:
            keys.append(native)
    return keys


# The primary DeFiLlama coin key of a listing, or '' if it has none
def llama_coin_key(symbol: JalSymbol) -> str:
    keys = llama_coin_keys(symbol)
    return keys[0] if keys else ''


# Converts a '/chart' API answer into a dataframe of daily quotes (Date index, Close values), dropping low
# confidence points. It is a pure function of the downloaded data, so it may be tested with a stored sample.
def parse_llama_chart(content, coin_key: str) -> pd.DataFrame:
    quotes = []
    try:  # parse_float keeps full precision of a price as it was given in the answer
        coin = json.loads(content, parse_float=Decimal)['coins'][coin_key]
        prices = coin['prices']
    except (json.decoder.JSONDecodeError, KeyError, TypeError):
        return pd.DataFrame([], columns=["Date", "Close"]).set_index("Date")
    # '/chart' reports one confidence value for the whole coin while '/batchHistorical' gives it per point,
    # so a point value is taken when present and the value of the coin is used otherwise.
    confidence = coin.get('confidence', 1)
    for point in prices:
        try:
            if Decimal(point.get('confidence', confidence)) < _LLAMA_MIN_CONFIDENCE:
                continue
            # Answer timestamps drift around the requested time and a point of one day may come back as 23:59:5x
            # of the previous one. As a quote is stored at the beginning of a day each point is put to the
            # midnight that is nearest to it, not to the midnight of the day it formally belongs to.
            timestamp = day_begin(int(point['timestamp']) + SECONDS_IN_DAY // 2)
            quotes.append({"Date": datetime.fromtimestamp(timestamp, tz=timezone.utc),
                           "Close": Decimal(point['price'])})
        except (KeyError, TypeError, ArithmeticError):
            continue  # Skip a malformed point rather than lose the whole answer
    data = pd.DataFrame(quotes, columns=["Date", "Close"])
    data = data.drop_duplicates(subset="Date", keep="first").set_index("Date")
    return data.sort_index()


# ===================================================================================================================
# UI dialog class
# ===================================================================================================================
class QuotesUpdateDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.ui = Ui_UpdateQuotesDlg()
        self.ui.setupUi(self)
        self._updating_all_sources = False
        self._all_sources_state_before_click = Qt.Unchecked
        self.ui.StartDateEdit.setDate(QDate.currentDate().addMonths(-1))
        self.ui.EndDateEdit.setDate(QDate.currentDate())
        sources = JalAsset.get_sources_list()
        for source in sources:
            item = QListWidgetItem(sources[source], self.ui.SourcesList)
            item.setData(DATA_SOURCE_ROLE, source)
            item.setCheckState(Qt.Checked)
            self.ui.SourcesList.addItem(item)
        self.ui.SourcesList.itemChanged.connect(self._on_sources_item_changed)
        self.ui.AllSourcesCheck.pressed.connect(self._on_all_sources_pressed)
        self.ui.AllSourcesCheck.clicked.connect(self._on_all_sources_clicked)
        self._sync_all_sources_check()

        # center dialog with respect to parent window
        x = parent.x() + parent.width() / 2 - self.width() / 2
        y = parent.y() + parent.height() / 2 - self.height() / 2
        self.setGeometry(x, y, self.width(), self.height())

    def getStartDate(self):
        return self.ui.StartDateEdit.dateTime().toSecsSinceEpoch()

    def getEndDate(self):
        return self.ui.EndDateEdit.dateTime().toSecsSinceEpoch()

    # Returns a list that contains IDs of all checked data sources
    def getSourceList(self):
        checked = []
        for item_index in range(self.ui.SourcesList.count()):
            item = self.ui.SourcesList.item(item_index)
            if item.checkState() == Qt.Checked:
                checked.append(item.data(DATA_SOURCE_ROLE))
        return checked

    @Slot(QListWidgetItem)
    def _on_sources_item_changed(self, _item):
        if self._updating_all_sources:
            return
        self._sync_all_sources_check()

    @Slot()
    def _on_all_sources_pressed(self):
        self._all_sources_state_before_click = self.ui.AllSourcesCheck.checkState()

    @Slot(bool)
    def _on_all_sources_clicked(self, _checked):
        if self._updating_all_sources:
            return
        target_state = Qt.Unchecked if self._all_sources_state_before_click == Qt.Checked else Qt.Checked
        self._updating_all_sources = True
        try:
            for item_index in range(self.ui.SourcesList.count()):
                self.ui.SourcesList.item(item_index).setCheckState(target_state)
        finally:
            self._updating_all_sources = False
        self._sync_all_sources_check()

    def _sync_all_sources_check(self):
        checked_count = 0
        item_count = self.ui.SourcesList.count()
        for item_index in range(item_count):
            if self.ui.SourcesList.item(item_index).checkState() == Qt.Checked:
                checked_count += 1

        self._updating_all_sources = True
        try:
            if checked_count == 0:
                self.ui.AllSourcesCheck.setCheckState(Qt.Unchecked)
            elif checked_count == item_count:
                self.ui.AllSourcesCheck.setCheckState(Qt.Checked)
            else:
                self.ui.AllSourcesCheck.setCheckState(Qt.PartiallyChecked)
        finally:
            self._updating_all_sources = False


# ===================================================================================================================
# Worker class
# ===================================================================================================================
# noinspection SpellCheckingInspection
class QuoteDownloader(QObject):
    download_completed = Signal()
    show_progress = Signal(bool)     # Signal is emitted when downloader wants to start or stop display progress
    update_progress = Signal(float)  # Signal is emitted to report current % of execution

    def __init__(self):
        super().__init__()
        self._request = None
        self._pending = []   # Requests abandoned by a cancelled download, see _wait_for_event()
        self._cancelled = False
        self._cbr_codes = None
        self._victoria_quotes = []
        self._victoria_date = None

    @Slot()
    def on_cancel(self):
        self._cancelled = True

    # Blocks until the requests abandoned by a cancelled download are over. Must be called before the
    # application quits - destroying a running QThread aborts the process.
    def wait_for_pending(self) -> None:
        for request in self._pending:
            request.wait()
        self._pending = []

    # this method waits for completion of downloading process or for user interrupt (in this case exception is raised)
    def _wait_for_event(self):
        self._pending = [x for x in self._pending if x.isRunning()]
        while self._request.isRunning():
            QApplication.processEvents()
            if self._cancelled:
                # An interrupted request can't be stopped: WebRequest is a QThread with an overridden run() that
                # blocks in 'requests', so it has no event loop for quit() to end. Dropping it isn't an option
                # either - destroying a running QThread aborts the application. So it is kept aside until it
                # completes on its own and is only released later, when it is no longer running.
                self._pending.append(self._request)
                self._request = None
                raise KeyboardInterrupt

    def showQuoteDownloadDialog(self, parent):
        dialog = QuotesUpdateDialog(parent)
        if dialog.exec():
            self.DownloadData(dialog.getStartDate(), dialog.getEndDate(), dialog.getSourceList())
            self.download_completed.emit()

    def DownloadData(self, start_timestamp, end_timestamp, sources_list):
        self._cancelled = False
        self.show_progress.emit(True)
        try:
            if AssetLocation.BANK_ACCOUNT in sources_list:
                self.download_currency_rates(start_timestamp, end_timestamp)
            self.download_asset_prices(start_timestamp, end_timestamp, sources_list)
        except KeyboardInterrupt:
            logging.warning(self.tr("Interrupted by user"))
        finally:
            self.show_progress.emit(False)
        if not self._cancelled:
            logging.info(self.tr("Download completed"))

    # Checks for present quotations of 'asset' in given 'currency' and adjusts 'start' timestamp to be at
    # the end of available quotes interval if needed.
    def _adjust_start(self, asset: JalAsset, currency_id: int, start) -> int:
        quotes_begin, quotes_end = asset.quotes_range(currency_id)
        if start < quotes_begin:
            from_timestamp = start
        else:
            from_timestamp = quotes_end if quotes_end > start else start
        return from_timestamp

    def _store_quotations(self, asset: JalAsset, currency_id: int, data: pd.DataFrame) -> None:
        if data is not None:
            data.dropna(inplace=True)
            quotations = []
            for date, quote in data.iterrows():  # Date in pandas dataset is in UTC by default
                quotations.append({'timestamp': int(date.timestamp()), 'quote': quote['Close']})
            asset.set_quotes(quotations, currency_id)

    def download_currency_rates(self, start_timestamp, end_timestamp):
        data_loaders = {
            "RUB": self.CBR_DataReader,
            "EUR": self.ECB_DataReader
        }
        currencies = [x for x in JalAsset.get_currencies() if x.location(None) == AssetLocation.BANK_ACCOUNT]
        for base in set([x[1] for x in JalAsset.get_base_currency_history(start_timestamp, end_timestamp)]):
            base_symbol = JalAsset(base).symbol()
            logging.info(self.tr("Loading currency rates for " + base_symbol))
            for i, currency in enumerate([x for x in currencies if x.id() != base]):  # base currency rate is always 1
                if self._cancelled:
                    raise KeyboardInterrupt
                from_timestamp = self._adjust_start(currency, base, start_timestamp)
                try:
                    if from_timestamp <= end_timestamp:
                        data = data_loaders[base_symbol](currency, from_timestamp, end_timestamp)
                        self._store_quotations(currency, base, data)
                except (xml_tree.ParseError, pd.errors.EmptyDataError, KeyError):
                    logging.warning(self.tr("No rates were downloaded for ") + f"{currency.symbol()}/{base_symbol}")
                    continue
                self.update_progress.emit(100.0 * (i+1) / len(currencies))

    def download_asset_prices(self, start_timestamp, end_timestamp, sources_list):
        data_loaders = {
            AssetLocation.MOEX_EXCHANGE: self.MOEX_DataReader,
            AssetLocation.EURONEXT_EXCHANGE: self.Euronext_DataReader,
            AssetLocation.NYSE_EXCHANGE: self.Yahoo_Downloader,
            AssetLocation.NASDAQ_EXCHANGE: self.Yahoo_Downloader,
            AssetLocation.TMX_EXCHANGE: self.TMX_Downloader,
            AssetLocation.LSE_EXCHANGE: self.YahooLSE_Downloader,
            AssetLocation.FRA_EXCHANGE: self.YahooFRA_Downloader,
            AssetLocation.SMA_VICTORIA: self.Victoria_Downloader,
            AssetLocation.MILAN_EXCHANGE: self.EuronextMilan_DataReader,
            AssetLocation.WSE_EXCHANGE: self.Stooq_DataReader
        }
        data_loaders.update({x: self.Llama_Downloader for x in BLOCKCHAIN_LOCATIONS})
        symbols = JalSymbol.get_active_symbols(start_timestamp, end_timestamp)
        symbols = [(x['symbol'], x['currency']) for x in symbols if x['symbol'].location() in sources_list]
        symbols = self._quote_series(symbols)
        logging.info(self.tr("Loading assets prices"))
        for i, (symbol, currency) in enumerate(symbols):
            from_timestamp = self._adjust_start(symbol.asset(), currency, start_timestamp)
            try:
                if from_timestamp <= end_timestamp:
                    data = data_loaders[symbol.location()](symbol, currency, from_timestamp, end_timestamp)
                    self._store_quotations(symbol.asset(), currency, data)
            except (pd.errors.EmptyDataError, KeyError, json.decoder.JSONDecodeError):
                logging.warning(self.tr("No quotes were downloaded for ") + f"{symbol.symbol()}")
                continue
            self.update_progress.emit(100.0 * (i + 1) / len(symbols))

    # Takes a list of (symbol, account currency) pairs and returns a list of (symbol, quote currency) pairs that
    # describe the quote series to download - one pair per series.
    # Quotes are stored per (asset, currency) while an asset may have several listings, so listings that share a
    # series have to be collapsed into one download. Blockchain sources are quoted in USD only, which means that
    # all listings of a crypto asset share a single USD series regardless of the currency of the account holding
    # it; for other sources listings in different currencies are separate series and are all kept.
    def _quote_series(self, symbols: list) -> list:
        usd = [x.id() for x in JalAsset.get_currencies() if x.symbol() == 'USD']
        series = []
        stored = set()
        for symbol, currency in symbols:
            if symbol.location() in BLOCKCHAIN_LOCATIONS:
                if not usd:
                    logging.warning(self.tr("Can't store crypto quotes as there is no USD currency in the ledger: ")
                                    + f"{symbol.symbol()}")
                    continue
                currency = usd[0]
            if (symbol.asset().id(), currency) in stored:
                continue
            stored.add((symbol.asset().id(), currency))
            series.append((symbol, currency))
        return series

    def PrepareRussianCBReader(self):
        rows = []
        self._request = WebRequest(WebRequest.GET, "http://www.cbr.ru/scripts/XML_valFull.asp")
        self._wait_for_event()
        try:
            xml_root = xml_tree.fromstring(self._request.data())
            for node in xml_root:
                code = node.find("ParentCode").text.strip() if node is not None else None
                iso = node.find("ISO_Char_Code").text if node is not None else None
                rows.append({"ISO_name": iso, "CBR_code": code})
        except xml_tree.ParseError:
            pass
        self._cbr_codes = pd.DataFrame(rows, columns=["ISO_name", "CBR_code"])

    # Empty method to make a unified call for any asset
    def Dummy_DataReader(self, _asset, _currency_id, _start_timestamp, _end_timestamp):
        return None

    def CBR_DataReader(self, currency, start_timestamp, end_timestamp):
        if self._cbr_codes is None:
            self.PrepareRussianCBReader()
        try:
            code = str(self._cbr_codes.loc[self._cbr_codes["ISO_name"] == currency.symbol(), "CBR_code"].values[0]).strip()
        except IndexError:
            logging.debug(self.tr("There are no CBR data for: ") + f"{currency.symbol()}")
            return None
        params = {
            'date_req1': datetime.fromtimestamp(start_timestamp, tz=timezone.utc).strftime('%d/%m/%Y'),
            'date_req2': (datetime.fromtimestamp(end_timestamp, tz=timezone.utc) + timedelta(days=1)).strftime('%d/%m/%Y'), # add 1 day to end_timestamp as CBR sets rate are a day ahead
            'VAL_NM_RQ': code
        }
        url = "http://www.cbr.ru/scripts/XML_dynamic.asp"
        self._request = WebRequest(WebRequest.GET, url, params=params)
        self._wait_for_event()
        xml_root = xml_tree.fromstring(self._request.data())
        rows = []
        for node in xml_root:
            s_date = node.attrib['Date'] if node is not None else None
            s_val = node.find("Value").text if node is not None else None
            s_multiplier = node.find("Nominal").text if node is not None else 1
            rows.append({"Date": s_date, "Close": s_val, "Multiplier": s_multiplier})
        data = pd.DataFrame(rows, columns=["Date", "Close", "Multiplier"])
        data['Date'] = pd.to_datetime(data['Date'], format="%d.%m.%Y", utc=True)
        data['Close'] = [x.replace(',', '.') for x in data['Close']]
        data['Close'] = data['Close'].apply(Decimal)
        data['Multiplier'] = data['Multiplier'].apply(Decimal)
        data['Close'] = data['Close'] / data['Multiplier']
        data.drop('Multiplier', axis=1, inplace=True)
        rates = data.set_index("Date")
        return rates

    def ECB_DataReader(self, currency, start_timestamp, end_timestamp):
        url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{currency.symbol()}.EUR.SP00.A"
        params = {
            'startPeriod': datetime.fromtimestamp(start_timestamp, tz=timezone.utc).strftime('%Y-%m-%d'),
            'endPeriod': datetime.fromtimestamp(end_timestamp, tz=timezone.utc).strftime('%Y-%m-%d')
        }
        self._request = WebRequest(WebRequest.GET, url, params=params, headers={'Accept': 'text/csv'})
        self._wait_for_event()
        file = StringIO(self._request.data())
        try:
            data = pd.read_csv(file, dtype={'TIME_PERIOD': str, 'OBS_VALUE': str})
        except ParserError:
            return None
        data.rename(columns={'TIME_PERIOD': 'Date', 'OBS_VALUE': 'Close'}, inplace=True)
        data = data[['Date', 'Close']]  # Keep only required columns
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d", utc=True)
        data['Close'] = data['Close'].apply(Decimal)   # Convert from str to Decimal
        data['Close'] = Decimal('1') / data['Close']
        data['Close'] = data['Close'].apply(round, args=(10, ))
        rates = data.set_index("Date")
        return rates

    # noinspection PyMethodMayBeStatic
    def MOEX_DataReader(self, symbol, currency_id, start_timestamp, end_timestamp, update_symbol=True):
        currency = JalAsset(currency_id).symbol()
        moex_info = MOEX().asset_info(symbol=symbol.symbol(), isin=symbol.identifier(SymbolId.ISIN), currency=currency, special=True)
        if not ('engine' in moex_info and 'market' in moex_info and 'board' in moex_info) or \
                (moex_info['engine'] is None) or (moex_info['market'] is None) or (moex_info['board'] is None):
            logging.warning(f"Failed to find {symbol.symbol()} ({symbol.identifier(SymbolId.ISIN)}) on moex.com")
            return None
        if (moex_info['market'] == 'bonds') and (moex_info['board'] in ['TQCB', 'TQIR']):
            asset_code = symbol.identifier(SymbolId.ISIN)   # Corporate bonds are quoted by ISIN
        elif (moex_info['market'] == 'shares') and (moex_info['board'] == 'TQIF'):
            asset_code = symbol.identifier(SymbolId.ISIN)   # ETFs are quoted by ISIN
        else:
            asset_code = symbol.symbol()
        if update_symbol:
            isin = moex_info['isin'] if 'isin' in moex_info else ''
            reg_number = moex_info['reg_number'] if 'reg_number' in moex_info else ''
            expiry = moex_info['expiry'] if 'expiry' in moex_info else 0
            principal = moex_info['principal'] if 'principal' in moex_info else 0
            details = {'isin': isin, 'reg_number': reg_number, 'expiry': expiry, 'principal': principal}
            symbol.update_data(details)
        # Get price history
        url = f"http://iss.moex.com/iss/history/engines/{moex_info['engine']}/markets/{moex_info['market']}/" \
              f"boards/{moex_info['board']}/securities/{asset_code}.json"
        params = {
            'from': datetime.fromtimestamp(start_timestamp, tz=timezone.utc).strftime('%Y-%m-%d'),
            'till': datetime.fromtimestamp(end_timestamp, tz=timezone.utc).strftime('%Y-%m-%d')
        }
        self._request = WebRequest(WebRequest.GET, url, params=params)
        self._wait_for_event()
        moex_data = json.loads(self._request.data())
        if 'history' not in moex_data:
            return None
        quotes_data = [dict(zip(moex_data['history']['columns'], x)) for x in moex_data['history']['data']]
        quotes = []
        for x in quotes_data:
            if x['CLOSE']:   # CLOSE field is numeric, it gives a lot of digits after direct conversion to Decimal, so we treat it as a string
                price = Decimal(str(x['CLOSE'])) * Decimal(str(x['FACEVALUE'])) / Decimal('100') if 'FACEVALUE' in x else x['CLOSE']
                quotes.append({"Date": x['TRADEDATE'], "Close": str(price)})
        data = pd.DataFrame(quotes, columns=["Date", "Close"])
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d", utc=True)
        data['Close'] = data['Close'].apply(Decimal)
        close = data.set_index("Date")
        return close

    # noinspection PyMethodMayBeStatic
    def Yahoo_Downloader(self, symbol, currency_id, start_timestamp, end_timestamp, suffix=''):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.symbol()+suffix}"
        params = {
            'period1': start_timestamp,
            'period2': end_timestamp,
            'interval': '1d'
        }
        self._request = WebRequest(WebRequest.GET, url, params=params)
        self._wait_for_event()
        web_data = json.loads(self._request.data())
        web_data = web_data['chart']
        if web_data['error'] is not None:
            logging.error(self.tr("Yahoo returned and error: ") + web_data['error'])
            return []
        if len(web_data['result']) != 1:
            logging.error(self.tr("Yahoo returned more then one result: ") + web_data['result'])
            return []
        timestamps = [datetime.fromtimestamp(x, tz=timezone.utc) for x in web_data['result'][0]['timestamp']]
        closes = web_data['result'][0]['indicators']['quote'][0]['close']
        try:
            data = pd.DataFrame({'Date': timestamps, 'Close': closes})
        except ParserError:
            return None
        data['Close'] = data['Close'].apply(Decimal)
        close = data.set_index("Date")
        return close

    # The same as Yahoo_Downloader but it adds ".L" suffix to asset_code and returns prices in GBP
    def YahooLSE_Downloader(self, symbol, currency_id, start_timestamp, end_timestamp):
        return self.Yahoo_Downloader(symbol, currency_id, start_timestamp, end_timestamp, suffix='.L')

    # The same as Yahoo_Downloader but it adds ".F" suffix to asset_code and returns prices in EUR
    def YahooFRA_Downloader(self, symbol, currency_id, start_timestamp, end_timestamp):
        return self.Yahoo_Downloader(symbol, currency_id, start_timestamp, end_timestamp, suffix='.F')

    # noinspection PyMethodMayBeStatic
    def Euronext_DataReader(self, symbol, currency_id, start_timestamp, end_timestamp):
        suffix = "ETFP" if symbol.asset().type() == PredefinedAsset.ETF else "BGEM"  # Dates don't work for ETFP due to glitch on their site, 'BGEM' - global equity market
        url = f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{symbol.identifier(SymbolId.ISIN)}-{suffix}"
        params = {
            'format': 'csv',
            'decimal_separator': '.',
            'date_form': 'd/m/Y',
            'op': '',
            'adjusted': 'N',
            'base100': '',
            'startdate': datetime.fromtimestamp(start_timestamp, tz=timezone.utc).strftime('%Y-%m-%d'),
            'enddate': datetime.fromtimestamp(end_timestamp, tz=timezone.utc).strftime('%Y-%m-%d')
        }
        self._request = WebRequest(WebRequest.GET, url, params=params)
        self._wait_for_event()
        quotes = self._request.data()
        quotes_text = quotes.replace(u'\ufeff', '').splitlines()    # Remove BOM from the beginning
        if len(quotes_text) < 4:
            logging.warning(self.tr("Euronext quotes history reply is too short: ") + quotes)
            return None
        if quotes_text[0] != '"Historical Data"':
            logging.warning(self.tr("Euronext quotes header not found in: ") + quotes)
            return None
        if quotes_text[2] != symbol.identifier(SymbolId.ISIN):
            logging.warning(self.tr("Euronext quotes ISIN mismatch in: ") + quotes)
            return None
        quotes_text = [x.replace("'", "") for x in quotes_text]   # Some lines have occasional quote in some places
        quotes = "\n".join(quotes_text)
        file = StringIO(quotes)
        try:
            data = pd.read_csv(file, header=3, sep=';', dtype={'Date': str, 'Close': str}, index_col=False)
        except ParserError:
            return None
        data['Date'] = pd.to_datetime(data['Date'], format="%d/%m/%Y", utc=True)
        data = data[data.Date >= datetime.fromtimestamp(start_timestamp, tz=timezone.utc)]   # There is a bug on Euronext side - it returns full set regardless of date
        data = data[data.Date <= datetime.fromtimestamp(end_timestamp, tz=timezone.utc)]
        data['Close'] = data['Close'].apply(Decimal)
        data = data.drop(columns=['Open', 'High', 'Low', 'Last', 'Number of Shares', 'Number of Trades', 'Turnover', 'vwap'],
                         errors='ignore')  # Ignore errors as some columns might be missing
        close = data.set_index("Date")
        close.sort_index(inplace=True)
        return close

    # noinspection PyMethodMayBeStatic
    def EuronextMilan_DataReader(self, symbol, currency_id, start_timestamp, end_timestamp):
        suffix = "ETF" if symbol.asset().type() == PredefinedAsset.ETF else "MTA"
        url = "https://charts.borsaitaliana.it/charts/services/ChartWService.asmx/GetPricesWithVolume"
        params = {
            "request": {
                "SampleTime":"1d",
                "TimeFrame":None,
                "RequestedDataSetType":"ohlc",
                "ChartPriceType":"price",
                "Key": symbol.symbol() + "." + suffix,
                "OffSet":0,
                "FromDate":start_timestamp,
                "ToDate":end_timestamp,
                "UseDelay":False,
                "KeyType":"Topic",
                "KeyType2":"Topic",
                "Language":"en-US"
            }
        }
        self._request = WebRequest(WebRequest.POST_JSON, url, params=params, headers={'Accept': 'text/csv'})
        self._wait_for_event()
        json_content = json.loads(self._request.data())
        if 'd' not in json_content:
            return None
        data = pd.DataFrame(json_content['d'], columns=["Date", "Unk", "O", "H", "L", "Close", "V"])
        data = data.drop(columns=["Unk", "O", "H", "L", "V"], errors='ignore')
        data['Date'] = pd.to_datetime(data['Date'], unit='ms', utc=True)
        data['Close'] = data['Close'].astype('str').apply(Decimal)
        close = data.set_index("Date")
        close.sort_index(inplace=True)
        return close

    # noinspection PyMethodMayBeStatic
    def TMX_Downloader(self, symbol, _currency_id, start_timestamp, end_timestamp):
        url = 'https://app-money.tmx.com/graphql'
        params = {
            "operationName": "getCompanyPriceHistoryForDownload",
            "variables":
                {
                    "symbol": symbol.symbol(),
                    "start": datetime.fromtimestamp(start_timestamp, tz=timezone.utc).strftime('%Y-%m-%d'),
                    "end": datetime.fromtimestamp(end_timestamp, tz=timezone.utc).strftime('%Y-%m-%d'),
                    "adjusted": False,
                    "adjustmentType": None,
                    "unadjusted": True
                },
            "query": "query getCompanyPriceHistoryForDownload($symbol: String!, $start: String, $end: String, $adjusted: Boolean, $adjustmentType: String, $unadjusted: Boolean) "
                     "{getCompanyPriceHistoryForDownload(symbol: $symbol, start: $start, end: $end, adjusted: $adjusted, adjustmentType: $adjustmentType, unadjusted: $unadjusted) "
                     "{ datetime closePrice}}"
        }
        self._request = WebRequest(WebRequest.POST_JSON, url, params=params)
        self._wait_for_event()
        json_content = json.loads(self._request.data())
        result_data = json_content['data'] if 'data' in json_content else None
        if 'getCompanyPriceHistoryForDownload' in result_data:
            price_array = result_data['getCompanyPriceHistoryForDownload']
        else:
            logging.warning(self.tr("Can't parse data for TSX quotes: ") + json_content)
            return None
        data = pd.DataFrame(price_array)
        data.rename(columns={'datetime': 'Date', 'closePrice': 'Close'}, inplace=True)
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d", utc=True)
        data['Close'] = data['Close'].apply(str)   # Convert from float to str
        data['Close'] = data['Close'].apply(Decimal)   # Convert from str to Decimal
        close = data.set_index("Date")
        close.sort_index(inplace=True)
        return close

    def Victoria_Downloader(self, symbol, _currency_id, _start_timestamp, _end_timestamp):
        quotes = self._get_victoria_quotes()
        if not quotes:
            return None
        # Filter asset price
        asset_quotes = [x for x in quotes if x['name'] == symbol.asset().name()]
        if len(asset_quotes) != 1:
            logging.warning(self.tr("Can't find quote for Victoria Seguros fund: ") + symbol.asset().name())
            return None
        data = pd.DataFrame([{'Date': self._victoria_date, 'Close': asset_quotes[0]['price']}])
        close = data.set_index("Date")
        return close

    def _get_victoria_quotes(self) -> list:
        months = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro',
                  'novembro', 'dezembro']
        if self._victoria_quotes:
            return self._victoria_quotes
        if not dependency_present(['pypdf']):
            logging.warning(self.tr("Package pypdf not found for PDF parsing."))
            return []
        # Download PDF-file with current quotes
        self._request = WebRequest(WebRequest.GET, "https://www.victoria-seguros.pt/cdu-services/UNIDADES_PARTICIPACAO_VIDA_OPC1_UP", binary=True)
        self._wait_for_event()
        pdf_data = self._request.data()
        if not pdf_data:
            return []
        try:
            pdf = PdfReader(BytesIO(pdf_data))
        except PdfStreamError:
            logging.error(self.tr("Can't parse server response as pdf: ") + str(pdf_data))
            return []
        if len(pdf.pages) != 1:
            logging.warning(self.tr("Unexpected number of pages in Victoria Seguros document: ") + len(pdf.pages))
            return []
        # Get text from downloaded PDF-file together with font type and font size of each text fragment
        parts = []
        def visitor_body(text, cm, tm, font_dict, font_size):
            font = {} if font_dict is None else font_dict
            if text:
                parts.append({'size': font_size, 'font': font['/BaseFont'], 'text': text})
        pdf.pages[0].extract_text(visitor_text=visitor_body)
        # Combine text fragments into lines according to line breaks and font changes
        lines = []
        line = ''
        font = ''
        for part in parts:
            if part['text'] == '\n':
                lines.append(line)
                line = ''
                continue
            if part['font'] != font:
                font = part['font']
                if line:
                    lines.append(line)
                line = part['text']
                continue
            line += part['text']
        # Get quote date
        match = re.match(r"(\d\d?) de (\w+) de (\d\d\d\d)", lines[-1])
        if match is None:
            logging.warning(self.tr("Can't parse date from Victoria Seguros file"))
            return []
        day, month, year = match.groups()
        self._victoria_date = datetime(int(year), months.index(month) + 1, int(day))
        # Get quotation lines from the file
        self._victoria_quotes = []
        for line in lines:
            match = re.match(r"(.*) EUR (\d+[,.]\d+)", line)
            if match is None:
                continue
            fund_name, price = match.groups()
            self._victoria_quotes.append({'name': fund_name, 'price': Decimal(price.replace(',', '.'))})
        return self._victoria_quotes

    def Stooq_DataReader(self, symbol, currency_id, start_timestamp, end_timestamp):
        """Fetches historical data from Warsaw Stock Exchange (GPW) using Stooq API"""
        url = "https://stooq.com/q/d/l/"
        params = {
            's': symbol.symbol(),
            'd1': datetime.fromtimestamp(start_timestamp, tz=timezone.utc).strftime('%Y%m%d'),
            'd2': datetime.fromtimestamp(end_timestamp, tz=timezone.utc).strftime('%Y%m%d'),
            'i': 'd'
        }
        
        self._request = WebRequest(WebRequest.GET, url, params=params)
        self._wait_for_event()
        
        try:
            data = pd.read_csv(
                StringIO(self._request.data()),
                converters={'Close': lambda x: Decimal(x.strip())} # не теряем точность при чтении
            )
            if data.empty:
                return None
                
            # Convert dates and filter required columns
            data['Date'] = pd.to_datetime(data['Date'], format='%Y-%m-%d', utc=True)
            
            close = data[['Date', 'Close']].set_index('Date')
            close.sort_index(inplace=True)
            return close
            
        except (ParserError, KeyError, ValueError) as e:
            logging.error(f"Failed to parse Stooq data: {str(e)}")
            return None

    # Downloads daily crypto quotes from DeFiLlama. The source quotes in USD only, therefore 'currency_id' is
    # ignored here - the caller stores the result as a USD series (see download_asset_prices) and conversion into
    # any other currency is a matter of quote look-up, not of download.
    def Llama_Downloader(self, symbol, currency_id, start_timestamp, end_timestamp):
        coins = llama_coin_keys(symbol)
        if not coins:
            logging.warning(self.tr("Can't identify crypto asset to download quotes: ") + f"{symbol.symbol()}")
            return None
        # A listing may offer more than one key (see llama_coin_keys) and only one of them is usually indexed by the
        # source. They are tried in turn and the first one that answers with any data wins; an empty answer is not an
        # error here, it simply means the source doesn't know that form of the identifier.
        for coin in coins:
            data = self._llama_chart(coin, start_timestamp, end_timestamp)
            if data is not None:
                return data
        logging.warning(self.tr("No quotes were received from DeFiLlama for ")
                        + f"{symbol.symbol()} ({', '.join(coins)})")
        return None

    # Daily quotes of one DeFiLlama coin key, or None when the source has none for it
    def _llama_chart(self, coin: str, start_timestamp, end_timestamp):
        chunks = []
        start = day_begin(start_timestamp)
        while start <= end_timestamp:
            span = min(int((end_timestamp - start) / SECONDS_IN_DAY) + 1, _LLAMA_MAX_SPAN)
            self._request = WebRequest(WebRequest.GET, f"https://coins.llama.fi/chart/{coin}",
                                       params={'start': start, 'span': span, 'period': '1d',
                                               'searchWidth': _LLAMA_SEARCH_WIDTH})
            self._wait_for_event()
            chunk = parse_llama_chart(self._request.data(), coin)
            if chunk.empty:   # There is no data for this interval and it is unlikely to appear in the next ones
                break
            chunks.append(chunk)
            start += span * SECONDS_IN_DAY
        if not chunks:
            return None
        data = pd.concat(chunks)
        return data[~data.index.duplicated(keep='first')].sort_index()

    # Not used for quotes update since Llama_Downloader took over the blockchain locations - it makes one request
    # per asset per day and is keyed by ticker, which makes it unusable for a backfill. Kept as an alternative source.
    def Coinbase_Downloader(self, symbol, currency_id, start_timestamp, end_timestamp):
        currency_symbol = JalAsset(currency_id).symbol()
        url = f"https://api.coinbase.com/v2/prices/{symbol.symbol()}-{currency_symbol}/spot"
        quotes = []
        for ts in timestamp_range(start_timestamp, end_timestamp):
            date_string = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')
            self._request = WebRequest(WebRequest.GET, url, params={'date': date_string})
            self._wait_for_event()
            try:
                result_data = json.loads(self._request.data())
                quote = result_data['data']['amount']
            except (json.decoder.JSONDecodeError, KeyError):
                continue
            quotes.append({"Date": datetime.fromtimestamp(ts, tz=timezone.utc), "Close": quote})
        data = pd.DataFrame(quotes, columns=["Date", "Close"])
        data['Close'] = data['Close'].apply(Decimal)
        close = data.set_index("Date")
        return close

    # Returns a list of currencies supported by Coinbase exchange as a list of {'symbol', 'name'}
    @staticmethod
    def Coinbase_GetCurrencyList() -> list:
        request = WebRequest(WebRequest.GET, "https://api.coinbase.com/v2/currencies/crypto")
        while request.isRunning():
            QApplication.processEvents()
        result_data = json.loads(request.data())
        data = result_data['data']
        assets = [{'symbol': x['code'], 'name': x['name']} for x in data if x['type'] == 'crypto']
        return assets
