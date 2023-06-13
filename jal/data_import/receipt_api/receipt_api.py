from abc import ABC, abstractmethod
from PySide6.QtCore import QObject, Signal


#-----------------------------------------------------------------------------------------------------------------------
# Meta class to resolve conflict
class ReceiptAPIMeta(type(QObject), type(ABC)):
    pass

#-----------------------------------------------------------------------------------------------------------------------
# Base parent class for various API used by JAL for downloading information about purchases (slips)
class ReceiptAPI(metaclass=ReceiptAPIMeta):
    slip_load_failed = Signal()
    slip_load_ok = Signal()

    def __init__(self):
        super().__init__()

    # Provides a list of parameters required for slip query if manual input is in use
    @staticmethod
    @abstractmethod
    def input_data_list() -> list:
        pass

    # Method performs required actions to have active API session that may be used for queries
    # Returns True after successful activation and False otherwise
    @abstractmethod
    def activate_session(self) -> bool:
        pass

    # Request slip data via API
    @abstractmethod
    def query_slip(self):
        pass

    # Returns a list of purchased items (as dictionaries with name, price, amount, etc)
    @abstractmethod
    def slip_lines(self) -> list:
        pass

    # Returns a shop name where purchase was done (if it is possible to get)
    @abstractmethod
    def shop_name(self) -> str:
        pass
