import re
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS
from jal.data_import.receipt_api.eu_lidl_plus import ReceiptEuLidlPlus
from jal.data_import.receipt_api.pt_pingo_doce import ReceiptPtPingoDoce
from jal.widgets.qr_scanner import ScanDialog, QRScanner


# ----------------------------------------------------------------------------------------------------------------------
# Possible values that may be used by factory
RU_FNS_API = 'RU_FNS'
EU_LIDL_PLUS_API = 'EU_LIDL_PLUS'
PT_PINGO_DOCE_API = 'PT_PINGO_DOCE'


# ----------------------------------------------------------------------------------------------------------------------
class ReceiptAPIFactory(QObject):
    def __init__(self):
        super().__init__()
        self._apis = {
            RU_FNS_API: ReceiptRuFNS,
            EU_LIDL_PLUS_API: ReceiptEuLidlPlus,
            PT_PINGO_DOCE_API: ReceiptPtPingoDoce
        }
        self.supported_names = {
            RU_FNS_API: self.tr("Russian receipt"),
            EU_LIDL_PLUS_API: self.tr("European Lidl receipt"),
            PT_PINGO_DOCE_API: self.tr("Portuguese Pingo Doce receipt")
        }
        self._pt_nifs = {
            '503340855': EU_LIDL_PLUS_API,
            '500829993': PT_PINGO_DOCE_API
        }

    def get_api_parameters(self, api_type):
        api = self._apis.get(api_type)
        return api.parameters_list()

    # Selects required API class based on QR data pattern
    def get_api_for_qr(self, qr_text):
        extra_data=''
        api_type = self._detect_api_id_by_qr(qr_text)
        if api_type == EU_LIDL_PLUS_API:
            scanner = ScanDialog(code_type=QRScanner.TYPE_ITF,
                                 message=self.tr("Please scan flat barcode from the receipt"))
            if scanner.exec() == QDialog.Accepted:
                extra_data = scanner.data
        api = self._apis.get(api_type)
        return api(qr_text=qr_text, aux_data=extra_data)

    def _detect_api_id_by_qr(self, qr_text):
        ru_fns_keys = ["i=", "n=", "s=", "t=", "fn=", "fp="]
        pt_at_pattern = r"A:(?P<NIF>.{1,9})\*B:.{1,30}\*C:PT\*D:FS\*E:N\*F:\d{8}\*G:.{1,30}\*H:.{1,70}\*I1:PT\*.*"
        if all([x in qr_text for x in ru_fns_keys]):
            return RU_FNS_API
        parts = re.match(pt_at_pattern, qr_text)
        if parts is not None:
            NIF = parts.groupdict()['NIF']
            try:
                return self._pt_nifs[NIF]
            except KeyError:
                raise ValueError(self.tr("Portuguese QR recognized but shop isn't supported, NIF: ") + f"{NIF}")
        raise ValueError(self.tr("No API found for QR data: ") + f"'{qr_text}'")

    def get_api_with_params(self, api_type, params):
        api = self._apis.get(api_type)
        return api(params=params)
