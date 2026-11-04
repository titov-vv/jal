import json

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from decimal import Decimal

from tests.helpers import d2t, dt2t, create_assets, create_quotes, create_dividends, create_trades, create_actions, create_coupons, \
    create_corporate_actions, create_stock_dividends, json_decimal2float, symbol_id_for, figure_fingerprint
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, CorporateAction, AssetIncome, AssetPayment
from jal.data_export.irs_modelo3 import IRS_Modelo3
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
    # Default is one rate, the disposal's (CIRS a.23); a short converts at its opening sale's rate
    tax_report = TaxesPortugal().prepare_tax_report(2024, 1)
    json_decimal2float(tax_report)
    assert tax_report == expected['default']

    assert figure_fingerprint(tax_report, "Summary", "Not covered") == \
           figure_fingerprint(expected['default'], "Summary", "Not covered")

    tax_report = TaxesPortugal().prepare_tax_report(2024, 1, use_one_currency_rate=False)
    json_decimal2float(tax_report)
    assert tax_report['Shares'] == expected['two_rates_shares']


# The Modelo 3 lines are made of the Shares rows: one per deal, in EUR
def test_modelo3_lines_follow_the_shares_rows(prepare_db_taxes):
    create_pt_scenario()
    report = TaxesPortugal().prepare_tax_report(2024, 1)
    form = IRS_Modelo3()
    form.update_taxes(report, {'broker_iso_country': '840'})
    line = "<AnexoJq092AT01-Linha><CodPais>840</CodPais><Codigo>{}</Codigo><AnoRealizacao>{}</AnoRealizacao>" \
           "<MesRealizacao>{}</MesRealizacao><DiaRealizacao>{}</DiaRealizacao><ValorRealizacao>{}</ValorRealizacao>" \
           "<AnoAquisicao>{}</AnoAquisicao><MesAquisicao>{}</MesAquisicao><DiaAquisicao>{}</DiaAquisicao>" \
           "<ValorAquisicao>{}</ValorAquisicao><DespesasEncargos>{}</DespesasEncargos>" \
           "<RespeitaValoresMobiliarios>S</RespeitaValoresMobiliarios></AnexoJq092AT01-Linha>"
    assert form._tax_form.splitlines() == [
        line.format("G01", 2024, 3, 12, "1647.00", 2023, 11, 15, "1372.50", "2.01"),
        line.format("G01", 2024, 7, 8, "508.20", 2024, 1, 10, "462.00", "1.39"),
        line.format("G01", 2024, 9, 3, "417.15", 2024, 4, 2, "463.50", "1.85"),   # short: values as exported today
        line.format("G01", 2024, 10, 15, "2019.60", 2024, 2, 1, "1836.00", "1.84"),
        line.format("G01", 2024, 12, 30, "576.00", 2024, 1, 10, "480.00", "1.44")
    ]


# Costs of holding grouped by kind, then the broker's fees; each of them marked printed
def test_fees_sheet(prepare_db_taxes):
    create_assets([("ERIC", "Ericsson ADR", "US2948216088", 2, PredefinedAsset.Stock, 'se')])   # ID 4
    create_quotes(2, 3, [(d2t(240101), 0.9)])
    for subtype, note in ((AssetPayment.DepositaryFee, "ADR Fee"), (AssetPayment.AssetFee, "Some asset tax")):
        LedgerTransaction.create_new(LedgerTransaction.AssetPayment, {
            'timestamp': d2t(240510), 'type': subtype, 'account_id': 1, 'symbol_id': symbol_id_for(4),
            'amount': '-2', 'tax': '0', 'note': note})
    create_actions([(d2t(240601), 1, 1, [(PredefinedCategory.Fees, -10.0, "Monthly fee")])])
    Ledger().rebuild(from_timestamp=0)

    report = TaxesPortugal().prepare_tax_report(2024, 1)
    rows = [(x['fee_type'], x['description'], x['amount'], x['amount_eur']) for x in report['Fees'][:-1]]
    assert rows == [("Depositary fee", "ERIC: ADR Fee", Decimal('2'), Decimal('1.80')),
                    ("Other asset fee or tax", "ERIC: Some asset tax", Decimal('2'), Decimal('1.80')),
                    ("Broker fee", "Monthly fee", Decimal('10'), Decimal('9.00'))]
    assert report['Not covered'] == []


# Crypto income is listed at its quote for information; without a quote it shows 0 and says so
def test_crypto_income_without_quote(prepare_db_taxes):
    create_assets([("SOL", "Solana", "", 2, PredefinedAsset.Crypto, 0), ("NEW", "No quote coin", "", 2, PredefinedAsset.Crypto, 0)])
    create_quotes(2, 3, [(d2t(240101), 0.9)])
    create_quotes(4, 2, [(d2t(240201), 100.0)])
    for asset_id, subtype in ((4, AssetIncome.StakingReward), (5, AssetIncome.Reward)):
        LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
            'timestamp': d2t(240202), 'type': subtype, 'account_id': 1, 'symbol_id': symbol_id_for(asset_id),
            'amount': '2', 'tax': '0', 'number': '', 'note': 'income'})
    Ledger().rebuild(from_timestamp=0)

    report = TaxesPortugal().prepare_tax_report(2024, 1)
    rows = [(x['symbol'], x['price'], x['value_eur'], x['note']) for x in report['Crypto income'][:-1]]
    assert rows == [("SOL", Decimal('100'), Decimal('180.00'), ''),
                    ("NEW", Decimal('0'), Decimal('0.00'), "quotation is not present in database")]


# The fingerprint holds the same figures wherever their rows stand, and tells a changed figure
def test_figure_fingerprint(data_path):
    with open(data_path + 'taxes_pt.json', 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)['default']
    fingerprint = figure_fingerprint(report, "Summary", "Not covered")
    moved = {"Summary": [], "All": [x for name, section in report.items() if name not in ("Summary", "Not covered")
                                    for x in section if x['report_template'] != "totals"], "Not covered": []}
    moved["All"] = [{(k if k == 'report_template' else f"renamed_{k}"): v for k, v in x.items()} for x in reversed(moved["All"])]
    assert figure_fingerprint(moved, "Summary", "Not covered") == fingerprint
    moved["All"][0] = {k: (v + 0.01 if isinstance(v, float) else v) for k, v in moved["All"][0].items()}
    assert figure_fingerprint(moved, "Summary", "Not covered") != fingerprint


# 2025, 1 USD = 0.9 EUR: a bond B (ID 4) with accrued interest paid on purchase and received on sale and a coupon between,
# an option D (ID 5), and crypto C (ID 6) - one lot held 735 days, one held 28 days
def _g_category_scenario():
    create_assets([("B", "Bond B", "US0000000B01", 2, PredefinedAsset.Bond, 'us'),
                   ("D", "Option D", "", 2, PredefinedAsset.Derivative, 'us'),
                   ("C", "Coin C", "", 2, PredefinedAsset.Crypto, 0)])
    create_quotes(2, 3, [(d2t(220102), 0.9)])
    create_trades(1, [(d2t(250102), d2t(250104), 4, 2, 1000, 1, "bb"), (d2t(250602), d2t(250604), 4, -2, 1010, 1, "bs"),
                      (d2t(250110), d2t(250110), 5, 1, 50, 1, "db"), (d2t(250210), d2t(250210), 5, -1, 70, 1, "ds"),
                      (d2t(230101), d2t(230101), 6, 1, 100, 0, "c1"), (d2t(250105), d2t(250105), 6, -1, 150, 0, "c2"),
                      (d2t(250201), d2t(250201), 6, 1, 200, 0, "c3"), (d2t(250301), d2t(250301), 6, -1, 210, 0, "c4")])
    create_coupons([(d2t(250102), 1, 4, -10.0, 0.0, "accrued paid", "bb"), (d2t(250301), 1, 4, 25.0, 0.0, "coupon", ""),
                    (d2t(250602), 1, 4, 5.0, 0.0, "accrued received", "bs")])
    Ledger().rebuild(from_timestamp=0)


# Bonds and derivatives are category G deals at their price; bond interest received is category E, that paid with a
# purchase is skipped; crypto splits at 365 days
def test_g_category_sheets(prepare_db_taxes):
    _g_category_scenario()
    taxes = TaxesPortugal()
    report = taxes.prepare_tax_report(2025, 1)
    bond, bond_totals = report["Bonds"]
    assert (bond['code'], bond['o_amount_eur'], bond['c_amount_eur'], bond['profit_eur']) == \
           ('G10', Decimal('1800.00'), Decimal('1818.00'), Decimal('16.20'))
    assert taxes.texts['bond_accrued'] in taxes.section_headers("Bonds")
    option, _ = report["Derivatives"]
    assert (option['code'], option['o_amount_eur'], option['c_amount_eur'], option['profit_eur']) == \
           ('G30', Decimal('45.00'), Decimal('63.00'), Decimal('16.20'))
    interest = [(x['description'], x['amount_eur'], x['code']) for x in report["Interest"] if x['report_template'] == "interest"]
    assert interest == [("Bond interest B: coupon", Decimal('22.50'), 'E21'),
                        ("Bond interest B: accrued received", Decimal('4.50'), 'E21')]
    long_held, _ = report["Crypto ≥ 365 days"]
    short_held, _ = report["Crypto < 365 days"]
    assert (long_held['c_number'], long_held['days'], 'code' in long_held) == ("c2", 735, False)
    assert (short_held['c_number'], short_held['days']) == ("c4", 28)
    assert taxes.texts['quadro_g1'] in taxes.section_headers("Crypto ≥ 365 days")
    assert taxes.texts['quadro_94a'] in taxes.section_headers("Crypto < 365 days")
    skipped = [x for x in report["Not covered"] if x['report_template'] == "skipped"]
    assert [(x['reason'], x['count']) for x in skipped] == [(taxes.texts['accrued_paid'], "Skipped by rule: 1")]
    assert [x for x in report["Not covered"] if x['report_template'] == "operation"] == []
