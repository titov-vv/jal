import json
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from data_import.broker_statements.ibkr import StatementIBKR
from jal.data_import.statement import FOF
from tests.helpers import d2t
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.asset import JalAsset, AssetData
from jal.constants import PredefinedAsset, BookAccount, AssetId


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
        {'id': 1, 'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'country_id': 0, 'base_asset': '',
         'ID': {AssetId.ISO4217_CODE: 'RUB'},
         'symbols': [{'symbol': 'RUB', 'description': 'Российский Рубль', 'active': 1, 'currency_id': '', 'quote_source': -1}]},
        {'id': 2, 'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'country_id': 0, 'base_asset': '',
         'ID': {AssetId.ISO4217_CODE: 'USD'},
         'symbols': [{'symbol': 'USD', 'description': 'Доллар США', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 3, 'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'country_id': 0, 'base_asset': '',
         'ID': {AssetId.ISO4217_CODE: 'EUR'},
         'symbols': [{'symbol': 'EUR', 'description': 'Евро', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 4, 'type_id': PredefinedAsset.Stock, 'full_name': 'PACIFIC ETHANOL INC', 'country_id': 0, 'base_asset': '',
         'ID': {AssetId.ISIN: 'US69423U3059', AssetId.REG_CODE: '69423U305'},
         'symbols': [{'symbol': 'PEIX', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}]},
        {'id': 5, 'type_id': PredefinedAsset.Derivative, 'full_name': 'FANG 21JAN22 40.0 C', 'country_id': 0, 'base_asset': '',
         'ID': {},
         'symbols': [{'symbol': 'FANG  220121C00040000', 'description': 'CBOE', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.ExpiryDate: str(d2t(220121))}},
        {'id': 6, 'type_id': PredefinedAsset.Stock, 'full_name': 'EXXON MOBIL CORP', 'country_id': 2, 'base_asset': '',
         'ID': {AssetId.ISIN: 'US30231G1022', AssetId.REG_CODE: '30231G102'},
         'symbols': [{'symbol': 'XOM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}]},
        {'id': 7, 'type_id': PredefinedAsset.Derivative, 'full_name': 'XOM 21JAN22 42.5 C', 'country_id': 0, 'base_asset': '',
         'ID': {},
         'symbols': [{'symbol': 'XOM   220121C00042500', 'description': 'CBOE', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.ExpiryDate: str(d2t(220121))}},
        {'id': 8, 'type_id': PredefinedAsset.Stock, 'full_name': 'AURORA CANNABIS INC', 'country_id': 0, 'base_asset': '',
         'ID': {AssetId.REG_CODE: '05156X108'},
         'symbols': [{'symbol': 'ACB', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}]},
        {'id': 9, 'type_id': PredefinedAsset.Stock, 'full_name': 'TWO HARBORS INVESTMENT CORP', 'country_id': 2, 'base_asset': '',
         'ID': {AssetId.ISIN: 'US90187B4086', AssetId.REG_CODE: '90187B408'},
         'symbols': [{'symbol': 'TWO', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}]},
        {'id': 10, 'type_id': PredefinedAsset.Stock, 'full_name': 'NEW RESIDENTIAL INVESTMENT', 'country_id': 2, 'base_asset': '',
         'ID': {AssetId.ISIN: 'US64828T2015', AssetId.REG_CODE: '64828T201'},
         'symbols': [{'symbol': 'NRZ', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}]},
        {'id': 11, 'type_id': PredefinedAsset.Stock, 'full_name': 'INTERACTIVE BROKERS GRO-CL A', 'country_id': 0, 'base_asset': '',
         'ID': {AssetId.ISIN: 'US45841N1072', AssetId.REG_CODE: '45841N107'},
         'symbols': [{'symbol': 'IBKR', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}]},
        {'id': 12, 'type_id': PredefinedAsset.Stock, 'full_name': 'VERB TECHNOLOGY CO INC', 'country_id': 0, 'base_asset': '',
         'ID': {AssetId.ISIN: 'US92337U1043', AssetId.REG_CODE: '92337U104'},
         'symbols': [{'symbol': 'VERB', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}]}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets

    # validate trades
    test_trades = [
        [1, 3, 1573716263, 1574035200, '2608038423', 1, 8, '150.0', '3.46', '1.0', ''],
        [2, 3, 1604926434, 1604966400, '3210359211', 1, 5, '-300.0', '5.5', '0.953865', ''],
        [3, 3, 1606471692, 1606780800, '3256333343', 1, 4, '70.0', '6.898', '0.36425725', ''],
        [4, 3, 1606821387, 1606953600, '3264444280', 1, 4, '70.0', '6.08', '0.32925725', ''],
        [5, 3, 1607095765, 1607299200, '3276656996', 1, 7, '-100.0', '5.2', '0.667292', '']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade

    # validate dividend & tax
    test_dividends = [
        [1, 2, 1592770800, 0, '', 1, 1, 6, '16.76', '1.68', 'XOM (US30231G1022) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [2, 2, 1596054000, 0, '', 1, 1, 9, '51.0', '5.1', 'TWO(US90187B4086) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)'],
        [3, 2, 1588191600, 0, '', 1, 1, 10, '25.0', '2.5', 'NRZ(US64828T2015) CASH DIVIDEND USD 0.25 PER SHARE (Ordinary Dividend)']
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
        {'id': 1, 'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'RUB', 'description': 'Российский Рубль', 'active': 1, 'currency_id': '', 'quote_source': -1}]},
        {'id': 2, 'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'USD', 'description': 'Доллар США', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 3, 'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'EUR', 'description': 'Евро', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 4, 'type_id': PredefinedAsset.Stock, 'full_name': 'PACIFIC ETHANOL INC', 'isin': 'US69423U3059', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'PEIX', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '69423U305'}},
        {'id': 5, 'type_id': PredefinedAsset.Derivative, 'full_name': 'FANG 21JAN22 40.0 C', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'FANG  220121C00040000', 'description': 'CBOE', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.ExpiryDate: str(d2t(220121))}},
        {'id': 6, 'type_id': PredefinedAsset.Stock, 'full_name': 'EXXON MOBIL CORP', 'isin': 'US30231G1022', 'country_id': 2, 'base_asset': '',
         'symbols': [{'symbol': 'XOM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '30231G102'}},
        {'id': 7, 'type_id': PredefinedAsset.Derivative, 'full_name': 'XOM 21JAN22 42.5 C', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'XOM   220121C00042500', 'description': 'CBOE', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.ExpiryDate: str(d2t(220121))}},
        {'id': 8, 'type_id': PredefinedAsset.Stock, 'full_name': 'AURORA CANNABIS INC', 'isin': 'CA05156X1087', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'ACB', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '05156X108'}},
        {'id': 9, 'type_id': PredefinedAsset.Stock, 'full_name': 'TWO HARBORS INVESTMENT CORP', 'isin': 'US90187B4086', 'country_id': 2, 'base_asset': '',
         'symbols': [{'symbol': 'TWO', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '90187B408'}},
        {'id': 10, 'type_id': PredefinedAsset.Stock, 'full_name': 'NEW RESIDENTIAL INVESTMENT', 'isin': 'US64828T2015', 'country_id': 2, 'base_asset': '',
         'symbols': [{'symbol': 'NRZ', 'description': 'NYSE', 'active': 0, 'currency_id': 2, 'quote_source': 2},
                     {'symbol': 'RITM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '64828T201'}},
        {'id': 11, 'type_id': PredefinedAsset.Stock, 'full_name': 'INTERACTIVE BROKERS GRO-CL A', 'isin': 'US45841N1072', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'IBKR', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '45841N107'}},
        {'id': 12, 'type_id': PredefinedAsset.Stock, 'full_name': 'VERB TECHNOLOGY CO INC', 'isin': 'US92337U1043', 'country_id': 0, 'base_asset': '',
            'symbols': [{'symbol': 'VERB', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
            'data': {1: '92337U104'}},
        {'id': 13, 'type_id': PredefinedAsset.Stock, 'full_name': 'ALTO INGREDIENTS INC', 'isin': 'US0215131063', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'ALTO', 'description': 'NASDAQ', 'active': 0, 'currency_id': 2, 'quote_source': 2},
                     {'symbol': 'PEIX', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '021513106'}},
        {'id': 14, 'type_id': PredefinedAsset.Stock, 'full_name': 'AURORA CANNABIS INC', 'isin': 'CA05156X8843', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'ACB', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '05156X884'}},
        {'id': 15, 'type_id': PredefinedAsset.Stock, 'full_name': 'VERB TECHNOLOGY CO INC', 'isin': 'US92337U2033', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VERB', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '92337U203'}},
        {'id': 16, 'type_id': PredefinedAsset.Stock, 'full_name': 'VERB TECHNOLOGY CO INC', 'isin': 'US92337U3023', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VERB', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '92337U302'}},
        {'id': 17,  'type_id': PredefinedAsset.Stock, 'full_name': 'VOLCON INC', 'isin': 'US92864V4005', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VLCN', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '92864V400'}},
        {'id': 18, 'type_id': PredefinedAsset.Stock, 'full_name': 'VOLCON INC', 'isin': 'US92864V2025', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VLCN', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '92864V202'}},
        {'id': 19, 'type_id': PredefinedAsset.Stock, 'full_name': 'VOLCON INC', 'isin': 'US92864V3015', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VLCN', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {1: '92864V301'}}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets

    # validate trades
    test_trades = [
        [1, 3, 1573716263, 1574035200, '2608038423', 1, 8, '150.0', '3.46', '1.0', ''],
        [2, 3, 1604926434, 1604966400, '3210359211', 1, 5, '-300.0', '5.5', '0.953865', ''],
        [3, 3, 1606471692, 1606780800, '3256333343', 1, 4, '70.0', '6.898', '0.36425725', ''],
        [4, 3, 1606821387, 1606953600, '3264444280', 1, 4, '70.0', '6.08', '0.32925725', ''],
        [5, 3, 1607095765, 1607299200, '3276656996', 1, 7, '-100.0', '5.2', '0.667292', ''],
        [6, 3, 1610625615, 1611014400, '3381623127', 1, 13, '-70.0', '7.42', '0.23706599', ''],
        [7, 3, 1612871230, 1613001600, '3480222427', 1, 13, '-70.0', '7.71', '0.23751462', ''],
        [8, 3, 1620750000, 1620864000, '3764387743', 1, 6, '-100.0', '42.5', '0.033575', 'Option assignment/exercise'],
        [9, 3, 1620750000, 1620777600, '3764387737', 1, 7, '100.0', '0.0', '0.0', 'Option assignment'],
        [10, 3, 1623247000, 1623283200, '3836250920', 1, 5, '300.0', '50.8', '-0.1266', '']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade

    # validate dividend & tax
    test_dividends = [
        [1, 2, 1592770800, 0, '', 1, 1, 6, '16.76', '0.21', 'XOM (US30231G1022) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [2, 2, 1596054000, 0, '', 1, 1, 9, '51.0', '0.01', 'TWO(US90187B4086) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)'],
        [3, 2, 1588191600, 0, '', 1, 1, 10, '25.0', '1.04', 'NRZ(US64828T2015) CASH DIVIDEND USD 0.25 PER SHARE (Ordinary Dividend)'],
        [4, 2, 1659484800, 0, '', 4, 1, 11, '0.3052', '0', 'Stock Award Vesting']
    ]
    payments = JalAccount(1).dump_asset_payments()
    assert len(payments) == len(test_dividends)
    for i, payment in enumerate(test_dividends):
        assert payments[i] == payment

    # validate corp actions
    test_asset_actions = [
        [1, 5, 1610569500, '14909999818', 1, 3, 4, '140.0', 'PEIX(US69423U3059) CUSIP/ISIN CHANGE TO (US0215131063) (PEIX, ALTO INGREDIENTS INC, US0215131063)',
         [1, 1, 13, '140.0', '1.0']],
        [2, 5, 1588969500, '12693114547', 1, 4, 8, '150.0', 'ACB(CA05156X1087) SPLIT 1 FOR 12 (ACB, AURORA CANNABIS INC, CA05156X8843)',
         [2, 2, 14, '12.5', '1.0']]
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
# Warnings are expected for this test:
# Payment was reversed by approximate description: 30/06/2022 20:20:00, 'BEP(BMG162581083) CASH DIVIDEND USD 0.0161 PER SHARE (Ordinary Dividend)': 12.15
# Payment was reversed by approximate description: 30/06/2022 20:20:00, 'BEP(BMG162581083) CASH DIVIDEND USD 0.0161 PER SHARE (Bonus Dividend)': 0.65
# Payment was reversed by approximate description: 30/06/2022 20:20:00, 'BEP(BMG162581083) CASH DIVIDEND USD 0.0161 PER SHARE (Ordinary Dividend)': 12.15
# Payment was reversed by approximate description: 30/06/2022 20:20:00, 'BEP(BMG162581083) CASH DIVIDEND USD 0.30371 PER SHARE (Ordinary Dividend)': 0.64
# Payment was reversed with different reported date: 17/07/2020 20:20:00, 'TEF (US8793822086) STOCK DIVIDEND US8793822086 416666667 FOR 10000000000 (Ordinary Dividend)': 3.69
def test_ibkr_dividends(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_dividends.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_dividends.xml')
    assert IBKR._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_corp_actions(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_corp_actions.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_corp_actions.xml')
    assert IBKR._data == statement


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_q1_tax_correction_does_not_match_future_dividend():
    # The DB already contains a later dividend with the same previous tax amount.
    # A Q1 correction for February must not be attached to that future dividend.
    ibkr = StatementIBKR()
    ibkr._data = {
        FOF.ASSET_PAYMENTS: [
            {'id': 1, 'type': FOF.PAYMENT_DIVIDEND, 'account': 1, 'asset': 95, 'timestamp': d2t(250214),
             'amount': 13.73, 'tax': 0.79, 'description': 'O(US7561091049) CASH DIVIDEND USD 0.264 PER SHARE (Ordinary Dividend)'},
            {'id': 2, 'type': FOF.PAYMENT_DIVIDEND, 'account': 1, 'asset': 95, 'timestamp': d2t(250314),
             'amount': 13.94, 'tax': 4.12, 'description': 'O(US7561091049) CASH DIVIDEND USD 0.268 PER SHARE (Ordinary Dividend)'},
        ]
    }
    ibkr._map_db_account = lambda _: 0
    ibkr._map_db_asset = lambda _: 0

    dividend = ibkr.find_dividend4tax(
        d2t(250214),
        1,
        95,
        Decimal('4.12'),
        Decimal('0'),
        'O(US7561091049) CASH DIVIDEND USD 0.264 PER SHARE',
    )

    assert dividend is None


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_merger_with_prefixed_old_symbol_pairs_correctly():
    ibkr = StatementIBKR()
    ibkr._data = {FOF.CORP_ACTIONS: []}
    ibkr.locate_asset = lambda symbol, isin: {
        ('BGTK', 'US34520J2078'): 28,
    }.get((symbol, isin))

    action = {
        'type': 'merger',
        'account': 1,
        'asset': 29,
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
        'asset': 28,
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
    assert len(ibkr._data[FOF.CORP_ACTIONS]) == 1
    merger = ibkr._data[FOF.CORP_ACTIONS][0]
    assert merger['asset'] == 28
    assert merger['quantity'] == 10000.0
    assert merger['outcome'] == [{'asset': 29, 'quantity': 10000.0, 'share': 0.0}]


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_split_with_prefixed_parenthetical_symbol_pairs_correctly():
    ibkr = StatementIBKR()
    ibkr._data = {FOF.CORP_ACTIONS: []}
    ibkr.locate_asset = lambda symbol, isin: {
        ('VYNE', 'US92941V2097'): 171,
    }.get((symbol, isin))

    action = {
        'type': 'split',
        'account': 1,
        'asset': 170,
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
        'asset': 171,
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
    assert len(ibkr._data[FOF.CORP_ACTIONS]) == 1
    split = ibkr._data[FOF.CORP_ACTIONS][0]
    assert split['asset'] == 171
    assert split['quantity'] == 12.5
    assert split['outcome'] == [{'asset': 170, 'quantity': 0.6944, 'share': 1.0}]


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_find_db_stock_dividend_for_tax_correction(monkeypatch):
    class DummyDividend:
        def oid(self):
            return 332

        def timestamp(self):
            return 1672258800

        def number(self):
            return '22598209889'

        def amount(self):
            return 0.2776

        def tax(self):
            return 0.48

        def note(self):
            return 'BCV (US0596951063) STOCK DIVIDEND US0596951063 18507808 FOR 1000000000'

    def fake_get_list(account, asset, subtype):
        if subtype == 3:
            return [DummyDividend()]
        return []

    monkeypatch.setattr('data_import.broker_statements.ibkr.AssetPayment.get_list', fake_get_list)

    ibkr = StatementIBKR()
    ibkr._data = {FOF.ASSET_PAYMENTS: []}
    ibkr._map_db_account = lambda _: 1
    ibkr._map_db_asset = lambda _: 294

    dividend = ibkr.find_dividend4tax(
        1672258800,
        1,
        294,
        Decimal('0.48'),
        Decimal('0'),
        'BCV (US0596951063) STOCK DIVIDEND US0596951063 18507808 FOR 1000000000',
    )

    assert dividend is not None
    assert dividend['id'] == -332


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_mlp_extra_tax_reported_separately_is_saved_as_fee():
    ibkr = StatementIBKR()
    ibkr._data = {
        FOF.ASSET_PAYMENTS: [
            {'id': 1, 'type': FOF.PAYMENT_DIVIDEND, 'account': 1, 'asset': 161, 'timestamp': 1699042800,
             'amount': 5.25, 'tax': 1.94, 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE (Ordinary Dividend)'},
        ],
        FOF.ASSETS: [{'id': 161, 'type': FOF.ASSET_MLP}],
    }
    ibkr._map_db_account = lambda _: 0
    ibkr._map_db_asset = lambda _: 0

    taxes = [
        {'id': 10, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'asset': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1709078400, 'amount': 1.94, 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
        {'id': 11, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'asset': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1709078400, 'amount': -1.94, 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
        {'id': 12, 'type': 'Withholding Tax', 'source': 'CASH', 'account': 1, 'asset': 161, 'currency': 1, 'timestamp': 1699042800,
         'reported': 1724803200, 'amount': -0.53, 'description': 'USAC(US90290N1090) CASH DIVIDEND USD 0.525 PER SHARE - US TAX'},
    ]

    aggregated = ibkr.aggregate_taxes(taxes)

    assert [tax['amount'] for tax in aggregated] == [-1.94, 1.94]
    extra_fees = [x for x in ibkr._data[FOF.ASSET_PAYMENTS] if x['type'] == FOF.PAYMENT_FEE]
    assert len(extra_fees) == 1
    assert extra_fees[0]['amount'] == -0.53
    assert extra_fees[0]['description'].endswith(' - Extra 10% tax due to IRS section 1446')


# ----------------------------------------------------------------------------------------------------------------------
def test_ibkr_spinoff_allows_fractional_entitlement_rounding():
    ibkr = StatementIBKR()
    ibkr._data = {
        FOF.ASSETS: [
            {'id': 1, 'symbol': 'SVAC', 'isin': 'US85521J1097'},
            {'id': 2, 'symbol': 'CYXTW', 'isin': 'US23284C1100'},
        ],
        FOF.CORP_ACTIONS: [],
    }

    action = {
        'type': 'spin-off',
        'account': 1,
        'asset': 2,
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
    assert ibkr._data[FOF.CORP_ACTIONS][0]['asset'] == 1
    assert ibkr._data[FOF.CORP_ACTIONS][0]['quantity'] == 50
