import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from PySide6.QtCore import QDateTime, QDate, QTime

from tests.fixtures import project_root, data_path, prepare_db
from tests.test_at_qr import LIDL
from jal.db.clock import local_zone
from jal.data_import.receipt import parse_vat_table, parse_total, shop_profile
from jal.data_import.receipt_pdf import layout_text, pdf_receipt
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.shop_receipts.lidl import ReceiptLidl
from jal.data_import.shop_receipts.pingo_doce import ReceiptPingoDoce

LISBON_SUMMER = timezone(timedelta(hours=1))
CAPTURED = datetime(2026, 8, 20, 9, 5, tzinfo=LISBON_SUMMER)
QR = LIDL.replace("O:11.94", "O:4.84")


# A one-page PDF in the standard Courier font with each piece of text where (x, y) puts it; 'form' draws the text
# inside a form XObject, the way Lidl's PDFs do
def make_pdf(fragments, form=False) -> bytes:
    text = "".join(f"BT /F1 10 Tf {x} {y} Td ({t}) Tj ET\n" for x, y, t in fragments).encode()
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"
    page = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 291 841] /Contents 5 0 R /Resources << "
    if form:
        stream = b"q\nBT\n36 805 Td\nET\nQ\nq 1 0 0 1 0 0 cm /Xf1 Do Q\n"
        objects = [page + b"/XObject << /Xf1 6 0 R >> >> >>", font,
                   b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
                   b"<< /Type /XObject /Subtype /Form /BBox [0 0 291 841] /Resources << /Font << /F1 4 0 R >> >> "
                   b"/Length %d >>\nstream\n" % len(text) + text + b"endstream"]
    else:
        objects = [page + b"/Font << /F1 4 0 R >> >> >>", font,
                   b"<< /Length %d >>\nstream\n" % len(text) + text + b"endstream"]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"] + objects
    pdf, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1) + b"".join(b"%010d 00000 n \n" % x for x in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return pdf


# Fabricated after the layout of a real Lidl receipt: B = 1,41 - 0,41 + 1,99 = 2,99 and A = 1,70 + 0,15 = 1,85
def lidl_receipt(nif="503340855", strawberries="1,99", total="4,84"):
    return [(46, 800, "LIDL & Cia - Loja Teste"), (46, 785, f"NIF:{nif}  C.S. 498.880 EUR"),
            (10, 770, "FATURA SIMPLIFICADA"), (10, 755, "Original     Data de Venda:"), (184, 755, "2026-08-14"),
            (10, 740, "No : FS 0421/000317"), (238, 725, "EUR"),
            (10, 710, "TOMATE REDONDO"), (238, 710, "1,41"), (268, 710, "B"),
            (22, 695, "0,744"), (58, 695, "kg x"), (88, 695, "1,89"), (130, 695, "EUR/kg"),
            (22, 680, "Promocao Lidl Plus"), (232, 680, "-0,41"),
            (10, 665, "MORANGO 300G"), (238, 665, strawberries), (268, 665, "B"),
            (10, 650, "CROISSANT CHOCOLATE 80GR"),   # the count line is drawn over the name, as Lidl does
            (142, 650, "0,85"), (184, 650, "x"), (196, 650, "2"), (226, 650, "1,70"), (256, 650, "A"),
            (10, 635, "Saco de Papel"), (238, 635, "0,15"), (268, 635, "A"),
            (208, 620, "------------"), (10, 605, "Total"), (232, 605, total), (10, 590, "MULTIBANCO"), (232, 590, total),
            (22, 575, "Taxa"), (70, 575, "Base Imp."), (142, 575, "Val.Total"), (208, 575, "Val.IVA"),
            (16, 560, "A 23%"), (82, 560, "1,50"), (154, 560, "1,85"), (220, 560, "0,35"),
            (16, 545, "B  6%"), (82, 545, "2,82"), (154, 545, "2,99"), (220, 545, "0,17"),
            (100, 530, "085"), (184, 530, "14.08.26"), (256, 530, "18:53"),
            (70, 515, "ATCUD:"), (118, 515, "JFXK7T2P-317")]


# ----------------------------------------------------------------------------------------------------------------------
def test_layout_puts_text_in_its_columns():
    for form in (False, True):
        lines = layout_text(make_pdf(lidl_receipt(), form=form))
        assert "TOMATE REDONDO                         1,41 B" in lines
        assert "  0,744  kg x 1,89   EUR/kg" in lines
        assert lines[0] == "      LIDL & Cia - Loja Teste"      # nothing of the form's text is repeated


def test_layout_moves_overprinted_text_to_a_line_of_its_own():
    lines = layout_text(make_pdf(lidl_receipt()))
    at = lines.index("CROISSANT CHOCOLATE 80GR")
    assert lines[at + 1] == "                      0,85    x 2    1,70 A"


def test_lidl_items_add_up():
    receipt = ReceiptLidl(layout_text(make_pdf(lidl_receipt())))
    assert receipt.problems() == []
    assert [(x.name, receipt.paid(x), x.vat) for x in receipt.items] == [
        ("TOMATE REDONDO", Decimal('1.00'), 'B'), ("MORANGO 300G", Decimal('1.99'), 'B'),
        ("CROISSANT CHOCOLATE 80GR", Decimal('1.70'), 'A'), ("Saco de Papel", Decimal('0.15'), 'A')]
    tomato, croissant = receipt.items[0], receipt.items[2]
    assert (tomato.qty, tomato.price, tomato.discounts) == (Decimal('0.744'), Decimal('1.89'),
                                                            [("Promocao Lidl Plus", Decimal('0.41'))])
    assert (croissant.qty, croissant.price) == (Decimal('2'), Decimal('0.85'))
    assert receipt.total == Decimal('4.84')
    assert receipt.timestamp == datetime(2026, 8, 14, 18, 53)
    assert receipt.header == {'nif': "503340855", 'doc': "FS 0421/000317", 'atcud': "JFXK7T2P-317"}


def test_a_misread_item_is_caught():
    receipt = ReceiptLidl(layout_text(make_pdf(lidl_receipt(strawberries="2,09"))))
    assert receipt.problems() == ["VAT B: items 3.09, table 2.99", "total: items 4.94, receipt 4.84"]


def test_vat_columns_follow_the_table_header():
    pingo_doce = ["  Taxa     Valor s/IVA   Valor IVA   Valor c/IVA",
                  "  C  6%          2,45        0,15          2,60",
                  "  E 23%          3,07        0,71          3,78"]
    assert parse_vat_table(pingo_doce) == {'C': {'rate': 6, 'total': Decimal('2.60')},
                                           'E': {'rate': 23, 'total': Decimal('3.78')}}
    without_total = ["Cod.  Taxa   Liquido    IVA",
                     " 0    23%     67,45    15,51"]
    assert parse_vat_table(without_total) == {'0': {'rate': 23, 'total': Decimal('82.96')}}


def test_total_to_pay_wins_over_a_plain_total():
    assert parse_total(["Total      9,99", "TOTAL A PAGAR   8,99"]) == Decimal('8.99')
    assert parse_total(["Total de artigos 14"]) is None


def test_pingo_doce_items_add_up():
    receipt = ReceiptPingoDoce(["PINGO DOCE",
                                "NIF: 500829993",
                                "PADARIA/PASTELARIA",
                                " C PAO DE MISTURA               1,29",
                                "FRUTAS E VEGETAIS",
                                " C BANANA           0,980 X 1,39  1,36",
                                "   Poupanca Imediata         (0,05)",
                                "TOTAL A PAGAR                   2,60",
                                "  Taxa     Valor s/IVA   Valor IVA   Valor c/IVA",
                                "  C  6%          2,45        0,15          2,60",
                                "        004292 2026-08-23 19:32 0770 0070 0391"])
    assert receipt.problems() == []
    assert [(x.department, x.name, receipt.paid(x)) for x in receipt.items] == [
        ("PADARIA/PASTELARIA", "PAO DE MISTURA", Decimal('1.29')), ("FRUTAS E VEGETAIS", "BANANA", Decimal('1.31'))]
    assert receipt.timestamp == datetime(2026, 8, 23, 19, 32)


def test_profiles_are_found_by_nif():
    assert shop_profile("503340855") is ReceiptLidl
    assert shop_profile("500829993") is ReceiptPingoDoce
    assert shop_profile("999999990") is None


# ----------------------------------------------------------------------------------------------------------------------
def test_pdf_receipt_brings_every_item(prepare_db):
    receipt = pdf_receipt(make_pdf(lidl_receipt(), form=True), AtQr.parse(QR), CAPTURED)
    assert receipt.slip_lines() == [
        {'name': "TOMATE REDONDO (0.744 x 1.89)", 'amount': Decimal('-1.00')},
        {'name': "MORANGO 300G", 'amount': Decimal('-1.99')},
        {'name': "CROISSANT CHOCOLATE 80GR (2 x 0.85)", 'amount': Decimal('-1.70')},
        {'name': "Saco de Papel", 'amount': Decimal('-0.15')}]
    assert receipt.shop_name() == "NIF 503340855"
    assert receipt.number() == "503340855:FS 0421/000317"
    assert receipt.datetime() == QDateTime(QDate(2026, 8, 14), QTime(18, 53), local_zone())


def test_pdf_receipt_that_does_not_add_up_is_one_line_of_its_total(prepare_db):
    receipt = pdf_receipt(make_pdf(lidl_receipt(strawberries="2,09")), AtQr.parse(QR), CAPTURED)
    assert receipt.slip_lines() == [{'name': "NIF 503340855", 'amount': Decimal('-4.84')}]


def test_pdf_receipt_whose_total_differs_from_the_qr_is_one_line_of_the_qr_total(prepare_db):
    receipt = pdf_receipt(make_pdf(lidl_receipt()), AtQr.parse(LIDL), CAPTURED)     # the QR says 11.94
    assert receipt.slip_lines() == [{'name': "NIF 503340855", 'amount': Decimal('-11.94')}]


def test_pdf_receipt_without_qr_reads_the_shop_and_number_from_the_text(prepare_db):
    receipt = pdf_receipt(make_pdf(lidl_receipt()), None, CAPTURED)
    assert len(receipt.slip_lines()) == 4
    assert receipt.number() == "503340855:FS 0421/000317"


def test_pdf_receipt_of_an_unknown_shop_is_one_line_of_its_total(prepare_db):
    receipt = pdf_receipt(make_pdf(lidl_receipt(nif="509999999")), None, CAPTURED)
    assert receipt.slip_lines() == [{'name': "NIF 509999999", 'amount': Decimal('-4.84')}]
    assert receipt.number() == "509999999:FS 0421/000317"
    assert receipt.datetime() == QDateTime(QDate(2026, 8, 20), QTime(9, 5), local_zone())   # no date read: capture


def test_pdf_receipt_of_a_broken_file_is_nothing(prepare_db):
    assert pdf_receipt(b"%PDF-1.4 truncated", None, CAPTURED) is None
