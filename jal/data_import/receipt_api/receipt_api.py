from PySide6.QtCore import QObject, Signal, QDateTime
from PySide6.QtWidgets import QApplication


#-----------------------------------------------------------------------------------------------------------------------
# Base parent class for various API used by JAL for downloading information about purchases (slips)
class ReceiptAPI(QObject):
    slip_load_failed = Signal()
    slip_load_ok = Signal()

    def __init__(self):
        super().__init__()

    def tr(self, text):
        return QApplication.translate("ReceiptAPI", text)

    # Provides a list of parameters required for slip query if manual input is in use in form of dictionary
    # { "parameter_name" : "parameter_type" }
    @staticmethod
    def parameters_list() -> dict:
        raise NotImplementedError(f"parameters_list() shouldn't be called for ReceiptAPI class")

    # Method performs required actions to have active API session that may be used for queries
    # Returns True after successful activation and False otherwise
    def activate_session(self) -> bool:
        raise NotImplementedError(f"activate_session() method is not implemented in {type(self).__name__}")

    # Request slip data via API
    def query_slip(self):
        raise NotImplementedError(f"query_slip() method is not implemented in {type(self).__name__}")

    # Returns a list of purchased items (as dictionaries with name, price, amount, etc)
    def slip_lines(self) -> list:
        raise NotImplementedError(f"slip_lines() method is not implemented in {type(self).__name__}")

    # Returns a shop name where purchase was done (if it is possible to get)
    def shop_name(self) -> str:
        raise NotImplementedError(f"shop_name() method is not implemented in {type(self).__name__}")

    # Returns data/time of the operation from the receipt
    def datetime(self) -> QDateTime:
        raise NotImplementedError(f"datetime() method is not implemented in {type(self).__name__}")
