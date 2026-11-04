import os
import openpyxl
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.test_tax_overrides import _year_2025, _rows, PARAMETERS
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.data_export.xlsx import XLSX


# Each RU section with an estimate states its rate; the Summary sums the estimates per section and in all
def test_estimates_stated_and_summed(prepare_db_taxes):
    _year_2025()
    taxes = TaxesRussia()
    report = taxes.prepare_tax_report(2025, 1)
    assert taxes.section_headers("Дивиденды") == [taxes.texts['estimate_dividend'].format(rate="13")]
    assert taxes.section_headers("Проценты") == [taxes.texts['estimate_interest'].format(rate="13")]
    assert _rows(report["Проценты"], "interest")[0]['tax2pay'] == Decimal('65')   # 13 % of 500 RUB
    summary = report[taxes.summary_section[0]]
    assert _rows(summary, "estimates") == [{'report_template': "estimates", 'title': taxes.texts['estimates']}]
    # dividends: 30 (STK, treaty) + 0 (ERIC, 600 withheld exceeds 260)
    assert [(x['label'], x['amount']) for x in _rows(summary, "estimate")] == \
           [("Дивиденды", Decimal('30')), ("Проценты", Decimal('65')), (taxes.texts['estimate_total'], Decimal('95'))]

    pt = TaxesPortugal()
    assert _rows(pt.prepare_tax_report(2025, 1)[pt.summary_section[0]], "estimates") == []


# A year without parameters has no estimate, so no header line and no Summary block
def test_no_parameters_no_estimates(prepare_db_taxes):
    _year_2025()
    taxes = TaxesRussia()
    report = taxes.prepare_tax_report(2019, 1)
    assert taxes.section_headers("Дивиденды") == []
    assert _rows(report[taxes.summary_section[0]], "estimates") == []


# The estimate is italic on its own fill, in the rows and in the totals, and the column header names it
def test_estimates_marked_in_the_workbook(prepare_db_taxes, tmp_path):
    _year_2025()
    taxes = TaxesRussia()
    report = taxes.prepare_tax_report(2025, 1)
    file = str(tmp_path) + os.sep + "report.xlsx"
    xlsx = XLSX(file)
    for section in report:
        xlsx.output_data(report[section], taxes.report_template(section), PARAMETERS,
                         headers=taxes.section_headers(section))
    assert xlsx.save()
    sheet = openpyxl.load_workbook(file)["Дивиденды"]
    header_row = next(r for r in range(1, sheet.max_row + 1) if sheet.cell(row=r, column=1).value == "Дата выплаты")
    assert sheet.cell(row=header_row, column=10).value == "Налог к уплате, RUB (базовая оценка)"
    estimate, withheld = sheet.cell(row=header_row + 2, column=10), sheet.cell(row=header_row + 2, column=9)
    assert estimate.value == 30 and estimate.font.i and estimate.fill.fgColor.rgb.endswith("FFF2CC")
    assert not withheld.font.i
    totals = sheet.cell(row=header_row + 4, column=10)
    assert totals.value == 30 and totals.font.i
