from PySide6.QtCore import QObject
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS
from jal.data_import.receipt_api.eu_lidl_plus import ReceiptEuLidlPlus
from jal.data_import.receipt_api.pt_pingo_doce import ReceiptPtPingoDoce


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

    def get_api_parameters(self, api_type):
        api = self._apis.get(api_type)
        return api.parameters_list()

    def get_api_with_params(self, api_type, params):
        api = self._apis.get(api_type)
        return api(params=params)
