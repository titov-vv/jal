import json
import os
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from jal.data_import.receipt_inbox import JalrFile, scan_inbox, move_done, route, Route, is_fns_qr
from tests.test_at_qr import LIDL

FNS = "t=20240115T1830&s=1234.50&fn=7380440700000000&i=12345&fp=1234567890&n=1"


# Writes a container the way the ReceiptScan app does (see receipt.schema.json 'jal.receipt/1')
def make_jalr(folder, name, kind="paper_scan", codes=(), schema="jal.receipt/1",
              captured_at="2026-08-14T18:42:00+01:00", extra=None) -> str:
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
            container.writestr("original.pdf", b"%PDF-1.4 fake")
        else:
            container.writestr("scan-1.jpg", b"fake")
    return path


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
