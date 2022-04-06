import json
from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr, prepare_db_moex

from jal.data_import.statement import Statement
from jal.db.helpers import readSQL
from jal.constants import PredefinedAsset


def test_ibkr_json_import(tmp_path, project_root, data_path, prepare_db_ibkr):
    statement = Statement()
    statement.load(data_path + 'ibkr.json')
    statement.validate_format()
    statement.match_db_ids()

    with open(data_path + 'matched.json', 'r') as json_file:
        expected_result = json.load(json_file)

    assert statement._data == expected_result

    statement.import_into_db()

    # validate assets
    test_assets = [
        [1, PredefinedAsset.Money, 'Российский Рубль', '', 0, ''],
        [2, PredefinedAsset.Money, 'Доллар США', '', 0, ''],
        [3, PredefinedAsset.Money, 'Евро', '', 0, ''],
        [4, PredefinedAsset.ETF, 'Growth ETF', 'US9229087369', 2, ''],
        [5, PredefinedAsset.ETF, 'VANGUARD EXTENDED DUR TREAS', '', 2, ''],
        [6, PredefinedAsset.ETF, 'PIMCO 25+ YR ZERO CPN US TIF', 'US72201R8824', 2, ''],
        [7, PredefinedAsset.Money, '', '', 0, ''],
        [8, PredefinedAsset.Stock, 'AMAZON.COM INC', 'US0231351067', 0, ''],
        [9, PredefinedAsset.Stock, 'ALIBABA GROUP HOLDING-SP ADR', 'US01609W1027', 0, ''],
        [10, PredefinedAsset.Stock, 'DOMINION ENERGY INC', '', 0, ''],
        [11, PredefinedAsset.Stock, 'DOMINION ENERGY MIDSTREAM PA', '', 0, ''],
        [12, PredefinedAsset.Bond, 'X 6 1/4 03/15/26', 'US912909AN84', 0, ''],
        [13, PredefinedAsset.Derivative, 'SPY 29MAY20 295.0 C', '', 0, ''],
        [14, PredefinedAsset.Derivative, 'DSKEW 27FEB22 11.5 C', 'US23753F1158', 0, ''],
        [15, PredefinedAsset.Stock, 'MYLAN NV', 'NL0011031208', 0, ''],
        [16, PredefinedAsset.Stock, 'VIATRIS INC-W/I', 'US92556V1061', 0, ''],
        [17, PredefinedAsset.Stock, 'WABTEC CORP', '', 0, ''],
        [18, PredefinedAsset.Stock, 'TELEFONICA SA-SPON ADR', 'US8793822086', 0, ''],
        [19, PredefinedAsset.Stock, 'EQM MIDSTREAM PARTNERS LP', 'US26885B1008', 0, ''],
        [20, PredefinedAsset.Stock, 'EQUITRANS MIDSTREAM CORP', 'US2946001011', 0, ''],
        [21, PredefinedAsset.Stock, 'GENERAL ELECTRIC CO', 'US3696041033', 0, ''],
        [22, PredefinedAsset.Stock, 'EWELLNESS HEALTHCARE CORP', 'US30051D1063', 0, ''],
        [23, PredefinedAsset.Stock, 'EWELLNESS HEALTHCARE CORP', 'US30051D2053', 0, ''],
        [24, PredefinedAsset.Stock, 'LIVONGO HEALTH INC', 'US5391831030', 0, ''],
        [25, PredefinedAsset.Stock, 'TELADOC HEALTH INC', 'US87918A1051', 0, ''],
        [26, PredefinedAsset.Stock, 'LUMEN TECHNOLOGIES INC', 'US5502411037', 0, ''],
        [27, PredefinedAsset.Stock, 'CENTURYLINK INC', 'US1567001060', 0, ''],
        [28, PredefinedAsset.Bond, 'X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26', 'US912CALAN84', 0, ''],
        [29, PredefinedAsset.Derivative, 'BKSY 30DEC24 11.5 C', 'US68839R1207', 0, ''],
        [30, PredefinedAsset.Derivative, 'BKSY 30DEC24 11.5 C', 'US09263B1162', 0, ''],
        [31, PredefinedAsset.Stock, 'APPLE INC', 'US0378331005', 0, ''],
        [32, PredefinedAsset.Derivative, 'VLO 24JUL20 64.0 P', '', 0, ''],
        [33, PredefinedAsset.Stock, 'VALERO ENERGY CORP', 'US91913Y1001', 0, ''],
        [34, PredefinedAsset.Stock, '', 'US5543821012', 0, ''],
        [35, PredefinedAsset.Stock, '', 'US3696043013', 0, ''],
        [36, PredefinedAsset.Bond, '', 'US345370CV02', 0, ''],
        [37, PredefinedAsset.Stock, '', 'CA1125851040', 0, ''],
        [38, PredefinedAsset.Stock, '', 'BMG1624R1079', 0, ''],
        [39, PredefinedAsset.Stock, '', 'US11282X1037', 0, ''],
        [40, PredefinedAsset.Stock, '', 'US8713321029', 0, ''],
        [41, PredefinedAsset.Stock, '', 'US2183521028', 0, ''],
        [42, PredefinedAsset.Stock, '', 'US218NSPODD6', 0, ''],
        [43, PredefinedAsset.Stock, '', 'CA6295231014', 0, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM assets") == len(test_assets)
    for i, asset in enumerate(test_assets):
        assert readSQL("SELECT * FROM assets WHERE id=:id", [(":id", i + 1)]) == asset

    # validate symbols
    test_symbols = [
        [1, 1, 'RUB', 1, 'Российский Рубль', 0, 1],
        [2, 2, 'USD', 1, 'Доллар США (Банк России)', 0, 1],
        [3, 3, 'EUR', 1, 'Евро (Банк России)', 0, 1],
        [4, 4, 'VUG', 2, 'ARCA', 2, 1],
        [5, 5, 'EDV', 2, 'ARCA', 2, 1],
        [6, 6, 'ZROZ', 2, 'ARCA', 2, 1],
        [7, 7, 'CAD', 1, '', 0, 1],
        [8, 8, 'AMZN', 2, 'NASDAQ', 2, 1],
        [9, 9, 'BABA', 2, 'NYSE', 2, 1],
        [10, 10, 'D', 2, 'NYSE', 2, 1],
        [11, 11, 'DM', 2, 'NYSE', 2, 1],
        [12, 12, 'X 6 1/4 03/15/26', 2, '', -1, 1],
        [13, 13, 'SPY   200529C00295000', 2, '', -1, 1],
        [14, 14, 'DSKEW', 2, 'NASDAQ', 2, 1],
        [15, 15, 'MYL', 2, '', -1, 1],
        [16, 16, 'VTRS', 2, 'NASDAQ', 2, 1],
        [17, 17, 'WAB', 2, 'NYSE', 2, 1],
        [18, 17, 'WBB', 7, 'TSE', 4, 1],
        [19, 18, 'TEF', 2, 'NYSE', 2, 1],
        [20, 19, 'EQM', 2, 'NYSE', 2, 1],
        [21, 20, 'ETRN', 2, 'NYSE', 2, 1],
        [22, 21, 'GE', 2, 'NYSE', 2, 1],
        [23, 22, 'EWLL', 2, 'PINK', -1, 1],
        [24, 23, 'EWLL', 2, 'PINK', -1, 0],
        [25, 24, 'LVGO', 2, '', -1, 1],
        [26, 25, 'TDOC', 2, 'NYSE', 2, 1],
        [27, 26, 'LUMN', 2, 'NYSE', 2, 1],
        [28, 27, 'LUMN', 2, 'NYSE', 2, 1],
        [29, 28, 'X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26', 2, '', -1, 1],
        [30, 29, 'SFTW WS', 2, 'NYSE', 2, 1],
        [31, 30, 'BKSY WS', 2, 'NYSE', 2, 1],
        [32, 31, 'AAPL', 2, 'NASDAQ', 2, 1],
        [33, 32, 'VLO   200724P00064000', 2, 'CBOE', -1, 1],
        [34, 33, 'VLO', 2, 'NYSE', 2, 1],
        [35, 34, 'MAC', 2, 'NYSE', 2, 1],
        [36, 23, 'EWLLD', 2, 'PINK', -1, 1],
        [37, 35, 'GE', 2, 'NYSE', 2, 1],
        [38, 36, 'F 8 1/2 04/21/23', 2, '', -1, 1],
        [39, 37, 'BAM', 2, 'NYSE', 2, 1],
        [40, 38, 'BPYPM', 2, 'NASDAQ', 2, 1],
        [41, 39, 'BPYU', 2, '', -1, 1],
        [42, 40, 'SLVM', 2, 'NYSE', 2, 1],
        [43, 41, 'CORT', 2, 'NASDAQ', 2, 1],
        [44, 42, 'CORT.OD2', 2, 'CORPACT', -1, 1],
        [45, 43, 'NABIF', 2, '', -1, 1]
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_tickers") == len(test_symbols)
    for i, symbol in enumerate(test_symbols):
        assert readSQL("SELECT * FROM asset_tickers WHERE id=:id", [(":id", i + 1)]) == symbol

    # validate asset's data
    test_asset_data = [
        [1, 5, 1, '921910709'],
        [2, 8, 1, '023135106'],
        [3, 9, 1, '01609W102'],
        [4, 10, 1, '25746U109'],
        [5, 11, 1, '257454108'],
        [6, 12, 1, '912909AN8'], [7, 12, 2, '1773532800'],
        [8, 13, 2, '1590710400'],
        [9, 14, 1, '23753F115'], [10, 14, 2, '1645920000'],
        [11, 16, 1, '92556V106'],
        [12, 17, 1, '929740108'],
        [13, 18, 1, '879382208'],
        [14, 19, 1, '26885B100'],
        [15, 20, 1, '294600101'],
        [16, 21, 1, '369604103'],
        [17, 22, 1, '30051D106'],
        [18, 23, 1, '30051D205'],
        [19, 6, 1, '72201R882'],
        [20, 24, 1, '539183103'],
        [21, 25, 1, '87918A105'],
        [22, 26, 1, '550241103'],
        [23, 27, 1, '156700106'],
        [24, 28, 1, '912CALAN8'], [25, 28, 2, '1773532800'],
        [26, 29, 1, '68839R120'], [27, 29, 2, '1735516800'],
        [28, 30, 2, '1735516800'],
        [29, 31, 1, '037833100'],
        [30, 4, 1, '922908736'],
        [31, 33, 1, '91913Y100'],
        [32, 34, 1, '554382101'],
        [33, 35, 1, '369604301'],
        [34, 36, 1, '345370CV0'],
        [35, 37, 1, '112585104'],
        [36, 39, 1, '11282X103'],
        [37, 40, 1, '871332102'],
        [38, 41, 1, '218352102'],
        [39, 42, 1, '218NSPODD'],
        [40, 43, 1, '629523101']
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_data") == len(test_asset_data)
    for i, data in enumerate(test_asset_data):
        assert readSQL("SELECT * FROM asset_data WHERE id=:id", [(":id", i + 1)]) == data

    # validate accounts
    test_accounts = [
        [1, 4, 'Inv. Account', 2, 1, 'U7654321', 0, 1, 0],
        [2, 4, 'Inv. Account.RUB', 1, 1, 'U7654321', 0, 1, 0],
        [3, 4, 'TEST_ACC.USD', 2, 1, 'TEST_ACC', 0, 2, 0],
        [4, 4, 'Inv. Account.CAD', 7, 1, 'U7654321', 0, 1, 0],
        [5, 4, 'TEST_ACC.CAD', 7, 1, 'TEST_ACC', 0, 2, 0],
        [6, 4, 'Inv. Account.EUR', 3, 1, 'U7654321', 0, 1, 0]
    ]
    assert readSQL("SELECT COUNT(*) FROM accounts") == len(test_accounts)
    for i, account in enumerate(test_accounts):
        assert readSQL("SELECT * FROM accounts WHERE id=:id", [(":id", i+1)]) == account

    # validate peers
    test_peers = [
        [1, 0, 'IB', ''],
        [2, 0, 'Bank for #TEST_ACC', '']
    ]
    assert readSQL("SELECT COUNT(*) FROM agents") == len(test_peers)
    for i, peer in enumerate(test_peers):
        assert readSQL("SELECT * FROM agents WHERE id=:id", [(":id", i + 1)]) == peer

    # validate income/spending
    test_actions = [
        [1, 1, 8, '', 42.4, 0.0, 'LVGO(US5391831030) CASH and STOCK MERGER (Acquisition) US87918A1051 592 FOR 1000 AND EUR 4.24 (TDOC, TELADOC HEALTH INC, US87918A1051)'],
        [2, 2, 8, '', 7554.3909201, 0.0, 'BPYU(US11282X1037) CASH and STOCK MERGER (Acquisition) BAM 9133631 FOR 100000000, G1624R107 6572057 FOR 100000000 AND USD 12.38424741 (BAM, BROOKFIELD ASSET MANAGE-CL A, CA1125851040)'],
        [3, 3, 5, '', -7.96, 0.0, 'BALANCE OF MONTHLY MINIMUM FEE FOR DEC 2019'],
        [4, 4, 5, '', 0.6905565, 0.0, 'COMMISS COMPUTED AFTER TRADE REPORTED (EWLL)'],
        [5, 5, 8, '', 0.5, 0.0, 'RUB CREDIT INT FOR MAY-2020'],
        [6, 6, 6, '', -0.249018, 0.0, 'BABA (ALIBABA GROUP HOLDING-SP ADR) - French Transaction Tax']
    ]
    assert readSQL("SELECT COUNT(amount) FROM action_details") == len(test_actions)
    for i, action in enumerate(test_actions):
        assert readSQL("SELECT * FROM action_details WHERE id=:id", [(":id", i+1)]) == action

    # validate transfers
    test_transfers = [
        [1, 4, 1580443370, 6, 890.47, 1580443370, 1, 1000.0, 1, 3.0, '', 'IDEALFX'],
        [2, 4, 1581322108, 2, 78986.6741, 1581322108, 1, 1234.0, 1, 2.0, '', 'IDEALFX'],
        [3, 4, 1590522832, 2, 44.07, 1590522832, 1, 0.621778209, '', '', '', 'IDEALFX'],
        [4, 4, 1600374600, 1, 123456.78, 1600374600, 2, 123456.78, '', '', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS'],
        [5, 4, 1605744000, 1, 1234.0, 1605744000, 1, 1234.0, '', '', '', 'DISBURSEMENT INITIATED BY John Doe']
    ]
    assert readSQL("SELECT COUNT(*) FROM transfers") == len(test_transfers)
    for i, transfer in enumerate(test_transfers):
        assert readSQL("SELECT * FROM transfers WHERE id=:id", [(":id", i+1)]) == transfer

    # validate trades
    test_trades = [
        [1, 3, 1553545500, 1553545500, '', 1, 9, -0.777, 168.37, 0.0, ''],
        [2, 3, 1579094694, 1579219200, '2661774904', 1, 22, 45000.0, 0.0012, 0.54, ''],
        [3, 3, 1580215513, 1580215513, '2674740000', 1, 4, -1240.0, 54.84, 7.75519312, ''],
        [4, 3, 1580215566, 1580342400, '2674740000', 1, 31, -148.0, 316.68, -0.987792848, ''],
        [5, 3, 1590595065, 1590710400, '2882737839', 1, 12, 2.0, 637.09, 2.0, ''],
        [6, 3, 1592575273, 1592784000, '2931083780', 1, 32, -100.0, 4.54, 1.1058334, ''],
        [7, 3, 1595607600, 1595808000, '2997636969', 1, 32, 100.0, 0.0, 0.0, 'Option assignment'],
        [8, 3, 1595607600, 1595607600, '2997636973', 1, 33, 100.0, 64.0, 0.0, 'Option assignment/exercise'],
        [9, 3, 1603882231, 1604016000, '3183801882', 1, 23, 500000.0, 0.0001, 0.7503675, ''],
        [10, 3, 1640895900, 1640895900, '18952523919', 1, 30, -30.0, 0.1, 0.0, 'BKSY WS(US09263B1162) MERGED(Liquidation) FOR USD 0.10 PER SHARE (BKSY WS, BKSY 30OCT24 11.5 C, US09263B1162)'],
        [11, 3, 1638822300, 1638822300, '18694975077', 1, 36, -8.0, 1103.06815, 0.0, '(US345370CV02) FULL CALL / EARLY REDEMPTION FOR USD 1.10306815 PER BOND (F 8 1/2 04/21/23, F 8 1/2 04/21/23, US345370CV02)'],
        [12, 3, 1640031900, 1640031900, '18882610202', 1, 42, -99.0, 20.75, 0.0, 'CORT.OD2(US218NSPODD6) MERGED(Voluntary Offer Allocation) FOR USD 20.75 PER SHARE (CORT.OD2, CORCEPT THERAPEUTICS INC - TENDER ODD LOT, US218NSPODD6)']
    ]
    assert readSQL("SELECT COUNT(*) FROM trades") == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert readSQL("SELECT * FROM trades WHERE id=:id", [(":id", i + 1)]) == trade

    # validate asset payments
    test_payments = [
        [1, 2, 1529612400, '', '', 1, 1, 5, 16.76, 0.0, 'EDV (US9219107094) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [2, 2, 1533673200, '', '', 1, 1, 5, 20.35, 0.54, 'EDV(US9219107094) CASH DIVIDEND 0.10175000 USD PER SHARE (Ordinary Dividend)'],
        [3, 2, 1633033200, '', '16054321038', 3, 1, 4, 5.887, 15.0, 'VUG (US9229087369) Stock Dividend US9229087369 196232339 for 10000000000'],
        [4, 2, 1595017200, '', '13259965038', 3, 1, 18, 3.0, 0.0, 'TEF (US8793822086) STOCK DIVIDEND US8793822086 416666667 FOR 10000000000'],
        [5, 2, 1591215600, '', '12882908488', 3, 1, 34, 3.0, 0.0, 'MAC (US5543821012) CASH DIVIDEND USD 0.10, STOCK DIVIDEND US5543821012 548275673 FOR 10000000000'],
        [6, 2, 1578082800, '', '', 1, 1, 6, 60.2, 6.02, 'ZROZ(US72201R8824) CASH DIVIDEND USD 0.86 PER SHARE (Ordinary Dividend)'],
        [7, 2, 1633033200, '', '', 1, 1, 4, 158.6, 15.86, 'VUG (US9229087369) CASH DIVIDEND USD 0.52 (Ordinary Dividend)'],
        [8, 2, 1590595065, '', '2882737839', 2, 1, 12, -25.69, 0.0, 'PURCHASE ACCRUED INT X 6 1/4 03/15/26'],
        [9, 2, 1600128000, '', '', 2, 1, 12, 62.5, 0.0, 'BOND COUPON PAYMENT (X 6 1/4 03/15/26)']
    ]
    assert readSQL("SELECT COUNT(*) FROM dividends") == len(test_payments)
    for i, payment in enumerate(test_payments):
        assert readSQL("SELECT * FROM dividends WHERE id=:id", [(":id", i + 1)]) == payment

    # Verify that asset prices were loaded for stock dividends
    stock_quotes = [
        [1, 946684800, 1, 1, 1.0],
        [2, 1633033200, 4, 2, 25.73],
        [3, 1595017200, 18, 2, 4.7299999999999995],
        [4, 1591215600, 34, 2, 8.59]
    ]
    for i, quote in enumerate(stock_quotes):
        assert readSQL("SELECT * FROM quotes WHERE id=:id", [(":id", i + 1)]) == quote

    # validate corp actions
    test_corp_actons = [
        [1, 5, 1618345500, '16074977038', 1, 4, 8, 217.0, 8, 271.25, 1.0, 'AMZN(US0231351067) SPLIT 5 FOR 4 (AMZN, AMAZON.COM INC, US0231351067)'],
        [2, 5, 1605731100, '10162291403', 1, 1, 11, 70.0, 10, 17.444, 1.0, 'DM(US2574541080) MERGED(Acquisition) WITH US25746U1097 2492 FOR 10000 (D, DOMINION ENERGY INC, 25746U109)'],
        [3, 5, 1605558300, '14302257657', 1, 3, 15, 5.0, 16, 5.0, 1.0, 'MYL(NL0011031208) CUSIP/ISIN CHANGE TO (US92556V1061) (VTRS, VIATRIS INC-W/I, US92556V1061)'],
        [4, 5, 1605817500, '10302900848', 1, 2, 21, 100.0, 17, 0.5371, 0.0, 'GE(US3696041033) SPINOFF  5371 FOR 1000000 (WAB, WABTEC CORP, 929740108)'],
        [5, 5, 1592339100, '13006963996', 1, 1, 19, 70.0, 20, 170.8, 1.0, 'EQM(US26885B1008) MERGED(Voluntary Offer Allocation) WITH US2946001011 244 FOR 100 (ETRN, EQUITRANS MIDSTREAM CORP, US2946001011)'],
        [6, 5, 1581452700, '12029570527', 1, 4, 22, 45000.0, 23, 900.0, 1.0, 'EWLL(US30051D1063) SPLIT 1 FOR 50 (EWLLD, EWELLNESS HEALTHCARE CORP, US30051D2053)'],
        [7, 5, 1604089500, '14147163475', 1, 1, 24, 10.0, 25, 5.92, 1.0, 'LVGO(US5391831030) CASH and STOCK MERGER (Acquisition) US87918A1051 592 FOR 1000 AND EUR 4.24 (TDOC, TELADOC HEALTH INC, US87918A1051)'],
        [8, 5, 1611260700, '15015004953', 1, 1, 27, 200.0, 26, 200.0, 1.0, 'LUMN.OLD(US1567001060) MERGED(Acquisition) WITH US5502411037 1 FOR 1 (LUMN, LUMEN TECHNOLOGIES INC, US5502411037)'],
        [9, 5, 1630007100, '17569476329', 1, 1, 12, 2.0, 28, 2.0, 1.0, 'X 6 1/4 03/15/26(US912909AN84) TENDERED TO US912CALAN84 1 FOR 1 (X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26, X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26, US912CALAN84)'],
        [10, 5, 1631219100, '17667047189', 1, 3, 29, 20.0, 30, 20.0, 1.0, 'SFTW WS(US68839R1207) CUSIP/ISIN CHANGE TO (US09263B1162) (BKSY WS, BKSY 30OCT24 11.5 C, US09263B1162)'],
        [11, 5, 1627676700, '17240033443', 1, 4, 21, 104.0, 35, 13.0, 1.0, 'GE(US3696041033) SPLIT 1 FOR 8 (GE, GENERAL ELECTRIC CO, US3696043013)'],
        [12, 5, 1627331099, '17200082800', 1, 2, 39, 610.0, 37, 55.7151, 1.0, 'BPYU(US11282X1037) CASH and STOCK MERGER (Acquisition) BAM 9133631 FOR 100000000, G1624R107 6572057 FOR 100000000 AND USD 12.38424741 (BAM, BROOKFIELD ASSET MANAGE-CL A, CA1125851040)'],
        [13, 5, 1627331100, '17200082811', 1, 1, 39, 610.0, 38, 40.0895, 1.0, 'BPYU(US11282X1037) CASH and STOCK MERGER (Acquisition) BAM 9133631 FOR 100000000, G1624R107 6572057 FOR 100000000 AND USD 12.38424741 (BPYPM, NEW LP PREFERRED UNITS, BMG1624R1079)'],
        [14, 5, 1633033500, '17897699521', 1, 2, 21, 320.0, 40, 29.0909, 0.0, 'GE(US3696041033) SPINOFF  1 FOR 11 (SLVM, SYLVAMO CORP, US8713321029)'],
        [15, 5, 1639597500, '18787960371', 1, 1, 41, 99.0, 42, 99.0, 1.0, 'CORT(US2183521028) TENDERED TO US218NSPODD6 1 FOR 1 (CORT.OD2, CORCEPT THERAPEUTICS INC - TENDER ODD LOT, US218NSPODD6)'],
        [16, 5, 1612470300, '15238437826', 1, 5, 43, 20000.0, 43, 0.0, 1.0, '(CA6295231014) DELISTED (NABIF, NABIS HOLDINGS INC, CA6295231014)']
    ]
    assert readSQL("SELECT COUNT(*) FROM corp_actions") == len(test_corp_actons)
    for i, action in enumerate(test_corp_actons):
        assert readSQL("SELECT * FROM corp_actions WHERE id=:id", [(":id", i + 1)]) == action


def test_ukfu_json_import(tmp_path, project_root, data_path, prepare_db_moex):
    statement = Statement()
    statement.load(data_path + 'ukfu.json')
    statement.validate_format()
    statement.match_db_ids()
    statement.import_into_db()

    # validate assets
    test_assets = [
        [1, PredefinedAsset.Money, 'Российский Рубль', '', 0, ''],
        [2, PredefinedAsset.Money, 'Доллар США', '', 0, ''],
        [3, PredefinedAsset.Money, 'Евро', '', 0, ''],
        [4, PredefinedAsset.Stock, '', 'RU0009029540', 0, ''],
        [5, PredefinedAsset.Derivative, 'Si-12.11 Контракт на курс доллар-рубль', '', 0, ''],
        [6, PredefinedAsset.Bond, '', 'RU000A1038V6', 0, ''],
        [7, PredefinedAsset.Bond, '', 'RU000A1014H6', 0, ''],
        [8, PredefinedAsset.Stock, 'Аэрофлот-росс.авиалин(ПАО)ао', 'RU0009062285', 0, ''],
        [9, PredefinedAsset.ETF, 'FinEx Gold ETF USD', 'IE00B8XB7377', 0, ''],
        [10, PredefinedAsset.Bond, 'АО "Тинькофф Банк" БО-07', 'RU000A0JWM31', 0, ''],
        [11, PredefinedAsset.ETF, 'ЗПИФ Фонд ПНК-Рентал', 'RU000A1013V9', 0, ''],
        [12, PredefinedAsset.Stock, 'ао ПАО Банк ВТБ', 'RU000A0JP5V6', 0, ''],
        [13, PredefinedAsset.Stock, 'Polymetal International plc', 'JE00B6T5S470', 0, ''],
        [14, PredefinedAsset.Derivative, 'Фьючерсный контракт Si-12.21', '', 0, ''],
        [15, PredefinedAsset.Stock, 'ПАО Московская Биржа', 'RU000A0JR4A1', 0, ''],
        [16, PredefinedAsset.Stock, 'Северсталь (ПАО)ао', 'RU0009046510', 0, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM assets") == len(test_assets)
    for i, asset in enumerate(test_assets):
        assert readSQL("SELECT * FROM assets WHERE id=:id", [(":id", i + 1)]) == asset

    # validate assets
    test_symbols = [
        [1, 1, 'RUB', 1, 'Российский Рубль', 0, 1],
        [2, 2, 'USD', 1, 'Доллар США (Банк России)', 0, 1],
        [3, 3, 'EUR', 1, 'Евро (Банк России)', 0, 1],
        [4, 4, 'SBER', 1, '', -1, 1],
        [5, 5, 'SiZ1', 1, '', -1, 1],
        [6, 6, 'SU26238RMFS4', 1, '', -1, 1],
        [7, 7, 'МКБ 1P2', 1, '', -1, 1],
        [8, 8, 'AFLT', 1, 'MOEX', 1, 1],
        [9, 9, 'FXGD', 1, 'MOEX', 1, 1],
        [10, 10, 'ТинькоффБ7', 1, 'MOEX', 1, 1],
        [11, 11, 'ЗПИФ ПНК', 1, 'MOEX', 1, 1],
        [12, 12, 'VTBR', 1, 'MOEX', 1, 1],
        [13, 13, 'POLY', 1, 'MOEX', 1, 1],
        [14, 14, 'SiZ1', 1, 'MOEX', 1, 1],
        [15, 15, 'MOEX', 1, 'MOEX', 1, 1],
        [16, 16, 'CHMF', 1, 'MOEX', 1, 1]
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_tickers") == len(test_symbols)
    for i, symbol in enumerate(test_symbols):
        assert readSQL("SELECT * FROM asset_tickers WHERE id=:id", [(":id", i + 1)]) == symbol

    # validate assets
    test_data = [
        [1, 8, 1, '1-01-00010-A'],
        [2, 10, 1, '4B020702673B'], [3, 10, 2, '1624492800'], [4, 10, 3, '1000.0'],
        [5, 11, 1, '2770'],
        [6, 12, 1, '10401000B'],
        [7, 14, 2, '1639612800'],
        [8, 15, 1, '1-05-08443-H'],
        [9, 16, 1, '1-02-00143-A']
    ]
    assert readSQL("SELECT COUNT(*) FROM asset_data") == len(test_data)
    for i, data in enumerate(test_data):
        assert readSQL("SELECT * FROM asset_data WHERE id=:id", [(":id", i + 1)]) == data