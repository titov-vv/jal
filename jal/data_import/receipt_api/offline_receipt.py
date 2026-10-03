import re
import logging
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from PySide6.QtCore import QDateTime, QDate, QTime
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.receipt_inbox import JalrFile, PaperItem
from jal.data_import.receipt import ReceiptItem, LineTrust, Verdict, shop_profile, line_name, vat_problems, \
    discount_line, parse_vouchers
from jal.db.clock import local_zone

OCR_CONFIDENCE_THRESHOLD = Decimal('0.5')     # provisional: the phone's own 'ocr_confidence' bar


#-----------------------------------------------------------------------------------------------------------------------
# A receipt that is already at hand (read from a file of the phone inbox): nothing to log in to or to download
class ReceiptOffline(ReceiptAPI):
    def __init__(self, shop_name: str, date_time: QDateTime, lines: list, number: str = '',
                 total: Optional[Decimal] = None, verdict: str = ''):
        super().__init__()
        self._shop_name = shop_name
        self._date_time = date_time
        self._lines = lines
        self._number = number
        self._total = total
        self._verdict = verdict

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
    return lines_as_read(receipt.paper_items, at_qr.nif if at_qr is not None else '', sign, reliable), False


# Lines by the phone's 'effect' and what doesn't add up in them. Items that add up to the QR's base rather than its
# total are priced net of VAT and get it added.
def proven_lines(receipt: JalrFile, at_qr: AtQr, sign: Decimal) -> tuple:
    paid, discounts, problems = by_effect(receipt.paper_items)
    discount = sum((a for _, a in discounts), Decimal('0'))
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
    if at_qr.tax_total and not discount and total == at_qr.total - at_qr.tax_total:     # priced net of VAT
        paid = with_vat(paid, receipt.tax_table, problems)
        total = sum((amount for _, amount in paid), Decimal('0'))
    if total != at_qr.total:
        problems.append(f"total: items {total}, QR code {at_qr.total}")
    lines = [{'name': line_name(x), 'amount': sign * amount} for x, amount in paid]
    lines += [discount_line(label, amount, sign) for label, amount in discounts]
    return [dict(x, trust=LineTrust.PROVEN) for x in lines], problems


# Lines as the phone read them, nothing folded: an item is spent (money back if printed negative), a discount is a
# line of its own. A shop profile leaves out the discounts under an item where they are already in its price.
# 'reliable' is False for a scan without a usable fiscal code.
def lines_as_read(paper_items: list, nif: str, sign: Decimal, reliable: bool) -> list:
    profile = shop_profile(nif) if nif else None
    in_price = profile is not None and not profile.discounts_netted
    lines = []
    for x in paper_items:
        if x.role == PaperItem.ITEM:
            amount = x.amount if x.sign_printed == PaperItem.POSITIVE else -x.amount
            line = {'name': line_name(_receipt_item(x)), 'amount': sign * amount}
        elif x.role == PaperItem.DISCOUNT:
            if in_price and x.scope == PaperItem.UNDER_ITEM:
                continue
            line = discount_line(x.text, x.amount, sign)
        else:
            continue
        confident = reliable and x.confidence is not None and x.confidence >= OCR_CONFIDENCE_THRESHOLD
        lines.append(dict(line, trust=LineTrust.READ if confident else LineTrust.UNRELIABLE))
    return lines


def _receipt_item(x: PaperItem) -> ReceiptItem:
    return ReceiptItem(name=x.text, amount=x.amount, vat=x.tax_code, qty=x.quantity, price=x.unit_price,
                       department=x.department)


# (item, amount paid) pairs, receipt-wide discounts and problems by the phone's 'effect': a deduction printed under an
# item is folded into it, one off the whole receipt is a discount of its own, a line of no effect is left out
def by_effect(paper_items: list) -> tuple:
    paid, discounts, problems = [], [], []
    for x in paper_items:
        if x.effect == PaperItem.CHARGE:
            paid.append([_receipt_item(x), x.amount])
        elif x.effect == PaperItem.DEDUCTION and x.role == PaperItem.ITEM:     # money back on an item line
            paid.append([_receipt_item(x), -x.amount])
        elif x.effect == PaperItem.DEDUCTION:
            if x.scope == PaperItem.RECEIPT or not paid:
                discounts.append((x.text, x.amount))
            else:
                paid[-1][0].discounts.append((x.text, x.amount))
                paid[-1][1] -= x.amount
        elif x.effect != PaperItem.NO_EFFECT:
            problems.append(f"'{x.text}' has unknown effect '{x.effect}'")
    return [tuple(x) for x in paid], discounts, problems


# (item, amount) pairs of 'paid' with each item's VAT added at the rate of its VAT table row; a row's rounding cents
# go to its largest item, so every row adds up to its base + tax
def with_vat(paid: list, table: list, problems: list) -> list:
    members = [[] for _ in table]
    for i, (x, _) in enumerate(paid):
        row = vat_row(x.vat, table)
        if row is None:
            problems.append(f"net of VAT: no VAT table row for '{x.name}' of VAT '{x.vat}'")
            return paid
        members[row].append(i)
    result, cent = list(paid), Decimal('0.01')
    for row, items in zip(table, members):
        if row['rate'] is None or row['base'] is None or row['tax'] is None:
            problems.append(f"net of VAT: VAT {row['code']} has no rate, base or tax")
            continue
        base = sum((paid[i][1] for i in items), Decimal('0'))
        if base != row['base']:
            problems.append(f"net of VAT: VAT {row['code']} items {base}, table base {row['base']}")
            continue
        vat = {i: (paid[i][1] * row['rate'] / 100).quantize(cent, rounding=ROUND_HALF_UP) for i in items}
        rest = row['tax'] - sum(vat.values(), Decimal('0'))
        if abs(rest) > cent * len(items) / 2:
            problems.append(f"net of VAT: VAT {row['code']} items' tax {row['tax'] - rest}, table {row['tax']}")
            continue
        if items:
            vat[max(items, key=lambda i: paid[i][1])] += rest
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
