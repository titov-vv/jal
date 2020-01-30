from constants import *
import requests
from datetime import datetime
from PySide2.QtSql import QSqlQuery
import pandas as pd
import pandas_datareader.data as web
import xml.etree.ElementTree as xml_tree
from io import StringIO

class QuoteDownloader:
    def __init__(self, db):
        self.db = db

        # proxies = {"http": "http://135.245.192.7:8000",
        #            "https": "http://135.245.192.7:8000"}
        self.session = requests.Session()
        # self.session.proxies = proxies

    def UpdateQuotes(self, start_timestamp, end_timestamp):
        self.PrepareRussianCBReader()

        query = QSqlQuery(self.db)
        assert query.exec_("DELETE FROM holdings_aux")

        # Collect list of assets that are held on end date
        assert query.prepare(
            "INSERT INTO holdings_aux(asset) "
            "SELECT l.active_id AS asset FROM ledger AS l "
            "WHERE l.book_account = 4 AND l.timestamp <= :end_timestamp "
            "GROUP BY l.active_id "
            "HAVING sum(l.amount) > :tolerance "
            "UNION "
            "SELECT DISTINCT l.active_id AS asset FROM ledger AS l "
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
        assert query.prepare("SELECT h.asset, a.name, a.src_id, a.isin FROM holdings_aux AS h "
                             "LEFT JOIN actives AS a ON a.id=h.asset "
                             "ORDER BY a.src_id")
        query.setForwardOnly(True)
        assert query.exec_()
        while query.next():
            asset_id = query.value(0)
            asset = query.value(1)
            feed_id = query.value(2)
            isin = query.value(3)
            print("LOAD: ", asset)
            if (feed_id == FEED_NONE):
                continue
            elif (feed_id == FEED_CBR):
                data = self.CBR_DataReader(asset, start_timestamp, end_timestamp)
            elif (feed_id == FEED_RU):
                data = self.MOEX_DataReader(asset, start_timestamp, end_timestamp)
            elif (feed_id == FEED_EU):
                data = self.Euronext_DataReader(asset, isin, start_timestamp, end_timestamp)
            elif (feed_id == FEED_US):
                data = self.US_DataReader(asset, start_timestamp, end_timestamp)
            else:
                print(f"Data feed {feed_id} is not implemented")
                continue
            for date, quote in data.iterrows():
                self.SubmitQuote(asset_id, int(date.timestamp()), float(quote[0]))

    def PrepareRussianCBReader(self):
        xml_root = xml_tree.fromstring(requests.get("http://www.cbr.ru/scripts/XML_valFull.asp").text)
        rows = []
        for node in xml_root:
            code = node.find("ParentCode").text if node is not None else None
            iso = node.find("ISO_Char_Code").text if node is not None else None
            rows.append({"ISO_name": iso, "CBR_code": code})
        self.CBR_codes = pd.DataFrame(rows, columns=["ISO_name", "CBR_code"])

    def CBR_DataReader(self, currency_code, start_timestamp, end_timestamp):
        date1 = datetime.fromtimestamp(start_timestamp).strftime('%d/%m/%Y')
        date2 = datetime.fromtimestamp(end_timestamp).strftime('%d/%m/%Y')
        code = str(self.CBR_codes.loc[self.CBR_codes["ISO_name"] == currency_code, "CBR_code"].values[0]).strip()
        xml_root = xml_tree.fromstring(requests.get(
            f"http://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={date1}&date_req2={date2}&VAL_NM_RQ={code}").text)
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

    def MOEX_DataReader(self, asset_code, start_timestamp, end_timestamp):
        # Get primary board ID
        xml_root = xml_tree.fromstring(requests.get(f"http://iss.moex.com/iss/securities/{asset_code}.xml").text)
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

        date1 = datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d')
        date2 = datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d')
        xml_root = xml_tree.fromstring(requests.get(
            f"http://iss.moex.com/iss/history/engines/{engine}/markets/{market}/boards/{board_id}/securities/{asset_code}.xml?from={date1}&till={date2}").text)
        for node in xml_root:
            if node.tag == 'data' and node.attrib['id'] == 'history':
                sections = list(node)
                for section in sections:
                    if section.tag == "rows":
                        hisotry_rows = list(section)
                        rows = []
                        for row in hisotry_rows:
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

    def US_DataReader(self, asset_code, start_timestamp, end_timestamp):
        # data = web.DataReader(asset_code, 'yahoo', start=datetime.fromtimestamp(start_timestamp),
        #                end=datetime.fromtimestamp(end_timestamp), session=self.session)
        # close = data.drop(columns=['High', 'Low', 'Open', 'Volume', 'Adj Close'])
        date1 = datetime.fromtimestamp(start_timestamp).strftime('%Y%m%d')
        date2 = datetime.fromtimestamp(end_timestamp).strftime('%Y%m%d')
        web_data = requests.get(f"https://stooq.com/q/d/l/?s={asset_code}.US&i=d&d1={date1}&d2={date2}").text
        file = StringIO(web_data)
        data = pd.read_csv(file)
        data['Date'] = pd.to_datetime(data['Date'], format="%Y-%m-%d")
        data = data.drop(columns=['Open', 'High', 'Low', 'Volume'])
        close = data.set_index("Date")
        return close

    def Euronext_DataReader(self, asset_code, isin, start_timestamp, end_timestamp):
        start = int(start_timestamp * 1000)
        end = int(end_timestamp * 1000)
        web_data = requests.get(
            f"https://euconsumer.euronext.com/nyx_eu_listings/price_chart/download_historical?typefile=csv&layout=vertical&typedate=dmy&separator=point&mic=XPAR&isin={isin}&name={asset_code}&namefile=Price_Data_Historical&from={start}&to={end}&adjusted=1&base=0").text
        file = StringIO(web_data)
        data = pd.read_csv(file, header=3)
        data['Date'] = pd.to_datetime(data['Date'], format="%d/%m/%Y")
        data = data.drop(
            columns=['ISIN', 'MIC', 'Ouvert', 'Haut', 'Bas', 'Nombre de titres', 'Number of Trades', 'Capitaux',
                     'Devise'])
        close = data.set_index("Date")
        return close

    # TODO check that values are rounded as it should be
    def SubmitQuote(self, asset_id, timestamp, quote):
        old_id = 0
        query = QSqlQuery(self.db)
        assert query.prepare("SELECT id FROM quotes WHERE active_id = :asset_id AND timestamp = :timestamp")
        query.bindValue(":asset_id", asset_id)
        query.bindValue(":timestamp", timestamp)
        assert query.exec_()
        while query.next():
            old_id = query.value(0)
        if old_id:
            assert query.prepare("UPDATE quotes SET quote=:quote WHERE id=:old_id")
            query.bindValue(":old_id", old_id)
        else:
            assert query.prepare("INSERT INTO quotes(timestamp, active_id, quote) VALUES (:timestamp, :asset_id, :quote)")
            query.bindValue(":timestamp", timestamp)
            query.bindValue(":asset_id", asset_id)
        query.bindValue(":quote", quote)
        assert query.exec_()
        self.db.commit()
        print("LOADED: ", asset_id, timestamp, quote)

