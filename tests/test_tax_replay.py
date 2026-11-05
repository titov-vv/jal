from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_quotes, create_trades, create_swaps, create_conversions, \
    create_corporate_actions, symbol_id_for
from jal.constants import PredefinedAsset, SwapTreatment, AssetData
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, AssetIncome, CorporateAction
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal

RUB, USD, EUR = 1, 2, 3
DEAL_FIELDS = ('symbol', 'qty', 'o_number', 'o_date', 'o_amount', 'c_number', 'c_date', 'c_amount', 'profit')


def deal_rows(section: list) -> list:
    return [x for x in section if x['report_template'] == "trade"]


def pick(row: dict, fields) -> dict:
    return {k: row[k] for k in fields}


# ----------------------------------------------------------------------------------------------------------------------
# RU, 2025, USD account 1: UNI 4, AVAX 5, ETH 6, WETH 7, SOL 8, LINK 9; no fees
#   UNI 100 @ 10 -> conversion swap into 40 AVAX (UNI quoted 12) -> AVAX sold @ 35
#   ETH 1 @ 3000 -> wrapped into 1 WETH (ETH quoted 3200) -> WETH sold @ 3500
#   SOL 2 staking reward (quoted 200) -> sale swap into 25 LINK (SOL quoted 220) -> LINK sold @ 20
RU_RATES = {250110: 100, 250115: 101, 250201: 102, 250301: 103, 250310: 104, 250320: 105, 250401: 106, 250410: 107,
            250501: 108}


def create_ru_scenario():
    create_assets([("UNI", "Uniswap", "", USD, PredefinedAsset.Crypto, 0),
                   ("AVAX", "Avalanche", "", USD, PredefinedAsset.Crypto, 0),
                   ("ETH", "Ether", "", USD, PredefinedAsset.Crypto, 0),
                   ("WETH", "Wrapped Ether", "", USD, PredefinedAsset.Crypto, 0),
                   ("SOL", "Solana", "", USD, PredefinedAsset.Crypto, 0),
                   ("LINK", "Chainlink", "", USD, PredefinedAsset.Crypto, 0)])
    create_quotes(USD, RUB, [(d2t(x), y) for x, y in RU_RATES.items()])
    create_quotes(4, USD, [(d2t(250301), 12)])
    create_quotes(5, USD, [(d2t(250301), 30)])
    create_quotes(6, USD, [(d2t(250310), 3200)])
    create_quotes(7, USD, [(d2t(250310), 3200)])
    create_quotes(8, USD, [(d2t(250201), 200), (d2t(250320), 220)])
    create_quotes(9, USD, [(d2t(250320), 17.6)])
    create_trades(1, [(d2t(250110), d2t(250110), 6, 1, 3000, 0, "buy-ETH"),
                      (d2t(250115), d2t(250115), 4, 100, 10, 0, "buy-UNI")])
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': d2t(250201), 'type': AssetIncome.StakingReward, 'account_id': 1, 'symbol_id': symbol_id_for(8),
        'amount': '2', 'tax': '0', 'number': 'reward-SOL', 'note': 'SOL staking reward'})
    create_swaps(1, [(d2t(250301), 4, 100, 5, 40)], treatment=SwapTreatment.Conversion)
    create_conversions(1, [(d2t(250310), 6, 1, 7, 1)])
    create_swaps(1, [(d2t(250320), 8, 2, 9, 25)], treatment=SwapTreatment.Sale)
    create_trades(1, [(d2t(250401), d2t(250401), 5, -40, 35, 0, "sell-AVAX"),
                      (d2t(250410), d2t(250410), 7, -1, 3500, 0, "sell-WETH"),
                      (d2t(250501), d2t(250501), 9, -25, 20, 0, "sell-LINK")])
    Ledger().rebuild(from_timestamp=0)


# Today: a lot that a conversion swap or a wrapping disposed of closes at its cost and the lot carried on keeps cost
# and date, both marked pending; the reward lot is re-priced to its quote by the report
def test_ru_crypto_today(prepare_db_taxes):
    create_ru_scenario()

    report = TaxesRussia().prepare_tax_report(2025, 1)
    assert [pick(x, DEAL_FIELDS + ('o_amount_rub', 'c_amount_rub', 'profit_rub')) | {'pending': 'pending_replay' in x}
            for x in deal_rows(report["Криптовалюты"])] == [
        {'symbol': "UNI", 'qty': Decimal('100'), 'o_number': "buy-UNI", 'o_date': d2t(250115),
         'o_amount': Decimal('1000.00'), 'c_number': '', 'c_date': d2t(250301), 'c_amount': Decimal('1000.00'),
         'profit': Decimal('0.00'), 'o_amount_rub': Decimal('101000.00'), 'c_amount_rub': Decimal('101000.00'),
         'profit_rub': Decimal('0.00'), 'pending': True},
        {'symbol': "ETH", 'qty': Decimal('1'), 'o_number': "buy-ETH", 'o_date': d2t(250110),
         'o_amount': Decimal('3000.00'), 'c_number': '', 'c_date': d2t(250310), 'c_amount': Decimal('3000.00'),
         'profit': Decimal('0.00'), 'o_amount_rub': Decimal('300000.00'), 'c_amount_rub': Decimal('300000.00'),
         'profit_rub': Decimal('0.00'), 'pending': True},
        {'symbol': "SOL", 'qty': Decimal('2'), 'o_number': "reward-SOL", 'o_date': d2t(250201),   # 2 x 200
         'o_amount': Decimal('400.00'), 'c_number': '', 'c_date': d2t(250320), 'c_amount': Decimal('440.00'),
         'profit': Decimal('40.00'), 'o_amount_rub': Decimal('40800.00'), 'c_amount_rub': Decimal('46200.00'),
         'profit_rub': Decimal('5400.00'), 'pending': False},
        {'symbol': "AVAX", 'qty': Decimal('40'), 'o_number': "buy-UNI", 'o_date': d2t(250115),
         'o_amount': Decimal('1000.00'), 'c_number': "sell-AVAX", 'c_date': d2t(250401), 'c_amount': Decimal('1400.00'),
         'profit': Decimal('400.00'), 'o_amount_rub': Decimal('101000.00'), 'c_amount_rub': Decimal('148400.00'),
         'profit_rub': Decimal('47400.00'), 'pending': True},
        {'symbol': "WETH", 'qty': Decimal('1'), 'o_number': "buy-ETH", 'o_date': d2t(250110),
         'o_amount': Decimal('3000.00'), 'c_number': "sell-WETH", 'c_date': d2t(250410), 'c_amount': Decimal('3500.00'),
         'profit': Decimal('500.00'), 'o_amount_rub': Decimal('300000.00'), 'c_amount_rub': Decimal('374500.00'),
         'profit_rub': Decimal('74500.00'), 'pending': True},
        {'symbol': "LINK", 'qty': Decimal('25'), 'o_number': '', 'o_date': d2t(250320),   # opened at the swap's 440
         'o_amount': Decimal('440.00'), 'c_number': "sell-LINK", 'c_date': d2t(250501), 'c_amount': Decimal('500.00'),
         'profit': Decimal('60.00'), 'o_amount_rub': Decimal('46200.00'), 'c_amount_rub': Decimal('54000.00'),
         'profit_rub': Decimal('7800.00'), 'pending': False}]
    income, = [x for x in report["Криптодоход"] if x['report_template'] == "income"]
    assert (income['value'], income['value_rub']) == (Decimal('400.00'), Decimal('40800.00'))
    pending, = [x for x in report["Сводка"] if x.get('label') == TaxesRussia.texts['pending_total']]
    assert pending['count'] == 4


# ----------------------------------------------------------------------------------------------------------------------
# PT, 2024-2025, USD account 1: ETH 4, UNI 5, SOL 6, AVAX 7, USDC 8, aUSDC 9 (lending receipt), OLD 10 (NL), NEW 11 (RU)
#   ETH 2 @ 1500 (2023) -> sale swap into 400 UNI (ETH quoted 3500) -> 200 UNI sold @ 20 275 days on, 200 @ 25 396 days on
#   SOL 10 @ 20 (2023) -> conversion swap into 20 AVAX -> AVAX sold @ 30 275 days on
#   USDC 1000 @ 1 (2023) -> supplied for aUSDC -> withdrawn -> sold @ 1.001
#   OLD 100 @ 30 (2023) -> merger into OLD (0.2) + 50 NEW (0.8), both keep the date -> NEW sold @ 70
PT_RATES = {230110: 0.93, 230301: 0.94, 230601: 0.92, 240301: 0.92, 240601: 0.93, 240828: 0.90, 240829: 0.90,
            241101: 0.92, 241201: 0.95, 250101: 0.96, 250201: 0.97, 250401: 0.91}


def create_pt_scenario():
    create_assets([("ETH", "Ether", "", USD, PredefinedAsset.Crypto, 0),
                   ("UNI", "Uniswap", "", USD, PredefinedAsset.Crypto, 0),
                   ("SOL", "Solana", "", USD, PredefinedAsset.Crypto, 0),
                   ("AVAX", "Avalanche", "", USD, PredefinedAsset.Crypto, 0),
                   ("USDC", "USD Coin", "", USD, PredefinedAsset.Crypto, 0),
                   ("aUSDC", "Aave USDC", "", USD, PredefinedAsset.Crypto, 0),
                   ("OLD", "Old Holding N.V.", "NL0000000101", USD, PredefinedAsset.Stock, 'nl'),
                   ("NEW", "New Holding PJSC", "RU0000000102", USD, PredefinedAsset.Stock, 'ru')])
    for datatype, value in ((AssetData.Rebasing, '1'), (AssetData.Protocol, 'Aave v3')):
        JalDB._exec("INSERT INTO asset_data(asset_id, datatype, value) VALUES(9, :dt, :v)",
                    [(":dt", datatype), (":v", value)], commit=True)
    create_quotes(USD, EUR, [(d2t(x), y) for x, y in PT_RATES.items()])
    create_quotes(4, USD, [(d2t(240301), 3500)])
    create_quotes(5, USD, [(d2t(240301), 17.5)])
    create_quotes(6, USD, [(d2t(240301), 25)])
    create_quotes(10, USD, [(d2t(240828), 32)])
    create_quotes(11, USD, [(d2t(240830), 50)])
    create_trades(1, [(d2t(230110), d2t(230110), 4, 2, 1500, 0, "buy-ETH"),
                      (d2t(230110), d2t(230110), 6, 10, 20, 0, "buy-SOL"),
                      (d2t(230301), d2t(230301), 10, 100, 30, 0, "buy-OLD"),
                      (d2t(230601), d2t(230601), 8, 1000, 1, 0, "buy-USDC")])
    create_swaps(1, [(d2t(240301), 4, 2, 5, 400)], treatment=SwapTreatment.Sale)
    create_swaps(1, [(d2t(240301), 6, 10, 7, 20)], treatment=SwapTreatment.Conversion)
    create_conversions(1, [(d2t(240601), 8, 1000, 9, 1000)])
    create_corporate_actions(1, [(d2t(240829), CorporateAction.Merger, 10, 100, "Merger OLD -> OLD + NEW",
                                  [(10, 100, 0.2), (11, 50, 0.8, True)])])
    create_trades(1, [(d2t(241101), d2t(241101), 11, -50, 70, 0, "sell-NEW"),
                      (d2t(241201), d2t(241201), 5, -200, 20, 0, "sell-UNI-1"),
                      (d2t(241201), d2t(241201), 7, -20, 30, 0, "sell-AVAX")])
    create_conversions(1, [(d2t(250101), 9, 1000, 8, 1000)])
    create_trades(1, [(d2t(250201), d2t(250201), 8, -1000, 1.001, 0, "sell-USDC"),
                      (d2t(250401), d2t(250401), 5, -200, 25, 0, "sell-UNI-2")])
    Ledger().rebuild(from_timestamp=0)


PT_FIELDS = DEAL_FIELDS + ('o_amount_eur', 'c_amount_eur', 'profit_eur', 'days')


# Today: the sale swap reset the UNI cost to the swap's value, the conversion swap and the lending legs kept cost and
# date, all of them marked pending; the merger carried the date and 0.8 of the cost into NEW, sold on Shares
def test_pt_2024_today(prepare_db_taxes):
    create_pt_scenario()

    report = TaxesPortugal().prepare_tax_report(2024, 1)
    short = [pick(x, PT_FIELDS) | {'pending': 'pending_replay' in x} for x in deal_rows(report["Crypto < 365 days"])]
    assert short == [
        {'symbol': "UNI", 'qty': Decimal('200'), 'o_number': '', 'o_date': d2t(240301), 'o_amount': Decimal('3500.00'),
         'c_number': "sell-UNI-1", 'c_date': d2t(241201), 'c_amount': Decimal('4000.00'), 'profit': Decimal('500.00'),
         'o_amount_eur': Decimal('3325.00'), 'c_amount_eur': Decimal('3800.00'), 'profit_eur': Decimal('475.00'),
         'days': 275, 'pending': True}]
    long = [pick(x, PT_FIELDS) | {'pending': 'pending_replay' in x} for x in deal_rows(report["Crypto ≥ 365 days"])]
    assert long == [
        {'symbol': "AVAX", 'qty': Decimal('20'), 'o_number': "buy-SOL", 'o_date': d2t(230110),
         'o_amount': Decimal('200.00'), 'c_number': "sell-AVAX", 'c_date': d2t(241201), 'c_amount': Decimal('600.00'),
         'profit': Decimal('400.00'), 'o_amount_eur': Decimal('190.00'), 'c_amount_eur': Decimal('570.00'),
         'profit_eur': Decimal('380.00'), 'days': 691, 'pending': True}]
    shares = [pick(x, DEAL_FIELDS + ('o_amount_eur', 'c_amount_eur', 'profit_eur')) for x in deal_rows(report["Shares"])]
    assert shares == [
        {'symbol': "NEW", 'qty': Decimal('50'), 'o_number': "buy-OLD", 'o_date': d2t(230301),
         'o_amount': Decimal('2400.00'), 'c_number': "sell-NEW", 'c_date': d2t(241101), 'c_amount': Decimal('3500.00'),
         'profit': Decimal('1100.00'), 'o_amount_eur': Decimal('2208.00'), 'c_amount_eur': Decimal('3220.00'),
         'profit_eur': Decimal('1012.00')}]
    pending, = [x for x in report["Summary"] if x.get('label') == TaxesPortugal.texts['pending_total']]
    assert pending['count'] == 2


def test_pt_2025_today(prepare_db_taxes):
    create_pt_scenario()

    report = TaxesPortugal().prepare_tax_report(2025, 1)
    assert deal_rows(report["Crypto < 365 days"]) == []
    long = [pick(x, PT_FIELDS) | {'pending': 'pending_replay' in x} for x in deal_rows(report["Crypto ≥ 365 days"])]
    assert long == [
        {'symbol': "USDC", 'qty': Decimal('1000'), 'o_number': "buy-USDC", 'o_date': d2t(230601),
         'o_amount': Decimal('1000.00'), 'c_number': "sell-USDC", 'c_date': d2t(250201), 'c_amount': Decimal('1001.00'),
         'profit': Decimal('1.00'), 'o_amount_eur': Decimal('970.00'), 'c_amount_eur': Decimal('970.97'),
         'profit_eur': Decimal('0.97'), 'days': 611, 'pending': True},
        {'symbol': "UNI", 'qty': Decimal('200'), 'o_number': '', 'o_date': d2t(240301), 'o_amount': Decimal('3500.00'),
         'c_number': "sell-UNI-2", 'c_date': d2t(250401), 'c_amount': Decimal('5000.00'), 'profit': Decimal('1500.00'),
         'o_amount_eur': Decimal('3185.00'), 'c_amount_eur': Decimal('4550.00'), 'profit_eur': Decimal('1365.00'),
         'days': 396, 'pending': True}]
