from decimal import Decimal, DecimalException

from jal.db.db import JalDB


# ----------------------------------------------------------------------------------------------------------------------
# Access to 'chain_balances' - the balance an account REALLY holds of an asset, as the chain itself reports it.
#
# It is valuation data and not an operation, and the distinction is the whole point of the table (see the schema
# comment in jal_init.sql). Two things make a chain balance drift away from the sum of the movements JAL imported:
# a rebasing receipt token grows through a protocol index that emits nothing, and a staking box accrues yield inside
# the container. Neither is an event a fetcher could have booked, both are unrealized gains, and JAL's convention
# for unrealized value is a quote rather than an operation.
#
# Nothing here writes to the ledger, and nothing here is read by the ledger rebuild. A row is a measurement with a
# date on it, exactly like a quote, and the reports decide what to make of it.
class JalChainBalance(JalDB):
    def __init__(self):
        super().__init__()

    # Records what the chain reports for one (account, asset) at 'timestamp'.
    #
    # The table is APPENDED to rather than updated: the series of measurements is the per-position yield history the
    # growth chart needs, for the price of one row per refresh. Two refreshes within the same second replace instead
    # of duplicating - the unique key is (account, asset, timestamp), the same shape 'quotes' uses, and a second
    # reading of the same second says nothing the first one didn't.
    #
    # The amount is stored as text, like every other quantity in the database: SQLite has no decimal type and a
    # balance that passed through a float would come back wrong in its last digits - which is precisely the range
    # this whole feature measures.
    def store(self, timestamp: int, account_id: int, asset_id: int, amount: Decimal) -> None:
        self._exec("INSERT OR REPLACE INTO chain_balances(timestamp, account_id, asset_id, amount) "
                   "VALUES(:timestamp, :account_id, :asset_id, :amount)",
                   [(":timestamp", int(timestamp)), (":account_id", account_id), (":asset_id", asset_id),
                    (":amount", str(amount))], commit=True)

    # The most recent measurement for (account, asset) that is not newer than 'timestamp', as
    # {'timestamp', 'amount'}, or None when the chain was never read for it.
    #
    # 'timestamp' is not decoration and callers must pass the date of the report they are drawing: a snapshot is a
    # "now" value, and letting today's reading into a report dated last January would rewrite history with a
    # quantity that did not exist then. Asking for the latest reading AS OF a date is what keeps that impossible.
    def latest(self, account_id: int, asset_id: int, timestamp: int) -> dict:
        record = self._read("SELECT timestamp, amount FROM chain_balances "
                            "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                            "ORDER BY timestamp DESC LIMIT 1",
                            [(":account_id", account_id), (":asset_id", asset_id), (":timestamp", timestamp)],
                            named=True)
        if not record:
            return None
        try:
            return {'timestamp': int(record['timestamp']), 'amount': Decimal(record['amount'])}
        except (DecimalException, ValueError, TypeError):
            # A row nobody can read is not a reason to stop a report. Answering "never measured" makes the caller
            # fall back to the ledger quantity, which is the same thing it does for every asset that has no row at
            # all - i.e. the reading that adds nothing to a position.
            return None

    # Every measurement for (account, asset), oldest first, as [{'timestamp', 'amount'}]. This is the yield history
    # the growth chart draws; unreadable rows are left out rather than breaking the series.
    def history(self, account_id: int, asset_id: int) -> list:
        records = []
        query = self._exec("SELECT timestamp, amount FROM chain_balances "
                           "WHERE account_id=:account_id AND asset_id=:asset_id ORDER BY timestamp",
                           [(":account_id", account_id), (":asset_id", asset_id)])
        while query.next():
            timestamp, amount = self._read_record(query)
            try:
                records.append({'timestamp': int(timestamp), 'amount': Decimal(amount)})
            except (DecimalException, ValueError, TypeError):
                continue
        return records

    # Forgets the measurements of a position that is gone from both the chain and the books.
    #
    # Deletion is deliberately NOT eager: the stored delta is what the realization rule uses as its guard when a
    # withdrawal digs into the accrual, so it has to outlive the position long enough to be asked. A row is dropped
    # only once there is nothing left for it to describe.
    def forget(self, account_id: int, asset_id: int) -> None:
        self._exec("DELETE FROM chain_balances WHERE account_id=:account_id AND asset_id=:asset_id",
                   [(":account_id", account_id), (":asset_id", asset_id)], commit=True)
