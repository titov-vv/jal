import json
from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr, prepare_db_moex

from jal.data_import.statement import Statement
from jal.db.helpers import readSQL
from jal.constants import PredefinedAsset


def test_ibkr_json_import(tmp_path, project_root, data_path, prepare_db_ibkr):
    statement = Statement()
    statement.load(data_path + 'ibkr.json')
    statement.validate_format()
    statement.match_db_ids(verbal=False)

    with open(data_path + 'matched.json', 'r') as json_file:
        expected_result = json.load(json_file)

    assert statement._data == expected_result

    statement.import_into_db()

    # validate assets
    test_assets = [
        [1, 'RUB', PredefinedAsset.Money, 'Российский Рубль', '', 0, -1, 0],
        [2, 'USD', PredefinedAsset.Money, 'Доллар США', '', 0, 0, 0],
        [3, 'EUR', PredefinedAsset.Money, 'Евро', '', 0, 0, 0],
        [4, 'VUG', PredefinedAsset.ETF, 'Growth ETF', 'US9229087369', 2, 0, 0],
        [5, 'EDV', PredefinedAsset.ETF, 'VANGUARD EXTENDED DUR TREAS', '', 2, 0, 0],
        [6, 'CAD', PredefinedAsset.Money, '', '', 0, -1, 0],
        [7, 'AMZN', PredefinedAsset.Stock, 'AMAZON.COM INC', 'US0231351067', 0, 2, 0],
        [8, 'BABA', PredefinedAsset.Stock, 'ALIBABA GROUP HOLDING-SP ADR', 'US01609W1027', 0, 2, 0],
        [9, 'D', PredefinedAsset.Stock, 'DOMINION ENERGY INC', '', 0, 2, 0],
        [10, 'DM', PredefinedAsset.Stock, 'DOMINION ENERGY MIDSTREAM PA', '', 0, 2, 0],
        [11, 'X 6 1/4 03/15/26', 3, 'X 6 1/4 03/15/26', 'US912909AN84', 0, -1, 1773532800],
        [12, 'SPY   200529C00295000', 6, 'SPY 29MAY20 295.0 C', '', 0, -1, 1590710400],
        [13, 'DSKEW', PredefinedAsset.Derivative, 'DSKEW 27FEB22 11.5 C', 'US23753F1158', 0, 2, 1645920000],
        [14, 'MYL', PredefinedAsset.Stock, 'MYLAN NV', 'NL0011031208', 0, -1, 0],
        [15, 'VTRS', PredefinedAsset.Stock, 'VIATRIS INC-W/I', 'US92556V1061', 0, 2, 0],
        [16, 'WAB', PredefinedAsset.Stock, 'WABTEC CORP', '', 0, 2, 0],
        [17, 'TEF', PredefinedAsset.Stock, 'TELEFONICA SA-SPON ADR', 'US8793822086', 0, 2, 0],
        [18, 'EQM', PredefinedAsset.Stock, 'EQM MIDSTREAM PARTNERS LP', 'US26885B1008', 0, 2, 0],
        [19, 'ETRN', PredefinedAsset.Stock, 'EQUITRANS MIDSTREAM CORP', 'US2946001011', 0, 2, 0],
        [20, 'GE', PredefinedAsset.Stock, 'GENERAL ELECTRIC CO', 'US3696041033', 0, 2, 0],
        [21, 'EWLL', PredefinedAsset.Stock, 'EWELLNESS HEALTHCARE CORP', 'US30051D1063', 0, -1, 0],
        [22, 'EWLL', PredefinedAsset.Stock, 'EWELLNESS HEALTHCARE CORP', 'US30051D2053', 0, -1, 0],
        [23, 'ZROZ', PredefinedAsset.ETF, 'PIMCO 25+ YR ZERO CPN US TIF', 'US72201R8824', 2, 2, 0],
        [24, 'LVGO', PredefinedAsset.Stock, 'LIVONGO HEALTH INC', 'US5391831030', 0, -1, 0],
        [25, 'TDOC', PredefinedAsset.Stock, 'TELADOC HEALTH INC', 'US87918A1051', 0, 2, 0],
        [26, 'LUMN', PredefinedAsset.Stock, 'LUMEN TECHNOLOGIES INC', 'US5502411037', 0, 2, 0],
        [27, 'LUMN', PredefinedAsset.Stock, 'CENTURYLINK INC', 'US1567001060', 0, 2, 0],
        [28, 'X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26', 3, 'X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26', 'US912CALAN84', 0, -1, 1773532800],
        [29, 'AAPL', PredefinedAsset.Stock, 'APPLE INC', 'US0378331005', 0, 2, 0],
        [30, 'VLO   200724P00064000', 6, 'VLO 24JUL20 64.0 P', '', 0, -1, 0],
        [31, 'VLO', PredefinedAsset.Stock, 'VALERO ENERGY CORP', 'US91913Y1001', 0, 2, 0],
        [32, 'MAC', PredefinedAsset.Stock, '', 'US5543821012', 0, 2, 0],
        [33, 'F 8 1/2 04/21/23', PredefinedAsset.Bond, '', 'US345370CV02', 0, -1, 0],
        [34, 'BAM', 2, '', 'CA1125851040', 0, 2, 0],
        [35, 'BPYPM', 2, '', 'BMG1624R1079', 0, 2, 0],
        [36, 'BPYU', 2, '', 'US11282X1037', 0, -1, 0],
        [37, 'SLVM', 2, '', 'US8713321029', 0, 2, 0]
    ]
    assert readSQL("SELECT COUNT(*) FROM assets") == len(test_assets)
    for i, asset in enumerate(test_assets):
        assert readSQL("SELECT * FROM assets WHERE id=:id", [(":id", i + 1)]) == asset

    # validate accounts
    test_accounts = [
        [1, 4, 'Inv. Account', 2, 1, 'U7654321', 0, 1, 0],
        [2, 4, 'Inv. Account.RUB', 1, 1, 'U7654321', 0, 1, 0],
        [3, 4, 'Inv. Account.CAD', 6, 1, 'U7654321', 0, 1, 0],
        [4, 4, 'TEST_ACC.CAD', 6, 1, 'TEST_ACC', 0, 2, 0],
        [5, 4, 'Inv. Account.EUR', 3, 1, 'U7654321', 0, 1, 0],
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
        [1, 4, 1580443370, 5, 890.47, 1580443370, 1, 1000.0, 1, 3.0, '', 'IDEALFX'],
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
        [1, 3, 1553545500, 1553545500, '', 1, 8, -0.777, 168.37, 0.0, ''],
        [2, 3, 1579094694, 1579219200, '2661774904', 1, 21, 45000.0, 0.0012, 0.54, ''],
        [3, 3, 1580215513, 1580215513, '2674740000', 1, 4, -1240.0, 54.84, 7.75519312, ''],
        [4, 3, 1580215566, 1580342400, '2674740000', 1, 29, -148.0, 316.68, -1.987792848, ''],
        [5, 3, 1590595065, 1590710400, '2882737839', 1, 11, 2.0, 637.09, 2.0, ''],
        [6, 3, 1592575273, 1592784000, '2931083780', 1, 30, -100.0, 4.54, 1.1058334, ''],
        [7, 3, 1595607600, 1595808000, '2997636969', 1, 30, 100.0, 0.0, 0.0, 'Option assignment'],
        [8, 3, 1595607600, 1595607600, '2997636973', 1, 31, 100.0, 64.0, 0.0, 'Option assignment/exercise'],
        [9, 3, 1603882231, 1604016000, '3183801882', 1, 22, 500000.0, 0.0001, 0.7503675, ''],
        [10, 3, 1638822300, 1638822300, '18694975077', 1, 33, -8.0, 1103.06815, 0.0, '(US345370CV02) FULL CALL / EARLY REDEMPTION FOR USD 1.10306815 PER BOND (F 8 1/2 04/21/23, F 8 1/2 04/21/23, US345370CV02)']
    ]
    assert readSQL("SELECT COUNT(*) FROM trades") == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert readSQL("SELECT * FROM trades WHERE id=:id", [(":id", i + 1)]) == trade

    # validate asset payments
    test_payments = [
        [1, 2, 1529612400, '', '', 1, 1, 5, 16.76, 0.0, 'EDV (US9219107094) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [2, 2, 1533673200, '', '', 1, 1, 5, 20.35, 0.54, 'EDV(US9219107094) CASH DIVIDEND 0.10175000 USD PER SHARE (Ordinary Dividend)'],
        [3, 2, 1633033200, '', '16054321038', 3, 1, 4, 5.887, 15.0, 'VUG (US9229087369) Stock Dividend US9229087369 196232339 for 10000000000'],
        [4, 2, 1595017200, '', '13259965038', 3, 1, 17, 3.0, 0.0, 'TEF (US8793822086) STOCK DIVIDEND US8793822086 416666667 FOR 10000000000'],
        [5, 2, 1591215600, '', '12882908488', 3, 1, 32, 3.0, 0.0, 'MAC (US5543821012) CASH DIVIDEND USD 0.10, STOCK DIVIDEND US5543821012 548275673 FOR 10000000000'],
        [6, 2, 1578082800, '', '', 1, 1, 23, 60.2, 6.02, 'ZROZ(US72201R8824) CASH DIVIDEND USD 0.86 PER SHARE (Ordinary Dividend)'],
        [7, 2, 1633033200, '', '', 1, 1, 4, 158.6, 15.86, 'VUG (US9229087369) CASH DIVIDEND USD 0.52 (Ordinary Dividend)'],
        [8, 2, 1590595065, '', '2882737839', 2, 1, 11, -25.69, 0.0, 'PURCHASE ACCRUED INT X 6 1/4 03/15/26'],
        [9, 2, 1600128000, '', '', 2, 1, 11, 62.5, 0.0, 'BOND COUPON PAYMENT (X 6 1/4 03/15/26)']
    ]
    assert readSQL("SELECT COUNT(*) FROM dividends") == len(test_payments)
    for i, payment in enumerate(test_payments):
        assert readSQL("SELECT * FROM dividends WHERE id=:id", [(":id", i + 1)]) == payment

    # Verify that asset prices were loaded for stock dividends
    stock_quotes = [
        [1, 946684800, 1, 1.0],
        [2, 1633033200, 4, 25.73],
        [3, 1595017200, 17, 4.7299999999999995],
        [4, 1591215600, 32, 8.59]
    ]
    for i, quote in enumerate(stock_quotes):
        assert readSQL("SELECT * FROM quotes WHERE id=:id", [(":id", i + 1)]) == quote

    # validate corp actions
    test_corp_actons = [
        [1, 5, 1618345500, '16074977038', 1, 4, 7, 217.0, 7, 271.25, 1.0, 'AMZN(US0231351067) SPLIT 5 FOR 4 (AMZN, AMAZON.COM INC, US0231351067)'],
        [2, 5, 1605731100, '10162291403', 1, 1, 10, 70.0, 9, 17.444, 1.0, 'DM(US2574541080) MERGED(Acquisition) WITH US25746U1097 2492 FOR 10000 (D, DOMINION ENERGY INC, 25746U109)'],
        [3, 5, 1605558300, '14302257657', 1, 3, 14, 5.0, 15, 5.0, 1.0, 'MYL(NL0011031208) CUSIP/ISIN CHANGE TO (US92556V1061) (VTRS, VIATRIS INC-W/I, US92556V1061)'],
        [4, 5, 1605817500, '10302900848', 1, 2, 20, 100.0, 16, 0.5371, 0.0, 'GE(US3696041033) SPINOFF  5371 FOR 1000000 (WAB, WABTEC CORP, 929740108)'],
        [5, 5, 1592339100, '13006963996', 1, 1, 18, 70.0, 19, 170.8, 1.0, 'EQM(US26885B1008) MERGED(Acquisition) WITH US2946001011 244 FOR 100 (ETRN, EQUITRANS MIDSTREAM CORP, US2946001011)'],
        [6, 5, 1627676700, '17240033443', 1, 4, 20, 104.0, 20, 13.0, 1.0, 'GE(US3696041033) SPLIT 1 FOR 8 (GE, GENERAL ELECTRIC CO, US3696043013)'],
        [7, 5, 1581452700, '12029570527', 1, 4, 21, 45000.0, 22, 900.0, 1.0, 'EWLL(US30051D1063) SPLIT 1 FOR 50 (EWLLD, EWELLNESS HEALTHCARE CORP, US30051D2053)'],
        [8, 5, 1604089500, '14147163475', 1, 1, 24, 10.0, 25, 5.92, 1.0, 'LVGO(US5391831030) CASH and STOCK MERGER (Acquisition) US87918A1051 592 FOR 1000 AND EUR 4.24 (TDOC, TELADOC HEALTH INC, US87918A1051)'],
        [9, 5, 1611260700, '15015004953', 1, 1, 27, 200.0, 26, 200.0, 1.0, 'LUMN.OLD(US1567001060) MERGED(Acquisition) WITH US5502411037 1 FOR 1 (LUMN, LUMEN TECHNOLOGIES INC, US5502411037)'],
        [10, 5, 1630007100, '17569476329', 1, 1, 11, 2.0, 28, 2.0, 1.0, 'X 6 1/4 03/15/26(US912909AN84) TENDERED TO US912CALAN84 1 FOR 1 (X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26, X 6 1/4 03/15/26 - PARTIAL CALL RED DATE 9/26, US912CALAN84)'],
        [11, 5, 1627331099, '17200082800', 1, 2, 36, 610.0, 34, 55.7151, 1.0, 'BPYU(US11282X1037) CASH and STOCK MERGER (Acquisition) BAM 9133631 FOR 100000000, G1624R107 6572057 FOR 100000000 AND USD 12.38424741 (BAM, BROOKFIELD ASSET MANAGE-CL A, CA1125851040)'],
        [12, 5, 1627331100, '17200082811', 1, 1, 36, 610.0, 35, 40.0895, 1.0, 'BPYU(US11282X1037) CASH and STOCK MERGER (Acquisition) BAM 9133631 FOR 100000000, G1624R107 6572057 FOR 100000000 AND USD 12.38424741 (BPYPM, NEW LP PREFERRED UNITS, BMG1624R1079)'],
        [13, 5, 1633033500, '17897699521', 1, 2, 20, 320.0, 37, 29.0909, 0.0, 'GE(US3696041033) SPINOFF  1 FOR 11 (SLVM, SYLVAMO CORP, US8713321029)']
    ]
    assert readSQL("SELECT COUNT(*) FROM corp_actions") == len(test_corp_actons)
    for i, action in enumerate(test_corp_actons):
        assert readSQL("SELECT * FROM corp_actions WHERE id=:id", [(":id", i + 1)]) == action


def test_ukfu_json_import(tmp_path, project_root, data_path, prepare_db_moex):
    statement = Statement()
    statement.load(data_path + 'ukfu.json')
    statement.validate_format()
    statement.match_db_ids(verbal=False)
    statement.import_into_db()

    # validate assets
    test_assets = [
        [1, 'RUB', 1, 'Российский Рубль', '', 0, -1, 0],
        [2, 'USD', 1, 'Доллар США', '', 0, 0, 0],
        [3, 'EUR', 1, 'Евро', '', 0, 0, 0],
        [4, 'SBER', 2, '', '', 0, 0, 0],
        [5, 'SiZ1', 6, 'Si-12.11 Контракт на курс доллар-рубль', '', 0, 0, 0],
        [6, 'SU26238RMFS4', 3, '', 'RU000A1038V6', 0, 0, 0],
        [7, 'МКБ 1P2', 3, '', 'RU000A1014H6', 0, 0, 0],
        [8, 'FXGD', 4, 'FinEx Gold ETF USD', 'IE00B8XB7377', 0, 1, 0],
        [9, 'ТинькоффБ7', 3, 'АО "Тинькофф Банк" БО-07', 'RU000A0JWM31', 0, 1, 1624492800],
        [10, 'ЗПИФ ПНК', 4, 'ЗПИФ Фонд ПНК-Рентал', 'RU000A1013V9', 0, 1, 0],
        [11, 'VTBR', 2, 'ао ПАО Банк ВТБ', 'RU000A0JP5V6', 0, 1, 0],
        [12, 'POLY', 2, 'Polymetal International plc', 'JE00B6T5S470', 0, 1, 0],
        [13, 'SiZ1', 6, 'Фьючерсный контракт Si-12.21', '', 0, 1, 1639612800],
        [14, 'MOEX', 2, 'ПАО Московская Биржа', 'RU000A0JR4A1', 0, 1, 0],
        [15, 'CHMF', 2, 'Северсталь (ПАО)ао', 'RU0009046510', 0, 1, 0]
    ]
    assert readSQL("SELECT COUNT(*) FROM assets") == len(test_assets)
    for i, asset in enumerate(test_assets):
        assert readSQL("SELECT * FROM assets WHERE id=:id", [(":id", i + 1)]) == asset