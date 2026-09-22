from datetime import datetime, time
from PySide6.QtCore import QDateTime, QDate, QTime
from jal.data_import.receipt_api.receipt_api import ReceiptAPI
from jal.data_import.receipt_api.pt_at_qr import AtQr
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

    # Only the Portuguese fiscal QR is readable: one line of the receipt total, for the day the QR gives
    @classmethod
    def from_at_qr(cls, at_qr: AtQr, captured_at: datetime) -> 'ReceiptOffline':
        shop = f"NIF {at_qr.nif}"
        amount = at_qr.total if at_qr.is_return else -at_qr.total
        day = at_qr.date
        moment = captured_at.time() if captured_at.date() == day else time(0, 0)   # a scan made later has no time
        date_time = QDateTime(QDate(day.year, day.month, day.day),
                              QTime(moment.hour, moment.minute, moment.second), local_zone())
        return cls(shop, date_time, [{'name': shop, 'amount': amount}], at_qr.number)

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
