from jal.data_import.statement import Statement

JAL_STATEMENT_CLASS = "StatementOpenPortfolio"


# -----------------------------------------------------------------------------------------------------------------------
class StatementOpenPortfolio(Statement):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Investbook / IZI-Invest")
        self.icon_name = "open_portfolio.png"
        self.filename_filter = self.tr("Open portfolio (*.json)")

    def load(self, filename: str) -> None:
        super().load(filename)
