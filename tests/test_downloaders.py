import pandas as pd
from decimal import Decimal
from pandas._testing import assert_frame_equal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_moex
from tests.helpers import d2t, d2dt, create_stocks, create_assets
from jal.db.asset import JalAsset
from jal.constants import PredefinedAsset
from jal.net.helpers import isEnglish
from jal.net.downloader import QuoteDownloader
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS


def test_English():
    assert isEnglish("asdfAF12!@#") == True
    assert isEnglish("asdfБF12!@#") == False
    assert isEnglish("asгfAF12!@#") == False

def test_INN_resolution():
    fns_api = ReceiptRuFNS(qr_text='t=20230101T0000&fn=0&fd=0&fp=0&i=0&n=0&s=0')
    fns_api.slip_json['userInn'] = '7707083893'
    name = fns_api.shop_name()
    assert name == 'ПАО СБЕРБАНК'

def test_MOEX_details():
    assert QuoteDownloader.MOEX_find_secid(reg_number='') == ''
    assert QuoteDownloader.MOEX_find_secid(isin='TEST') == ''
    assert QuoteDownloader.MOEX_find_secid(reg_number='0252-74113866') == 'RU000A0ERGA7'
    assert QuoteDownloader.MOEX_find_secid(reg_number='1-01-00010-A') == 'AFLT'
    assert QuoteDownloader.MOEX_find_secid(isin='IE00B8XB7377') == 'FXGD'
    assert QuoteDownloader.MOEX_find_secid(isin='JE00B6T5S470') == 'POLY'
    assert QuoteDownloader.MOEX_find_secid(isin='RU000A1038V6') == 'SU26238RMFS4'
    assert QuoteDownloader.MOEX_find_secid(isin='IE00B8XB7377', reg_number='CEOGCS') == 'FXGD'
    assert QuoteDownloader.MOEX_find_secid(name='МЕТАЛЛОИНВЕСТ 028') == 'RU000A105A04'
    assert QuoteDownloader.MOEX_find_secid(name='АБЗ-1 1Р01') == 'RU000A102LW1'

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
    assert QuoteDownloader.MOEX_info(symbol='', reg_number='0252-74113866') == {'symbol': 'ПИФСбер-КН',
                                                                      'isin': 'RU000A0ERGA7',
                                                                      'name': 'ПИФСбербанк Комм.недвижимость',
                                                                      'reg_number': '0252-74113866',
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
                                                                                        'name': 'Solidcore Resources plc',
                                                                                        'principal': 0.03,
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
    assert QuoteDownloader.MOEX_info(symbol='GLDRUB_TOM') == {'symbol': 'GLDRUB_TOM',
                                                              'name': 'GLD/RUB_TOM - GLD/РУБ',
                                                              'principal': 1.0,
                                                              'type': PredefinedAsset.Commodity}

def test_CBR_downloader(prepare_db):
    create_stocks([('TRY', '')], currency_id=1)   # id = 4
    codes = pd.DataFrame({'ISO_name': ['AUD', 'ATS'], 'CBR_code': ['R01010', 'R01015']})

    downloader = QuoteDownloader()
    downloader.PrepareRussianCBReader()
    assert_frame_equal(codes, downloader.CBR_codes.head(2))

    rates_usd = pd.DataFrame({'Rate': [Decimal('77.5104'), Decimal('77.2535'), Decimal('75.6826')],
                          'Date': [d2dt(210413), d2dt(210414), d2dt(210415)]})
    rates_usd = rates_usd.set_index('Date')
    rates_downloaded = downloader.CBR_DataReader(JalAsset(2), 1618272000, 1618358400)
    assert_frame_equal(rates_usd, rates_downloaded)

    rates_try = pd.DataFrame({'Rate': [Decimal('9.45087'), Decimal('9.49270'), Decimal('9.37234')],
                              'Date': [d2dt(210413), d2dt(210414), d2dt(210415)]})
    rates_try = rates_try.set_index('Date')
    rates_downloaded = downloader.CBR_DataReader(JalAsset(4), 1618272000, 1618358400)
    assert_frame_equal(rates_try, rates_downloaded)

def test_ECB_downloader(prepare_db):
    rates_usd = pd.DataFrame({'Rate': [Decimal('0.8406186954'), Decimal('0.8358408559')],
                              'Date': [d2dt(210413), d2dt(210414)]})
    rates_usd = rates_usd.set_index('Date')
    downloader = QuoteDownloader()
    rates_downloaded = downloader.ECB_DataReader(JalAsset(2), d2t(210413), d2t(210414))
    assert_frame_equal(rates_usd, rates_downloaded)

def test_MOEX_downloader(prepare_db_moex):
    create_assets([('ЗПИФ ПНК', 'ЗПИФ ПНК Рентал', 'RU000A1013V9', 1, PredefinedAsset.ETF, 0),         # ID 9
                   ('TEST', 'TEST', '', 1, PredefinedAsset.Stock, 0),                                  # ID 10
                   ('БДеньги-02', 'МФК Быстроденьги 02', 'RU000A102ZT7', 1, PredefinedAsset.Bond, 0),  # ID 11
                   ('GLDRUB_TOM', 'GLD/RUB_TOM - GLD/РУБ', '', 1, PredefinedAsset.Commodity, 0)])      # ID 12

    stock_quotes = pd.DataFrame({'Close': [Decimal('287.95'), Decimal('287.18')],
                                 'Date': [d2dt(210413), d2dt(210414)]})
    stock_quotes = stock_quotes.set_index('Date')
    bond_quotes = pd.DataFrame({'Close': [Decimal('1001.00'), Decimal('999.31')],
                                'Date': [d2dt(210722), d2dt(210723)]})
    bond_quotes = bond_quotes.set_index('Date')
    corp_quotes = pd.DataFrame({'Close': [Decimal('1002.90'), Decimal('1003.70')],
                                'Date': [d2dt(210722), d2dt(210723)]})
    corp_quotes = corp_quotes.set_index('Date')
    etf_quotes = pd.DataFrame({'Close': [Decimal('1736.8'), Decimal('1735.0')],
                               'Date': [d2dt(211213), d2dt(211214)]})
    etf_quotes = etf_quotes.set_index('Date')
    bond_quotes2 = pd.DataFrame({'Close': [Decimal('984.30'), Decimal('981.50')],
                                'Date': [d2dt(230913), d2dt(230914)]})
    bond_quotes2 = bond_quotes2.set_index('Date')
    metal_quotes = pd.DataFrame({'Close': [Decimal('5890.8'), Decimal('5870.03')],
                                 'Date': [d2dt(240206), d2dt(240207)]})
    metal_quotes = metal_quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(4), 1, d2t(210413), d2t(210414))
    assert_frame_equal(stock_quotes, quotes_downloaded)
    sber = JalAsset(4)
    assert sber.type() == PredefinedAsset.Stock
    assert sber.isin() == 'RU0009029540'
    assert sber.symbol(1) == 'SBER'
    assert sber.name() == ''
    assert sber.reg_number() == '10301481B'

    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(6), 1, d2t(210722), d2t(210723))
    assert_frame_equal(bond_quotes, quotes_downloaded)
    bond = JalAsset(6)
    assert bond.type() == PredefinedAsset.Bond
    assert bond.isin() == 'RU000A1038V6'
    assert bond.symbol(1) == 'SU26238RMFS4'
    assert bond.name() == ''
    assert bond.reg_number() == '26238RMFS'
    assert bond.expiry() == d2t(410515)
    assert bond.principal() == Decimal('1000')

    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(7), 1, d2t(210722), d2t(210723))
    assert_frame_equal(corp_quotes, quotes_downloaded)
    bond2 = JalAsset(7)
    assert bond2.type() == PredefinedAsset.Bond
    assert bond2.isin() == 'RU000A1014H6'
    assert bond2.symbol(1) == 'МКБ 1P2'
    assert bond2.name() == ''
    assert bond2.reg_number() == '4B020901978B001P'
    assert bond2.expiry() == d2t(211130)
    assert bond2.principal() == Decimal('1000')
    # Test of quotes download for PNK Rental Fund
    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(9), 1, d2t(211213), d2t(211214), update_symbol=False)
    assert_frame_equal(etf_quotes, quotes_downloaded)
    # Test of non-existing asset download
    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(10), 1, d2t(211213), d2t(211214), update_symbol=False)
    assert quotes_downloaded is None
    # Bond with high risk
    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(11), 1, d2t(230913), d2t(230914), update_symbol=False)
    assert_frame_equal(bond_quotes2, quotes_downloaded)
    # Metal
    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(12), 1, d2t(240206), d2t(240207), update_symbol=False)
    assert_frame_equal(metal_quotes, quotes_downloaded)


def test_MOEX_downloader_USD(prepare_db_moex):
    create_assets([('FXGD', 'FinEx Gold ETF', 'IE00B8XB7377', 2, PredefinedAsset.ETF, 0)])   # ID = 9
    create_assets([('ГазКЗ-30Д', 'Газпром капитал ООО ЗО30-1-Д', 'RU000A105SG2', 2, PredefinedAsset.Bond, 0)])

    JalAsset(9).add_symbol('FXGD', 1, 'FinEx Gold ETF - RUB')
    usd_quotes = pd.DataFrame({'Close': [Decimal('12.02'), Decimal('11.90')],
                               'Date': [d2dt(211213), d2dt(211214)]})
    usd_quotes = usd_quotes.set_index('Date')
    downloader = QuoteDownloader()
    quotes_downloaded = downloader.MOEX_DataReader(JalAsset(9), 2, d2t(211213), d2t(211214), update_symbol=False)
    assert_frame_equal(usd_quotes, quotes_downloaded)

    bond_usd_quotes = pd.DataFrame({'Close': [Decimal('846.509'), Decimal('844.998')],
                               'Date': [d2dt(240213), d2dt(240214)]})
    bond_usd_quotes = bond_usd_quotes.set_index('Date')
    bond_quotes = downloader.MOEX_DataReader(JalAsset(10), 2, d2t(240213), d2t(240214))
    assert_frame_equal(bond_quotes, bond_usd_quotes)

def test_NYSE_downloader(prepare_db):
    create_stocks([('AAPL', '')], currency_id=2)   # id = 4
    quotes = pd.DataFrame({'Close': [Decimal('134.429993'), Decimal('132.029999')],
                           'Date': [d2dt(210413), d2dt(210414)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Yahoo_Downloader(JalAsset(4), 2, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)


def test_LSE_downloader(prepare_db):
    create_stocks([('PSON', '')], currency_id=3)   # id = 4
    quotes = pd.DataFrame({'Close': [Decimal('792.599976'), Decimal('800.799988')],
                           'Date': [d2dt(210413), d2dt(210414)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.YahooLSE_Downloader(JalAsset(4), 3, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)


def test_Euronext_downloader(prepare_db):
    create_assets([('NOK', 'Nokia', 'FI0009000681', 3, PredefinedAsset.Stock, 0)])   # ID = 4
    quotes = pd.DataFrame({'Close': [Decimal('4.483'), Decimal('4.481'), Decimal('4.5115')],
                           'Date': [d2dt(230412), d2dt(230413), d2dt(230414)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Euronext_DataReader(JalAsset(4), 3, d2t(230412), d2t(230414))
    assert_frame_equal(quotes, quotes_downloaded)


def test_TMX_downloader(prepare_db):
    create_stocks([('RY', '')], currency_id=3)   # id = 4
    quotes = pd.DataFrame({'Close': [Decimal('117.18'), Decimal('117.34'), Decimal('118.02')],
                           'Date': [d2dt(210413), d2dt(210414), d2dt(210415)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.TMX_Downloader(JalAsset(4), 3, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)


def test_Frankfurt_downloader(prepare_db):
    create_stocks([('VOW3', '')], currency_id=3)   # id = 4
    quotes = pd.DataFrame({'Close': [Decimal('233.399994'), Decimal('234.250000')],
                           'Date': [d2dt(210413), d2dt(210414)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.YahooFRA_Downloader(JalAsset(4), 3, d2t(210413), d2t(210415))
    assert_frame_equal(quotes, quotes_downloaded)

def test_Coinbase_downloader(prepare_db):
    create_assets([('ALGO', 'Algorand', '', 3, PredefinedAsset.Crypto, 0)])  # ID = 4
    quotes = pd.DataFrame({'Close': [Decimal('0.20171559017841111516'), Decimal('0.19595558582536402655'), Decimal('0.20032663919036912874')],
                           'Date': [d2dt(230412), d2dt(230413), d2dt(230414)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Coinbase_Downloader(JalAsset(4), 3, d2t(230412), d2t(230414))
    assert_frame_equal(quotes, quotes_downloaded)
