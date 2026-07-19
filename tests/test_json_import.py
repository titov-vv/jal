from decimal import Decimal
from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr, prepare_db_moex

from jal.data_import.statement import Statement, JSF
from tests.helpers import d2t
from jal.constants import PredefinedAsset, SymbolId, AssetLocation
from jal.db.account import JalAccount
from jal.db.asset import JalAsset, AssetData


def test_ibkr_json_import(tmp_path, project_root, data_path, prepare_db_ibkr):
    statement = Statement()
    statement.load(data_path + 'ibkr.json')
    statement.validate_format()
    statement.match_db_ids()

    # Only pre-existing db elements are matched: RUB/USD/EUR currencies, VUG (by symbol),
    # EDV (by cusip), ZROZ (by isin), the USD account and the two dividends listed in the
    # fixture's 'db_ids' section (tax updates). Symbols are matched during import.
    assert statement._id_map == {
        JSF.ACCOUNTS: {2: 1},
        JSF.ASSETS: {1: 1, 2: 2, 32: 3, 5: 4, 43: 5, 21: 6},
        JSF.SYMBOLS: {},
        JSF.ASSET_PAYMENTS: {8: 1, 9: 2}
    }

    statement.import_into_db()

    # validate assets
    test_assets = [
        {'id': 1, 'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'country_id': 0,
         'symbols': [{'id': 1, 'symbol': 'RUB', 'currency_id': 1, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1, 'icon': ''}],
         'ID': {(1, SymbolId.ISO4217_CODE): '643'}},
        {'id': 2, 'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'country_id': 0,
         'symbols': [{'id': 2, 'symbol': 'USD', 'currency_id': 2, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1, 'icon': ''}],
         'ID': {(2, SymbolId.ISO4217_CODE): '840'}},
        {'id': 3, 'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'country_id': 0,
         'symbols': [{'id': 3, 'symbol': 'EUR', 'currency_id': 3, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1, 'icon': ''}],
         'ID': {(3, SymbolId.ISO4217_CODE): '978'}},
        {'id': 4, 'type_id': PredefinedAsset.ETF, 'full_name': 'Growth ETF', 'country_id': 2,
         'symbols': [{'id': 4, 'symbol': 'VUG', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(4, SymbolId.ISIN): 'US9229087369', (4, SymbolId.CUSIP): '922908736'}},
        {'id': 5, 'type_id': PredefinedAsset.ETF, 'full_name': 'VANGUARD EXTENDED DUR TREAS', 'country_id': 2,
         'symbols': [{'id': 5, 'symbol': 'EDV', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(5, SymbolId.CUSIP): '921910709'}},
        {'id': 6, 'type_id': PredefinedAsset.ETF, 'full_name': 'PIMCO 25+ YR ZERO CPN US TIF', 'country_id': 2,
         'symbols': [{'id': 6, 'symbol': 'ZROZ', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(6, SymbolId.ISIN): 'US72201R8824', (6, SymbolId.CUSIP): '72201R882'}},
        {'id': 7, 'type_id': PredefinedAsset.Money, 'full_name': 'CAD', 'country_id': 0,
         'symbols': [{'id': 7, 'symbol': 'CAD', 'currency_id': 7, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1, 'icon': ''}],
         'ID': {}},
        {'id': 8, 'type_id': PredefinedAsset.Stock, 'full_name': 'AMAZON.COM INC', 'country_id': 0,
         'symbols': [{'id': 8, 'symbol': 'AMZN', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(8, SymbolId.ISIN): 'US0231351067', (8, SymbolId.CUSIP): '023135106'}},
        {'id': 9, 'type_id': PredefinedAsset.Stock, 'full_name': 'ALIBABA GROUP HOLDING-SP ADR', 'country_id': 0,
         'symbols': [{'id': 9, 'symbol': 'BABA', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(9, SymbolId.ISIN): 'US01609W1027', (9, SymbolId.CUSIP): '01609W102'}},
        {'id': 10, 'type_id': PredefinedAsset.Stock, 'full_name': 'DOMINION ENERGY INC', 'country_id': 0,
         'symbols': [{'id': 10, 'symbol': 'D', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(10, SymbolId.CUSIP): '25746U109'}},
        {'id': 11, 'type_id': PredefinedAsset.Stock, 'full_name': 'DOMINION ENERGY MIDSTREAM PA', 'country_id': 0,
         'symbols': [{'id': 11, 'symbol': 'DM', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(11, SymbolId.CUSIP): '257454108'}},
        {'id': 12, 'type_id': PredefinedAsset.Bond, 'full_name': 'X 6 1/4 03/15/26', 'country_id': 0,
         'symbols': [{'id': 12, 'symbol': 'X 6 1/4 03/15/26', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(12, SymbolId.ISIN): 'US912909AN84', (12, SymbolId.CUSIP): '912909AN8'},
         'data': {AssetData.ExpiryDate: '1773532800', AssetData.PrincipalValue: '1000'}},
        {'id': 13, 'type_id': PredefinedAsset.Derivative, 'full_name': 'SPY 29MAY20 295.0 C', 'country_id': 0,
         'symbols': [{'id': 13, 'symbol': 'SPY   200529C00295000', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {},
         'data': {AssetData.ExpiryDate: '1590710400'}},
        {'id': 14, 'type_id': PredefinedAsset.Derivative, 'full_name': 'DSKEW 27FEB22 11.5 C', 'country_id': 0,
         'symbols': [{'id': 14, 'symbol': 'DSKEW', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(14, SymbolId.ISIN): 'US23753F1158', (14, SymbolId.CUSIP): '23753F115'},
         'data': {AssetData.ExpiryDate: '1645920000'}},
        {'id': 15, 'type_id': PredefinedAsset.Stock, 'full_name': 'MYLAN NV', 'country_id': 0,
         'symbols': [{'id': 15, 'symbol': 'MYL', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(15, SymbolId.ISIN): 'NL0011031208'}},
        {'id': 16, 'type_id': PredefinedAsset.Stock, 'full_name': 'VIATRIS INC-W/I', 'country_id': 0,
         'symbols': [{'id': 16, 'symbol': 'VTRS', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(16, SymbolId.ISIN): 'US92556V1061', (16, SymbolId.CUSIP): '92556V106'}},
        {'id': 17, 'type_id': PredefinedAsset.Stock, 'full_name': 'WABTEC CORP', 'country_id': 0,
         'symbols': [{'id': 17, 'symbol': 'WAB', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''},
                     {'id': 18, 'symbol': 'WBB', 'currency_id': 7, 'location_id': AssetLocation.TMX_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(17, SymbolId.CUSIP): '929740108', (18, SymbolId.CUSIP): '929740108'}},
        {'id': 18, 'type_id': PredefinedAsset.Stock, 'full_name': 'TELEFONICA SA-SPON ADR', 'country_id': 0,
         'symbols': [{'id': 19, 'symbol': 'TEF', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(19, SymbolId.ISIN): 'US8793822086', (19, SymbolId.CUSIP): '879382208'}},
        {'id': 19, 'type_id': PredefinedAsset.Stock, 'full_name': 'EQM MIDSTREAM PARTNERS LP', 'country_id': 0,
         'symbols': [{'id': 20, 'symbol': 'EQM', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(20, SymbolId.ISIN): 'US26885B1008', (20, SymbolId.CUSIP): '26885B100'}},
        {'id': 20, 'type_id': PredefinedAsset.Stock, 'full_name': 'EQUITRANS MIDSTREAM CORP', 'country_id': 0,
         'symbols': [{'id': 21, 'symbol': 'ETRN', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(21, SymbolId.ISIN): 'US2946001011', (21, SymbolId.CUSIP): '294600101'}},
        {'id': 21, 'type_id': PredefinedAsset.Stock, 'full_name': 'GENERAL ELECTRIC CO', 'country_id': 0,
         'symbols': [{'id': 22, 'symbol': 'GE', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(22, SymbolId.ISIN): 'US3696041033', (22, SymbolId.CUSIP): '369604103'}},
        {'id': 22, 'type_id': PredefinedAsset.Stock, 'full_name': 'EWELLNESS HEALTHCARE CORP', 'country_id': 0,
         'symbols': [{'id': 23, 'symbol': 'EWLL', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(23, SymbolId.ISIN): 'US30051D1063', (23, SymbolId.CUSIP): '30051D106'}},
        {'id': 23, 'type_id': PredefinedAsset.Stock, 'full_name': 'EWELLNESS HEALTHCARE CORP', 'country_id': 0,
         'symbols': [{'id': 24, 'symbol': 'EWLL', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 0, 'icon': ''},
                     {'id': 36, 'symbol': 'EWLLD', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(24, SymbolId.ISIN): 'US30051D2053', (24, SymbolId.CUSIP): '30051D205', (36, SymbolId.ISIN): 'US30051D2053', (36, SymbolId.CUSIP): '30051D205'}},
        {'id': 24, 'type_id': PredefinedAsset.Stock, 'full_name': 'LIVONGO HEALTH INC', 'country_id': 0,
         'symbols': [{'id': 25, 'symbol': 'LVGO', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(25, SymbolId.ISIN): 'US5391831030', (25, SymbolId.CUSIP): '539183103'}},
        {'id': 25, 'type_id': PredefinedAsset.Stock, 'full_name': 'TELADOC HEALTH INC', 'country_id': 0,
         'symbols': [{'id': 26, 'symbol': 'TDOC', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(26, SymbolId.ISIN): 'US87918A1051', (26, SymbolId.CUSIP): '87918A105'}},
        {'id': 26, 'type_id': PredefinedAsset.Stock, 'full_name': 'LUMEN TECHNOLOGIES INC', 'country_id': 0,
         'symbols': [{'id': 27, 'symbol': 'LUMN', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(27, SymbolId.ISIN): 'US5502411037', (27, SymbolId.CUSIP): '550241103'}},
        {'id': 27, 'type_id': PredefinedAsset.Stock, 'full_name': 'CENTURYLINK INC', 'country_id': 0,
         'symbols': [{'id': 28, 'symbol': 'LUMN', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(28, SymbolId.ISIN): 'US1567001060', (28, SymbolId.CUSIP): '156700106'}},
        {'id': 28, 'type_id': PredefinedAsset.Bond, 'full_name': 'X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26', 'country_id': 0,
         'symbols': [{'id': 29, 'symbol': 'X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(29, SymbolId.ISIN): 'US912CALAN84', (29, SymbolId.CUSIP): '912CALAN8'},
         'data': {AssetData.ExpiryDate: '1773532800', AssetData.PrincipalValue: '1000'}},
        {'id': 29, 'type_id': PredefinedAsset.Derivative, 'full_name': 'BKSY 30DEC24 11.5 C', 'country_id': 0,
         'symbols': [{'id': 30, 'symbol': 'SFTW WS', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(30, SymbolId.ISIN): 'US68839R1207', (30, SymbolId.CUSIP): '68839R120'},
         'data': {AssetData.ExpiryDate: '1735516800'}},
        {'id': 30, 'type_id': PredefinedAsset.Derivative, 'full_name': 'BKSY 30DEC24 11.5 C', 'country_id': 0,
         'symbols': [{'id': 31, 'symbol': 'BKSY WS', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(31, SymbolId.ISIN): 'US09263B1162'},
         'data': {AssetData.ExpiryDate: '1735516800'}},
        {'id': 31, 'type_id': PredefinedAsset.Stock, 'full_name': 'APPLE INC', 'country_id': 0,
         'symbols': [{'id': 32, 'symbol': 'AAPL', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(32, SymbolId.ISIN): 'US0378331005', (32, SymbolId.CUSIP): '037833100'}},
        {'id': 32, 'type_id': PredefinedAsset.Derivative, 'full_name': 'VLO 24JUL20 64.0 P', 'country_id': 0,
         'symbols': [{'id': 33, 'symbol': 'VLO   200724P00064000', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {}},
        {'id': 33, 'type_id': PredefinedAsset.Stock, 'full_name': 'VALERO ENERGY CORP', 'country_id': 0,
         'symbols': [{'id': 34, 'symbol': 'VLO', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(34, SymbolId.ISIN): 'US91913Y1001', (34, SymbolId.CUSIP): '91913Y100'}},
        {'id': 34, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 35, 'symbol': 'MAC', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(35, SymbolId.ISIN): 'US5543821012', (35, SymbolId.CUSIP): '554382101'}},
        {'id': 35, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 37, 'symbol': 'GE', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(37, SymbolId.ISIN): 'US3696043013', (37, SymbolId.CUSIP): '369604301'}},
        {'id': 36, 'type_id': PredefinedAsset.Bond, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 38, 'symbol': 'F 8 1/2 04/21/23', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(38, SymbolId.ISIN): 'US345370CV02', (38, SymbolId.CUSIP): '345370CV0'}},
        {'id': 37, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 39, 'symbol': 'BAM', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(39, SymbolId.ISIN): 'CA1125851040', (39, SymbolId.CUSIP): '112585104'}},
        {'id': 38, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 40, 'symbol': 'BPYPM', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(40, SymbolId.ISIN): 'BMG1624R1079'}},
        {'id': 39, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 41, 'symbol': 'BPYU', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(41, SymbolId.ISIN): 'US11282X1037', (41, SymbolId.CUSIP): '11282X103'}},
        {'id': 40, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 42, 'symbol': 'SLVM', 'currency_id': 2, 'location_id': AssetLocation.NYSE_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(42, SymbolId.ISIN): 'US8713321029', (42, SymbolId.CUSIP): '871332102'}},
        {'id': 41, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 43, 'symbol': 'CORT', 'currency_id': 2, 'location_id': AssetLocation.NASDAQ_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(43, SymbolId.ISIN): 'US2183521028', (43, SymbolId.CUSIP): '218352102'}},
        {'id': 42, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 44, 'symbol': 'CORT.OD2', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(44, SymbolId.ISIN): 'US218NSPODD6', (44, SymbolId.CUSIP): '218NSPODD'}},
        {'id': 43, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 45, 'symbol': 'NABIF', 'currency_id': 2, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(45, SymbolId.ISIN): 'CA6295231014', (45, SymbolId.CUSIP): '629523101'}}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets

    # validate accounts
    test_accounts = [
        {'id': 1, 'name': 'Inv. Account', 'currency_id': 2, 'active': 1, 'investing': 1, 'organization_id': 1, 'reconciled_on': 0, 'account_type': 2, 'data': {1: 'U7654321', 4: '10'}},
        {'id': 2, 'name': 'Inv. Account.RUB', 'currency_id': 1, 'active': 1, 'investing': 1, 'organization_id': 1, 'reconciled_on': 0, 'account_type': 2, 'data': {1: 'U7654321', 4: '10'}},
        {'id': 3, 'name': 'TEST_ACC.USD', 'currency_id': 2, 'active': 1, 'investing': 1, 'organization_id': 1, 'reconciled_on': 0, 'account_type': 2, 'data': {1: 'TEST_ACC', 4: '10'}},
        {'id': 4, 'name': 'Inv. Account.CAD', 'currency_id': 7, 'active': 1, 'investing': 1, 'organization_id': 1, 'reconciled_on': 0, 'account_type': 2, 'data': {1: 'U7654321', 4: '10'}},
        {'id': 5, 'name': 'TEST_ACC.CAD', 'currency_id': 7, 'active': 1, 'investing': 1, 'organization_id': 1, 'reconciled_on': 0, 'account_type': 2, 'data': {1: 'TEST_ACC', 4: '10'}},
        {'id': 6, 'name': 'Inv. Account.EUR', 'currency_id': 3, 'active': 1, 'investing': 1, 'organization_id': 1, 'reconciled_on': 0, 'account_type': 2, 'data': {1: 'U7654321', 4: '10'}}
    ]
    accounts = JalAccount.get_all_accounts()
    assert [x.dump() for x in accounts] == test_accounts

    # validate income/spending
    assert JalAccount(1).dump_actions() == [
        [1, 1, 1578073286, 1, 1, '', '', [1, 1, 5, '', '-7.96', '0', 'BALANCE OF MONTHLY MINIMUM FEE FOR DEC 2019']],
        [2, 1, 1601462520, 1, 1, '', '', [2, 2, 5, '', '0.6905565', '0', 'COMMISS COMPUTED AFTER TRADE REPORTED (EWLL)']],
        [4, 1, 1604534400, 1, 1, '', '', [4, 4, 6, '', '-0.0105', '0', 'VAT Spain 21%: 0.05 USD t*****71:Global Snapshot PnP']]
    ]
    assert JalAccount(2).dump_actions() == [
        [3, 1, 1591142400, 2, 1, '', '', [3, 3, 8, '', '0.5', '0', 'RUB CREDIT INT FOR MAY-2020']]
    ]

    # validate transfers
    assert JalAccount(1).dump_transfers() == [
        [1, 4, 1580443370, 6, '890.47', 1580443370, 1, '1000.0', 1, '3.0', '2674343226', '', 'IDEALFX', ''],
        [2, 4, 1581322108, 2, '78986.6741', 1581322108, 1, '1234.0', 1, '2.0', '2645393202', '', 'IDEALFX', ''],
        [3, 4, 1590522832, 2, '44.07', 1590522832, 1, '0.621778209', '', '', '2845906676', '', 'IDEALFX', ''],
        [4, 4, 1600374600, 1, '123456.78', 1600374600, 2, '123456.78', '', '', '13778635822', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS', ''],
        [5, 4, 1605744000, 1, '1234.0', 1605744000, 1, '1234.0', '', '', '14333901913', '', 'DISBURSEMENT INITIATED BY John Doe', ''],
        [6, 4, 1663372800, 1, '100.0', 1663372800, 1, '100.0', '', '', '1234567890', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS', ''],
        [7, 4, 1663372800, 1, '100.0', 1663372800, 1, '100.0', '', '', '1234567891', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS', ''],
        [8, 4, 1685702720, 3, '7.0', 1685702720, 1, '7.0', '', '', '24055511103', 8, 'INTERNAL TRANSFER (--)', ''],
        [9, 4, 1694777165, 1, '12345.0', 1694777165, 3, '12345.0', '', '', '21632131212', '', 'INTERNAL TRANSFER FROM U7654321 TO TEST_ACC', ''],
        [10, 4, 1683361518, 3, '150.0', 1683361518, 1, '150.0', '', '', '16377745681', '', 'INTERNAL TRANSFER FROM TEST_ACC TO U7654321', '']
    ]

    # validate trades
    test_trades = [
        [1, 3, 1553545500, 1553545500, '', 1, 9, '-0.777', '168.37', '0.0', ''],
        [2, 3, 1579094694, 1579219200, '2661774904', 1, 23, '45000.0', '0.0012', '0.54', ''],
        [3, 3, 1580215513, 1580215513, '2674740000', 1, 4, '-1240.0', '54.84', '7.75519312', ''],
        [4, 3, 1580215566, 1580342400, '2674741000', 1, 32, '-148.0', '316.68', '-5.007792848', ''],
        [5, 3, 1590595065, 1590710400, '2882737839', 1, 12, '2.0', '637.09', '2.0', ''],
        [6, 3, 1592575273, 1592784000, '2931083780', 1, 33, '-100.0', '4.54', '1.1058334', ''],
        [7, 3, 1595607600, 1595808000, '2997636969', 1, 33, '100.0', '0.0', '0.0', 'Option assignment'],
        [8, 3, 1595607600, 1595607600, '2997636973', 1, 34, '100.0', '64.0', '0.0', 'Option assignment/exercise'],
        [9, 3, 1603882231, 1604016000, '3183801882', 1, 24, '500000.0', '0.0001', '0.7503675', ''],
        [10, 3, 1640895900, 1640895900, '18952523919', 1, 31, '-30.0', '0.1', '0.0', 'BKSY WS(US09263B1162) MERGED(Liquidation) FOR USD 0.10 PER SHARE (BKSY WS, BKSY 30OCT24 11.5 C, US09263B1162)'],
        [11, 3, 1638822300, 1638822300, '18694975077', 1, 38, '-8.0', '1103.06815', '0.0', '(US345370CV02) FULL CALL / EARLY REDEMPTION FOR USD 1.10306815 PER BOND (F 8 1/2 04/21/23, F 8 1/2 04/21/23, US345370CV02)'],
        [12, 3, 1640031900, 1640031900, '18882610202', 1, 44, '-99.0', '20.75', '0.0', 'CORT.OD2(US218NSPODD6) MERGED(Voluntary Offer Allocation) FOR USD 20.75 PER SHARE (CORT.OD2, CORCEPT THERAPEUTICS INC - TENDER ODD LOT, US218NSPODD6)']
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
        [4, 2, 1595017200, 0, '13259965038', 3, 1, 19, '3.0', '0', 'TEF (US8793822086) STOCK DIVIDEND US8793822086 416666667 FOR 10000000000'],
        [5, 2, 1591215600, 0, '12882908488', 3, 1, 35, '3.0', '0', 'MAC (US5543821012) CASH DIVIDEND USD 0.10, STOCK DIVIDEND US5543821012 548275673 FOR 10000000000'],
        [6, 2, 1578082800, 1577664000, '', 1, 1, 6, '60.2', '6.02', 'ZROZ(US72201R8824) CASH DIVIDEND USD 0.86 PER SHARE (Ordinary Dividend)'],
        [7, 2, 1633033200, 0, '', 1, 1, 4, '158.6', '15.86', 'VUG (US9229087369) CASH DIVIDEND USD 0.52 (Ordinary Dividend)'],
        [8, 2, 1590595065, 0, '2882737839', 2, 1, 12, '-25.69', '0', 'PURCHASE ACCRUED INT X 6 1/4 03/15/26'],
        [9, 2, 1600128000, 0, '', 2, 1, 12, '62.5', '0', 'BOND COUPON PAYMENT (X 6 1/4 03/15/26)'],
        [10, 2, 1549843200, 0, '', 6, 1, 9, '-0.249018', '0', 'French Transaction Tax']
    ]
    payments = JalAccount(1).dump_asset_payments()
    assert len(payments) == len(test_payments)
    for i, payment in enumerate(test_payments):
        assert payments[i] == payment

    # Verify that asset prices were loaded for stock dividends and vestings
    assert JalAsset(1).quote(d2t(230101), 1) == (1672531200, Decimal('1'))
    assert JalAsset(4).quote(d2t(230101), 2) == (1633033200, Decimal('25.73'))
    assert JalAsset(18).quote(d2t(230101), 2) == (1595017200, Decimal('4.73'))
    assert JalAsset(34).quote(d2t(230101), 2) == (1591215600, Decimal('8.59'))
    assert JalAsset(8).quote(d2t(230101), 2) == (0, Decimal('0'))  # Stock granted but not vested

    # validate corp actions
    test_asset_actions = [
        [1, 5, 1618345500, '16074977038', 1, 4, 8, '217.0', 'AMZN(US0231351067) SPLIT 5 FOR 4 (AMZN, AMAZON.COM INC, US0231351067)', [1, 1, 8, '271.25', '1.0']],
        [2, 5, 1605731100, '10162291403', 1, 1, 11, '70.0', 'DM(US2574541080) MERGED(Acquisition) WITH US25746U1097 2492 FOR 10000 (D, DOMINION ENERGY INC, 25746U109)', [2, 2, 10, '17.444', '0.0']],
        [3, 5, 1605558300, '14302257657', 1, 3, 15, '5.0', 'MYL(NL0011031208) CUSIP/ISIN CHANGE TO (US92556V1061) (VTRS, VIATRIS INC-W/I, US92556V1061)', [3, 3, 16, '5.0', '1.0']],
        [4, 5, 1605817500, '10302900848', 1, 2, 22, '100', 'GE(US3696041033) SPINOFF  5371 FOR 1000000 (WAB, WABTEC CORP, 929740108)', [4, 4, 22, '100', '0.0'], [5, 4, 17, '0.5371', '0.0']],
        [5, 5, 1592339100, '13006963996', 1, 1, 20, '70.0', 'EQM(US26885B1008) MERGED(Voluntary Offer Allocation) WITH US2946001011 244 FOR 100 (ETRN, EQUITRANS MIDSTREAM CORP, US2946001011)', [6, 5, 21, '170.8', '0.0']],
        [6, 5, 1604089500, '14147163475', 1, 1, 25, '10.0', 'LVGO(US5391831030) CASH and STOCK MERGER (Acquisition) US87918A1051 592 FOR 1000 AND EUR 4.24 (TDOC, TELADOC HEALTH INC, US87918A1051)', [7, 6, 3, '42.4', '0.0'], [8, 6, 26, '5.92', '0.0']],
        [7, 5, 1611260700, '15015004953', 1, 1, 28, '200.0', 'LUMN.OLD(US1567001060) MERGED(Acquisition) WITH US5502411037 1 FOR 1 (LUMN, LUMEN TECHNOLOGIES INC, US5502411037)', [9, 7, 27, '200.0', '0.0']],
        [8, 5, 1630007100, '17569476329', 1, 1, 12, '2.0', 'X 6 1/4 03/15/26(US912909AN84) TENDERED TO US912CALAN84 1 FOR 1 (X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26, X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26, US912CALAN84)', [10, 8, 29, '2.0', '0.0']],
        [9, 5, 1631219100, '17667047189', 1, 3, 30, '20.0', 'SFTW WS(US68839R1207) CUSIP/ISIN CHANGE TO (US09263B1162) (BKSY WS, BKSY 30OCT24 11.5 C, US09263B1162)', [11, 9, 31, '20.0', '1.0']],
        [10, 5, 1581452700, '12029570527', 1, 4, 23, '45000.0', 'EWLL(US30051D1063) SPLIT 1 FOR 50 (EWLLD, EWELLNESS HEALTHCARE CORP, US30051D2053)', [12, 10, 36, '900.0', '1.0']],
        [11, 5, 1627676700, '17240033443', 1, 4, 22, '104.0', 'GE(US3696041033) SPLIT 1 FOR 8 (GE, GENERAL ELECTRIC CO, US3696043013)', [13, 11, 37, '13.0', '1.0']],
        [12, 5, 1627331100, '17200082800', 1, 1, 41, '610.0', 'BPYU(US11282X1037) CASH and STOCK MERGER (Acquisition) BAM 9133631 FOR 100000000, G1624R107 6572057 FOR 100000000 AND USD 12.38424741 (BAM, BROOKFIELD ASSET MANAGE-CL A, CA1125851040)', [14, 12, 2, '7554.3909201', '0.0'], [15, 12, 39, '55.7151', '0.0'], [16, 12, 40, '40.0895', '0.0']],
        [13, 5, 1633033500, '17897699521', 1, 2, 22, '320', 'GE(US3696041033) SPINOFF  1 FOR 11 (SLVM, SYLVAMO CORP, US8713321029)', [17, 13, 22, '320', '0.0'], [18, 13, 42, '29.0909', '0.0']],
        [14, 5, 1639597500, '18787960371', 1, 1, 43, '99.0', 'CORT(US2183521028) TENDERED TO US218NSPODD6 1 FOR 1 (CORT.OD2, CORCEPT THERAPEUTICS INC - TENDER ODD LOT, US218NSPODD6)', [19, 14, 44, '99.0', '0.0']],
        [15, 5, 1612470300, '15238437826', 1, 5, 45, '20000.0', '(CA6295231014) DELISTED (NABIF, NABIS HOLDINGS INC, CA6295231014)']
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
        {'id': 1, 'type_id': PredefinedAsset.Money, 'full_name': 'Российский Рубль', 'country_id': 0,
         'symbols': [{'id': 1, 'symbol': 'RUB', 'currency_id': 1, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1, 'icon': ''}],
         'ID': {(1, SymbolId.ISO4217_CODE): '643'}},
        {'id': 2, 'type_id': PredefinedAsset.Money, 'full_name': 'Доллар США', 'country_id': 0,
         'symbols': [{'id': 2, 'symbol': 'USD', 'currency_id': 2, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1, 'icon': ''}],
         'ID': {(2, SymbolId.ISO4217_CODE): '840'}},
        {'id': 3, 'type_id': PredefinedAsset.Money, 'full_name': 'Евро', 'country_id': 0,
         'symbols': [{'id': 3, 'symbol': 'EUR', 'currency_id': 3, 'location_id': AssetLocation.BANK_ACCOUNT, 'active': 1, 'icon': ''}],
         'ID': {(3, SymbolId.ISO4217_CODE): '978'}},
        {'id': 4, 'type_id': PredefinedAsset.Stock, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 4, 'symbol': 'SBER', 'currency_id': 1, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(4, SymbolId.ISIN): 'RU0009029540'}},
        {'id': 5, 'type_id': PredefinedAsset.Derivative, 'full_name': 'Si-12.11 Контракт на курс доллар-рубль', 'country_id': 0,
         'symbols': [{'id': 5, 'symbol': 'SiZ1', 'currency_id': 1, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {}},
        {'id': 6, 'type_id': PredefinedAsset.Bond, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 6, 'symbol': 'SU26238RMFS4', 'currency_id': 1, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(6, SymbolId.ISIN): 'RU000A1038V6'}},
        {'id': 7, 'type_id': PredefinedAsset.Bond, 'full_name': '', 'country_id': 0,
         'symbols': [{'id': 7, 'symbol': 'МКБ 1P2', 'currency_id': 1, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(7, SymbolId.ISIN): 'RU000A1014H6'}},
        {'id': 8, 'type_id': PredefinedAsset.Stock, 'full_name': 'АО Аэрофлот', 'country_id': 0,
         'symbols': [{'id': 8, 'symbol': 'AFLT', 'currency_id': 1, 'location_id': AssetLocation.UNDEFINED, 'active': 1, 'icon': ''}],
         'ID': {(8, SymbolId.ISIN): 'RU0009062285', (8, SymbolId.REG_CODE): '1-01-00010-A'}},
        {'id': 9, 'type_id': PredefinedAsset.ETF, 'full_name': 'FinEx Gold ETF USD', 'country_id': 0,
         'symbols': [{'id': 9, 'symbol': 'FXGD', 'currency_id': 1, 'location_id': AssetLocation.MOEX_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(9, SymbolId.ISIN): 'IE00B8XB7377'}},
        {'id': 10, 'type_id': PredefinedAsset.Bond, 'full_name': 'АО "Тинькофф Банк" БО-07', 'country_id': 0,
         'symbols': [{'id': 10, 'symbol': 'ТинькоффБ7', 'currency_id': 1, 'location_id': AssetLocation.MOEX_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(10, SymbolId.ISIN): 'RU000A0JWM31', (10, SymbolId.REG_CODE): '4B020702673B'},
         'data': {AssetData.ExpiryDate: '1624492800', AssetData.PrincipalValue: '1000'}},
        {'id': 11, 'type_id': PredefinedAsset.Stock, 'full_name': 'ао ПАО Банк ВТБ', 'country_id': 0,
         'symbols': [{'id': 11, 'symbol': 'VTBR', 'currency_id': 1, 'location_id': AssetLocation.MOEX_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(11, SymbolId.ISIN): 'RU000A0JP5V6', (11, SymbolId.REG_CODE): '10401000B'}},
        {'id': 12, 'type_id': PredefinedAsset.Derivative, 'full_name': 'Фьючерсный контракт Si-12.21', 'country_id': 0,
         'symbols': [{'id': 12, 'symbol': 'SiZ1', 'currency_id': 1, 'location_id': AssetLocation.MOEX_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {},
         'data': {AssetData.ExpiryDate: '1639612800'}},
        {'id': 13, 'type_id': PredefinedAsset.Stock, 'full_name': 'ПАО Московская Биржа', 'country_id': 0,
         'symbols': [{'id': 13, 'symbol': 'MOEX', 'currency_id': 1, 'location_id': AssetLocation.MOEX_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(13, SymbolId.ISIN): 'RU000A0JR4A1', (13, SymbolId.REG_CODE): '1-05-08443-H'}},
        {'id': 14, 'type_id': PredefinedAsset.Stock, 'full_name': 'Polymetal International plc', 'country_id': 0,
         'symbols': [{'id': 14, 'symbol': 'POLY', 'currency_id': 1, 'location_id': AssetLocation.MOEX_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(14, SymbolId.ISIN): 'JE00B6T5S470'}},
        {'id': 15, 'type_id': PredefinedAsset.Stock, 'full_name': 'Северсталь (ПАО)ао', 'country_id': 0,
         'symbols': [{'id': 15, 'symbol': 'CHMF', 'currency_id': 1, 'location_id': AssetLocation.MOEX_EXCHANGE, 'active': 1, 'icon': ''}],
         'ID': {(15, SymbolId.ISIN): 'RU0009046510', (15, SymbolId.REG_CODE): '1-02-00143-A'}}
    ]
    assets = JalAsset.get_assets()
    assert len(assets) == len(test_assets)
    assert [x.dump() for x in assets] == test_assets
