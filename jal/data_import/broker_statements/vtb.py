from jal.data_import.statement_xls import StatementXLS

JAL_STATEMENT_CLASS = "StatementVTB"

# ----------------------------------------------------------------------------------------------------------------------
class StatementVTB(StatementXLS):
    PeriodPattern = (7, 1, r"Отчет Банка ВТБ \(ПАО\) за период с (?P<S>\d\d\.\d\d\.\d\d\d\d) по (?P<E>\d\d\.\d\d\.\d\d\d\d) о сделках, .*")
    AccountPattern = (9, 7, None)

    def __init__(self):
        super().__init__()
        self.name = self.tr("VTB Investments")
        self.icon_name = "vtb.ico"
        self.filename_filter = self.tr("VTB statement (*.xls)")
        self.asset_withdrawal = []

    def _load_deals(self):
        pass

    def _load_cash_transactions(self):
        pass
