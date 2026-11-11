#!/usr/bin/env python
# The pictures and the sample workbook of the Russian 3-NDFL guide (docs/ru-tax-3ndfl), from a copy of the demo
# database with invented rouble rates and a year of deals on the demo trading account, in the Russian interface.
# The sheets are drawn by LibreOffice: 'soffice' and 'pdftoppm' have to be on the path.
import os
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from demo_env import prepare_environment, assert_demo_database, DEMO_DIR, DOCS_DIR, REPO_DIR

from PySide6.QtCore import QTranslator
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

SUBDIR = "ru_guide"
GUIDE_DIR = os.path.join(DOCS_DIR, "ru-tax-3ndfl")
IMG_DIR = os.path.join(GUIDE_DIR, "img")
WORKBOOK = os.path.join(GUIDE_DIR, "3ndfl_tax_report.xlsx")
YEAR = 2025
RUB, USD = 1, 2
BROKER, ACME = "Northgate Trading", "ACME"
# RUB value of one USD through 2025, invented: twelve points the weekly rates are drawn between
USD_RUB = [101.20, 97.80, 89.60, 84.30, 82.10, 79.40, 78.60, 80.30, 81.90, 81.20, 80.90, 78.50]
# Deals added to the demo account: a purchase, a sale filled in two trades and a purchase again, so that the later
# sales of the demo database still find their shares
TRADES = [("2025-03-12 15:45", 3, '121.10', '2.50', "T-101533"), ("2025-09-16 15:20", -12, '130.40', '1.20', "T-103871"),
          ("2025-09-16 15:21", -16, '130.55', '1.60', "T-103872"), ("2025-10-14 16:10", 12, '129.90', '2.50', "T-104102")]
SHEETS = {"Сводка": "report_summary", "Акции": "report_2", "Дивиденды": "report_1"}   # sheet: picture


def ts(text: str) -> int:
    layout = "%Y-%m-%d %H:%M" if ' ' in text else "%Y-%m-%d"
    return int(datetime.strptime(text, layout).replace(tzinfo=timezone.utc).timestamp())


def add_guide_data() -> int:
    from jal.db.db import JalDB
    from jal.db.asset import JalAsset
    from jal.db.ledger import Ledger
    from jal.db.operations import LedgerTransaction
    rates = []   # a rate a week, as the report takes a rate older than two weeks for a missing one
    for week in range(53):
        month, part = divmod(week * 12 / 53, 1)
        following = USD_RUB[min(int(month) + 1, 11)]
        rates.append({'timestamp': ts("2025-01-01") + week * 7 * 86400,
                      'quote': round(Decimal(str(USD_RUB[int(month)] + (following - USD_RUB[int(month)]) * part)), 4)})
    JalAsset(USD).set_quotes(rates, RUB)
    account = JalDB._read("SELECT id FROM accounts WHERE name=:name", [(":name", BROKER)])
    symbol = JalDB._read("SELECT id FROM asset_symbol WHERE symbol=:symbol AND currency_id=:currency",
                         [(":symbol", ACME), (":currency", USD)])
    for moment, qty, price, fee, number in TRADES:
        LedgerTransaction.create_new(LedgerTransaction.Trade, {
            'timestamp': ts(moment), 'settlement': ts(moment[:10]) + 2 * 86400, 'account_id': account,
            'symbol_id': symbol, 'qty': Decimal(qty), 'price': Decimal(price), 'fee': Decimal(fee), 'number': number})
    Ledger().rebuild(from_timestamp=0)
    return account


# The tax dialog filled in as the guide describes, saved as a picture, and the files it writes
def save_report(parent, declaration: str):
    from jal.data_export.tax_grouping import Grouping
    from jal.widgets.tax_widget import TaxWidget, REPORT, FORM
    widget = TaxWidget(parent)
    widget.ui.Year.setValue(YEAR)
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
    grouping = widget._editors[('ru', REPORT, 'grouping')]
    grouping.setCurrentIndex(grouping.findData(Grouping.SaleDay))
    widget.ui.FormGroup.setChecked(True)
    widget._editors[('ru', FORM, 'merge_lots')].setChecked(True)
    widget.ui.XlsFileName.setText(f"3ndfl_{YEAR}.xlsx")
    widget.ui.FormFileName.setText(f"3ndfl_{YEAR}.de{YEAR % 10}")
    widget.show()
    QApplication.processEvents()
    widget.resize(720, widget.sizeHint().height())
    QApplication.processEvents()
    widget.grab().save(os.path.join(IMG_DIR, "report_params.png"))
    print("saved", os.path.relpath(os.path.join(IMG_DIR, "report_params.png"), REPO_DIR))
    widget.ui.XlsFileName.setText(WORKBOOK)
    widget.ui.FormFileName.setText(declaration)
    widget.SaveReport()
    widget.close()
    print("saved", os.path.relpath(WORKBOOK, REPO_DIR))


# A sheet of the workbook as a picture: alone in a copy, without its footnotes, the lots of its groups unfolded,
# fitted to the width of a landscape page, printed to PDF by LibreOffice and cut to its content
def sheet_picture(sheet_name: str, picture: str, folder: str):
    import openpyxl
    book = openpyxl.load_workbook(WORKBOOK)
    for name in book.sheetnames:
        if name != sheet_name:
            del book[name]
    sheet = book[sheet_name]
    footnotes = next((x for x in range(1, sheet.max_row + 1) if sheet.cell(x, 1).value == "Описание данных в столбцах таблицы"),
                     None)
    if footnotes is not None:
        sheet.delete_rows(footnotes, sheet.max_row - footnotes + 1)
    for row in sheet.row_dimensions.values():
        row.hidden = False
    sheet.page_setup.orientation = "landscape"
    sheet.sheet_properties.pageSetUpPr = openpyxl.worksheet.properties.PageSetupProperties(fitToPage=True)
    sheet.page_setup.fitToWidth, sheet.page_setup.fitToHeight = 1, 0
    source = os.path.join(folder, picture + ".xlsx")
    book.save(source)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", folder, source], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "150", "-png", "-singlefile",
                    os.path.join(folder, picture + ".pdf"), os.path.join(folder, picture)], check=True)
    image = QImage(os.path.join(folder, picture + ".png"))
    inked = [(x, y) for y in range(0, image.height(), 2) for x in range(0, image.width(), 2)
             if image.pixelColor(x, y).lightness() < 245]
    left, top = min(x for x, _ in inked) - 12, min(y for _, y in inked) - 12
    right, bottom = max(x for x, _ in inked) + 12, max(y for _, y in inked) + 12
    image.copy(max(left, 0), max(top, 0), right - max(left, 0), bottom - max(top, 0)).save(os.path.join(IMG_DIR, picture + ".png"))
    print("saved", os.path.relpath(os.path.join(IMG_DIR, picture + ".png"), REPO_DIR))


def main():
    demo = os.path.join(DEMO_DIR, "jal.sqlite")
    if not os.path.isfile(demo):
        sys.exit("No demo database: run tools/manual/make_demo_db.py first")
    prepare_environment(subdir=SUBDIR)
    os.makedirs(os.path.join(DEMO_DIR, SUBDIR), exist_ok=True)
    shutil.copyfile(demo, os.path.join(DEMO_DIR, SUBDIR, "jal.sqlite"))
    app = QApplication.instance() or QApplication([])
    from jal.db.db import JalDB, JalDBError
    error = JalDB().init_db()
    if error.code != JalDBError.NoError:
        raise RuntimeError(f"Demo database is not ready: {error.message}")
    assert_demo_database(SUBDIR)
    translator = QTranslator()
    if not translator.load(os.path.join(REPO_DIR, "jal", "languages", "ru.qm")):
        raise RuntimeError("No Russian translation: run jal/compile_translations first")
    app.installTranslator(translator)
    QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok   # the report's notices need no answer here

    from jal.widgets.icons import JalIcon
    JalIcon()   # the country flags of the dialog
    add_guide_data()
    parent = QWidget()
    with tempfile.TemporaryDirectory() as folder:
        save_report(parent, os.path.join(folder, f"3ndfl_{YEAR}.de{YEAR % 10}"))
        for sheet_name, picture in SHEETS.items():
            sheet_picture(sheet_name, picture, folder)


if __name__ == "__main__":
    main()
