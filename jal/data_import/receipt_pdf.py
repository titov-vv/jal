import io
import re
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
from PySide6.QtCore import QDateTime, QDate, QTime
from jal.db.clock import local_zone
from jal.widgets.helpers import dependency_present
from jal.data_import.receipt import ReceiptItem, LineTrust, Verdict, parse_header, parse_total, shop_profile, \
    line_name, discount_line
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.data_import.receipt_api.offline_receipt import ReceiptOffline, voucher_lines, with_vat
from jal.data_import.receipt_api.pt_at_qr import AtQr
try:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError
except ImportError:
    pass  # PDF receipts can't be read without dependency

MONOSPACE_WIDTH = 0.6     # glyph width of a monospaced font, in units of its size
NUMERIC_DATE_AGE = 7       # days before the capture that a date of digits only may be, which tells its day from its month


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
        width = min(x[3] for x in fragments if x[3] > 0 and x[2].strip('\xa0')) * MONOSPACE_WIDTH   # a spacer may be tiny
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
_CELL = re.compile(r'\S+(?: \S+)*')     # a piece of a line with no wider gap than one space
_CURRENCIES = {'€': 'EUR', '£': 'GBP'}     # '$' is the sign of several currencies
_MONEY = re.compile(r'^(?P<minus>-)?\s*(?P<lead>[€$£]|[A-Z]{3})?\s*(?P<whole>\d[\d., ]*?)[.,](?P<cents>\d\d)\s*'
                    r'(?P<trail>[€$£]|[A-Z]{3})?$')
_MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


# Returns (amount, currency code) of an amount printed in either decimal convention, None if the text isn't one;
# the currency is '' where it isn't printed or isn't certain
def money(text: str) -> Optional[tuple]:
    match = _MONEY.match(text.strip())
    if not match:
        return None
    amount = Decimal(re.sub(r'\D', '', match['whole']) + '.' + match['cents'])
    symbol = match['lead'] or match['trail'] or ''
    return -amount if match['minus'] else amount, _CURRENCIES.get(symbol, symbol if len(symbol) == 3 else '')


# Date of a document captured on the day 'captured'. A date of digits only is read as day/month, then as month/day:
# the reading that is at most NUMERIC_DATE_AGE days old is taken, none if neither is.
def parse_date(text: str, captured: date) -> Optional[datetime]:
    text, recent = text.strip(), False
    if match := re.fullmatch(r'(\d{4})-(\d\d)-(\d\d)', text):
        readings = [(match[1], match[2], match[3])]
    elif match := re.fullmatch(r'([A-Za-z]{3,9})\.? (\d{1,2}),? (\d{4})', text):
        readings = [(match[3], match[1], match[2])]
    elif match := re.fullmatch(r'(\d{1,2}) ([A-Za-z]{3,9})\.?,? (\d{4})', text):
        readings = [(match[3], match[2], match[1])]
    elif match := re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})', text):
        year = match[3] if len(match[3]) == 4 else '20' + match[3]
        readings, recent = [(year, match[2], match[1]), (year, match[1], match[2])], True
    else:
        return None
    for year, month, day in readings:
        if not month.isdigit():
            month = _MONTHS.index(month[:3].lower()) + 1 if month[:3].lower() in _MONTHS else 0
        try:
            moment = datetime(int(year), int(month), int(day))
        except ValueError:
            continue
        age = (captured - moment.date()).days     # a seller's day may be one ahead of the local one
        if not recent or -1 <= age <= NUMERIC_DATE_AGE:
            return moment
    return None


# ----------------------------------------------------------------------------------------------------------------------
# An invoice of a seller that has no shop profile, read by the labels invoices commonly print: a table of items under
# a 'Description ... Amount' heading, then the subtotal, the tax and the total. It has the surface of ShopReceipt.
class GenericReceipt:
    name = "generic"
    COLUMNS = {'name': ['description', 'item'], 'qty': ['qty', 'quantity'], 'price': ['unit price', 'price'],
               'vat': ['tax', 'vat'], 'amount': ['amount', 'total']}
    NUMBERS = ['invoice number', 'receipt number']
    DATES = ['date paid', 'date of issue', 'invoice date', 'receipt date', 'date']
    _BODY_END = re.compile(r'^\s*(sub-?\s?total|total)\b', re.I)
    _SELLER = re.compile(r'^(vat|tax) ', re.I)
    _TAX_ID = re.compile(r'\b[A-Z]{2}\d[0-9A-Z]{7,11}\b')
    _TAX = re.compile(r'\b(vat|tax|gst|iva)\b.*?(?P<rate>\d+(?:[.,]\d+)?)\s*%(?:\s*on\s+(?P<base>[^\d\s]*\s?[\d.,]*\d))?',
                      re.I)

    def __init__(self, lines: list, captured: date):
        lines = [x.replace('\x00', '-') for x in lines]     # a dash of a font that doesn't tell its characters
        self.discounts = []
        self.currency = ''
        start, self.items, end = self._parse_items(lines)
        fields = {}
        for line in lines[:start]:
            cells = _CELL.findall(line)
            if len(cells) >= 2:
                fields.setdefault(cells[0].lower(), cells[1:])
        self.timestamp = next((x for x in (parse_date(fields[label][0], captured) for label in self.DATES
                                           if label in fields) if x is not None), None)
        seller = next((match[0] for label, value in fields.items()
                       if self._SELLER.match(label) and (match := self._TAX_ID.search(' '.join(value)))), '')
        self.shop = f"VAT {seller}" if seller else ''
        number = next((fields[label][0] for label in self.NUMBERS if label in fields), '')
        self.number = f"{seller}:{number}" if seller and number else ''
        self._subtotal, self.total, self._amount_paid, self._taxes = self._parse_summary(lines[end:])
        self._paid, self._problems = self._reconcile()

    # Returns the index of the table's heading (the number of lines if there is none), its items and the index
    # of the line the summary starts at
    def _parse_items(self, lines: list) -> tuple:
        columns, items, start = None, [], len(lines)
        for i, line in enumerate(lines):
            cells = [(x.start(), x[0]) for x in _CELL.finditer(line)]
            if columns is None:
                found = {role: at for at, text in cells for role, names in self.COLUMNS.items() if text.lower() in names}
                if cells and cells[0][1].lower() in self.COLUMNS['name'] and 'amount' in found:
                    columns, start = found, i
                continue
            if self._BODY_END.match(line):
                return start, items, i
            values = {min(columns, key=lambda role: abs(columns[role] - at)): text for at, text in cells}
            amount = money(values.get('amount', ''))
            if 'name' in values and amount is not None:
                price, qty = money(values.get('price', '')), values.get('qty', '').replace(',', '.')
                items.append(ReceiptItem(name=values['name'], amount=amount[0], vat=values.get('vat', ''),
                                         qty=Decimal(qty) if re.fullmatch(r'\d+(\.\d+)?', qty) else None,
                                         price=price[0] if price is not None else None))
            elif list(values) == ['name'] and items:     # the name goes on in a line of its own
                items[-1].name += ' ' + values['name']
        return start, items, len(lines) if columns is not None else 0

    # Returns the subtotal, the total, the amount paid (None where not printed) and the tax rows as
    # {'code', 'rate', 'base', 'tax'}, 'code' being the rate as an item's tax column prints it
    def _parse_summary(self, lines: list) -> tuple:
        amounts, taxes = {}, []
        for line in lines:
            cells = _CELL.findall(line)
            value = money(cells[1]) if len(cells) == 2 else None
            if value is None:
                continue
            label = cells[0].lower()
            if re.fullmatch(r'sub-?\s?total', label):
                amounts.setdefault('subtotal', value[0])
            elif label == 'total':
                if 'total' not in amounts:
                    amounts['total'], self.currency = value
            elif label == 'amount paid':
                amounts.setdefault('paid', value[0])
            elif not label.startswith('total') and (match := self._TAX.search(cells[0])):
                base = money(match['base']) if match['base'] else None
                taxes.append({'code': match['rate'] + '%', 'rate': Decimal(match['rate'].replace(',', '.')),
                              'base': base[0] if base is not None else None, 'tax': value[0]})
        if len(taxes) == 1 and taxes[0]['base'] is None:
            taxes[0]['base'] = amounts.get('subtotal')
        return amounts.get('subtotal'), amounts.get('total'), amounts.get('paid'), taxes

    # Returns what every item was paid with and what doesn't add up. Items that add up to the total less its tax
    # are priced net of it and get it added.
    def _reconcile(self) -> tuple:
        paid, problems = [(x, x.amount) for x in self.items], []
        if not self.items:
            problems.append("no items found")
        items = sum((x.amount for x in self.items), Decimal('0'))
        tax = sum((x['tax'] for x in self._taxes), Decimal('0'))
        if self._subtotal is not None and items != self._subtotal:
            problems.append(f"subtotal: items {items}, receipt {self._subtotal}")
        if self._amount_paid is not None and self._amount_paid != self.total:
            problems.append(f"paid {self._amount_paid} of the total {self.total}")
        if tax and self.total is not None and items + tax == self.total:
            if len(self._taxes) == 1:
                for x in self.items:
                    x.vat = x.vat or self._taxes[0]['code']
            paid = with_vat(paid, self._taxes, problems)
        if self.total is None or sum((amount for _, amount in paid), Decimal('0')) != self.total:
            problems.append(f"total: items {items}, tax {tax}, receipt {self.total}")
        return [amount for _, amount in paid], problems

    # Amount the item was paid with, its tax included
    def paid(self, item: ReceiptItem) -> Decimal:
        return next(amount for x, amount in zip(self.items, self._paid) if x is item)

    def problems(self) -> list:
        return list(self._problems)


# ----------------------------------------------------------------------------------------------------------------------
# A till receipt of a seller that has no shop profile: every line above the total that ends in an amount is an item,
# named by the rest of the line or, where that is codes only, by the line above. It has the surface of ShopReceipt.
class GenericTill:
    name = "generic till"
    _BODY_END = re.compile(r'^\s*(sub-?\s*total|total)\b', re.I)
    _TOTAL = re.compile(r'total(?: a pagar)?(?: ?\((?P<currency>[A-Z]{3})\))?', re.I)
    _VAT_CODE = re.compile(r'(?<=\d)\s+\(?[A-Z0-9]\)?\s*$')     # a letter or a digit, may be printed after the amount
    _WORD = re.compile(r'[^\W\d_]{3}')

    def __init__(self, lines: list):
        self.discounts = []
        self.currency = self.shop = self.number = ''
        self.timestamp = None
        end = next((i for i, x in enumerate(lines) if self._BODY_END.match(x)), 0)
        self.items = self._parse_items(lines[:end])
        self.total = self._parse_total(lines[end:])

    def _parse_items(self, lines: list) -> list:
        items, above = [], ''
        for line in lines:
            cells = _CELL.findall(self._VAT_CODE.sub('', line))
            amount = money(cells[-1]) if cells else None
            if amount is None:
                if self._WORD.search(line):
                    above = line.strip()
                continue
            name = ' '.join(cells[:-1])
            if not self._WORD.search(name):
                name, above = above, ''
            if name:
                items.append(ReceiptItem(name=name, amount=amount[0]))
        return items

    def _parse_total(self, lines: list) -> Optional[Decimal]:
        for line in lines:
            cells = _CELL.findall(line)
            value = money(cells[-1]) if len(cells) > 1 else None
            if value is not None and (match := self._TOTAL.fullmatch(' '.join(cells[:-1]))):
                self.currency = (match['currency'] or value[1]).upper()
                return value[0]
        return None

    # Amount the item was paid with
    def paid(self, item: ReceiptItem) -> Decimal:
        return item.amount

    def problems(self) -> list:
        problems = [] if self.items else ["no items found"]
        items = sum((x.amount for x in self.items), Decimal('0'))
        if items != self.total:
            problems.append(f"total: items {items}, receipt {self.total}")
        return problems


# A receipt without a shop profile is an invoice where the table of one is found, otherwise a till receipt
def generic_receipt(lines: list, captured: date):
    invoice = GenericReceipt(lines, captured)
    if invoice.items:
        return invoice
    till = GenericTill(lines)
    return till if till.items else invoice


# ----------------------------------------------------------------------------------------------------------------------
# Reads a receipt PDF into the lines of the import dialog. Every item that its shop profile finds, or a generic
# reader without one, is a line, proven where they add up to the receipt's own totals; otherwise the receipt is
# one line of its total.
# A payment by voucher is a discount line in either case.
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
    sign = Decimal('1') if at_qr is not None and at_qr.is_return else Decimal('-1')
    profile = shop_profile(nif) if nif else None
    receipt = profile(text) if profile is not None else generic_receipt(text, captured_at.date())
    generic = receipt if profile is None else None
    shop = f"NIF {nif}" if nif else generic.shop
    total = at_qr.total if at_qr is not None else parse_total(text)
    if total is None:
        total = receipt.total
    lines, timestamp, verdict = [], receipt.timestamp, Verdict.NOT_RECONCILED
    if profile is not None or receipt.items:
        problems = receipt.problems()
        if at_qr is not None and receipt.total is not None and receipt.total != at_qr.total:
            problems.append(f"total: receipt {receipt.total}, QR code {at_qr.total}")
        if problems:
            logging.warning(ReceiptAPI.tr("Receipt items don't add up, check the lines")
                            + f" ({receipt.name}): " + "; ".join(problems))
        else:
            verdict = Verdict.RECONCILED
        trust = LineTrust.READ if problems else LineTrust.PROVEN
        lines = [{'name': line_name(x), 'amount': sign * receipt.paid(x)} for x in receipt.items]
        lines += [discount_line(label, amount, sign) for label, amount in receipt.discounts]
        lines = [dict(x, trust=trust) for x in lines]
    if not lines:
        if total is None:
            logging.warning(ReceiptAPI.tr("Receipt PDF has no total that could be read"))
            return None
        lines = [{'name': shop, 'amount': sign * total}]
    vouchers = voucher_lines(text, nif, total, sign)     # the account paid that much less
    lines += vouchers
    expected = None if total is None else sign * total + sum(x['amount'] for x in vouchers)
    if at_qr is not None and (timestamp is None or timestamp.date() != at_qr.date):
        timestamp = datetime(at_qr.date.year, at_qr.date.month, at_qr.date.day)
    if timestamp is None:
        logging.warning(ReceiptAPI.tr("Receipt PDF has no date that could be read, the capture time is used"))
        timestamp = captured_at.replace(tzinfo=None)
    date_time = QDateTime(QDate(timestamp.year, timestamp.month, timestamp.day),
                          QTime(timestamp.hour, timestamp.minute, timestamp.second), local_zone())
    if at_qr is not None:
        number = at_qr.number
    elif nif and 'doc' in header:
        number = f"{nif}:{header['doc']}"
    else:
        number = generic.number if generic is not None else ''
    return ReceiptOffline(shop, date_time, lines, number, expected, verdict, generic.currency if generic else '')
