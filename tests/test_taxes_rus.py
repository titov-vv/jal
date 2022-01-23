import os
import json


from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import create_assets, create_quotes, create_dividends, create_trades, create_actions
from jal.db.ledger import Ledger
from jal.data_export.taxes import TaxesRus


# ----------------------------------------------------------------------------------------------------------------------
def test_taxes_rus(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'taxes_rus.json', 'r') as json_file:
        report = json.load(json_file)

    assets = [
        ("GE", "General Electric Company", "US3696043013", 2, 2),
        ("TLT", "iShares 20+ Year Treasury Bond ETF", "US4642874329", 4, 2),
        ("ERIC", "Telefonaktiebolaget LM Ericsson B ADR", "US2948216088", 2, 7),
        ("GOLD", "Barrick Gold Corp", "CA0679011084", 2, 6),
        ("TEVA", "Teva Pharma Industries Ltd ADR", "US8816242098", 2, 0)
    ]
    create_assets(assets)
    usd_rates = [
        (1569456000, 64.1873), (1569369600, 63.706), (1569283200, 63.9453), (1569024000, 63.8487),
        (1582243200, 63.7413), (1582156800, 63.6873), (1582070400, 63.7698), (1581984000, 63.3085),
        (1554163200, 65.4176), (1553904000, 64.7347), (1553817600, 64.8012), (1553731200, 64.5925),
        (1550016000, 65.7147), (1549929600, 65.6517), (1549670400, 66.0628), (1549584000, 66.0199),
        (1579910400, 61.8031),
        (1581033600, 62.7977),
        (1587513600, 76.2562),
        (1605039600, 76.9515)
    ]
    create_quotes(2, usd_rates)
    dividends = [
        (1580156400, 1, 4, 1.0, 0.1, "GE(US3696041033) CASH DIVIDEND USD 0.01 PER SHARE (Ordinary Dividend)"),
        (1581106800, 1, 5, 16.94, 0, "TLT(US4642874329) CASH DIVIDEND USD 0.241966 PER SHARE (Ordinary Dividend)"),
        (1587586800, 1, 6, 3.74, 1.12, "ERIC(US2948216088) CASH DIVIDEND USD 0.074728 PER SHARE (Ordinary Dividend)")
    ]
    create_dividends(dividends)
    trades = [
        (1569334259, 1569456000, 7, 10, 18.74, 0.32825725, "0001"),
        (1582116724, 1582243200, 7, -10, 20.95, 0.3370772, "0002"),
        (1549881381, 1550016000, 8, 4, 18.52, 0.34625725, "0000000003"),
        (1553861071, 1554163200, 8, 1, 15.8, 0.34995725, "0000000004"),
        (1582117021, 1582243200, 8, -5, 13.23, 0.33137108, "0000000005")
    ]
    create_trades(1, trades)

    # insert fee
    create_actions([(1605039600, 1, 1, [(5, -1.0, "ERIC(294821608) ADR Fee USD 0.02 PER SHARE - FEE")])])

    ledger = Ledger()    # Build ledger to have FIFO deals table
    ledger.rebuild(from_timestamp=0)

    taxes = TaxesRus()
    excel_file = str(tmp_path) + os.sep + 'taxes.xlsx'
    tax_report = taxes.save2file(excel_file, 2020, 1)
    assert tax_report == report

    os.remove(excel_file)  # cleanup
