import json
import pytest
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_quotes, create_dividends, create_trades, create_actions
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.ledger import Ledger
from jal.db.account import JalAccountCreator
from jal.data_export.taxes import TaxReport, GAIN, INCOME
from jal.data_export.tax_parameters import TaxParameters
from jal.data_export.ru_ndfl3 import Ru_NDFL3, FOREIGN_SECTION


# Each section of a report is in exactly one base or outside them all, and the sheets follow the bases' order
@pytest.mark.parametrize("code", list(TaxReport.jurisdictions))
def test_bases_list_every_section_in_order(prepare_db_taxes, code):
    report = TaxReport.create_report(code)
    assert all(kind in (GAIN, INCOME) and sections for _title, kind, sections in report.bases)
    assert [x for _title, _kind, sections in report.bases for x in sections] + report.outside == list(report.reports)


# A row's code comes from the parameters, except on an account of the jurisdiction's own country
@pytest.mark.parametrize("code, country, expected", [
    ('ru', 'us', ('1530', '201')), ('ru', 'ru', ('', '')), ('ru', 'pt', ('1530', '201')),
    ('pt', 'us', ('G01', '')), ('pt', 'pt', ('', '')), ('pt', 'ru', ('G01', ''))
])
def test_code_left_out_on_home_accounts(prepare_db_taxes, code, country, expected):
    account = JalAccountCreator(currency_id=2, number='H1', name='Home', investing=1, country=country).commit()
    report = TaxReport.create_report(code)
    report.prepare_tax_report(2025, account.id())
    assert report.code(TaxParameters.STOCK) == expected
    assert report.code("unknown") == ('', '')


# A dividend through a home-country account has no code, and its section says why
def test_home_account_rows_have_no_code(prepare_db_taxes):
    account = JalAccountCreator(currency_id=2, number='H1', name='Home', investing=1, country='ru').commit()
    create_assets([("AAPL", "Apple Inc", "US0378331005", 2, PredefinedAsset.Stock, 'us')])
    create_quotes(2, 1, [(d2t(250101), 100.0)])
    create_dividends([(dt2t(2505151430), account.id(), 4, 100.0, 10.0, "AAPL CASH DIVIDEND")])
    Ledger().rebuild(from_timestamp=0)
    report = TaxReport.create_report('ru')
    rows = report.prepare_tax_report(2025, account.id())["Дивиденды"]
    assert [x['code'] for x in rows if x['report_template'] == "dividend"] == ['']
    assert report.texts['home_codes'] in report.section_headers("Дивиденды")
    form = Ru_NDFL3(2025)    # the export reads the code by the row's kind, so the row is filed all the same
    form.update_taxes({"Дивиденды": rows}, {'currency': 'USD', 'broker_name': 'Bank', 'broker_iso_country': '643'})
    assert [x['IncomeCod'] for x in form._tax_form[FOREIGN_SECTION]] == ['1010']


# Every base total of a recorded report is the sum of its sections' own totals, and the RU 13/15 % line the signed sum
# of its bases with the interest of Russian payers
@pytest.mark.parametrize("file, path, code", [
    ('taxes_rus.json', [], 'ru'), ('taxes_cfd_rus.json', [], 'ru'), ('taxes_merger_complex_rus.json', [], 'ru'),
    ('taxes_crypto.json', ['ru'], 'ru'), ('taxes_pt.json', ['default'], 'pt'), ('taxes_crypto.json', ['pt'], 'pt')])
def test_base_totals_sum_their_sections(prepare_db, data_path, file, path, code):
    with open(data_path + file, 'r', encoding='utf-8') as json_file:
        report = json.load(json_file)
    for key in path:
        report = report[key]
    taxes = TaxReport.create_report(code)
    suffix = taxes.currency_suffix
    summary = report[taxes.summary_section[0]]
    totals = lambda name: ([x for x in report[name] if x['report_template'] == "totals"] or [{}])[0]
    for title, kind, sections in taxes.bases:
        fields = ('spending', 'income', 'profit') if kind == GAIN else ('amount', 'value')
        expected = {}
        for field in fields:
            values = [totals(x)[field + suffix] for x in sections if totals(x).get(field + suffix) is not None]
            if values:
                expected['gross' if kind == INCOME else field] = round(sum(values), 2)
        start = summary.index({'report_template': "base", 'title': title}) + 1
        end = next(i for i in range(start, len(summary)) if summary[i]['report_template'] in ("base", "base_sum"))
        found = {x['figure'].split(': ', 1)[1]: round(x['amount'], 2) for x in summary[start:end]
                 if x['report_template'] == "base_total"}
        assert found == {taxes.texts[k]: v for k, v in expected.items()}, title
    if code == 'ru':
        expected = sum(totals(x).get('profit_rub', 0) for x in ("Акции", "Облигации", "ПФИ", "Криптовалюты")) + \
            sum(x['amount_rub'] for x in report["Дивиденды"] if x['report_template'] == "dividend") + \
            sum(x['amount_rub'] for x in report["Проценты"] if x['report_template'] == "interest" and x['country_code'] == 'ru')
        line, = [x for x in summary if x['report_template'] == "base_sum"]
        assert round(line['amount'], 2) == round(expected, 2)


# A loss stays negative in the RU 13/15 % line, and interest paid by a Russian bank is in it
def test_rate_sum_keeps_a_loss(prepare_db_taxes):
    account = JalAccountCreator(currency_id=2, number='H1', name='Home', investing=1, country='ru').commit()
    create_assets([("AAPL", "Apple Inc", "US0378331005", 2, PredefinedAsset.Stock, 'us')])
    create_quotes(2, 1, [(d2t(250101), 100.0)])
    create_trades(account.id(), [(d2t(250102), d2t(250102), 4, 10, 10, 0), (d2t(250202), d2t(250202), 4, -10, 8, 0)])
    create_actions([(d2t(250301), account.id(), 1, [(PredefinedCategory.Interest, 5.0, "Deposit interest")])])
    Ledger().rebuild(from_timestamp=0)
    taxes = TaxReport.create_report('ru')
    summary = taxes.prepare_tax_report(2025, account.id())[taxes.summary_section[0]]
    line, = [x for x in summary if x['report_template'] == "base_sum"]
    assert line['amount'] == Decimal('-1500.00')    # (8 - 10) * 10 USD at 100 RUB, plus 5 USD of interest
