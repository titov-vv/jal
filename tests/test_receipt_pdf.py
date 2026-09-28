import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from PySide6.QtCore import QDateTime, QDate, QTime

from tests.fixtures import project_root, data_path, prepare_db
from tests.test_at_qr import LIDL
from jal.constants import PredefinedCategory
from jal.db.clock import local_zone
from jal.data_import.receipt import parse_vat_table, parse_total, parse_card, parse_vouchers, shop_profile
from jal.data_import.receipt_pdf import layout_text, pdf_receipt
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.shop_receipts.lidl import ReceiptLidl
from jal.data_import.shop_receipts.pingo_doce import ReceiptPingoDoce
from jal.data_import.shop_receipts.continente import ReceiptContinente

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


# The receipt above with a card discount below a 'Subtotal' row, shared by its VAT table as A 0,10 and B 0,40
def lidl_receipt_with_card_discount(b_total="2,59"):
    vat = {"1,85": "1,75", "2,99": b_total}
    fragments = [(x, y, vat.get(t, t) if y in (560, 545) else t)
                 for x, y, t in lidl_receipt(total="4,34") if t != "------------"]
    return fragments + [(10, 626, "Subtotal"), (232, 626, "4,84"), (22, 616, "Promocao Cartao"), (232, 616, "-0,50")]


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


def test_discount_below_subtotal_is_the_receipts():
    receipt = ReceiptLidl(layout_text(make_pdf(lidl_receipt_with_card_discount())))
    assert receipt.problems() == []
    assert receipt.discounts == [("Promocao Cartao", Decimal('0.50'))]
    assert receipt.items[0].discounts == [("Promocao Lidl Plus", Decimal('0.41'))]
    assert receipt.items[-1].discounts == []


def test_receipt_discount_must_be_shared_by_the_vat_table():
    receipt = ReceiptLidl(layout_text(make_pdf(lidl_receipt_with_card_discount(b_total="2,69"))))
    assert receipt.problems() == ["VAT: items less table A 0.10, B 0.30, receipt discount 0.50"]


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


def test_card_digits_as_printed_and_as_misread():
    assert parse_card(["MULTIBANCO   21,49", "VISA INTERNACIONAL", "CARTAO: ****1234     TC:9E1F0B3C"]) == "1234"
    assert parse_card(["CARTA0: ****5678"]) == "5678"             # OCR: letter O read as zero
    assert parse_card(["CARTAO: #***34l6"]) == "3416"             # OCR: '*' as '#', '1' as 'l'
    assert parse_card(["Cartão: **** 9O12"]) == "9012"


def test_card_digits_not_found():
    assert parse_card(["Multibanco 21,49"]) is None
    assert parse_card(["Cartao Frota: 704236123456789012"]) is None    # no mask: a fleet card, not a payment card
    assert parse_card(["CARTAO: ****12345"]) is None
    assert parse_card(["CARTAO: ****1234", "CARTAO: ****5678"]) is None   # split payment: no single card
    assert parse_card(["CARTAO: ****1234", "CARTA0: ****1234"]) == "1234"


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


# Fabricated after the layout of a real Pingo Doce receipt, paid partly with a bottle deposit voucher
PINGO_DOCE_VOUCHER = ["Registo C.R.C. Lisboa-Matricula/NIPC: 500829993",
                      "MERCEARIA + PET FOOD",
                      " E CHOCOLATE 3X50G                          3,29",
                      "PADARIA/PASTELARIA",
                      " C PAO TRIGO 400G         1,000 X 2,49     2,49",
                      "       Poupanca Imediata                  (0,50)",
                      "                                  Resumo",
                      "TOTAL                                      5,78",
                      "TOTAL POUPANCA                            (0,50)",
                      "TOTAL A PAGAR      5,28",
                      "TOTAL PAGO                                 5,28",
                      " V. Deposito Volta                         0,60",
                      "   9800000000000000000000000000",
                      " Multibanco                                4,68",
                      "Taxa      Valor s/IVA    Valor IVA  Valor c/IVA",
                      " C  6%           1,88         0,11         1,99",
                      " E 23%           2,67         0,62         3,29",
                      "           004292 2026-09-27 19:49 0768 0068 0391",
                      "Fatura Simplificada  FS 0391068260618/007693"]


def test_pingo_doce_voucher_is_not_part_of_the_items():
    receipt = ReceiptPingoDoce(PINGO_DOCE_VOUCHER)
    assert receipt.problems() == []
    assert receipt.items[0].department == "MERCEARIA + PET FOOD"
    assert parse_vouchers(PINGO_DOCE_VOUCHER, ReceiptPingoDoce.VoucherLabel, receipt.total) == \
        ([("V. Deposito Volta", Decimal('0.60'))], [])


# As a phone reads a paper receipt: label and amount one space apart, '€' read as 'E'
OCR_PAYMENTS = ["Resumo", "TOTAL A PAGAR 5,28", "V. Deposito Volta 0,60E", "Multibanco 4.68"]


def test_voucher_as_ocr_reads_it():
    assert parse_vouchers(OCR_PAYMENTS, ReceiptPingoDoce.VoucherLabel, Decimal('5.28')) == \
        ([("V. Deposito Volta", Decimal('0.60'))], [])


def test_voucher_that_leaves_an_amount_no_payment_shows_is_not_trusted():
    misread = [x.replace("0,60E", "6,60E") for x in OCR_PAYMENTS]
    for text, total in ((misread, Decimal('5.28')), (OCR_PAYMENTS, Decimal('5.38')), (OCR_PAYMENTS, None)):
        vouchers, problems = parse_vouchers(text, ReceiptPingoDoce.VoucherLabel, total)
        assert vouchers == [] and problems


def test_voucher_without_an_amount_is_not_trusted():
    text = OCR_PAYMENTS[:2] + ["V. Deposito Volta 0, 60", "Multibanco 4,68"]
    vouchers, problems = parse_vouchers(text, ReceiptPingoDoce.VoucherLabel, Decimal('5.28'))
    assert vouchers == [] and problems == ["no amount in 'V. Deposito Volta 0, 60'"]


def test_voucher_paying_everything_needs_no_other_payment():
    assert parse_vouchers(["TOTAL 0,60", "V. Deposito Volta 0,60"], ReceiptPingoDoce.VoucherLabel,
                          Decimal('0.60')) == ([("V. Deposito Volta", Decimal('0.60'))], [])


def test_voucher_label_among_the_items_is_not_a_payment():
    assert parse_vouchers([" C V. ITEM 1,00", "TOTAL 1,00"], ReceiptPingoDoce.VoucherLabel, Decimal('1.00')) == ([], [])


def test_continente_items_add_up():
    receipt = ReceiptContinente(["NIF:   PT502011475|C.S:403.827.000,00|EUR",
                                 "         Nro:FS AMO201/000001 26/09/2026 14:22",
                                 "IVA   DESCRICAO                                  VALOR",
                                 "Laticinios/Beb. Veg.:",
                                 "(A)   LEITE PAST GORDO 1L                        1,19",
                                 "Charcutaria&Queijos:",
                                 "(C)   SALMAO FUMADO  200G                        6,99",
                                 "Padaria:",
                                 "     POUPANCA                                0,22",     # already in its price
                                 "(A)   PAO DE QUEIJO UN",
                                 "      5 X 0,29                                    1,45",
                                 "(A)   PESSEGO VERMELHO",
                                 "      0,705 X 2,49                                1,76",
                                 "SUBTOTAL                                    11,39",
                                 "Desconto Cartao Utilizado                         0,70",
                                 "TOTAL A PAGAR                                10,69",
                                 "Cartao Credito                                   10,69",
                                 "Total de descontos e poupancas                    0,92",
                                 "         %IVA          Total Liq.      IVA       Total",
                                 "(A)       6,00%           3,93         0,24       4,17",
                                 "(C)      23,00%           5,24         1,28       6,52"])
    assert receipt.problems() == []
    assert [(x.department, x.name, x.vat, receipt.paid(x)) for x in receipt.items] == [
        ("Laticinios/Beb. Veg.", "LEITE PAST GORDO 1L", "A", Decimal('1.19')),
        ("Charcutaria&Queijos", "SALMAO FUMADO  200G", "C", Decimal('6.99')),
        ("Padaria", "PAO DE QUEIJO UN", "A", Decimal('1.45')),
        ("Padaria", "PESSEGO VERMELHO", "A", Decimal('1.76'))]
    assert (receipt.items[2].qty, receipt.items[2].price) == (Decimal('5'), Decimal('0.29'))
    assert (receipt.items[3].qty, receipt.items[3].price) == (Decimal('0.705'), Decimal('2.49'))
    assert receipt.discounts == [("Desconto Cartao Utilizado", Decimal('0.70'))]
    assert receipt.timestamp == datetime(2026, 9, 26, 14, 22)


def test_profiles_are_found_by_nif():
    assert shop_profile("503340855") is ReceiptLidl
    assert shop_profile("500829993") is ReceiptPingoDoce
    assert shop_profile("502011475") is ReceiptContinente
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


def test_pdf_receipt_discount_is_a_line_of_its_own(prepare_db):
    at_qr = AtQr.parse(LIDL.replace("O:11.94", "O:4.34"))
    lines = pdf_receipt(make_pdf(lidl_receipt_with_card_discount()), at_qr, CAPTURED).slip_lines()
    assert lines[-1] == {'name': "Promocao Cartao", 'amount': Decimal('0.50'), 'category': PredefinedCategory.Discounts}
    assert sum(x['amount'] for x in lines) == Decimal('-4.34')


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


def test_pdf_receipt_voucher_is_a_discount_line(prepare_db):
    at_qr = AtQr.parse(QR.replace("A:503340855", "A:500829993").replace("O:4.84", "O:5.28"))
    fragments = [(10, 800 - 15 * i, line) for i, line in enumerate(PINGO_DOCE_VOUCHER)]
    lines = pdf_receipt(make_pdf(fragments), at_qr, CAPTURED).slip_lines()
    assert lines[-1] == {'name': "V. Deposito Volta", 'amount': Decimal('0.60'), 'category': PredefinedCategory.Discounts}
    assert sum(x['amount'] for x in lines) == Decimal('-4.68')     # what the card paid


def test_pdf_receipt_voucher_reduces_a_receipt_of_one_line(prepare_db):
    at_qr = AtQr.parse(QR.replace("A:503340855", "A:500829993").replace("O:4.84", "O:5.28"))
    text = [x.replace("2,49     2,49", "2,49     2,59") for x in PINGO_DOCE_VOUCHER]    # a misread item
    fragments = [(10, 800 - 15 * i, line) for i, line in enumerate(text)]
    lines = pdf_receipt(make_pdf(fragments), at_qr, CAPTURED).slip_lines()
    assert [x['amount'] for x in lines] == [Decimal('-5.28'), Decimal('0.60')]
