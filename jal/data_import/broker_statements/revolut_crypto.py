import logging
import pandas
from jal.data_import.statement import FOF, Statement, Statement_Capabilities

JAL_STATEMENT_CLASS = "StatementRevolutCrypto"


# ----------------------------------------------------------------------------------------------------------------------
class StatementRevolutCrypto(Statement):
    ACCOUNT_ID = 1

    def __init__(self):
        super().__init__()
        self.name = self.tr("Revolut / Crypto")
        self.icon_name = "revolut.png"
        self.filename_filter = self.tr("Revolut statement (*.csv)")
        self._statement = None

    @staticmethod
    def capabilities() -> set:
        return {Statement_Capabilities.MULTIPLE_LOAD}

    def load(self, filename: str) -> None:
        self._data = {
            FOF.PERIOD: [0, 0],
            FOF.ACCOUNTS: [],
            FOF.ASSETS: [],
            FOF.SYMBOLS: [],
            FOF.ASSETS_DATA: [],
            FOF.TRADES: [],
            FOF.TRANSFERS: [],
            FOF.CORP_ACTIONS: [],
            FOF.ASSET_PAYMENTS: [],
            FOF.INCOME_SPENDING: []
        }

        self._statement = pandas.read_csv(filename, header=0)
        self._statement['Started Date'] = pandas.to_datetime(self._statement['Started Date'], format='%Y-%m-%d %H:%M:%S')
        self._statement['Completed Date'] = pandas.to_datetime(self._statement['Completed Date'], format='%Y-%m-%d %H:%M:%S')

        self._data[FOF.ACCOUNTS].append({'id': self.ACCOUNT_ID,
                                         'selection_text': self.tr("Revolut statement doesn't have account number.\nPlease select an account for import:")})

        for i, row in self._statement.iterrows():
            assert row['Type'] == 'REWARD', "Buy/Sell operations are not implemented yet"
            assert row['State'] == 'COMPLETED', "States other then COMPLETED were not tested"
            qty = row['Amount']
            amount = row['Fiat amount']
            op_date = row['Completed Date']
            currency_id = self.currency_id(row['Base currency'])
            asset_id = self.asset_id({'type': FOF.ASSET_CRYPTO, 'symbol': row['Currency'],
                           'name': row['Currency'], 'currency': currency_id})
            balance = row['Balance']  # end crypto balance after operation
            vesting = {'id': i, 'type': FOF.PAYMENT_STOCK_VESTING, 'account': self.ACCOUNT_ID, 'timestamp': int(op_date.timestamp()),
                       'asset': asset_id, 'amount': qty, 'price': amount/qty, 'description': row['Description']}
            self._data[FOF.ASSET_PAYMENTS].append(vesting)
        logging.info(self.tr("Statement loaded successfully: ") + f"{filename}")

