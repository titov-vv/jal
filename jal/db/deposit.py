from decimal import Decimal
from jal.constants import BookAccount
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction


class JalDeposit(JalDB):
    def __init__(self, id: int = 0):
        super().__init__()
        self._id = id
        self._data = self._read("SELECT account_id, note FROM term_deposits WHERE id=:deposit_id",
                                [(":deposit_id", self._id)], named=True)
        self._account_id = 0 if self._data is None else self._data['account_id']
        self._account = JalAccount(self._account_id)
        self._currency = JalAsset(self._account.currency())
        self._note = '' if self._data is None else self._data['note']
        actions_query = self._exec("SELECT timestamp, action_type, amount FROM deposit_actions "
                                   "WHERE deposit_id=:deposit_id", [(":deposit_id", self._id)])
        self._actions = []
        while actions_query.next():
            self._actions.append(self._read_record(actions_query, named=True))

    @classmethod
    # Returns a list of deposits that are opened before and not closed at given timestamp
    def get_term_deposits(cls, timestamp: int) -> list:
        deposits = []
        query = cls._exec(
            "SELECT o.deposit_id FROM deposit_actions o "
            "LEFT JOIN deposit_actions c ON o.action_type=1 AND c.action_type=100 and o.deposit_id=c.deposit_id "
            "WHERE o.timestamp<=:timestamp AND c.timestamp>=:timestamp", [(":timestamp", timestamp)])
        while query.next():
            deposits.append(JalDeposit(super(JalDeposit, JalDeposit)._read_record(query, cast=[int])))
        return deposits

    # returns name of the deposit as it was given in notes
    def name(self) -> str:
        return self._note

    # Returns currency of the deposit
    def currency(self) -> JalAsset:
        return self._currency

    def balance(self, timestamp: int) -> Decimal:
        balance = self._read(
            "WITH last_deposit_amount AS ( "
            "SELECT amount_acc, ROW_NUMBER() OVER (PARTITION BY op_type, operation_id ORDER BY id DESC) AS row_no "
            "FROM ledger WHERE book_account=:book AND op_type=:type AND operation_id=:id AND timestamp<=:timestamp) "
            "SELECT amount_acc FROM last_deposit_amount WHERE row_no=1",
            [(":book", BookAccount.Savings), (":type", LedgerTransaction.TermDeposit),
             (":id", self._id), (":timestamp", timestamp)])
        balance = Decimal('0') if balance is None else Decimal(balance)
        return balance
