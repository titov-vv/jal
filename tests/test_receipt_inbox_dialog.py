import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from PySide6.QtCore import QDateTime, QDate, QTime
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ledger
from tests.test_at_qr import LIDL
from tests.test_receipt_inbox import make_jalr, paper_scan, FNS
from tests.test_receipt_pdf import make_pdf, lidl_receipt, QR
from constants import PredefinedCategory
from jal.db.db import JalDB
from jal.db.clock import local_zone
from jal.db.settings import JalSettings
from jal.db.operations import IncomeSpending
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.receipt_inbox import JalrFile
from jal.data_import.receipt_api.offline_receipt import ReceiptOffline, paper_lines
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS
from jal.data_import.shop_receipt import ImportReceiptDialog, RECEIPT_INBOX_SETTING

LISBON_SUMMER = timezone(timedelta(hours=1))
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


def _paper_lines(tmp_path, qr, items, hypothesis=None, total=None) -> list:
    qr = qr if total is None else qr.replace("O:11.94", f"O:{total}")
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[qr], extra=paper_scan(items, hypothesis=hypothesis)))
    return paper_lines(jalr, AtQr.parse(qr))


def test_paper_items_are_lines(prepare_db, tmp_path):
    items = [{"role": "item", "text": "BANANA", "amount": "1.41", "sign_printed": "positive", "quantity": "0.705",
              "unit_price": "2.00", "tax_code": "A"},
             ("item", "LEITE", "10.53")]
    assert _paper_lines(tmp_path, PHARMACY, items) == [{'name': "BANANA (0.705 x 2.00)", 'amount': Decimal('-1.41')},
                                                       {'name': "LEITE", 'amount': Decimal('-10.53')}]


def test_paper_items_of_a_credit_note_are_money_back(prepare_db, tmp_path):
    lines = _paper_lines(tmp_path, PHARMACY.replace("D:FS", "D:NC"), [("item", "LEITE", "11.94")])
    assert lines == [{'name': "LEITE", 'amount': Decimal('11.94')}]


def test_paper_items_that_miss_the_total_are_refused(prepare_db, tmp_path):
    assert _paper_lines(tmp_path, PHARMACY, [("item", "LEITE", "11.93")]) == []


def test_netted_discount_reduces_its_item(prepare_db, tmp_path):
    items = [("item", "LEITE", "12.94"), ("discount", "Poupança", "1.00"), ("item", "PAO", "0.50")]
    lines = _paper_lines(tmp_path, PHARMACY, items, "netted", total="12.44")
    assert lines == [{'name': "LEITE", 'amount': Decimal('-11.94')}, {'name': "PAO", 'amount': Decimal('-0.50')}]


def test_informational_discount_is_not_money_off(prepare_db, tmp_path):
    items = [("item", "LEITE", "12.94"), ("discount", "POUPANCA", "1.00")]
    assert _paper_lines(tmp_path, PHARMACY, items, "informational", total="12.94") == \
        [{'name': "LEITE", 'amount': Decimal('-12.94')}]


def test_discount_needs_a_reading_that_balances_it(prepare_db, tmp_path):
    items = [("item", "LEITE", "12.94"), ("discount", "Poupança", "1.00")]
    for hypothesis in ("not_applicable", None):
        assert _paper_lines(tmp_path, PHARMACY, items, hypothesis, total="11.94") == []
    assert _paper_lines(tmp_path, PHARMACY, [("item", "LEITE", "11.94")], "not_applicable") != []


def test_discount_reading_must_agree_with_the_shop_profile(prepare_db, tmp_path):
    items = [("item", "LEITE", "12.94"), ("discount", "Promoção Lidl Plus", "1.00")]
    assert _paper_lines(tmp_path, LIDL, items, "netted", total="11.94") == \
        [{'name': "LEITE", 'amount': Decimal('-11.94')}]
    assert _paper_lines(tmp_path, LIDL, items, "informational", total="12.94") == []     # Lidl nets its discounts


def test_discount_above_every_item_is_refused(prepare_db, tmp_path):
    items = [("discount", "Poupança", "1.00"), ("item", "LEITE", "12.94")]
    assert _paper_lines(tmp_path, PHARMACY, items, "netted") == []


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
    items = [("item", "LEITE", "12.94"), ("discount", "Promoção Lidl Plus", "1.00")]
    path = make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL],
                     extra=paper_scan(items, hypothesis="netted"))
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "Portuguese QR and items: NIF 503340855, 11.94"
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.slip_lines['name'].tolist() == ["LEITE"]
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-11.94')]
    assert dialog.ui.SlipDateTime.dateTime() == _local(2026, 8, 14, 18, 42)

    dialog.ui.AccountEdit.selected_id = 1
    dialog.ui.PeerEdit.selected_id = 1
    dialog.slip_lines['category'] = PredefinedCategory.Fees
    dialog.addOperation()
    oid = IncomeSpending.find_by_number(NUMBER)
    assert oid and IncomeSpending(oid).amount() == Decimal('-11.94')
    assert not os.path.exists(path)


def test_amber_paper_scan_is_one_line_of_the_total(owner, inbox):
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL],
              extra=paper_scan([("item", "LEITE", "11.94")], status="amber"))
    dialog = _dialog(owner)
    assert dialog.ui.InboxList.item(0, 2).text() == "Portuguese QR: NIF 503340855, 11.94"
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.slip_lines['name'].tolist() == ["NIF 503340855"]
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-11.94')]


def test_green_items_that_dont_add_up_are_one_line_of_the_total(owner, inbox):
    make_jalr(inbox, "20260814-184200-00000001.jalr", codes=[LIDL], extra=paper_scan([("item", "LEITE", "1.94")]))
    dialog = _dialog(owner)
    dialog.ui.InboxList.setCurrentCell(0, 0)
    dialog.loadInboxReceipt()
    assert dialog.slip_lines['amount'].tolist() == [Decimal('-11.94')]


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
