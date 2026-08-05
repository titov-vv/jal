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

    # ------------------------------------------------------------------------------------------------------------------
    # How much MORE the chain holds of (account, asset) than the books do, as {'delta', 'measured'} - the quantity a
    # report has to add to the ledger one, and the moment it was measured (0 when nothing was ever measured).
    #
    # This is the single place the display rule is stated, because it is used by the Balances tree, the Asset
    # Portfolio and the Staked positions report, and the three must never disagree about what a position holds.
    #
    # Three things it refuses to do, each of which would be wrong in a way that is invisible on screen:
    #
    #  * it never applies a measurement to a report dated BEFORE it. A snapshot is a "now" value; letting today's
    #    reading into a report of last January would silently rewrite history with a quantity that did not exist
    #    then. latest() enforces this by asking for the newest reading as of the report date.
    #  * it never returns a NEGATIVE delta. A chain holding LESS than the books is not a correction to display - it
    #    means an outgoing movement was missed, or a stake was slashed, and it is a signal for reconciliation to
    #    raise. Subtracting it here would quietly hide the very discrepancy that matters, so the display falls back
    #    to the ledger and lets the books be seen for what they say.
    #  * it is suppressed entirely while a PENDING LEG exists for the position (see _has_pending_leg).
    def accrual(self, account_id: int, asset_id: int, ledger_amount: Decimal, timestamp: int) -> dict:
        snapshot = self.latest(account_id, asset_id, timestamp)
        if snapshot is None:
            return {'delta': Decimal('0'), 'measured': 0}
        delta = snapshot['amount'] - ledger_amount
        if delta <= Decimal('0') or self._has_pending_leg(account_id, asset_id, timestamp):
            return {'delta': Decimal('0'), 'measured': snapshot['timestamp']}
        return {'delta': delta, 'measured': snapshot['timestamp']}

    # True while a movement of this asset has been imported but not yet ASSIGNED to both of its ends.
    #
    # A fetcher leaves the far end of a custody transfer NULL until the user picks the account it went to, and until
    # then the coins are in neither place: they have left the wallet and have not arrived in the container. The chain
    # has them, the ledger has not, so the whole pending quantity is indistinguishable from accrual and shows up as
    # unrealized PROFIT. Measured on the real account: a 5.12751902 HYPE staking deposit displayed ~$160 of phantom
    # gain on a box whose true accrual was 0.0711 HYPE - a wrong number that scales with the DEPOSIT rather than with
    # the yield, and that looks entirely plausible on screen.
    #
    # It is transient and heals itself the moment the leg is assigned, which is why the delta is SUPPRESSED rather
    # than the snapshot being skipped: skipping the snapshot would leave the previous, smaller one in place and go on
    # comparing it against a ledger that has moved.
    #
    # The accounts that matter are this one and - when it is a staking box - the wallets that fill it, because the
    # unassigned leg of a stake sits on the WALLET while the quantity it is missing is the box's.
    def _has_pending_leg(self, account_id: int, asset_id: int, timestamp: int) -> bool:
        import jal.db.staking
        accounts = {account_id} | {x.id() for x in jal.db.staking.JalStakingBox(account_id).source_accounts()}
        placeholders = ', '.join(str(int(x)) for x in accounts)
        count = self._read(
            "SELECT COUNT(*) FROM transfers t JOIN asset_symbol s ON s.id=t.symbol_id "
            "WHERE (t.withdrawal_account IS NULL OR t.deposit_account IS NULL) AND s.asset_id=:asset_id "
            f"AND (t.withdrawal_account IN ({placeholders}) OR t.deposit_account IN ({placeholders})) "
            "AND (CASE WHEN t.deposit_account IS NULL THEN t.withdrawal_timestamp ELSE t.deposit_timestamp END)<=:timestamp",
            [(":asset_id", asset_id), (":timestamp", timestamp)])
        return bool(int(count)) if count else False

    # The yield history of a position, as [{'timestamp', 'chain', 'ledger', 'accrued'}] oldest first.
    #
    # This is what the append-only table buys, and it costs nothing extra: every refresh already leaves a row behind,
    # so the series exists whether or not anyone ever draws it. There is no API anywhere that would give it instead -
    # a balance is only ever available for NOW - which is why it can only be accumulated going forward.
    #
    # 'accrued' is each measurement against the books AS THEY STOOD at that moment, not as they stand today: a
    # deposit or a withdrawal since then moved the ledger, and comparing an old reading against today's quantity
    # would draw a step that never happened. It is floored at zero on the same grounds the display rule uses - a
    # chain reading below the books is a signal for reconciliation, never a negative yield.
    #
    # The series is LUMPY by nature, and that is honest rather than a defect: a point exists where a refresh
    # happened, so the shape of the line says as much about how often quotes were updated as about the yield.
    #
    # One shape to expect and NOT to smooth away: a measurement taken while a custody leg was still unassigned shows
    # the whole un-arrived deposit as accrual, and stays showing it after the leg is settled, because what was
    # measured then really was that far apart. The display suppresses that case live (see accrual()), but here it is
    # history and inventing a retroactive gate would hide a real reading. The chart shows both quantities behind
    # every point for exactly this reason - a spike with the books far below the chain reads as what it is.
    def accrual_history(self, account_id: int, asset_id: int) -> list:
        import jal.db.account
        account = jal.db.account.JalAccount(account_id)
        series = []
        for point in self.history(account_id, asset_id):
            ledger = account.get_asset_amount(point['timestamp'], asset_id)
            accrued = point['amount'] - ledger
            series.append({'timestamp': point['timestamp'], 'chain': point['amount'], 'ledger': ledger,
                           'accrued': accrued if accrued > Decimal('0') else Decimal('0')})
        return series

    # Forgets the measurements of a position that is gone from both the chain and the books.
    #
    # Deletion is deliberately NOT eager: the stored delta is what the realization rule uses as its guard when a
    # withdrawal digs into the accrual, so it has to outlive the position long enough to be asked. A row is dropped
    # only once there is nothing left for it to describe.
    def forget(self, account_id: int, asset_id: int) -> None:
        self._exec("DELETE FROM chain_balances WHERE account_id=:account_id AND asset_id=:asset_id",
                   [(":account_id", account_id), (":asset_id", asset_id)], commit=True)
