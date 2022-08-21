import pandas as pd
from datetime import datetime
from decimal import Decimal
from pandas._testing import assert_frame_equal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_moex
from tests.helpers import create_stocks, create_assets
from jal.db.helpers import readSQL
from jal.db.asset import JalAsset
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
    assert QuoteDownloader.MOEX_find_secid(reg_number='') == ''
    assert QuoteDownloader.MOEX_find_secid(isin='TEST') == ''
    assert QuoteDownloader.MOEX_find_secid(reg_number='2770') == 'RU000A1013V9'
    assert QuoteDownloader.MOEX_find_secid(reg_number='1-01-00010-A') == 'AFLT'
    assert QuoteDownloader.MOEX_find_secid(isin='IE00B8XB7377') == 'FXGD'
    assert QuoteDownloader.MOEX_find_secid(isin='JE00B6T5S470') == 'POLY'
    assert QuoteDownloader.MOEX_find_secid(isin='RU000A1038V6') == 'SU26238RMFS4'
    assert QuoteDownloader.MOEX_find_secid(isin='IE00B8XB7377', reg_number='CEOGCS') == 'FXGD'

    assert QuoteDownloader.MOEX_info() == {}
    assert QuoteDownloader.MOEX_info(special=True) == {}
    assert QuoteDownloader.MOEX_info(symbol='AFLT', special=True) == {'symbol': 'AFLT',
                                                                      'isin': 'RU0009062285',
                                                                      'name': 'Аэрофлот-росс.авиалин(ПАО)ао',
                                                                      'principal': 1.0,
                                                                      'reg_number': '1-01-00010-A',
                                                                      'engine': 'stock',
                                                                      'market': 'shares',
                                                                      'board': 'TQBR',
                                                                      'type': PredefinedAsset.Stock}
    assert QuoteDownloader.MOEX_info(isin='RU000A0JWUE9', special=True) == {'symbol': 'СберБ БО37',
                                                                            'isin': 'RU000A0JWUE9',
                                                                            'name': 'Сбербанк ПАО БО-37',
                                                                            'principal': 1000.0,
                                                                            'reg_number': '4B023701481B',
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
    assert QuoteDownloader.MOEX_info(symbol='', reg_number='2770') == {'symbol': 'ЗПИФ ПНК',
                                                                      'isin': 'RU000A1013V9',
                                                                      'name': 'ЗПИФ Фонд ПНК-Рентал',
                                                                      'reg_number': '2770',
                                                                      'type': PredefinedAsset.ETF}
    assert QuoteDownloader.MOEX_info(isin='IE00B8XB7377', reg_number='IE00B8XB7377', symbol='FXGD ETF') == {'symbol': 'FXGD',
                                                                                                           'isin': 'IE00B8XB7377',
                                                                                                           'name': 'FinEx Gold ETF USD',
                                                                                                           'type': PredefinedAsset.ETF}
    assert QuoteDownloader.MOEX_info(symbol='FXGD', currency='USD', special=True) == {"symbol": "FXGD",
                                                                                      "isin": "IE00B8XB7377",
                                                                                      "name": "FinEx Gold ETF USD",
                                                                                      "board": "TQTD",
                                                                                      "engine": "stock",
                                                                                      "market": "shares",
                                                                                      "type": PredefinedAsset.ETF}
    assert QuoteDownloader.MOEX_info(isin='JE00B6T5S470', reg_number='', symbol='') == {'symbol': 'POLY',
                                                                                       'isin': 'JE00B6T5S470',
                                                                                       'name': 'Polymetal International plc',
                                                                                       'type': PredefinedAsset.Stock}
    assert QuoteDownloader.MOEX_info(isin='RU000A1038V6') == {'symbol': 'SU26238RMFS4',
                                                              'isin': 'RU000A1038V6',
                                                              'name': 'ОФЗ-ПД 26238 15/05/2041',
                                                              'principal': 1000.0,
                                                              'reg_number': '26238RMFS',
                                                              'expiry': 2252188800,
                                                              'type': PredefinedAsset.Bond}

    assert QuoteDownloader.MOEX_info(**{'isin': 'RU0009062285',
                                        'reg_number': '1-01-00010-A',
                                        'symbol': 'Аэрофлот'}) == {'symbol': 'RU0009062285',
                                                                   'name': 'ОАО "Аэрофлот-росс.авл " (2 в)',
                                                                   'reg_number': '1-02-00010-A',
                                                                   'principal': 1.0,
                                                                   'type': PredefinedAsset.Stock}

def test_CBR_downloader(prepare_db):
    create_stocks([(4, 'TRY', '')], currency_id=1)
    codes = pd.DataFrame({'ISO_name': ['AUD', 'ATS'], 'CBR_code': ['R01010', 'R01015']})

    downloader = QuoteDownloader()
    downloader.PrepareRussianCBReader()
    assert_frame_equal(codes, downloader.CBR_codes.head(2))

    rates_usd = pd.DataFrame({'Rate': [Decimal('77.5104'), Decimal('77.2535'), Decimal('75.6826')],
                          'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14), datetime(2021, 4, 15)]})
    rates_usd = rates_usd.set_index('Date')
    rates_downloaded = downloader.CBR_DataReader(JalAsset(2), 1, 1618272000, 1618358400)
    assert_frame_equal(rates_usd, rates_downloaded)

    rates_try = pd.DataFrame({'Rate': [Decimal('9.45087'), Decimal('9.49270'), Decimal('9.37234')],
                              'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14), datetime(2021, 4, 15)]})
    rates_try = rates_try.set_index('Date')
    rates_downloaded = downloader.CBR_DataReader(JalAsset(4), 1, 1618272000, 1618358400)
    assert_frame_equal(rates_try, rates_downloaded)

def test_MOEX_downloader(prepare_db_moex):
    create_assets([(8, 'ЗПИФ ПНК', 'ЗПИФ ПНК Рентал', 'RU000A1013V9', 1, PredefinedAsset.ETF, 0)])
    stock_quotes = pd.DataFrame({'Close': [Decimal('287.95'), Decimal('287.18')],
                                 'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14)]})
    stock_quotes = stock_quotes.set_index('Date')
    bond_quotes = pd.DataFrame({'Close': [Decimal('1001.00'), Decimal('999.31')],
                                'Date': [datetime(2021, 7, 22), datetime(2021, 7, 23)]})
    bond_quotes = bond_quotes.set_index('Date')
    corp_quotes = pd.DataFrame({'Close': [Decimal('1002.90'), Decimal('1003.70')],
                                'Date': [datetime(2021, 7, 22), datetime(2021, 7, 23)]})
    corp_quotes = corp_quotes.set_index('Date')
    etf_quotes = pd.DataFrame({'Close': [Decimal('1736.8'), Decimal('1735.0')],
                               'Date': [datetime(2021, 12, 13), datetime(2021, 12, 14)]})
    etf_quotes = etf_quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(4), 1, 1618272000, 1618358400)
    assert_frame_equal(stock_quotes, quotes_downloaded)
    assert readSQL("SELECT * FROM assets_ext WHERE id=4") == [4, PredefinedAsset.Stock, 'SBER', '', 'RU0009029540', 1, 0, -1]
    assert readSQL("SELECT value FROM asset_data WHERE asset_id=4 AND datatype=1") == '10301481B'

    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(6), 1, 1626912000, 1626998400)
    assert_frame_equal(bond_quotes, quotes_downloaded)
    assert readSQL("SELECT * FROM assets_ext WHERE id=6") == [6, PredefinedAsset.Bond, 'SU26238RMFS4', '', 'RU000A1038V6', 1, 0, -1]
    assert readSQL("SELECT value FROM asset_data WHERE asset_id=6 AND datatype=1") == '26238RMFS'
    assert readSQL("SELECT value FROM asset_data WHERE asset_id=6 AND datatype=2") == '2252188800'
    assert readSQL("SELECT value FROM asset_data WHERE asset_id=6 AND datatype=3") == '1000'

    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(7), 1, 1626912000, 1626998400)
    assert_frame_equal(corp_quotes, quotes_downloaded)
    assert readSQL("SELECT * FROM assets_ext WHERE id=7") == [7, PredefinedAsset.Bond, 'МКБ 1P2', '', 'RU000A1014H6', 1, 0, -1]
    assert readSQL("SELECT value FROM asset_data WHERE asset_id=7 AND datatype=1") == '4B020901978B001P'
    assert readSQL("SELECT value FROM asset_data WHERE asset_id=7 AND datatype=2") == '1638230400'
    assert readSQL("SELECT value FROM asset_data WHERE asset_id=7 AND datatype=3") == '1000'

    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(8), 1, 1639353600, 1639440000, update_symbol=False)
    assert_frame_equal(etf_quotes, quotes_downloaded)


def test_MOEX_downloader_USD(prepare_db_moex):
    create_assets([(8, 'FXGD', 'FinEx Gold ETF', 'IE00B8XB7377', 2, PredefinedAsset.ETF, 0)])
    usd_quotes = pd.DataFrame({'Close': [Decimal('12.02'), Decimal('11.90')],
                               'Date': [datetime(2021, 12, 13), datetime(2021, 12, 14)]})
    usd_quotes = usd_quotes.set_index('Date')
    downloader = QuoteDownloader()
    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(8), 2, 1639353600, 1639440000, update_symbol=False)
    assert_frame_equal(usd_quotes, quotes_downloaded)


def test_NYSE_downloader(prepare_db):
    create_stocks([(4, 'AAPL', '')], currency_id=2)
    quotes = pd.DataFrame({'Close': [Decimal('134.429993'), Decimal('132.029999')],
                           'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Yahoo_Downloader(JalAsset(4), 2, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)


def test_LSE_downloader(prepare_db):
    create_stocks([(4, 'TSL', '')], currency_id=3)
    quotes = pd.DataFrame({'Close': [Decimal('73.5'), Decimal('75.5')],
                           'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.YahooLSE_Downloader(JalAsset(4), 3, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)


def test_Euronext_downloader(prepare_db):
    create_assets([(4, 'NOK', 'Nokia', 'FI0009000681', 3, PredefinedAsset.Stock, 0)])
    quotes = pd.DataFrame({'Close': [Decimal('3.4945'), Decimal('3.50'), Decimal('3.4995')],
                           'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14), datetime(2021, 4, 15)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Euronext_DataReader(JalAsset(4), 3, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)


def test_TMX_downloader(prepare_db):
    create_stocks([(4, 'RY', '')], currency_id=3)
    quotes = pd.DataFrame({'Close': [Decimal('117.18'), Decimal('117.34'), Decimal('118.02')],
                           'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14), datetime(2021, 4, 15)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.TMX_Downloader(JalAsset(4), 3, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)


def test_Frankfurt_downloader(prepare_db):
    create_stocks([(4, 'VOW3', '')], currency_id=3)
    quotes = pd.DataFrame({'Close': [Decimal('233.399994'), Decimal('234.250000')],
                           'Date': [datetime(2021, 4, 13), datetime(2021, 4, 14)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.YahooFRA_Downloader(JalAsset(4), 3, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)
