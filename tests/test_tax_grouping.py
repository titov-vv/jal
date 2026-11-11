import json
import pytest
from copy import deepcopy
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, dt2t, create_assets, create_quotes, create_trades, create_actions
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.ledger import Ledger
from jal.data_export.tax_grouping import Grouping, DealFields, DealGroup, DAY, deal_key, summarize, group_deals
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.data_export.ru_ndfl3 import Ru_NDFL3, FOREIGN_SECTION
from jal.data_export.irs_modelo3 import IRS_Modelo3

FIELDS = DealFields(security=('symbol',), qty='qty', opened=('o_date',), closed=('c_date',), figures=('qty', 'amount'))


def _row(symbol, qty, o_date, c_date, amount, template="trade", **more):
    return dict({'report_template': template, 'symbol': symbol, 'qty': Decimal(qty), 'o_date': o_date, 'c_date': c_date,
                 'amount': Decimal(amount)}, **more)


# A level keys a deal by its security, then by the day it was disposed of, then by the day it was acquired as well;
# a short is apart from a long and is disposed of by its opening leg
def test_deal_key_levels():
    long, short = _row("A", 5, 10 * DAY + 60, 20 * DAY + 120, 1), _row("A", -5, 10 * DAY + 60, 20 * DAY + 120, 1)
    assert deal_key(FIELDS, Grouping.Security)(long) == ("A", False)
    assert deal_key(FIELDS, Grouping.SaleDay)(long) == ("A", False, 20)
    assert deal_key(FIELDS, Grouping.Days)(long) == ("A", False, 20, 10)
    assert deal_key(FIELDS, Grouping.Security)(short) == ("A", True)
    assert deal_key(FIELDS, Grouping.SaleDay)(short) == ("A", True, 10)
    assert deal_key(FIELDS, Grouping.Days)(short) == ("A", True, 10, 20)


# A figure is summed, a date is kept if the deals share its day, any other value if they share it; the rest is left out
def test_summary_of_a_group():
    rows = [_row("A", 5, 10 * DAY + 60, 20 * DAY, '100.10', number="N1", note="x", price=Decimal('7'), extra=1),
            _row("A", 3, 10 * DAY + 30, 21 * DAY, '50.05', number="N2", note="x", price=Decimal('7'))]
    assert summarize(rows, FIELDS) == {'report_template': "trade", 'symbol': "A", 'qty': Decimal('8'),
                                       'o_date': 10 * DAY + 30, 'amount': Decimal('150.15'), 'note': "x",
                                       'price': Decimal('7')}


# A group stands where its first deal was and holds its deals in their order; the rows that are not deals stay as they
# are, and an account's header starts its groups anew
def test_groups_keep_the_order_and_the_account():
    a1, b1, a2 = _row("A", 1, DAY, 5 * DAY, 10), _row("B", 1, DAY, 5 * DAY, 20), _row("A", 2, DAY, 6 * DAY, 30)
    short_open, totals = _row("A", -1, DAY, 0, 5, template="short_open"), {'report_template': "totals"}
    account = {'report_template': "account"}
    a3 = _row("A", 4, DAY, 5 * DAY, 40)
    items = group_deals([account, a1, b1, a2, short_open, totals, account, a3, totals],
                        deal_key(FIELDS, Grouping.Security), FIELDS)
    assert [type(x) for x in items] == [dict, DealGroup, DealGroup, dict, dict, dict, DealGroup, dict]
    assert items[1].rows == [a1, a2] and items[2].rows == [b1] and items[6].rows == [a3]
    assert items[3] is short_open and items[4] is totals
    assert items[1].summary['amount'] == Decimal('40') and 'c_date' not in items[1].summary
    by_day = group_deals([a1, b1, a2], deal_key(FIELDS, Grouping.SaleDay), FIELDS)
    assert [x.rows for x in by_day] == [[a1], [b1], [a2]]


# AAPL bought in three trades on two days and sold in three trades on two days - five lots; a short of XYZ bought back
# in two trades of one day - two lots
def _partial_fills():
    create_assets([("AAPL", "Apple Inc", "US0378331005", 2, PredefinedAsset.Stock, 'us'),          # ID 4
                   ("XYZ", "XYZ Holdings Ltd", "KYG000000001", 2, PredefinedAsset.Stock, 'ky')])   # ID 5
    days = (240110, 240112, 240115, 240117, 240304, 240306, 240311, 240313, 240402, 240404)
    create_quotes(2, 1, [(d2t(x), 90.0 + i) for i, x in enumerate(days)])            # USD/RUB
    create_quotes(2, 3, [(d2t(x), 0.9 + i / 100) for i, x in enumerate(days)])       # USD/EUR
    create_actions([(d2t(230101), 1, 1, [(PredefinedCategory.StartingBalance, 20000.0)])])
    create_trades(1, [
        (dt2t(2401101430), d2t(240112), 4, 10, 150.0, 1.0, "B1"),
        (dt2t(2401101500), d2t(240112), 4, 5, 151.0, 0.5, "B2"),
        (dt2t(2401151430), d2t(240117), 4, 10, 160.0, 1.0, "B3"),
        (dt2t(2403041430), d2t(240306), 4, -12, 180.0, 1.2, "S1"),   # 10 of B1, 2 of B2
        (dt2t(2403041530), d2t(240306), 4, -8, 181.0, 0.8, "S2"),    # 3 of B2, 5 of B3
        (dt2t(2403111430), d2t(240313), 4, -5, 190.0, 0.5, "S3"),    # 5 of B3
        (dt2t(2401101430), d2t(240112), 5, -10, 50.0, 1.0, "X1"),    # short
        (dt2t(2404021430), d2t(240404), 5, 4, 45.0, 0.4, "X2"),
        (dt2t(2404021500), d2t(240404), 5, 6, 46.0, 0.6, "X3")
    ])
    Ledger().rebuild(from_timestamp=0)


# The groups of each level hold every deal once, and their figures add up to the totals of the sheet
@pytest.mark.parametrize("report_class, section, totalled", [
    (TaxesRussia, "Акции", ("income_rub", "spending_rub", "profit_rub", "profit")),
    (TaxesPortugal, "Shares", ("income_eur", "spending_eur", "profit_eur", "profit"))
])
@pytest.mark.parametrize("level, sizes", [(Grouping.Security, [5, 2]), (Grouping.SaleDay, [4, 1, 2]),
                                          (Grouping.Days, [3, 1, 1, 2])])
def test_groups_add_up_to_the_totals(prepare_db_taxes, report_class, section, totalled, level, sizes):
    _partial_fills()
    taxes = report_class()
    rows = taxes.prepare_tax_report(2024, 1)[section]
    fields = taxes.deal_fields
    deals, totals = rows[:-1], rows[-1]
    assert len(deals) == 7 and totals['report_template'] == "totals"
    items = group_deals(rows, deal_key(fields, level), fields)
    groups = items[:-1]
    assert items[-1] is totals and all(isinstance(x, DealGroup) for x in groups)
    assert [len(x.rows) for x in groups] == sizes
    assert sorted(id(row) for x in groups for row in x.rows) == sorted(id(x) for x in deals)
    for figure in totalled:
        assert sum(x.summary[figure] for x in groups) == totals[figure]
    for figure in fields.figures:
        assert sum(x.summary[figure] for x in groups) == sum(x[figure] for x in deals)
    long, short = groups[0].summary, groups[-1].summary
    assert long[fields.qty] > 0 > short[fields.qty]
    assert all(x in long and x in short for x in fields.security)
    dated = lambda summary: {x for x in fields.dates() if x in summary}
    if level == Grouping.Security:
        assert dated(long) == set() and dated(short) == set(fields.dates())   # the short has one day of each leg
    elif level == Grouping.SaleDay:
        assert dated(long) == set(fields.closed) and dated(short) == set(fields.dates())
    else:
        assert all(dated(x.summary) == set(fields.dates()) for x in groups)


def _modelo3_lines(report: dict, **options) -> list:
    form = IRS_Modelo3(2024, **options)
    form.update_taxes(report, {'broker_iso_country': '840'})
    values = lambda line: {x: line[line.index(f"<{x}>") + len(x) + 2:line.index(f"</{x}>")] for x in (
        "Codigo", "AnoRealizacao", "MesRealizacao", "DiaRealizacao", "ValorRealizacao", "AnoAquisicao", "MesAquisicao",
        "DiaAquisicao", "ValorAquisicao", "DespesasEncargos")}
    return [values(x) for x in form._tax_form.splitlines()]


# Modelo 3 with the lots merged: a line for the deals of a security acquired on one day and realized on one day. The
# figures are worked out by hand: each lot's amounts and its expenses converted and rounded on their own, then added.
def test_modelo3_merges_lots(prepare_db_taxes):
    _partial_fills()
    report = TaxesPortugal().prepare_tax_report(2024, 1)
    lots, merged = _modelo3_lines(report), _modelo3_lines(report, merge_lots=True)
    assert len(lots) == 7 and len(merged) == 4
    for figure in ("ValorRealizacao", "ValorAquisicao", "DespesasEncargos"):
        assert sum(Decimal(x[figure]) for x in merged) == sum(Decimal(x[figure]) for x in lots)
    line = lambda *x: dict(zip(("Codigo", "AnoRealizacao", "MesRealizacao", "DiaRealizacao", "ValorRealizacao",
                                "AnoAquisicao", "MesAquisicao", "DiaAquisicao", "ValorAquisicao", "DespesasEncargos"), x))
    assert merged == [
        # 10 + 2 + 3 bought on 10 Jan and sold on 4 Mar, at 0.94: 1692.00 + 338.40 + 510.42 less 1410.00 + 283.88 + 425.82
        line("G01", "2024", "3", "4", "2540.82", "2024", "1", "10", "2119.70", "2.82"),
        line("G01", "2024", "3", "4", "850.70", "2024", "1", "15", "752.00", "0.94"),     # 5 of B3 in S2
        line("G01", "2024", "3", "11", "912.00", "2024", "1", "15", "768.00", "0.96"),    # 5 of B3 in S3, at 0.96
        # the short: sold on 10 Jan at 0.90, bought back in two trades on 2 Apr
        line("G01", "2024", "1", "10", "450.00", "2024", "4", "2", "410.40", "1.80")
    ]


def _ndfl3_records(report: dict, **options) -> list:
    form = Ru_NDFL3(2025, **options)
    form.update_taxes(deepcopy(report), {'currency': 'USD', 'broker_name': 'IBKR', 'broker_iso_country': '840',
                                         'account_name': 'TEST'})
    return json.loads(json.dumps(form._tax_form[FOREIGN_SECTION], ensure_ascii=False))


# 3-NDFL with the lots merged: a record for the deals of a security sold on one day, with the one date of income and
# rate they share. The figures are worked out by hand, each lot converted and rounded on its own.
def test_ndfl3_merges_lots(prepare_db_taxes):
    _partial_fills()
    report = TaxesRussia().prepare_tax_report(2024, 1)
    lots, merged = _ndfl3_records(report), _ndfl3_records(report, merge_lots=True)
    assert len(lots) == 7 and len(merged) == 3
    for figure in ("IncomeSum", "IncomeRoubleSum", "SubtractSum"):
        assert sum(Decimal(str(x[figure])) for x in merged) == sum(Decimal(str(x[figure])) for x in lots)
    figures = lambda x: (x['SourseName'], x['IncomeGetDate'], x['CurrencyExchange'], x['IncomeSum'],
                         x['IncomeRoubleSum'], x['SubtractSum'], x['IncomeCod'], x['SubtractCod'])
    assert [figures(x) for x in merged] == [
        # S1 and S2 of 4 Mar, settled on 6 Mar at 95: 20 shares for 3608 USD. The cost at the rates of the purchases'
        # settlements (91, 91, 91, 93) is 279605, the fees at the rates of the trade dates 369
        ("Доход от сделки с AAPL (US0378331005)", "2024-03-06T00:00:00", 9500.0, 3608.0, 342760.0, 279974.0,
         "1530", "201"),
        # S3: 5 shares for 950 USD at 97; cost 800 USD at 93, fees 0.5 at 92 and 0.5 at 96
        ("Доход от сделки с AAPL (US0378331005)", "2024-03-13T00:00:00", 9700.0, 950.0, 92150.0, 74494.0,
         "1530", "201"),
        # the short: the income is the sale of 10 Jan, settled on 12 Jan at 91; bought back for 180 + 276 USD at 99,
        # fees 1.0 at 90 and 1.0 at 98
        ("Доход от сделки с XYZ (KYG000000001)", "2024-01-12T00:00:00", 9100.0, 500.0, 45500.0, 45332.0,
         "1530", "201")
    ]
