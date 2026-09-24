import os
import re
import logging
import importlib
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from jal.constants import Setup
from jal.db.settings import JalSettings
from jal.db.helpers import remove_exponent

AMOUNT = r'[\d.]*\d,\d\d'     # Portuguese amount as printed: '1.234,56'


def pt_decimal(text: str) -> Decimal:
    return Decimal(text.replace('.', '').replace(',', '.'))


# ----------------------------------------------------------------------------------------------------------------------
# The VAT summary table, whose column order differs per shop: roles are read from the table's own header
VAT_COLUMNS = {
    'base': ['base imp', 'valor s/iva', 'total liq', 'liquido', 'líquido'],
    'vat': ['val.iva', 'valor iva', 'iva'],
    'total': ['val.total', 'valor c/iva', 'total'],
}
_VAT_HEADER = re.compile(r'(taxa|%iva|cod\.)', re.I)
_VAT_ROW = re.compile(r'^\s*\(?(?P<code>[A-Z0-9])\)?\s+(?P<rate>\d+(?:,\d+)?)\s*%(?:\s*de)?\s+(?P<values>(?:\s*' + AMOUNT
                      + r')+)\s*$')


# Returns {VAT code: {'rate': int, 'total': Decimal}}, 'total' being the amount with VAT
def parse_vat_table(lines: list) -> dict:
    roles, table = None, {}
    for line in lines:
        if _VAT_HEADER.search(line) and not _VAT_ROW.match(line):
            text = line.lower()
            found = []
            for role, words in VAT_COLUMNS.items():
                for word in words:
                    if word in text:
                        found.append((text.index(word), role))
                        break
            roles = [role for _, role in sorted(found)]
            continue
        match = _VAT_ROW.match(line)
        if match and roles:
            columns = dict(zip(roles, [pt_decimal(x) for x in re.findall(AMOUNT, match['values'])]))
            total = columns.get('total')
            if total is None:                     # a table without the with-VAT column
                total = columns.get('base', Decimal('0')) + columns.get('vat', Decimal('0'))
            table[match['code']] = {'rate': int(match['rate'].split(',')[0]), 'total': total}
    return table


_TOTALS = [(re.compile(r'^\s*TOTAL A PAGAR\s+(' + AMOUNT + r')\s*$', re.I), 10),
           (re.compile(r'^\s*Total\s{2,}(' + AMOUNT + r')\s*$', re.I), 1)]


def parse_total(lines: list) -> Optional[Decimal]:
    best, priority = None, -1
    for line in lines:
        for pattern, rank in _TOTALS:
            match = pattern.match(line)
            if match and rank > priority:
                best, priority = pt_decimal(match.group(1)), rank
    return best


_NIF = re.compile(r'NIF:?\s*(?:PT)?(\d{9})|NIPC:\s*(\d{9})|^\s*(\d{9})\s*$', re.I)
_ATCUD = re.compile(r'ATCUD:?\s*(\S+)')
_DOCUMENT = re.compile(r'\b(F[SAR]S?)\s+(\S+)')


# Returns {'nif', 'atcud', 'doc'} as far as they are found; 'doc' is printed the way the QR's field G holds it
def parse_header(lines: list) -> dict:
    header = {}
    for line in lines:
        if 'nif' not in header and (match := _NIF.search(line)):
            header['nif'] = next(x for x in match.groups() if x)
        if match := _ATCUD.search(line):
            header['atcud'] = match.group(1)
        if 'doc' not in header and (match := _DOCUMENT.search(line)):
            header['doc'] = f"{match.group(1)} {match.group(2)}"
    return header


_CARD = re.compile(r'CART[AÃ][O0]\s*:?\s*[*#Xx]{2,}\s*([0-9lIOo]{4})(?![0-9A-Za-z])', re.I)
_CARD_DIGITS = str.maketrans('lIOo', '1100')     # OCR reads '1' and '0' as letters


# Last 4 digits of the payment card as 'CARTAO: ****1234' prints them; None if absent or several cards disagree
def parse_card(lines: list) -> Optional[str]:
    cards = {match.group(1).translate(_CARD_DIGITS) for line in lines for match in _CARD.finditer(line)}
    return cards.pop() if len(cards) == 1 else None


_BODY_END = re.compile(r'^\s*(Resumo|TOTAL|Total)\b')


# Item lines end where the summary starts
def body_of(lines: list) -> list:
    for i, line in enumerate(lines):
        if _BODY_END.match(line):
            return lines[:i]
    return lines


# ----------------------------------------------------------------------------------------------------------------------
@dataclass
class ReceiptItem:
    name: str
    amount: Optional[Decimal] = None      # as printed on the item line, before any discount
    vat: str = ''                         # VAT code of the receipt's own legend
    qty: Optional[Decimal] = None
    price: Optional[Decimal] = None
    department: str = ''
    discounts: list = field(default_factory=list)   # (label, amount) pairs, amount > 0 as money off


# Name of the item's line in the import dialog
def line_name(item: ReceiptItem) -> str:
    if item.qty is None or item.qty == 1 or item.price is None:
        return item.name
    return f"{item.name} ({remove_exponent(item.qty)} x {item.price:.2f})"


# ----------------------------------------------------------------------------------------------------------------------
# A Portuguese shop receipt read from its text. A shop profile subclasses it and declares its line grammar;
# the VAT table, the total and the reconciliation are the same for every shop.
class ShopReceipt:
    NIF = ''                      # issuer's tax number, the key a profile is found by
    name = ''
    discounts_netted = True       # False where a printed discount is a loyalty credit, not money off
    # Line patterns, tried in this order: a line is taken by the first one that matches
    DepartmentPattern = ''        # (?P<dept>)
    DiscountPattern = ''          # (?P<label>) (?P<amount>)
    QuantityAmountPattern = ''    # completes a name-only item: (?P<qty>) (?P<price>) (?P<amount>) [(?P<vat>)]
    QuantityPattern = ''          # printed under its item: (?P<qty>) (?P<price>)
    ItemPattern = ''              # (?P<name>) [(?P<amount>) (?P<vat>) (?P<qty>) (?P<price>)]
    DatetimePattern = ''          # (?P<year>) (?P<month>) (?P<day>) (?P<hour>) (?P<minute>) [(?P<second>)]

    def __init__(self, lines: list):
        self.header = parse_header(lines)
        self.vat_table = parse_vat_table(lines)
        self.total = parse_total(lines)
        self.timestamp = self._parse_datetime(lines)
        self.items = self._parse_body(body_of(lines))

    # Amount the item was paid with
    def paid(self, item: ReceiptItem) -> Decimal:
        if not self.discounts_netted:
            return item.amount
        return item.amount - sum(amount for _, amount in item.discounts)

    # Returns what doesn't add up: every VAT bucket and the grand total must equal the sum of the paid items
    def problems(self) -> list:
        problems = []
        if not self.items:
            problems.append("no items found")
        if not self.vat_table:
            problems.append("no VAT table found")
        for code, row in sorted(self.vat_table.items()):
            parsed = sum((self.paid(x) for x in self.items if x.vat == code), Decimal('0'))
            if parsed != row['total']:
                problems.append(f"VAT {code}: items {parsed}, table {row['total']}")
        codes = set(x.vat for x in self.items) - set(self.vat_table)
        if codes:
            problems.append(f"items with VAT codes not in the table: {', '.join(sorted(codes))}")
        parsed = sum((self.paid(x) for x in self.items), Decimal('0'))
        if self.total is None or parsed != self.total:
            problems.append(f"total: items {parsed}, receipt {self.total}")
        return problems

    def _parse_datetime(self, lines: list) -> Optional[datetime]:
        if not self.DatetimePattern:
            return None
        pattern = re.compile(self.DatetimePattern)
        for line in lines:
            if match := pattern.match(line):
                year = int(match['year'])
                year = year + 2000 if year < 100 else year
                second = int(match.groupdict().get('second') or 0)
                try:
                    return datetime(year, int(match['month']), int(match['day']), int(match['hour']),
                                    int(match['minute']), second)
                except ValueError:
                    return None
        return None

    def _parse_body(self, lines: list) -> list:
        rules = [(name, re.compile(pattern)) for name, pattern in (
            ('department', self.DepartmentPattern), ('discount', self.DiscountPattern),
            ('quantity_amount', self.QuantityAmountPattern), ('quantity', self.QuantityPattern),
            ('item', self.ItemPattern)) if pattern]
        items, department, pending = [], '', None
        for line in lines:
            if not line.strip():
                continue
            for name, pattern in rules:
                match = pattern.match(line)
                if not match:
                    continue
                values = match.groupdict()
                if name == 'department':
                    department, pending = values['dept'].strip(), None
                elif name == 'discount':
                    if pending is not None:
                        pending.discounts.append((values['label'].strip(), pt_decimal(values['amount'])))
                elif name == 'quantity_amount':
                    if pending is not None and pending.amount is None:
                        pending.qty, pending.price = pt_decimal(values['qty']), pt_decimal(values['price'])
                        pending.amount = pt_decimal(values['amount'])
                        pending.vat = values.get('vat') or pending.vat
                elif name == 'quantity':
                    if pending is not None:
                        pending.qty, pending.price = pt_decimal(values['qty']), pt_decimal(values['price'])
                elif name == 'item':
                    item = ReceiptItem(name=values['name'].strip(), department=department,
                                       amount=pt_decimal(values['amount']) if values.get('amount') else None,
                                       vat=values.get('vat') or '',
                                       qty=pt_decimal(values['qty']) if values.get('qty') else None,
                                       price=pt_decimal(values['price']) if values.get('price') else None)
                    if item.name:
                        items.append(item)
                        pending = item
                break
        return [x for x in items if x.amount is not None]


# ----------------------------------------------------------------------------------------------------------------------
# Shop profiles found in 'shop_receipts', by the NIF of the shop
_profiles = None


def shop_profile(nif: str) -> Optional[type]:
    global _profiles
    if _profiles is None:
        _profiles = _load_profiles()
    return _profiles.get(nif)


def _load_profiles() -> dict:
    profiles = {}
    folder = JalSettings.path(JalSettings.PATH_APP) + Setup.IMPORT_PATH + os.sep + Setup.RECEIPT_PATH
    for module_name in sorted(x[:-3] for x in os.listdir(folder) if x.endswith(".py")):
        try:
            module = importlib.import_module(f"jal.data_import.{Setup.RECEIPT_PATH}.{module_name}")
        except ImportError:
            logging.error(f"Receipt profile module can't be imported: {module_name}")
            continue
        class_name = getattr(module, "JAL_RECEIPT_CLASS", None)
        if class_name is None:
            continue
        profile = getattr(module, class_name, None)
        if profile is None:
            logging.error(f"Receipt profile class can't be loaded: {class_name}")
            continue
        profiles[profile.NIF] = profile
    return profiles
