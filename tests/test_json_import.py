import json
from decimal import Decimal
from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr, prepare_db_moex

from jal.data_import.statement import Statement
from tests.helpers import d2t
from jal.constants import PredefinedAsset
from jal.db.account import JalAccount
from jal.db.asset import JalAsset, AssetData
from jal.db.peer import JalPeer


def test_ibkr_json_import(tmp_path, project_root, data_path, prepare_db_ibkr):
    statement = Statement()
    statement.load(data_path + 'ibkr.json')
    statement.validate_format()
    statement.match_db_ids()

    with open(data_path + 'matched.json', 'r', encoding='utf-8') as json_file:
        expected_result = json.load(json_file)

    assert statement._data == expected_result

    statement.import_into_db()

    # validate assets
    test_assets = [
        {'id': 1, 'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'RUB', 'description': 'Российский Рубль', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 2, 'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'USD', 'description': 'Доллар США', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 3, 'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'EUR', 'description': 'Евро', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 4, 'type_id': PredefinedAsset.ETF, 'full_name': 'Growth ETF', 'isin': 'US9229087369', 'country_id': 2, 'base_asset': '',
         'symbols': [{'symbol': 'VUG', 'description': 'ARCA', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '922908736'}},
        {'id': 5, 'type_id': PredefinedAsset.ETF, 'full_name': 'VANGUARD EXTENDED DUR TREAS', 'isin': '', 'country_id': 2, 'base_asset': '',
         'symbols': [{'symbol': 'EDV', 'description': 'ARCA', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '921910709'}},
        {'id': 6, 'type_id': PredefinedAsset.ETF, 'full_name': 'PIMCO 25+ YR ZERO CPN US TIF', 'isin': 'US72201R8824', 'country_id': 2, 'base_asset': '',
         'symbols': [{'symbol': 'ZROZ', 'description': 'ARCA', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '72201R882'}},
        {'id': 7, 'type_id': PredefinedAsset.Money, 'full_name': '', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'CAD', 'description': '', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 8, 'type_id': PredefinedAsset.Stock, 'full_name': 'AMAZON.COM INC', 'isin': 'US0231351067', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'AMZN', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '023135106'}},
        {'id': 9, 'type_id': PredefinedAsset.Stock, 'full_name': 'ALIBABA GROUP HOLDING-SP ADR', 'isin': 'US01609W1027', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'BABA', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '01609W102'}},
        {'id': 10, 'type_id': PredefinedAsset.Stock, 'full_name': 'DOMINION ENERGY INC', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'D', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '25746U109'}},
        {'id': 11, 'type_id': PredefinedAsset.Stock, 'full_name': 'DOMINION ENERGY MIDSTREAM PA', 'isin': '','country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'DM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '257454108'}},
        {'id': 12, 'type_id': PredefinedAsset.Bond, 'full_name': 'X 6 1/4 03/15/26', 'isin': 'US912909AN84', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'X 6 1/4 03/15/26', 'description': '', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.RegistrationCode: '912909AN8', AssetData.ExpiryDate: '1773532800', AssetData.PrincipalValue: '1000'}},
        {'id': 13, 'type_id': PredefinedAsset.Derivative, 'full_name': 'SPY 29MAY20 295.0 C', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'SPY   200529C00295000', 'description': '', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.ExpiryDate: '1590710400'}},
        {'id': 14, 'type_id': PredefinedAsset.Derivative, 'full_name': 'DSKEW 27FEB22 11.5 C', 'isin': 'US23753F1158', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'DSKEW', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '23753F115', AssetData.ExpiryDate: '1645920000'}},
        {'id': 15, 'type_id': PredefinedAsset.Stock, 'full_name': 'MYLAN NV', 'isin': 'NL0011031208', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'MYL', 'description': '', 'active': 1, 'currency_id': 2, 'quote_source': -1}]},
        {'id': 16, 'type_id': PredefinedAsset.Stock, 'full_name': 'VIATRIS INC-W/I', 'isin': 'US92556V1061', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VTRS', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '92556V106'}},
        {'id': 17, 'type_id': PredefinedAsset.Stock, 'full_name': 'WABTEC CORP', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'WAB', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2},
                     {'symbol': 'WBB', 'description': 'TSE', 'active': 1, 'currency_id': 7, 'quote_source': 4}],
         'data': {AssetData.RegistrationCode: '929740108'}},
        {'id': 18, 'type_id': PredefinedAsset.Stock, 'full_name': 'TELEFONICA SA-SPON ADR', 'isin': 'US8793822086', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'TEF', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '879382208'}},
        {'id': 19, 'type_id': PredefinedAsset.Stock, 'full_name': 'EQM MIDSTREAM PARTNERS LP', 'isin': 'US26885B1008','country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'EQM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '26885B100'}},
        {'id': 20, 'type_id': PredefinedAsset.Stock, 'full_name': 'EQUITRANS MIDSTREAM CORP', 'isin': 'US2946001011', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'ETRN', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '294600101'}},
        {'id': 21, 'type_id': PredefinedAsset.Stock, 'full_name': 'GENERAL ELECTRIC CO', 'isin': 'US3696041033', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'GE', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '369604103'}},
        {'id': 22, 'type_id': PredefinedAsset.Stock, 'full_name': 'EWELLNESS HEALTHCARE CORP', 'isin': 'US30051D1063', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'EWLL', 'description': 'PINK', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.RegistrationCode: '30051D106'}},
        {'id': 23, 'type_id': PredefinedAsset.Stock, 'full_name': 'EWELLNESS HEALTHCARE CORP', 'isin': 'US30051D2053', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'EWLL', 'description': 'PINK', 'active': 0, 'currency_id': 2, 'quote_source': -1},
                     {'symbol': 'EWLLD', 'description': 'PINK', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.RegistrationCode: '30051D205'}},
        {'id': 24, 'type_id': PredefinedAsset.Stock, 'full_name': 'LIVONGO HEALTH INC', 'isin': 'US5391831030', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'LVGO', 'description': '', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.RegistrationCode: '539183103'}},
        {'id': 25, 'type_id': PredefinedAsset.Stock, 'full_name': 'TELADOC HEALTH INC', 'isin': 'US87918A1051', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'TDOC', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '87918A105'}},
        {'id': 26, 'type_id': PredefinedAsset.Stock, 'full_name': 'LUMEN TECHNOLOGIES INC', 'isin': 'US5502411037', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'LUMN', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '550241103'}},
        {'id': 27, 'type_id': PredefinedAsset.Stock, 'full_name': 'CENTURYLINK INC', 'isin': 'US1567001060', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'LUMN', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '156700106'}},
        {'id': 28, 'type_id': PredefinedAsset.Bond, 'full_name': 'X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26', 'isin': 'US912CALAN84', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26', 'description': '', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.RegistrationCode: '912CALAN8', AssetData.ExpiryDate: '1773532800', AssetData.PrincipalValue: '1000'}},
        {'id': 29, 'type_id': PredefinedAsset.Derivative, 'full_name': 'BKSY 30DEC24 11.5 C', 'isin': 'US68839R1207', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'SFTW WS', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '68839R120', AssetData.ExpiryDate: '1735516800'}},
        {'id': 30, 'type_id': PredefinedAsset.Derivative, 'full_name': 'BKSY 30DEC24 11.5 C', 'isin': 'US09263B1162', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'BKSY WS', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.ExpiryDate: '1735516800'}},
        {'id': 31, 'type_id': PredefinedAsset.Stock, 'full_name': 'APPLE INC', 'isin': 'US0378331005', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'AAPL', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '037833100'}},
        {'id': 32, 'type_id': PredefinedAsset.Derivative, 'full_name': 'VLO 24JUL20 64.0 P', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VLO   200724P00064000', 'description': 'CBOE', 'active': 1, 'currency_id': 2, 'quote_source': -1}]},
        {'id': 33, 'type_id': PredefinedAsset.Stock, 'full_name': 'VALERO ENERGY CORP', 'isin': 'US91913Y1001', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VLO', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '91913Y100'}},
        {'id': 34, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'US5543821012', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'MAC', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '554382101'}},
        {'id': 35, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'US3696043013', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'GE', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '369604301'}},
        {'id': 36, 'type_id': PredefinedAsset.Bond, 'full_name': '', 'isin': 'US345370CV02', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'F 8 1/2 04/21/23', 'description': '', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.RegistrationCode: '345370CV0'}},
        {'id': 37, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'CA1125851040', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'BAM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '112585104'}},
        {'id': 38, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'BMG1624R1079', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'BPYPM', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}]},
        {'id': 39, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'US11282X1037', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'BPYU', 'description': '', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.RegistrationCode: '11282X103'}},
        {'id': 40, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'US8713321029', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'SLVM', 'description': 'NYSE', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '871332102'}},
        {'id': 41, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'US2183521028', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'CORT', 'description': 'NASDAQ', 'active': 1, 'currency_id': 2, 'quote_source': 2}],
         'data': {AssetData.RegistrationCode: '218352102'}},
        {'id': 42, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'US218NSPODD6', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'CORT.OD2', 'description': 'CORPACT', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
         'data': {AssetData.RegistrationCode: '218NSPODD'}},
         {'id': 43, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'CA6295231014', 'country_id': 0, 'base_asset': '',
          'symbols': [{'symbol': 'NABIF', 'description': '', 'active': 1, 'currency_id': 2, 'quote_source': -1}],
          'data': {AssetData.RegistrationCode: '629523101'}}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets

    # validate accounts
    test_accounts = [
        {'id': 1, 'type_id': 4, 'name': 'Inv. Account', 'number': 'U7654321', 'currency_id': 2, 'active': 1, 'organization_id': 1, 'country_id': 0, 'reconciled_on': 0, 'precision': 10},
        {'id': 2, 'type_id': 4, 'name': 'Inv. Account.RUB', 'number': 'U7654321', 'currency_id': 1, 'active': 1, 'organization_id': 1, 'country_id': 0, 'reconciled_on': 0, 'precision': 10},
        {'id': 3, 'type_id': 4, 'name': 'TEST_ACC.USD', 'number': 'TEST_ACC', 'currency_id': 2, 'active': 1, 'organization_id': 2, 'country_id': 0, 'reconciled_on': 0, 'precision': 10},
        {'id': 4, 'type_id': 4, 'name': 'Inv. Account.CAD', 'number': 'U7654321', 'currency_id': 7, 'active': 1, 'organization_id': 1, 'country_id': 0, 'reconciled_on': 0, 'precision': 10},
        {'id': 5, 'type_id': 4, 'name': 'TEST_ACC.CAD', 'number': 'TEST_ACC', 'currency_id': 7, 'active': 1, 'organization_id': 2, 'country_id': 0, 'reconciled_on': 0, 'precision': 10},
        {'id': 6, 'type_id': 4, 'name': 'Inv. Account.EUR', 'number': 'U7654321', 'currency_id': 3, 'active': 1, 'organization_id': 1, 'country_id': 0, 'reconciled_on': 0, 'precision': 10}
    ]
    accounts = JalAccount.get_all_accounts()
    assert [x.dump() for x in accounts] == test_accounts

    # validate peers
    test_peers = [{'name': 'IB'}, {'name': 'Bank for account #TEST_ACC'}]
    peers = JalPeer.get_all_peers()
    assert [x.dump() for x in peers] == test_peers

    # validate income/spending
    assert JalAccount(1).dump_actions() == [
        [1, 1, 1578073286, 1, 1, '', '', [1, 1, 5, '', '-7.96', '0', 'BALANCE OF MONTHLY MINIMUM FEE FOR DEC 2019']],
        [2, 1, 1601462520, 1, 1, '', '', [2, 2, 5, '', '0.6905565', '0', 'COMMISS COMPUTED AFTER TRADE REPORTED (EWLL)']],
        [4, 1, 1549843200, 1, 1, '', '', [4, 4, 6, '', '-0.249018', '0', 'BABA (ALIBABA GROUP HOLDING-SP ADR) - French Transaction Tax']]
    ]
    assert JalAccount(2).dump_actions() == [
        [3, 1, 1591142400, 2, 1, '', '', [3, 3, 8, '', '0.5', '0', 'RUB CREDIT INT FOR MAY-2020']]
    ]

    # validate transfers
    assert JalAccount(1).dump_transfers() == [
        [1, 4, 1580443370, 6, '890.47', 1580443370, 1, '1000.0', 1, '3.0', '2674343226', '', 'IDEALFX'],
        [2, 4, 1581322108, 2, '78986.6741', 1581322108, 1, '1234.0', 1, '2.0', '2645393202', '', 'IDEALFX'],
        [3, 4, 1590522832, 2, '44.07', 1590522832, 1, '0.621778209', '', '', '2845906676', '', 'IDEALFX'],
        [4, 4, 1600374600, 1, '123456.78', 1600374600, 2, '123456.78', '', '', '13778635822', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS'],
        [5, 4, 1605744000, 1, '1234.0', 1605744000, 1, '1234.0', '', '', '14333901913', '', 'DISBURSEMENT INITIATED BY John Doe'],
        [6, 4, 1663372800, 1, '100.0', 1663372800, 1, '100.0', '', '', '1234567890', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS'],
        [7, 4, 1663372800, 1, '100.0', 1663372800, 1, '100.0', '', '', '1234567891', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS'],
        [8, 4, 1685702720, 3, '7.0', 1685702720, 1, '7.0', '', '', '24055511103', 8, 'INTERNAL TRANSFER (--)']
    ]

    # validate trades
    test_trades = [
        [1, 3, 1553545500, 1553545500, '', 1, 9, '-0.777', '168.37', '0.0', ''],
        [2, 3, 1579094694, 1579219200, '2661774904', 1, 22, '45000.0', '0.0012', '0.54', ''],
        [3, 3, 1580215513, 1580215513, '2674740000', 1, 4, '-1240.0', '54.84', '7.75519312', ''],
        [4, 3, 1580215566, 1580342400, '2674740000', 1, 31, '-148.0', '316.68', '-1.987792848', ''],
        [5, 3, 1590595065, 1590710400, '2882737839', 1, 12, '2.0', '637.09', '2.0', ''],
        [6, 3, 1592575273, 1592784000, '2931083780', 1, 32, '-100.0', '4.54', '1.1058334', ''],
        [7, 3, 1595607600, 1595808000, '2997636969', 1, 32, '100.0', '0.0', '0.0', 'Option assignment'],
        [8, 3, 1595607600, 1595607600, '2997636973', 1, 33, '100.0', '64.0', '0.0', 'Option assignment/exercise'],
        [9, 3, 1603882231, 1604016000, '3183801882', 1, 23, '500000.0', '0.0001', '0.7503675', ''],
        [10, 3, 1640895900, 1640895900, '18952523919', 1, 30, '-30.0', '0.1', '0.0', 'BKSY WS(US09263B1162) MERGED(Liquidation) FOR USD 0.10 PER SHARE (BKSY WS, BKSY 30OCT24 11.5 C, US09263B1162)'],
        [11, 3, 1638822300, 1638822300, '18694975077', 1, 36, '-8.0', '1103.06815', '0.0', '(US345370CV02) FULL CALL / EARLY REDEMPTION FOR USD 1.10306815 PER BOND (F 8 1/2 04/21/23, F 8 1/2 04/21/23, US345370CV02)'],
        [12, 3, 1640031900, 1640031900, '18882610202', 1, 42, '-99.0', '20.75', '0.0', 'CORT.OD2(US218NSPODD6) MERGED(Voluntary Offer Allocation) FOR USD 20.75 PER SHARE (CORT.OD2, CORCEPT THERAPEUTICS INC - TENDER ODD LOT, US218NSPODD6)']
    ]
    trades = JalAccount(1).dump_trades()
    assert len(trades) == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert trades[i] == trade

    # validate asset payments
    test_payments = [
        [1, 2, 1529612400, 0, '', 1, 1, 5, '16.76', '0', 'EDV (US9219107094) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [2, 2, 1533673200, 0, '', 1, 1, 5, '20.35', '0.54', 'EDV(US9219107094) CASH DIVIDEND 0.10175000 USD PER SHARE (Ordinary Dividend)'],
        [3, 2, 1633033200, 0, '16054321038', 3, 1, 4, '5.887', '15.0', 'VUG (US9229087369) Stock Dividend US9229087369 196232339 for 10000000000'],
        [4, 2, 1595017200, 0, '13259965038', 3, 1, 18, '3.0', '0', 'TEF (US8793822086) STOCK DIVIDEND US8793822086 416666667 FOR 10000000000'],
        [5, 2, 1591215600, 0, '12882908488', 3, 1, 34, '3.0', '0', 'MAC (US5543821012) CASH DIVIDEND USD 0.10, STOCK DIVIDEND US5543821012 548275673 FOR 10000000000'],
        [6, 2, 1578082800, 1577664000, '', 1, 1, 6, '60.2', '6.02', 'ZROZ(US72201R8824) CASH DIVIDEND USD 0.86 PER SHARE (Ordinary Dividend)'],
        [7, 2, 1633033200, 0, '', 1, 1, 4, '158.6', '15.86', 'VUG (US9229087369) CASH DIVIDEND USD 0.52 (Ordinary Dividend)'],
        [8, 2, 1590595065, 0, '2882737839', 2, 1, 12, '-25.69', '0', 'PURCHASE ACCRUED INT X 6 1/4 03/15/26'],
        [9, 2, 1600128000, 0, '', 2, 1, 12, '62.5', '0', 'BOND COUPON PAYMENT (X 6 1/4 03/15/26)'],
        [10, 2, 1620345600, 0, '', 4, 1, 8, '2.0', '0', 'Stock Award Grant for Cash Deposit']
    ]
    dividends = JalAccount(1).dump_dividends()
    assert len(dividends) == len(test_payments)
    for i, dividend in enumerate(test_payments):
        assert dividends[i] == dividend

    # Verify that asset prices were loaded for stock dividends and vestings
    assert JalAsset(1).quote(d2t(230101), 1) == (1672531200, Decimal('1'))
    assert JalAsset(4).quote(d2t(230101), 2) == (1633033200, Decimal('25.73'))
    assert JalAsset(18).quote(d2t(230101), 2) == (1595017200, Decimal('4.73'))
    assert JalAsset(34).quote(d2t(230101), 2) == (1591215600, Decimal('8.59'))
    assert JalAsset(8).quote(d2t(230101), 2) == (1620345600, Decimal('678'))

    # validate corp actions
    test_asset_actions = [
        [1, 5, 1618345500, '16074977038', 1, 4, 8, '217.0', 'AMZN(US0231351067) SPLIT 5 FOR 4 (AMZN, AMAZON.COM INC, US0231351067)',
         [1, 1, 8, '271.25', '1.0']],
        [2, 5, 1605731100, '10162291403', 1, 1, 11, '70.0', 'DM(US2574541080) MERGED(Acquisition) WITH US25746U1097 2492 FOR 10000 (D, DOMINION ENERGY INC, 25746U109)',
         [2, 2, 10, '17.444', '0.0']],
        [3, 5, 1605558300, '14302257657', 1, 3, 15, '5.0', 'MYL(NL0011031208) CUSIP/ISIN CHANGE TO (US92556V1061) (VTRS, VIATRIS INC-W/I, US92556V1061)',
         [3, 3, 16, '5.0', '1.0']],
        [4, 5, 1605817500, '10302900848', 1, 2, 21, '100', 'GE(US3696041033) SPINOFF  5371 FOR 1000000 (WAB, WABTEC CORP, 929740108)',
         [4, 4, 21, '100', '0.0'], [5, 4, 17, '0.5371', '0.0']],
        [5, 5, 1592339100, '13006963996', 1, 1, 19, '70.0', 'EQM(US26885B1008) MERGED(Voluntary Offer Allocation) WITH US2946001011 244 FOR 100 (ETRN, EQUITRANS MIDSTREAM CORP, US2946001011)',
         [6, 5, 20, '170.8', '0.0']],
        [6, 5, 1581452700, '12029570527', 1, 4, 22, '45000.0', 'EWLL(US30051D1063) SPLIT 1 FOR 50 (EWLLD, EWELLNESS HEALTHCARE CORP, US30051D2053)',
         [7, 6, 23, '900.0', '1.0']],
        [7, 5, 1604089500, '14147163475', 1, 1, 24, '10.0', 'LVGO(US5391831030) CASH and STOCK MERGER (Acquisition) US87918A1051 592 FOR 1000 AND EUR 4.24 (TDOC, TELADOC HEALTH INC, US87918A1051)',
         [8, 7, 3, '42.4', '0.0'], [9, 7, 25, '5.92', '0.0']],
        [8, 5, 1611260700, '15015004953', 1, 1, 27, '200.0', 'LUMN.OLD(US1567001060) MERGED(Acquisition) WITH US5502411037 1 FOR 1 (LUMN, LUMEN TECHNOLOGIES INC, US5502411037)',
         [10, 8, 26, '200.0', '0.0']],
        [9, 5, 1630007100, '17569476329', 1, 1, 12, '2.0', 'X 6 1/4 03/15/26(US912909AN84) TENDERED TO US912CALAN84 1 FOR 1 (X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26, X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26, US912CALAN84)',
         [11, 9, 28, '2.0', '0.0']],
        [10, 5, 1631219100, '17667047189', 1, 3, 29, '20.0', 'SFTW WS(US68839R1207) CUSIP/ISIN CHANGE TO (US09263B1162) (BKSY WS, BKSY 30OCT24 11.5 C, US09263B1162)',
         [12, 10, 30, '20.0', '1.0']],
        [11, 5, 1627676700, '17240033443', 1, 4, 21, '104.0', 'GE(US3696041033) SPLIT 1 FOR 8 (GE, GENERAL ELECTRIC CO, US3696043013)',
         [13, 11, 35, '13.0', '1.0']],
        [12, 5, 1627331100, '17200082800', 1, 1, 39, '610.0', 'BPYU(US11282X1037) CASH and STOCK MERGER (Acquisition) BAM 9133631 FOR 100000000, G1624R107 6572057 FOR 100000000 AND USD 12.38424741 (BAM, BROOKFIELD ASSET MANAGE-CL A, CA1125851040)',
         [14, 12, 2, '7554.3909201', '0.0'], [15, 12, 37, '55.7151', '0.0'], [16, 12, 38, '40.0895', '0.0']],
        [13, 5, 1633033500, '17897699521', 1, 2, 21, '320', 'GE(US3696041033) SPINOFF  1 FOR 11 (SLVM, SYLVAMO CORP, US8713321029)',
         [17, 13, 21, '320', '0.0'], [18, 13, 40, '29.0909', '0.0']],
        [14, 5, 1639597500, '18787960371', 1, 1, 41, '99.0', 'CORT(US2183521028) TENDERED TO US218NSPODD6 1 FOR 1 (CORT.OD2, CORCEPT THERAPEUTICS INC - TENDER ODD LOT, US218NSPODD6)',
         [19, 14, 42, '99.0', '0.0']],
        [15, 5, 1612470300, '15238437826', 1, 5, 43, '20000.0', '(CA6295231014) DELISTED (NABIF, NABIS HOLDINGS INC, CA6295231014)']
    ]
    actions = JalAccount(1).dump_corporate_actions()
    assert len(actions) == len(test_asset_actions)
    for i, action in enumerate(test_asset_actions):
        assert actions[i] == action


def test_ukfu_json_import(tmp_path, project_root, data_path, prepare_db_moex):
    statement = Statement()
    statement.load(data_path + 'tvoy.json')
    statement.validate_format()
    statement.match_db_ids()
    statement.import_into_db()

    # validate assets
    test_assets = [
        {'id': 1, 'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'RUB', 'description': 'Российский Рубль', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 2, 'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'USD', 'description': 'Доллар США', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 3, 'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'EUR', 'description': 'Евро', 'active': 1, 'currency_id': '', 'quote_source': 0}]},
        {'id': 4, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'isin': 'RU0009029540', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'SBER',  'description': '', 'active': 1,'currency_id': 1, 'quote_source': -1}]},
        {'id': 5, 'type_id': PredefinedAsset.Derivative, 'full_name': 'Si-12.11 Контракт на курс доллар-рубль', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'SiZ1', 'description': '', 'active': 1, 'currency_id': 1, 'quote_source': -1}]},
        {'id': 6, 'type_id': PredefinedAsset.Bond, 'full_name': '', 'isin': 'RU000A1038V6', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'SU26238RMFS4', 'description': '', 'active': 1, 'currency_id': 1, 'quote_source': -1}]},
        {'id': 7, 'type_id': PredefinedAsset.Bond, 'full_name': '', 'isin': 'RU000A1014H6', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'МКБ 1P2', 'description': '', 'active': 1, 'currency_id': 1, 'quote_source': -1}]},
        {'id': 8, 'type_id': PredefinedAsset.Stock, 'full_name': 'АО Аэрофлот', 'isin': 'RU0009062285', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'AFLT', 'description': '', 'active': 1, 'currency_id': 1, 'quote_source': -1}]},
        {'id': 9, 'type_id': PredefinedAsset.ETF, 'full_name': 'FinEx Gold ETF USD', 'isin': 'IE00B8XB7377', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'FXGD', 'description': 'MOEX', 'active': 1, 'currency_id': 1, 'quote_source': 1}]},
        {'id': 10, 'type_id': PredefinedAsset.Bond, 'full_name': 'АО "Тинькофф Банк" БО-07', 'isin': 'RU000A0JWM31', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'ТинькоффБ7', 'description': 'MOEX', 'active': 1, 'currency_id': 1, 'quote_source': 1}],
         'data': {AssetData.RegistrationCode: '4B020702673B', AssetData.ExpiryDate: '1624492800', AssetData.PrincipalValue: '1000'}},
        {'id': 11, 'type_id': PredefinedAsset.Stock, 'full_name': 'ГДР ЕвроМедЦентр GEMC', 'isin': 'US91085A2033', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'GEMC', 'description': 'MOEX', 'active': 1, 'currency_id': 1, 'quote_source': 1}]},
        {'id': 12, 'type_id': PredefinedAsset.Stock, 'full_name': 'ао ПАО Банк ВТБ', 'isin': 'RU000A0JP5V6', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'VTBR', 'description': 'MOEX', 'active': 1, 'currency_id': 1, 'quote_source': 1}],
         'data': {AssetData.RegistrationCode: '10401000B'}},
        {'id': 13, 'type_id': PredefinedAsset.Derivative, 'full_name': 'Фьючерсный контракт Si-12.21', 'isin': '', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'SiZ1', 'description': 'MOEX', 'active': 1, 'currency_id': 1, 'quote_source': 1}],
         'data': {AssetData.ExpiryDate: '1639612800'}},
        {'id': 14, 'type_id': PredefinedAsset.Stock, 'full_name': 'ПАО Московская Биржа', 'isin': 'RU000A0JR4A1', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'MOEX', 'description': 'MOEX', 'active': 1, 'currency_id': 1, 'quote_source': 1}],
         'data': {AssetData.RegistrationCode: '1-05-08443-H'}},
        {'id': 15, 'type_id': PredefinedAsset.Stock, 'full_name': 'Polymetal International plc', 'isin': 'JE00B6T5S470',
         'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'POLY', 'description': 'MOEX', 'active': 1, 'currency_id': 1, 'quote_source': 1}]},
        {'id': 16, 'type_id': PredefinedAsset.Stock, 'full_name': 'Северсталь (ПАО)ао', 'isin': 'RU0009046510', 'country_id': 0, 'base_asset': '',
         'symbols': [{'symbol': 'CHMF', 'description': 'MOEX', 'active': 1, 'currency_id': 1, 'quote_source': 1}],
         'data': {AssetData.RegistrationCode: '1-02-00143-A'}}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets
