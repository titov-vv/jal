from jal.data_import.receipt_api.receipt_api import ReceiptAPI


#-----------------------------------------------------------------------------------------------------------------------
class ReceiptPtPingoDoce(ReceiptAPI):
    receipt_pattern = r"A:.*\*B:.*\*C:PT\*D:FS\*E:N\*F:(?P<date>\d{8})\*G:FS (?P<shop_id>\d{4})\d(?P<register_id>\d{2})..\/.*\*H:.{1,70}\*I1:PT\*.*"
    def __init__(self, qr_text=''):
        super().__init__()