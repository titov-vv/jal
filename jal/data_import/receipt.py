import os
import re
import logging
import importlib
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from jal.constants import Setup, PredefinedCategory
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


_SUBTOTAL = re.compile(r'^\s*SUB-?\s*TOTAL\b', re.I)


# A discount printed below a SUBTOTAL row is on the whole receipt, not on the item above it
def is_subtotal(line: str) -> bool:
    return bool(_SUBTOTAL.match(line))


# Returns what doesn't add up between the paid items of each VAT code {code: sum} and the VAT table {code: total}.
# A receipt-wide discount is shared by the codes: each code's items less its table total must be money off,
# and these shares must add up to the discount.
def vat_problems(paid: dict, table: dict, discount: Decimal) -> list:
    problems = []
    shares = {code: paid.get(code, Decimal('0')) - total for code, total in sorted(table.items())}
    if discount:
        if any(x < 0 for x in shares.values()) or sum(shares.values(), Decimal('0')) != discount:
            problems.append(f"VAT: items less table {', '.join(f'{c} {x}' for c, x in shares.items())}, "
                            f"receipt discount {discount}")
    else:
        problems += [f"VAT {code}: items {paid.get(code, Decimal('0'))}, table {table[code]}"
                     for code, share in shares.items() if share]
    codes = set(paid) - set(table)
    if codes:
        problems.append(f"items with VAT codes not in the table: {', '.join(sorted(codes))}")
    return problems


# Line of a receipt-wide discount, in the import dialog's sign ('sign' is the items' one)
def discount_line(label: str, amount: Decimal, sign: Decimal) -> dict:
    return {'name': label, 'amount': -sign * amount, 'category': PredefinedCategory.Discounts}


_VOUCHER_AMOUNT = r'\s+(?P<amount>\d+[,.]\d\d)\s*[€E]?\s*$'     # OCR joins with one space and reads '€' as 'E'


def _amount_in(text: str, amount: Decimal) -> bool:
    return bool(re.search(r'(?<![\d,.])' + str(int(amount)) + r'[,.]' + f"{amount % 1:.2f}"[2:] + r'(?!\d)', text))


# Payments by voucher after the receipt's body, as (label, amount) pairs, and what doesn't let them be trusted.
# What the voucher left to pay must be printed as another payment, which guards against a misread amount.
def parse_vouchers(lines: list, label: str, total: Optional[Decimal]) -> tuple:
    if not label:
        return [], []
    tail = lines[len(body_of(lines)):]
    pattern, start = re.compile(r'^\s*(?P<label>(?:' + label + r').*?)' + _VOUCHER_AMOUNT), re.compile(r'^\s*' + label)
    vouchers, problems = [], []
    for line in tail:
        if match := pattern.match(line):
            vouchers.append((match['label'].strip(), Decimal(match['amount'].replace(',', '.'))))
        elif start.match(line):
            problems.append(f"no amount in '{line.strip()}'")
    if vouchers and not problems:
        rest = None if total is None else total - sum(amount for _, amount in vouchers)
        if rest is None or rest < 0 or (rest and not any(_amount_in(x, rest) for x in tail)):
            problems.append(f"{', '.join(f'{x} {a}' for x, a in vouchers)} leaves {rest} of {total} to pay, "
                            f"which no payment line shows")
    return ([], problems) if problems else (vouchers, [])


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
    discounts_netted = True       # False where an item's discount is already in its price or is a loyalty credit
    # Line patterns, tried in this order: a line is taken by the first one that matches
    DepartmentPattern = ''        # (?P<dept>)
    DiscountPattern = ''          # (?P<label>) (?P<amount>)
    QuantityAmountPattern = ''    # completes a name-only item: (?P<qty>) (?P<price>) (?P<amount>) [(?P<vat>)]
    QuantityPattern = ''          # printed under its item: (?P<qty>) (?P<price>)
    ItemPattern = ''              # (?P<name>) [(?P<amount>) (?P<vat>) (?P<qty>) (?P<price>)]
    DatetimePattern = ''          # (?P<year>) (?P<month>) (?P<day>) (?P<hour>) (?P<minute>) [(?P<second>)]
    VoucherLabel = ''             # start of a payment line by voucher, which is outside the VAT table

    def __init__(self, lines: list):
        self.discounts = []       # (label, amount) pairs of the whole receipt, amount > 0 as money off
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

    # Money off the whole receipt, which its VAT table must share
    def receipt_discount(self) -> Decimal:
        return sum((amount for _, amount in self.discounts), Decimal('0'))

    # Returns what doesn't add up: every VAT bucket and the grand total must equal the sum of the paid items,
    # less the receipt-wide discount
    def problems(self) -> list:
        problems = []
        if not self.items:
            problems.append("no items found")
        if not self.vat_table:
            problems.append("no VAT table found")
        paid = {}
        for x in self.items:
            paid[x.vat] = paid.get(x.vat, Decimal('0')) + self.paid(x)
        table = {code: row['total'] for code, row in self.vat_table.items()}
        problems += vat_problems(paid, table, self.receipt_discount())
        parsed = sum(paid.values(), Decimal('0')) - self.receipt_discount()
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
        items, department, pending, subtotal = [], '', None, False
        indent = min((len(x) - len(x.lstrip(' ')) for x in lines if x.strip()), default=0)
        for line in (x[indent:] for x in lines):   # the page may start left of the body, at a card slip
            if not line.strip():
                continue
            if is_subtotal(line):
                pending, subtotal = None, True
                continue
            for name, pattern in rules:
                match = pattern.match(line)
                if not match:
                    continue
                values = match.groupdict()
                if name == 'department':
                    department, pending = values['dept'].strip(), None
                elif name == 'discount':
                    if subtotal:
                        self.discounts.append((values['label'].strip(), pt_decimal(values['amount'])))
                    elif pending is not None:
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
