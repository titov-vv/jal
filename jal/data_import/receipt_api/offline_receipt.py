import re
import logging
from datetime import datetime, time
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Optional
from PySide6.QtCore import QDateTime, QDate, QTime
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.receipt_inbox import JalrFile, PaperItem
from jal.data_import.receipt import ReceiptItem, LineTrust, Verdict, shop_profile, line_name, vat_problems, \
    discount_line, parse_vouchers
from jal.db.clock import local_zone

OCR_CONFIDENCE_THRESHOLD = Decimal('0.5')     # provisional: the phone's own 'ocr_confidence' bar
CENT = Decimal('0.01')


# What items priced net of VAT may differ from their signed base by: half a cent of VAT rounding an item, as the
# phone allows (Reconcile.tolerance of the ReceiptScan app)
def net_rounding(items: int) -> Decimal:
    return (Decimal('0.005') * items).quantize(CENT, rounding=ROUND_CEILING)


#-----------------------------------------------------------------------------------------------------------------------
# A receipt that is already at hand (read from a file of the phone inbox): nothing to log in to or to download
class ReceiptOffline(ReceiptAPI):
    def __init__(self, shop_name: str, date_time: QDateTime, lines: list, number: str = '',
                 total: Optional[Decimal] = None, verdict: str = '', currency: str = ''):
        super().__init__()
        self._shop_name = shop_name
        self._date_time = date_time
        self._lines = lines
        self._number = number
        self._total = total
        self._verdict = verdict
        self._currency = currency

    # A receipt of the Portuguese fiscal QR, for the day it gives: the 'lines' given or one line of its total,
    # then the vouchers its 'text' shows as paid
    @classmethod
    def from_at_qr(cls, at_qr: AtQr, captured_at: datetime, lines: Optional[list] = None,
                   text: Optional[list] = None, verdict: str = Verdict.NOT_RECONCILED) -> 'ReceiptOffline':
        shop = f"NIF {at_qr.nif}"
        amount = at_qr.total if at_qr.is_return else -at_qr.total
        day = at_qr.date
        moment = captured_at.time() if captured_at.date() == day else time(0, 0)   # a scan made later has no time
        date_time = QDateTime(QDate(day.year, day.month, day.day),
                              QTime(moment.hour, moment.minute, moment.second), local_zone())
        vouchers = voucher_lines(text or [], at_qr.nif, at_qr.total, Decimal('1') if at_qr.is_return else Decimal('-1'))
        lines = (lines or [{'name': shop, 'amount': amount}]) + vouchers
        return cls(shop, date_time, lines, at_qr.number, amount + sum(x['amount'] for x in vouchers), verdict)

    # A scan without a fiscal code: only what the phone read, at the time of the scan; nothing to check the lines
    # against and no document number to tell a second import by
    @classmethod
    def unverified(cls, receipt: JalrFile, lines: list) -> 'ReceiptOffline':
        moment = receipt.captured_at
        date_time = QDateTime(QDate(moment.year, moment.month, moment.day),
                              QTime(moment.hour, moment.minute, moment.second), local_zone())
        return cls(receipt.shop_name, date_time, lines, verdict=Verdict.NO_CODE)

    def activate_session(self) -> bool:
        return True

    def query_slip(self):
        self.slip_load_ok.emit()

    def slip_lines(self) -> list:
        return [dict(x) for x in self._lines]

    def shop_name(self) -> str:
        return self._shop_name

    def datetime(self) -> QDateTime:
        return QDateTime(self._date_time)

    def number(self) -> str:
        return self._number

    def total(self) -> Optional[Decimal]:
        return self._total

    def verdict(self) -> str:
        return self._verdict

    def currency(self) -> str:
        return self._currency


# ----------------------------------------------------------------------------------------------------------------------
# Discount lines of the payments by voucher that the shop profile of 'nif' finds in the receipt's text;
# a voucher that can't be trusted is left out, to be added by hand
def voucher_lines(text: list, nif: str, total: Optional[Decimal], sign: Decimal) -> list:
    profile = shop_profile(nif) if nif else None
    if profile is None:
        return []
    vouchers, problems = parse_vouchers(text, profile.VoucherLabel, total)
    if problems:
        logging.warning(ReceiptAPI.tr("Receipt voucher can't be read, add it by hand") + f" ({profile.name}): "
                        + "; ".join(problems))
    return [discount_line(label, amount, sign) for label, amount in vouchers]


# ----------------------------------------------------------------------------------------------------------------------
# Returns (lines, proven) of the items the phone read off a paper receipt; 'at_qr' is None without a fiscal code.
# A file whose every line says what it did ('effect') is proven where that adds up to the QR's total; any other is
# loaded as read, for the user to check.
def paper_lines(receipt: JalrFile, at_qr: Optional[AtQr]) -> tuple:
    sign = Decimal('1') if at_qr is not None and at_qr.is_return else Decimal('-1')
    if at_qr is not None and receipt.paper_items and all(x.effect for x in receipt.paper_items):
        lines, problems = proven_lines(receipt, at_qr, sign)
        if not problems:
            return lines, True
        logging.warning(ReceiptAPI.tr("Receipt items don't add up, check the lines")
                        + f" ({receipt.name}): " + "; ".join(problems))
    reliable = at_qr is not None and receipt.validation_status != JalrFile.RED
    items = read_items(receipt.paper_items, at_qr.nif if at_qr is not None else '')
    lines = lines_as_read(items, sign, reliable)
    if reliable:
        lines = vat_added(lines, items, receipt.tax_table, at_qr, sign)
    return lines, False


# Lines by the phone's 'effect' and what doesn't add up in them. Items that give the QR's base rather than its total
# are priced net of VAT and get it added.
def proven_lines(receipt: JalrFile, at_qr: AtQr, sign: Decimal) -> tuple:
    paid, discounts, problems = by_effect(receipt.paper_items)
    discount = sum((a for _, a, _ in discounts), Decimal('0'))
    if discount and receipt.tax_table:
        if any(x['total'] is None for x in receipt.tax_table):
            problems.append("VAT table without totals")
        else:
            by_code = {}
            for x, amount in paid:
                row = vat_row(x.vat, receipt.tax_table)
                code = x.vat if row is None else receipt.tax_table[row]['code']
                by_code[code] = by_code.get(code, Decimal('0')) + amount
            unmarked = by_code.pop('', Decimal('0'))     # VAT code not read by the phone: any row may hold these items
            problems += vat_problems(by_code, {x['code']: x['total'] for x in receipt.tax_table}, discount - unmarked)
    total = sum((amount for _, amount in paid), Decimal('0')) - discount
    if not discount and is_net_of_vat(total, len(paid), at_qr):
        paid = with_vat(paid, receipt.tax_table, problems)
        total = sum((amount for _, amount in paid), Decimal('0'))
    if total != at_qr.total:
        problems.append(f"total: items {total}, QR code {at_qr.total}")
    lines = [_sourced({'name': line_name(x), 'amount': sign * amount}, x.source_lines) for x, amount in paid]
    lines += [_sourced(discount_line(label, amount, sign), source) for label, amount, source in discounts]
    return [dict(x, trust=LineTrust.PROVEN) for x in lines], problems


# True if 'total' of that many lines is the QR's base and not its total: the receipt is priced net of VAT
def is_net_of_vat(total: Decimal, lines: int, at_qr: AtQr) -> bool:
    base = at_qr.total - at_qr.tax_total
    return bool(at_qr.tax_total) and total != at_qr.total and abs(total - base) <= net_rounding(lines)


# The line with the 'ocr.lines' rows it was read from, where the phone told them
def _sourced(line: dict, source_lines: tuple) -> dict:
    return dict(line, source=tuple(source_lines)) if source_lines else line


# Paper items that make a line when loaded as read: a shop profile leaves out the discounts under an item where they
# are already in its price
def read_items(paper_items: list, nif: str) -> list:
    profile = shop_profile(nif) if nif else None
    in_price = profile is not None and not profile.discounts_netted
    return [x for x in paper_items if x.role == PaperItem.ITEM
            or (x.role == PaperItem.DISCOUNT and not (in_price and x.scope == PaperItem.UNDER_ITEM))]


# Lines as the phone read them, nothing folded: an item is spent (money back if printed negative), a discount is a
# line of its own, an item whose amount wasn't read is marked so. 'reliable' is False for a scan without a usable
# fiscal code.
def lines_as_read(items: list, sign: Decimal, reliable: bool) -> list:
    lines = []
    for x in items:
        if x.role == PaperItem.ITEM:
            amount = x.amount if x.sign_printed == PaperItem.POSITIVE else -x.amount
            line = {'name': line_name(_receipt_item(x)), 'amount': sign * amount}
        else:
            line = discount_line(x.text, x.amount, sign)
        if x.amount_source == PaperItem.UNREAD:
            trust = LineTrust.MISSING
        elif reliable and x.confidence is not None and x.confidence >= OCR_CONFIDENCE_THRESHOLD:
            trust = LineTrust.READ
        else:
            trust = LineTrust.UNRELIABLE
        lines.append(dict(_sourced(line, x.source_lines), trust=trust))
    return lines


# 'lines' read off a receipt priced net of VAT (they give the QR's base, not its total) with the VAT added, so they
# add up to what was paid; the lines as given if they aren't net or their VAT can't be told. A document of one VAT
# bucket takes the QR's own tax to its base, any other needs the VAT table and every line's row in it.
def vat_added(lines: list, items: list, tax_table: list, at_qr: AtQr, sign: Decimal) -> list:
    paid = [(_receipt_item(x), sign * line['amount']) for x, line in zip(items, lines)]
    if not is_net_of_vat(sum((amount for _, amount in paid), Decimal('0')), len(paid), at_qr):
        return lines
    buckets = at_qr.tax_lines
    if len(buckets) == 1 and buckets[0] == (at_qr.total - at_qr.tax_total, at_qr.tax_total):
        base, tax = buckets[0]
        tax_table = [{'code': '', 'rate': tax / base * 100, 'base': base, 'tax': tax}]
    problems = []
    paid = with_vat(paid, tax_table, problems)
    if problems or sum((amount for _, amount in paid), Decimal('0')) != at_qr.total:
        logging.debug(f"Receipt lines look net of VAT, but it can't be added: {'; '.join(problems)}")
        return lines
    logging.info(ReceiptAPI.tr("The receipt is priced net of VAT: the VAT was added to its lines"))
    return [dict(line, amount=sign * amount) for line, (_, amount) in zip(lines, paid)]


def _receipt_item(x: PaperItem) -> ReceiptItem:
    return ReceiptItem(name=x.text, amount=x.amount, vat=x.tax_code, qty=x.quantity, price=x.unit_price,
                       department=x.department, source_lines=x.source_lines)


_ROW_AMOUNT = re.compile(r'^(?P<name>.*?\S)\s+(?P<minus>-\s?)?(?P<amount>\d+[.,]\d\d)\s*(?:€|EUR|[A-Z])?\s*$')


# A line of one printed row that the phone read as no item, made on the user's word: the amount the row ends with,
# or a line marked as having none. 'sign' is the receipt's items' one.
def line_of_row(text: str, sign: Decimal) -> dict:
    match = _ROW_AMOUNT.match(text)
    if match is None:
        return {'name': text.strip(), 'amount': Decimal('0'), 'trust': LineTrust.MISSING}
    amount = Decimal(match['amount'].replace(',', '.'))
    return {'name': match['name'].strip(), 'amount': sign * (-amount if match['minus'] else amount),
            'trust': LineTrust.UNRELIABLE}


# (item, amount paid) pairs, receipt-wide discounts as (label, amount, source lines) and problems by the phone's
# 'effect': a deduction printed under an item is folded into it, one off the whole receipt is a discount of its own,
# a line of no effect is left out
def by_effect(paper_items: list) -> tuple:
    paid, discounts, problems = [], [], []
    for x in paper_items:
        if x.effect == PaperItem.CHARGE:
            paid.append([_receipt_item(x), x.amount])
        elif x.effect == PaperItem.DEDUCTION and x.role == PaperItem.ITEM:     # money back on an item line
            paid.append([_receipt_item(x), -x.amount])
        elif x.effect == PaperItem.DEDUCTION:
            if x.scope == PaperItem.RECEIPT or not paid:
                discounts.append((x.text, x.amount, x.source_lines))
            else:
                paid[-1][0].discounts.append((x.text, x.amount))
                paid[-1][0].source_lines += x.source_lines
                paid[-1][1] -= x.amount
        elif x.effect != PaperItem.NO_EFFECT:
            problems.append(f"'{x.text}' has unknown effect '{x.effect}'")
    return [tuple(x) for x in paid], discounts, problems


# (item, amount) pairs of 'paid' with each item's VAT added at the rate of its VAT table row; a row's rounding cents
# go to its largest item, so every row adds up to its base + tax. A row's items may miss its base by net_rounding().
# A table of one row holds every item, whatever its VAT code was read as.
def with_vat(paid: list, table: list, problems: list) -> list:
    members = [[] for _ in table]
    for i, (x, _) in enumerate(paid):
        row = 0 if len(table) == 1 else vat_row(x.vat, table)
        if row is None:
            problems.append(f"net of VAT: no VAT table row for '{x.name}' of VAT '{x.vat}'")
            return paid
        members[row].append(i)
    result = list(paid)
    for row, items in zip(table, members):
        if row['rate'] is None or row['base'] is None or row['tax'] is None:
            problems.append(f"net of VAT: VAT {row['code']} has no rate, base or tax")
            continue
        base = sum((paid[i][1] for i in items), Decimal('0'))
        if abs(base - row['base']) > net_rounding(len(items)):
            problems.append(f"net of VAT: VAT {row['code']} items {base}, table base {row['base']}")
            continue
        vat = {i: (paid[i][1] * row['rate'] / 100).quantize(CENT, rounding=ROUND_HALF_UP) for i in items}
        rest = row['tax'] - sum(vat.values(), Decimal('0'))
        if abs(rest) > CENT * len(items) / 2:
            problems.append(f"net of VAT: VAT {row['code']} items' tax {row['tax'] - rest}, table {row['tax']}")
            continue
        if items:
            vat[max(items, key=lambda i: paid[i][1])] += rest + row['base'] - base
        for i in items:
            result[i] = (paid[i][0], paid[i][1] + vat[i])
    return result


# Index of the VAT table row of an item's VAT code: the same code, or else the same rate ('6%' is row '6,00%');
# None if there is no such row or more than one
def vat_row(code: str, table: list) -> Optional[int]:
    rows = [i for i, x in enumerate(table) if x['code'] == code]
    if not rows and (match := re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*%\s*', code)):
        rate = Decimal(match[1].replace(',', '.'))
        rows = [i for i, x in enumerate(table) if x['rate'] == rate]
    return rows[0] if len(rows) == 1 else None
