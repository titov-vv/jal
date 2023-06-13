from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS
# ----------------------------------------------------------------------------------------------------------------------
# Possible values that may be used by factory
RU_FNS_API = 'RU_FNS'
EU_LIDL_PLUS_API = 'EU_LIDL_PLUS'
PT_PINGO_DOCE_API = 'EU_PINGO_DOCE'


# ----------------------------------------------------------------------------------------------------------------------
class ReceiptAPIFactory:
    def __init__(self):
        self._apis = {
            RU_FNS_API: ReceiptRuFNS
        }

    # Selects required API class based on QR data pattern
    def get_api_for_qr(self, qr_text):
        return self._get_api(self._detect_api_id(qr_text))

    def _get_api(self, api_id):
        api = self._apis.get(api_id)
        if not api:
            raise ValueError(api_id)
        return api()

    def _detect_api_id(self, text):
        ru_fns_keys = ["i=", "n=", "s=", "t=", "fn=", "fp="]
        if all([x in text for x in ru_fns_keys]):
            return RU_FNS_API
        return ''
