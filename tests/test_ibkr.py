import json
from decimal import Decimal

import pytest

from PySide6.QtWidgets import QMessageBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from data_import.broker_statements.ibkr import StatementIBKR
from jal.data_import.statement import JSF, Statement, Statement_ImportError
from tests.helpers import d2t
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset, AssetData
from jal.db.db import JalDB
from jal.db.operations import AssetPayment
from jal.constants import PredefinedAsset, BookAccount, SymbolId, AssetLocation


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
        [1, 3, 1573734263, 1574035200, '2608038423', 1, 8, '150.0', '3.46', '1.0', ''],
        [2, 3, 1604944434, 1604966400, '3210359211', 1, 5, '-300.0', '5.5', '0.953865', ''],
        [3, 3, 1606489692, 1606780800, '3256333343', 1, 4, '70.0', '6.898', '0.36425725', ''],
        [4, 3, 1606839387, 1606953600, '3264444280', 1, 4, '70.0', '6.08', '0.32925725', ''],
        [5, 3, 1607113765, 1607299200, '3276656996', 1, 7, '-100.0', '5.2', '0.667292', '']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade

    # validate dividend & tax
    test_dividends = [
        [1, 2, 1592770800, 1, 0, '', 1, 1, 6, '16.76', '1.68', '', 'XOM (US30231G1022) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [2, 2, 1596054000, 1, 0, '', 1, 1, 9, '51.0', '5.1', '', 'TWO(US90187B4086) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)'],
        [3, 2, 1588191600, 1, 0, '', 1, 1, 10, '25.0', '2.5', '', 'NRZ(US64828T2015) CASH DIVIDEND USD 0.25 PER SHARE (Ordinary Dividend)']
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
        [1, 3, 1573734263, 1574035200, '2608038423', 1, 8, '150.0', '3.46', '1.0', ''],
        [2, 3, 1604944434, 1604966400, '3210359211', 1, 5, '-300.0', '5.5', '0.953865', ''],
        [3, 3, 1606489692, 1606780800, '3256333343', 1, 4, '70.0', '6.898', '0.36425725', ''],
        [4, 3, 1606839387, 1606953600, '3264444280', 1, 4, '70.0', '6.08', '0.32925725', ''],
        [5, 3, 1607113765, 1607299200, '3276656996', 1, 7, '-100.0', '5.2', '0.667292', ''],
        [6, 3, 1610643615, 1611014400, '3381623127', 1, 21, '-70.0', '7.42', '0.23706599', ''],
        [7, 3, 1612889230, 1613001600, '3480222427', 1, 13, '-70.0', '7.71', '0.23751462', ''],
        [8, 3, 1620764400, 1620864000, '3764387743', 1, 6, '-100.0', '42.5', '0.033575', 'Option assignment/exercise'],
        [9, 3, 1620764400, 1620777600, '3764387737', 1, 7, '100.0', '0.0', '0.0', 'Option assignment'],
        [10, 3, 1623261400, 1623283200, '3836250920', 1, 5, '300.0', '50.8', '-0.1266', '']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade

    # validate dividend & tax
    test_dividends = [
        [1, 2, 1592770800, 1, 0, '', 1, 1, 6, '16.76', '0.21', '', 'XOM (US30231G1022) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [2, 2, 1596054000, 1, 0, '', 1, 1, 9, '51.0', '0.01', '', 'TWO(US90187B4086) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)'],
        [3, 2, 1588191600, 1, 0, '', 1, 1, 10, '25.0', '1.04', '', 'NRZ(US64828T2015) CASH DIVIDEND USD 0.25 PER SHARE (Ordinary Dividend)'],
        [4, 2, 1659484800, 0, 0, '', 4, 1, 11, '0.3052', '0', '59.21', 'Stock Award Vesting']
    ]
    payments = JalAccount(1).dump_asset_payments()
    assert len(payments) == len(test_dividends)
    for i, payment in enumerate(test_dividends):
        assert payments[i] == payment

    # validate corp actions
    test_asset_actions = [
        [1, 5, 1588969500, 1, '12693114547', 1, 4, 8, '150.0', 'ACB(CA05156X1087) SPLIT 1 FOR 12 (ACB, AURORA CANNABIS INC, CA05156X8843)',
         [1, 1, 14, '12.5', '1.0']],
        [2, 5, 1610569500, 1, '14909999818', 1, 3, 4, '140.0', 'PEIX(US69423U3059) CUSIP/ISIN CHANGE TO (US0215131063) (PEIX, ALTO INGREDIENTS INC, US0215131063)',
         [2, 2, 21, '140.0', '1.0']]
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
def test_ibkr_cfd(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_cfd.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_cfd.xml')
    assert IBKR._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_corp_actions(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_corp_actions.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)

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
             'amount': 13.73, 'tax': 0.79, 'description': 'O(US7561091049) CASH DIVIDEND USD 0.264 PER SHARE (Ordinary Dividend)'},
            {'id': 2, 'type': JSF.PAYMENT_DIVIDEND, 'account': 1, 'symbol': 95, 'timestamp': d2t(250314),
             'amount': 13.94, 'tax': 4.12, 'description': 'O(US7561091049) CASH DIVIDEND USD 0.268 PER SHARE (Ordinary Dividend)'},
        ],
        JSF.ASSETS: [{'id': 1, JSF.SYMBOLS: [{'id': 95, 'symbol': 'O', 'isin': 'US7561091049'}]}]
    }
    ibkr._map_db_account = lambda _: 0
    ibkr._map_db_asset_by_symbol = lambda _: 0

    tax = {'account': 1, 'symbol': 95, 'timestamp': d2t(250301), 'reported': d2t(250301), 'amount': 4.12,
           'action_id': '', 'description': 'O(US7561091049) CASH DIVIDEND USD 0.264 PER SHARE - US TAX'}
    with pytest.raises(Statement_ImportError):
        ibkr.find_dividend4tax(tax)


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_merger_with_prefixed_old_symbol_pairs_correctly():
    ibkr = StatementIBKR()
    ibkr._data = {JSF.CORP_ACTIONS: []}
    ibkr.locate_symbol = lambda symbol, isin: {
        ('BGTK', 'US34520J2078'): 28,
    }.get((symbol, isin))

    action = {
        'type': 'merger',
        'account': 1,
        'symbol': 29,
        'asset_type': 'stock',
        'timestamp': 1646857500,
        'number': '19750736274',
        'description': '20220309164306BGTK(US34520J2078) MERGED(Acquisition) WITH US0896931054 1 FOR 1 (BGTK, BIG TOKEN INC, US0896931054)',
        'quantity': 10000.0,
        'value': 24.0,
        'proceeds': 0.0,
        'code': '',
        'jal_processed': False,
    }
    parts_b = [{
        'type': 'merger',
        'account': 1,
        'symbol': 28,
        'asset_type': 'stock',
        'timestamp': 1646857500,
        'number': '19750736269',
        'description': '20220309164306BGTK(US34520J2078) MERGED(Acquisition) WITH US0896931054 1 FOR 1 (BGTK.OLD, FORCE PROTECTION VIDEO EQUIP, US34520J2078)',
        'quantity': -10000.0,
        'value': -20.0,
        'proceeds': 0.0,
        'code': '',
        'jal_processed': False,
    }]

    loaded = ibkr.load_merger(action, parts_b)

    assert loaded == 2
    assert parts_b[0]['jal_processed'] is True
    assert len(ibkr._data[JSF.CORP_ACTIONS]) == 1
    merger = ibkr._data[JSF.CORP_ACTIONS][0]
    assert merger['symbol'] == 28
    assert merger['quantity'] == 10000.0
    assert merger['outcome'] == [{'symbol': 29, 'quantity': 10000.0, 'share': 0.0}]


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_split_with_prefixed_parenthetical_symbol_pairs_correctly():
    ibkr = StatementIBKR()
    ibkr._data = {JSF.CORP_ACTIONS: []}
    ibkr.locate_symbol = lambda symbol, isin: {
        ('VYNE', 'US92941V2097'): 171,
    }.get((symbol, isin))

    action = {
        'type': 'split',
        'account': 1,
        'symbol': 170,
        'asset_type': 'stock',
        'timestamp': 1676060700,
        'number': '23018699773',
        'description': 'VYNE(US92941V2097) SPLIT 1 FOR 18 (VYNE, VYNE THERAPEUTICS INC, US92941V3087)',
        'quantity': 0.6944,
        'value': 0.0,
        'proceeds': 0.0,
        'code': '',
        'jal_processed': False,
    }
    parts_b = [{
        'type': 'split',
        'account': 1,
        'symbol': 171,
        'asset_type': 'stock',
        'timestamp': 1676060700,
        'number': '23018699768',
        'description': 'VYNE(US92941V2097) SPLIT 1 FOR 18 (20230213002014VYNE, VYNE THERAPEUTICS INC, US92941V2097)',
        'quantity': -12.5,
        'value': 0.0,
        'proceeds': 0.0,
        'code': '',
        'jal_processed': False,
    }]

    loaded = ibkr.load_split(action, parts_b)

    assert loaded == 2
    assert parts_b[0]['jal_processed'] is True
    assert len(ibkr._data[JSF.CORP_ACTIONS]) == 1
    split = ibkr._data[JSF.CORP_ACTIONS][0]
    assert split['symbol'] == 171
    assert split['quantity'] == 12.5
    assert split['outcome'] == [{'symbol': 170, 'quantity': 0.6944, 'share': 1.0}]


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_find_db_stock_dividend_for_tax_correction(prepare_db, monkeypatch):
    # The payment a correction belongs to is usually not in the statement that carries the correction - it was
    # stored a year earlier - so a stored payment has to be a candidate like any other, and is pulled into the
    # statement under an id of its own when it wins.
    class StoredPayment:
        def oid(self): return 332
        def timestamp(self): return 1672258800
        def number(self): return '22598209889'          # the corporate action it was stored under
        def amount(self): return 0.2776
        def tax(self): return 0.48
        def note(self): return 'BCV (US0596951063) STOCK DIVIDEND US0596951063 18507808 FOR 1000000000'

    monkeypatch.setattr('data_import.broker_statements.ibkr.AssetPayment.get_list',
                        lambda account, asset, subtype: [StoredPayment()] if subtype == 3 else [])

    ibkr = StatementIBKR()
    ibkr._data = {JSF.ASSET_PAYMENTS: [],
                  JSF.ASSETS: [{'id': 1, JSF.SYMBOLS: [{'id': 294, 'symbol': 'BCV', 'isin': 'US0596951063'}]}]}
    ibkr._map_db_account = lambda _: 1
    ibkr._map_db_asset_by_symbol = lambda _: 294

    tax = {'account': 1, 'symbol': 294, 'timestamp': 1672258800, 'reported': 1672258800, 'amount': 0.48,
           'action_id': '22598209889',
           'description': 'BCV (US0596951063) STOCK DIVIDEND US0596951063 18507808 FOR 1000000000 - CH TAX'}
    dividend = ibkr.find_dividend4tax(tax)

    assert dividend is not None
    assert dividend['id'] == 1   # first free statement payment id, reserved for the db record
    assert ibkr._id_map[JSF.ASSET_PAYMENTS] == {1: 332}


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_mlp_extra_tax_reported_separately_is_saved_as_fee():
    ibkr = StatementIBKR()
    ibkr._data = {
        JSF.ASSET_PAYMENTS: [
            {'id': 1, 'type': JSF.PAYMENT_DIVIDEND, 'account': 1, 'symbol': 161, 'timestamp': 1699042800,
             'amount': 5.25, 'tax': 1.94, 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE (Ordinary Dividend)'},
        ],
        JSF.ASSETS: [{'id': 61, 'type': JSF.ASSET_MLP, JSF.SYMBOLS: [{'id': 161, 'symbol': 'USAC'}]}],
    }
    ibkr._map_db_account = lambda _: 0
    ibkr._map_db_asset_by_symbol = lambda _: 0

    taxes = [
        {'id': 10, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'symbol': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1709078400, 'amount': 1.94, 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
        {'id': 11, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'symbol': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1709078400, 'amount': -1.94, 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
        {'id': 12, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'symbol': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1724803200, 'amount': -0.53, 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
    ]

    aggregated = ibkr.aggregate_taxes(taxes)

    assert [tax['amount'] for tax in aggregated] == [-1.94, 1.94]
    extra_fees = [x for x in ibkr._data[JSF.ASSET_PAYMENTS] if x['type'] == JSF.PAYMENT_FEE]
    assert len(extra_fees) == 1
    assert extra_fees[0]['amount'] == -0.53
    assert extra_fees[0]['description'].endswith(' - Extra 10% tax due to IRS section 1446')


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
        'quantity': 17.0,
        'value': 30.77,
        'proceeds': 0.0,
        'code': '',
        'jal_processed': False
    }

    assert ibkr.load_spinoff(action, None) == 1
    assert ibkr._data[JSF.CORP_ACTIONS][0]['symbol'] == 11
    assert ibkr._data[JSF.CORP_ACTIONS][0]['quantity'] == 50


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
