import json
from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ibkr

from jal.data_import.statement import Statement
from jal.db.helpers import readSQL


def test_statement_json_import(tmp_path, project_root, data_path, prepare_db_ibkr):
    statement = Statement()
    statement.load(data_path + 'ibkr.json')
    statement.match_db_ids(verbal=False)

    with open(data_path + 'matched.json', 'r') as json_file:
        expected_result = json.load(json_file)

    assert statement._data == expected_result

    statement.import_into_db()

    # validate assets
    test_assets = [
        [1, 'RUB', 1, 'Российский Рубль', '', 0, -1],
        [2, 'USD', 1, 'Доллар США', '', 0, 0],
        [3, 'EUR', 1, 'Евро', '', 0, 0],
        [4, 'VUG', 4, 'Growth ETF', 'US9229087369', 0, 0],
        [5, 'EDV', 4, 'VANGUARD EXTENDED DUR TREAS', '', 0, 0],
        [6, 'CAD', 1, '', '', 0, -1],
        [7, 'AMZN', 2, 'AMAZON.COM INC', 'US0231351067', 0, 2],
        [8, 'BABA', 2, 'ALIBABA GROUP HOLDING-SP ADR', 'US01609W1027', 0, 2],
        [9, 'D', 2, 'DOMINION ENERGY INC', '', 0, 2],
        [10, 'DM', 2, 'DOMINION ENERGY MIDSTREAM PA', '', 0, 2],
        [11, 'X 6 1/4 03/15/26', 3, 'X 6 1/4 03/15/26', 'US912909AN84', 0, -1],
        [12, 'SPY   200529C00295000', 6, 'SPY 29MAY20 295.0 C', '', 0, -1],
        [13, 'DSKEW', 6, 'DSKEW 27FEB22 11.5 C', 'US23753F1158', 0, 2],
        [14, 'MYL', 2, 'MYLAN NV', 'NL0011031208', 0, -1],
        [15, 'VTRS', 2, 'VIATRIS INC-W/I', 'US92556V1061', 0, 2],
        [16, 'WAB', 2, 'WABTEC CORP', '', 0, 2],
        [17, 'TEF', 2, 'TELEFONICA SA-SPON ADR', 'US8793822086', 0, 2],
        [18, 'EQM', 2, 'EQM MIDSTREAM PARTNERS LP', 'US26885B1008', 0, 2],
        [19, 'ETRN', 2, 'EQUITRANS MIDSTREAM CORP', 'US2946001011', 0, 2],
        [20, 'GE', 2, 'GENERAL ELECTRIC CO', '', 0, 2],
        [21, 'EWLL', 2, 'EWELLNESS HEALTHCARE CORP', 'US30051D1063', 0, -1],
        [22, 'EWLL', 2, 'EWELLNESS HEALTHCARE CORP', 'US30051D2053', 0, -1],
        [23, 'ZROZ', 4, 'PIMCO 25+ YR ZERO CPN US TIF', 'US72201R8824', 2, 2],
        [24, 'LVGO', 2, 'LIVONGO HEALTH INC', 'US5391831030', 0, -1],
        [25, 'TDOC', 2, 'TELADOC HEALTH INC', 'US87918A1051', 0, 2],
        [26, 'AAPL', 2, 'APPLE INC', 'US0378331005', 0, 2],
        [27, 'VLO   200724P00064000', 6, 'VLO 24JUL20 64.0 P', '', 0, -1],
        [28, 'VLO', 2, 'VALERO ENERGY CORP', 'US91913Y1001', 0, 2],
        [29, 'MAC', 2, '', 'US5543821012', 0, 2]
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
        [2, 2, 5, '', -7.96, 0.0, 'BALANCE OF MONTHLY MINIMUM FEE FOR DEC 2019'],
        [3, 3, 5, '', 0.6905565, 0.0, 'COMMISS COMPUTED AFTER TRADE REPORTED (EWLL)'],
        [4, 4, 8, '', 0.5, 0.0, 'RUB CREDIT INT FOR MAY-2020'],
        [5, 5, 6, '', -0.249018, 0.0, 'BABA (ALIBABA GROUP HOLDING-SP ADR) - French Transaction Tax']
    ]
    assert readSQL("SELECT COUNT(amount) FROM action_details") == len(test_actions)
    for i, action in enumerate(test_actions):
        assert readSQL("SELECT * FROM action_details WHERE id=:id", [(":id", i+1)]) == action

    # validate transfers
    test_transfers = [
        [1, 1580443370, 5, 890.47, 1580443370, 1, 1000.0, 1, 3.0, '', 'IDEALFX'],
        [2, 1581322108, 2, 78986.6741, 1581322108, 1, 1234.0, 1, 2.0, '', 'IDEALFX'],
        [3, 1590522832, 2, 44.07, 1590522832, 1, 0.621778209, '', '', '', 'IDEALFX'],
        [4, 1600374600, 1, 123456.78, 1600374600, 2, 123456.78, '', '', '', 'CASH RECEIPTS / ELECTRONIC FUND TRANSFERS'],
        [5, 1605744000, 1, 1234.0, 1605744000, 1, 1234.0, '', '', '', 'DISBURSEMENT INITIATED BY John Doe']
    ]
    assert readSQL("SELECT COUNT(*) FROM transfers") == len(test_transfers)
    for i, transfer in enumerate(test_transfers):
        assert readSQL("SELECT * FROM transfers WHERE id=:id", [(":id", i+1)]) == transfer

    # validate trades
    test_trades = [
        [1, 1553545500, 1553545500, '', 1, 8, -0.777, 168.37, 0.0, ''],
        [2, 1579094694, 1579219200, '2661774904', 1, 21, 45000.0, 0.0012, 0.54, ''],
        [3, 1580215513, 1580215513, '2674740000', 1, 4, -1240.0, 54.84, 7.75519312, ''],
        [4, 1580215566, 1580342400, '2674740000', 1, 26, -148.0, 316.68, -1.987792848, ''],
        [5, 1590595065, 1590710400, '2882737839', 1, 11, 2.0, 637.09, 2.0, ''],
        [6, 1592575273, 1592784000, '2931083780', 1, 27, -100.0, 4.54, 1.1058334, ''],
        [7, 1595607600, 1595808000, '2997636969', 1, 27, 100.0, 0.0, 0.0, 'Option assignment'],
        [8, 1595607600, 1595607600, '2997636973', 1, 28, 100.0, 64.0, 0.0, 'Option assignment/exercise'],
        [9, 1603882231, 1604016000, '3183801882', 1, 22, 500000.0, 0.0001, 0.7503675, '']
    ]
    assert readSQL("SELECT COUNT(*) FROM trades") == len(test_trades)
    for i, trade in enumerate(test_trades):
        assert readSQL("SELECT * FROM trades WHERE id=:id", [(":id", i + 1)]) == trade

    # validate asset payments
    test_payments = [
        [1, 1529612400, '', '', 1, 1, 5, 16.76, 0.0, 'EDV (US9219107094) CASH DIVIDEND USD 0.8381 (Ordinary Dividend)'],
        [2, 1533673200, '', '', 1, 1, 5, 20.35, 0.54, 'EDV(US9219107094) CASH DIVIDEND 0.10175000 USD PER SHARE (Ordinary Dividend)'],
        [3, 1578082800, '', '', 1, 1, 23, 60.2, 6.02, 'ZROZ(US72201R8824) CASH DIVIDEND USD 0.86 PER SHARE (Ordinary Dividend)'],
        [4, 1590595065, '', '2882737839', 2, 1, 11, -25.69, 0.0, 'PURCHASE ACCRUED INT X 6 1/4 03/15/26'],
        [5, 1600128000, '', '', 2, 1, 11, 62.5, 0.0, 'BOND COUPON PAYMENT (X 6 1/4 03/15/26)']
    ]
    assert readSQL("SELECT COUNT(*) FROM dividends") == len(test_payments)
    for i, payment in enumerate(test_payments):
        assert readSQL("SELECT * FROM dividends WHERE id=:id", [(":id", i + 1)]) == payment

    # validate corp actions
    test_corp_actons = [
        [1, 1605731100, '10162291403', 1, 1, 10, 70.0, 9, 17.444, 1.0, 'DM(US2574541080) MERGED(Acquisition) WITH US25746U1097 2492 FOR 10000 (D, DOMINION ENERGY INC, 25746U109)'],
        [2, 1605558300, '14302257657', 1, 3, 14, 5.0, 15, 5.0, 1.0, 'MYL(NL0011031208) CUSIP/ISIN CHANGE TO (US92556V1061) (VTRS, VIATRIS INC-W/I, US92556V1061)'],
        [3, 1605817500, '10302900848', 1, 2, 20, 100.0, 16, 0.5371, 0.0, 'GE(US3696041033) SPINOFF  5371 FOR 1000000 (WAB, WABTEC CORP, 929740108)'],
        [4, 1595017200, '13259965038', 1, 5, 17, -1.0, 17, 3.0, 0.0, 'TEF (US8793822086) STOCK DIVIDEND US8793822086 416666667 FOR 10000000000 (TEF, TELEFONICA SA-SPON ADR, US8793822086)'],
        [5, 1592339100, '13006963996', 1, 1, 18, 70.0, 19, 170.8, 1.0, 'EQM(US26885B1008) MERGED(Acquisition) WITH US2946001011 244 FOR 100 (ETRN, EQUITRANS MIDSTREAM CORP, US2946001011)'],
        [6, 1581452700, '12029570527', 1, 4, 21, 45000.0, 22, 900.0, 1.0, 'EWLL(US30051D1063) SPLIT 1 FOR 50 (EWLLD, EWELLNESS HEALTHCARE CORP, US30051D2053)'],
        [7, 1604089500, '14147163475', 1, 1, 24, 10.0, 25, 5.92, 1.0, 'LVGO(US5391831030) CASH and STOCK MERGER (Acquisition) US87918A1051 592 FOR 1000 AND EUR 4.24 (TDOC, TELADOC HEALTH INC, US87918A1051)'],
        [8, 1591215600, '12882908488', 1, 5, 29, -1.0, 29, 2.0, 0.0, 'MAC (US5543821012) CASH DIVIDEND USD 0.10, STOCK DIVIDEND US5543821012 548275673 FOR 10000000000 (MAC, MACERICH CO/THE, US5543821012)'],
    ]
    assert readSQL("SELECT COUNT(*) FROM corp_actions") == len(test_corp_actons)
    for i, action in enumerate(test_corp_actons):
        assert readSQL("SELECT * FROM corp_actions WHERE id=:id", [(":id", i + 1)]) == action
