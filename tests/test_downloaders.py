import pandas as pd
from datetime import datetime
from pandas._testing import assert_frame_equal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_moex
from jal.db.helpers import readSQL
from jal.data_import.downloader import QuoteDownloader
from jal.data_import.slips_tax import SlipsTaxAPI

def test_INN_resolution():
    tax_API = SlipsTaxAPI()
    name = tax_API.get_shop_name_by_inn('7707083893')
    assert name == 'ПАО СБЕРБАНК'

def test_CBR_downloader():
    codes = pd.DataFrame({'ISO_name': ['AUD', 'ATS'], 'CBR_code': ['R01010', 'R01015']})
    rates = pd.DataFrame({'Rate': [77.5104, 77.2535, 75.6826],
                         'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14), datetime(2021, 4, 15)]})
    rates = rates.set_index('Date')

    downloader = QuoteDownloader()
    downloader.PrepareRussianCBReader()
    assert_frame_equal(codes, downloader.CBR_codes.head(2))
    rates_downloaded = downloader.CBR_DataReader(0, 'USD', '', 1618272000, 1618358400)
    assert_frame_equal(rates, rates_downloaded)

def test_MOEX_downloader(prepare_db_moex):
    quotes = pd.DataFrame({'Close': [287.95, 287.18],
                          'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.MOEX_DataReader(4, 'SBER', 'RU0009029540', 1618272000, 1618358400)
    assert_frame_equal(quotes, quotes_downloaded)
    assert readSQL("SELECT * FROM assets WHERE id=4") == [4, 'SBER', 2, '', 'RU0009029540', 0, 0]
    assert readSQL("SELECT * FROM asset_reg_id WHERE asset_id=4") == [4, '10301481B']

def test_Yahoo_downloader():
    quotes = pd.DataFrame({'Close': [134.429993, 132.029999],
                           'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Yahoo_Downloader(0, 'AAPL', '', 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)

def test_Euronext_downloader():
    quotes = pd.DataFrame({'Close': [3.4945, 3.5000, 3.4995],
                           'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14), datetime(2021, 4, 15)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Euronext_DataReader(0, '', 'FI0009000681', 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)

def test_TMX_downloader():
    quotes = pd.DataFrame({'Close': [117.18, 117.34, 118.02],
                           'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14), datetime(2021, 4, 15)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.TMX_Downloader(0, 'RY', '', 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)
