import os
import openpyxl
import pytest
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_quotes, create_trades, symbol_id_for
from jal.constants import PredefinedAsset
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, AssetIncome
from jal.data_export.taxes import TaxReportStop
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.data_export.xlsx import XLSX

PARAMETERS = {"period": "01/01/2025 - 31/12/2025", "account": "U7654321 (USD)", "currency": "USD"}


# One stock bought and sold in 2025 on account 1
def _one_sale():
    create_assets([("STK", "Stock Corp", "US0000000501", 2, PredefinedAsset.Stock, 'us')])   # ID 4
    create_quotes(2, 1, [(d2t(250102), 100.0)])
    create_quotes(2, 3, [(d2t(250102), 0.9)])
    create_trades(1, [(d2t(250102), d2t(250104), 4, 10, 10, 0, "buy"), (d2t(250602), d2t(250604), 4, -10, 12, 0, "sell")])
    Ledger().rebuild(from_timestamp=0)


class _NotedReport(TaxesRussia):
    def prepare_stocks_and_etf(self):
        self.add_header("Сделки сопоставлены по FIFO")
        return super().prepare_stocks_and_etf()


# A line a section states under its title follows the template's own headers; the summary links to "Not covered"
def test_header_lines_and_links_reach_the_workbook(prepare_db_taxes, tmp_path):
    _one_sale()
    create_assets([("SOL", "Solana", "", 2, PredefinedAsset.Crypto, 0)])   # ID 5, its rent return is skipped by rule
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': d2t(250201), 'type': AssetIncome.TokenRentReturn, 'account_id': 1, 'symbol_id': symbol_id_for(5),
        'amount': '0.002', 'tax': '0', 'number': 'close', 'note': 'rent back'})
    Ledger().rebuild(from_timestamp=0)
    taxes = _NotedReport()
    report = taxes.prepare_tax_report(2025, 1)
    assert taxes.section_headers("Акции") == ["Сделки сопоставлены по FIFO"]
    assert taxes.section_headers("Облигации") == []

    file = str(tmp_path) + os.sep + "report.xlsx"
    xlsx = XLSX(file)
    for section in report:
        xlsx.output_data(report[section], taxes.report_template(section), PARAMETERS,
                         headers=taxes.section_headers(section))
    assert xlsx.save()

    book = openpyxl.load_workbook(file)
    assert book.sheetnames == ["Сводка", "Акции", "Не отражено"]       # empty sections make no sheet
    trades = book["Акции"]
    lines = [trades.cell(row=r, column=1).value for r in range(3, 8)]
    assert lines == ["Документ-основание: ", "Период: 01/01/2025 - 31/12/2025", "ФИО: ",
                     "Номер счета: U7654321 (USD)", "Сделки сопоставлены по FIFO"]
    summary = book["Сводка"]
    links = [(c.value, c.hyperlink.location) for row in summary.iter_rows() for c in row if c.hyperlink]
    assert links == [("Пропущено по правилу юрисдикции", "'Не отражено'!A1")]   # nothing uncovered, no link


class _QuotelessReport(TaxesRussia):
    def prepare_dividends(self):
        self.missing_quote("SOL", d2t(250201))
        self.missing_quote("SOL", d2t(250201))
        return super().prepare_dividends()

    def prepare_crypto(self):
        self.missing_quote("ETH", d2t(250301))
        return super().prepare_crypto()


# Every missing quote of every section is listed once, then the report stops
def test_missing_quotes_stop_the_report(prepare_db_taxes):
    _one_sale()
    with pytest.raises(TaxReportStop) as stop:
        _QuotelessReport().prepare_tax_report(2025, 1)
    assert stop.value.missing == [("SOL", d2t(250201)), ("ETH", d2t(250301))]


# A returned token account rent is a refund, not income: both jurisdictions skip it by rule
@pytest.mark.parametrize("report_class, section, reason", [
    (TaxesRussia, "Не отражено", "Возврат ренты токен-аккаунта: возврат уплаченного, а не доход"),
    (TaxesPortugal, "Not covered", "Token account rent returned: a refund of rent paid, not income")])
def test_rent_return_is_skipped_by_rule(prepare_db_taxes, report_class, section, reason):
    create_assets([("SOL", "Solana", "", 2, PredefinedAsset.Crypto, 0)])   # ID 4
    create_quotes(4, 2, [(d2t(250201), 200.0)])
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': d2t(250201), 'type': AssetIncome.TokenRentReturn, 'account_id': 1, 'symbol_id': symbol_id_for(4),
        'amount': '0.002', 'tax': '0', 'number': 'close', 'note': 'rent back'})
    Ledger().rebuild(from_timestamp=0)

    report = report_class().prepare_tax_report(2025, 1)
    assert [(x['report_template'], x['reason']) for x in report[section]] == [("skipped", reason)]


# A direct-only quote takes the stored pair and never builds a cross-rate through the residence currency
def test_direct_only_quote_takes_no_cross_rate(prepare_db_taxes):
    create_quotes(2, 1, [(d2t(250102), 100.0)])     # USD/RUB
    create_quotes(3, 1, [(d2t(250102), 110.0)])     # EUR/RUB
    usd = JalAsset(2)
    assert usd.quote(d2t(250110), 3)[1] == Decimal('100') / Decimal('110')      # the cross-rate, as before
    assert usd.quote(d2t(250110), 3, report_missing=False, direct_only=True) == (0, Decimal('0'))
    create_quotes(2, 3, [(d2t(250102), 0.9)])
    assert usd.quote(d2t(250110), 3, direct_only=True)[1] == Decimal('0.9')
