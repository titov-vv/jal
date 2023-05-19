import json
import os
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from data_import.broker_statements.ibkr import StatementIBKR
from tests.helpers import d2t, create_assets, create_quotes, create_dividends, create_coupons, create_trades, \
    create_actions, create_corporate_actions, create_stock_dividends, json_decimal2float
from constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, CorporateAction, Dividend
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.taxes_flow import TaxesFlowRus
from jal.data_export.xlsx import XLSX


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
        (Dividend.StockDividend, 1593205200, 1, 4, 2.0, 2, 53.4, 10.68, 'GE (US3696041033) Stock Dividend US3696041033 196232339 for 10000000000')
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
        statement = json.load(json_file)
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
    LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, 1).set_result_share(JalAsset(5), Decimal('1.0'))

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2021, 1)
    json_decimal2float(tax_report)
    assert tax_report == report

    # reports_xls = XLSX(str(tmp_path) + os.sep + "taxes.xls")
    # templates = {
    #     "Облигации": "tax_rus_bonds.json",
    #     "Корп.события": "tax_rus_corporate_actions.json"
    # }
    # parameters = {
    #     "period": "01.01.2021 - 31.12.2021",
    #     "account": "TEST U7654321 (USD)",
    #     "currency": "USD",
    #     "broker_name": "IBKR",
    #     "broker_iso_country": "840"
    # }
    # for section in tax_report:
    #     if section not in templates:
    #         continue
    #     reports_xls.output_data(tax_report[section], templates[section], parameters)
    # reports_xls.save()


def test_taxes_stock_vesting(data_path, prepare_db_taxes):
    with open(data_path + 'taxes_vesting_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    assets = [
        ("VTRS", "VIATRIS INC", "US92556V1061", 2, PredefinedAsset.Stock, 0)   # ID = 4
    ]
    create_assets(assets)
    stock_dividends = [
        (Dividend.StockVesting, 1621641600, 1, 4, 11.0, 2, 22.53, 0.0, 'Stock vesting')
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
    json_decimal2float(tax_report)
    assert tax_report == report


def test_taxes_merger_complex(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_merger_complex.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
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
    action = LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, 1)
    action.set_result_share(JalAsset(5), Decimal('0.95'))
    action.set_result_share(JalAsset(4), Decimal('0.05'))

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2021, 1)

    with open(data_path + 'taxes_merger_complex_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    json_decimal2float(tax_report)
    assert tax_report == report

    # reports_xls = XLSX(str(tmp_path) + os.sep + "taxes.xls")
    # templates = {
    #     "Корп.события": "tax_rus_corporate_actions.json"
    # }
    # parameters = {
    #     "period": "01.01.2021 - 31.12.2021",
    #     "account": "TEST U7654321 (USD)",
    #     "currency": "USD",
    #     "broker_name": "IBKR",
    #     "broker_iso_country": "840"
    # }
    # for section in tax_report:
    #     if section not in templates:
    #         continue
    #     reports_xls.output_data(tax_report[section], templates[section], parameters)
    # reports_xls.save()


def test_taxes_spinoff(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_spinoff.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
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
    action = LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, 1)
    action.set_result_share(JalAsset(4), Decimal('0.9'))
    action.set_result_share(JalAsset(5), Decimal('0.1'))

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRussia()
    tax_report = taxes.prepare_tax_report(2021, 1)

    with open(data_path + 'taxes_spinoff_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    json_decimal2float(tax_report)
    assert tax_report == report

    # reports_xls = XLSX(str(tmp_path) + os.sep + "taxes.xls")
    # templates = {
    #     "Корп.события": "tax_rus_corporate_actions.json"
    # }
    # parameters = {
    #     "period": "01.01.2021 - 31.12.2021",
    #     "account": "TEST U7654321 (USD)",
    #     "currency": "USD",
    #     "broker_name": "IBKR",
    #     "broker_iso_country": "840"
    # }
    # for section in tax_report:
    #     if section not in templates:
    #         continue
    #     reports_xls.output_data(tax_report[section], templates[section], parameters)
    # reports_xls.save()


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

    json_decimal2float(tax_report)
    with open(data_path + 'taxes_over_years_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    assert tax_report == report

    # reports_xls = XLSX(str(tmp_path) + os.sep + "taxes.xls")
    # templates = {
    #     "Корп.события": "tax_rus_corporate_actions.json",
    #     "ПФИ": "tax_rus_derivatives.json"
    # }
    # parameters = {
    #     "period": "01.01.2021 - 31.12.2021",
    #     "account": "TEST U7654321 (USD)",
    #     "currency": "USD",
    #     "broker_name": "IBKR",
    #     "broker_iso_country": "840"
    # }
    # for section in tax_report:
    #     if section not in templates:
    #         continue
    #     reports_xls.output_data(tax_report[section], templates[section], parameters)
    # reports_xls.save()

# Load double IBKR statement with mergers and spin-offs
def test_taxes_merger_spinoff(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_merger_spinoff.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
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
    # 100% NTRP -> 100% PTPI
    action = LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, 1)
    action.set_result_share(JalAsset(5), Decimal('1.0'))
    # 100% NTRP -> 100% NTRP + 0% SNPX
    action = LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, 2)
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

    with open(data_path + 'taxes_merger_spinoff_rus.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    json_decimal2float(tax_report)
    assert tax_report == report

    # reports_xls = XLSX(str(tmp_path) + os.sep + "taxes.xls")
    # templates = {
    #     "Корп.события": "tax_rus_corporate_actions.json",
    # }
    # parameters = {
    #     "period": "01.01.2022 - 31.12.2022",
    #     "account": "TEST U7654321 (USD)",
    #     "currency": "USD",
    #     "broker_name": "IBKR",
    #     "broker_iso_country": "840"
    # }
    # for section in tax_report:
    #     if section not in templates:
    #         continue
    #     reports_xls.output_data(tax_report[section], templates[section], parameters)
    # reports_xls.save()


# Tests IBKR report with CFD short trades and dividends withdrawn for tax report preparation
def test_taxes_cfd_short_dividends(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_cfd.json', 'r', encoding='utf-8') as json_file:
        statement = json.load(json_file)
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
    json_decimal2float(tax_report)
    assert tax_report == report

    # reports_xls = XLSX(str(tmp_path) + os.sep + "taxes.xls")
    # templates = {
    #     "ПФИ": "tax_rus_derivatives.json",
    #     "Комиссии": "tax_rus_fees.json"
    # }
    # parameters = {
    #     "period": "01.01.2022 - 31.12.2022",
    #     "account": "TEST U7654321F (USD)",
    #     "currency": "USD",
    #     "broker_name": "IBKR",
    #     "broker_iso_country": "840"
    # }
    # for section in tax_report:
    #     if section not in templates:
    #         continue
    #     reports_xls.output_data(tax_report[section], templates[section], parameters)
    # reports_xls.save()
