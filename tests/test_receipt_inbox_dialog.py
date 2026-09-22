import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from PySide6.QtCore import QDateTime, QDate, QTime
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_ledger
from tests.test_at_qr import LIDL
from tests.test_receipt_inbox import make_jalr
from constants import PredefinedCategory
from jal.db.db import JalDB
from jal.db.clock import local_zone
from jal.db.settings import JalSettings
from jal.db.operations import IncomeSpending
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.receipt_api.offline_receipt import ReceiptOffline
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
