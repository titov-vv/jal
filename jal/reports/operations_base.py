# Base classes for Category, Tag and Peer reports
from decimal import Decimal
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from jal.db.asset import JalAsset
from jal.db.helpers import localize_decimal
from jal.db.operations_model import OperationsModel

class ReportOperationsModel(OperationsModel):
    def __init__(self, parent_view):
        self._total = Decimal('0')
        self._total_currency = 0
        self._total_currency_name = ''
        super().__init__(parent_view)

    # Is used by view to display footer Title, Total amount and Total currency with right font and alignment in columns 3-5
    def footerData(self, section: int, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if section == 4:
                return localize_decimal(self._total, precision=2)
            elif section == 5:
                return self._total_currency_name
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            if section == 3 or section == 4:
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        return None

    # Triggers view update if display parameters were changed
    def updateView(self, update: bool, dates_range: tuple, total_currency_id: int):
        if self._begin != dates_range[0]:
            self._begin = dates_range[0]
            update = True
        if self._end != dates_range[1]:
            self._end = dates_range[1]
            update = True
        if self._total_currency != total_currency_id:
            self._total_currency = total_currency_id
            self._total_currency_name = JalAsset(total_currency_id).symbol()
            update = True
        if update:
            self.prepareData()
            self.configureView()
