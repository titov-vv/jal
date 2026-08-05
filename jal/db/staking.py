from decimal import Decimal
from jal.constants import BookAccount, PredefinedAccountType, AccountData, AssetLocation
from jal.db.db import JalDB
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset


# ----------------------------------------------------------------------------------------------------------------------
# A staking box is an account of the hidden PredefinedAccountType.Staking type - the container an asset was staked
# into, kept as an account of its own. It is the deposit box (see jal/db/deposit.py, CRYPTO_PATH decisions #49-#51)
# applied to the case the custody classification produces: a validator's stake account, a venue's staking balance or
# a protocol contract that issues no receipt token holds coins that are still the user's, so what moved is a transfer
# and the box is the end it moved to.
#
# It differs from a term deposit in what it holds and in where its yield appears:
#   * a deposit holds MONEY in the account's own currency; a box holds ASSETS, and its currency only says what its
#     value is measured in, so every figure here is per asset;
#   * a deposit's interest is booked INSIDE the box as an income operation; staking yield reaches the WALLET as a
#     StakingReward payment (the fetchers split it off a withdrawal, or a claim pays it out on its own), so a box
#     never sees it and nothing here reports "what this box earned" - a wallet may stake into several containers and
#     nothing records which of them a reward came from, so a figure here would be a guess rather than a gap.
#
# Like a deposit box it is never created by hand, is filtered out of every account picker (AccountListModel) and is
# deactivated once it is emptied, so unstaked positions don't pile up in the application.
class JalStakingBox(JalDB):
    def __init__(self, account_id: int = 0):
        super().__init__()
        self._account = JalAccount(account_id)
        self._id = self._account.id()

    @classmethod
    # Creates a new staking box for the asset held by 'source' - the account it is staked FROM - and returns it.
    # 'name' has to be unique among all accounts (the box is one).
    #
    # 'address'/'chain' are the container's own on-chain identity and are what makes a box settle its legs without
    # being asked: JalAccount.at_address() resolves a pending leg's counterparty address to the box, so both the
    # Settle pass and the next fetch complete the movement on their own. They stay empty for a container that has no
    # address at all - a centralized venue's staking balance is internal to the venue and names nothing on a chain.
    def create(cls, source: JalAccount, name: str, protocol: str = '',
               chain: int = AssetLocation.UNDEFINED, address: str = '') -> "JalStakingBox":
        # Currency and PRECISION are taken from the account the asset comes from, and neither is cosmetic. The
        # ledger rounds every amount it books to the precision of the account it books it on (Ledger.
        # appendTransaction), so a box left at the default of 2 decimals turns 15.10216183332242345 staked LINK into
        # 15.10 - and the unstaking of what was really put in then asks the box for more than it holds and stops the
        # ledger rebuild dead. The currency does the same job for the cost basis: an asset moving between two
        # currencies needs its basis restated, and nothing about a stake could state it.
        #
        # Created through JalAccountCreator rather than by an INSERT of its own (which is what a deposit box does):
        # the address has to be validated and normalized before it is stored, or a lookup by the very same address
        # would fail to find the box back.
        creator = JalAccountCreator(currency_id=source.currency(), number='', name=name, investing=1,
                                    precision=source.precision(), account_type=PredefinedAccountType.Staking,
                                    address=address, chain=chain)
        box = cls(creator.id())
        box.set_protocol(protocol)
        return box

    @classmethod
    # Returns the boxes that held something at 'timestamp': created before it and not yet emptied at that moment.
    # A box that still holds an asset is returned even if it is deactivated, so a closing that hasn't been recorded
    # yet can't make a staked position disappear from the report.
    def get_boxes(cls, timestamp: int) -> list:
        boxes = []
        query = cls._exec("SELECT id FROM accounts WHERE account_type=:type",
                          [(":type", PredefinedAccountType.Staking)])
        while query.next():
            box = cls(cls._read_record(query, cast=[int]))
            if box.opened_at() and box.opened_at() <= timestamp and box.holdings(timestamp):
                boxes.append(box)
        return boxes

    @classmethod
    # Every staking box that exists, open or not, oldest first - what a chooser offers when a leg has to be assigned
    # to one. Unlike get_boxes() an empty box is included: a box is emptied by unstaking and re-used by staking
    # again, and the second stake has to find the box the first one created.
    def all_boxes(cls) -> list:
        boxes = []
        query = cls._exec("SELECT id FROM accounts WHERE account_type=:type ORDER BY id",
                          [(":type", PredefinedAccountType.Staking)])
        while query.next():
            boxes.append(cls(cls._read_record(query, cast=[int])))
        return boxes

    def id(self) -> int:
        return self._id

    def account(self) -> JalAccount:
        return self._account

    def name(self) -> str:
        return self._account.name()

    # The currency the box's value is measured in. It holds no money, so this is not what it contains - only the
    # currency its assets are valued in, and it matches the wallet the asset comes from (see create()).
    def currency(self) -> JalAsset:
        return JalAsset(self._account.currency())

    # The protocol or venue holding the asset, as a human calls it ('' when it wasn't stated)
    def protocol(self) -> str:
        return self._account.get_data(AccountData.StakeProtocol) or ''

    def set_protocol(self, protocol: str) -> None:
        self._account.set_data(AccountData.StakeProtocol, protocol if protocol else None)

    # On-chain address of the container ('' when it has none - a venue's internal staking balance)
    def address(self) -> str:
        return self._account.address()

    def chain(self) -> int:
        return self._account.chain()

    def is_active(self) -> bool:
        return self._account.is_active()

    # The accounts this box was ever filled FROM, i.e. the wallets it belongs to.
    #
    # No column records the relation, and none needs to: a box is created from a source account and every fill is a
    # transfer, so the transfers themselves say it. That matters most for a box that has no address of its own - a
    # venue's internal staking balance names nothing on a chain, so the wallet found here is the only thing that says
    # which address its balance may be read at.
    #
    # A container box normally answers with exactly one account; the list is not narrowed to one here because a
    # caller that CARES whether there is more than one has to be able to see that for itself.
    def source_accounts(self) -> list:
        accounts = self._read_to_list(
            "SELECT DISTINCT withdrawal_account FROM transfers "
            "WHERE deposit_account=:box AND NOT withdrawal_account IS NULL", [(":box", self._id)])
        return [JalAccount(int(x)) for x in accounts]

    # Timestamp of the first transfer that put an asset into the box, i.e. when staking started (0 if empty)
    def opened_at(self) -> int:
        timestamp = self._read("SELECT MIN(deposit_timestamp) FROM transfers WHERE deposit_account=:id",
                               [(":id", self._id)])
        return int(timestamp) if timestamp else 0

    # What the box holds at the given moment, as [{'asset', 'amount', 'value'}]. Usually one asset - a container
    # stakes one coin - but nothing forbids a protocol that took two, so it is a list and not a single figure.
    def holdings(self, timestamp: int) -> list:
        return self._account.assets_list(timestamp)

    # Value of everything the box holds at the given moment, in the currency asked for
    def value(self, timestamp: int, currency_id: int = 0) -> Decimal:
        currency_id = currency_id if currency_id else self._account.currency()
        value = Decimal('0')
        for holding in self.holdings(timestamp):
            value += holding['amount'] * holding['asset'].quote(timestamp, currency_id)[1]
        return value

    # Everything that happened to the box up to 'timestamp', oldest first, as a list of
    # {"timestamp", "asset", "amount", "balance", "operation"} where 'amount' is signed the way the box sees it and
    # 'balance' is the running quantity of THAT asset (a box holding two assets has two independent balances).
    def details(self, timestamp: int) -> list:
        records = []
        query = self._exec("SELECT timestamp, asset_id, amount, otype, oid FROM ledger "
                           "WHERE account_id=:id AND book_account=:assets AND timestamp<=:timestamp ORDER BY id",
                           [(":id", self._id), (":assets", BookAccount.Assets), (":timestamp", timestamp)])
        balances = {}
        while query.next():
            record = self._read_record(query, named=True, cast=[int, int, Decimal, int, int])
            asset_id = record['asset_id']
            balances[asset_id] = balances.get(asset_id, Decimal('0')) + record['amount']
            record['asset'] = JalAsset(asset_id)
            record['balance'] = balances[asset_id]
            records.append(record)
        return records

    # Closes an emptied box: it stops being active, so it disappears from every default view and from the list of
    # staked positions, while everything it recorded stays in place.
    def close(self) -> None:
        self._account.set_active(False)
