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
from jal.constants import MarketDataFeed, PredefinedAsset
from jal.db.asset import JalAsset
from jal.net.web_request import WebRequest
from jal.net.moex import MOEX
try:
    from pypdf import PdfReader
    from pypdf.errors import PdfStreamError
except ImportError:
    pass  # PDF files won't be downloaded without dependency

DATA_SOURCE_ROLE = Qt.UserRole + 1

# ===================================================================================================================
# UI dialog class
# ===================================================================================================================
class QuotesUpdateDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.ui = Ui_UpdateQuotesDlg()
        self.ui.setupUi(self)
        self.ui.StartDateEdit.setDate(QDate.currentDate().addMonths(-1))
        self.ui.EndDateEdit.setDate(QDate.currentDate())
        sources = JalAsset.get_sources_list()
        for source in sources:
            if source != MarketDataFeed.NA:
                item = QListWidgetItem(sources[source], self.ui.SourcesList)
                item.setData(DATA_SOURCE_ROLE, source)
                item.setCheckState(Qt.Checked)
                self.ui.SourcesList.addItem(item)

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
        self._cancelled = False
        self._waiting = False
        self._cbr_codes = None
        self._victoria_quotes = []
        self._victoria_date = None

    @Slot()
    def on_cancel(self):
        self._cancelled = True

    # this method waits for completion of downloading process or for user interrupt (in this case exception is raised)
    def _wait_for_event(self):
        while self._request.isRunning():
            QApplication.processEvents()
            if self._cancelled:
                self._request.quit()
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
            if MarketDataFeed.FX in sources_list:
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
        currencies = [x for x in JalAsset.get_currencies() if x.quote_source(None) == MarketDataFeed.FX]
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
            MarketDataFeed.NA: self.Dummy_DataReader,
            MarketDataFeed.RU: self.MOEX_DataReader,
            MarketDataFeed.EU: self.Euronext_DataReader,
            MarketDataFeed.US: self.Yahoo_Downloader,
            MarketDataFeed.CA: self.TMX_Downloader,
            MarketDataFeed.GB: self.YahooLSE_Downloader,
            MarketDataFeed.FRA: self.YahooFRA_Downloader,
            MarketDataFeed.SMA_VICTORIA: self.Victoria_Downloader,
            MarketDataFeed.COIN: self.Coinbase_Downloader,
            MarketDataFeed.MILAN: self.EuronextMilan_DataReader,
            MarketDataFeed.WSE: self.Stooq_DataReader
        }
        assets = JalAsset.get_active_assets(start_timestamp, end_timestamp)
        assets = [(x['asset'], x['currency']) for x in assets if x['asset'].quote_source(x['currency']) in sources_list]
        logging.info(self.tr("Loading assets prices"))
        for i, (asset, currency) in enumerate(assets):
            from_timestamp = self._adjust_start(asset, currency, start_timestamp)
            try:
                if from_timestamp <= end_timestamp:
                    data = data_loaders[asset.quote_source(currency)](asset, currency, from_timestamp, end_timestamp)
                    self._store_quotations(asset, currency, data)
            except (pd.errors.EmptyDataError, KeyError, json.decoder.JSONDecodeError):
                logging.warning(self.tr("No quotes were downloaded for ") + f"{asset.symbol()}")
                continue
            self.update_progress.emit(100.0 * i / len(assets))

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
    def MOEX_DataReader(self, asset, currency_id, start_timestamp, end_timestamp, update_symbol=True):
        currency = JalAsset(currency_id).symbol()
        moex_info = MOEX().asset_info(symbol=asset.symbol(currency_id), isin=asset.isin(), currency=currency, special=True)
        if not ('engine' in moex_info and 'market' in moex_info and 'board' in moex_info) or \
                (moex_info['engine'] is None) or (moex_info['market'] is None) or (moex_info['board'] is None):
            logging.warning(f"Failed to find {asset.symbol(currency_id)} ({asset.isin()}) on moex.com")
            return None
        if (moex_info['market'] == 'bonds') and (moex_info['board'] in ['TQCB', 'TQIR']):
            asset_code = asset.isin()   # Corporate bonds are quoted by ISIN
        elif (moex_info['market'] == 'shares') and (moex_info['board'] == 'TQIF'):
            asset_code = asset.isin()   # ETFs are quoted by ISIN
        else:
            asset_code = asset.symbol(currency_id)
        if update_symbol:
            isin = moex_info['isin'] if 'isin' in moex_info else ''
            reg_number = moex_info['reg_number'] if 'reg_number' in moex_info else ''
            expiry = moex_info['expiry'] if 'expiry' in moex_info else 0
            principal = moex_info['principal'] if 'principal' in moex_info else 0
            details = {'isin': isin, 'reg_number': reg_number, 'expiry': expiry, 'principal': principal}
            asset.update_data(details)
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
    def Yahoo_Downloader(self, asset, currency_id, start_timestamp, end_timestamp, suffix=''):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{asset.symbol(currency_id)+suffix}"
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
    def YahooLSE_Downloader(self, asset, currency_id, start_timestamp, end_timestamp):
        return self.Yahoo_Downloader(asset, currency_id, start_timestamp, end_timestamp, suffix='.L')

    # The same as Yahoo_Downloader but it adds ".F" suffix to asset_code and returns prices in EUR
    def YahooFRA_Downloader(self, asset, currency_id, start_timestamp, end_timestamp):
        return self.Yahoo_Downloader(asset, currency_id, start_timestamp, end_timestamp, suffix='.F')

    # noinspection PyMethodMayBeStatic
    def Euronext_DataReader(self, asset, currency_id, start_timestamp, end_timestamp):
        suffix = "ETFP" if asset.type() == PredefinedAsset.ETF else "XPAR"  # Dates don't work for ETFP due to glitch on their site
        url = f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{asset.isin()}-{suffix}"
        params = {
            'format': 'csv',
            'decimal_separator': '.',
            'date_form': 'd%2Fm%2FY',
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
        if quotes_text[2] != asset.isin():
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
    def EuronextMilan_DataReader(self, asset, currency_id, start_timestamp, end_timestamp):
        suffix = "ETF" if asset.type() == PredefinedAsset.ETF else "MTA"
        url = "https://charts.borsaitaliana.it/charts/services/ChartWService.asmx/GetPricesWithVolume"
        params = {
            "request": {
                "SampleTime":"1d",
                "TimeFrame":None,
                "RequestedDataSetType":"ohlc",
                "ChartPriceType":"price",
                "Key": asset.symbol(currency_id) + "." + suffix,
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
    def TMX_Downloader(self, asset, _currency_id, start_timestamp, end_timestamp):
        url = 'https://app-money.tmx.com/graphql'
        params = {
            "operationName": "getCompanyPriceHistoryForDownload",
            "variables":
                {
                    "symbol": asset.symbol(),
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

    def Victoria_Downloader(self, asset, _currency_id, _start_timestamp, _end_timestamp):
        quotes = self._get_victoria_quotes()
        if not quotes:
            return None
        # Filter asset price
        asset_quotes = [x for x in quotes if x['name'] == asset.name()]
        if len(asset_quotes) != 1:
            logging.warning(self.tr("Can't find quote for Victoria Seguros fund: ") + asset.name())
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

    def Stooq_DataReader(self, asset, currency_id, start_timestamp, end_timestamp):
        """Fetches historical data from Warsaw Stock Exchange (GPW) using Stooq API"""
        url = "https://stooq.com/q/d/l/"
        params = {
            's': asset.symbol(currency_id),
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

    def Coinbase_Downloader(self, asset, currency_id, start_timestamp, end_timestamp):
        currency_symbol = JalAsset(currency_id).symbol()
        url = f"https://api.coinbase.com/v2/prices/{asset.symbol(currency_id)}-{currency_symbol}/spot"
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
