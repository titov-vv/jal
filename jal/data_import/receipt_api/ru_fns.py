from urllib.parse import parse_qs
from PySide6.QtCore import Qt, QDateTime
from jal.data_import.receipt_api.receipt_api import ReceiptAPI


#-----------------------------------------------------------------------------------------------------------------------
class ReceiptRuFNS(ReceiptAPI):
    timestamp_patterns = ['yyyyMMddTHHmm', 'yyyyMMddTHHmmss', 'yyyy-MM-ddTHH:mm', 'yyyy-MM-ddTHH:mm:ss']

    def __init__(self, qr_text=''):
        super().__init__()
        self.session_id = ''
        try:
            params = parse_qs(qr_text)
            for timestamp_pattern in self.timestamp_patterns:
                datetime = QDateTime.fromString(params['t'][0], timestamp_pattern)
                datetime.setTimeSpec(Qt.UTC)
                if datetime.isValid():
                    self.timestamp = datetime.toSecsSinceEpoch()
            self.amount = params['s'][0]
            self.fn = params['fn'][0]
            self.fd = params['i'][0]
            self.fp = params['fp'][0]
            self.op_type = params['n'][0]
        except Exception:
            raise ValueError(self.tr("FNS QR available but pattern isn't recognized: " + qr_text))
