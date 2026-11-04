import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_quotes, create_dividends
from jal.constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.db.account import JalAccountCreator
from jal.data_export.taxes import TaxReport, GAIN, INCOME
from jal.data_export.tax_parameters import TaxParameters


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
