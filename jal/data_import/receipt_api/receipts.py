import re
from PySide6.QtCore import QObject
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS
from jal.data_import.receipt_api.eu_lidl_plus import ReceiptEuLidlPlus
from jal.data_import.receipt_api.pt_pingo_doce import ReceiptPtPingoDoce

# ----------------------------------------------------------------------------------------------------------------------
# Possible values that may be used by factory
RU_FNS_API = 'RU_FNS'
EU_LIDL_PLUS_API = 'EU_LIDL_PLUS'
PT_PINGO_DOCE_API = 'EU_PINGO_DOCE'


# ----------------------------------------------------------------------------------------------------------------------
class ReceiptAPIFactory(QObject):
    def __init__(self):
        super().__init__()
        self._apis = {
            RU_FNS_API: ReceiptRuFNS,
            EU_LIDL_PLUS_API: ReceiptEuLidlPlus,
            PT_PINGO_DOCE_API: ReceiptPtPingoDoce
        }
        self._pt_nifs = {
            '503340855': EU_LIDL_PLUS_API,
            '500829993': PT_PINGO_DOCE_API
        }

    # Selects required API class based on QR data pattern
    def get_api_for_qr(self, qr_text):
        api = self._apis.get(self._detect_api_id_by_qr(qr_text))
        return api(qr_text)

    def _detect_api_id_by_qr(self, qr_text):
        ru_fns_keys = ["i=", "n=", "s=", "t=", "fn=", "fp="]
        pt_at_pattern = r"A:(?P<NIF>.{1,9})\*.*B:.{1,30}\*.*C:PT\*D:FS\*E:N\*F:\d{8}\*G:.{1,30}\*H:.{1,70}\*I1:PT\*.*"
        if all([x in qr_text for x in ru_fns_keys]):
            return RU_FNS_API
        parts = re.match(pt_at_pattern, qr_text)
        if parts is not None:
            NIF = parts.groupdict()['NIF']
            try:
                return self._pt_nifs[NIF]
            except KeyError:
                raise ValueError(self.tr("Portuguese QR recognized but shop isn't supported, NIF: " + f"{NIF}"))
        raise ValueError(self.tr("No API found for QR data: " + f"'{qr_text}'"))
