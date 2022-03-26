import json
import os

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from data_import.broker_statements.ibkr import StatementIBKR
from tests.helpers import create_assets, create_quotes, create_dividends, create_coupons, create_trades, \
    create_actions, create_corporate_actions, create_stock_dividends
from constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.data_export.taxes import TaxesRus
from jal.data_export.xlsx import XLSX


# ----------------------------------------------------------------------------------------------------------------------
def test_taxes_rus(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'taxes_rus.json', 'r') as json_file:
        report = json.load(json_file)

    assets = [
        (4, "GE", "General Electric Company", "US3696043013", 2, PredefinedAsset.Stock, 2),
        (5, "TLT", "iShares 20+ Year Treasury Bond ETF", "US4642874329", 2, PredefinedAsset.ETF, 2),
        (6, "ERIC", "Telefonaktiebolaget LM Ericsson B ADR", "US2948216088", 2, PredefinedAsset.ETF, 7),
        (7, "GOLD", "Barrick Gold Corp", "CA0679011084", 2, PredefinedAsset.ETF, 6),
        (8, "TEVA", "Teva Pharma Industries Ltd ADR", "US8816242098", 2, PredefinedAsset.Stock, 0),
        (9, "X 6 1/4 03/15/26", "X 6 1/4 03/15/26", "US912909AN84", 2, PredefinedAsset.Bond, 2),
        (10, "AAL   210115C00030000", "AAL 15JAN21 30.0 C", "", 2, PredefinedAsset.Derivative, 0),
        (11, "MYL", "MYLAN NV", "NL0011031208", 2, PredefinedAsset.Stock, 0),
        (12, "VTRS", "VIATRIS INC", "US92556V1061", 2, PredefinedAsset.Stock, 0)
    ]
    create_assets(assets)
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
        (1593205200, 1, 4, 2.0, 2, 53.4, 10.68, 'GE (US3696041033) Stock Dividend US3696041033 196232339 for 10000000000')
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
        (1608044400, 1608163200, 5, -25, 2.5, 0.35, "B2")
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
        (1605528000, 3, 11, 50, 12, 50, 1, "Symbol change MYL->VTRS"),
        (1604448000, 4, 5, 10, 5, 50, 1, "Split 5:1 of TLT")
    ]
    create_corporate_actions(1, corporate_actions)

    ledger = Ledger()    # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRus()
    tax_report = taxes.prepare_tax_report(2020, 1)
    assert tax_report == report


# ----------------------------------------------------------------------------------------------------------------------
def test_taxes_rus_bonds(tmp_path, project_root, data_path, prepare_db_taxes):
    with open(data_path + 'ibkr_bond.json', 'r') as json_file:
        statement = json.load(json_file)
    with open(data_path + 'taxes_bond_rus.json', 'r') as json_file:
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

    ledger = Ledger()  # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRus()
    tax_report = taxes.prepare_tax_report(2021, 1)
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
