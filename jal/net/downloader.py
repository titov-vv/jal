import logging
import xml.etree.ElementTree as xml_tree
from datetime import datetime, timedelta, timezone
from io import StringIO

import pandas as pd
from pandas.errors import ParserError
import json
from PySide2 import QtCore
from PySide2.QtCore import QObject, Signal
from PySide2.QtWidgets import QDialog

from jal.ui.ui_update_quotes_window import Ui_UpdateQuotesDlg
from jal.constants import Setup, MarketDataFeed, BookAccount, PredefinedAsset
from jal.db.helpers import executeSQL, readSQLrecord
from jal.db.update import JalDB
from jal.net.helpers import get_web_data, post_web_data, isEnglish
from jal.widgets.helpers import g_tr


# ===================================================================================================================
# UI dialog class
# ===================================================================================================================
class QuotesUpdateDialog(QDialog, Ui_UpdateQuotesDlg):
    def __init__(self, parent):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)
        self.StartDateEdit.setDate(QtCore.QDate.currentDate().addMonths(-1))
        self.EndDateEdit.setDate(QtCore.QDate.currentDate())

        # center dialog with respect to parent window
        x = parent.x() + parent.width()/2 - self.width()/2
        y = parent.y() + parent.height()/2 - self.height()/2
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
            MarketDataFeed.CA: self.TMX_Downloader
        }

    def showQuoteDownloadDialog(self, parent):
        dialog = QuotesUpdateDialog(parent)
        if dialog.exec_():
            self.UpdateQuotes(dialog.getStartDate(), dialog.getEndDate())
            self.download_completed.emit()

    def UpdateQuotes(self, start_timestamp, end_timestamp):
        self.PrepareRussianCBReader()
        jal_db = JalDB()

        query = executeSQL("WITH _holdings AS ( "
                           "SELECT l.asset_id AS asset FROM ledger AS l "
                           "WHERE l.book_account = 4 AND l.timestamp <= :end_timestamp "
                           "GROUP BY l.asset_id "
                           "HAVING SUM(l.amount) > :tolerance "
                           "UNION "
                           "SELECT DISTINCT l.asset_id AS asset FROM ledger AS l "
                           "WHERE l.book_account = :assets_book AND l.timestamp >= :start_timestamp "
                           "AND l.timestamp <= :end_timestamp "
                           "UNION "
                           "SELECT DISTINCT a.currency_id AS asset FROM ledger AS l "
                           "LEFT JOIN accounts AS a ON a.id = l.account_id "
                           "WHERE (l.book_account = :money_book OR l.book_account = :liabilities_book) "
                           "AND l.timestamp >= :start_timestamp AND l.timestamp <= :end_timestamp "
                           ") "
                           "SELECT h.asset AS asset_id, a.name AS name, a.src_id AS feed_id, a.isin AS isin, "
                           "MIN(q.timestamp) AS first_timestamp, MAX(q.timestamp) AS last_timestamp "
                           "FROM _holdings AS h "
                           "LEFT JOIN assets AS a ON a.id=h.asset "
                           "LEFT JOIN quotes AS q ON q.asset_id=h.asset "
                           "GROUP BY h.asset "
                           "ORDER BY a.src_id",
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
                data = self.data_loaders[asset['feed_id']](asset['asset_id'], asset['name'], asset['isin'],
                                                           from_timestamp, end_timestamp)
            except (xml_tree.ParseError, pd.errors.EmptyDataError, KeyError):
                logging.warning(g_tr('QuotesUpdateDialog', "No data were downloaded for ") + f"{asset}")
                continue
            if data is not None:
                for date, quote in data.iterrows():  # Date in pandas dataset is in UTC by default
                    jal_db.update_quote(asset['asset_id'], int(date.timestamp()), float(quote[0]))
        jal_db.commit()
        logging.info(g_tr('QuotesUpdateDialog', "Download completed"))

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
    def Dummy_DataReader(self, _asset_id, _symbol, _isin, _start_timestamp, _end_timestamp):
        return None

    def CBR_DataReader(self, _asset_id, currency_code, _isin, start_timestamp, end_timestamp):
        date1 = datetime.utcfromtimestamp(start_timestamp).strftime('%d/%m/%Y')
        # add 1 day to end_timestamp as CBR sets rate are a day ahead
        date2 = (datetime.utcfromtimestamp(end_timestamp) + timedelta(days=1)).strftime('%d/%m/%Y')
        code = str(self.CBR_codes.loc[self.CBR_codes["ISO_name"] == currency_code, "CBR_code"].values[0]).strip()
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
    #     symbol, isin, regcode - to identify asset
    #     special - if 'engine', 'market' and 'board' should be returned as part of result
    # Returns asset data or empty dictionary if nothing found
    @staticmethod
    def MOEX_info(**kwargs) -> dict:
        data = {}
        if 'symbol' in kwargs and not isEnglish(kwargs['symbol']):
            del kwargs['symbol']
        # First try to load with symbol or isin from asset details API
        if 'symbol' in kwargs:
            data = QuoteDownloader.MOEX_download_info(kwargs['symbol'])
        if not data and 'isin' in kwargs:
            data = QuoteDownloader.MOEX_download_info(kwargs['isin'])
        # If not found try to use search API with regnumber or isin
        if not data and 'regnumber' in kwargs:
            data = QuoteDownloader.MOEX_download_info(QuoteDownloader.MOEX_find_secid_by_regcode(kwargs['regnumber']))
        if not data and 'isin' in kwargs:
            data = QuoteDownloader.MOEX_download_info(QuoteDownloader.MOEX_find_secid_by_regcode(kwargs['isin']))
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
    def MOEX_download_info(asset_code) -> dict:
        mapping = {
            'SECID': 'symbol',
            'NAME': 'name',
            'SHORTNAME': 'short_name',
            'ISIN': 'isin',
            'REGNUMBER': 'reg_code',
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
            logging.error(g_tr('QuoteDownloader', "Unsupported MOEX security type: ") + f"{asset['type']}")
            return {}

        for board in boards:
            if board.attrib['is_primary'] == '1':
                asset.update({'engine': board.attrib['engine'],
                              'market': board.attrib['market'],
                              'board': board.attrib['boardid']})
                break
        return asset

    # Searches for asset info on http://www.moex.com by given reg.number
    # Returns ISIN if asset was found and empty string otherwise
    @staticmethod
    def MOEX_find_secid_by_regcode(regnumber) -> str:
        secid = ''
        if not regnumber:
            return secid
        url = f"https://iss.moex.com/iss/securities.json?q={regnumber}&iss.meta=off&limit=10"
        asset_data = json.loads(get_web_data(url))
        securities = asset_data['securities']
        columns = securities['columns']
        data = securities['data']
        if data:
            if len(data) > 1:
                logging.info(g_tr('QuoteDownloader', "MOEX: multiple assets found for reg.number: ") + regnumber)
                return secid
            asset_data = dict(zip(columns, data[0]))
            secid = asset_data['secid'] if 'secid' in asset_data else ''
        return secid

    # noinspection PyMethodMayBeStatic
    def MOEX_DataReader(self, asset_id, asset_code, isin, start_timestamp, end_timestamp):
        asset = self.MOEX_info(symbol=asset_code, isin=isin, special=True)
        if (asset['engine'] is None) or (asset['market'] is None) or (asset['board'] is None):
            logging.warning(f"Failed to find {asset_code} on moex.com")
            return None

        isin = asset['isin'] if 'isin' in asset else ''
        reg_code = asset['reg_code'] if 'reg_code' in asset else ''
        expiry = asset['expiry'] if 'expiry' in asset else 0
        JalDB().update_asset_data(asset_id, new_isin=isin, new_reg=reg_code, expiry=expiry)

        # Get price history
        date1 = datetime.utcfromtimestamp(start_timestamp).strftime('%Y-%m-%d')
        date2 = datetime.utcfromtimestamp(end_timestamp).strftime('%Y-%m-%d')
        url = f"http://iss.moex.com/iss/history/engines/{asset['engine']}/markets/{asset['market']}/"\
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
    def Yahoo_Downloader(self, _asset_id, asset_code, _isin, start_timestamp, end_timestamp):
        url = f"https://query1.finance.yahoo.com/v7/finance/download/{asset_code}?"\
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

    # noinspection PyMethodMayBeStatic
    def Euronext_DataReader(self, _asset_id, _asset_code, isin, start_timestamp, end_timestamp):
        params = {'format': 'csv', 'decimal_separator': '.', 'date_form': 'd/m/Y', 'op': '', 'adjusted': '',
                  'base100': '', 'startdate': datetime.utcfromtimestamp(start_timestamp).strftime('%Y-%m-%d'),
                  'enddate': datetime.utcfromtimestamp(end_timestamp).strftime('%Y-%m-%d')}
        url = f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{isin}-XPAR"
        quotes = post_web_data(url, params=params)
        quotes_text = quotes.splitlines()
        if len(quotes_text) < 4:
            logging.warning(g_tr('QuotesUpdateDialog', "Euronext quotes history reply is too short: ") + quotes)
            return None
        if quotes_text[0] != '"Historical Data"':
            logging.warning(g_tr('QuotesUpdateDialog', "Euronext quotes header not found in: ") + quotes)
            return None
        if quotes_text[2] != isin:
            logging.warning(g_tr('QuotesUpdateDialog', "Euronext quotes ISIN mismatch in: ") + quotes)
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
    def TMX_Downloader(self, _asset_id, asset_code, _isin, start_timestamp, end_timestamp):
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
            logging.warning(g_tr('QuotesUpdateDialog', "Can't parse data for TSX quotes: ") + json_content)
            return None
        data = pd.DataFrame(price_array)
        data.rename(columns={'datetime': 'Date', 'closePrice': 'Close'}, inplace=True)
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d")
        close = data.set_index("Date")
        close.sort_index(inplace=True)
        return close
