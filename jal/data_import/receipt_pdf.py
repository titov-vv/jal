import io
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from PySide6.QtCore import QDateTime, QDate, QTime
from jal.db.clock import local_zone
from jal.db.helpers import remove_exponent
from jal.widgets.helpers import dependency_present
from jal.data_import.receipt import ShopReceipt, ReceiptItem, parse_header, parse_total, shop_profile
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.data_import.receipt_api.offline_receipt import ReceiptOffline
from jal.data_import.receipt_api.pt_at_qr import AtQr
try:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError
except ImportError:
    pass  # PDF receipts can't be read without dependency

MONOSPACE_WIDTH = 0.6     # glyph width of a monospaced font, in units of its size


# ----------------------------------------------------------------------------------------------------------------------
# Text of a receipt PDF as lines, with each piece of text at the column its position gives (receipts are printed in
# a monospaced font). pypdf's own layout mode returns nothing for Lidl's PDFs, so the page is laid out here.
def layout_text(data: bytes) -> list:
    lines = []
    for page in PdfReader(io.BytesIO(data)).pages:
        fragments = []

        def visit(text, cm, tm, font, size):
            if font is None or not text.strip('\n'):   # pypdf repeats a form's whole text without a font
                return
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            scale = tm[0] * cm[0] + tm[1] * cm[2]
            fragments.append((x, y, text.replace('\n', ''), abs(size * (scale if scale else 1))))

        page.extract_text(visitor_text=visit)
        if not fragments:
            continue
        width = min(x[3] for x in fragments if x[3] > 0) * MONOSPACE_WIDTH
        left = min(x[0] for x in fragments)
        rows = {}
        for x, y, text, size in fragments:
            row = next((key for key in rows if abs(key - y) < size / 3), y)
            rows.setdefault(row, []).append((x, text))
        for y in sorted(rows, reverse=True):
            line = ''
            for x, text in sorted(rows[y]):
                start = round((x - left) / width) + len(text) - len(text.lstrip(' '))   # first visible character
                if start < len(line.rstrip()):          # text drawn over text goes on a line of its own
                    lines.append(line.rstrip())
                    line = ''
                line = line.rstrip().ljust(start) + text.lstrip(' ')
            lines.append(line.rstrip())
    return lines


# ----------------------------------------------------------------------------------------------------------------------
def _line_name(item: ReceiptItem) -> str:
    if item.qty is None or item.qty == 1:
        return item.name
    return f"{item.name} ({remove_exponent(item.qty)} x {item.price:.2f})"


# Reads a receipt PDF into the lines of the import dialog. With a shop profile whose items add up to the receipt's
# VAT table and total, every item is a line; otherwise the receipt is one line of its total, to be split by hand.
def pdf_receipt(data: bytes, at_qr: Optional[AtQr], captured_at: datetime) -> Optional[ReceiptOffline]:
    if not dependency_present(['pypdf']):
        logging.warning(ReceiptAPI.tr("Package pypdf not found for PDF parsing."))
        return None
    try:
        text = layout_text(data)
    except (PyPdfError, ValueError, KeyError, TypeError) as e:
        logging.warning(ReceiptAPI.tr("Receipt PDF can't be read") + f": {e}")
        return None
    header = parse_header(text)
    nif = at_qr.nif if at_qr is not None else header.get('nif', '')
    shop = f"NIF {nif}" if nif else ''
    sign = Decimal('1') if at_qr is not None and at_qr.is_return else Decimal('-1')
    total = at_qr.total if at_qr is not None else parse_total(text)
    lines, timestamp = [], None
    profile = shop_profile(nif) if nif else None
    if profile is not None:
        receipt = profile(text)     # type: ShopReceipt
        timestamp = receipt.timestamp
        problems = receipt.problems()
        if at_qr is not None and receipt.total is not None and receipt.total != at_qr.total:
            problems.append(f"total: receipt {receipt.total}, QR code {at_qr.total}")
        if problems:
            logging.warning(ReceiptAPI.tr("Receipt items don't add up, the receipt is loaded as one line")
                            + f" ({profile.name}): " + "; ".join(problems))
        else:
            lines = [{'name': _line_name(x), 'amount': sign * receipt.paid(x)} for x in receipt.items]
    if not lines:
        if total is None:
            logging.warning(ReceiptAPI.tr("Receipt PDF has no total that could be read"))
            return None
        lines = [{'name': shop, 'amount': sign * total}]
    if at_qr is not None and (timestamp is None or timestamp.date() != at_qr.date):
        timestamp = datetime(at_qr.date.year, at_qr.date.month, at_qr.date.day)
    if timestamp is None:
        logging.warning(ReceiptAPI.tr("Receipt PDF has no date that could be read, the capture time is used"))
        timestamp = captured_at.replace(tzinfo=None)
    date_time = QDateTime(QDate(timestamp.year, timestamp.month, timestamp.day),
                          QTime(timestamp.hour, timestamp.minute, timestamp.second), local_zone())
    if at_qr is not None:
        number = at_qr.number
    else:
        number = f"{nif}:{header['doc']}" if nif and 'doc' in header else ''
    return ReceiptOffline(shop, date_time, lines, number)
