import logging
from decimal import Decimal
from jal.constants import BookAccount, DepositActions
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction


class JalDeposit(JalDB):
    def __init__(self, id: int = 0):
        super().__init__()
        self._id = id
        self._data = self._read("SELECT account_id, note FROM term_deposits WHERE oid=:oid",
                                [(":oid", self._id)], named=True)
        self._account_id = 0 if self._data is None else self._data['account_id']
        self._account = JalAccount(self._account_id)
        self._currency = JalAsset(self._account.currency())
        self._note = '' if self._data is None else self._data['note']
        actions_query = self._exec("SELECT timestamp, action_type, amount FROM deposit_actions "
                                   "WHERE deposit_id=:deposit_id", [(":deposit_id", self._id)])
        self._actions = []
        while actions_query.next():
            self._actions.append(self._read_record(actions_query, named=True, cast=[int, int, Decimal]))

    @classmethod
    # Returns a list of deposits that are opened before and not closed at given timestamp
    def get_term_deposits(cls, timestamp: int) -> list:
        deposits = []
        query = cls._exec(
            "SELECT o.deposit_id FROM deposit_actions o "
            "LEFT JOIN deposit_actions c ON o.action_type=:opening AND c.action_type=:closing and o.deposit_id=c.deposit_id "
            "WHERE o.timestamp<=:timestamp AND c.timestamp>=:timestamp",
            [(":timestamp", timestamp), (":opening", DepositActions.Opening), (":closing", DepositActions.Closing)])
        while query.next():
            deposits.append(JalDeposit(super(JalDeposit, JalDeposit)._read_record(query, cast=[int])))
        return deposits

    # returns name of the deposit as it was given in notes
    def name(self) -> str:
        return self._note

    # Returns currency of the deposit
    def currency(self) -> JalAsset:
        return self._currency

    # Return accumulated money for the deposit at given timestamp
    def balance(self, timestamp: int) -> Decimal:
        balance = Decimal('0')
        query = self._exec("SELECT amount FROM ledger "
                           "WHERE book_account=:book AND otype=:type AND oid=:id AND timestamp<=:timestamp",
                           [(":book", BookAccount.Savings), (":type", LedgerTransaction.TermDeposit),
                            (":id", self._id), (":timestamp", timestamp)])
        while query.next():
            balance += self._read_record(query, cast=[Decimal])
        return balance

    # Return a timestamp of deposit opening
    def start_date(self) -> int:
        opening = [x for x in self._actions if x['action_type']==DepositActions.Opening]
        assert len(opening) == 1
        return opening[0]['timestamp']

    # Return a timestamp of deposit closure
    def end_date(self) -> int:
        opening = [x for x in self._actions if x['action_type'] == DepositActions.Closing]
        assert len(opening) == 1
        return opening[0]['timestamp']

    def open_amount(self) -> Decimal:
        opening = [x for x in self._actions if x['action_type'] == DepositActions.Opening]
        assert len(opening) == 1
        return opening[0]['amount']

    def accrued_interest(self, timestamp) -> Decimal:
        amount = Decimal('0')
        interests = [x for x in self._actions if x['timestamp'] <= timestamp]
        for interest in interests:
            if interest['action_type'] == DepositActions.InterestAccrued:
                amount += interest['amount']
            elif interest['action_type'] == DepositActions.TaxWithheld:
                amount += interest['amount']
            else:
                continue
        return amount

    def close_amount(self) -> Decimal:
        amount = self.open_amount()
        for action in self._actions:
            if action['action_type'] in [DepositActions.TopUp, DepositActions.InterestAccrued]:
                amount += action['amount']
            elif action['action_type'] in [DepositActions.PartialWithdrawal, DepositActions.TaxWithheld]:
                amount -= action['amount']
            elif action['action_type'] in [DepositActions.Opening, DepositActions.Closing, DepositActions.Renewal]:
                continue
            else:
                logging.warning(self.tr("Unexpected deposit action: ") + action['action_type'])
        return amount
