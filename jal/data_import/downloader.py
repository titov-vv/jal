import logging
import xml.etree.ElementTree as xml_tree
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
import json
import requests
from PySide2 import QtCore
from PySide2.QtCore import QObject, Signal
from PySide2.QtWidgets import QDialog

from jal.ui.ui_update_quotes_window import Ui_UpdateQuotesDlg
from jal.constants import Setup, MarketDataFeed, BookAccount
from jal.db.helpers import executeSQL, readSQLrecord
from jal.db.update import JalDB
from jal.widgets.helpers import g_tr


# ===================================================================================================================
# Function download URL and return it content as string or empty string if site returns error
# ===================================================================================================================
def get_web_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        logging.error(f"URL: {url}" + g_tr('QuotesUpdateDialog', " failed with response ") + f"{response}")
        return ''


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
                code = node.find("ParentCode").text if node is not None else None
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

    # noinspection PyMethodMayBeStatic
    def MOEX_DataReader(self, asset_id, asset_code, _isin, start_timestamp, end_timestamp):
        engine = None
        market = None
        board_id = None
        # Get primary board ID
        url = f"http://iss.moex.com/iss/securities/{asset_code}.xml"
        xml_root = xml_tree.fromstring(get_web_data(url))
        for node in xml_root:
            if node.tag == 'data' and node.attrib['id'] == 'boards':
                boards_data = list(node)
                for row in boards_data:
                    if row.tag == 'rows':
                        boards = list(row)
                        for board in boards:
                            if board.attrib['is_primary'] == '1':
                                engine = board.attrib['engine']
                                market = board.attrib['market']
                                board_id = board.attrib['boardid']
        if (engine is None) or (market is None) or (board_id is None):
            logging.warning(f"Failed to find {asset_code} at {url}")
            return None

        # Get security info
        url = f"https://iss.moex.com/iss/engines/{engine}/"\
              f"markets/{market}/boards/{board_id}/securities/{asset_code}.xml"
        xml_root = xml_tree.fromstring(get_web_data(url))
        for node in xml_root:
            if node.tag == 'data' and node.attrib['id'] == 'securities':
                sec_data = list(node)
                for row in sec_data:
                    if row.tag == 'rows':
                        if len(list(row)) == 1:
                            asset_info = list(row)[0]
                            isin = asset_info.attrib['ISIN'] if 'ISIN' in asset_info.attrib else ''
                            reg_code = asset_info.attrib['REGNUMBER'] if 'REGNUMBER' in asset_info.attrib else ''
                            JalDB().update_asset_data(asset_id, new_isin=isin, new_reg=reg_code)

        # Get price history
        date1 = datetime.utcfromtimestamp(start_timestamp).strftime('%Y-%m-%d')
        date2 = datetime.utcfromtimestamp(end_timestamp).strftime('%Y-%m-%d')
        url = f"http://iss.moex.com/iss/history/engines/"\
              f"{engine}/markets/{market}/boards/{board_id}/securities/{asset_code}.xml?from={date1}&till={date2}"
        xml_root = xml_tree.fromstring(get_web_data(url))
        rows = []
        for node in xml_root:
            if node.tag == 'data' and node.attrib['id'] == 'history':
                sections = list(node)
                for section in sections:
                    if section.tag == "rows":
                        history_rows = list(section)
                        for row in history_rows:
                            if row.tag == "row":
                                if row.attrib['CLOSE']:
                                    if 'FACEVALUE' in row.attrib:  # Correction for bonds
                                        price = float(row.attrib['CLOSE']) * float(row.attrib['FACEVALUE']) / 100.0
                                        rows.append({"Date": row.attrib['TRADEDATE'], "Close": price})
                                    else:
                                        rows.append({"Date": row.attrib['TRADEDATE'], "Close": row.attrib['CLOSE']})
        data = pd.DataFrame(rows, columns=["Date", "Close"])
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d")
        close = data.set_index("Date")
        return close

    # noinspection PyMethodMayBeStatic
    def Yahoo_Downloader(self, _asset_id, asset_code, _isin, start_timestamp, end_timestamp):
        url = f"https://query1.finance.yahoo.com/v7/finance/download/{asset_code}?"\
              f"period1={start_timestamp}&period2={end_timestamp}&interval=1d&events=history"
        file = StringIO(get_web_data(url))
        data = pd.read_csv(file)
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d")
        data = data.drop(columns=['Open', 'High', 'Low', 'Adj Close', 'Volume'])
        close = data.set_index("Date")
        return close

    # noinspection PyMethodMayBeStatic
    def Euronext_DataReader(self, _asset_id, asset_code, isin, start_timestamp, end_timestamp):
        start = int(start_timestamp * 1000)
        end = int(end_timestamp * 1000)
        url = f"https://euconsumer.euronext.com/nyx_eu_listings/price_chart/download_historical?"\
              f"typefile=csv&layout=vertical&typedate=dmy&separator=point&mic=XPAR&isin={isin}&name={asset_code}&"\
              f"namefile=Price_Data_Historical&from={start}&to={end}&adjusted=1&base=0"
        file = StringIO(get_web_data(url))
        data = pd.read_csv(file, header=3)
        data['Date'] = pd.to_datetime(data['Date'], format="%d/%m/%Y")
        data = data.drop(
            columns=['ISIN', 'MIC', 'Ouvert', 'Haut', 'Bas', 'Nombre de titres', 'Number of Trades', 'Capitaux',
                     'Devise'])
        close = data.set_index("Date")
        return close

    # noinspection PyMethodMayBeStatic
    def TMX_Downloader(self, _asset_id, asset_code, _isin, start_timestamp, end_timestamp):
        url = 'https://app-money.tmx.com/graphql'
        s = requests.Session()
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
        response = s.post(url, json=params)
        if response.status_code != 200:
            logging.error(f"URL: {url}" + g_tr('QuotesUpdateDialog',
                                               " failed with response ") + f"{response.status_code}: {response.text}")
            return None
        json_content = json.loads(response.text)
        result_data = json_content['data'] if 'data' in json_content else None
        if 'getCompanyPriceHistoryForDownload' in result_data:
            price_array = result_data['getCompanyPriceHistoryForDownload']
        else:
            logging.warning(g_tr('QuotesUpdateDialog', "Can't parse data for TSX quotes: ") + f"{response.text}")
            return None
        data = pd.DataFrame(price_array)
        data['datetime'] = pd.to_datetime(data['datetime'], format="%Y-%m-%d")
        close = data.set_index("datetime")
        return close
