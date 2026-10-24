import json

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_quotes, create_dividends, create_trades, create_actions, \
    create_corporate_actions, create_stock_dividends, json_decimal2float
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.ledger import Ledger
from jal.db.operations import CorporateAction, AssetIncome
from jal.data_export.tax_reports.portugal import TaxesPortugal


# ----------------------------------------------------------------------------------------------------------------------
# A USD account reported in EUR for 2024; expected values in taxes_pt.json are computed by hand from the rates below
def create_pt_scenario():
    assets = [
        ("AAPL", "Apple Inc", "US0378331005", 2, PredefinedAsset.Stock, 'us'),               # ID 4
        ("VWRL", "Vanguard FTSE All-World ETF", "IE00B3RBWM25", 2, PredefinedAsset.ETF, 'ie'),  # ID 5
        ("XYZ", "XYZ Holdings Ltd", "KYG000000001", 2, PredefinedAsset.Stock, 'ky'),         # ID 6
        ("SPLT", "Split Corp", "US0000000002", 2, PredefinedAsset.Stock, 'us'),              # ID 7
        ("MRG", "Merged Corp", "US0000000003", 2, PredefinedAsset.Stock, 'us'),              # ID 8
        ("NEWCO", "New Corp", "US0000000004", 2, PredefinedAsset.Stock, 'us')                # ID 9
    ]
    create_assets(assets)
    usd_eur = [
        (d2t(231115), 0.9200), (d2t(240110), 0.9100), (d2t(240201), 0.9230), (d2t(240215), 0.9300),
        (d2t(240312), 0.9150), (d2t(240402), 0.9270), (d2t(240510), 0.9280), (d2t(240603), 0.9210),
        (d2t(240620), 0.9250), (d2t(240708), 0.9240), (d2t(240801), 0.9190), (d2t(240903), 0.9050),
        (d2t(241015), 0.9180), (d2t(241104), 0.9230), (d2t(241230), 0.9600)
    ]
    create_quotes(2, 3, usd_eur)
    create_actions([
        (d2t(230101), 1, 1, [(PredefinedCategory.StartingBalance, 20000.0)]),
        (dt2t(2312011430), 1, 1, [(PredefinedCategory.Interest, 2.0, "USD CREDIT INT FOR NOV-2023")]),  # other year
        (dt2t(2408011430), 1, 1, [(PredefinedCategory.Interest, 3.5, "USD CREDIT INT FOR JUL-2024")])
    ])
    create_dividends([
        (dt2t(2402151430), 1, 4, 24.0, 3.6, "AAPL(US0378331005) CASH DIVIDEND USD 0.24 PER SHARE"),
        (dt2t(2402201430), 1, 4, -24.0, -3.6, "AAPL(US0378331005) CASH DIVIDEND USD 0.24 PER SHARE - REVERSAL"),
        (dt2t(2405101430), 1, 6, 10.0, 0.0, "XYZ(KYG000000001) CASH DIVIDEND USD 1.00 PER SHARE")
    ])
    create_trades(1, [
        (dt2t(2311151430), d2t(231117), 4, 10, 150.0, 1.0, "T01"),
        (dt2t(2403121430), d2t(240314), 4, -10, 180.0, 1.2, "T02"),
        (dt2t(2401101430), d2t(240112), 5, 20, 100.0, 2.0, "T03"),
        (dt2t(2407081430), d2t(240710), 5, -5, 110.0, 1.0, "T04"),
        (dt2t(2412301430), d2t(250102), 5, -5, 120.0, 1.0, "T05"),   # settles in 2025 - out of the 2024 report
        (dt2t(2404021430), d2t(240404), 6, -10, 50.0, 1.0, "T06"),   # short
        (dt2t(2409031430), d2t(240905), 6, 10, 45.0, 1.0, "T07"),
        (dt2t(2402011430), d2t(240205), 7, 10, 200.0, 1.0, "T08"),
        (dt2t(2410151430), d2t(241017), 7, -20, 110.0, 1.0, "T09"),
        (dt2t(2401101500), d2t(240112), 8, 10, 30.0, 0.0, "T10")
    ])
    create_stock_dividends([
        (AssetIncome.StockDividend, dt2t(2406201430), 1, 5, 2.0, 2, 100.0, 0.0, "VWRL Stock Dividend 1 for 10")
    ])
    create_corporate_actions(1, [
        (dt2t(2406031430), CorporateAction.Split, 7, 10, "Split 2:1 of SPLT", [(7, 20.0, 1.0)]),
        (dt2t(2411041430), CorporateAction.Merger, 8, 10, "Merger MRG->NEWCO + cash", [(9, 5.0, 1.0), (2, 25.5, 0.0)])
    ])
    Ledger().rebuild(from_timestamp=0)


# ----------------------------------------------------------------------------------------------------------------------
def test_taxes_pt(tmp_path, data_path, prepare_db_taxes):
    with open(data_path + 'taxes_pt.json', 'r', encoding='utf-8') as json_file:
        expected = json.load(json_file)
    create_pt_scenario()

    # Hand check: amount_eur = round(amount * rate, 2); profit_eur = c_amount_eur - (o_amount_eur + round(fees_eur, 2))
    # Frozen as is: Shares totals sum 'income_eur'/'spending_eur' that no row has; SPLT's o_price is the
    # pre-split 200 beside qty 20; T05 is dropped by its 2025 settlement though portugal.py cites CIRS a.44 for trade date
    tax_report = TaxesPortugal().prepare_tax_report(2024, 1)
    json_decimal2float(tax_report)
    assert tax_report == expected['default']

    tax_report = TaxesPortugal().prepare_tax_report(2024, 1, use_one_currency_rate=True)
    json_decimal2float(tax_report)
    assert tax_report['Shares'] == expected['one_currency_rate_shares']
