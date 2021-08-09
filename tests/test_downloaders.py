import pandas as pd
from datetime import datetime
from pandas._testing import assert_frame_equal

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
