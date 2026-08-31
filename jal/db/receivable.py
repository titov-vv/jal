from decimal import Decimal, DecimalException

from jal.db.db import JalDB


# ----------------------------------------------------------------------------------------------------------------------
# Access to 'receivables' - what a distributor owes an account and hasn't paid yet.
#
# It is valuation data and not an operation, exactly as a chain balance is (see the schema comment in jal_init.sql).
# What makes it a table of its own rather than another kind of chain balance is that a receivable is denominated in
# an asset the account holds NONE of - so there is no ledger quantity to compare it against - and that it is keyed by
# the SOURCE that owes it, because several distributors pay the same token to the same wallet.
#
# Only one of JalChainBalance.accrual()'s three display rules carries over, and it is the important one: a reading is
# never handed to a report dated BEFORE it was taken (latest() enforces it). The other two do not apply here - there
# is no ledger amount for the figure to be negative against, and a pending transfer leg says nothing about a claim
# whose asset has never moved anywhere.
#
# Nothing here writes to the ledger and nothing here is read by the ledger rebuild. The claim itself is booked when
# it happens, as a StakingReward payment at market value; what is stored here is what remains UNCLAIMED, which the
# chain reports directly, so the two can never count the same reward twice.
class JalReceivable(JalDB):
    def __init__(self):
        super().__init__()

    # Records what one 'source' owes an account in one asset at 'timestamp'.
    #
    # Appended to rather than updated, like 'chain_balances' and 'quotes': the series of readings is the claim
    # history for the price of one row per refresh, and two readings within the same second replace rather than
    # duplicate. Both amounts are stored as text because SQLite has no decimal type and a reward that passed through
    # a float would come back wrong in its last digits.
    def store(self, timestamp: int, account_id: int, asset_id: int, source: str,
              amount: Decimal, pending: Decimal = Decimal('0')) -> None:
        self._exec("INSERT OR REPLACE INTO receivables(timestamp, account_id, asset_id, source, amount, pending) "
                   "VALUES(:timestamp, :account_id, :asset_id, :source, :amount, :pending)",
                   [(":timestamp", int(timestamp)), (":account_id", account_id), (":asset_id", asset_id),
                    (":source", source), (":amount", str(amount)), (":pending", str(pending))], commit=True)

    # The most recent reading of (account, asset, source) that is not newer than 'timestamp', as
    # {'timestamp', 'amount', 'pending'}, or None when this claim was never read.
    #
    # 'timestamp' is not decoration and callers must pass the date of the report they are drawing: a claim is a "now"
    # value, and letting today's reading into a report dated last January would show a reward that did not exist then.
    def latest(self, account_id: int, asset_id: int, source: str, timestamp: int) -> dict:
        record = self._read("SELECT timestamp, amount, pending FROM receivables "
                            "WHERE account_id=:account_id AND asset_id=:asset_id AND source=:source "
                            "AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                            [(":account_id", account_id), (":asset_id", asset_id), (":source", source),
                             (":timestamp", timestamp)], named=True)
        if not record:
            return None
        try:
            return {'timestamp': int(record['timestamp']), 'amount': Decimal(record['amount']),
                    'pending': Decimal(record['pending'])}
        except (DecimalException, ValueError, TypeError):
            # A row nobody can read is not a reason to stop a report. Answering "never read" makes the caller behave
            # as it does for every claim that has no row at all - i.e. add nothing.
            return None

    # Every (asset_id, source) pair ever recorded for an account, whatever it currently says.
    #
    # This is what lets a reader keep its table honest: a claim that has vanished from the source it came from has to
    # be written down as zero, and to do that the reader has to be told what it used to know about.
    def known_claims(self, account_id: int) -> list:
        claims = []
        query = self._exec("SELECT DISTINCT asset_id, source FROM receivables WHERE account_id=:account_id",
                           [(":account_id", account_id)])
        while query.next():
            asset_id, source = self._read_record(query, cast=[int, str])
            claims.append((asset_id, source))
        return claims

    # What is owed to an account at 'timestamp', as [{'asset_id', 'source', 'amount', 'pending', 'timestamp'}].
    #
    # A claim that currently reads zero is left out rather than listed as nothing: it has been claimed, or the
    # campaign that paid it has ended, and either way there is no receivable to show. The zero row itself is kept in
    # the table - it is a measurement, and it is what stops a stale figure from lingering on screen.
    #
    # This is the single place the display rule is stated, because both the Balances tree and the Staked positions
    # report read it and the two must never disagree about what is owed.
    def claims(self, account_id: int, timestamp: int) -> list:
        owed = []
        for asset_id, source in self.known_claims(account_id):
            record = self.latest(account_id, asset_id, source, timestamp)
            if record is None or record['amount'] <= Decimal('0'):
                continue
            owed.append({'asset_id': asset_id, 'source': source, 'amount': record['amount'],
                         'pending': record['pending'], 'timestamp': record['timestamp']})
        return owed

    # Every account that is owed something at 'timestamp', so a report doesn't have to walk them all.
    def accounts_with_claims(self, timestamp: int) -> list:
        accounts = self._read_to_list(
            "SELECT DISTINCT account_id FROM receivables WHERE timestamp<=:timestamp", [(":timestamp", timestamp)])
        return [x for x in [int(account_id) for account_id in accounts] if self.claims(x, timestamp)]

    # What is owed to an account, valued in 'currency_id'. Only the CLAIMABLE part is valued: 'pending' is accruing
    # inside an epoch that has published no root, so no proof backs it and it cannot be turned into anything today.
    def value(self, account_id: int, timestamp: int, currency_id: int) -> Decimal:
        import jal.db.asset
        total = Decimal('0')
        for claim in self.claims(account_id, timestamp):
            total += claim['amount'] * jal.db.asset.JalAsset(claim['asset_id']).quote(timestamp, currency_id)[1]
        return total

    # The history of one claim, as [{'timestamp', 'accrued', 'pending'}] oldest first - what the claim chart draws.
    #
    # It costs nothing extra: every refresh already leaves a row behind, so the series exists whether or not anyone
    # opens it, and there is no API anywhere that would give it instead - what is owed is only ever available for NOW.
    # The claimable amount is named 'accrued' because that is the key the chart plots, and because it is the same
    # thing the accrual chart draws: value earned and not yet received. Unreadable rows are skipped rather than
    # breaking the series.
    def claim_history(self, account_id: int, asset_id: int, source: str) -> list:
        records = []
        query = self._exec("SELECT timestamp, amount, pending FROM receivables "
                           "WHERE account_id=:account_id AND asset_id=:asset_id AND source=:source ORDER BY timestamp",
                           [(":account_id", account_id), (":asset_id", asset_id), (":source", source)])
        while query.next():
            timestamp, amount, pending = self._read_record(query)
            try:
                records.append({'timestamp': int(timestamp), 'accrued': Decimal(amount), 'pending': Decimal(pending)})
            except (DecimalException, ValueError, TypeError):
                continue
        return records

    # Forgets a claim entirely. Writing a zero is what a reader does when a source stops paying - the row stays as
    # the measurement that says so. This is for the case where there is nothing left to describe at all.
    def forget(self, account_id: int, asset_id: int, source: str) -> None:
        self._exec("DELETE FROM receivables WHERE account_id=:account_id AND asset_id=:asset_id AND source=:source",
                   [(":account_id", account_id), (":asset_id", asset_id), (":source", source)], commit=True)
