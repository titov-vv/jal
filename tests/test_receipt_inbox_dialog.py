import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from PySide6.QtCore import QDateTime, QDate, QTime
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ledger
from tests.test_at_qr import LIDL
from tests.test_receipt_inbox import make_jalr, FNS
from tests.test_receipt_pdf import make_pdf, lidl_receipt, QR
from constants import PredefinedCategory
from jal.db.db import JalDB
from jal.db.clock import local_zone
from jal.db.settings import JalSettings
from jal.db.operations import IncomeSpending
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.receipt_api.offline_receipt import ReceiptOffline
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
    dialog = ImportReceiptDialog(owner)
    dialog.tensor_flow_present = False
    return dialog


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
    dialog.recognizeCategories()              # must not fail with nothing loaded
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
