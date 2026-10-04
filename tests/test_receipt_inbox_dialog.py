import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt, QDateTime, QDate, QTime
from PySide6.QtWidgets import QWidget, QHeaderView, QLineEdit, QMessageBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ledger
from tests.test_at_qr import LIDL
from tests.test_receipt_inbox import make_jalr, paper_scan, FNS
from tests.test_receipt_pdf import make_pdf, lidl_receipt, QR, invoice, invoice_fragments
from jal.constants import PredefinedCategory, PredefinedAccountType, AccountData
from jal.db.account import JalAccountCreator
from jal.db.db import JalDB
from jal.db.peer import JalPeer
from jal.db.clock import local_zone
from jal.db.settings import JalSettings
from jal.db.operations import IncomeSpending
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.receipt import LineTrust, Verdict
from jal.data_import.receipt_inbox import JalrFile
from jal.data_import.receipt_api.offline_receipt import ReceiptOffline, paper_lines
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS
from jal.data_import.shop_receipt import ImportReceiptDialog, RECEIPT_INBOX_SETTING

LISBON_SUMMER = timezone(timedelta(hours=1))
RUB, USD, EUR = 1, 2, 3       # currency ids of the test database
NUMBER = "503340855:FS 0421/000317"


def _local(year, month, day, hour=0, minute=0) -> QDateTime:
    return QDateTime(QDate(year, month, day), QTime(hour, minute), local_zone())


# ----------------------------------------------------------------------------------------------------------------------
def test_tier0_is_one_negative_line_of_the_total(prepare_db):
    receipt = ReceiptOffline.from_at_qr(AtQr.parse(LIDL), datetime(2026, 8, 14, 18, 42, tzinfo=LISBON_SUMMER))
    assert receipt.slip_lines() == [{'name': "NIF 503340855", 'amount': Decimal('-11.94')}]
    assert receipt.shop_name() == "NIF 503340855"
    assert receipt.number() == NUMBER
    assert receipt.datetime() == _local(2026, 8, 14, 18, 42)


def test_tier0_scanned_on_a_later_day_has_no_time(prepare_db):
    receipt = ReceiptOffline.from_at_qr(AtQr.parse(LIDL), datetime(2026, 8, 20, 9, 5, tzinfo=LISBON_SUMMER))
    assert receipt.datetime() == _local(2026, 8, 14)


def test_tier0_credit_note_is_money_back(prepare_db):
    credit_note = AtQr.parse(LIDL.replace("D:FS", "D:NC"))
    receipt = ReceiptOffline.from_at_qr(credit_note, datetime(2026, 8, 14, 18, 42, tzinfo=LISBON_SUMMER))
    assert receipt.slip_lines()[0]['amount'] == Decimal('11.94')


# ----------------------------------------------------------------------------------------------------------------------
PHARMACY = LIDL.replace("A:503340855", "A:509103774")     # a shop without a profile


# Lines of a GREEN scan whose items say what they did ('effect'), and whether they are proven
def _proven(tmp_path, qr, items, total=None, tax_table=()) -> tuple:
    qr = qr if total is None else qr.replace("O:11.94", f"O:{total}")
    extra = paper_scan(items, tax_table=tax_table, effect=True)
    return paper_lines(JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[qr], extra=extra)), AtQr.parse(qr))


def _amounts(result: tuple) -> list:
    return [x['amount'] for x in result[0]]


def _proven_line(name, amount, **kwargs) -> dict:
    return dict(name=name, amount=Decimal(amount), trust=LineTrust.PROVEN, **kwargs)


def test_paper_items_are_lines(prepare_db, tmp_path):
    items = [{"role": "item", "text": "BANANA", "amount": "1.41", "sign_printed": "positive", "quantity": "0.705",
              "unit_price": "2.00", "tax_code": "A"},
             ("item", "LEITE", "10.53")]
    assert _proven(tmp_path, PHARMACY, items) == (
        [_proven_line("BANANA (0.705 x 2.00)", '-1.41'), _proven_line("LEITE", '-10.53')], True)


def test_paper_items_of_a_credit_note_are_money_back(prepare_db, tmp_path):
    assert _proven(tmp_path, PHARMACY.replace("D:FS", "D:NC"), [("item", "LEITE", "11.94")]) == \
        ([_proven_line("LEITE", '11.94')], True)


# Lines that say what they did but miss the QR's total are loaded as read, nothing folded, for the user to check
def test_effect_lines_that_miss_the_total_are_not_proven(prepare_db, tmp_path):
    items = [("item", "LEITE", "12.94"), ("discount", "Promo", "1.00")]
    lines, proven = _proven(tmp_path, PHARMACY, items, total="11.90")
    assert not proven
    assert [(x['name'], x['amount']) for x in lines] == [("LEITE", Decimal('-12.94')), ("Promo", Decimal('1.00'))]
    assert {x['trust'] for x in lines} == {LineTrust.UNRELIABLE}      # the fixture gives no OCR confidence


PINGO_DOCE = PHARMACY.replace("A:" + PHARMACY[2:11], "A:500829993")
PAYMENTS = {"ocr": {"lines": [{"text": x} for x in ("Resumo", "TOTAL A PAGAR 11,94", "V. Deposito Volta 0,60",
                                                    "Multibanco 11,34")]}}


def test_paper_voucher_is_a_discount_line(owner, inbox):
    extra = dict(paper_scan([("item", "LEITE", "11.94")], effect=True), **PAYMENTS)
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[PINGO_DOCE], extra=extra)
    make_jalr(inbox, "20260814-184300-00000002.jalr", codes=[PINGO_DOCE.replace("G:", "G:X")], extra=PAYMENTS)
    dialog = _dialog(owner)
    voucher = {'name': "V. Deposito Volta", 'category': PredefinedCategory.Discounts, 'tag': None,
               'amount': Decimal('0.60'), 'trust': ''}
    for row, first in ((0, "LEITE"), (1, "NIF 500829993")):     # with items, and a QR alone
        dialog.ui.InboxList.setCurrentCell(row, 0)
        dialog.loadInboxReceipt()
        lines = dialog.slip_lines.to_dict('records')
        assert lines[0]['name'] == first and lines[-1] == voucher
        assert sum(x['amount'] for x in lines) == Decimal('-11.34')
        assert dialog.ui.DifferenceLbl.text() == "Difference: 0.00"     # the voucher is off the total to pay


# Items priced net of VAT add up to the QR's base 10.66: 6% 6.92 + 0.42, 23% 3.74 + 0.86 (items' own VAT 0.87)
NET_TAX_TABLE = [{"code": "6,00%", "rate": "6.00", "base": "6.92", "tax": "0.42", "total": "7.34"},
                 {"code": "23,00%", "rate": "23.00", "base": "3.74", "tax": "0.86", "total": "4.60"}]


def _net_scan(tmp_path, tax_table=NET_TAX_TABLE, codes=("6%", "23%", "23%", "23%")) -> tuple:
    items = [dict(role="item", text=text, amount=amount, sign_printed="positive", tax_code=code)
             for text, amount, code in zip(("LEITE", "VINHO", "CERVEJA", "SUMO"), ("6.92", "1.25", "1.24", "1.25"),
                                           codes)]
    return _proven(tmp_path, PHARMACY, items, tax_table=tax_table)


def test_items_net_of_vat_get_it_added(prepare_db, tmp_path):
    result = _net_scan(tmp_path)
    assert result[1] and _amounts(result) == [Decimal('-7.34'), Decimal('-1.53'), Decimal('-1.53'), Decimal('-1.54')]


def test_items_net_of_vat_need_their_vat_table_row(prepare_db, tmp_path):
    net = [Decimal('-6.92'), Decimal('-1.25'), Decimal('-1.24'), Decimal('-1.25')]     # as read, VAT not added
    for result in (_net_scan(tmp_path, tax_table=()), _net_scan(tmp_path, codes=("6%", "13%", "23%", "23%")),
                   _net_scan(tmp_path, codes=("23%", "6%", "23%", "23%"))):     # the last: rows' bases don't match
        assert not result[1] and _amounts(result) == net


# A fabricated shop that prints a discount off the whole receipt: A = 5.00 - 0.60, C = 7.00 - 0.40
def _receipt_discount(qr=PHARMACY, vat=("4.40", "6.60")) -> tuple:
    items = [dict(role="item", text="LEITE", amount="5.00", sign_printed="positive", tax_code="A", source_lines=[1]),
             dict(role="item", text="SALMAO", amount="7.00", sign_printed="positive", tax_code="C", source_lines=[2]),
             dict(role="discount", text="Desconto Cartao", amount="1.00", sign_printed="positive", source_lines=[4],
                  scope="receipt")]
    tax_table = [{"code": "A", "total": vat[0]}, {"code": "C", "total": vat[1]}]
    extra = paper_scan(items, tax_table=tax_table, effect=True)
    extra.update(_ocr("SHOP", "(A) LEITE 5,00", "(C) SALMAO 7,00", "SUBTOTAL 12,00", "Desconto Cartao 1,00",
                      "TOTAL A PAGAR 11,00"))
    return qr.replace("O:11.94", "O:11.00"), extra


def _receipt_discount_scan(tmp_path, **kwargs) -> tuple:
    qr, extra = _receipt_discount(**kwargs)
    return paper_lines(JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[qr], extra=extra)), AtQr.parse(qr))


def test_receipt_discount_is_a_line_of_its_own(prepare_db, tmp_path):
    assert _receipt_discount_scan(tmp_path) == ([
        _proven_line("LEITE", '-5.00'), _proven_line("SALMAO", '-7.00'),
        _proven_line("Desconto Cartao", '1.00', category=PredefinedCategory.Discounts)], True)
    result = _receipt_discount_scan(tmp_path, qr=PHARMACY.replace("D:FS", "D:NC"))
    assert result[1] and _amounts(result) == [Decimal('5.00'), Decimal('7.00'), Decimal('-1.00')]


# SACO's VAT code wasn't read: its 0.20 may be in either row, the rest must still add up to the discount
def test_item_without_vat_code_beside_a_receipt_discount(prepare_db, tmp_path):
    def scan(vat):
        qr, extra = _receipt_discount(vat=vat)
        extra['paper']['items'].insert(0, dict(role="item", text="SACO", amount="0.20", sign_printed="positive",
                                               source_lines=[0], effect="charge"))
        qr = qr.replace("O:11.00", "O:11.20")
        return paper_lines(JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[qr], extra=extra)), AtQr.parse(qr))
    amounts = [Decimal('-0.20'), Decimal('-5.00'), Decimal('-7.00'), Decimal('1.00')]
    result = scan(("4.60", "6.60"))
    assert result[1] and _amounts(result) == amounts
    result = scan(("4.40", "6.60"))      # the table is 0.20 short of the items less the discount
    assert not result[1] and _amounts(result) == amounts


def test_receipt_discount_must_be_shared_by_the_vat_table(prepare_db, tmp_path):
    assert not _receipt_discount_scan(tmp_path, vat=("3.90", "7.10"))[1]      # C would be dearer than its items
    assert not _receipt_discount_scan(tmp_path, vat=("4.50", "6.60"))[1]      # the shares make 0.90, not 1.00


def test_receipt_discount_shared_by_vat_rows_of_the_items_rates(prepare_db, tmp_path):
    qr, extra = _receipt_discount()
    for item, code in zip(extra['paper']['items'], ("6%", "23%")):
        item['tax_code'] = code
    extra['paper']['tax_table'] = [{"code": "6,00%", "rate": "6.00", "total": "4.40"},
                                   {"code": "23,00%", "rate": "23.00", "total": "6.60"}]
    result = paper_lines(JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[qr], extra=extra)), AtQr.parse(qr))
    assert result[1] and _amounts(result) == [Decimal('-5.00'), Decimal('-7.00'), Decimal('1.00')]


# A GREEN file says what each line did ('effect'); jal follows it with no reading, no subtotal words and no profile
def _effect_scan(tmp_path, qr, lines, total) -> tuple:
    items = [dict(role=role, text=text, amount=amount, sign_printed="negative" if role == "item" and effect == "deduction"
                  else "positive", effect=effect, source_lines=[n], **({"scope": scope} if scope else {}))
             for n, (role, text, amount, effect, scope) in enumerate(lines)]
    qr = qr.replace("O:11.94", f"O:{total}")
    return paper_lines(JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[qr], extra=paper_scan(items))),
                       AtQr.parse(qr))


def test_effect_folds_item_deductions_and_keeps_receipt_ones(prepare_db, tmp_path):
    lines = [("item", "LEITE", "5.00", "charge", None),
             ("discount", "Promo", "0.50", "deduction", "item"),
             ("item", "SALMAO", "7.00", "charge", None),
             ("discount", "POUPANCA", "0.22", "none", "item"),          # already in SALMAO's price
             ("item", "TARA", "0.30", "deduction", None),               # money back on an item line
             ("discount", "Desconto Global", "1.00", "deduction", "receipt")]
    assert _effect_scan(tmp_path, PHARMACY, lines, "10.20") == ([
        _proven_line("LEITE", '-4.50'), _proven_line("SALMAO", '-7.00'), _proven_line("TARA", '0.30'),
        _proven_line("Desconto Global", '1.00', category=PredefinedCategory.Discounts)], True)
    result = _effect_scan(tmp_path, PHARMACY, lines, "10.42")     # lines that don't give the QR total: all six as read
    assert not result[1] and _amounts(result) == [Decimal('-5.00'), Decimal('0.50'), Decimal('-7.00'), Decimal('0.22'),
                                                  Decimal('0.30'), Decimal('1.00')]


# A Continente scan: POUPANCA under an item is already in its price, 'Desconto Cartao' below SUBTOTAL is money off
CONTINENTE = PHARMACY.replace("A:" + PHARMACY[2:11], "A:502011475")


def test_effect_is_taken_over_the_shop_profile(prepare_db, tmp_path):
    lines = [("item", "LEITE", "5.00", "charge", None), ("discount", "POUPANCA", "0.22", "deduction", "item"),
             ("item", "SALMAO", "7.00", "charge", None)]
    assert _effect_scan(tmp_path, CONTINENTE, lines, "11.78") == (          # Continente's profile wouldn't net it
        [_proven_line("LEITE", '-4.78'), _proven_line("SALMAO", '-7.00')], True)


# ----------------------------------------------------------------------------------------------------------------------
# A file without 'effect' (AMBER, RED, or written before the phone stamped it) is loaded as read: items as spent,
# every discount a line of its own, each line marked by how well it was read
def _as_read(tmp_path, qr, items, status="amber") -> tuple:
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[qr] if qr else [], extra=paper_scan(items, status)))
    return paper_lines(jalr, AtQr.parse(qr) if qr else None)


def _read_item(role, text, amount, confidence=None, sign="positive", scope=None) -> dict:
    item = dict(role=role, text=text, amount=amount, sign_printed=sign, confidence=confidence)
    return dict(item, scope=scope) if scope else item


def test_unproven_lines_are_loaded_as_read_and_marked_by_confidence(prepare_db, tmp_path):
    items = [_read_item("item", "LEITE", "12.94", 0.9), _read_item("discount", "Promo", "1.00", 0.5, scope="item"),
             _read_item("item", "PAO", "0.50", 0.49), _read_item("item", "TARA", "0.30", 0.8, sign="negative"),
             _read_item("item", "SACO", "0.10")]
    assert _as_read(tmp_path, PHARMACY, items) == ([
        {'name': "LEITE", 'amount': Decimal('-12.94'), 'trust': LineTrust.READ},
        {'name': "Promo", 'amount': Decimal('1.00'), 'category': PredefinedCategory.Discounts, 'trust': LineTrust.READ},
        {'name': "PAO", 'amount': Decimal('-0.50'), 'trust': LineTrust.UNRELIABLE},
        {'name': "TARA", 'amount': Decimal('0.30'), 'trust': LineTrust.READ},
        {'name': "SACO", 'amount': Decimal('-0.10'), 'trust': LineTrust.UNRELIABLE}], False)     # confidence unknown
    result = _as_read(tmp_path, PHARMACY.replace("D:FS", "D:NC"), items)
    assert _amounts(result) == [Decimal('12.94'), Decimal('-1.00'), Decimal('0.50'), Decimal('-0.30'), Decimal('0.10')]


# A GREEN file older than 'effect' is not proven to jal either, though its lines happen to add up
def test_green_file_without_effect_is_loaded_as_read(prepare_db, tmp_path):
    lines, proven = _as_read(tmp_path, PHARMACY, [_read_item("item", "LEITE", "11.94", 0.9)], status="green")
    assert not proven and lines == [{'name': "LEITE", 'amount': Decimal('-11.94'), 'trust': LineTrust.READ}]


# Continente prints item savings that are already in the price: its profile leaves them out, but only where the
# phone says the discount was printed under an item
def test_shop_profile_leaves_out_item_discounts_already_in_the_price(prepare_db, tmp_path):
    items = [_read_item("item", "LEITE", "5.00", 0.9), _read_item("discount", "POUPANCA", "0.22", 0.9, scope="item"),
             _read_item("discount", "Desconto Cartao Utilizado", "1.00", 0.9, scope="receipt"),
             _read_item("discount", "Desconto", "0.10", 0.9)]
    assert _amounts(_as_read(tmp_path, CONTINENTE, items)) == [Decimal('-5.00'), Decimal('1.00'), Decimal('0.10')]
    assert _amounts(_as_read(tmp_path, PHARMACY, items)) == \
        [Decimal('-5.00'), Decimal('0.22'), Decimal('1.00'), Decimal('0.10')]
    assert _amounts(_as_read(tmp_path, LIDL, items)) == \
        [Decimal('-5.00'), Decimal('0.22'), Decimal('1.00'), Decimal('0.10')]          # Lidl nets its discounts


# Nothing proves a RED scan, however well it was read; one without a fiscal code is a purchase
def test_red_scan_lines_are_unreliable(prepare_db, tmp_path):
    items = [_read_item("item", "LEITE", "12.94", 0.95), _read_item("discount", "Promo", "1.00", 0.95)]
    for qr in (PHARMACY, None):
        lines, proven = _as_read(tmp_path, qr, items, status="red")
        assert not proven and [x['amount'] for x in lines] == [Decimal('-12.94'), Decimal('1.00')]
        assert {x['trust'] for x in lines} == {LineTrust.UNRELIABLE}


# ----------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def owner(prepare_db_ledger):
    parent = QWidget()
    yield parent
    parent.deleteLater()


@pytest.fixture
def inbox(tmp_path):
    folder = tmp_path / "inbox"
    folder.mkdir()
    JalSettings().setValue(RECEIPT_INBOX_SETTING, str(folder))
    return folder


def _dialog(owner) -> ImportReceiptDialog:
    return ImportReceiptDialog(owner)


def _load_and_add(dialog, row=0):
    dialog.ui.InboxList.setCurrentCell(row, 0)
    dialog.loadInboxReceipt()
    dialog.ui.AccountEdit.selected_id = 1
    dialog.ui.PeerEdit.selected_id = 1
    dialog.slip_lines['category'] = PredefinedCategory.Fees
    dialog.addOperation()


def _operations() -> int:
    return JalDB._read("SELECT COUNT(*) FROM actions")


def test_no_inbox_folder(owner):
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.rowCount() == 0
    assert not dialog.ui.InboxLoadBtn.isEnabled()
    assert "Preferences" in dialog.ui.InboxFolderLbl.text()


def test_inbox_is_listed(owner, inbox):
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL])
    make_jalr(inbox, "20260814-184300-00000002.jalr", kind="image_import")
    dialog = _dialog(owner)
    assert dialog.ui.InboxFolderLbl.text() == str(inbox)
    assert dialog.ui.InboxList.rowCount() == 2
    assert dialog.ui.InboxList.item(0, 1).text() == "Paper scan"
    assert dialog.ui.InboxList.item(0, 2).text() == "Portuguese QR: NIF 503340855, 11.94"
    assert dialog.ui.InboxList.item(1, 2).text() == "Unsupported: no QR code found"


def test_paper_scan_is_imported_and_leaves_the_inbox(owner, inbox):
    path = make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL])
    dialog = _dialog(owner)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.ui.SlipShopName.text() == "NIF 503340855"
    assert dialog.ui.SlipDateTime.dateTime() == _local(2026, 8, 14, 18, 42)
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-11.94')]

    dialog.ui.AccountEdit.selected_id = 1
    dialog.ui.PeerEdit.selected_id = 1
    dialog.slip_lines['category'] = PredefinedCategory.Fees
    dialog.addOperation()
    oid = IncomeSpending.find_by_number(NUMBER)
    assert oid
    operation = IncomeSpending(oid)
    assert operation.amount() == Decimal('-11.94')
    assert operation.timestamp() == _local(2026, 8, 14, 18, 42).toSecsSinceEpoch()
    assert not os.path.exists(path)
    assert os.path.isfile(inbox / "done" / "20260814-184200-00000001.jalr")
    assert dialog.ui.InboxList.rowCount() == 0


def test_the_same_receipt_twice_is_refused(owner, inbox):
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL])
    make_jalr(inbox, "20260814-190000-00000002.jalr", kind="image_import", codes=[LIDL])   # its screenshot as well
    dialog = _dialog(owner)
    before = _operations()
    _load_and_add(dialog)
    assert _operations() == before + 1
    _load_and_add(dialog)
    assert _operations() == before + 1
    assert sorted(os.listdir(inbox / "done")) == ["20260814-184200-00000001.jalr", "20260814-190000-00000002.jalr"]


def test_cleared_receipt_stays_in_the_inbox(owner, inbox):
    path = make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL])
    dialog = _dialog(owner)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    dialog.clearSlipData()
    dialog.addOperation()                     # nothing is loaded any more
    assert os.path.isfile(path)
    assert IncomeSpending.find_by_number(NUMBER) == 0


def test_peer_of_the_last_receipt_is_not_reused(owner, inbox):
    JalPeer(1).add_or_update_mapped_name("NIF 503340855")
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL])
    make_jalr(inbox, "20260814-184300-00000002.jalr", codes=[LIDL.replace("A:503340855", "A:509999999")])
    dialog = _dialog(owner)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.ui.PeerEdit.selected_id == 1
    dialog.ui.InboxList.setCurrentCell(1, 0)
    dialog.loadInboxReceipt()
    assert dialog.ui.PeerEdit.selected_id == 0


def test_unsupported_file_loads_nothing(owner, inbox):
    path = make_jalr(inbox, "20260814-184300-00000002.jalr", kind="image_import")
    dialog = _dialog(owner)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.slip_lines is None
    assert os.path.isfile(path)


# ----------------------------------------------------------------------------------------------------------------------
FNS_NUMBER = "7380440700000000:12345:1234567890"
# What FNS returns for a receipt, trimmed to the keys the dialog reads; amounts are in kopecks
FNS_SLIP = {'dateTime': 1705343400, 'operationType': 1, 'user': 'ООО "Магазин"',
            'items': [{'name': 'Хлеб', 'quantity': 1, 'price': 5990, 'sum': 5990},
                      {'name': 'Молоко', 'quantity': 2, 'price': 8990, 'sum': 17980}]}


def test_fns_number_comes_from_the_qr(owner):
    assert ReceiptRuFNS(qr_text=FNS).number() == FNS_NUMBER


def test_fns_file_goes_to_the_fns_download(owner, inbox, monkeypatch):
    path = make_jalr(inbox, "20240115-183000-00000003.jalr", codes=["4607035400014", FNS])
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "Russian QR"
    monkeypatch.setattr(dialog, "downloadSlipJSON", lambda: None)   # FNS itself is not asked
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert isinstance(dialog.receipt_api, ReceiptRuFNS)
    dialog.receipt_api.slip_json = FNS_SLIP
    dialog.slip_loaded()
    assert dialog.ui.SlipShopName.text() == 'ООО "Магазин"'
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-59.9'), Decimal('-179.8')]

    dialog.ui.AccountEdit.selected_id = 1
    dialog.ui.PeerEdit.selected_id = 1
    dialog.slip_lines['category'] = PredefinedCategory.Fees
    dialog.addOperation()
    oid = IncomeSpending.find_by_number(FNS_NUMBER)
    assert oid
    assert IncomeSpending(oid).amount() == Decimal('-239.7')
    assert not os.path.exists(path)


def test_malformed_fns_code_loads_nothing(owner, inbox):
    path = make_jalr(inbox, "20240115-183000-00000004.jalr", codes=["t=yesterday&s=1&fn=1&i=1&fp=1&n=1"])
    dialog = _dialog(owner)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.receipt_api is None and dialog.slip_lines is None
    assert os.path.isfile(path)


# ----------------------------------------------------------------------------------------------------------------------
def test_pdf_file_brings_its_items(owner, inbox):
    path = make_jalr(inbox, "20260814-190000-00000005.jalr", kind="pdf_import", codes=[QR],
                     pdf=make_pdf(lidl_receipt(), form=True))
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "PDF document"
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.slip_lines['name'].tolist() == ["TOMATE REDONDO (0.744 x 1.89)", "MORANGO 300G",
                                                  "CROISSANT CHOCOLATE 80GR (2 x 0.85)", "Saco de Papel"]
    assert sum(dialog.slip_lines['amount'].tolist()) == Decimal('-4.84')
    assert dialog.ui.SlipDateTime.dateTime() == _local(2026, 8, 14, 18, 53)

    dialog.ui.AccountEdit.selected_id = 1
    dialog.ui.PeerEdit.selected_id = 1
    dialog.slip_lines['category'] = PredefinedCategory.Fees
    dialog.addOperation()
    oid = IncomeSpending.find_by_number(NUMBER)
    assert oid and IncomeSpending(oid).amount() == Decimal('-4.84') and len(IncomeSpending(oid).lines()) == 4
    assert not os.path.exists(path)


def test_paper_scan_of_a_receipt_imported_as_pdf_is_refused(owner, inbox):
    make_jalr(inbox, "20260814-190000-00000005.jalr", kind="pdf_import", pdf=make_pdf(lidl_receipt()))  # no QR read
    make_jalr(inbox, "20260814-190100-00000006.jalr", codes=[QR])
    dialog = _dialog(owner)
    before = _operations()
    _load_and_add(dialog)
    _load_and_add(dialog)
    assert _operations() == before + 1
    assert len(os.listdir(inbox / "done")) == 2


def test_unreadable_pdf_loads_nothing(owner, inbox):
    path = make_jalr(inbox, "20260814-190000-00000007.jalr", kind="pdf_import")
    dialog = _dialog(owner)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.receipt_api is None and dialog.slip_lines is None
    assert os.path.isfile(path)


# ----------------------------------------------------------------------------------------------------------------------
def test_green_paper_scan_brings_its_items(owner, inbox):
    items = [("item", "LEITE", "12.94"), dict(role="discount", text="Promoção Lidl Plus", amount="1.00",
                                              sign_printed="negative", scope="item")]
    path = make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL], extra=paper_scan(items, effect=True))
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "Portuguese QR and items: NIF 503340855, 11.94"
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.slip_lines['name'].tolist() == ["LEITE"]
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-11.94')]
    assert dialog.slip_lines['trust'].tolist() == [LineTrust.PROVEN]
    assert dialog.ui.SlipDateTime.dateTime() == _local(2026, 8, 14, 18, 42)
    assert dialog.ui.VerdictLbl.text() == "Reconciled automatically"
    assert dialog.ui.TotalsLbl.text() == "Lines: -11.94    Receipt total: -11.94"
    assert dialog.ui.DifferenceLbl.text() == "Difference: 0.00"

    dialog.ui.AccountEdit.selected_id = 1
    dialog.ui.PeerEdit.selected_id = 1
    dialog.slip_lines['category'] = PredefinedCategory.Fees
    dialog.addOperation()
    oid = IncomeSpending.find_by_number(NUMBER)
    assert oid and IncomeSpending(oid).amount() == Decimal('-11.94')
    assert not os.path.exists(path)
    assert dialog.ui.VerdictLbl.text() == '' and dialog.ui.TotalsLbl.text() == ''     # nothing is loaded any more


def test_receipt_discount_line_comes_with_its_category(owner, inbox):
    qr, extra = _receipt_discount()
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[qr], extra=extra)
    dialog = _dialog(owner)
    _load(dialog)
    assert dialog.slip_lines['category'].tolist() == [0, 0, PredefinedCategory.Discounts]


def test_scan_without_items_is_one_line_of_the_total(owner, inbox):
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL], extra=paper_scan([], status="amber"))
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "Portuguese QR: NIF 503340855, 11.94"
    _load(dialog)
    assert dialog.slip_lines['name'].tolist() == ["NIF 503340855"]
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-11.94')]
    assert dialog.slip_lines['trust'].tolist() == ['']
    assert dialog.ui.VerdictLbl.text() == "Not reconciled, check the lines"


def _unreconciled(inbox, status="amber", codes=(LIDL,), **kwargs) -> str:
    items = [_read_item("item", "LEITE", "10.00", 0.9), _read_item("item", "PAO", "1.00", 0.3)]
    return make_jalr(inbox, "20260814-184200-00000001.jalr", codes=list(codes),
                     extra=paper_scan(items, status=status, **kwargs))


def test_amber_paper_scan_brings_its_lines_to_check(owner, inbox):
    _unreconciled(inbox)
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "Portuguese QR and items: NIF 503340855, 11.94"
    assert not dialog.ui.AddLineBtn.isEnabled() and not dialog.ui.DeleteLineBtn.isEnabled()
    _load(dialog)
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-10.00'), Decimal('-1.00')]
    assert dialog.slip_lines['trust'].tolist() == [LineTrust.READ, LineTrust.UNRELIABLE]
    assert dialog.ui.VerdictLbl.text() == "Not reconciled, check the lines"
    assert dialog.ui.TotalsLbl.text() == "Lines: -11.00    Receipt total: -11.94"
    assert dialog.ui.DifferenceLbl.text() == "Difference: 0.94"
    assert dialog.ui.AddLineBtn.isEnabled() and dialog.ui.DeleteLineBtn.isEnabled()
    assert "Read confidently" in dialog.model.data(dialog.model.index(0, 0), Qt.ToolTipRole)
    assert "Unreliable" in dialog.model.data(dialog.model.index(1, 3), Qt.ToolTipRole)


def test_lines_are_fixed_by_hand_until_they_add_up(owner, inbox):
    _unreconciled(inbox)
    dialog = _dialog(owner)
    _load(dialog)
    model, delegate, editor = dialog.model, dialog.delegate, QLineEdit(dialog)
    editor.setText("1,44")                                    # PAO was misread: -1.44 would do, the sign is the user's
    delegate.setModelData(editor, model, model.index(1, 3))
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-10.00'), Decimal('1.44')]
    assert dialog.slip_lines['trust'].tolist() == [LineTrust.READ, '']     # the user's amount carries no mark
    assert dialog.ui.DifferenceLbl.text() == "Difference: 3.38"
    editor.setText("one euro")                                # not an amount: the line stays
    delegate.setModelData(editor, model, model.index(1, 3))
    editor.setText("NaN")
    delegate.setModelData(editor, model, model.index(1, 3))
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-10.00'), Decimal('1.44')]
    editor.setText("-1.44")
    delegate.setModelData(editor, model, model.index(1, 3))
    editor.setText(" PAO DE FORMA ")
    delegate.setModelData(editor, model, model.index(1, 0))
    assert dialog.slip_lines['name'].tolist() == ["LEITE", "PAO DE FORMA"]

    dialog.addLine()                                          # an item the phone missed
    assert model.rowCount() == 3 and dialog.slip_lines.iloc[2].tolist() == ['', 0, None, Decimal('0'), '']
    assert dialog.slip_lines['category'].dtype == int
    model.setData(model.index(2, 0), "SACO")
    model.setData(model.index(2, 3), Decimal('-0.60'))
    dialog.addLine()                                          # and a line added by mistake
    dialog.ui.LinesTableView.setCurrentIndex(model.index(3, 0))
    dialog.deleteLine()
    assert dialog.slip_lines['name'].tolist() == ["LEITE", "PAO DE FORMA", "SACO"]
    assert dialog.ui.TotalsLbl.text() == "Lines: -12.04    Receipt total: -11.94"
    assert dialog.ui.DifferenceLbl.text() == "Difference: -0.10"
    dialog.ui.LinesTableView.setCurrentIndex(model.index(2, 0))
    dialog.deleteLine()
    model.setData(model.index(0, 3), Decimal('-10.50'))
    assert dialog.ui.DifferenceLbl.text() == "Difference: 0.00"


def test_lines_that_dont_add_up_are_added_on_confirmation_only(owner, inbox, monkeypatch):
    path = _unreconciled(inbox)
    dialog = _dialog(owner)
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: asked.append(args[3]) or QMessageBox.No)
    _load_and_add(dialog)
    assert len(asked) == 1 and "0.94" in asked[0]
    assert _operations() == 0 and os.path.exists(path) and dialog.slip_lines is not None
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    dialog.addOperation()
    assert IncomeSpending(IncomeSpending.find_by_number(NUMBER)).amount() == Decimal('-11.00')
    assert not os.path.exists(path)


def test_receipt_without_lines_is_not_added(owner, inbox):
    _unreconciled(inbox)
    dialog = _dialog(owner)
    _load(dialog)
    dialog.model.removeRows(0, 2)
    assert dialog.ui.TotalsLbl.text() == "Lines: 0.00    Receipt total: -11.94"
    dialog.ui.AccountEdit.selected_id = 1
    dialog.ui.PeerEdit.selected_id = 1
    dialog.addOperation()
    assert _operations() == 0


def test_green_items_that_dont_add_up_are_loaded_as_read(owner, inbox):
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL],
              extra=paper_scan([("item", "LEITE", "1.94")], effect=True))
    dialog = _dialog(owner)
    _load(dialog)
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-1.94')]
    assert dialog.ui.VerdictLbl.text() == "Not reconciled, check the lines"
    assert dialog.ui.DifferenceLbl.text() == "Difference: 10.00"


# A RED scan is loaded only after the user confirms it; its code, if jal can parse it, still gives the total to check
def test_red_scan_is_loaded_on_confirmation_only(owner, inbox, monkeypatch):
    _unreconciled(inbox, status="red")
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "Not verified, Portuguese QR: NIF 503340855, 11.94"
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.No)
    _load(dialog)
    assert dialog.slip_lines is None and dialog.ui.VerdictLbl.text() == ''
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    _load(dialog)
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-10.00'), Decimal('-1.00')]
    assert dialog.slip_lines['trust'].tolist() == [LineTrust.UNRELIABLE, LineTrust.UNRELIABLE]
    assert dialog.ui.VerdictLbl.text() == "No usable fiscal code, rescan recommended"
    assert dialog.ui.DifferenceLbl.text() == "Difference: 0.94"


# Without a code there is no total, no date and no document number: the scan's own time, and no second-import guard
def test_red_scan_without_a_code_brings_its_lines_alone(owner, inbox, monkeypatch):
    path = _unreconciled(inbox, status="red", codes=(), shop_name="MERCADO DA ESQUINA")
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "Not verified, no fiscal code"
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: asked.append(args[3]) or QMessageBox.Yes)
    _load(dialog)
    assert dialog.ui.SlipShopName.text() == "MERCADO DA ESQUINA"
    assert dialog.ui.SlipDateTime.dateTime() == _local(2026, 8, 14, 18, 42)
    assert dialog.ui.VerdictLbl.text() == "No usable fiscal code, rescan recommended"
    assert dialog.ui.TotalsLbl.text() == "Lines: -11.00" and dialog.ui.DifferenceLbl.text() == ''
    dialog.ui.AccountEdit.selected_id = 1
    dialog.ui.PeerEdit.selected_id = 1
    dialog.slip_lines['category'] = PredefinedCategory.Fees
    dialog.addOperation()
    assert len(asked) == 1                                    # the load was confirmed; there is no total to differ from
    assert _operations() == 1 and not os.path.exists(path)
    assert JalDB._read("SELECT number FROM actions") == ''


def test_skipped_file_leaves_the_inbox_without_an_operation(owner, inbox):
    first = make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL])
    second = make_jalr(inbox, "20260814-184300-00000002.jalr", kind="image_import")
    dialog = _dialog(owner)
    before = _operations()
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.skipInboxReceipt()
    assert dialog.slip_lines is None                      # the skipped receipt was the loaded one
    assert not os.path.exists(first) and os.path.isfile(inbox / "done" / "20260814-184200-00000001.jalr")
    assert dialog.ui.InboxList.rowCount() == 1
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.skipInboxReceipt()                             # an unsupported file can be skipped too
    assert not os.path.exists(second)
    assert dialog.ui.InboxList.rowCount() == 0 and not dialog.ui.InboxSkipBtn.isEnabled()
    assert _operations() == before


# ----------------------------------------------------------------------------------------------------------------------
def _card_account(cards="1234", currency_id=EUR, name='Card bank') -> int:
    account = JalAccountCreator(currency_id=currency_id, number='', name=name,
                                account_type=PredefinedAccountType.Bank).commit()
    account.set_data(AccountData.CardDigits, cards)
    return account.id()


def _ocr(*rows) -> dict:
    return {"ocr": {"engine": "test", "lines": [{"page": 1, "text": x} for x in rows]}}


def _load(dialog, row=0):
    dialog.ui.InboxList.setCurrentCell(row, 0)
    dialog.loadInboxReceipt()


def test_account_is_chosen_by_the_card_a_pdf_prints(owner, inbox):
    account_id = _card_account()
    make_jalr(inbox, "20260814-190000-00000005.jalr", kind="pdf_import", codes=[QR],
              pdf=make_pdf(lidl_receipt() + [(10, 500, "CARTAO: ****1234     TC:9E1F0B3C")], form=True))
    dialog = _dialog(owner)
    _load(dialog)
    assert dialog.ui.AccountEdit.selected_id == account_id


def test_account_is_chosen_by_the_card_a_paper_scan_reads(owner, inbox):
    account_id = _card_account()
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL], extra=_ocr("MULTIBANCO 11,94", "CARTA0: ****1234"))
    dialog = _dialog(owner)
    _load(dialog)
    assert dialog.ui.AccountEdit.selected_id == account_id


def test_card_account_is_the_one_in_the_currency_of_the_qr(owner, inbox, monkeypatch):
    _card_account(currency_id=USD, name='Card.USD')
    eur_id = _card_account(currency_id=EUR, name='Card.EUR')
    rub_id = _card_account(currency_id=RUB, name='Card.RUB')
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL], extra=_ocr("CARTAO: ****1234"))
    make_jalr(inbox, "20260814-184300-00000002.jalr", codes=[FNS], extra=_ocr("CARTAO: ****1234"))
    make_jalr(inbox, "20260814-184400-00000003.jalr", kind="pdf_import",
              pdf=make_pdf(lidl_receipt() + [(10, 500, "CARTAO: ****1234")]))       # no QR read: any currency
    dialog = _dialog(owner)
    monkeypatch.setattr(dialog, "downloadSlipJSON", lambda: None)   # FNS itself is not asked
    _load(dialog, 0)
    assert dialog.ui.AccountEdit.selected_id == eur_id
    _load(dialog, 1)
    assert dialog.ui.AccountEdit.selected_id == rub_id
    _load(dialog, 2)
    assert dialog.ui.AccountEdit.selected_id == 0          # three accounts hold the card


def test_card_account_is_the_one_in_the_currency_a_pdf_without_a_code_prints(owner, inbox):
    _card_account(cards="4321", currency_id=USD, name='Card.USD')
    eur_id = _card_account(cards="4321", currency_id=EUR, name='Card.EUR')
    make_jalr(inbox, "20260820-090500-00000001.jalr", kind="pdf_import", pdf=make_pdf(invoice_fragments(invoice())))
    dialog = _dialog(owner)
    _load(dialog)
    assert dialog.ui.AccountEdit.selected_id == eur_id
    assert dialog.ui.SlipShopName.text() == "VAT IE1234567AB"


def test_account_of_the_previous_receipt_is_not_kept(owner, inbox):
    _card_account()
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL], extra=_ocr("MULTIBANCO 11,94"))
    make_jalr(inbox, "20260814-184300-00000002.jalr", codes=[PHARMACY], extra=_ocr("CARTAO: ****9999"))
    dialog = _dialog(owner)
    for row in (0, 1):                     # no card printed; a card no account holds
        dialog.ui.AccountEdit.selected_id = 1
        _load(dialog, row)
        assert dialog.ui.AccountEdit.selected_id == 0


def test_window_size_and_line_columns_are_kept(owner, inbox):
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL])
    make_jalr(inbox, "20260814-184300-00000002.jalr", codes=[PHARMACY])
    dialog = _dialog(owner)
    dialog.show()
    dialog.resize(700, 600)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    dialog.ui.LinesTableView.setColumnWidth(1, 250)
    dialog.clearSlipData()
    dialog.reject()                            # Esc: no close event, and the lines table is empty by now
    dialog = _dialog(owner)
    dialog.show()
    assert (dialog.width(), dialog.height()) == (700, 600)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    header = dialog.ui.LinesTableView.horizontalHeader()
    assert header.sectionSize(1) == 250
    assert header.sectionResizeMode(0) == QHeaderView.Stretch
    dialog.close()
