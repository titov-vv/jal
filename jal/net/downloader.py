import logging
import xml.etree.ElementTree as xml_tree
from datetime import datetime, timedelta, timezone
from io import StringIO

import pandas as pd
from pandas.errors import ParserError
import json
from PySide6.QtCore import QObject, Signal, QDate
from PySide6.QtWidgets import QApplication, QDialog

from jal.ui.ui_update_quotes_window import Ui_UpdateQuotesDlg
from jal.constants import Setup, MarketDataFeed, BookAccount, PredefinedAsset
from jal.db.helpers import executeSQL, readSQLrecord
from jal.db.db import JalDB
from jal.net.helpers import get_web_data, post_web_data, isEnglish


# ===================================================================================================================
# UI dialog class
# ===================================================================================================================
class QuotesUpdateDialog(QDialog, Ui_UpdateQuotesDlg):
    def __init__(self, parent):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)
        self.StartDateEdit.setDate(QDate.currentDate().addMonths(-1))
        self.EndDateEdit.setDate(QDate.currentDate())

        # center dialog with respect to parent window
        x = parent.x() + parent.width() / 2 - self.width() / 2
        y = parent.y() + parent.height() / 2 - self.height() / 2
        self.setGeometry(x, y, self.width(), self.height())

    def getStartDate(self):
        return self.StartDateEdit.dateTime().toSecsSinceEpoch()

    def getEndDate(self):
        return self.EndDateEdit.dateTime().toSecsSinceEpoch()


# ===================================================================================================================
# Worker class
# ===================================================================================================================
# noinspection SpellCheckingInspection
class QuoteDownloader(QObject):
    download_completed = Signal()

    def __init__(self):
        super().__init__()
        self.CBR_codes = None
        self.data_loaders = {
            MarketDataFeed.NA: self.Dummy_DataReader,
            MarketDataFeed.CBR: self.CBR_DataReader,
            MarketDataFeed.RU: self.MOEX_DataReader,
            MarketDataFeed.EU: self.Euronext_DataReader,
            MarketDataFeed.US: self.Yahoo_Downloader,
            MarketDataFeed.CA: self.TMX_Downloader,
            MarketDataFeed.GB: self.YahooLSE_Downloader,
            MarketDataFeed.FRA: self.YahooFRA_Downloader
        }

    def showQuoteDownloadDialog(self, parent):
        dialog = QuotesUpdateDialog(parent)
        if dialog.exec():
            self.UpdateQuotes(dialog.getStartDate(), dialog.getEndDate())
            self.download_completed.emit()

    # FIXME This method may work incorrectly for assets with multiple symbols
    def UpdateQuotes(self, start_timestamp, end_timestamp):
        self.PrepareRussianCBReader()
        jal_db = JalDB()
        query = executeSQL("WITH _holdings AS ( "
                           "SELECT l.asset_id AS asset, l.account_id FROM ledger AS l "
                           "WHERE l.book_account = :assets_book AND l.timestamp <= :end_timestamp "
                           "GROUP BY l.asset_id "
                           "HAVING SUM(l.amount) > :tolerance "
                           "UNION "
                           "SELECT DISTINCT l.asset_id AS asset, l.account_id FROM ledger AS l "
                           "WHERE l.book_account = :assets_book AND l.timestamp >= :start_timestamp "
                           "AND l.timestamp <= :end_timestamp "
                           "UNION "
                           "SELECT DISTINCT a.currency_id AS asset, NULL FROM ledger AS l "
                           "LEFT JOIN accounts AS a ON a.id = l.account_id "
                           "WHERE (l.book_account = :money_book OR l.book_account = :liabilities_book) "
                           "AND l.timestamp >= :start_timestamp AND l.timestamp <= :end_timestamp "
                           ") "
                           "SELECT h.asset AS asset_id, coalesce(ac.currency_id, 1) AS currency_id, "
                           "a.symbol AS name, a.quote_source AS feed_id, a.isin AS isin, "
                           "MIN(q.timestamp) AS first_timestamp, MAX(q.timestamp) AS last_timestamp "
                           "FROM _holdings AS h "
                           "LEFT JOIN accounts AS ac ON ac.id=h.account_id "
                           "LEFT JOIN assets_ext AS a ON a.id=h.asset AND a.currency_id=coalesce(ac.currency_id, 1) "
                           "LEFT JOIN quotes AS q ON q.asset_id=h.asset "
                           "GROUP BY h.asset, ac.currency_id "
                           "ORDER BY feed_id",
                           [(":start_timestamp", start_timestamp), (":end_timestamp", end_timestamp),
                            (":assets_book", BookAccount.Assets), (":money_book", BookAccount.Money),
                            (":liabilities_book", BookAccount.Liabilities), (":tolerance", Setup.CALC_TOLERANCE)])
        while query.next():
            asset = readSQLrecord(query, named=True)
            first_timestamp = asset['first_timestamp'] if asset['first_timestamp'] != '' else 0
            last_timestamp = asset['last_timestamp'] if asset['last_timestamp'] != '' else 0
            if start_timestamp < first_timestamp:
                from_timestamp = start_timestamp
            else:
                from_timestamp = last_timestamp if last_timestamp > start_timestamp else start_timestamp
            if end_timestamp < from_timestamp:
                continue
            try:
                data = self.data_loaders[asset['feed_id']](asset['asset_id'], asset['name'], asset['currency_id'],
                                                           asset['isin'], from_timestamp, end_timestamp)
            except (xml_tree.ParseError, pd.errors.EmptyDataError, KeyError):
                logging.warning(self.tr("No data were downloaded for ") + f"{asset}")
                continue
            if data is not None:
                quotations = []
                for date, quote in data.iterrows():  # Date in pandas dataset is in UTC by default
                    quotations.append({'timestamp': int(date.timestamp()), 'quote': float(quote[0])})
                jal_db.update_quotes(asset['asset_id'], asset['currency_id'], quotations)
        jal_db.commit()
        logging.info(self.tr("Download completed"))

    def PrepareRussianCBReader(self):
        rows = []
        try:
            xml_root = xml_tree.fromstring(get_web_data("http://www.cbr.ru/scripts/XML_valFull.asp"))
            for node in xml_root:
                code = node.find("ParentCode").text.strip() if node is not None else None
                iso = node.find("ISO_Char_Code").text if node is not None else None
                rows.append({"ISO_name": iso, "CBR_code": code})
        except xml_tree.ParseError:
            pass
        self.CBR_codes = pd.DataFrame(rows, columns=["ISO_name", "CBR_code"])

    # Empty method to make a unified call for any asset
    def Dummy_DataReader(self, _asset_id, _symbol, _currency, _isin, _start_timestamp, _end_timestamp):
        return None

    def CBR_DataReader(self, _asset_id, currency_code, _currency, _isin, start_timestamp, end_timestamp):
        date1 = datetime.utcfromtimestamp(start_timestamp).strftime('%d/%m/%Y')
        # add 1 day to end_timestamp as CBR sets rate are a day ahead
        date2 = (datetime.utcfromtimestamp(end_timestamp) + timedelta(days=1)).strftime('%d/%m/%Y')
        try:
            code = str(self.CBR_codes.loc[self.CBR_codes["ISO_name"] == currency_code, "CBR_code"].values[0]).strip()
        except IndexError:
            logging.error(self.tr("Failed to get CBR data for: " + f"{currency_code}"))
            return None
        url = f"http://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={date1}&date_req2={date2}&VAL_NM_RQ={code}"
        xml_root = xml_tree.fromstring(get_web_data(url))
        rows = []
        for node in xml_root:
            s_date = node.attrib['Date'] if node is not None else None
            s_val = node.find("Value").text if node is not None else None
            rows.append({"Date": s_date, "Rate": s_val})
        data = pd.DataFrame(rows, columns=["Date", "Rate"])
        data['Date'] = pd.to_datetime(data['Date'], format="%d.%m.%Y")
        data['Rate'] = [x.replace(',', '.') for x in data['Rate']]
        data['Rate'] = data['Rate'].astype(float)
        rates = data.set_index("Date")
        return rates

    # Get asset data from http://www.moex.com
    # Accepts parameters:
    #     symbol, isin, reg_number - to identify asset
    #     special - if 'engine', 'market' and 'board' should be returned as part of result
    # Returns asset data or empty dictionary if nothing found
    @staticmethod
    def MOEX_info(**kwargs) -> dict:
        data = {}
        if 'symbol' in kwargs and not isEnglish(kwargs['symbol']):
            del kwargs['symbol']
        currency = kwargs['currency'] if 'currency' in kwargs else ''
        # First try to load with symbol or isin from asset details API
        if 'symbol' in kwargs:
            data = QuoteDownloader.MOEX_download_info(kwargs['symbol'], currency=currency)
        if not data and 'isin' in kwargs:
            data = QuoteDownloader.MOEX_download_info(kwargs['isin'], currency=currency)
        # If not found try to use search API with regnumber or isin
        if not data and 'reg_number' in kwargs:
            data = QuoteDownloader.MOEX_download_info(QuoteDownloader.MOEX_find_secid(reg_number=kwargs['reg_number']))
        if not data and 'isin' in kwargs:
            data = QuoteDownloader.MOEX_download_info(QuoteDownloader.MOEX_find_secid(isin=kwargs['isin']))
        if 'special' not in kwargs:
            for key in ['engine', 'market', 'board']:
                try:
                    del data[key]
                except KeyError:
                    pass
        return data

    # Searches for asset info on http://www.moex.com by symbol or ISIN provided as asset_code parameter
    # Returns disctionary with asset data: {symbol, isin, regnumber, engine, market, board, pricipal, expiry, etc}
    @staticmethod
    def MOEX_download_info(asset_code, currency='') -> dict:
        mapping = {
            'SECID': 'symbol',
            'NAME': 'name',
            'SHORTNAME': 'short_name',
            'ISIN': 'isin',
            'REGNUMBER': 'reg_number',
            'FACEVALUE': 'principal',
            'MATDATE': 'expiry',
            'LSTDELDATE': 'expiry',
            'GROUP': 'type'
        }
        asset_type = {
            'stock_shares': PredefinedAsset.Stock,
            'stock_dr': PredefinedAsset.Stock,
            'stock_bonds': PredefinedAsset.Bond,
            'stock_etf': PredefinedAsset.ETF,
            'stock_ppif': PredefinedAsset.ETF,
            'futures_forts': PredefinedAsset.Derivative
        }
        asset = {}
        if not asset_code:
            return asset
        url = f"http://iss.moex.com/iss/securities/{asset_code}.xml"
        xml_root = xml_tree.fromstring(get_web_data(url))
        info_rows = xml_root.findall("data[@id='description']/rows/*")
        boards = xml_root.findall("data[@id='boards']/rows/*")
        if not boards:   # can't find boards -> not traded asset
            return asset
        for info in info_rows:
            asset.update({mapping[field]: info.attrib['value'] for field in mapping if info.attrib['name'] == field})
        if 'isin' in asset:
            # replace symbol with short name if we have isin in place of symbol
            asset['symbol'] = asset['short_name'] if asset['symbol'] == asset['isin'] else asset['symbol']
        del asset['short_name']  # drop short name as we won't use it further
        if 'principal' in asset:  # Convert principal into float if possible or drop otherwise
            try:
                asset['principal'] = float(asset['principal'])
            except ValueError:
                del asset['principal']
        if 'expiry' in asset:  # convert YYYY-MM-DD into timestamp
            date_value = datetime.strptime(asset['expiry'], "%Y-%m-%d")
            asset['expiry'] = int(date_value.replace(tzinfo=timezone.utc).timestamp())
        try:
            asset['type'] = asset_type[asset['type']]
        except KeyError:
            logging.error(QApplication.translate("MOEX", "Unsupported MOEX security type: ") + f"{asset['type']}")
            return {}

        boards_list = [board.attrib for board in boards]
        primary_board = [x for x in boards_list if "is_primary" in x and x["is_primary"] == '1']
        if primary_board:
            if currency == 'USD':
                board_id = primary_board[0]['boardid'][:-1] + 'D'
            elif currency == 'EUR':
                board_id = primary_board[0]['boardid'][:-1] + 'E'
            else:
                board_id = primary_board[0]['boardid']
            board = [x for x in boards_list if "boardid" in x and x["boardid"] == board_id]
            if board:
                asset.update({'engine': board[0]['engine'],
                              'market': board[0]['market'],
                              'board': board[0]['boardid']})
        return asset

    # Searches for asset info on http://www.moex.com by given reg_number or isin
    # Returns 'secid' if asset was found and empty string otherwise
    @staticmethod
    def MOEX_find_secid(**kwargs) -> str:
        secid = ''
        data = []
        if 'reg_number' in kwargs:
            url = f"https://iss.moex.com/iss/securities.json?q={kwargs['reg_number']}&iss.meta=off&limit=10"
            asset_data = json.loads(get_web_data(url))
            securities = asset_data['securities']
            columns = securities['columns']
            data = [x for x in securities['data'] if
                    x[columns.index('regnumber')] == kwargs['reg_number'] or x[columns.index('regnumber')] is None]
        if not data and 'isin' in kwargs:
            url = f"https://iss.moex.com/iss/securities.json?q={kwargs['isin']}&iss.meta=off&limit=10"
            asset_data = json.loads(get_web_data(url))
            securities = asset_data['securities']
            columns = securities['columns']
            data = securities['data']  # take the whole list if we search by isin
        if data:
            if len(data) > 1:
                # remove not traded assets if there are any outdated doubles present
                data = [x for x in data if x[columns.index('is_traded')] == 1]
            if len(data) > 1:  # and then check again
                logging.info(QApplication.translate("MOEX", "Multiple MOEX assets found for: ") + f"{kwargs}")
                return secid
            asset_data = dict(zip(columns, data[0]))
            secid = asset_data['secid'] if 'secid' in asset_data else ''
        return secid

    # noinspection PyMethodMayBeStatic
    def MOEX_DataReader(self, asset_id, asset_code, currency, isin, start_timestamp, end_timestamp, update_symbol=True):
        currency = JalDB().get_asset_name(currency)
        asset = self.MOEX_info(symbol=asset_code, isin=isin, currency=currency, special=True)
        if (asset['engine'] is None) or (asset['market'] is None) or (asset['board'] is None):
            logging.warning(f"Failed to find {asset_code} on moex.com")
            return None
        if (asset['market'] == 'bonds') and (asset['board'] == 'TQCB'):
            asset_code = isin   # Corporate bonds are quoted by ISIN
        if (asset['market'] == 'shares') and (asset['board'] == 'TQIF'):
            asset_code = isin   # ETFs are quoted by ISIN
        if update_symbol:
            isin = asset['isin'] if 'isin' in asset else ''
            reg_number = asset['reg_number'] if 'reg_number' in asset else ''
            expiry = asset['expiry'] if 'expiry' in asset else 0
            principal = asset['principal'] if 'principal' in asset else 0
            details = {'isin': isin, 'reg_number': reg_number, 'expiry': expiry, 'principal': principal}
            JalDB().update_asset_data(asset_id, details)

        # Get price history
        date1 = datetime.utcfromtimestamp(start_timestamp).strftime('%Y-%m-%d')
        date2 = datetime.utcfromtimestamp(end_timestamp).strftime('%Y-%m-%d')
        url = f"http://iss.moex.com/iss/history/engines/{asset['engine']}/markets/{asset['market']}/" \
              f"boards/{asset['board']}/securities/{asset_code}.xml?from={date1}&till={date2}"
        xml_root = xml_tree.fromstring(get_web_data(url))
        history_rows = xml_root.findall("data[@id='history']/rows/*")
        quotes = []
        for row in history_rows:
            if row.attrib['CLOSE']:
                if 'FACEVALUE' in row.attrib:  # Correction for bonds
                    price = float(row.attrib['CLOSE']) * float(row.attrib['FACEVALUE']) / 100.0
                    quotes.append({"Date": row.attrib['TRADEDATE'], "Close": price})
                else:
                    quotes.append({"Date": row.attrib['TRADEDATE'], "Close": row.attrib['CLOSE']})
        data = pd.DataFrame(quotes, columns=["Date", "Close"])
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d")
        data['Close'] = pd.to_numeric(data['Close'])
        close = data.set_index("Date")
        return close

    # noinspection PyMethodMayBeStatic
    def Yahoo_Downloader(self, _asset_id, asset_code, _currency, _isin, start_timestamp, end_timestamp):
        url = f"https://query1.finance.yahoo.com/v7/finance/download/{asset_code}?" \
              f"period1={start_timestamp}&period2={end_timestamp}&interval=1d&events=history"
        file = StringIO(get_web_data(url))
        try:
            data = pd.read_csv(file)
        except ParserError:
            return None
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d")
        data = data.drop(columns=['Open', 'High', 'Low', 'Adj Close', 'Volume'])
        close = data.set_index("Date")
        return close

    # The same as Yahoo_Downloader but it adds ".L" suffix to asset_code and returns prices in GBP
    def YahooLSE_Downloader(self, asset_id, asset_code, currency, _isin, start_timestamp, end_timestamp):
        return self.Yahoo_Downloader(asset_id, asset_code + '.L', currency, _isin, start_timestamp, end_timestamp)

    # The same as Yahoo_Downloader but it adds ".F" suffix to asset_code and returns prices in EUR
    def YahooFRA_Downloader(self, asset_id, asset_code, currency, _isin, start_timestamp, end_timestamp):
        return self.Yahoo_Downloader(asset_id, asset_code + '.F', currency, _isin, start_timestamp, end_timestamp)

    # noinspection PyMethodMayBeStatic
    def Euronext_DataReader(self, _asset_id, _asset_code, _currency, isin, start_timestamp, end_timestamp):
        params = {'format': 'csv', 'decimal_separator': '.', 'date_form': 'd/m/Y', 'op': '', 'adjusted': '',
                  'base100': '', 'startdate': datetime.utcfromtimestamp(start_timestamp).strftime('%Y-%m-%d'),
                  'enddate': datetime.utcfromtimestamp(end_timestamp).strftime('%Y-%m-%d')}
        url = f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{isin}-XPAR"
        quotes = post_web_data(url, params=params)
        quotes_text = quotes.splitlines()
        if len(quotes_text) < 4:
            logging.warning(self.tr("Euronext quotes history reply is too short: ") + quotes)
            return None
        if quotes_text[0] != '"Historical Data"':
            logging.warning(self.tr("Euronext quotes header not found in: ") + quotes)
            return None
        if quotes_text[2] != isin:
            logging.warning(self.tr("Euronext quotes ISIN mismatch in: ") + quotes)
            return None
        file = StringIO(quotes)
        try:
            data = pd.read_csv(file, header=3, sep=';')
        except ParserError:
            return None
        data['Date'] = pd.to_datetime(data['Date'], format="%d/%m/%Y")
        data = data.drop(columns=['Open', 'High', 'Low', 'Number of Shares', 'Number of Trades',
                                  'Turnover', 'Number of Trades', 'vwap'])
        close = data.set_index("Date")
        close.sort_index(inplace=True)
        return close

    # noinspection PyMethodMayBeStatic
    def TMX_Downloader(self, _asset_id, asset_code, _currency, _isin, start_timestamp, end_timestamp):
        url = 'https://app-money.tmx.com/graphql'
        params = {
            "operationName": "getCompanyPriceHistoryForDownload",
            "variables":
                {
                    "symbol": asset_code,
                    "start": datetime.utcfromtimestamp(start_timestamp).strftime('%Y-%m-%d'),
                    "end": datetime.utcfromtimestamp(end_timestamp).strftime('%Y-%m-%d'),
                    "adjusted": False,
                    "adjustmentType": None,
                    "unadjusted": True
                },
            "query": "query getCompanyPriceHistoryForDownload($symbol: String!, $start: String, $end: String, $adjusted: Boolean, $adjustmentType: String, $unadjusted: Boolean) "
                     "{getCompanyPriceHistoryForDownload(symbol: $symbol, start: $start, end: $end, adjusted: $adjusted, adjustmentType: $adjustmentType, unadjusted: $unadjusted) "
                     "{ datetime closePrice}}"
        }
        json_content = json.loads(post_web_data(url, json_params=params))
        result_data = json_content['data'] if 'data' in json_content else None
        if 'getCompanyPriceHistoryForDownload' in result_data:
            price_array = result_data['getCompanyPriceHistoryForDownload']
        else:
            logging.warning(self.tr("Can't parse data for TSX quotes: ") + json_content)
            return None
        data = pd.DataFrame(price_array)
        data.rename(columns={'datetime': 'Date', 'closePrice': 'Close'}, inplace=True)
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d")
        close = data.set_index("Date")
        close.sort_index(inplace=True)
        return close

    def updataData(self):
        query = executeSQL("SELECT * FROM assets_ext WHERE quote_source!=:NA",
                           [(":NA", MarketDataFeed.NA)])
        while query.next():
            asset = readSQLrecord(query, named=True)
            if asset['type_id'] in [PredefinedAsset.Money, PredefinedAsset.Commodity, PredefinedAsset.Forex]:
                continue
            if asset['quote_source'] == MarketDataFeed.RU:
                logging.info(self.tr("Checking MOEX data for: ") + asset['symbol'])
                data = self.MOEX_info(symbol=asset['symbol'], isin=asset['isin'])
                if data:
                    if asset['full_name'] != data['name']:
                        logging.info(self.tr("New full name found for:  ")
                                     + f"{JalDB().get_asset_name(asset['id'])}: {asset['full_name']} -> {data['name']}")
                    isin = data['isin'] if not asset['isin'] and 'isin' in data and data['isin'] else ''
                    JalDB().update_asset_data(asset['id'], {'isin': isin})
