import os
import json
import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from jal.data_import.receipt_api.pt_at_qr import AtQr


# ----------------------------------------------------------------------------------------------------------------------
# One barcode as the phone read it
@dataclass
class ReceiptCode:
    format: str
    raw: str
    page: int = 0


# One item or discount line of 'paper.items': as printed, the amount is always positive
@dataclass
class PaperItem:
    ITEM = "item"
    DISCOUNT = "discount"

    role: str
    text: str
    amount: Decimal
    sign_printed: str
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    unit: str = ''
    tax_code: str = ''
    department: str = ''


def _money(value) -> Optional[Decimal]:
    return None if value is None else Decimal(value)


# ----------------------------------------------------------------------------------------------------------------------
# A '.jalr' container written by the ReceiptScan app: a zip of 'receipt.json' plus page images or 'original.pdf'
class JalrFile:
    EXTENSION = ".jalr"
    SCHEMA = "jal.receipt"
    SCHEMA_MAJOR = "1"
    PAPER_SCAN = "paper_scan"
    IMAGE_IMPORT = "image_import"
    PDF_IMPORT = "pdf_import"
    PDF_NAME = "original.pdf"
    GREEN = "green"
    NO_VALUE = "no_value"
    NETTED = "netted"                    # values of 'validation.discount_hypothesis'
    INFORMATIONAL = "informational"
    NOT_APPLICABLE = "not_applicable"

    def __init__(self, path: str, data: dict):
        self._path = path
        self._data = data
        self._kind = data['source']['kind']
        self._captured_at = self._timestamp(data['captured_at'])
        self._codes = [ReceiptCode(x.get('format', ''), x['raw'], x.get('page', 0)) for x in data['codes']]
        self._paper_items, self._tax_table = self._read_paper(path, data.get('paper') or {})

    # A malformed 'paper' block is dropped rather than the file: the fiscal code alone still imports it
    @staticmethod
    def _read_paper(path: str, paper: dict) -> tuple:
        try:
            items = [PaperItem(role=x['role'], text=x['text'], amount=Decimal(x['amount']),
                               sign_printed=x['sign_printed'], quantity=_money(x.get('quantity')),
                               unit_price=_money(x.get('unit_price')), unit=x.get('unit') or '',
                               tax_code=x.get('tax_code') or '', department=x.get('department') or '')
                     for x in paper.get('items') or []]
            tax_table = [{'code': x['code'], 'rate': _money(x.get('rate')), 'base': _money(x.get('base')),
                          'tax': _money(x.get('tax')), 'total': _money(x.get('total'))}
                         for x in paper.get('tax_table') or []]
        except (ArithmeticError, AttributeError, KeyError, TypeError, ValueError) as e:
            logging.warning(f"Receipt file has malformed 'paper' block, it is ignored, {path}: {e!r}")
            return [], []
        return items, tax_table

    # Returns None for a file that isn't a finished container (half-uploaded, not a zip) or has an unknown format
    @classmethod
    def open(cls, path: str) -> Optional['JalrFile']:
        try:
            with zipfile.ZipFile(path) as container:
                data = json.loads(container.read("receipt.json"), parse_float=Decimal)
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
            logging.debug(f"Receipt file skipped, {path}: {e}")
            return None
        try:
            name, _, version = data['schema'].partition('/')
            if name != cls.SCHEMA or version.split('.')[0] != cls.SCHEMA_MAJOR:
                logging.warning(f"Receipt file has unsupported format '{data['schema']}': {path}")
                return None
            if data['source']['kind'] not in (cls.PAPER_SCAN, cls.IMAGE_IMPORT, cls.PDF_IMPORT):
                logging.warning(f"Receipt file has unknown source '{data['source']['kind']}': {path}")
                return None
            return cls(path, data)
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logging.warning(f"Receipt file is malformed, {path}: {e!r}")
            return None

    # RFC 3339; datetime.fromisoformat() before Python 3.11 doesn't take 'Z', which the phone writes for UTC+0
    @staticmethod
    def _timestamp(text: str) -> datetime:
        if text.endswith('Z'):
            text = text[:-1] + "+00:00"
        timestamp = datetime.fromisoformat(text)
        if timestamp.tzinfo is None:
            raise ValueError(f"'captured_at' has no time zone: {text}")
        return timestamp

    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str:
        return os.path.basename(self._path)

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def captured_at(self) -> datetime:
        return self._captured_at

    @property
    def codes(self) -> list:
        return self._codes

    @property
    def pages(self) -> int:
        return self._data['source'].get('pages', 0)

    @property
    def image_names(self) -> list:
        return [x['file'] for x in self._data['source'].get('images', [])]

    @property
    def paper_items(self) -> list:
        return self._paper_items

    @property
    def tax_table(self) -> list:
        return self._tax_table

    @property
    def validation_status(self) -> str:
        return (self._data.get('validation') or {}).get('status') or ''

    @property
    def discount_hypothesis(self) -> str:
        return (self._data.get('validation') or {}).get('discount_hypothesis') or ''

    def pdf_bytes(self) -> bytes:
        with zipfile.ZipFile(self._path) as container:
            return container.read(self.PDF_NAME)


# ----------------------------------------------------------------------------------------------------------------------
# Returns the finished receipt files of the inbox folder, oldest first (names start with the capture time)
def scan_inbox(folder: str) -> list:
    if not folder or not os.path.isdir(folder):
        return []
    names = sorted(x for x in os.listdir(folder) if x.endswith(JalrFile.EXTENSION))
    files = [JalrFile.open(os.path.join(folder, x)) for x in names if os.path.isfile(os.path.join(folder, x))]
    return [x for x in files if x is not None]


# Moves a processed file into 'done/' beside it and returns the new path
def move_done(path: str) -> str:
    done = os.path.join(os.path.dirname(path), "done")
    os.makedirs(done, exist_ok=True)
    target = os.path.join(done, os.path.basename(path))
    if os.path.exists(target):
        raise FileExistsError(f"Receipt file is already in 'done': {target}")
    os.replace(path, target)
    return target


# ----------------------------------------------------------------------------------------------------------------------
# Russian FNS receipt QR: 't=20240101T1200&s=100.00&fn=...&i=...&fp=...&n=1'
def is_fns_qr(raw: str) -> bool:
    return all(x in raw for x in ["i=", "n=", "s=", "t=", "fn=", "fp="])


@dataclass
class Route:
    FNS = "fns"                  # Russian QR: the receipt is downloaded from FNS
    PDF = "pdf"                  # the document itself is parsed by a shop profile
    PT_QR = "pt_qr"              # only the Portuguese QR is readable: date, shop and total
    PT_ITEMS = "pt_items"        # Portuguese QR plus the items the phone proved against its total
    UNSUPPORTED = "unsupported"
    NO_CODE = "no_code"                   # reasons for UNSUPPORTED
    UNKNOWN_CODE = "unknown_code"
    DOCUMENT_TYPE = "document_type"
    DOCUMENT_STATUS = "document_status"
    NO_VALUE = "no_value"

    kind: str
    reason: str = ''
    code: str = ''                       # raw FNS code
    at_qr: Optional[AtQr] = None


# Decides how a receipt file may be imported
def route(receipt: JalrFile) -> Route:
    for code in receipt.codes:
        if is_fns_qr(code.raw):
            return Route(Route.FNS, code=code.raw)
    at_qr = next((x for x in (AtQr.parse(c.raw) for c in receipt.codes) if x is not None), None)
    if receipt.kind == JalrFile.PDF_IMPORT:
        return Route(Route.PDF, at_qr=at_qr)
    if at_qr is None:
        return Route(Route.UNSUPPORTED, reason=Route.UNKNOWN_CODE if receipt.codes else Route.NO_CODE)
    if at_qr.total == 0:     # decided by the QR itself, so files older than the phone's 'no_value' status agree
        return Route(Route.UNSUPPORTED, reason=Route.NO_VALUE, at_qr=at_qr)
    if receipt.validation_status == JalrFile.NO_VALUE:
        logging.warning(f"Receipt file is marked 'no_value' but its QR total is {at_qr.total}: {receipt.path}")
    if at_qr.doc_type not in AtQr.PURCHASES + AtQr.RETURNS:
        return Route(Route.UNSUPPORTED, reason=Route.DOCUMENT_TYPE, at_qr=at_qr)
    if at_qr.status != AtQr.NORMAL:
        return Route(Route.UNSUPPORTED, reason=Route.DOCUMENT_STATUS, at_qr=at_qr)
    if receipt.kind == JalrFile.PAPER_SCAN and receipt.validation_status == JalrFile.GREEN \
            and any(x.role == PaperItem.ITEM for x in receipt.paper_items):
        return Route(Route.PT_ITEMS, at_qr=at_qr)
    return Route(Route.PT_QR, at_qr=at_qr)
