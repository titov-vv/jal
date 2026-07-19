import pandas as pd
from decimal import Decimal
from pandas._testing import assert_frame_equal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_moex
from tests.helpers import d2t, d2dt, dt2dt, create_stocks, create_assets, symbol_id_for
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol
from jal.constants import AssetLocation, PredefinedAsset, SymbolId
from jal.net.downloader import QuoteDownloader, llama_coin_key, parse_llama_chart
from jal.net.moex import MOEX
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS


def test_INN_resolution():
    fns_api = ReceiptRuFNS(qr_text='t=20230101T0000&fn=0&fd=0&fp=0&i=0&n=0&s=0')
    fns_api.slip_json['userInn'] = '7707083893'
    name = fns_api.shop_name()
    assert name == 'ПАО СБЕРБАНК'

def test_MOEX_lookup():
    assert MOEX().find_asset(reg_number='') == ''
    assert MOEX().find_asset(isin='TEST') == ''
    assert MOEX().find_asset(reg_number='0252-74113866') == 'RU000A0ERGA7'
    assert MOEX().find_asset(reg_number='1-01-00010-A') == 'AFLT'
    assert MOEX().find_asset(isin='IE00B8XB7377') == 'FXGD'
    assert MOEX().find_asset(isin='JE00B6T5S470') == 'POLY'
    assert MOEX().find_asset(isin='RU000A1038V6') == 'SU26238RMFS4'
    assert MOEX().find_asset(isin='IE00B8XB7377', reg_number='CEOGCS') == 'FXGD'
    assert MOEX().find_asset(name='МЕТАЛЛОИНВЕСТ 028') == 'RU000A105A04'
    assert MOEX().find_asset(name='АБЗ-1 1Р01') == 'RU000A102LW1'
    assert MOEX().find_asset(name='CNY-9.24') == 'CRU4'

def test_MOEX_details():
    assert MOEX().asset_info() == {}
    assert MOEX().asset_info(special=True) == {}
    assert MOEX().asset_info(symbol='AFLT', special=True) == {'symbol': 'AFLT',
                                                                      'isin': 'RU0009062285',
                                                                      'name': 'Аэрофлот-росс.авиалин(ПАО)ао',
                                                                      'principal': 1.0,
                                                                      'reg_number': '1-01-00010-A',
                                                                      'engine': 'stock',
                                                                      'market': 'shares',
                                                                      'board': 'TQBR',
                                                                      'type': PredefinedAsset.Stock}
    assert MOEX().asset_info(isin='RU000A0JWUE9', special=True) == {'symbol': 'СберБ БО37',
                                                                            'isin': 'RU000A0JWUE9',
                                                                            'name': 'Сбербанк ПАО БО-37',
                                                                            'principal': 1000.0,
                                                                            'reg_number': '4B023701481B',
                                                                            'expiry': 1632960000,
                                                                            'engine': 'stock',
                                                                            'market': 'bonds',
                                                                            'board': 'TQCB',
                                                                            'type': PredefinedAsset.Bond}
    assert MOEX().asset_info(symbol='SiZ1', isin='', special=True) == {'symbol': 'SiZ1',
                                                                               'name': 'Фьючерсный контракт Si-12.21',
                                                                               'expiry': 1639612800,
                                                                               'engine': 'futures',
                                                                               'market': 'forts',
                                                                               'board': 'RFUD',
                                                                               'type': PredefinedAsset.Derivative}
    assert MOEX().asset_info(symbol='', reg_number='0252-74113866') == {'symbol': 'ПИФСбер-КН',
                                                                      'isin': 'RU000A0ERGA7',
                                                                      'name': 'ПИФСбербанк Комм.недвижимость',
                                                                      'reg_number': '0252-74113866',
                                                                      'type': PredefinedAsset.ETF}
    assert MOEX().asset_info(isin='RU000A1038V6') == {'symbol': 'SU26238RMFS4',
                                                              'isin': 'RU000A1038V6',
                                                              'name': 'ОФЗ-ПД 26238 15/05/2041',
                                                              'principal': 1000.0,
                                                              'reg_number': '26238RMFS',
                                                              'expiry': 2252188800,
                                                              'type': PredefinedAsset.Bond}

    assert MOEX().asset_info(**{'isin': 'RU0009062285',
                                        'reg_number': '1-01-00010-A',
                                        'symbol': 'Аэрофлот'}) == {'symbol': 'RU0009062285',
                                                                   'name': 'ОАО "Аэрофлот-росс.авл " (2 в)',
                                                                   'reg_number': '1-02-00010-A',
                                                                   'principal': 1.0,
                                                                   'type': PredefinedAsset.Stock}
    assert MOEX().asset_info(symbol='GLDRUB_TOM') == {'symbol': 'GLDRUB_TOM',
                                                              'name': 'GLD/RUB_TOM - GLD/РУБ',
                                                              'principal': 1.0,
                                                              'type': PredefinedAsset.Commodity}

def test_CBR_downloader(prepare_db):
    create_stocks([('TRY', '')], currency_id=1)   # id = 4

    downloader = QuoteDownloader()

    rates_usd = pd.DataFrame({'Close': [Decimal('77.5104'), Decimal('77.2535'), Decimal('75.6826')],
                          'Date': [d2dt(210413), d2dt(210414), d2dt(210415)]})
    rates_usd = rates_usd.set_index('Date')
    rates_downloaded = downloader.CBR_DataReader(JalAsset(2), 1618272000, 1618358400)
    assert_frame_equal(rates_usd, rates_downloaded)

    rates_try = pd.DataFrame({'Close': [Decimal('9.45087'), Decimal('9.49270'), Decimal('9.37234')],
                              'Date': [d2dt(210413), d2dt(210414), d2dt(210415)]})
    rates_try = rates_try.set_index('Date')
    rates_downloaded = downloader.CBR_DataReader(JalAsset(4), 1618272000, 1618358400)
    assert_frame_equal(rates_try, rates_downloaded)

def test_ECB_downloader(prepare_db):
    rates_usd = pd.DataFrame({'Close': [Decimal('0.8406186954'), Decimal('0.8358408559')],
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
    quotes_downloaded = downloader.MOEX_DataReader(JalSymbol(symbol_id_for(4, 1)), 1, d2t(210413), d2t(210414))
    assert_frame_equal(stock_quotes, quotes_downloaded)
    sber = JalAsset(4)
    assert sber.type() == PredefinedAsset.Stock
    assert sber.symbol_id(SymbolId.ISIN) == 'RU0009029540'
    assert sber.symbol(1) == 'SBER'
    assert sber.name() == ''
    assert sber.symbol_id(SymbolId.REG_CODE)== '10301481B'

    quotes_downloaded = downloader.MOEX_DataReader(JalSymbol(symbol_id_for(6, 1)), 1, d2t(210722), d2t(210723))
    assert_frame_equal(bond_quotes, quotes_downloaded)
    bond = JalAsset(6)
    assert bond.type() == PredefinedAsset.Bond
    assert bond.symbol_id(SymbolId.ISIN) == 'RU000A1038V6'
    assert bond.symbol(1) == 'SU26238RMFS4'
    assert bond.name() == ''
    assert bond.symbol_id(SymbolId.REG_CODE) == '26238RMFS'
    assert bond.expiry() == d2t(410515)
    assert bond.principal() == Decimal('1000')

    quotes_downloaded = downloader.MOEX_DataReader(JalSymbol(symbol_id_for(7, 1)), 1, d2t(210722), d2t(210723))
    assert_frame_equal(corp_quotes, quotes_downloaded)
    bond2 = JalAsset(7)
    assert bond2.type() == PredefinedAsset.Bond
    assert bond2.symbol_id(SymbolId.ISIN) == 'RU000A1014H6'
    assert bond2.symbol(1) == 'МКБ 1P2'
    assert bond2.name() == ''
    assert bond2.symbol_id(SymbolId.REG_CODE) == '4B020901978B001P'
    assert bond2.expiry() == d2t(211130)
    assert bond2.principal() == Decimal('1000')
    # Test of quotes download for PNK Rental Fund
    quotes_downloaded = downloader.MOEX_DataReader(JalSymbol(symbol_id_for(9, 1)), 1, d2t(211213), d2t(211214), update_symbol=False)
    assert_frame_equal(etf_quotes, quotes_downloaded)
    # Test of non-existing asset download
    quotes_downloaded = downloader.MOEX_DataReader(JalSymbol(symbol_id_for(10, 1)), 1, d2t(211213), d2t(211214), update_symbol=False)
    assert quotes_downloaded is None
    # Bond with high risk
    quotes_downloaded = downloader.MOEX_DataReader(JalSymbol(symbol_id_for(11, 1)), 1, d2t(230913), d2t(230914), update_symbol=False)
    assert_frame_equal(bond_quotes2, quotes_downloaded)
    # Metal
    quotes_downloaded = downloader.MOEX_DataReader(JalSymbol(symbol_id_for(12, 1)), 1, d2t(240206), d2t(240207), update_symbol=False)
    assert_frame_equal(metal_quotes, quotes_downloaded)


def test_MOEX_downloader_USD(prepare_db_moex):
    create_assets([('ГазКЗ-30Д', 'Газпром капитал ООО ЗО30-1-Д', 'RU000A105SG2', 2, PredefinedAsset.Bond, 0)])  # ID = 9

    downloader = QuoteDownloader()
    bond_usd_quotes = pd.DataFrame({'Close': [Decimal('846.509'), Decimal('844.998')],
                                    'Date': [d2dt(240213), d2dt(240214)]})
    bond_usd_quotes = bond_usd_quotes.set_index('Date')
    bond_quotes = downloader.MOEX_DataReader(JalSymbol(symbol_id_for(9, 2)), 2, d2t(240213), d2t(240214))
    assert_frame_equal(bond_quotes, bond_usd_quotes)

def test_NYSE_downloader(prepare_db):
    create_stocks([('AAPL', '')], currency_id=2)   # id = 4
    quotes = pd.DataFrame({'Close': [Decimal('134.42999267578125'), Decimal('132.029998779296875')],
                           'Date': [dt2dt(2104131330), dt2dt(2104141330)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Yahoo_Downloader(JalSymbol(symbol_id_for(4, 2)), 2, d2t(210413), d2t(210415))
    assert_frame_equal(quotes, quotes_downloaded)


def test_LSE_downloader(prepare_db):
    create_stocks([('PSON', '')], currency_id=3)   # id = 4
    quotes = pd.DataFrame({'Close': [Decimal('792.5999755859375'), Decimal('800.79998779296875')],
                           'Date': [dt2dt(2104130700), dt2dt(2104140700)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.YahooLSE_Downloader(JalSymbol(symbol_id_for(4, 3)), 3, d2t(210413), d2t(210415))
    assert_frame_equal(quotes, quotes_downloaded)


def test_Euronext_downloader(prepare_db):
    create_assets([('NOK', 'Nokia', 'FI0009000681', 3, PredefinedAsset.Stock, 0)])   # ID = 4
    quotes = pd.DataFrame({'Close': [Decimal('4.483'), Decimal('4.481'), Decimal('4.5115')],
                           'Date': [d2dt(230412), d2dt(230413), d2dt(230414)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Euronext_DataReader(JalSymbol(symbol_id_for(4, 3)), 3, d2t(230412), d2t(230414))
    assert_frame_equal(quotes, quotes_downloaded)

def test_EuronextMilan_DataReader(prepare_db):
    create_assets([('MINT', 'Pimco Us Dollar Short Maturity Ucits Etf', 'IE00B67B7N93', 3, PredefinedAsset.ETF, 0)])   # ID = 4
    quotes = pd.DataFrame({'Close': [Decimal('95.20'), Decimal('95.02'), Decimal('94.80')],
                           'Date': [d2dt(241203), d2dt(241204), d2dt(241205)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.EuronextMilan_DataReader(JalSymbol(symbol_id_for(4, 3)), 3, d2t(241203), d2t(241205))
    assert_frame_equal(quotes, quotes_downloaded)


def test_TMX_downloader(prepare_db):
    create_stocks([('RY', '')], currency_id=3)   # id = 4
    quotes = pd.DataFrame({'Close': [Decimal('117.18'), Decimal('117.34'), Decimal('118.02')],
                           'Date': [d2dt(210413), d2dt(210414), d2dt(210415)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.TMX_Downloader(JalSymbol(symbol_id_for(4, 3)), 3, 1618272000, 1618444800)
    assert_frame_equal(quotes, quotes_downloaded)


def test_Frankfurt_downloader(prepare_db):
    create_stocks([('VOW3', '')], currency_id=3)   # id = 4
    quotes = pd.DataFrame({'Close': [Decimal('233.399993896484375'), Decimal('234.25')],
                           'Date': [dt2dt(2104130600), dt2dt(2104140600)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.YahooFRA_Downloader(JalSymbol(symbol_id_for(4, 3)), 3, d2t(210413), d2t(210415))
    assert_frame_equal(quotes, quotes_downloaded)


def test_Coinbase_downloader(prepare_db):
    create_assets([('ALGO', 'Algorand', '', 3, PredefinedAsset.Crypto, 0)])  # ID = 4
    quotes = pd.DataFrame({'Close': [Decimal('0.20171559017841111516'), Decimal('0.19595558582536402655'), Decimal('0.20032663919036912874')],
                           'Date': [d2dt(230412), d2dt(230413), d2dt(230414)]})
    quotes = quotes.set_index('Date')

    downloader = QuoteDownloader()
    quotes_downloaded = downloader.Coinbase_Downloader(JalSymbol(symbol_id_for(4, 3)), 3, d2t(230412), d2t(230414))
    assert_frame_equal(quotes, quotes_downloaded)


def test_Stooq_downloader(prepare_db):
    create_stocks([('CDR', '')], currency_id=3)  # ID = 4
    downloader = QuoteDownloader()
    expected = pd.DataFrame({
        'Date': [d2dt(200102)],
        'Close': [Decimal('271.81')]
    }).set_index('Date')
    result = downloader.Stooq_DataReader(JalSymbol(symbol_id_for(4, 3)), 3, d2t(200102), d2t(200102))
    assert_frame_equal(expected, result)


# ----------------------------------------------------------------------------------------------------------------------
# Creates a crypto asset with one listing on given blockchain location and returns (asset_id, symbol_id).
# 'address' is the contract address of the token on that chain - an empty one means the native coin of the chain.
def create_crypto(name: str, symbol: str, currency_id: int, location_id: int, address: str = '',
                  id_type: int = 0) -> tuple:
    creator = JalAssetCreator(PredefinedAsset.Crypto, name)
    symbol_id = creator.add_symbol(symbol, currency_id, location_id=location_id)
    if address:
        creator.add_identifier(symbol_id, id_type, address)
    asset = creator.commit()
    return asset.id(), symbol_id


def test_llama_coin_key(prepare_db):
    # A token is identified by its contract address on the chain it is listed at
    _, usdc_arb = create_crypto('USD Coin', 'USDC', 2, AssetLocation.ARB_BLOCKCHAIN,
                                '0xaf88d065e77c8cC2239327C5EDb3A432268e5831', SymbolId.ARB_ADDRESS)
    assert llama_coin_key(JalSymbol(usdc_arb)) == 'arbitrum:0xaf88d065e77c8cC2239327C5EDb3A432268e5831'
    _, usdc_eth = create_crypto('USD Coin ETH', 'USDC', 2, AssetLocation.ETH_BLOCKCHAIN,
                                '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', SymbolId.ETH_ADDRESS)
    assert llama_coin_key(JalSymbol(usdc_eth)) == 'ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
    _, sol_token = create_crypto('Jupiter', 'JUP', 2, AssetLocation.SOL_BLOCKCHAIN,
                                 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN', SymbolId.SOL_ADDRESS)
    assert llama_coin_key(JalSymbol(sol_token)) == 'solana:JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN'
    _, usdt_trx = create_crypto('Tether', 'USDT', 2, AssetLocation.TRX_BLOCKCHAIN,
                                'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', SymbolId.TRX_ADDRESS)
    assert llama_coin_key(JalSymbol(usdt_trx)) == 'tron:TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'

    # A listing without a contract address is the native coin of its chain
    _, btc = create_crypto('Bitcoin', 'BTC', 2, AssetLocation.BTC_BLOCKCHAIN)
    assert llama_coin_key(JalSymbol(btc)) == 'coingecko:bitcoin'
    _, eth = create_crypto('Ether', 'ETH', 2, AssetLocation.ETH_BLOCKCHAIN)
    assert llama_coin_key(JalSymbol(eth)) == 'coingecko:ethereum'
    _, sol = create_crypto('Solana', 'SOL', 2, AssetLocation.SOL_BLOCKCHAIN)
    assert llama_coin_key(JalSymbol(sol)) == 'coingecko:solana'
    _, trx = create_crypto('Tron', 'TRX', 2, AssetLocation.TRX_BLOCKCHAIN)
    assert llama_coin_key(JalSymbol(trx)) == 'coingecko:tron'
    # Native coin of Arbitrum is bridged ETH and not the ARB token (the latter has a contract address)
    _, eth_arb = create_crypto('Ether ARB', 'ETH', 2, AssetLocation.ARB_BLOCKCHAIN)
    assert llama_coin_key(JalSymbol(eth_arb)) == 'coingecko:ethereum'

    # A listing that isn't on a blockchain has no key at all
    _, stock = create_crypto('Not a coin', 'NPC', 2, AssetLocation.NYSE_EXCHANGE)
    assert llama_coin_key(JalSymbol(stock)) == ''


def test_llama_chart_parsing(data_path):
    coin = 'arbitrum:0xaf88d065e77c8cC2239327C5EDb3A432268e5831'
    with open(data_path + 'defillama_chart.json', 'r') as sample:
        content = sample.read()
    # Prices of the sample are given a few seconds after midnight and are expected at the midnight of the same day
    expected = pd.DataFrame({'Close': [Decimal('0.999386'), Decimal('1'), Decimal('0.999924'), Decimal('0.999194')],
                             'Date': [d2dt(240701), d2dt(240702), d2dt(240703), d2dt(240704)]}).set_index('Date')
    assert_frame_equal(expected, parse_llama_chart(content, coin))

    # An answer for another coin, a broken answer or an empty one give no quotes but don't raise
    assert parse_llama_chart(content, 'coingecko:bitcoin').empty
    assert parse_llama_chart('{"coins": {}}', coin).empty
    assert parse_llama_chart('not a json', coin).empty
    assert parse_llama_chart('', coin).empty


def test_llama_chart_parsing_details():
    coin = 'coingecko:bitcoin'
    # A price given before midnight belongs to the day that starts right after it, not to the day it falls into
    content = '{"coins": {"' + coin + '": {"confidence": 0.99, "prices": [' \
              '{"timestamp": 1719791998, "price": 100}, {"timestamp": 1719878421, "price": 200}]}}}'
    expected = pd.DataFrame({'Close': [Decimal('100'), Decimal('200')],
                             'Date': [d2dt(240701), d2dt(240702)]}).set_index('Date')
    assert_frame_equal(expected, parse_llama_chart(content, coin))

    # Low confidence prices are dropped - both when confidence is set for the coin and for a single point
    content = '{"coins": {"' + coin + '": {"confidence": 0.5, "prices": [{"timestamp": 1719792081, "price": 100}]}}}'
    assert parse_llama_chart(content, coin).empty
    content = '{"coins": {"' + coin + '": {"confidence": 0.99, "prices": [' \
              '{"timestamp": 1719792081, "price": 100, "confidence": 0.1}, ' \
              '{"timestamp": 1719878421, "price": 200}]}}}'
    expected = pd.DataFrame({'Close': [Decimal('200')], 'Date': [d2dt(240702)]}).set_index('Date')
    assert_frame_equal(expected, parse_llama_chart(content, coin))

    # A malformed point is skipped but the rest of the answer is kept
    content = '{"coins": {"' + coin + '": {"confidence": 0.99, "prices": [' \
              '{"timestamp": 1719792081}, {"timestamp": 1719878421, "price": 200}]}}}'
    expected = pd.DataFrame({'Close': [Decimal('200')], 'Date': [d2dt(240702)]}).set_index('Date')
    assert_frame_equal(expected, parse_llama_chart(content, coin))

    # Several prices that fall into the same day are stored once
    content = '{"coins": {"' + coin + '": {"confidence": 0.99, "prices": [' \
              '{"timestamp": 1719792081, "price": 100}, {"timestamp": 1719792999, "price": 300}]}}}'
    expected = pd.DataFrame({'Close': [Decimal('100')], 'Date': [d2dt(240701)]}).set_index('Date')
    assert_frame_equal(expected, parse_llama_chart(content, coin))


def test_llama_downloader(prepare_db):
    _, symbol_id = create_crypto('USD Coin', 'USDC', 2, AssetLocation.ARB_BLOCKCHAIN,
                                 '0xaf88d065e77c8cC2239327C5EDb3A432268e5831', SymbolId.ARB_ADDRESS)
    expected = pd.DataFrame({'Close': [Decimal('0.999386'), Decimal('1'), Decimal('0.999924')],
                             'Date': [d2dt(240701), d2dt(240702), d2dt(240703)]}).set_index('Date')
    downloader = QuoteDownloader()
    assert_frame_equal(expected, downloader.Llama_Downloader(JalSymbol(symbol_id), 2, d2t(240701), d2t(240703)))


def test_quote_series_selection(prepare_db):
    downloader = QuoteDownloader()
    usd, eur = 2, 3

    # All listings of a crypto asset share one USD series: same asset on two chains and in two account
    # currencies has to be downloaded once and stored as USD
    asset_id, arb_symbol = create_crypto('USD Coin', 'USDC', usd, AssetLocation.ARB_BLOCKCHAIN,
                                         '0xaf88d065e77c8cC2239327C5EDb3A432268e5831', SymbolId.ARB_ADDRESS)
    eth_symbol = JalAsset(asset_id).add_symbol('USDC', usd, location_id=AssetLocation.ETH_BLOCKCHAIN)
    JalAsset(asset_id).add_identifier(eth_symbol, SymbolId.ETH_ADDRESS,
                                      '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48')
    series = downloader._quote_series([(JalSymbol(arb_symbol), usd), (JalSymbol(eth_symbol), usd),
                                       (JalSymbol(arb_symbol), eur), (JalSymbol(eth_symbol), eur)])
    assert len(series) == 1
    assert series[0][0].id() == arb_symbol   # the first listing of the series is the one that is downloaded
    assert series[0][1] == usd               # ... and it is stored as a USD series despite the EUR accounts

    # Listings of a non-crypto asset in different currencies are different series and all of them are kept
    stock = JalAssetCreator(PredefinedAsset.Stock, 'Some Company')
    usd_listing = stock.add_symbol('SC', usd, location_id=AssetLocation.NYSE_EXCHANGE)
    eur_listing = stock.add_symbol('SC', eur, location_id=AssetLocation.EURONEXT_EXCHANGE)
    stock.commit()
    series = downloader._quote_series([(JalSymbol(usd_listing), usd), (JalSymbol(eur_listing), eur)])
    assert [(x[0].id(), x[1]) for x in series] == [(usd_listing, usd), (eur_listing, eur)]

    # A repeated listing of a non-crypto asset (several accounts in one currency) is downloaded once
    series = downloader._quote_series([(JalSymbol(usd_listing), usd), (JalSymbol(usd_listing), usd)])
    assert [(x[0].id(), x[1]) for x in series] == [(usd_listing, usd)]


def test_crypto_quotes_are_stored_as_usd(prepare_db, monkeypatch):
    usd, eur = 2, 3
    # One asset listed on two chains, held in accounts of two different currencies
    asset_id, arb_symbol = create_crypto('USD Coin', 'USDC', usd, AssetLocation.ARB_BLOCKCHAIN,
                                         '0xaf88d065e77c8cC2239327C5EDb3A432268e5831', SymbolId.ARB_ADDRESS)
    eth_symbol = JalAsset(asset_id).add_symbol('USDC', eur, location_id=AssetLocation.ETH_BLOCKCHAIN)
    JalAsset(asset_id).add_identifier(eth_symbol, SymbolId.ETH_ADDRESS,
                                      '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48')
    monkeypatch.setattr(JalSymbol, 'get_active_symbols',
                        classmethod(lambda cls, begin, end: [{"symbol": JalSymbol(arb_symbol), "currency": usd},
                                                             {"symbol": JalSymbol(eth_symbol), "currency": eur}]))
    downloaded = []
    quotes = pd.DataFrame({'Close': [Decimal('0.99')], 'Date': [d2dt(240701)]}).set_index('Date')
    def fake_download(symbol, currency_id, start_timestamp, end_timestamp):
        downloaded.append((symbol.id(), currency_id))
        return quotes
    downloader = QuoteDownloader()
    monkeypatch.setattr(downloader, 'Llama_Downloader', fake_download)
    downloader.download_asset_prices(d2t(240701), d2t(240701),
                                     [AssetLocation.ARB_BLOCKCHAIN, AssetLocation.ETH_BLOCKCHAIN])

    # Both listings share one series, so a single download is made and it is requested in USD
    assert downloaded == [(arb_symbol, usd)]
    # ... and the quote is stored as USD even though one of the accounts is in EUR
    assert JalAsset(asset_id).quotes(d2t(240701), d2t(240701), usd) == [(d2t(240701), Decimal('0.99'))]
    assert JalAsset(asset_id).quotes(d2t(240701), d2t(240701), eur) == []
