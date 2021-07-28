from jal.data_import.statement import Statement, FOF


class StatementOpenBroker(Statement):
    def __init__(self):
        super().__init__()
        self._data = {}

    def load(self, filename: str) -> None:
        self._data = {
            FOF.PERIOD: [None, None],
            FOF.ACCOUNTS: [],
            FOF.ASSETS: [],
            FOF.TRADES: [],
            FOF.TRANSFERS: [],
            FOF.CORP_ACTIONS: [],
            FOF.ASSET_PAYMENTS: [],
            FOF.INCOME_SPENDING: []
        }
