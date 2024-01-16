from jal.ui.widgets.ui_term_deposit_operation import Ui_TermDepositOperation
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.db.operations import LedgerTransaction


# ----------------------------------------------------------------------------------------------------------------------
class TermDepositWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        super().__init__(parent=parent, ui_class=Ui_TermDepositOperation)
        self.operation_type = LedgerTransaction.TermDeposit

        super()._init_db("term_deposits")
