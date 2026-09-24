from PySide6.QtCore import QObject
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS


# ----------------------------------------------------------------------------------------------------------------------
# Possible values that may be used by factory
RU_FNS_API = 'RU_FNS'


# ----------------------------------------------------------------------------------------------------------------------
class ReceiptAPIFactory(QObject):
    def __init__(self):
        super().__init__()
        self._apis = {
            RU_FNS_API: ReceiptRuFNS
        }
        self.supported_names = {
            RU_FNS_API: self.tr("Russian receipt")
        }

    def get_api_parameters(self, api_type):
        api = self._apis.get(api_type)
        return api.parameters_list()

    def get_api_with_params(self, api_type, params):
        api = self._apis.get(api_type)
        return api(params=params)
