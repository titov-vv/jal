import logging
import xml.etree.ElementTree as xml_tree
from datetime import datetime
from io import StringIO

import pandas as pd
import requests
from PySide2 import QtCore
from PySide2.QtSql import QSqlQuery
from PySide2.QtWidgets import QDialog

from UI.ui_update_quotes_window import Ui_UpdateQuotesDlg
from constants import *


# ===================================================================================================================
# Function downlaod URL and return it content as string or empty string if site returns error
# ===================================================================================================================
def get_web_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        logging.error(f"URL: {url} failed with {response}")
        return ''


# ===================================================================================================================
# UI dialog class
# ===================================================================================================================
class QuotesUpdateDialog(QDialog, Ui_UpdateQuotesDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.StartDateEdit.setDate(QtCore.QDate.currentDate().addMonths(-1))
        self.EndDateEdit.setDate(QtCore.QDate.currentDate())

    def getStartDate(self):
        return self.StartDateEdit.dateTime().toSecsSinceEpoch()

    def getEndDate(self):
        return self.EndDateEdit.dateTime().toSecsSinceEpoch()

    def getUseProxy(self):
        return self.UseProxyCheck.isChecked()


# ===================================================================================================================
# Worker class
# ===================================================================================================================
class QuoteDownloader:
    def __init__(self, db):
        self.db = db
        self.CBR_codes = None

    def UpdateQuotes(self, start_timestamp, end_timestamp, use_proxy):
        if use_proxy:
            logging.fatal("Download via proxy is not implemented")
            return

        self.PrepareRussianCBReader()

        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM holdings_aux")

        # Collect list of assets that are held on end date
        assert query.prepare(
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
            "AND l.timestamp >= :start_timestamp AND l.timestamp <= :end_timestamp")
        query.bindValue(":start_timestamp", start_timestamp)
        query.bindValue(":end_timestamp", end_timestamp)
        query.bindValue(":tolerance", CALC_TOLERANCE)
        assert query.exec_()

        # Get a list of symbols ordered by data source ID
        assert query.prepare("SELECT h.asset, a.name, a.src_id, a.isin, MAX(q.timestamp) AS last_timestamp "
                             "FROM holdings_aux AS h "
                             "LEFT JOIN assets AS a ON a.id=h.asset "
                             "LEFT JOIN quotes AS q ON q.asset_id=h.asset "
                             "GROUP BY h.asset "
                             "ORDER BY a.src_id")
        query.setForwardOnly(True)
        assert query.exec_()
        while query.next():
            asset_id = query.value(0)
            asset = query.value(1)
            feed_id = query.value(2)
            isin = query.value(3)
            last_timestamp = query.value(4)
            if last_timestamp == '':
                last_timestamp = 0
            if last_timestamp > start_timestamp:
                from_timestamp = last_timestamp
            else:
                from_timestamp = start_timestamp
            try:
                if feed_id == FEED_NONE:
                    continue
                elif feed_id == FEED_CBR:
                    data = self.CBR_DataReader(asset, from_timestamp, end_timestamp)
                elif feed_id == FEED_RU:
                    data = self.MOEX_DataReader(asset, from_timestamp, end_timestamp)
                elif feed_id == FEED_EU:
                    data = self.Euronext_DataReader(asset, isin, from_timestamp, end_timestamp)
                elif feed_id == FEED_US:
                    data = self.Yahoo_Downloader(asset, from_timestamp, end_timestamp)
                else:
                    logging.error(f"Data feed {feed_id} is not implemented")
                    continue
            except (xml_tree.ParseError, pd.errors.EmptyDataError):
                logging.warning(f"No data were downloaded for {asset}")
                continue
            for date, quote in data.iterrows():
                self.SubmitQuote(asset_id, asset, int(date.timestamp()), float(quote[0]))
        logging.info("Download completed")

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

    def CBR_DataReader(self, currency_code, start_timestamp, end_timestamp):
        date1 = datetime.fromtimestamp(start_timestamp).strftime('%d/%m/%Y')
        date2 = datetime.fromtimestamp(end_timestamp + 86400).strftime(
            '%d/%m/%Y')  # Add 1 day as CBR sets rate a day ahead
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
    def MOEX_DataReader(self, asset_code, start_timestamp, end_timestamp):
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
            logging.error(f"Failed to find {asset_code} at {url}")
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
    def Yahoo_Downloader(self, asset_code, start_timestamp, end_timestamp):
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
        query = QSqlQuery(self.db)
        assert query.prepare("SELECT id FROM quotes WHERE asset_id = :asset_id AND timestamp = :timestamp")
        query.bindValue(":asset_id", asset_id)
        query.bindValue(":timestamp", timestamp)
        assert query.exec_()
        while query.next():
            old_id = query.value(0)
        if old_id:
            assert query.prepare("UPDATE quotes SET quote=:quote WHERE id=:old_id")
            query.bindValue(":old_id", old_id)
        else:
            assert query.prepare(
                "INSERT INTO quotes(timestamp, asset_id, quote) VALUES (:timestamp, :asset_id, :quote)")
            query.bindValue(":timestamp", timestamp)
            query.bindValue(":asset_id", asset_id)
        query.bindValue(":quote", quote)
        assert query.exec_()
        self.db.commit()
        logging.info(
            f"Quote loaded: {asset_name} @ {datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')} = {quote}")
