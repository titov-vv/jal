import json

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from data_import.broker_statements.ibkr import StatementIBKR
from jal.db.ledger import Ledger
from jal.db.helpers import readSQL
from jal.constants import PredefinedAsset


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
        [1, PredefinedAsset.Money, 'Российский Рубль', '', 0, ''],
        [2, PredefinedAsset.Money, 'Доллар США', '', 0, ''],
        [3, PredefinedAsset.Money, 'Евро', '', 0, ''],
        [4, PredefinedAsset.Stock, 'PACIFIC ETHANOL INC', 'US69423U3059', 0, ''],
        [5, PredefinedAsset.Derivative, 'FANG 21JAN22 40.0 C', '', 0, ''],
        [6, PredefinedAsset.Stock, 'EXXON MOBIL CORP', 'US30231G1022', 0, ''],
        [7, PredefinedAsset.Derivative, 'XOM 21JAN22 42.5 C', '', 0, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM assets") == len(test_assets)
    for i, asset in enumerate(test_assets):
        assert readSQL("SELECT * FROM assets WHERE id=:id", [(":id", i + 1)]) == asset

    # validate assets symbols
    test_symbols = [
        [1, 1, 'RUB', 1, 'Российский Рубль', -1, 1],
        [2, 2, 'USD', 1, 'Доллар США (Банк России)', 0, 1],
        [3, 3, 'EUR', 1, 'Евро (Банк России)', 0, 1],
        [4, 4, 'PEIX', 2, 'NASDAQ', 2, 1],
        [5, 5, 'FANG  220121C00040000', 2, 'CBOE', -1, 1],
        [6, 6, 'XOM', 2, 'NYSE', 2, 1],
        [7, 7, 'XOM   220121C00042500', 2, 'CBOE', -1, 1]
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_tickers") == len(test_symbols)
    for i, symbol in enumerate(test_symbols):
        assert readSQL("SELECT * FROM asset_tickers WHERE id=:id", [(":id", i + 1)]) == symbol

    # validate assets data
    test_data = [
        [1, 4, 1, '69423U305'],
        [2, 5, 2, '1642723200'],
        [3, 6, 1, '30231G102'],
        [4, 7, 2, '1642723200']
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_data") == len(test_data)
    for i, data in enumerate(test_data):
        assert readSQL("SELECT * FROM asset_data WHERE id=:id", [(":id", i + 1)]) == data

    # validate trades
    test_trades = [
        [1, 3, 1604926434, 1604966400, '3210359211', 1, 5, -300.0, 5.5, 0.953865, ''],
        [2, 3, 1606471692, 1606780800, '3256333343', 1, 4, 70.0, 6.898, 0.36425725, ''],
        [3, 3, 1606821387, 1606953600, '3264444280', 1, 4, 70.0, 6.08, 0.32925725, ''],
        [4, 3, 1607095765, 1607299200, '3276656996', 1, 7, -100.0, 5.2, 0.667292, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM trades") == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert readSQL("SELECT * FROM trades WHERE id=:id", [(":id", i + 1)]) == trade

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
        [1, PredefinedAsset.Money, 'Российский Рубль', '', 0, ''],
        [2, PredefinedAsset.Money, 'Доллар США', '', 0, ''],
        [3, PredefinedAsset.Money, 'Евро', '', 0, ''],
        [4, PredefinedAsset.Stock, 'PACIFIC ETHANOL INC', 'US69423U3059', 0, ''],
        [5, PredefinedAsset.Derivative, 'FANG 21JAN22 40.0 C', '', 0, ''],
        [6, PredefinedAsset.Stock, 'EXXON MOBIL CORP', 'US30231G1022', 0, ''],
        [7, PredefinedAsset.Derivative, 'XOM 21JAN22 42.5 C', '', 0, ''],
        [8, PredefinedAsset.Stock, 'ALTO INGREDIENTS INC', 'US0215131063', 0, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM assets") == len(test_assets)
    for i, asset in enumerate(test_assets):
        assert readSQL("SELECT * FROM assets WHERE id=:id", [(":id", i + 1)]) == asset

    # validate assets
    test_symbols = [
        [1, 1, 'RUB', 1, 'Российский Рубль', -1, 1],
        [2, 2, 'USD', 1, 'Доллар США (Банк России)', 0, 1],
        [3, 3, 'EUR', 1, 'Евро (Банк России)', 0, 1],
        [4, 4, 'PEIX', 2, 'NASDAQ', 2, 1],
        [5, 5, 'FANG  220121C00040000', 2, 'CBOE', -1, 1],
        [6, 6, 'XOM', 2, 'NYSE', 2, 1],
        [7, 7, 'XOM   220121C00042500', 2, 'CBOE', -1, 1],
        [8, 8, 'ALTO', 2, 'NASDAQ', 2, 0],
        [9, 8, 'PEIX', 2, 'NASDAQ', 2, 1]
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_tickers") == len(test_symbols)
    for i, symbol in enumerate(test_symbols):
        assert readSQL("SELECT * FROM asset_tickers WHERE id=:id", [(":id", i + 1)]) == symbol

    # validate assets
    test_data = [
        [1, 4, 1, '69423U305'],
        [3, 6, 1, '30231G102'],
        [5, 8, 1, '021513106'],
        [6, 5, 2, '1642723200'],
        [7, 7, 2, '1642723200']
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_data") == len(test_data)
    for data in test_data:
        assert readSQL("SELECT * FROM asset_data WHERE id=:id", [(":id", data[0])]) == data

    # validate trades
    test_trades = [
        [1, 3, 1604926434, 1604966400, '3210359211', 1, 5, -300.0, 5.5, 0.953865, ''],
        [2, 3, 1606471692, 1606780800, '3256333343', 1, 4, 70.0, 6.898, 0.36425725, ''],
        [3, 3, 1606821387, 1606953600, '3264444280', 1, 4, 70.0, 6.08, 0.32925725, ''],
        [4, 3, 1607095765, 1607299200, '3276656996', 1, 7, -100.0, 5.2, 0.667292, ''],
        [5, 3, 1610625615, 1611014400, '3381623127', 1, 8, -70.0, 7.42, 0.23706599, ''],
        [6, 3, 1612871230, 1613001600, '3480222427', 1, 8, -70.0, 7.71, 0.23751462, ''],
        [7, 3, 1620750000, 1620864000, '3764387743', 1, 6, -100.0, 42.5, 0.033575, 'Option assignment/exercise'],
        [8, 3, 1620750000, 1620777600, '3764387737', 1, 7, 100.0, 0.0, 0.0, 'Option assignment'],
        [9, 3, 1623247000, 1623283200, '3836250920', 1, 5, 300.0, 50.8, -0.1266, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM trades") == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert readSQL("SELECT * FROM trades WHERE id=:id", [(":id", i + 1)]) == trade

    # validate corp actions
    test_asset_actions = [
        [1, 5, 1610569500, '14909999818', 1, 3, 4, 140.0, 'PEIX(US69423U3059) CUSIP/ISIN CHANGE TO (US0215131063) (PEIX, ALTO INGREDIENTS INC, US0215131063)']
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_actions") == len(test_asset_actions)
    for i, action in enumerate(test_asset_actions):
        assert readSQL("SELECT * FROM asset_actions WHERE id=:id", [(":id", i + 1)]) == action

    test_action_results = [
        [1, 1, 8, 140.0, 1.0]
    ]
    assert readSQL("SELECT COUNT(*) FROM action_results") == len(test_action_results)
    for i, result in enumerate(test_action_results):
        assert readSQL("SELECT * FROM action_results WHERE id=:id", [(":id", i + 1)]) == result

    # Check that there are no remainders
    assert readSQL("SELECT amount_acc, value_acc FROM ledger_totals WHERE asset_id=4 ORDER BY id DESC LIMIT 1") == [0.0, 0.0]
    assert readSQL("SELECT amount_acc, value_acc FROM ledger_totals WHERE asset_id=7 ORDER BY id DESC LIMIT 1") == [0.0, 0.0]
    assert readSQL("SELECT amount_acc, value_acc FROM ledger WHERE asset_id=4 ORDER BY id DESC LIMIT 1") == [0.0, 0.0]
    assert readSQL("SELECT amount_acc, value_acc FROM ledger WHERE asset_id=7 ORDER BY id DESC LIMIT 1") == [0.0, 0.0]

    # Check correct number of deals
    assert readSQL("SELECT COUNT(*) FROM deals_ext") == 6


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_warrants(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_warrants.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_warrants.xml')
    assert IBKR._data == statement
