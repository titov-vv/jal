from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_quotes, create_trades
from jal.constants import PredefinedAsset
from jal.db.ledger import Ledger
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.data_export.ru_ndfl3 import Ru_NDFL3, FOREIGN_SECTION
from jal.data_export.irs_modelo3 import IRS_Modelo3


# 1 USD = 100 RUB = 0.9 EUR. Stock S (ID 4): 10 sold short 20 Dec 2024 at 100 (fee 1), bought back 15 Jan 2025 at 90.
# Stock T (ID 5): sold 30 Dec 2024, settled 3 Jan 2025, bought back 10 Jan 2025. Stock U (ID 6): sold 15 Dec 2025, open.
# ETF E (ID 7): sold 20 Dec 2024, bought back 15 Jan 2025.
def _shorts():
    create_assets([("S", "Stock S", "US0000000S01", 2, PredefinedAsset.Stock, 'us'),
                   ("T", "Stock T", "US0000000T01", 2, PredefinedAsset.Stock, 'us'),
                   ("U", "Stock U", "US0000000U01", 2, PredefinedAsset.Stock, 'us'),
                   ("E", "ETF E", "US0000000E01", 2, PredefinedAsset.ETF, 'us')])
    create_quotes(2, 1, [(d2t(240101), 100.0)])
    create_quotes(2, 3, [(d2t(240101), 0.9)])
    create_trades(1, [(d2t(241220), d2t(241223), 4, -10, 100, 1, "s-sell"), (d2t(250115), d2t(250117), 4, 10, 90, 1, "s-buy"),
                      (d2t(241230), d2t(250103), 5, -5, 50, 0, "t-sell"), (d2t(250110), d2t(250114), 5, 5, 40, 0, "t-buy"),
                      (d2t(251215), d2t(251217), 6, -2, 30, 0, "u-sell"),
                      (d2t(241220), d2t(241223), 7, -4, 20, 0, "e-sell"), (d2t(250115), d2t(250117), 7, 4, 25, 0, "e-buy")])
    Ledger().rebuild(from_timestamp=0)


def _rows(section, template):
    return [x for x in section if x['report_template'] == template]


# RU, by settlement: S is a 2024 sale without cost; T settles in 2025, so it is an ordinary deal there
def test_ru_stock_short_in_year_of_sale(prepare_db_taxes):
    _shorts()
    taxes = TaxesRussia()
    report = taxes.prepare_tax_report(2024, 1)
    short, = _rows(report["Акции"], "short_open")
    assert (short['c_symbol'], short['c_qty'], short['code']) == ("S", Decimal('-10'), '1530 / 201')
    assert (short['income_rub'], short['spending_rub'], short['profit_rub']) == \
           (Decimal('100000.00'), Decimal('100.00'), Decimal('99900.00'))
    assert _rows(report["Акции"], "trade") == []
    assert taxes.short_warnings == [taxes.texts['short_unhandled'].format(symbol="E", date="23.12.2024")]

    form = Ru_NDFL3(2024 + 1)
    form.update_taxes(report, {'currency': 'USD', 'broker_name': 'B', 'broker_iso_country': '840'})
    record, = form._tax_form[FOREIGN_SECTION]
    assert (record['IncomeCod'], record['IncomeSum'], record['SubtractCod'], record['SubtractSum']) == \
           ('1530', 1000.0, '201', 100.0)
    assert record['IncomeGetDate'] == "2024-12-23T00:00:00"

    taxes = TaxesRussia()
    report = taxes.prepare_tax_report(2025, 1)
    assert [x['c_symbol'] for x in _rows(report["Акции"], "trade")] == ["T", "E"]
    assert [(x['c_symbol'], x['income_rub']) for x in _rows(report["Акции"], "short_open")] == [("U", Decimal('6000.00'))]
    carried, = _rows(report["Не отражено"], "operation")
    assert (carried['number'], carried['reason']) == ("s-buy", taxes.texts['short_carried'].format(year=2024))
    skipped, = [x for x in _rows(report["Сводка"], "count") if x['label'] == taxes.texts['skipped_total']]
    assert skipped['count'] == 1
    assert taxes.texts['short_unhandled'].format(symbol="E", date="23.12.2024") in \
           [x['warning'] for x in _rows(report["Сводка"], "warning")]


# PT, by trade date: S and T are 2024 sales without cost, left out of the Modelo 3 file
def test_pt_stock_short_in_year_of_sale(prepare_db_taxes):
    _shorts()
    taxes = TaxesPortugal()
    report = taxes.prepare_tax_report(2024, 1)
    shorts = [(x['symbol'], x['income_eur'], x['spending_eur'], x['profit_eur']) for x in _rows(report["Shares"], "short_open")]
    assert shorts == [("S", Decimal('900.00'), Decimal('0.90'), Decimal('899.10')),
                      ("T", Decimal('225.00'), Decimal('0.00'), Decimal('225.00'))]
    form = IRS_Modelo3(2024)
    form.update_taxes(report, {'broker_iso_country': '840'})
    assert form._tax_form == ""

    taxes = TaxesPortugal()
    report = taxes.prepare_tax_report(2025, 1)
    assert [x['symbol'] for x in _rows(report["Shares"], "trade")] == ["E"]
    assert [x['number'] for x in _rows(report["Not covered"], "operation")] == ["t-buy", "s-buy"]   # by date
