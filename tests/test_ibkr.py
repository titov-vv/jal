from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from jal.data_import.broker_statements.ibkr import StatementIBKR
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
        [4, PredefinedAsset.Stock, 'PACIFIC ETHANOL INC', 'US69423U3059', 0, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM assets") == len(test_assets)
    for i, asset in enumerate(test_assets):
        assert readSQL("SELECT * FROM assets WHERE id=:id", [(":id", i + 1)]) == asset

    # validate assets
    test_symbols = [
        [1, 1, 'RUB', 1, 'Российский Рубль', -1, 1],
        [2, 2, 'USD', 1, 'Доллар США (Банк России)', 0, 1],
        [3, 3, 'EUR', 1, 'Евро (Банк России)', 0, 1],
        [4, 4, 'PEIX', 2, 'NASDAQ', 2, 1]
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_tickers") == len(test_symbols)
    for i, symbol in enumerate(test_symbols):
        assert readSQL("SELECT * FROM asset_tickers WHERE id=:id", [(":id", i + 1)]) == symbol

    # validate assets
    test_data = [
        [1, 4, 1, '69423U305']
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_data") == len(test_data)
    for i, data in enumerate(test_data):
        assert readSQL("SELECT * FROM asset_data WHERE id=:id", [(":id", i + 1)]) == data

    # validate trades
    test_trades = [
        [1, 3, 1606471692, 1606780800, '3256333343', 1, 4, 70.0, 6.898, 0.36425725, ''],
        [2, 3, 1606821387, 1606953600, '3264444280', 1, 4, 70.0, 6.08, 0.32925725, '']
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
        [5, PredefinedAsset.Stock, 'ALTO INGREDIENTS INC', 'US0215131063', 0, '']
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
        [5, 5, 'ALTO', 2, 'NASDAQ', 2, 0],
        [6, 5, 'PEIX', 2, 'NASDAQ', 2, 1]
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_tickers") == len(test_symbols)
    for i, symbol in enumerate(test_symbols):
        assert readSQL("SELECT * FROM asset_tickers WHERE id=:id", [(":id", i + 1)]) == symbol

    # validate assets
    test_data = [
        [1, 4, 1, '69423U305'],
        [2, 5, 1, '021513106']
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_data") == len(test_data)
    for i, data in enumerate(test_data):
        assert readSQL("SELECT * FROM asset_data WHERE id=:id", [(":id", i + 1)]) == data

    # validate trades
    test_trades = [
        [1, 3, 1606471692, 1606780800, '3256333343', 1, 4, 70.0, 6.898, 0.36425725, ''],
        [2, 3, 1606821387, 1606953600, '3264444280', 1, 4, 70.0, 6.08, 0.32925725, ''],
        [3, 3, 1610625615, 1611014400, '3381623127', 1, 5, -70.0, 7.42, 0.23706599, ''],
        [4, 3, 1612871230, 1613001600, '3480222427', 1, 5, -70.0, 7.71, 0.23751462, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM trades") == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert readSQL("SELECT * FROM trades WHERE id=:id", [(":id", i + 1)]) == trade

    # validate corp actions
    test_corp_actons = [
        [1, 5, 1610569500, '14909999818', 1, 3, 4, 140.0, 5, 140.0, 1.0, 'PEIX(US69423U3059) CUSIP/ISIN CHANGE TO (US0215131063) (PEIX, ALTO INGREDIENTS INC, US0215131063)']
    ]
    assert readSQL("SELECT COUNT(*) FROM corp_actions") == len(test_corp_actons)
    for i, action in enumerate(test_corp_actons):
        assert readSQL("SELECT * FROM corp_actions WHERE id=:id", [(":id", i + 1)]) == action

    # Check that there are no remainders
    assert readSQL("SELECT amount_acc, value_acc FROM ledger_totals WHERE asset_id=4 ORDER BY id DESC LIMIT 1") == [0.0, 0.0]
    assert readSQL("SELECT amount_acc, value_acc FROM ledger_totals WHERE asset_id=5 ORDER BY id DESC LIMIT 1") == [0.0, 0.0]
    assert readSQL("SELECT amount_acc, value_acc FROM ledger WHERE asset_id=4 ORDER BY id DESC LIMIT 1") == [0.0, 0.0]
    assert readSQL("SELECT amount_acc, value_acc FROM ledger WHERE asset_id=5 ORDER BY id DESC LIMIT 1") == [0.0, 0.0]

    # Check correct number of deals
    assert readSQL("SELECT COUNT(*) FROM deals_ext") == 4
