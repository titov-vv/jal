import json
import logging
import pytest
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from jal.data_import.broker_statements.ibkr import StatementIBKR
from tests.helpers import d2t, create_assets, create_quotes, create_dividends, create_coupons, create_trades, \
    create_actions, create_corporate_actions, create_stock_dividends, json_decimal2float, save_test_xls_report, \
    nth_operation, symbol_id_for, create_swaps, check_ndfl3_export
from jal.constants import PredefinedAsset, PredefinedCategory, AssetLocation, SymbolId
from jal.db.ledger import Ledger
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, CorporateAction, AssetPayment, AssetIncome
from jal.data_export.taxes import TaxReportStop
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.data_export.taxes_flow import TaxesFlowRus


# ----------------------------------------------------------------------------------------------------------------------
def test_taxes_rus(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'taxes_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)

    assets = [
        ("GE", "General Electric Company", "US3696043013", 2, PredefinedAsset.Stock, 'us'),   # ID 4 - > 14
        ("TLT", "iShares 20+ Year Treasury Bond ETF", "US4642874329", 2, PredefinedAsset.ETF, 'us'),
        ("ERIC", "Telefonaktiebolaget LM Ericsson B ADR", "US2948216088", 2, PredefinedAsset.ETF, 'se'),
        ("GOLD", "Barrick Gold Corp", "CA0679011084", 2, PredefinedAsset.ETF, 'ca'),
        ("TEVA", "Teva Pharma Industries Ltd ADR", "US8816242098", 2, PredefinedAsset.Stock, 0),
        ("X 6 1/4 03/15/26", "X 6 1/4 03/15/26", "US912909AN84", 2, PredefinedAsset.Bond, 'us'),
        ("AAL   210115C00030000", "AAL 15JAN21 30.0 C", "", 2, PredefinedAsset.Derivative, 0),
        ("MYL", "MYLAN NV", "NL0011031208", 2, PredefinedAsset.Stock, 0),
        ("VTRS", "VIATRIS INC", "US92556V1061", 2, PredefinedAsset.Stock, 0),
        ("DEL", "DELISTED STOCK", "US12345X0000", 2, PredefinedAsset.Stock, 0),
        ("BTC", "Bitcoin", "", 2, PredefinedAsset.Crypto, 0)
    ]
    create_assets(assets, data=[(9, 'principal', "1000")])
    usd_rates = [
        (1569456000, 64.1873), (1569369600, 63.706), (1569283200, 63.9453), (1569024000, 63.8487),
        (1582243200, 63.7413), (1582156800, 63.6873), (1582070400, 63.7698), (1581984000, 63.3085),
        (1554163200, 65.4176), (1553904000, 64.7347), (1553817600, 64.8012), (1553731200, 64.5925),
        (1550016000, 65.7147), (1549929600, 65.6517), (1549670400, 66.0628), (1549584000, 66.0199),
        (1579132800, 61.4328), (1579046400, 61.414), (1578960000, 60.9474), (1578700800, 61.2632),
        (1582934400, 66.9909), (1582848000, 65.6097), (1582761600, 65.5177), (1582675200, 64.9213),
        (1590710400, 71.1012), (1590624000, 71.0635), (1590537600, 71.1408), (1590451200, 71.5962),
        (1604448000, 80.0006), (1604361600, 80.5749), (1604102400, 79.3323), (1604016000, 78.8699),
        (1593820800, 70.4999), (1593734400, 70.5198), (1593648000, 70.4413), (1593561600, 70.4413),
        (1608163200, 73.4201), (1608076800, 73.4453), (1607990400, 72.9272), (1607731200, 73.1195),
        (1579910400, 61.8031),
        (1581033600, 62.7977),
        (1587513600, 76.2562),
        (1605039600, 76.9515),
        (1600128000, 74.7148),
        (1591142400, 68.9831),
        (1593129600, 69.4660)
    ]
    create_quotes(2, 1, usd_rates)
    dividends = [
        (1580156400, 1, 4, 1.0, 0.1, "GE(US3696041033) CASH DIVIDEND USD 0.01 PER SHARE (Ordinary Dividend)"),
        (1581106800, 1, 5, 16.94, 0, "TLT(US4642874329) CASH DIVIDEND USD 0.241966 PER SHARE (Ordinary Dividend)"),
        (1587586800, 1, 6, 3.74, 1.12, "ERIC(US2948216088) CASH DIVIDEND USD 0.074728 PER SHARE (Ordinary Dividend)")
    ]
    create_dividends(dividends)
    stock_dividends = [
        (AssetIncome.StockDividend, 1593205200, 1, 4, 2.0, 2, 53.4, 10.68, 'GE (US3696041033) Stock Dividend US3696041033 196232339 for 10000000000')
    ]
    create_stock_dividends(stock_dividends)
    coupons = [
        (1590587855, 1, 9, -25.69, 0, "PURCHASE ACCRUED INT X 6 1/4 03/15/26", "2881234567"),
        (1600128000, 1, 9, 62.5, 0, "BOND COUPON PAYMENT (X 6 1/4 03/15/26)", ""),
        (1604319194, 1, 9, 16.89, 0, "SALE ACCRUED INT X 6 1/4 03/15/26", "2881234589")
    ]
    create_coupons(coupons)
    trades = [
        (1569334259, 1569456000, 7, 10, 18.74, 0.32825725, "0001"),
        (1582116724, 1582243200, 7, -10, 20.95, 0.3370772, "0002"),
        (1549881381, 1550016000, 8, 4, 18.52, 0.34625725, "0000000003"),
        (1553861071, 1554163200, 8, 1, 15.8, 0.34995725, "0000000004"),
        (1582117021, 1582243200, 8, -5, 13.23, 0.33137108, "0000000005"),
        (1579097059, 1579132800, 10, -100, 2.94, 0.8018858, "2661844383"),
        (1582886521, 1583107200, 10, 100, 1.31, 1.0938, "2716375310"),
        (1590587855, 1590710400, 9, 2, 639.07, 2, "2881234567"),
        (1604319194, 1604448000, 9, -2, 800, 2, "2881234589"),
        (1593604800, 1593993600, 11, 50, 15.9, 0.35, "1118233222"),
        (1608044400, 1608163200, 12, -50, 17.71, 0.35, "2227095222"),
        (1593604800, 1593993600, 5, 10, 10.0, 0.35, "A"),
        (1608044400, 1608163200, 5, -25, 3.0, 0.35, "B1"),
        (1608044400, 1608163200, 5, -25, 2.5, 0.35, "B2"),
        (1607871600, 1608044400, 13, 10, 11, 0.5, "1000000001"),
        (1607871600, 1608044400, 14, 0.001, 35123, 0, "crypto-buy"),
        (1608044400, 1608163200, 14, -0.001, 36321, 0, "crypto-sell")
    ]
    create_trades(1, trades)

    # insert fees and interest
    operations = [
        (1604343555, 1, 1, [(5, -10.0, "BALANCE OF MONTHLY MINIMUM FEE FOR OCT 2020")]),
        (1605039600, 1, 1, [(5, -1.0, "ERIC(294821608) ADR Fee USD 0.02 PER SHARE - FEE")]),
        (1591142400, 1, 1, [(8, 1.5, "RUB CREDIT INT FOR MAY-2020")])
    ]
    create_actions(operations)

    corporate_actions = [
        (1605528000, CorporateAction.SymbolChange, 11, 50, "Symbol change MYL->VTRS", [(12, 50.0, 1.0)]),
        (1604448000, CorporateAction.Split, 5, 10, "Split 5:1 of TLT", [(5, 50.0, 1.0)]),
        (1608217200, CorporateAction.Delisting, 13, 10, "Delisting of DEL", [(13, 0.0, 1.0)])
    ]
    create_corporate_actions(1, corporate_actions)

    ledger = Ledger()    # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2020, 1)
    check_ndfl3_export(tax_report, data_path, 'rus_2020')
    check_ndfl3_export(tax_report, data_path, 'rus_2020_broker', broker_as_income=True)
    check_ndfl3_export(tax_report, data_path, 'rus_2020_dividends', only_dividends=True)
    json_decimal2float(tax_report)
    assert tax_report == report

    # Flow report test - it needs transactions' data so can't be detached in a separate test
    with open(data_path + 'taxes_flow.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)

    taxes_flow = TaxesFlowRus()
    flow_reports = taxes_flow.prepare_flow_report(2020)
    for flow_report in flow_reports:
        json_decimal2float(flow_report)
    assert flow_reports == report


# ----------------------------------------------------------------------------------------------------------------------
def test_taxes_rus_bonds(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_bond.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file, parse_float=Decimal)
    with open(data_path + 'taxes_bond_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)

    usd_rates = [
        (1632441600, 72.7245), (1629936000, 73.7428), (1631664000, 72.7171), (1622073600, 73.4737),
        (1621987200, 73.3963), (1621900800, 73.5266), (1621641600, 73.5803), (1632528000, 73.0081)
    ]
    create_quotes(2, 1, usd_rates)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_bond.xml')
    assert IBKR._data == statement

    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()

    # Adjust share of result allocation to 100% of initial bond
    nth_operation(LedgerTransaction.CorporateAction, 1).set_result_share(JalAsset(5), Decimal('1.0'))

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2021, 1)
    check_ndfl3_export(tax_report, data_path, 'bond')
    json_decimal2float(tax_report)
    assert tax_report == report

    # save_test_xls_report(tmp_path, tax_report)


def test_taxes_stock_vesting(data_path, prepare_db_taxes):
    with open(data_path + 'taxes_vesting_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    assets = [
        ("VTRS", "VIATRIS INC", "US92556V1061", 2, PredefinedAsset.Stock, 0)   # ID = 4
    ]
    create_assets(assets)
    stock_dividends = [
        (AssetIncome.StockVesting, 1621641600, 1, 4, 11.0, 2, 22.53, 0.0, 'Stock vesting')
    ]
    create_stock_dividends(stock_dividends)
    test_trades = [
        (1632528000, 1632700800, 4, -11.0, 27.14, 1.0)  # Sell vested stocks
    ]
    create_trades(1, test_trades)
    usd_rates = [
        (1621641600, 73.5803), (1632528000, 73.3963), (1632700800, 73.5266)
    ]
    create_quotes(2, 1, usd_rates)

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 1
    assert trades[0].profit() == Decimal('49.71')

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2021, 1)
    check_ndfl3_export(tax_report, data_path, 'vesting')
    json_decimal2float(tax_report)
    assert tax_report == report


def test_taxes_merger_complex(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_merger_complex.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file, parse_float=Decimal)
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_merger_complex.xml')
    assert IBKR._data == statement

    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()

    usd_rates = [
        (1630972800, 72.9538), (1631145600, 73.4421), (1631491200, 72.7600), (1631664000, 72.7171),
        (1632441600, 72.7245), (1632787200, 72.6613), (1633478400, 72.5686), (1633651200, 72.2854),
        (1634601600, 71.1714), (1634774400, 71.0555)
    ]
    create_quotes(2, 1, usd_rates)

    # Adjust share of resulting assets: 100% SRNGU -> 95% DNA + 5% DNA WS
    action = nth_operation(LedgerTransaction.CorporateAction, 1)
    action.set_result_share(JalAsset(5), Decimal('0.95'))
    action.set_result_share(JalAsset(4), Decimal('0.05'))

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2021, 1)
    check_ndfl3_export(tax_report, data_path, 'merger_complex')

    with open(data_path + 'taxes_merger_complex_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    json_decimal2float(tax_report)
    assert tax_report == report

    # save_test_xls_report(tmp_path, tax_report)


def test_taxes_spinoff(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_spinoff.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file, parse_float=Decimal)
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_spinoff.xml')
    assert IBKR._data == statement

    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()

    usd_rates = [
        (1635760683, 72.9538), (1635897600, 73.4421), (1637679039, 72.7600), (1637798400, 72.7171),
        (1638370239, 72.7245), (1638489600, 72.6613)
    ]
    create_quotes(2, 1, usd_rates)

    # Adjust share of resulting assets: 100% GE -> 90% GE + 10% WAB
    action = nth_operation(LedgerTransaction.CorporateAction, 1)
    action.set_result_share(JalAsset(4), Decimal('0.9'))
    action.set_result_share(JalAsset(5), Decimal('0.1'))

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2021, 1)
    check_ndfl3_export(tax_report, data_path, 'spinoff')

    with open(data_path + 'taxes_spinoff_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    json_decimal2float(tax_report)
    assert tax_report == report

    # save_test_xls_report(tmp_path, tax_report)


def test_taxes_over_years(tmp_path, project_root, data_path, prepare_db_taxes):
    # Load first year
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_year0.xml')
    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()
    # Load second year
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_year1.xml')
    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()

    usd_rates = [
        (1604880000, 77.1875), (1604966400, 76.9515), (1623196800, 72.8256), (1623283200, 72.0829),
        (1607040000, 75.1996), (1607299200, 74.2529), (1620691200, 74.1373), (1620777600, 74.1567),
        (1610582400, 73.5264), (1611014400, 73.9735), (1606435200, 75.4518), (1606780800, 76.1999),
        (1612828800, 73.8453), (1613001600, 73.6059), (1606953600, 75.6151)
    ]
    create_quotes(2, 1, usd_rates)

    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2021, 1)
    check_ndfl3_export(tax_report, data_path, 'over_years')

    json_decimal2float(tax_report)
    with open(data_path + 'taxes_over_years_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    assert tax_report == report

    # save_test_xls_report(tmp_path, tax_report)


# Load double IBKR statement with mergers and spin-offs
def test_taxes_merger_spinoff(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_merger_spinoff.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file, parse_float=Decimal)
    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_merger_spinoff.xml', index=0)   # Load statement for the first year
    assert IBKR._data == statement[0]

    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()

    usd_rates = [
        (d2t(210905), 72.8545), (d2t(210907), 72.9538), (d2t(210909), 73.4421), (d2t(211126), 74.6004),
        (d2t(211201), 74.8926), (d2t(220518), 63.5428), (d2t(221130), 61.0742)
    ]
    create_quotes(2, 1, usd_rates)

    # Adjust share of resulting assets:
    # Merger: 100% NTRP -> 100% PTPI
    action = nth_operation(LedgerTransaction.CorporateAction, 1)
    action.set_result_share(JalAsset(5), Decimal('1.0'))
    # Spin-off: 100% NTRP -> 100% NTRP + 0% SNPX
    action = nth_operation(LedgerTransaction.CorporateAction, 2)
    action.set_result_share(JalAsset(4), Decimal('1.0'))

    ledger = Ledger()  # Build ledger to have everything in place
    ledger.rebuild(from_timestamp=0)

    IBKR.load(data_path + 'ibkr_merger_spinoff.xml', index=1)  # Load statement for the second year
    assert IBKR._data == statement[1]

    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()

    ledger.rebuild(from_timestamp=0)  # re-build after second year loading

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2022, 1)
    check_ndfl3_export(tax_report, data_path, 'merger_spinoff')

    with open(data_path + 'taxes_merger_spinoff_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    json_decimal2float(tax_report)
    assert tax_report == report

    # save_test_xls_report(tmp_path, tax_report)


# Tests IBKR report with CFD short trades and dividends withdrawn for tax report preparation
def test_taxes_cfd_short_dividends(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_cfd.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file, parse_float=Decimal)
    with open(data_path + 'taxes_cfd_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)

    usd_rates = [
        (d2t(220706), 58.5118), (d2t(220707), 62.9110), (d2t(220708), 63.1427), (d2t(220711), 61.2664),
        (d2t(220726), 57.7821)
    ]
    create_quotes(2, 1, usd_rates)

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_cfd.xml')
    assert IBKR._data == statement

    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2022, 2)  # Account '7654321F' will be here
    check_ndfl3_export(tax_report, data_path, 'cfd')
    json_decimal2float(tax_report)
    assert tax_report == report

    # save_test_xls_report(tmp_path, tax_report)


# ----------------------------------------------------------------------------------------------------------------------
# A short call that a split of its underlying asset turned from 1 contract into 2 and that expired worthless:
# the premium (185.00 USD at 80 RUB) is the income, the commission of the sale (0.62869 USD) is the only expense
def test_taxes_short_option_adjusted_by_split(tmp_path, data_path, prepare_db_taxes):
    create_quotes(2, 1, [(d2t(251101), 80.0), (d2t(251226), 78.0), (d2t(251229), 77.0)])

    IBKR = StatementIBKR()
    IBKR.load(data_path + 'ibkr_option_split.xml')
    IBKR.validate_format()
    IBKR.match_db_ids()
    IBKR.import_into_db()

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    deal, totals = TaxesRussia().prepare_tax_report(2025, 1)['ПФИ']
    expected = {
        'report_template': 'corporate_action', 'o_type': 'Продажа', 'c_type': 'Покупка',
        'o_qty': Decimal('-100'), 'o_price': Decimal('1.85'), 'o_amount': Decimal('185.00'),
        'o_fee': Decimal('0.62869'), 'o_fee_rub': Decimal('50.30'),
        'c_qty': Decimal('-200'), 'c_price': Decimal('0'), 'c_amount': Decimal('0.00'), 'c_fee': Decimal('0'),
        'income': Decimal('185.00'), 'income_rub': Decimal('14800.00'), 'spending_rub': Decimal('50.30'),
        'profit': Decimal('184.37'), 'profit_rub': Decimal('14749.70')
    }
    assert {key: deal[key] for key in expected} == expected
    assert 'SPLIT 2 FOR 1 (XLE 251226C00046750' in deal['note']
    assert (totals['income_rub'], totals['spending_rub']) == (Decimal('14800.00'), Decimal('50.30'))


# ----------------------------------------------------------------------------------------------------------------------
# The flow report sorts its rows by account number, and a cash account, a wallet or a deposit carries none. An absent
# number has to sort beside the numbers that are there rather than crash the report - which is every report of this
# kind, as an account without a number is the common case abroad.
def test_flow_report_lists_an_account_that_carries_no_number(prepare_db):
    numbered = JalAccountCreator(currency_id=2, number='U7654321', name='Broker', investing=1, country='us').commit()
    numberless = JalAccountCreator(currency_id=2, number='', name='Rental deposit', country='pt').commit()
    create_actions([(d2t(200601), numbered.id(), 1, [(PredefinedCategory.Interest, Decimal('100'))]),
                    (d2t(200601), numberless.id(), 1, [(PredefinedCategory.Interest, Decimal('250'))])])
    Ledger().rebuild(from_timestamp=0)

    assert numberless.number() == ''
    report = TaxesFlowRus().prepare_flow_report(2020)
    assert [(x['account'], x['account_name'], x['money_in']) for x in report] == \
           [('', 'Rental deposit', Decimal('0.25')), ('U7654321', 'Broker', Decimal('0.1'))]


# ----------------------------------------------------------------------------------------------------------------------
# A bond price is reported as a percentage of the face value, but the face value may be absent - it isn't provided by
# every statement. The report has to be produced anyway (only the price cells are left empty) and to say in the log
# which bond needs the face value to be filled in.
def test_bond_without_face_value_prints_prices_per_bond(prepare_db_taxes, caplog):
    create_assets([("SU26216RMFS0", "ОФЗ 26216", "RU000A0JXQK2", 2, PredefinedAsset.Bond, 'ru')])   # ID 4, no principal
    create_trades(1, [(d2t(210315), d2t(210317), 4, 10.0, 950.0, 1.0, "B1"),
                      (d2t(211011), d2t(211013), 4, -10.0, 980.0, 1.0, "S1"),
                      (d2t(211101), d2t(211103), 4, 5.0, 990.0, 1.0, "B2"),
                      (d2t(211201), d2t(211203), 4, -5.0, 995.0, 1.0, "S2")])
    create_quotes(2, 1, [(d2t(210315), 73.5), (d2t(210317), 73.6), (d2t(211011), 72.0), (d2t(211013), 72.1),
                         (d2t(211101), 71.0), (d2t(211103), 71.1), (d2t(211201), 74.0), (d2t(211203), 74.1)])
    Ledger().rebuild(from_timestamp=0)

    assert JalAsset(4).principal() == Decimal('0')
    with caplog.at_level(logging.WARNING):
        tax_report = TaxesRussia().prepare_tax_report(2021, 1)

    trades = [x for x in tax_report["Облигации"] if x['report_template'] == "bond_trade"]
    assert [(x['o_price'], x['c_price']) for x in trades] == [(Decimal('950'), Decimal('980')),
                                                             (Decimal('990'), Decimal('995'))]
    assert all('principal' not in x for x in trades)
    assert trades[0]['profit'] == Decimal('298')   # (980 - 950) * 10 - 2 of fees
    assert [x.message for x in caplog.records if x.levelno == logging.WARNING] == []


# ----------------------------------------------------------------------------------------------------------------------
# One asset with two listings: bought as OLDT, renamed inside the asset, then paid and sold as NEWT. Each report row
# prints the ticker and ISIN of its own operation's listing, not the asset's first ISIN and current ticker.
def test_reports_print_the_listing_of_each_operation(prepare_db_taxes):
    create_assets([("OLDT", "Old Name Corp", "US0000000011", 2, PredefinedAsset.Stock, 'us')])   # ID 4
    old_listing = symbol_id_for(4)
    new_listing = JalAsset(4).add_symbol("NEWT", 2, AssetLocation.UNDEFINED)
    JalAsset(4).add_identifier(new_listing, SymbolId.ISIN, "US0000000029")
    create_trades(1, [(d2t(240304), d2t(240306), 4, 10.0, 100.0, 1.0, "B1")])   # on the old listing
    LedgerTransaction.create_new(LedgerTransaction.CorporateAction, {
        'timestamp': d2t(240603), 'account_id': 1, 'type': CorporateAction.SymbolChange, 'symbol_id': old_listing,
        'qty': 10.0, 'note': 'OLDT -> NEWT', 'outcome': [{'symbol_id': new_listing, 'qty': 10.0, 'value_share': 1.0}]})
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment, {
        'timestamp': d2t(240902), 'type': AssetPayment.Dividend, 'account_id': 1, 'symbol_id': new_listing,
        'amount': 5.0, 'tax': 0.5, 'note': 'NEWT CASH DIVIDEND'})
    LedgerTransaction.create_new(LedgerTransaction.Trade, {
        'timestamp': d2t(241104), 'settlement': d2t(241106), 'account_id': 1, 'symbol_id': new_listing,
        'qty': -10.0, 'price': 120.0, 'fee': 1.0, 'number': 'S1'})
    dates = [d2t(x) for x in (240304, 240306, 240603, 240902, 241104, 241106)]
    create_quotes(2, 1, [(x, 90.0) for x in dates])
    create_quotes(2, 3, [(x, 0.9) for x in dates])
    Ledger().rebuild(from_timestamp=0)

    ru = TaxesRussia().prepare_tax_report(2024, 1)
    deal = ru['Акции'][0]
    assert (deal['o_symbol'], deal['o_isin']) == ("OLDT", "US0000000011")
    assert (deal['c_symbol'], deal['c_isin']) == ("NEWT", "US0000000029")
    assert (ru['Дивиденды'][0]['symbol'], ru['Дивиденды'][0]['isin']) == ("NEWT", "US0000000029")

    pt = TaxesPortugal().prepare_tax_report(2024, 1)
    assert (pt['Shares'][0]['symbol'], pt['Shares'][0]['isin']) == ("NEWT", "US0000000029")
    assert (pt['Dividends'][0]['symbol'], pt['Dividends'][0]['isin']) == ("NEWT", "US0000000029")


# ----------------------------------------------------------------------------------------------------------------------
# A spin-off whose child was also bought on the market before it: the spun-off lot is acquired at the
# spin-off, so the market lot goes first in FIFO. Figures computed by hand:
# A 100 @ 10 -> spin-off 80% A + 50 B at 20% (basis 200, 4 per share); B 10 @ 30 bought between; sold 20 @ 35, 40 @ 40.
def test_spinoff_child_bought_before_the_spinoff(prepare_db_taxes):
    create_assets([("AAA", "Parent Corp", "US0000000101", 2, PredefinedAsset.Stock, 'us'),      # ID 4
                   ("BBB", "Spun Corp", "US0000000102", 2, PredefinedAsset.Stock, 'us')])       # ID 5
    create_quotes(2, 1, [(d2t(240101), 100.0)])   # USD/RUB
    create_quotes(2, 3, [(d2t(240101), 0.5)])     # USD/EUR
    create_trades(1, [(d2t(240110), d2t(240112), 4, 100.0, 10.0, 0.0, "B1"),
                      (d2t(240210), d2t(240212), 5, 10.0, 30.0, 0.0, "B2"),
                      (d2t(240603), d2t(240605), 5, -20.0, 35.0, 0.0, "S1"),
                      (d2t(240902), d2t(240904), 5, -40.0, 40.0, 0.0, "S2")])
    create_corporate_actions(1, [(d2t(240301), CorporateAction.SpinOff, 4, 100.0, "Spin-off BBB",
                                  [(4, 100.0, 0.8), (5, 50.0, 0.2)])])
    Ledger().rebuild(from_timestamp=0)

    fields = ('o_number', 'o_date', 'c_number', 'c_qty', 'spending_rub', 'profit', 'profit_rub')
    deals = [{k: x[k] for k in fields} for x in TaxesRussia().prepare_tax_report(2024, 1)['Акции'][:-1]]
    assert deals == [
        {'o_number': 'B2', 'o_date': d2t(240210), 'c_number': 'S1', 'c_qty': Decimal('10'),
         'spending_rub': Decimal('30000.00'), 'profit': Decimal('50.00'), 'profit_rub': Decimal('5000.00')},
        {'o_number': 'B1', 'o_date': d2t(240301), 'c_number': 'S1', 'c_qty': Decimal('10'),
         'spending_rub': Decimal('4000.00'), 'profit': Decimal('310.00'), 'profit_rub': Decimal('31000.00')},
        {'o_number': 'B1', 'o_date': d2t(240301), 'c_number': 'S2', 'c_qty': Decimal('40'),
         'spending_rub': Decimal('16000.00'), 'profit': Decimal('1440.00'), 'profit_rub': Decimal('144000.00')}]

    fields = ('o_number', 'o_date', 'c_number', 'qty', 'o_amount_eur', 'profit_eur')
    deals = [{k: x[k] for k in fields} for x in TaxesPortugal().prepare_tax_report(2024, 1)['Shares'][:-1]]
    assert deals == [
        {'o_number': 'B2', 'o_date': d2t(240210), 'c_number': 'S1', 'qty': Decimal('10'),
         'o_amount_eur': Decimal('150.00'), 'profit_eur': Decimal('25.00')},
        {'o_number': 'B1', 'o_date': d2t(240301), 'c_number': 'S1', 'qty': Decimal('10'),
         'o_amount_eur': Decimal('20.00'), 'profit_eur': Decimal('155.00')},
        {'o_number': 'B1', 'o_date': d2t(240301), 'c_number': 'S2', 'qty': Decimal('40'),
         'o_amount_eur': Decimal('80.00'), 'profit_eur': Decimal('720.00')}]


# ----------------------------------------------------------------------------------------------------------------------
# A position that vanished without proceeds is reported nowhere, while a sale next to it is
@pytest.mark.parametrize("action", [CorporateAction.Delisting, CorporateAction.WriteOff])
def test_lost_position_stays_out_of_tax_reports(prepare_db_taxes, action):
    create_assets([("STK", "Lost stock", "US0000000001", 2, PredefinedAsset.Stock, 'us'),     # ID 4
                   ("LOST", "Lost coin", "", 2, PredefinedAsset.Crypto, 0),                   # ID 5
                   ("SOLD", "Sold coin", "", 2, PredefinedAsset.Crypto, 0)])                  # ID 6
    rates = [(1607731200, 73.1195), (1607990400, 72.9272), (1608076800, 73.4453), (1608163200, 73.4201)]
    create_quotes(2, 1, rates)
    create_quotes(2, 3, [(x[0], 0.82) for x in rates])
    create_trades(1, [(1607871600, 1608044400, 4, 10, 11, 0.5, "stk-buy"),
                      (1607871600, 1608044400, 5, 2, 30, 0, "lost-buy"),
                      (1607871600, 1608044400, 6, 3, 40, 0, "sold-buy"),
                      (1608044400, 1608163200, 6, -3, 45, 0, "sold-sell")])
    create_corporate_actions(1, [(1608217200, action, 4, 10, "Gone", []), (1608217200, action, 5, 2, "Gone", [])])
    Ledger().rebuild(from_timestamp=0)

    reports = json.dumps([TaxesRussia().prepare_tax_report(2020, 1), TaxesPortugal().prepare_tax_report(2020, 1)],
                         default=str)
    assert "SOLD" in reports
    assert "STK" not in reports and "LOST" not in reports


# ----------------------------------------------------------------------------------------------------------------------
# A swap is a disposal at market value in RU, where the lot it opens is sold at that value; skipped by rule in PT,
# where that lot carries the purchase's cost
def test_swap_is_a_disposal_in_ru_and_skipped_in_pt(prepare_db_taxes):
    create_assets([("AAA", "Coin A", "", 2, PredefinedAsset.Crypto, 0),     # ID 4
                   ("BBB", "Coin B", "", 2, PredefinedAsset.Crypto, 0)])    # ID 5
    t_buy, t_swap, t_sell = d2t(201201), d2t(201210), d2t(201215)
    create_quotes(2, 1, [(t_buy, 75.0), (t_swap, 74.0), (t_sell, 73.0)])
    create_quotes(2, 3, [(t_buy, 0.83), (t_swap, 0.82), (t_sell, 0.81)])
    create_quotes(4, 2, [(t_swap, 15.0)])                                   # 10 A are worth 150 USD at the swap
    create_trades(1, [(t_buy, t_buy, 4, 10, 10, 1, "buy-A")])
    create_swaps(1, [(t_swap, 4, 10, 5, 30)])
    create_trades(1, [(t_sell, t_sell, 5, -30, 6, 0.5, "sell-B")])
    Ledger().rebuild(from_timestamp=0)

    swap_deals = JalAccount(1).closed_trades_list(close_otypes=(LedgerTransaction.Trade, LedgerTransaction.Swap))
    assert [(x.asset().id(), x.profit()) for x in swap_deals] == [(4, Decimal('49')), (5, Decimal('29.5'))]

    report = TaxesRussia().prepare_tax_report(2020, 1)
    assert [k for k, v in report.items() if v] == ["Сводка", "Криптовалюты"]
    swap, deal, totals = report["Криптовалюты"]
    assert {k: swap[k] for k in ('symbol', 'o_number', 'o_amount_rub', 'o_fee_rub', 'c_amount_rub', 'spending_rub',
                                 'profit_rub')} == \
           {'symbol': "AAA", 'o_number': "buy-A", 'o_amount_rub': Decimal('7500.00'), 'o_fee_rub': Decimal('75.00'),
            'c_amount_rub': Decimal('11100.00'), 'spending_rub': Decimal('7575.00'), 'profit_rub': Decimal('3525.00')}
    assert {k: deal[k] for k in ('symbol', 'qty', 'o_number', 'o_date', 'o_rate', 'o_price', 'o_amount_rub', 'o_fee',
                                 'c_number', 'c_date', 'c_amount_rub', 'c_fee_rub', 'spending_rub', 'profit',
                                 'profit_rub')} == \
           {'symbol': "BBB", 'qty': Decimal('30'), 'o_number': '', 'o_date': t_swap, 'o_rate': Decimal('74'),
            'o_price': Decimal('5'), 'o_amount_rub': Decimal('11100.00'), 'o_fee': Decimal('0'),
            'c_number': "sell-B", 'c_date': t_sell, 'c_amount_rub': Decimal('13140.00'), 'c_fee_rub': Decimal('36.50'),
            'spending_rub': Decimal('11136.50'), 'profit': Decimal('29.50'), 'profit_rub': Decimal('2003.50')}
    assert totals['report_template'] == "totals" and totals['profit_rub'] == Decimal('5528.50')
    report = TaxesPortugal().prepare_tax_report(2020, 1)
    assert [k for k, v in report.items() if v] == ["Summary", "Crypto < 365 days", "Not covered"]
    skipped, = report["Not covered"]
    assert (skipped['reason'], skipped['count']) == \
           ("Crypto-for-crypto exchange: not taxed until exit to fiat (CIRS art. 10.º, n.º 20)", "Skipped by rule: 1")
    sale, _totals = report["Crypto < 365 days"]   # the purchase's cost carried through the swap, its clock restarted
    assert {k: sale[k] for k in ('c_number', 'o_number', 'o_date', 'o_amount', 'o_amount_eur', 'c_amount_eur',
                                 'spending_eur', 'profit_eur')} == \
           {'c_number': "sell-B", 'o_number': "buy-A", 'o_date': t_swap, 'o_amount': Decimal('100.00'),
            'o_amount_eur': Decimal('81.00'), 'c_amount_eur': Decimal('145.80'), 'spending_eur': Decimal('82.22'),
            'profit_eur': Decimal('63.58')}


# Crypto income is valued at its quote on receipt: without one the RU report stops and names it
def test_crypto_income_without_quote_stops_the_report(prepare_db_taxes):
    create_assets([("SOL", "Solana", "", 2, PredefinedAsset.Crypto, 0), ("NEW", "No quote coin", "", 2, PredefinedAsset.Crypto, 0)])
    create_quotes(2, 1, [(d2t(250101), 100.0)])
    create_quotes(4, 2, [(d2t(250201), 150.0)])
    for asset_id in (4, 5):
        LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
            'timestamp': d2t(250202), 'type': AssetIncome.StakingReward, 'account_id': 1,
            'symbol_id': symbol_id_for(asset_id), 'amount': '2', 'tax': '0', 'number': '', 'note': 'reward'})
    Ledger().rebuild(from_timestamp=0)

    with pytest.raises(TaxReportStop) as stop:
        TaxesRussia().prepare_tax_report(2025, 1)
    assert stop.value.missing == [("NEW", d2t(250202))]
    create_quotes(5, 2, [(d2t(250202), 1.0)])
    income = TaxesRussia().prepare_tax_report(2025, 1)["Криптодоход"]
    assert [(x['symbol'], x['value_rub']) for x in income[:-1]] == [("SOL", Decimal('30000.00')), ("NEW", Decimal('200.00'))]


# The RU report converts at CBR rates only: a USD/RUB rate that exists only as a cross through EUR stops it
def test_missing_cbr_rate_stops_the_report(prepare_db_taxes):
    create_assets([("STK", "Stock Corp", "US0000000601", 2, PredefinedAsset.Stock, 'us')])   # ID 4
    create_quotes(2, 3, [(d2t(250101), 0.9)])        # USD/EUR (ECB)
    create_quotes(1, 3, [(d2t(250101), 0.01)])       # RUB/EUR (ECB) - together a cross-rate, not a CBR rate
    create_trades(1, [(d2t(250102), d2t(250104), 4, 10, 10, 0, "buy"), (d2t(250602), d2t(250604), 4, -10, 12, 0, "sell")])
    Ledger().rebuild(from_timestamp=0)

    with pytest.raises(TaxReportStop) as stop:
        TaxesRussia().prepare_tax_report(2025, 1)
    assert ("USD/RUB", d2t(250604)) in stop.value.missing
