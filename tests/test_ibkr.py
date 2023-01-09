import json
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from data_import.broker_statements.ibkr import StatementIBKR
from tests.helpers import d2t
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset, AssetData
from jal.constants import PredefinedAsset, BookAccount


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_ibkr(tmp_path, project_root, data_path, prepare_db_taxes):
    #  Import first year
    ibkr_statement0 = StatementIBKR()
    ibkr_statement0.load(data_path + 'ibkr_year0.xml')
    ibkr_statement0.validate_format()
    ibkr_statement0.match_db_ids()
    ibkr_statement0.import_into_db()

    # validate assets
    test_assets = [
        {'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'isin': '', 'country_id': 0,
         'symbols': [{'symbol': 'RUB', 'description': 'Российский Рубль', 'active': 1, 'currency_id': 1, 'quote_source': -1}]},
        {'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'isin': '', 'country_id': 0,
         'symbols': [{'symbol': 'USD', 'description': 'Доллар США (Банк России)', 'active': 1, 'currency_id': 1, 'quote_source': 0}]},
        {'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'isin': '', 'country_id': 0,
         'symbols': [{'symbol': 'EUR', 'description': 'Евро (Банк России)', 'active': 1, 'currency_id': 1, 'quote_source': 0}]},
        {'type_id': PredefinedAsset.Stock, 'full_name': 'PACIFIC ETHANOL INC', 'isin': 'US69423U3059', 'country_id': 0,
         'symbols': [{'symbol': 'PEIX', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': [{'datatype': AssetData.RegistrationCode, 'value': '69423U305'}]},
        {'type_id': PredefinedAsset.Derivative, 'full_name': 'FANG 21JAN22 40.0 C', 'isin': '', 'country_id': 0,
         'symbols': [{'symbol': 'FANG  220121C00040000', 'description': 'CBOE', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': [{'datatype': AssetData.ExpiryDate, 'value': str(d2t(220121))}]},
        {'type_id': PredefinedAsset.Stock, 'full_name': 'EXXON MOBIL CORP', 'isin': 'US30231G1022', 'country_id': 2,
         'symbols': [{'symbol': 'XOM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': [{'datatype': AssetData.RegistrationCode, 'value': '30231G102'}]},
        {'type_id': PredefinedAsset.Derivative, 'full_name': 'XOM 21JAN22 42.5 C', 'isin': '', 'country_id': 0,
         'symbols': [{'symbol': 'XOM   220121C00042500', 'description': 'CBOE', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': [{'datatype': AssetData.ExpiryDate, 'value': str(d2t(220121))}]}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets

    # validate trades
    test_trades = [
        [1, 3, 1604926434, 1604966400, '3210359211', 1, 5, '-300.0', '5.5', '0.953865', ''],
        [2, 3, 1606471692, 1606780800, '3256333343', 1, 4, '70.0', '6.898', '0.36425725', ''],
        [3, 3, 1606821387, 1606953600, '3264444280', 1, 4, '70.0', '6.08', '0.32925725', ''],
        [4, 3, 1607095765, 1607299200, '3276656996', 1, 7, '-100.0', '5.2', '0.667292', '']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade

    # validate dividend & tax
    test_dividends = [
        [1, 2, 1592770800, '', '', 1, 1, 6, '16.76', '1.68', 'XOM (US30231G1022) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
    ]
    dividends = JalAccount(1).dump_dividends()
    assert len(dividends) == len(test_dividends)
    for i, dividend in enumerate(test_dividends):
        assert dividends[i] == dividend

    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Import second year
    ibkr_statement1 = StatementIBKR()
    ibkr_statement1.load(data_path + 'ibkr_year1.xml')
    ibkr_statement1.validate_format()
    ibkr_statement1.match_db_ids()
    ibkr_statement1.import_into_db()

    ledger.rebuild(from_timestamp=0)

    # validate assets
    test_assets = [
        {'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'isin': '', 'country_id': 0,
         'symbols': [
             {'symbol': 'RUB', 'description': 'Российский Рубль', 'active': 1, 'currency_id': 1, 'quote_source': -1}]},
        {'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'isin': '', 'country_id': 0,
         'symbols': [{'symbol': 'USD', 'description': 'Доллар США (Банк России)', 'active': 1, 'currency_id': 1,
                      'quote_source': 0}]},
        {'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'isin': '', 'country_id': 0,
         'symbols': [
             {'symbol': 'EUR', 'description': 'Евро (Банк России)', 'active': 1, 'currency_id': 1, 'quote_source': 0}]},
        {'type_id': PredefinedAsset.Stock, 'full_name': 'PACIFIC ETHANOL INC', 'isin': 'US69423U3059', 'country_id': 0,
         'symbols': [{'symbol': 'PEIX', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': [{'datatype': AssetData.RegistrationCode, 'value': '69423U305'}]},
        {'type_id': PredefinedAsset.Derivative, 'full_name': 'FANG 21JAN22 40.0 C', 'isin': '', 'country_id': 0,
         'symbols': [{'symbol': 'FANG  220121C00040000', 'description': 'CBOE', 'active': 1, 'currency_id': 2,
                      'quote_source': -1}],
         'data': [{'datatype': AssetData.ExpiryDate, 'value': str(d2t(220121))}]},
        {'type_id': PredefinedAsset.Stock, 'full_name': 'EXXON MOBIL CORP', 'isin': 'US30231G1022', 'country_id': 2,
         'symbols': [{'symbol': 'XOM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': [{'datatype': AssetData.RegistrationCode, 'value': '30231G102'}]},
        {'type_id': PredefinedAsset.Derivative, 'full_name': 'XOM 21JAN22 42.5 C', 'isin': '', 'country_id': 0,
         'symbols': [{'symbol': 'XOM   220121C00042500', 'description': 'CBOE', 'active': 1, 'currency_id': 2,
                      'quote_source': -1}],
         'data': [{'datatype': AssetData.ExpiryDate, 'value': str(d2t(220121))}]},
        {'type_id': PredefinedAsset.Stock, 'full_name': 'ALTO INGREDIENTS INC', 'isin': 'US0215131063', 'country_id': 0,
         'symbols': [{'symbol': 'ALTO', 'description': 'NASDAQ', 'active': 0, 'currency_id': 2, 'quote_source': 2},
                     {'symbol': 'PEIX', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': [{'datatype': 1, 'value': '021513106'}]}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets

    # validate trades
    test_trades = [
        [1, 3, 1604926434, 1604966400, '3210359211', 1, 5, '-300.0', '5.5', '0.953865', ''],
        [2, 3, 1606471692, 1606780800, '3256333343', 1, 4, '70.0', '6.898', '0.36425725', ''],
        [3, 3, 1606821387, 1606953600, '3264444280', 1, 4, '70.0', '6.08', '0.32925725', ''],
        [4, 3, 1607095765, 1607299200, '3276656996', 1, 7, '-100.0', '5.2', '0.667292', ''],
        [5, 3, 1610625615, 1611014400, '3381623127', 1, 8, '-70.0', '7.42', '0.23706599', ''],
        [6, 3, 1612871230, 1613001600, '3480222427', 1, 8, '-70.0', '7.71', '0.23751462', ''],
        [7, 3, 1620750000, 1620864000, '3764387743', 1, 6, '-100.0', '42.5', '0.033575', 'Option assignment/exercise'],
        [8, 3, 1620750000, 1620777600, '3764387737', 1, 7, '100.0', '0.0', '0.0', 'Option assignment'],
        [9, 3, 1623247000, 1623283200, '3836250920', 1, 5, '300.0', '50.8', '-0.1266', '']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade

    # validate dividend & tax
    test_dividends = [
        [1, 2, 1592770800, '', '', 1, 1, 6, '16.76', '0.21', 'XOM (US30231G1022) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)']
    ]
    dividends = JalAccount(1).dump_dividends()
    assert len(dividends) == len(test_dividends)
    for i, dividend in enumerate(test_dividends):
        assert dividends[i] == dividend

    # validate corp actions
    test_asset_actions = [
        [1, 5, 1610569500, '14909999818', 1, 3, 4, '140.0', 'PEIX(US69423U3059) CUSIP/ISIN CHANGE TO (US0215131063) (PEIX, ALTO INGREDIENTS INC, US0215131063)',
         [1, 1, 8, '140.0', '1.0']]
    ]
    actions = JalAccount(1).dump_corporate_actions()
    assert len(actions) == len(test_asset_actions)
    for i, action in enumerate(test_asset_actions):
        assert actions[i] == action

    # Check that there are no remainders
    total_amount = LedgerAmounts("amount_acc")
    total_value = LedgerAmounts("value_acc")
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert total_value[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert total_amount[(BookAccount.Assets, 1, 7)] == Decimal('0')
    assert total_value[(BookAccount.Assets, 1, 7)] == Decimal('0')


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_warrants(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_warrants.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_warrants.xml')
    assert IBKR._data == statement


# ----------------------------------------------------------------------------------------------------------------------
# Warnings are expected for this test:
# Payment was reversed by approximate description: 30/06/2022 20:20:00, 'BEP(BMG162581083) CASH DIVIDEND USD 0.0161 PER SHARE (Ordinary Dividend)': 12.15
# Payment was reversed by approximate description: 30/06/2022 20:20:00, 'BEP(BMG162581083) CASH DIVIDEND USD 0.0161 PER SHARE (Bonus Dividend)': 0.65
# Payment was reversed by approximate description: 30/06/2022 20:20:00, 'BEP(BMG162581083) CASH DIVIDEND USD 0.0161 PER SHARE (Ordinary Dividend)': 12.15
# Payment was reversed by approximate description: 30/06/2022 20:20:00, 'BEP(BMG162581083) CASH DIVIDEND USD 0.30371 PER SHARE (Ordinary Dividend)': 0.64
def test_ibkr_dividends(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_dividends.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_dividends.xml')
    assert IBKR._data == statement
