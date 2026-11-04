import os
import pytest
import openpyxl
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_quotes, create_trades, create_dividends, create_actions, \
    create_corporate_actions, operation_id
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.ledger import Ledger
from jal.db.country import JalCountry
from jal.db.operations import LedgerTransaction, CorporateAction
from jal.data_export.taxes import TaxReportStop
from jal.db.tax_override import JalTaxOverride, TaxOverride
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.data_export.xlsx import XLSX

PARAMETERS = {"period": "01/01/2025 - 31/12/2025", "account": "U7654321 (USD)", "currency": "USD"}


# Account 1 in 2025: STK (us, ID 4) bought and sold, a dividend of STK (10 % withheld) and one of ERIC (se, ID 5,
# 30 % withheld), broker interest; one more STK dividend in 2024. Returns {name: operation id}.
def _year_2025() -> dict:
    create_assets([("STK", "Stock Corp", "US0000000501", 2, PredefinedAsset.Stock, 'us'),
                   ("ERIC", "Ericsson ADR", "US2948216088", 2, PredefinedAsset.Stock, 'se')])
    create_quotes(2, 1, [(d2t(240102), 100.0)])
    create_quotes(2, 3, [(d2t(240102), 0.9)])
    create_trades(1, [(d2t(250102), d2t(250104), 4, 10, 10, 0, "buy"), (d2t(250602), d2t(250604), 4, -10, 12, 0, "sell")])
    create_dividends([(d2t(240305), 1, 4, 5.0, 0.5, "STK 2024"), (d2t(250303), 1, 4, 10.0, 1.0, "STK 2025"),
                      (d2t(250401), 1, 5, 20.0, 6.0, "ERIC 2025")])
    create_actions([(d2t(250801), 1, 1, [(PredefinedCategory.Interest, 5.0, "USD CREDIT INT")])])
    Ledger().rebuild(from_timestamp=0)
    return {'stk_2024': operation_id(LedgerTransaction.AssetPayment, 1),
            'stk': operation_id(LedgerTransaction.AssetPayment, 2),
            'eric': operation_id(LedgerTransaction.AssetPayment, 3),
            'sell': operation_id(LedgerTransaction.Trade, 2),
            'interest': operation_id(LedgerTransaction.IncomeSpending, 1)}


def _rows(section, template) -> list:
    return [x for x in section if x['report_template'] == template]


def _decisions(report, taxes) -> list:
    return [x['decision'] for x in _rows(report[taxes.summary_section[0]], "decision")]


def test_no_overrides_no_decisions(prepare_db_taxes):
    _year_2025()
    for taxes in (TaxesRussia(), TaxesPortugal()):
        report = taxes.prepare_tax_report(2025, 1)
        assert _rows(report[taxes.summary_section[0]], "decisions") == []
        assert _rows(report[taxes.uncovered_section[0]], "operation") == []


# Not a tax event: the section leaves the operation out, "Not covered" lists it under the note, the Summary lists the
# decision; the other jurisdiction's report doesn't see it
def test_excluded_operations_ru(prepare_db_taxes):
    oid = _year_2025()
    JalTaxOverride.set('ru', oid['eric'], TaxOverride.NotTaxEvent, '', "Return of capital")
    JalTaxOverride.set('ru', oid['interest'], TaxOverride.NotTaxEvent, '', "Refund of a fee")
    JalTaxOverride.set('ru', oid['stk_2024'], TaxOverride.NotTaxEvent, '', "Other year")
    taxes = TaxesRussia()
    report = taxes.prepare_tax_report(2025, 1)

    dividends = _rows(report["Дивиденды"], "dividend")
    assert [x['symbol'] for x in dividends] == ["STK"]
    assert _rows(report["Дивиденды"], "totals")[0]['amount_rub'] == Decimal('1000')
    assert report["Проценты"] == []
    assert len(_rows(report["Акции"], "trade")) == 1
    uncovered = _rows(report[taxes.uncovered_section[0]], "operation")
    assert [x['reason'] for x in uncovered] == [taxes.texts['excluded'].format("Return of capital"),
                                                taxes.texts['excluded'].format("Refund of a fee")]
    assert _rows(report[taxes.summary_section[0]], "decisions")[0]['title'] == taxes.texts['decisions']
    decisions = _rows(report[taxes.summary_section[0]], "decision")
    assert [x['operation'] for x in decisions] == ["01.04.2025 Дивиденд ERIC", "01.08.2025 Денежная операция"]
    assert [x['decision'] for x in decisions] == [f"{taxes.texts['override_excluded']}: Return of capital",
                                                  f"{taxes.texts['override_excluded']}: Refund of a fee"]

    pt = TaxesPortugal()
    pt_report = pt.prepare_tax_report(2025, 1)
    assert [x['symbol'] for x in _rows(pt_report["Dividends"], "dividend")] == ["STK", "ERIC"]
    assert _decisions(pt_report, pt) == []


# A deal is excluded by its closing operation, in its own jurisdiction only
def test_excluded_deal_pt(prepare_db_taxes):
    oid = _year_2025()
    JalTaxOverride.set('pt', oid['sell'], TaxOverride.NotTaxEvent, '', "Transfer in kind")
    pt = TaxesPortugal()
    report = pt.prepare_tax_report(2025, 1)
    assert report["Shares"] == []
    assert [x['reason'] for x in _rows(report[pt.uncovered_section[0]], "operation")] == \
           [pt.texts['excluded'].format("Transfer in kind")]
    assert _decisions(report, pt) == [f"{pt.texts['override_excluded']}: Transfer in kind"]
    assert len(_rows(TaxesRussia().prepare_tax_report(2025, 1)["Акции"], "trade")) == 1


# Treaty: the decision on one dividend wins over the parameters, and the estimate follows it
def test_treaty_override(prepare_db_taxes):
    oid = _year_2025()
    taxes = TaxesRussia()
    stk, eric = _rows(taxes.prepare_tax_report(2025, 1)["Дивиденды"], "dividend")
    assert (stk['tax_treaty'], stk['tax2pay']) == ("Да", Decimal('30'))   # 13 % of 1000 less 100 withheld
    assert (eric['tax_treaty'], eric['tax2pay']) == ("Да", Decimal('0'))

    JalTaxOverride.set('ru', oid['stk'], TaxOverride.Treaty, TaxOverride.NoTreaty, "Broker lost its treaty status")
    JalTaxOverride.set('pt', oid['eric'], TaxOverride.Treaty, TaxOverride.TreatyApplies, "Treaty claimed at source")
    report = taxes.prepare_tax_report(2025, 1)
    stk, eric = _rows(report["Дивиденды"], "dividend")
    assert (stk['tax_treaty'], stk['tax2pay']) == ("Нет", Decimal('130'))
    assert (eric['tax_treaty'], eric['tax2pay']) == ("Да", Decimal('0'))
    assert _decisions(report, taxes) == [f"{taxes.texts['override_no_treaty']}: Broker lost its treaty status"]
    assert _rows(report[taxes.uncovered_section[0]], "operation") == []

    pt = TaxesPortugal()
    pt_report = pt.prepare_tax_report(2025, 1)
    assert [x['tax_treaty'] for x in _rows(pt_report["Dividends"], "dividend")] == ["Y", "Y"]   # 'se' has none
    assert _decisions(pt_report, pt) == [f"{pt.texts['override_treaty']}: Treaty claimed at source"]


# The two rows of the decision block reach the Summary sheet
def test_decisions_reach_the_workbook(prepare_db_taxes, tmp_path):
    oid = _year_2025()
    JalTaxOverride.set('pt', oid['eric'], TaxOverride.NotTaxEvent, '', "Return of capital")
    pt = TaxesPortugal()
    report = pt.prepare_tax_report(2025, 1)
    file = str(tmp_path) + os.sep + "report.xlsx"
    xlsx = XLSX(file)
    for section in report:
        xlsx.output_data(report[section], pt.report_template(section), PARAMETERS, headers=pt.section_headers(section))
    assert xlsx.save()
    sheet = openpyxl.load_workbook(file)["Summary"]
    cells = [(sheet.cell(row=r, column=1).value, sheet.cell(row=r, column=2).value) for r in range(1, sheet.max_row + 1)]
    assert cells[-2:] == [(pt.texts['decisions'], None),
                          ("01.04.2025 Dividend ERIC", f"{pt.texts['override_excluded']}: Return of capital")]


# Account 1 in 2025: 10 MRG (ID 4) bought, merged into 5 NEWCO (ID 5) and 25.5 USD of cash. Returns the merger's id.
def _cash_merger(country) -> int:
    create_assets([("MRG", "Merger Corp", "CA0000000401", 2, PredefinedAsset.Stock, country),
                   ("NEWCO", "New Corp", "CA0000000501", 2, PredefinedAsset.Stock, 'ca')])
    create_quotes(2, 1, [(d2t(240102), 100.0)])
    create_trades(1, [(d2t(250102), d2t(250104), 4, 10, 10, 0, "buy")])
    create_corporate_actions(1, [(d2t(250701), CorporateAction.Merger, 4, 10, "Merger MRG->NEWCO + cash",
                                  [(5, 5.0, 1.0), (2, 25.5, 0.0)])])
    Ledger().rebuild(from_timestamp=0)
    return operation_id(LedgerTransaction.CorporateAction, 1)


# The cash of a corporate action is paid by the broker in its country, or - by the user's decision - by the asset's
# issuer in the asset's country; the Summary lists the decision
def test_asset_source_override(prepare_db_taxes):
    merger = _cash_merger('ca')
    payer = lambda report: [{k: x[k] for k in ('payer', 'country', 'country_code')}
                            for x in _rows(report["Проценты"], "interest")]
    taxes = TaxesRussia()
    assert payer(taxes.prepare_tax_report(2025, 1)) == \
           [{'payer': 'None', 'country': JalCountry(2).name(language='ru'), 'country_code': 'us'}]
    JalTaxOverride.set('ru', merger, TaxOverride.AssetSource, TaxOverride.AssetCountry, "Cash paid by the issuer")
    report = taxes.prepare_tax_report(2025, 1)
    canada = JalCountry(data={'code': 'ca'}, search=True)
    assert payer(report) == [{'payer': 'Merger Corp', 'country': canada.name(language='ru'), 'country_code': 'ca'}]
    assert _decisions(report, taxes) == [f"{taxes.texts['override_asset_source']}: Cash paid by the issuer"]


# The override needs the asset's country: without one the report stops and names the asset
def test_asset_source_without_country_stops(prepare_db_taxes):
    merger = _cash_merger(0)
    JalTaxOverride.set('ru', merger, TaxOverride.AssetSource, TaxOverride.AssetCountry, "Cash paid by the issuer")
    with pytest.raises(TaxReportStop) as stop:
        TaxesRussia().prepare_tax_report(2025, 1)
    assert stop.value.missing == [] and stop.value.no_country == ["MRG (Merger Corp)"]


def test_asset_source_values(prepare_db_taxes):
    merger = _cash_merger('ca')
    with pytest.raises(ValueError):
        JalTaxOverride.set('ru', merger, TaxOverride.AssetSource, '0', "Wrong value")
    assert TaxOverride.takes_asset_source(LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, merger))
