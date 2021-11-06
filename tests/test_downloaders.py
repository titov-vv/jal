import pandas as pd
from datetime import datetime
from pandas._testing import assert_frame_equal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_moex
from jal.db.helpers import readSQL
from jal.constants import PredefinedAsset
from jal.net.helpers import isEnglish
from jal.net.downloader import QuoteDownloader
from jal.data_import.slips_tax import SlipsTaxAPI


def test_English():
    assert isEnglish("asdfAF12!@#") == True
    assert isEnglish("asdfБF12!@#") == False
    assert isEnglish("asгfAF12!@#") == False

def test_INN_resolution():
    tax_API = SlipsTaxAPI()
    name = tax_API.get_shop_name_by_inn('7707083893')
    assert name == 'ПАО СБЕРБАНК'

def test_MOEX_details():
    assert QuoteDownloader.MOEX_find_secid(regcode='') == ''
    assert QuoteDownloader.MOEX_find_secid(isin='TEST') == ''
    assert QuoteDownloader.MOEX_find_secid(regcode='2770') == 'RU000A1013V9'
    assert QuoteDownloader.MOEX_find_secid(regcode='1-01-00010-A') == 'AFLT'
    assert QuoteDownloader.MOEX_find_secid(isin='IE00B8XB7377') == 'FXGD'
    assert QuoteDownloader.MOEX_find_secid(isin='JE00B6T5S470') == 'POLY'
    assert QuoteDownloader.MOEX_find_secid(isin='RU000A1038V6') == 'SU26238RMFS4'

    assert QuoteDownloader.MOEX_info() == {}
    assert QuoteDownloader.MOEX_info(special=True) == {}
    assert QuoteDownloader.MOEX_info(symbol='AFLT', special=True) == {'symbol': 'AFLT',
                                                                      'isin': 'RU0009062285',
                                                                      'name': 'Аэрофлот-росс.авиалин(ПАО)ао',
                                                                      'principal': 1.0,
                                                                      'reg_code': '1-01-00010-A',
                                                                      'engine': 'stock',
                                                                      'market': 'shares',
                                                                      'board': 'TQBR',
                                                                      'type': PredefinedAsset.Stock}
    assert QuoteDownloader.MOEX_info(isin='RU000A0JWUE9', special=True) == {'symbol': 'СберБ БО37',
                                                                            'isin': 'RU000A0JWUE9',
                                                                            'name': 'Сбербанк ПАО БО-37',
                                                                            'principal': 1000.0,
                                                                            'reg_code': '4B023701481B',
                                                                            'expiry': 1632960000,
                                                                            'engine': 'stock',
                                                                            'market': 'bonds',
                                                                            'board': 'TQCB',
                                                                            'type': PredefinedAsset.Bond}
    assert QuoteDownloader.MOEX_info(symbol='SiZ1', isin='', special=True) == {'symbol': 'SiZ1',
                                                                               'name': 'Фьючерсный контракт Si-12.21',
                                                                               'expiry': 1639612800,
                                                                               'engine': 'futures',
                                                                               'market': 'forts',
                                                                               'board': 'RFUD',
                                                                               'type': PredefinedAsset.Derivative}
    assert QuoteDownloader.MOEX_info(symbol='', regnumber='2770') == {'symbol': 'ЗПИФ ПНК',
                                                                      'isin': 'RU000A1013V9',
                                                                      'name': 'ЗПИФ Фонд ПНК-Рентал',
                                                                      'reg_code': '2770',
                                                                      'type': PredefinedAsset.ETF}
    assert QuoteDownloader.MOEX_info(isin='IE00B8XB7377', regnumber='IE00B8XB7377', symbol='FXGD ETF') == {'symbol': 'FXGD',
                                                                                                           'isin': 'IE00B8XB7377',
                                                                                                           'name': 'FinEx Gold ETF USD',
                                                                                                           'type': PredefinedAsset.ETF}
    assert QuoteDownloader.MOEX_info(isin='JE00B6T5S470', regnumber='', symbol='') == {'symbol': 'POLY',
                                                                                       'isin': 'JE00B6T5S470',
                                                                                       'name': 'Polymetal International plc',
                                                                                       'type': PredefinedAsset.Stock}
    assert QuoteDownloader.MOEX_info(isin='RU000A1038V6') == {'symbol': 'SU26238RMFS4',
                                                              'isin': 'RU000A1038V6',
                                                              'name': 'ОФЗ-ПД 26238 15/05/2041',
                                                              'principal': 1000.0,
                                                              'reg_code': '26238RMFS',
                                                              'expiry': 2252188800,
                                                              'type': PredefinedAsset.Bond}

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
    stock_quotes = pd.DataFrame({'Close': [287.95, 287.18],
                                 'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14)]})
    stock_quotes = stock_quotes.set_index('Date')
    bond_quotes = pd.DataFrame({'Close': [1001.00, 999.31],
                                'Date': [datetime(2021, 7, 22), datetime(2021, 7, 23)]})
    bond_quotes = bond_quotes.set_index('Date')
    corp_quotes = pd.DataFrame({'Close': [1002.90, 1003.70],
                                'Date': [datetime(2021, 7, 22), datetime(2021, 7, 23)]})
    corp_quotes = corp_quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.MOEX_DataReader(4, 'SBER', 'RU0009029540', 1618272000, 1618358400)
    assert_frame_equal(stock_quotes, quotes_downloaded)
    assert readSQL("SELECT * FROM assets WHERE id=4") == [4, 'SBER', PredefinedAsset.Stock, '', 'RU0009029540', 0, 0, 0]
    assert readSQL("SELECT * FROM asset_reg_id WHERE asset_id=4") == [4, '10301481B']

    quotes_downloaded = downloader.MOEX_DataReader(6, 'SU26238RMFS4', 'RU000A1038V6', 1626912000, 1626998400)
    assert_frame_equal(bond_quotes, quotes_downloaded)
    assert readSQL("SELECT * FROM assets WHERE id=6") == [6, 'SU26238RMFS4', PredefinedAsset.Bond, '', 'RU000A1038V6', 0, 0, 2252188800]
    assert readSQL("SELECT * FROM asset_reg_id WHERE asset_id=6") == [6, '26238RMFS']

    quotes_downloaded = downloader.MOEX_DataReader(7, 'МКБ 1P2', 'RU000A1014H6', 1626912000, 1626998400)
    print(quotes_downloaded)
    assert_frame_equal(corp_quotes, quotes_downloaded)
    assert readSQL("SELECT * FROM assets WHERE id=7") == [7, 'МКБ 1P2', 3, '', 'RU000A1014H6', 0, 0, 1638230400]
    assert readSQL("SELECT * FROM asset_reg_id WHERE asset_id=7") == [7, '4B020901978B001P']

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
