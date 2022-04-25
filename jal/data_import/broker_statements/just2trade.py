from jal.data_import.statement_xls import StatementXLS

JAL_STATEMENT_CLASS = "StatementJ2T"


# ----------------------------------------------------------------------------------------------------------------------
class StatementJ2T(StatementXLS):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Just2Trade")
        self.icon_name = "j2t.png"
        self.filename_filter = self.tr("Just2Trade statement (*.xlsx)")
        self.asset_withdrawal = []
