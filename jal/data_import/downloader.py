import logging
import xml.etree.ElementTree as xml_tree
from datetime import datetime
from io import StringIO

import pandas as pd
import requests
from PySide2 import QtCore
from PySide2.QtCore import QObject, Signal
from PySide2.QtWidgets import QDialog

from jal.ui.ui_update_quotes_window import Ui_UpdateQuotesDlg
from jal.constants import Setup, MarketDataFeed
from jal.db.helpers import executeSQL
from jal.ui_custom.helpers import g_tr


# ===================================================================================================================
# Function downlaod URL and return it content as string or empty string if site returns error
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
class QuoteDownloader(QObject):
    download_completed = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.CBR_codes = None
        self.data_loaders = {
            MarketDataFeed.NA: self.Dummy_DataReader,
            MarketDataFeed.CBR: self.CBR_DataReader,
            MarketDataFeed.RU: self.MOEX_DataReader,
            MarketDataFeed.EU: self.Euronext_DataReader,
            MarketDataFeed.US: self.Yahoo_Downloader
        }

    def showQuoteDownloadDialog(self, parent):
        dialog = QuotesUpdateDialog(parent)
        if dialog.exec_():
            self.UpdateQuotes(dialog.getStartDate(), dialog.getEndDate())
            self.download_completed.emit()

    def UpdateQuotes(self, start_timestamp, end_timestamp):
        self.PrepareRussianCBReader()

        executeSQL(self.db, "DELETE FROM holdings_aux")

        # Collect list of assets that are/were held on end date
        executeSQL(self.db,
            "INSERT INTO holdings_aux(asset) "
            "SELECT l.asset_id AS asset FROM ledger AS l "
            "WHERE l.book_account = 4 AND l.timestamp <= :end_timestamp "
            "GROUP BY l.asset_id "
            "HAVING sum(l.amount) > :tolerance "
            "UNION "
            "SELECT DISTINCT l.asset_id AS asset FROM ledger AS l "
            "WHERE l.book_account = 4 AND l.timestamp >= :start_timestamp AND l.timestamp <= :end_timestamp "
            "UNION "
            "SELECT DISTINCT a.currency_id AS asset FROM ledger AS l "
            "LEFT JOIN accounts AS a ON a.id = l.account_id "
            "WHERE (l.book_account = 3 OR l.book_account = 5) "
            "AND l.timestamp >= :start_timestamp AND l.timestamp <= :end_timestamp",
                   [(":start_timestamp", start_timestamp),
                    (":end_timestamp", end_timestamp),
                    (":tolerance", Setup.CALC_TOLERANCE)])

        # Get a list of symbols ordered by data source ID
        query = executeSQL(self.db, "SELECT h.asset, a.name, a.src_id, a.isin, MAX(q.timestamp) AS last_timestamp "
                                    "FROM holdings_aux AS h "
                                    "LEFT JOIN assets AS a ON a.id=h.asset "
                                    "LEFT JOIN quotes AS q ON q.asset_id=h.asset "
                                    "GROUP BY h.asset "
                                    "ORDER BY a.src_id")
        while query.next():
            asset_id = query.value(0)
            asset = query.value(1)
            feed_id = query.value(2)
            isin = query.value(3)
            last_timestamp = query.value(4) if query.value(4) != '' else 0
            from_timestamp = last_timestamp if last_timestamp > start_timestamp else start_timestamp
            try:
                data = self.data_loaders[feed_id](asset, isin, from_timestamp, end_timestamp)
            except (xml_tree.ParseError, pd.errors.EmptyDataError, KeyError):
                logging.warning(g_tr('QuotesUpdateDialog', "No data were downloaded for ") + f"{asset}")
                continue
            if data is not None:
                for date, quote in data.iterrows():
                    self.SubmitQuote(asset_id, asset, int(date.timestamp()), float(quote[0]))
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
    def Dummy_DataReader(self, _symbol, _isin, _start_timestamp, _end_timestamp):
        return None

    def CBR_DataReader(self, currency_code, _isin, start_timestamp, end_timestamp):
        date1 = datetime.fromtimestamp(start_timestamp).strftime('%d/%m/%Y')
        date2 = datetime.fromtimestamp(end_timestamp + 86400).strftime('%d/%m/%Y')  # add 1 as CBR sets rate a day ahead
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
    def MOEX_DataReader(self, asset_code, _isin, start_timestamp, end_timestamp):
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

        date1 = datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d')
        date2 = datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d')
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
    def Yahoo_Downloader(self, asset_code, _isin, start_timestamp, end_timestamp):
        url = f"https://query1.finance.yahoo.com/v7/finance/download/{asset_code}?"\
              f"period1={start_timestamp}&period2={end_timestamp}&interval=1d&events=history"
        file = StringIO(get_web_data(url))
        data = pd.read_csv(file)
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d")
        data = data.drop(columns=['Open', 'High', 'Low', 'Adj Close', 'Volume'])
        close = data.set_index("Date")
        return close

    # noinspection PyMethodMayBeStatic
    def Euronext_DataReader(self, asset_code, isin, start_timestamp, end_timestamp):
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

    def SubmitQuote(self, asset_id, asset_name, timestamp, quote):
        old_id = 0
        query = executeSQL(self.db,
                           "SELECT id FROM quotes WHERE asset_id = :asset_id AND timestamp = :timestamp",
                           [(":asset_id", asset_id), (":timestamp", timestamp)])
        if query.next():
            old_id = query.value(0)
        if old_id:
            executeSQL(self.db, "UPDATE quotes SET quote=:quote WHERE id=:old_id",
                       [(":quote", quote), (":old_id", old_id), ])
        else:
            executeSQL(self.db, "INSERT INTO quotes(timestamp, asset_id, quote) VALUES (:timestamp, :asset_id, :quote)",
                       [(":timestamp", timestamp), (":asset_id", asset_id), (":quote", quote)])
        self.db.commit()
        logging.info(g_tr('QuotesUpdateDialog', "Quote loaded: ") +
                     f"{asset_name} @ {datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')} = {quote}")
