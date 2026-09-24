import json
import os
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from decimal import Decimal
from jal.data_import.receipt_inbox import JalrFile, PaperItem, scan_inbox, move_done, route, Route, is_fns_qr
from tests.test_at_qr import LIDL

# Fabricated zero-value working document ('DC'), shaped like a fleet-card fuel delivery note
ZERO_DC = "A:500000000*B:999999990*C:PT*D:DC*E:F*F:20260924*G:DC 01/123*H:0*I1:0*N:0.00*O:0.00*Q:abcd*R:0000"
FNS = "t=20240115T1830&s=1234.50&fn=7380440700000000&i=12345&fp=1234567890&n=1"


# Writes a container the way the ReceiptScan app does (see receipt.schema.json 'jal.receipt/1')
def make_jalr(folder, name, kind="paper_scan", codes=(), schema="jal.receipt/1",
              captured_at="2026-08-14T18:42:00+01:00", extra=None, pdf=b"%PDF-1.4 fake") -> str:
    data = {
        "schema": schema,
        "id": "8f2a1c44-6b3e-4d19-9a7c-2e5f0b81d3a6",
        "captured_at": captured_at,
        "device": {"model": "Pixel 9 Pro", "app_version": "0.1.0"},
        "source": {"kind": kind, "pages": 1},
        "codes": [{"format": "QR_CODE", "raw": x, "page": 1} for x in codes],
        "receipt": {"country": None, "total": None, "tax_lines": []},
        "validation": {"status": "unchecked", "checks": []}
    }
    if kind != "pdf_import":
        data['source']['images'] = [{"file": "scan-1.jpg", "page": 1, "width": 10, "height": 20}]
    data.update(extra or {})
    path = os.path.join(folder, name)
    with zipfile.ZipFile(path, 'w') as container:
        container.writestr("receipt.json", json.dumps(data))
        if kind == "pdf_import":
            container.writestr("original.pdf", pdf)
        else:
            container.writestr("scan-1.jpg", b"fake")
    return path


# 'paper' and 'validation' blocks of a scan; items are (role, text, amount) or dicts of all the fields
def paper_scan(items, status="green", hypothesis=None, tax_table=()) -> dict:
    rows = []
    for x in items:
        if isinstance(x, tuple):
            role, text, amount = x
            x = {"role": role, "text": text, "amount": amount,
                 "sign_printed": "positive" if role == "item" else "negative", "tax_code": "A"}
        rows.append(x)
    return {"paper": {"shop_name": None, "printed_at": None, "tax_table": list(tax_table), "items": rows},
            "validation": {"status": status, "checks": [], "discount_hypothesis": hypothesis}}


# ----------------------------------------------------------------------------------------------------------------------
def test_open_reads_what_jal_needs(tmp_path):
    jalr = JalrFile.open(make_jalr(tmp_path, "20260814-184200-8f2a1c44.jalr", codes=[LIDL]))
    assert jalr.name == "20260814-184200-8f2a1c44.jalr"
    assert jalr.kind == JalrFile.PAPER_SCAN
    assert jalr.captured_at == datetime(2026, 8, 14, 18, 42, tzinfo=timezone(timedelta(hours=1)))
    assert jalr.pages == 1
    assert jalr.image_names == ["scan-1.jpg"]
    assert len(jalr.codes) == 1
    assert jalr.codes[0].format == "QR_CODE" and jalr.codes[0].raw == LIDL and jalr.codes[0].page == 1


def test_pdf_bytes_come_back_untouched(tmp_path):
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", kind="pdf_import"))
    assert jalr.pdf_bytes() == b"%PDF-1.4 fake"
    assert jalr.image_names == []


def test_utc_capture_time_written_as_z(tmp_path):
    # The phone's 'XXX' pattern writes 'Z' for a zero offset - Portugal in winter
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", captured_at="2026-01-10T09:05:00Z"))
    assert jalr.captured_at == datetime(2026, 1, 10, 9, 5, tzinfo=timezone.utc)


def test_unknown_keys_and_minor_versions_are_accepted(tmp_path):
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", schema="jal.receipt/1.3", extra={"ocr": {"lines": []}}))
    assert jalr is not None


def test_unreadable_files_are_refused(tmp_path):
    part = tmp_path / "b.jalr"
    part.write_bytes(b"PK\x03\x04 half an upload")
    assert JalrFile.open(str(part)) is None
    assert JalrFile.open(make_jalr(tmp_path, "c.jalr", schema="jal.receipt/2")) is None
    assert JalrFile.open(make_jalr(tmp_path, "d.jalr", schema="other/1")) is None
    assert JalrFile.open(make_jalr(tmp_path, "e.jalr", kind="fax")) is None
    assert JalrFile.open(make_jalr(tmp_path, "f.jalr", captured_at="2026-08-14T18:42:00")) is None  # no zone
    no_json = tmp_path / "g.jalr"
    with zipfile.ZipFile(no_json, 'w') as container:
        container.writestr("scan-1.jpg", b"fake")
    assert JalrFile.open(str(no_json)) is None


def test_scan_lists_finished_files_oldest_first(tmp_path):
    make_jalr(tmp_path, "20260922-114518-1fe3ae17.jalr")
    make_jalr(tmp_path, "20260922-104646-193cf0e1.jalr")
    make_jalr(tmp_path, "20260922-120000-00000000.jalr.part")           # still being written by the phone
    (tmp_path / "20260922-120100-11111111.jalr").write_bytes(b"PK\x03")  # still being uploaded
    (tmp_path / "notes.txt").write_text("not a receipt")
    os.makedirs(tmp_path / "done")
    make_jalr(tmp_path / "done", "20260901-000000-22222222.jalr")
    assert [x.name for x in scan_inbox(str(tmp_path))] == ["20260922-104646-193cf0e1.jalr",
                                                           "20260922-114518-1fe3ae17.jalr"]


def test_scan_of_a_missing_folder_is_empty(tmp_path):
    assert scan_inbox('') == []
    assert scan_inbox(str(tmp_path / "absent")) == []


def test_move_done(tmp_path):
    path = make_jalr(tmp_path, "a.jalr")
    target = move_done(path)
    assert target == os.path.join(tmp_path, "done", "a.jalr")
    assert os.path.isfile(target) and not os.path.exists(path)
    path = make_jalr(tmp_path, "a.jalr")
    with pytest.raises(FileExistsError):
        move_done(path)
    assert os.path.isfile(path)


# ----------------------------------------------------------------------------------------------------------------------
def test_fns_qr_detection():
    assert is_fns_qr(FNS)
    assert not is_fns_qr(LIDL)
    assert not is_fns_qr(FNS.replace("&fp=1234567890", ""))


def test_route_fns_from_any_source(tmp_path):
    for kind in (JalrFile.PAPER_SCAN, JalrFile.IMAGE_IMPORT, JalrFile.PDF_IMPORT):
        jalr = JalrFile.open(make_jalr(tmp_path, f"{kind}.jalr", kind=kind, codes=["7123529", FNS]))
        result = route(jalr)
        assert result.kind == Route.FNS and result.code == FNS


def test_route_pt_qr_from_paper_and_images(tmp_path):
    for kind in (JalrFile.PAPER_SCAN, JalrFile.IMAGE_IMPORT):
        jalr = JalrFile.open(make_jalr(tmp_path, f"{kind}.jalr", kind=kind, codes=["7123529", LIDL]))
        result = route(jalr)
        assert result.kind == Route.PT_QR
        assert result.at_qr.number == "503340855:FS 0421/000317"


def test_route_pdf_with_and_without_qr(tmp_path):
    result = route(JalrFile.open(make_jalr(tmp_path, "a.jalr", kind="pdf_import", codes=["888049542088", LIDL])))
    assert result.kind == Route.PDF and result.at_qr.nif == "503340855"
    result = route(JalrFile.open(make_jalr(tmp_path, "b.jalr", kind="pdf_import")))
    assert result.kind == Route.PDF and result.at_qr is None


def test_route_credit_note(tmp_path):
    credit_note = LIDL.replace("D:FS", "D:NC")
    result = route(JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[credit_note])))
    assert result.kind == Route.PT_QR and result.at_qr.is_return


def test_route_unsupported(tmp_path):
    cases = [([], Route.NO_CODE),
             (["7123529"], Route.UNKNOWN_CODE),
             ([LIDL.replace("D:FS", "D:GR")], Route.DOCUMENT_TYPE),      # delivery note, not a sale
             ([LIDL.replace("E:N", "E:A")], Route.DOCUMENT_STATUS)]      # annulled
    for i, (codes, reason) in enumerate(cases):
        result = route(JalrFile.open(make_jalr(tmp_path, f"{i}.jalr", kind="image_import", codes=codes)))
        assert (result.kind, result.reason) == (Route.UNSUPPORTED, reason)


def test_route_no_value_by_qr_total_with_and_without_phone_status(tmp_path):
    for i, status in enumerate(("no_value", "unchecked")):
        for kind in (JalrFile.PAPER_SCAN, JalrFile.IMAGE_IMPORT):
            jalr = JalrFile.open(make_jalr(tmp_path, f"{i}-{kind}.jalr", kind=kind, codes=[ZERO_DC],
                                           extra={"validation": {"status": status, "checks": []}}))
            result = route(jalr)
            assert (result.kind, result.reason) == (Route.UNSUPPORTED, Route.NO_VALUE)
            assert result.at_qr.total == Decimal('0.00')


def test_route_ignores_no_value_status_over_a_non_zero_qr(tmp_path):
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[LIDL],
                                   extra={"validation": {"status": "no_value", "checks": []}}))
    assert route(jalr).kind == Route.PT_QR


def test_route_currency_comes_from_the_fiscal_code(tmp_path):
    assert route(JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[LIDL]))).currency == "EUR"
    assert route(JalrFile.open(make_jalr(tmp_path, "b.jalr", kind="pdf_import", codes=[LIDL]))).currency == "EUR"
    assert route(JalrFile.open(make_jalr(tmp_path, "c.jalr", codes=[FNS]))).currency == "RUB"
    assert route(JalrFile.open(make_jalr(tmp_path, "d.jalr", kind="pdf_import"))).currency == ''
    assert route(JalrFile.open(make_jalr(tmp_path, "e.jalr", codes=[ZERO_DC]))).currency == "EUR"

# ----------------------------------------------------------------------------------------------------------------------
def test_paper_block_is_read(tmp_path):
    item = {"role": "item", "text": "BANANA", "amount": "1.41", "sign_printed": "positive", "quantity": "0.705",
            "unit_price": "2.00", "unit": "kg", "tax_code": "A", "department": "FRUTAS", "source_lines": [3, 4],
            "confidence": 0.9}
    table = [{"code": "A", "rate": "6.00", "base": "1.33", "tax": "0.08", "total": "1.41", "source_line": 20}]
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[LIDL],
                                   extra=paper_scan([item, ("discount", "Promo", "0.10")], hypothesis="netted",
                                                    tax_table=table)))
    assert jalr.validation_status == "green" and jalr.discount_hypothesis == JalrFile.NETTED
    assert jalr.paper_items[0] == PaperItem("item", "BANANA", Decimal('1.41'), "positive", Decimal('0.705'),
                                            Decimal('2.00'), "kg", "A", "FRUTAS")
    assert jalr.paper_items[1].role == PaperItem.DISCOUNT and jalr.paper_items[1].quantity is None
    assert jalr.tax_table == [{'code': "A", 'rate': Decimal('6.00'), 'base': Decimal('1.33'),
                               'tax': Decimal('0.08'), 'total': Decimal('1.41')}]


def test_scan_without_paper_block(tmp_path):
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[LIDL]))
    assert jalr.paper_items == [] and jalr.tax_table == []
    assert jalr.validation_status == "unchecked" and jalr.discount_hypothesis == ''


def test_malformed_paper_block_leaves_the_file_readable(tmp_path):
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[LIDL],
                                   extra=paper_scan([("item", "BANANA", "1,41")])))
    assert jalr is not None and jalr.paper_items == []
    assert route(jalr).kind == Route.PT_QR


def test_route_items_of_a_green_paper_scan_only(tmp_path):
    items = [("item", "BANANA", "11.94")]
    jalr = JalrFile.open(make_jalr(tmp_path, "a.jalr", codes=[LIDL], extra=paper_scan(items)))
    assert route(jalr).kind == Route.PT_ITEMS and route(jalr).at_qr.total == Decimal('11.94')
    for i, status in enumerate(("amber", "red", "unchecked")):
        jalr = JalrFile.open(make_jalr(tmp_path, f"{status}.jalr", codes=[LIDL], extra=paper_scan(items, status)))
        assert route(jalr).kind == Route.PT_QR
    jalr = JalrFile.open(make_jalr(tmp_path, "b.jalr", kind="image_import", codes=[LIDL], extra=paper_scan(items)))
    assert route(jalr).kind == Route.PT_QR
    jalr = JalrFile.open(make_jalr(tmp_path, "c.jalr", codes=[LIDL], extra=paper_scan([])))
    assert route(jalr).kind == Route.PT_QR
    jalr = JalrFile.open(make_jalr(tmp_path, "d.jalr", codes=[LIDL.replace("E:N", "E:A")], extra=paper_scan(items)))
    assert route(jalr).reason == Route.DOCUMENT_STATUS
