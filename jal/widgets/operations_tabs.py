from PySide6.QtWidgets import QWidget, QStackedWidget

from jal.widgets.corporate_action_widget import CorporateActionWidget
from jal.widgets.dividend_widget import DividendWidget
from jal.widgets.income_spending_widget import IncomeSpendingWidget
from jal.widgets.trade_widget import TradeWidget
from jal.widgets.transfer_widget import TransferWidget


class JalOperationsTabs(QStackedWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.NoOperation = QWidget(self)
        self.addWidget(self.NoOperation)
        self.IncomeSpending = IncomeSpendingWidget(self)
        self.addWidget(self.IncomeSpending)
        self.Dividend = DividendWidget(self)
        self.addWidget(self.Dividend)
        self.Trade = TradeWidget(self)
        self.addWidget(self.Trade)
        self.Transfer = TransferWidget(self)
        self.addWidget(self.Transfer)
        self.CorporateAction = CorporateActionWidget(self)
        self.addWidget(self.CorporateAction)
