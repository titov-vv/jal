from decimal import Decimal
from jal.constants import BookAccount, PredefinedAccountType, PredefinedCategory, AccountData
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset


# A term deposit is an account of the hidden PredefinedAccountType.Deposit type - a "box" the bank keeps the money in
# for a term (CRYPTO_PATH decision #49). Money is put in and taken out with ordinary transfers and the interest is an
# ordinary income operation, so there is no deposit-specific operation and nothing here touches the ledger: this class
# only reads a box's figures back and creates/closes boxes for the Deposits window.
#
# The word "account" never surfaces in that window - a deposit box is not created by hand, is filtered out of every
# account picker (see AccountListModel) and is deactivated as soon as it is emptied, so the list of past deposits
# never clutters the application the way an account per deposit did before.
class JalDepositBox(JalDB):
    def __init__(self, account_id: int = 0):
        super().__init__()
        self._account = JalAccount(account_id)
        self._id = self._account.id()

    @classmethod
    # Creates a new deposit box and returns it. 'name' has to be unique among all accounts (the box is one).
    def create(cls, name: str, currency_id: int, organization_id: int,
               end_date: int = 0, rate: Decimal = Decimal('0')) -> "JalDepositBox":
        query = cls._exec("INSERT INTO accounts (name, currency_id, active, investing, reconciled_on, "
                          "organization_id, account_type) VALUES(:name, :currency, 1, 0, 0, :organization, :type)",
                          [(":name", name), (":currency", currency_id), (":organization", organization_id),
                           (":type", PredefinedAccountType.Deposit)], commit=True)
        box = cls(query.lastInsertId())
        JalAccount.db_cache.update_data(JalAccount._load_account_data, (box.id(),))
        box.set_terms(end_date, rate)
        return box

    @classmethod
    # Returns the boxes that were open at 'timestamp': created before it and not yet emptied at that moment.
    # A box that still holds money is returned even if it is deactivated, so a closing that hasn't been recorded
    # yet can't make the money disappear from the report.
    def get_deposits(cls, timestamp: int) -> list:
        deposits = []
        query = cls._exec("SELECT id FROM accounts WHERE account_type=:type", [(":type", PredefinedAccountType.Deposit)])
        while query.next():
            box = cls(cls._read_record(query, cast=[int]))
            if box.opened_at() and box.opened_at() <= timestamp and box.balance(timestamp) != Decimal('0'):
                deposits.append(box)
        return deposits

    def id(self) -> int:
        return self._id

    def account(self) -> JalAccount:
        return self._account

    def name(self) -> str:
        return self._account.name()

    def currency(self) -> JalAsset:
        return JalAsset(self._account.currency())

    def organization(self) -> int:
        return self._account.organization()

    def is_active(self) -> bool:
        return self._account.is_active()

    # Planned maturity date of the deposit (0 if it isn't known)
    def end_date(self) -> int:
        return self._account.deposit_end()

    # Nominal interest rate, per cent per annum (0 if it isn't known)
    def rate(self) -> Decimal:
        return self._account.deposit_rate()

    def set_terms(self, end_date: int, rate: Decimal) -> None:
        self._account.set_data(AccountData.DepositEnd, end_date if end_date else None)
        self._account.set_data(AccountData.DepositRate, rate if rate else None)

    # Timestamp of the first operation that put money into the box, i.e. when the deposit started (0 if empty)
    def opened_at(self) -> int:
        timestamp = self._read("SELECT MIN(deposit_timestamp) FROM transfers WHERE deposit_account=:id",
                               [(":id", self._id)])
        return int(timestamp) if timestamp else 0

    # Money accumulated in the box at the given timestamp
    def balance(self, timestamp: int) -> Decimal:
        return self._account.get_asset_amount(timestamp, self._account.currency())

    # Interest credited to the box up to the given timestamp, net of the tax withheld from it
    def accrued_interest(self, timestamp: int) -> Decimal:
        interest = self._account.get_category_turnover(PredefinedCategory.Interest, 0, timestamp)
        taxes = self._account.get_category_turnover(PredefinedCategory.Taxes, 0, timestamp)
        # 'ledger' books an income as a negative amount in the Incomes book and a cost as a positive one in Costs,
        # so both turnovers have to be negated to read as "how much the deposit earned" and "how much was withheld".
        return -interest - taxes

    # Everything that happened to the box up to 'timestamp', oldest first, as a list of
    # {"timestamp", "amount", "balance", "operation"} where 'amount' is signed the way the box sees it.
    def details(self, timestamp: int) -> list:
        records = []
        query = self._exec("SELECT timestamp, amount, otype, oid FROM ledger "
                           "WHERE account_id=:id AND book_account=:money AND timestamp<=:timestamp ORDER BY id",
                           [(":id", self._id), (":money", BookAccount.Money), (":timestamp", timestamp)])
        balance = Decimal('0')
        while query.next():
            record = self._read_record(query, named=True, cast=[int, Decimal, int, int])
            balance += record['amount']
            record['balance'] = balance
            records.append(record)
        return records

    # Closes an emptied box: it stops being active, so it disappears from every default view and from the list of
    # deposits, while everything it recorded stays in place.
    def close(self) -> None:
        self._account.set_active(False)
