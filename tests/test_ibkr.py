import json
from decimal import Decimal

import pytest

from PySide6.QtWidgets import QMessageBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from jal.data_import.broker_statements.ibkr import StatementIBKR
from jal.data_import.statement import JSF, Statement, Statement_ImportError
from tests.helpers import d2t
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset, AssetData
from jal.db.db import JalDB
from jal.db.operations import AssetPayment, AssetIncome
from jal.constants import PredefinedAsset, PredefinedCategory, BookAccount, SymbolId, AssetLocation


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
        {'id': 1, 'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'country_id': 0,
         'symbols': [{'id': 1, 'symbol': 'RUB', 'currency_id': 1, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1}],
         'ID': {(1, SymbolId.ISO4217_CODE): '643'}},
        {'id': 2, 'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'country_id': 0,
         'symbols': [{'id': 2, 'symbol': 'USD', 'currency_id': 2, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1}],
         'ID': {(2, SymbolId.ISO4217_CODE): '840'}},
        {'id': 3, 'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'country_id': 0,
         'symbols': [{'id': 3, 'symbol': 'EUR', 'currency_id': 3, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1}],
         'ID': {(3, SymbolId.ISO4217_CODE): '978'}},
        {'id': 4, 'type_id': PredefinedAsset.Stock, 'full_name': 'PACIFIC ETHANOL INC', 'country_id': 0,
         'symbols': [{'id': 4, 'symbol': 'PEIX', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(4, SymbolId.ISIN): 'US69423U3059', (4, SymbolId.CUSIP): '69423U305'}},
        {'id': 5, 'type_id': PredefinedAsset.Derivative, 'full_name': 'FANG 21JAN22 40.0 C', 'country_id': 0,
         'symbols': [{'id': 5, 'symbol': 'FANG  220121C00040000', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1}],
         'ID': {},
         'data': {AssetData.ExpiryDate: '1642723200'}},
        {'id': 6, 'type_id': PredefinedAsset.Stock, 'full_name': 'EXXON MOBIL CORP', 'country_id': 2,
         'symbols': [{'id': 6, 'symbol': 'XOM', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(6, SymbolId.ISIN): 'US30231G1022', (6, SymbolId.CUSIP): '30231G102'}},
        {'id': 7, 'type_id': PredefinedAsset.Derivative, 'full_name': 'XOM 21JAN22 42.5 C', 'country_id': 0,
         'symbols': [{'id': 7, 'symbol': 'XOM   220121C00042500', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1}],
         'ID': {},
         'data': {AssetData.ExpiryDate: '1642723200'}},
        {'id': 8, 'type_id': PredefinedAsset.Stock, 'full_name': 'AURORA CANNABIS INC', 'country_id': 0,
         'symbols': [{'id': 8, 'symbol': 'ACB', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(8, SymbolId.CUSIP): '05156X108'}},
        {'id': 9, 'type_id': PredefinedAsset.Stock, 'full_name': 'TWO HARBORS INVESTMENT CORP', 'country_id': 2,
         'symbols': [{'id': 9, 'symbol': 'TWO', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(9, SymbolId.ISIN): 'US90187B4086', (9, SymbolId.CUSIP): '90187B408'}},
        {'id': 10, 'type_id': PredefinedAsset.Stock, 'full_name': 'NEW RESIDENTIAL INVESTMENT', 'country_id': 2,
         'symbols': [{'id': 10, 'symbol': 'NRZ', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(10, SymbolId.ISIN): 'US64828T2015', (10, SymbolId.CUSIP): '64828T201'}},
        {'id': 11, 'type_id': PredefinedAsset.Stock, 'full_name': 'INTERACTIVE BROKERS GRO-CL A', 'country_id': 0,
         'symbols': [{'id': 11, 'symbol': 'IBKR', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(11, SymbolId.ISIN): 'US45841N1072', (11, SymbolId.CUSIP): '45841N107'}},
        {'id': 12, 'type_id': PredefinedAsset.Stock, 'full_name': 'VERB TECHNOLOGY CO INC', 'country_id': 0,
         'symbols': [{'id': 12, 'symbol': 'VERB', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(12, SymbolId.ISIN): 'US92337U1043', (12, SymbolId.CUSIP): '92337U104'}}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets

    # validate trades
    test_trades = [
        [1, 3, 1573734263, 1574035200, '2608038423', 1, 8, '1.5E+2', '3.46', ''],
        [2, 3, 1604944434, 1604966400, '3210359211', 1, 5, '-3E+2', '5.5', ''],
        [3, 3, 1606489692, 1606780800, '3256333343', 1, 4, '7E+1', '6.898', ''],
        [4, 3, 1606839387, 1606953600, '3264444280', 1, 4, '7E+1', '6.08', ''],
        [5, 3, 1607113765, 1607299200, '3276656996', 1, 7, '-1E+2', '5.2', '']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade
    fees = {f[1]: f[5] for f in JalAccount(1).dump_fees() if f[1] in [t[0] for t in test_trades]}
    assert fees == {1: '1', 2: '0.953865', 3: '0.36425725', 4: '0.32925725', 5: '0.667292'}

    # validate dividend & tax
    # Operation ids are global (they come from the 'operations' root), so these continue after the five trades above
    test_dividends = [
        [6, 2, 1592770800, 1, 0, '', 1, 1, 6, '16.76', '1.68', 'XOM (US30231G1022) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [7, 2, 1596054000, 1, 0, '', 1, 1, 9, '51', '5.1', 'TWO(US90187B4086) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)'],
        [8, 2, 1588191600, 1, 0, '', 1, 1, 10, '25', '2.5', 'NRZ(US64828T2015) CASH DIVIDEND USD 0.25 PER SHARE (Ordinary Dividend)']
    ]
    payments = JalAccount(1).dump_asset_payments()
    assert len(payments) == len(test_dividends)
    for i, payment in enumerate(test_dividends):
        assert payments[i] == payment

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
        {'id': 1, 'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'country_id': 0,
         'symbols': [{'id': 1, 'symbol': 'RUB', 'currency_id': 1, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1}],
         'ID': {(1, SymbolId.ISO4217_CODE): '643'}},
        {'id': 2, 'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'country_id': 0,
         'symbols': [{'id': 2, 'symbol': 'USD', 'currency_id': 2, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1}],
         'ID': {(2, SymbolId.ISO4217_CODE): '840'}},
        {'id': 3, 'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'country_id': 0,
         'symbols': [{'id': 3, 'symbol': 'EUR', 'currency_id': 3, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1}],
         'ID': {(3, SymbolId.ISO4217_CODE): '978'}},
        {'id': 4, 'type_id': PredefinedAsset.Stock, 'full_name': 'PACIFIC ETHANOL INC', 'country_id': 0,
         'symbols': [{'id': 4, 'symbol': 'PEIX', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(4, SymbolId.ISIN): 'US69423U3059', (4, SymbolId.CUSIP): '69423U305'}},
        {'id': 5, 'type_id': PredefinedAsset.Derivative, 'full_name': 'FANG 21JAN22 40.0 C', 'country_id': 0,
         'symbols': [{'id': 5, 'symbol': 'FANG  220121C00040000', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1}],
         'ID': {},
         'data': {AssetData.ExpiryDate: '1642723200'}},
        {'id': 6, 'type_id': PredefinedAsset.Stock, 'full_name': 'EXXON MOBIL CORP', 'country_id': 2,
         'symbols': [{'id': 6, 'symbol': 'XOM', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(6, SymbolId.ISIN): 'US30231G1022', (6, SymbolId.CUSIP): '30231G102'}},
        {'id': 7, 'type_id': PredefinedAsset.Derivative, 'full_name': 'XOM 21JAN22 42.5 C', 'country_id': 0,
         'symbols': [{'id': 7, 'symbol': 'XOM   220121C00042500', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1}],
         'ID': {},
         'data': {AssetData.ExpiryDate: '1642723200'}},
        {'id': 8, 'type_id': PredefinedAsset.Stock, 'full_name': 'AURORA CANNABIS INC', 'country_id': 0,
         'symbols': [{'id': 8, 'symbol': 'ACB', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(8, SymbolId.ISIN): 'CA05156X1087', (8, SymbolId.CUSIP): '05156X108'}},
        {'id': 9, 'type_id': PredefinedAsset.Stock, 'full_name': 'TWO HARBORS INVESTMENT CORP', 'country_id': 2,
         'symbols': [{'id': 9, 'symbol': 'TWO', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(9, SymbolId.ISIN): 'US90187B4086', (9, SymbolId.CUSIP): '90187B408'}},
        {'id': 10, 'type_id': PredefinedAsset.Stock, 'full_name': 'NEW RESIDENTIAL INVESTMENT', 'country_id': 2,
         'symbols': [{'id': 10, 'symbol': 'NRZ', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 0},
                     {'id': 15, 'symbol': 'RITM', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(10, SymbolId.ISIN): 'US64828T2015', (10, SymbolId.CUSIP): '64828T201', (15, SymbolId.ISIN): 'US64828T2015', (15, SymbolId.CUSIP): '64828T201'}},
        {'id': 11, 'type_id': PredefinedAsset.Stock, 'full_name': 'INTERACTIVE BROKERS GRO-CL A', 'country_id': 0,
         'symbols': [{'id': 11, 'symbol': 'IBKR', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(11, SymbolId.ISIN): 'US45841N1072', (11, SymbolId.CUSIP): '45841N107'}},
        {'id': 12, 'type_id': PredefinedAsset.Stock, 'full_name': 'VERB TECHNOLOGY CO INC', 'country_id': 0,
         'symbols': [{'id': 12, 'symbol': 'VERB', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(12, SymbolId.ISIN): 'US92337U1043', (12, SymbolId.CUSIP): '92337U104'}},
        {'id': 13, 'type_id': PredefinedAsset.Stock, 'full_name': 'ALTO INGREDIENTS INC', 'country_id': 0,
         'symbols': [{'id': 13, 'symbol': 'ALTO', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 0},
                     {'id': 21, 'symbol': 'PEIX', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(13, SymbolId.ISIN): 'US0215131063', (13, SymbolId.CUSIP): '021513106', (21, SymbolId.ISIN): 'US0215131063', (21, SymbolId.CUSIP): '021513106'}},
        {'id': 14, 'type_id': PredefinedAsset.Stock, 'full_name': 'AURORA CANNABIS INC', 'country_id': 0,
         'symbols': [{'id': 14, 'symbol': 'ACB', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1}],
         'ID': {(14, SymbolId.ISIN): 'CA05156X8843', (14, SymbolId.CUSIP): '05156X884'}},
        {'id': 15, 'type_id': PredefinedAsset.Stock, 'full_name': 'VERB TECHNOLOGY CO INC', 'country_id': 0,
         'symbols': [{'id': 16, 'symbol': 'VERB', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(16, SymbolId.ISIN): 'US92337U2033', (16, SymbolId.CUSIP): '92337U203'}},
        {'id': 16, 'type_id': PredefinedAsset.Stock, 'full_name': 'VERB TECHNOLOGY CO INC', 'country_id': 0,
         'symbols': [{'id': 17, 'symbol': 'VERB', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(17, SymbolId.ISIN): 'US92337U3023', (17, SymbolId.CUSIP): '92337U302'}},
        {'id': 17, 'type_id': PredefinedAsset.Stock, 'full_name': 'VOLCON INC', 'country_id': 0,
         'symbols': [{'id': 18, 'symbol': 'VLCN', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(18, SymbolId.ISIN): 'US92864V4005', (18, SymbolId.CUSIP): '92864V400'}},
        {'id': 18, 'type_id': PredefinedAsset.Stock, 'full_name': 'VOLCON INC', 'country_id': 0,
         'symbols': [{'id': 19, 'symbol': 'VLCN', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(19, SymbolId.ISIN): 'US92864V2025', (19, SymbolId.CUSIP): '92864V202'}},
        {'id': 19, 'type_id': PredefinedAsset.Stock, 'full_name': 'VOLCON INC', 'country_id': 0,
         'symbols': [{'id': 20, 'symbol': 'VLCN', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1}],
         'ID': {(20, SymbolId.ISIN): 'US92864V3015', (20, SymbolId.CUSIP): '92864V301'}}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets

    # validate trades
    test_trades = [
        [1, 3, 1573734263, 1574035200, '2608038423', 1, 8, '1.5E+2', '3.46', ''],
        [2, 3, 1604944434, 1604966400, '3210359211', 1, 5, '-3E+2', '5.5', ''],
        [3, 3, 1606489692, 1606780800, '3256333343', 1, 4, '7E+1', '6.898', ''],
        [4, 3, 1606839387, 1606953600, '3264444280', 1, 4, '7E+1', '6.08', ''],
        [5, 3, 1607113765, 1607299200, '3276656996', 1, 7, '-1E+2', '5.2', ''],
        [9, 3, 1610643615, 1611014400, '3381623127', 1, 21, '-7E+1', '7.42', ''],
        [10, 3, 1612889230, 1613001600, '3480222427', 1, 13, '-7E+1', '7.71', ''],
        [11, 3, 1620764400, 1620864000, '3764387743', 1, 6, '-1E+2', '42.5', 'Option assignment/exercise'],
        [12, 3, 1620764400, 1620777600, '3764387737', 1, 7, '1E+2', '0', 'Option assignment'],
        [13, 3, 1623261400, 1623283200, '3836250920', 1, 5, '3E+2', '50.8', '']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade
    fees = {f[1]: f[5] for f in JalAccount(1).dump_fees() if f[1] in [t[0] for t in test_trades]}
    assert fees == {1: '1', 2: '0.953865', 3: '0.36425725', 4: '0.32925725', 5: '0.667292', 9: '0.23706599', 10: '0.23751462', 11: '0.033575', 13: '-0.1266'}

    # validate dividend & tax
    test_dividends = [
        [6, 2, 1592770800, 1, 0, '', 1, 1, 6, '16.76', '0.21', 'XOM (US30231G1022) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [7, 2, 1596054000, 1, 0, '', 1, 1, 9, '51', '0.01', 'TWO(US90187B4086) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)'],
        [8, 2, 1588191600, 1, 0, '', 1, 1, 10, '25', '1.04', 'NRZ(US64828T2015) CASH DIVIDEND USD 0.25 PER SHARE (Ordinary Dividend)'],
    ]
    payments = JalAccount(1).dump_asset_payments()
    assert len(payments) == len(test_dividends)
    for i, payment in enumerate(test_dividends):
        assert payments[i] == payment

    # ... and the vesting, which is the asset itself arriving and is stored as such
    assert JalAccount(1).dump_asset_incomes() == [
        [14, 9, 1659484800, 0, 0, '', AssetIncome.StockVesting, 1, 11, '0.3052', '0', '59.21', 'Stock Award Vesting']]

    # validate corp actions
    test_asset_actions = [
        [15, 5, 1588969500, 1, '12693114547', 1, 4, 8, '1.5E+2', 'ACB(CA05156X1087) SPLIT 1 FOR 12 (ACB, AURORA CANNABIS INC, CA05156X8843)',
         [1, 15, 14, '12.5', '1']],
        [16, 5, 1610569500, 1, '14909999818', 1, 3, 4, '1.4E+2', 'PEIX(US69423U3059) CUSIP/ISIN CHANGE TO (US0215131063) (PEIX, ALTO INGREDIENTS INC, US0215131063)',
         [2, 16, 21, '1.4E+2', '1']]
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
        statement = json.load(json_file, parse_float=Decimal)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_warrants.xml')
    assert IBKR._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_cfd(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_cfd.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file, parse_float=Decimal)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_cfd.xml')
    assert IBKR._data == statement



# A CFD charge that names an asset is stored as a fee of that asset whatever it is called, and one that names none
# is a spending only when it is a known kind of interest
def test_ibkr_cfd_charge_on_an_asset_is_an_asset_fee(caplog):
    ibkr = StatementIBKR()
    ibkr._data = {JSF.ASSET_PAYMENTS: [{'id': 4}], JSF.INCOME_SPENDING: []}
    charges = [
        {'account': 1, 'symbol': 3, 'timestamp': 1657065600, 'amount': Decimal('-0.02'), 'number': '11',
         'description': 'CFD BORROW FEE FOR MU for 06-JUL-2022'},
        {'account': 1, 'symbol': 3, 'timestamp': 1657065600, 'amount': Decimal('-0.50'), 'number': '12',
         'description': 'SOMETHING NEW FOR MU'},
        {'account': 1, 'symbol': StatementIBKR.NoAsset, 'timestamp': 1657065600, 'amount': Decimal('-0.06'),
         'number': '13', 'description': 'SHORT CFD INTEREST FOR 06-JUL-2022'},
        {'account': 1, 'symbol': StatementIBKR.NoAsset, 'timestamp': 1657065600, 'amount': Decimal('-0.07'),
         'number': '14', 'description': 'SOMETHING NEW'},
    ]
    ibkr.load_cfd_charges(charges)

    fees = [x for x in ibkr._data[JSF.ASSET_PAYMENTS] if x.get('type') == JSF.PAYMENT_FEE]
    assert [(x['id'], x['symbol'], x['amount'], x['number']) for x in fees] == [
        (5, 3, Decimal('-0.02'), '11'), (6, 3, Decimal('-0.50'), '12')]
    assert [(x['id'], x['lines'][0]['amount']) for x in ibkr._data[JSF.INCOME_SPENDING]] == [(1, Decimal('-0.06'))]
    unknown = [x.message for x in caplog.records if 'Unknown CFD charge description' in x.message]
    assert [x.split(': ')[1] for x in unknown] == ['SOMETHING NEW FOR MU', 'SOMETHING NEW']

# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_corp_actions(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_corp_actions.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file, parse_float=Decimal)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_corp_actions.xml')
    assert IBKR._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_q1_tax_correction_does_not_match_future_dividend(prepare_db):
    # A correction that names no corporate action can only fall back on the day it was paid, and a later dividend
    # carrying the very same tax figure must not be taken for it however well the amounts line up.
    ibkr = StatementIBKR()
    ibkr._data = {
        JSF.ASSET_PAYMENTS: [
            {'id': 1, 'type': JSF.PAYMENT_DIVIDEND, 'account': 1, 'symbol': 95, 'timestamp': d2t(250214),
             'amount': Decimal('13.73'), 'tax': Decimal('0.79'), 'description': 'O(US7561091049) CASH DIVIDEND USD 0.264 PER SHARE (Ordinary Dividend)'},
            {'id': 2, 'type': JSF.PAYMENT_DIVIDEND, 'account': 1, 'symbol': 95, 'timestamp': d2t(250314),
             'amount': Decimal('13.94'), 'tax': Decimal('4.12'), 'description': 'O(US7561091049) CASH DIVIDEND USD 0.268 PER SHARE (Ordinary Dividend)'},
        ],
        JSF.ASSETS: [{'id': 1, JSF.SYMBOLS: [{'id': 95, 'symbol': 'O', 'isin': 'US7561091049'}]}]
    }
    ibkr._map_db_account = lambda _: 0
    ibkr._map_db_asset_by_symbol = lambda _: 0

    tax = {'account': 1, 'symbol': 95, 'timestamp': d2t(250301), 'reported': d2t(250301), 'amount': Decimal('4.12'),
           'action_id': '', 'description': 'O(US7561091049) CASH DIVIDEND USD 0.264 PER SHARE - US TAX'}
    with pytest.raises(Statement_ImportError):
        ibkr.find_dividend4tax(tax)


# ----------------------------------------------------------------------------------------------------------------------
# Legs of a corporate action are paired by their actionID, whatever a symbol in the description looks like
def test_ibkr_merger_legs_are_paired_by_action_id():
    ibkr = StatementIBKR()
    ibkr._data = {JSF.CORP_ACTIONS: []}
    actions = [{
        'type': 'merger', 'account': 1, 'symbol': 29, 'asset_type': 'stock', 'timestamp': 1646857500,
        'number': '19750736274', 'action_id': '123456789', 'currency': 'USD',
        'description': '20220309164306BGTK(US34520J2078) MERGED(Acquisition) WITH US0896931054 1 FOR 1 (BGTK, BIG TOKEN INC, US0896931054)',
        'quantity': Decimal('10000'), 'value': Decimal('24'), 'proceeds': Decimal('0'), 'code': ''
    }, {
        'type': 'merger', 'account': 1, 'symbol': 28, 'asset_type': 'stock', 'timestamp': 1646857500,
        'number': '19750736269', 'action_id': '123456789', 'currency': 'USD',
        'description': '20220309164306BGTK(US34520J2078) MERGED(Acquisition) WITH US0896931054 1 FOR 1 (BGTK.OLD, FORCE PROTECTION VIDEO EQUIP, US34520J2078)',
        'quantity': Decimal('-10000'), 'value': Decimal('-20'), 'proceeds': Decimal('0'), 'code': ''
    }]

    ibkr.load_corporate_actions(actions)

    assert len(ibkr._data[JSF.CORP_ACTIONS]) == 1
    merger = ibkr._data[JSF.CORP_ACTIONS][0]
    assert merger['symbol'] == 28
    assert merger['quantity'] == Decimal('10000')
    assert merger['outcome'] == [{'symbol': 29, 'quantity': Decimal('10000'), 'share': Decimal('0')}]
    assert 'action_id' not in merger and 'currency' not in merger


# ----------------------------------------------------------------------------------------------------------------------
# Two real reverse splits with a change of ISIN: each one is a pair of records that share an actionID
def test_ibkr_split_legs_are_paired_by_action_id(tmp_path, project_root, data_path, prepare_db_taxes):
    ibkr = StatementIBKR()
    ibkr.load(data_path + 'ibkr_split_action_id.xml')

    isin = lambda symbol_id: ibkr._symbol(symbol_id)['isin']
    splits = [(isin(x['symbol']), x['quantity'], isin(x['outcome'][0]['symbol']), x['outcome'][0]['quantity'],
               x['outcome'][0]['share'], x['type']) for x in ibkr._data[JSF.CORP_ACTIONS]]
    assert sorted(splits) == [
        ('US74347G1922', Decimal('3'), 'US74350P6759', Decimal('0.6'), Decimal('1'), JSF.ACTION_SPLIT),
        ('US90187E3036', Decimal('15000'), 'US90187E4026', Decimal('15'), Decimal('1'), JSF.ACTION_SPLIT)
    ]


# ----------------------------------------------------------------------------------------------------------------------
# A tax given back on the '.OLD' symbol with neither ISIN nor CUSIP gets the asset of the dividend it has the actionID
# of, though the ticker alone is ambiguous here: SQQQ is both the asset before a split and the one after it
def test_ibkr_tax_without_identifiers_finds_its_asset_by_action_id(tmp_path, project_root, data_path, prepare_db_taxes):
    ibkr = StatementIBKR()
    ibkr.load(data_path + 'ibkr_old_symbol_tax.xml')

    assert len(ibkr._data[JSF.ASSET_PAYMENTS]) == 1
    dividend = ibkr._data[JSF.ASSET_PAYMENTS][0]
    assert ibkr._symbol(dividend['symbol'])['isin'] == 'US74347G1922'
    assert dividend['amount'] == Decimal('0.96')
    assert dividend.get('tax', Decimal('0')) == Decimal('0')   # -0.29 +0.29 -0.29 +0.29


# ----------------------------------------------------------------------------------------------------------------------
# Loads a statement of test data after a change made in its text
def load_changed(tmp_path, data_path, file_name, old, new, count=1) -> StatementIBKR:
    with open(data_path + file_name, 'r', encoding='utf-8') as xml_file:
        text = xml_file.read()
    assert text.count(old) == count
    with open(tmp_path / file_name, 'w', encoding='utf-8') as xml_file:
        xml_file.write(text.replace(old, new))
    ibkr = StatementIBKR()
    ibkr.load(str(tmp_path / file_name))
    return ibkr


# A corporate action without 'actionID' attribute isn't imported: Flex Query has to be set up to give it
def test_ibkr_corporate_action_without_action_id_halts_the_import(tmp_path, project_root, data_path, prepare_db_taxes,
                                                                  monkeypatch):
    dumps = []
    monkeypatch.setattr(Statement, 'save_debug_info', lambda self, **kwargs: dumps.append(kwargs['debug_info']))
    with pytest.raises(Statement_ImportError) as refusal:
        load_changed(tmp_path, data_path, 'ibkr_corp_actions.xml', ' actionID="SYNT-EXAMPLE-1"', '', count=2)
    assert "'actionID' attribute" in str(refusal.value) and 'Flex Query' in str(refusal.value)
    assert 'TWOHD.OLD' in str(refusal.value)   # the records are shown
    assert dumps == []                          # nothing to report - it is the query that has to be fixed


# An empty 'actionID' is not expected at all: the user is asked to report it and gets a dump to attach
def test_ibkr_corporate_action_with_empty_action_id_halts_the_import(tmp_path, project_root, data_path,
                                                                     prepare_db_taxes, monkeypatch):
    dumps = []
    monkeypatch.setattr(Statement, 'save_debug_info', lambda self, **kwargs: dumps.append(kwargs['debug_info']))
    with pytest.raises(Statement_ImportError) as refusal:
        load_changed(tmp_path, data_path, 'ibkr_corp_actions.xml', 'actionID="SYNT-EXAMPLE-1"', 'actionID=""', count=2)
    assert '/issues' in str(refusal.value) and StatementIBKR.FormerCorpActionsTag in str(refusal.value)
    assert len(dumps) == 1
    assert 'TWOHD' in dumps[0] and 'U7654321' in dumps[0]


# Records of an action that are not what its type has to have stop the import and say what differs
@pytest.mark.parametrize("file_name, old, new, count, expected", [
    # a leg of a split with ISIN change is on its own
    ('ibkr_corp_actions.xml', 'quantity="-35" fifoPnlRealized="0" mtmPnl="0" code="" type="RS" actionID="SYNT-EXAMPLE-1"',
     'quantity="-35" fifoPnlRealized="0" mtmPnl="0" code="" type="RS" actionID="SYNT-EXAMPLE-9"', 1, 'a split that changes ISIN'),
    # both legs of a split take the asset away
    ('ibkr_corp_actions.xml', 'quantity="0.035"', 'quantity="-0.035"', 1, 'withdrawn (-) / received (+) records is 1/0 or 0/1 or 1/1'),
    # legs of one action are of different types
    ('ibkr_corp_actions.xml', 'code="" type="RS" actionID="SYNT-EXAMPLE-1" transactionID="25164201877"',
     'code="" type="IC" actionID="SYNT-EXAMPLE-1" transactionID="25164201877"', 1, 'the same type, account and date'),
    # a spin-off shares its id with another record
    ('ibkr_merger_spinoff.xml', 'actionID="SYNT-EXAMPLE-2"', 'actionID="SYNT-EXAMPLE-1"', 1, 'the same type, account and date'),
    # a merger pays money that its description says nothing about
    ('ibkr_merger_complex.xml', 'CASH and STOCK MERGER', 'STOCK MERGER', 6, "has 'CASH' in its description"),
    # a cancellation that cancels nothing
    ('ibkr_spinoff.xml', 'mtmPnl="0" code="" type="SO"', 'mtmPnl="0" code="Ca" type="SO"', 1, 'a cancellation repeats the record'),
])
def test_ibkr_unexpected_corporate_action_halts_the_import(tmp_path, project_root, data_path, prepare_db_taxes,
                                                           monkeypatch, file_name, old, new, count, expected):
    monkeypatch.setattr(Statement, 'save_debug_info', lambda self, **kwargs: None)
    with pytest.raises(Statement_ImportError) as refusal:
        load_changed(tmp_path, data_path, file_name, old, new, count)
    assert expected in str(refusal.value)
    assert '/issues' in str(refusal.value)


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_find_db_stock_dividend_for_tax_correction(prepare_db, monkeypatch):
    # The payment a correction belongs to is usually not in the statement that carries the correction - it was
    # stored a year earlier - so a stored payment has to be a candidate like any other, and is pulled into the
    # statement under an id of its own when it wins.
    class StoredPayment:
        def oid(self): return 332
        def timestamp(self): return 1672258800
        def number(self): return '22598209889'          # the corporate action it was stored under
        def amount(self): return Decimal('0.2776')
        def tax(self): return Decimal('0.48')
        def note(self): return 'BCV (US0596951063) STOCK DIVIDEND US0596951063 18507808 FOR 1000000000'

    monkeypatch.setattr('jal.data_import.broker_statements.ibkr.AssetIncome.get_list',
                        lambda account, asset, subtype: [StoredPayment()] if subtype == AssetIncome.StockDividend else [])

    ibkr = StatementIBKR()
    ibkr._data = {JSF.ASSET_PAYMENTS: [],
                  JSF.ASSETS: [{'id': 1, JSF.SYMBOLS: [{'id': 294, 'symbol': 'BCV', 'isin': 'US0596951063'}]}]}
    ibkr._map_db_account = lambda _: 1
    ibkr._map_db_asset_by_symbol = lambda _: 294

    tax = {'account': 1, 'symbol': 294, 'timestamp': 1672258800, 'reported': 1672258800, 'amount': Decimal('0.48'),
           'action_id': '22598209889',
           'description': 'BCV (US0596951063) STOCK DIVIDEND US0596951063 18507808 FOR 1000000000 - CH TAX'}
    dividend = ibkr.find_dividend4tax(tax)

    assert dividend is not None
    assert dividend['id'] == 1   # first free statement payment id, reserved for the db record
    assert ibkr._id_map[JSF.ASSET_PAYMENTS] == {1: 332}


# A refused tax lists a stock dividend of the statement among the payments it considered
def test_ibkr_unmatched_tax_refusal_lists_stock_dividend(prepare_db, monkeypatch):
    monkeypatch.setattr(Statement, 'save_debug_info', lambda self, **kwargs: None)
    ibkr = StatementIBKR()
    ibkr._data = {JSF.ASSET_PAYMENTS: [{'id': 1, 'type': JSF.PAYMENT_DIVIDEND, 'account': 1, 'symbol': 294,
                                        'timestamp': 1672258800, 'number': '22598209881', 'amount': Decimal('8.11'),
                                        'description': 'BCV (US0596951063) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)'}],
                  JSF.ASSETS: [{'id': 1, JSF.SYMBOLS: [{'id': 294, 'symbol': 'BCV', 'isin': 'US0596951063'}]}]}
    ibkr._map_db_account = lambda _: 0
    ibkr._map_db_asset_by_symbol = lambda _: 0
    ibkr.load_stock_dividend([], [{'type': JSF.PAYMENT_STOCK_DIVIDEND, 'account': 1, 'symbol': 294, 'timestamp': 1672258800, 'number': '22598209889',
                              'description': 'BCV (US0596951063) STOCK DIVIDEND US0596951063 18507808 FOR 1000000000 (BCV, BANCROFT FUND LTD, US0596951063)',
                              'quantity': Decimal('0.2776'), 'value': Decimal('5.5'), 'proceeds': Decimal('0'),
                              'code': '', 'asset_type': JSF.ASSET_STOCK}])

    tax = {'account': 1, 'symbol': 294, 'timestamp': 1672258800, 'reported': 1672258800, 'amount': Decimal('-0.48'),
           'action_id': '11111111111',
           'description': 'BCV (US0596951063) STOCK DIVIDEND US0596951063 18507808 FOR 1000000000 - CH TAX'}
    with pytest.raises(Statement_ImportError):
        ibkr.find_dividend4tax(tax)


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_mlp_extra_tax_reported_separately_is_saved_as_fee():
    ibkr = StatementIBKR()
    ibkr._data = {
        JSF.ASSET_PAYMENTS: [
            {'id': 1, 'type': JSF.PAYMENT_DIVIDEND, 'account': 1, 'symbol': 161, 'timestamp': 1699042800,
             'amount': Decimal('5.25'), 'tax': Decimal('1.94'), 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE (Ordinary Dividend)'},
        ],
        JSF.ASSETS: [{'id': 61, 'type': JSF.ASSET_MLP, JSF.SYMBOLS: [{'id': 161, 'symbol': 'USAC'}]}],
    }
    ibkr._map_db_account = lambda _: 0
    ibkr._map_db_asset_by_symbol = lambda _: 0

    taxes = [
        {'id': 10, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'symbol': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1709078400, 'amount': Decimal('1.94'), 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
        {'id': 11, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'symbol': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1709078400, 'amount': Decimal('-1.94'), 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
        {'id': 12, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'symbol': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1724803200, 'amount': Decimal('-0.53'), 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
    ]

    aggregated = ibkr.aggregate_taxes(taxes)

    assert [tax['amount'] for tax in aggregated] == [Decimal('-1.94'), Decimal('1.94')]
    extra_fees = [x for x in ibkr._data[JSF.ASSET_PAYMENTS] if x['type'] == JSF.PAYMENT_FEE]
    assert len(extra_fees) == 1
    assert extra_fees[0]['amount'] == Decimal('-0.53')
    assert extra_fees[0]['description'].endswith(' - Extra 10% tax due to IRS section 1446')


# The extra tax carries the actionID of its dividend, as a real statement gives it, and is stored as a fee
def test_ibkr_mlp_extra_tax_is_imported_as_fee(tmp_path, project_root, data_path, prepare_db_taxes):
    statement = StatementIBKR()
    statement.load(data_path + 'ibkr_mlp_extra_tax.xml')
    statement.match_db_ids()
    statement.import_into_db()

    imported = [x for x in JalAccount.get_all_accounts() if x.number() == 'U7654321F'][0]
    dividends = AssetPayment.get_list(imported.id(), subtype=AssetPayment.Dividend)
    assert len(dividends) == 1
    assert dividends[0].amount() == Decimal('5.25')
    assert dividends[0].tax() == Decimal('1.94')
    fees = AssetPayment.get_list(imported.id(), subtype=AssetPayment.AssetFee)
    assert len(fees) == 1
    assert fees[0].amount() == Decimal('-0.53')
    assert fees[0].note().endswith(' - Extra 10% tax due to IRS section 1446')

    # The ledger keeps the extra tax apart from the withholding one and arrives at the ending cash of the statement
    Ledger().rebuild(from_timestamp=0)
    booked = JalDB._read_to_list("SELECT book_account, category_id, SUM(CAST(amount AS REAL)) FROM ledger "
                                 "WHERE category_id IS NOT NULL GROUP BY book_account, category_id "
                                 "ORDER BY book_account, category_id")
    assert [(book, category, round(amount, 2)) for book, category, amount in booked] == [
        (BookAccount.Costs, PredefinedCategory.Fees, 0.53),
        (BookAccount.Costs, PredefinedCategory.Taxes, 1.94),
        (BookAccount.Incomes, PredefinedCategory.Dividends, -5.25)
    ]
    assert imported.get_asset_amount(d2t(240101), imported.currency()) == Decimal('2.78')


# A tax charged on a trade adds to the commission of that trade, a standalone one is a fee of its asset
def test_ibkr_transaction_tax_adds_to_the_trade_fee(tmp_path, project_root, data_path, prepare_db_taxes):
    statement = StatementIBKR()
    statement.load(data_path + 'ibkr_transaction_tax.xml')

    trades = statement._data[JSF.TRADES]
    assert len(trades) == 1
    assert trades[0]['fee'] == Decimal('5.007792848')   # commission 1.987792848 + tax 3.02
    fees = [x for x in statement._data[JSF.ASSET_PAYMENTS] if x['type'] == JSF.PAYMENT_FEE]
    assert [(x['amount'], x['description']) for x in fees] == [(Decimal('-0.249018'), 'French Transaction Tax')]


# A holding bought out for cash is stored as a sale at the offer price
def test_ibkr_cash_merger_is_imported_as_sell_trade(tmp_path, project_root, data_path, prepare_db_taxes):
    statement = StatementIBKR()
    statement.load(data_path + 'ibkr_cash_merger.xml')
    statement.match_db_ids()
    statement.import_into_db()

    assert JalAccount(1).dump_trades() == [
        [1, 3, 1640031900, 1640031900, '18882610202', 1, 4, '-99', '20.75',
         'ACQD(US3333333333) MERGED(Voluntary Offer Allocation) FOR USD 20.75 PER SHARE (ACQD, ACQUIRED THERAPEUTICS INC, US3333333333)']
    ]


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_spinoff_allows_fractional_entitlement_rounding():
    ibkr = StatementIBKR()
    ibkr._data = {
        JSF.ASSETS: [
            {'id': 1, JSF.SYMBOLS: [{'id': 11, 'symbol': 'SVAC', 'isin': 'US85521J1097'}]},
            {'id': 2, JSF.SYMBOLS: [{'id': 12, 'symbol': 'CYXTW', 'isin': 'US23284C1100'}]},
        ],
        JSF.CORP_ACTIONS: [],
    }

    action = {
        'type': 'spin-off',
        'account': 1,
        'symbol': 12,
        'asset_type': 'warrant',
        'timestamp': 1627331100,
        'number': '17255221054',
        'description': 'SVAC(US85521J1097) SPINOFF  1000000 FOR 2917329 (CYXTW, CYXTW 10SEP27 11.5 C, US23284C1100)',
        'quantity': Decimal('17'),
        'value': Decimal('30.77'),
        'proceeds': Decimal('0'),
        'code': ''
    }

    assert ibkr.load_spinoff([], [action]) == 1
    assert ibkr._data[JSF.CORP_ACTIONS][0]['symbol'] == 11
    assert ibkr._data[JSF.CORP_ACTIONS][0]['quantity'] == 50   # rounded to a whole number, so an int


# ----------------------------------------------------------------------------------------------------------------------
# A withholding tax belongs to the payment it was taken out of, and IBKR says which one by giving the payment, the
# tax and every later correction of that tax one and the same corporate action id. The correction arrives in the
# statement of the following February, by which time the payment is in the ledger and nothing but that id connects
# them - the correction names its own report date, and the payment's own date is a year behind.
def test_ibkr_tax_correction_of_a_later_year_finds_its_payment_by_action_id(tmp_path, project_root, data_path,
                                                                            prepare_db_taxes):
    first = StatementIBKR()
    first.load(data_path + 'ibkr_dividends_year1.xml')
    first.match_db_ids()
    first.import_into_db()

    imported = [x for x in JalAccount.get_all_accounts() if x.number() == 'U7654321F'][0]
    payment = AssetPayment.get_list(imported.id())[0]
    assert payment.number() == '136178726'          # stored under the corporate action it came from
    assert payment.amount() == Decimal('50')
    assert payment.tax() == Decimal('5')

    second = StatementIBKR()
    second.load(data_path + 'ibkr_dividends_year2.xml')
    second.match_db_ids()
    second.import_into_db()

    # 5.00 given back and 0.25 taken again, applied to the payment that was already stored rather than to a new one
    payments = AssetPayment.get_list(imported.id())
    assert len(payments) == 1
    assert payments[0].tax() == Decimal('0.25')
    assert payments[0].amount() == Decimal('50')


# A tax that names an action nothing carries stops the import outright. Booking the payment without its correction
# would leave a tax figure quietly a year out of date, and nothing afterwards would point at it - so the statement is
# refused whole and nothing of it is kept.
def test_ibkr_tax_without_a_matching_action_halts_the_import(tmp_path, project_root, data_path, prepare_db_taxes,
                                                             monkeypatch):
    monkeypatch.setattr(Statement, 'save_debug_info', lambda self, **kwargs: None)
    statement = StatementIBKR()
    with pytest.raises(Statement_ImportError):
        statement.load(data_path + 'ibkr_dividends_year2.xml')   # the payment it corrects was never imported
    assert statement._data[JSF.ASSET_PAYMENTS] == []


# The dump left behind by a refusal has to be readable by someone who has never seen the account: the records of the
# one asset involved, as the statement gives them and as the ledger holds them, and the account number masked out so
# that the file can be sent on as it is.
def test_ibkr_refusal_dump_carries_the_asset_and_not_the_account(tmp_path, project_root, data_path, prepare_db_taxes,
                                                                 monkeypatch):
    first = StatementIBKR()
    first.load(data_path + 'ibkr_dividends_year1.xml')
    first.match_db_ids()
    first.import_into_db()
    # The stored payment loses the action id and moves a day, so neither the id nor the day can reach it any more
    JalDB._exec("UPDATE asset_payments SET number='x', timestamp=timestamp+86400", commit=True)

    dumps = []
    monkeypatch.setattr(Statement, 'save_debug_info', lambda self, **kwargs: dumps.append(kwargs['debug_info']))
    with pytest.raises(Statement_ImportError):
        StatementIBKR().load(data_path + 'ibkr_dividends_year2.xml')

    assert len(dumps) == 1
    assert 'TRSY' in dumps[0] and 'US1111111111' in dumps[0]   # the asset that could not be reconciled
    assert '136178726' in dumps[0]                             # the action the tax named
    assert 'U7654321F' not in dumps[0]                         # ... and never the account it belongs to
    assert 'U7654321' in dumps[0]                              # which is replaced by the placeholder
    assert 'balance="' not in dumps[0] or 'balance=""' in dumps[0]   # nor what the rest of the portfolio is worth


# A payment stored before the corporate action id was ever recorded carries none. Importing the same statement again
# once the id IS recorded must recognise that payment, not store a second copy of it beside the first.
def test_ibkr_a_payment_stored_without_an_action_id_is_not_imported_twice(tmp_path, project_root, data_path,
                                                                          prepare_db_taxes, monkeypatch):
    # Re-importing a period that is already covered is what the test is about, and that asks the user to confirm
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Yes)
    first = StatementIBKR()
    first.load(data_path + 'ibkr_dividends_year1.xml')
    first.match_db_ids()
    first.import_into_db()
    imported = [x for x in JalAccount.get_all_accounts() if x.number() == 'U7654321F'][0]
    payment = AssetPayment.get_list(imported.id())[0]
    JalDB._exec("UPDATE asset_payments SET number='' WHERE oid=:oid",   # as stored before this was recorded
                [(":oid", payment.oid())], commit=True)

    again = StatementIBKR()
    again.load(data_path + 'ibkr_dividends_year1.xml')
    again.match_db_ids()
    again.import_into_db()
    assert len(AssetPayment.get_list(imported.id())) == 1


# An ADR fee names the asset it was charged on and is stored as a fee of that asset; a fee that names none stays
# an ordinary spending
def test_ibkr_fee_charged_on_an_asset_is_imported_as_asset_fee(tmp_path, project_root, data_path, prepare_db_taxes):
    statement = StatementIBKR()
    statement.load(data_path + 'ibkr_adr_fee.xml')
    statement.match_db_ids()
    statement.import_into_db()

    imported = [x for x in JalAccount.get_all_accounts() if x.number() == 'U7654321'][0]
    fees = AssetPayment.get_list(imported.id(), subtype=AssetPayment.AssetFee)
    assert len(fees) == 1
    assert fees[0].amount() == Decimal('-4')
    assert fees[0].timestamp() == d2t(251111) + 20 * 3600 + 20 * 60
    assert fees[0].number() == '160219822'
    assert fees[0].note() == 'ERIC(294821608) ADR Fee USD 0.02 PER SHARE - FEE'
    assert fees[0].asset().name() == 'ERICSSON (LM) TEL-SP ADR'
    spendings = JalDB._read_to_list("SELECT amount, category_id, note FROM action_details")
    assert spendings == [['-0.01', PredefinedCategory.Fees, 'U******1:US CONSOLIDATED SNAPSHOT FOR OCT 2025']]

    # Both are costs of the same category and together they arrive at the ending cash of the statement
    Ledger().rebuild(from_timestamp=0)
    booked = JalDB._read_to_list("SELECT book_account, category_id, SUM(CAST(amount AS REAL)) FROM ledger "
                                 "WHERE category_id IS NOT NULL GROUP BY book_account, category_id")
    assert [(book, category, round(amount, 2)) for book, category, amount in booked] == [
        (BookAccount.Costs, PredefinedCategory.Fees, 4.01)]
    assert imported.get_asset_amount(d2t(260101), imported.currency()) == Decimal('-4.01')


# ----------------------------------------------------------------------------------------------------------------------
# A reversed dividend is dropped together with its reversal. The match is exact first, then ignoring the description,
# then ignoring the report date; a reversal that matches nothing stops the import
def test_ibkr_dividend_reversal_is_matched_in_three_ways():
    ibkr = StatementIBKR()
    paid = lambda symbol, description, reported: {
        'type': 'Dividends', 'account': 1, 'symbol': symbol, 'currency': 1, 'timestamp': 1720210800,
        'reported': reported, 'amount': Decimal('50'), 'action_id': str(symbol), 'description': description}
    reversed_ = lambda symbol, description, reported: {**paid(symbol, description, reported), 'amount': Decimal('-50')}
    kept = paid(14, 'KEPT CASH DIVIDEND', 1720137600)
    dividends = [
        paid(11, 'AAA CASH DIVIDEND', 1720137600), reversed_(11, 'AAA CASH DIVIDEND - REVERSAL', 1720137600),
        paid(12, 'BBB CASH DIVIDEND (Ordinary Dividend)', 1720137600), reversed_(12, 'CANCEL BBB CASH DIVIDEND', 1720137600),
        paid(13, 'CCC CASH DIVIDEND', 1720137600), reversed_(13, 'CCC CASH DIVIDEND - REVERSAL', 1725148800),
        kept]
    assert ibkr.aggregate_dividends(dividends) == [kept]

    with pytest.raises(Statement_ImportError):
        ibkr.aggregate_dividends([kept, reversed_(15, 'DDD CASH DIVIDEND - REVERSAL', 1720137600)])


# A dividend and its tax, both reversed two months later under another report date, leave nothing behind
def test_ibkr_reversed_dividend_takes_its_reversed_tax_with_it(tmp_path, project_root, data_path, prepare_db_taxes):
    statement = StatementIBKR()
    statement.load(data_path + 'ibkr_dividend_reversal.xml')
    assert statement._data[JSF.ASSET_PAYMENTS] == []


# ... and a tax that was not reversed with its dividend has no payment left to belong to, so the import is refused
def test_ibkr_tax_left_by_a_reversed_dividend_halts_the_import(tmp_path, project_root, data_path, prepare_db_taxes,
                                                               monkeypatch):
    monkeypatch.setattr(Statement, 'save_debug_info', lambda self, **kwargs: None)
    with open(data_path + 'ibkr_dividend_reversal.xml', 'r', encoding='utf-8') as xml_file:
        lines = xml_file.read().splitlines()
    tax_reversals = [x for x in lines if 'type="Withholding Tax"' in x and 'reportDate="20240901"' in x]
    assert len(tax_reversals) == 1
    without_tax_reversal = tmp_path / 'tax_not_reversed.xml'
    without_tax_reversal.write_text('\n'.join(x for x in lines if x not in tax_reversals), encoding='utf-8')

    statement = StatementIBKR()
    with pytest.raises(Statement_ImportError, match="withholding tax matches no payment"):
        statement.load(str(without_tax_reversal))
