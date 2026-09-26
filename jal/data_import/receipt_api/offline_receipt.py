import logging
from datetime import datetime, time
from decimal import Decimal
from typing import Optional
from PySide6.QtCore import QDateTime, QDate, QTime
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.data_import.receipt_api.pt_at_qr import AtQr
from jal.data_import.receipt_inbox import JalrFile, PaperItem
from jal.data_import.receipt import ReceiptItem, shop_profile, line_name, is_subtotal, vat_problems, discount_line
from jal.db.clock import local_zone


#-----------------------------------------------------------------------------------------------------------------------
# A receipt that is already at hand (read from a file of the phone inbox): nothing to log in to or to download
class ReceiptOffline(ReceiptAPI):
    def __init__(self, shop_name: str, date_time: QDateTime, lines: list, number: str = ''):
        super().__init__()
        self._shop_name = shop_name
        self._date_time = date_time
        self._lines = lines
        self._number = number

    # A receipt of the Portuguese fiscal QR, for the day it gives: the 'lines' given or one line of its total
    @classmethod
    def from_at_qr(cls, at_qr: AtQr, captured_at: datetime, lines: Optional[list] = None) -> 'ReceiptOffline':
        shop = f"NIF {at_qr.nif}"
        amount = at_qr.total if at_qr.is_return else -at_qr.total
        day = at_qr.date
        moment = captured_at.time() if captured_at.date() == day else time(0, 0)   # a scan made later has no time
        date_time = QDateTime(QDate(day.year, day.month, day.day),
                              QTime(moment.hour, moment.minute, moment.second), local_zone())
        return cls(shop, date_time, lines or [{'name': shop, 'amount': amount}], at_qr.number)

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


# ----------------------------------------------------------------------------------------------------------------------
# Lines of the items the phone read off a paper receipt, or [] when they can't be trusted (the receipt is then one
# line of its total). A discount belongs to the item above it, or to the whole receipt below a SUBTOTAL row; the shop
# profile, if any, says whether it is money off and must agree with the reading the phone found to balance.
def paper_lines(receipt: JalrFile, at_qr: AtQr) -> list:
    problems, items, discounts, item_rows = [], [], [], ()
    texts = receipt.ocr_texts
    for x in receipt.paper_items:
        if x.role == PaperItem.ITEM:
            items.append(ReceiptItem(name=x.text, amount=x.amount, vat=x.tax_code, qty=x.quantity,
                                     price=x.unit_price, department=x.department))
            item_rows = x.source_lines
        elif x.role == PaperItem.DISCOUNT and items:
            between = texts[max(item_rows) + 1:min(x.source_lines)] if item_rows and x.source_lines else []
            if any(is_subtotal(line) for line in between):
                discounts.append((x.text, x.amount))
            else:
                items[-1].discounts.append((x.text, x.amount))
        else:
            problems.append(f"'{x.text}' isn't an item or a discount of one")
    netted = True
    if discounts or any(x.discounts for x in items):
        hypothesis = receipt.discount_hypothesis
        if hypothesis not in (JalrFile.NETTED, JalrFile.INFORMATIONAL):
            problems.append(f"discounts without a reading that balances them ('{hypothesis}')")
        netted = hypothesis == JalrFile.NETTED
        profile = shop_profile(at_qr.nif)
        if profile is not None and profile.discounts_netted != netted:
            problems.append(f"discounts are {'' if profile.discounts_netted else 'not '}money off for "
                            f"{profile.name}, the phone balanced them as '{hypothesis}'")
    paid = [(x, x.amount - sum(a for _, a in x.discounts) if netted else x.amount) for x in items]
    discount = sum((a for _, a in discounts), Decimal('0')) if netted else Decimal('0')
    if discount and receipt.tax_table:
        if any(x['total'] is None for x in receipt.tax_table):
            problems.append("VAT table without totals")
        else:
            by_code = {}
            for x, amount in paid:
                by_code[x.vat] = by_code.get(x.vat, Decimal('0')) + amount
            problems += vat_problems(by_code, {x['code']: x['total'] for x in receipt.tax_table}, discount)
    total = sum((amount for _, amount in paid), Decimal('0')) - discount
    if total != at_qr.total:
        problems.append(f"total: items {total}, QR code {at_qr.total}")
    if problems:
        logging.warning(ReceiptAPI.tr("Receipt items don't add up, the receipt is loaded as one line")
                        + f" ({receipt.name}): " + "; ".join(problems))
        return []
    sign = Decimal('1') if at_qr.is_return else Decimal('-1')
    lines = [{'name': line_name(x), 'amount': sign * amount} for x, amount in paid]
    if discount:
        lines += [discount_line(label, amount, sign) for label, amount in discounts]
    return lines
