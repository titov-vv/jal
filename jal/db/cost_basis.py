from decimal import Decimal
from jal.db.asset import JalAsset
from jal.db.db import JalDB


# A rate found this long before the moment it is asked about is no longer a statement about that moment. Currency
# rates are published every business day, so a wider gap means the series ended before the date (or never covered
# it) - and JalAsset.quote() returns the newest row at or before the date without complaint, so a rate years out of
# date looks exactly like a fresh one unless its own timestamp is looked at.
STALE_RATE_LIMIT = 7 * 24 * 60 * 60


# When the moment a rate is really from is not the moment JalAsset.quote() reports it from.
#
# quote() answers a pair it holds no rate for by dividing the two rates of its halves against the base currency - and
# it dates that answer to the moment it was ASKED ABOUT, because it computed it just now. But a rate built out of a
# series that ended years ago is exactly as old as that series, and reported this way it is indistinguishable from
# one published the same day.
#
# What this costs when it goes unnoticed, measured on real data: a transfer of 490 USDT out of a RUB account in May
# 2025 was offered a RUB->USD rate of 0.00967, dated to the day of the transfer and looking perfectly current. It had
# been made from a RUB/EUR rate of March 2022 - the last one the ECB published - and valued the 490 USDT at 388 USD,
# a fifth below what they were worth. Dated honestly, the same rate is three years old, is shown as such, and is not
# offered as a default at all.
#
# So a rate the database does not hold for the pair, and that the base currency stands between, is dated by the OLDER
# of the two rates it was made of. A rate that IS stored is dated by its own row, whatever it was asked about.
def _rate_age(currency: int, target_currency: int, timestamp: int, rate_timestamp: int) -> int:
    if currency == target_currency:
        return rate_timestamp                      # one currency at both ends involves no rate to be old
    stored = _stored_rate_age(currency, target_currency, timestamp)
    if stored:
        return stored                              # a rate the database holds, dated by its own row
    base = JalAsset.get_base_currency(timestamp)
    if not base:
        return rate_timestamp
    # What is left was divided out of the rates against the base currency. A side that IS the base contributes a
    # rate of one, which is never out of date and is not what dates the answer - the other side is. (This matters
    # for the commonest pair of all: with EUR as the base currency, EUR -> USD is 1 divided by the stored USD/EUR
    # rate, so the whole age of the answer sits in a half that isn't looked at unless it is looked for here.)
    halves = [JalAsset(x).quote(timestamp, base)[0] for x in (currency, target_currency) if x != base]
    return min(halves) if all(halves) else 0


# The moment of the newest rate the database holds FOR THIS PAIR at or before 'timestamp', 0 when it holds none.
# This is the row JalAsset.quote() would find, looked up the same way it looks it up, and asked here only to tell a
# rate that was read from a rate that was computed - which is what the answer above turns on.
def _stored_rate_age(currency: int, target_currency: int, timestamp: int) -> int:
    stored = JalDB._read("SELECT timestamp FROM quotes WHERE asset_id=:asset_id AND currency_id=:currency_id "
                         "AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                         [(":asset_id", currency), (":currency_id", target_currency), (":timestamp", timestamp)])
    return int(stored) if stored else 0


# ----------------------------------------------------------------------------------------------------------------------
# What 'qty' of 'asset' cost the account that holds it, and what that cost amounts to in 'target_currency'.
#
# This is the read-only twin of LedgerTransaction._close_deals_fifo(): it takes the same open lots, in the same FIFO
# order, from the same 'trades_opened' table - but writes nothing, closes no deal and moves no quantity. It answers
# what an operation WOULD consume if it were recorded at 'timestamp', which is what lets a cost basis be shown, and
# corrected, before anything is committed.
#
# It is exact rather than an estimate, as long as the ledger is built past 'timestamp': open_trades_list() rebuilds
# the lots as they stood at that moment, which is the state the rebuild will meet when it reaches the operation.
#
# Everything it returns is a statement about what is already recorded, and nothing here is stored anywhere - the
# caller decides what to write, and the user may overrule the number entirely (which is the point of showing it).
# Nothing is refused either: a missing rate and lots too small to cover the quantity are reported, not corrected,
# because both are things only the user can settle.
#
# Returns a dict of:
#   'qty'            quantity the open lots could cover - less than asked when the account doesn't hold enough
#   'short'          quantity they could NOT cover; non-zero means recording the operation would break the ledger
#   'lots'           how many lots the quantity was taken from
#   'basis'          what that quantity cost, in the currency of 'account'
#   'currency'       the currency 'basis' is measured in (the account's own)
#   'rate'           'currency' -> 'target_currency' as of 'timestamp' (0 when there is no rate at all)
#   'rate_timestamp' the moment that rate was published (0 when there is none) - how old the answer really is
#   'stale'          the rate is older than STALE_RATE_LIMIT, so it doesn't describe the day it was asked about
#   'value'          'basis' converted into 'target_currency'
#   'complete'       every part of the answer is present and current, so it may be offered as a default
def carried_basis(account, asset, qty: Decimal, timestamp: int, target_currency: int) -> dict:
    matched = Decimal('0')
    basis = Decimal('0')
    lots = 0
    if qty > Decimal('0'):
        for trade in account.open_trades_list(asset, timestamp):
            available = trade.open_qty()
            taken = available if available < (qty - matched) else (qty - matched)
            matched += taken
            basis += taken * trade.open_price(adjusted=True)
            lots += 1
            if matched >= qty:
                break
    currency = account.currency()
    rate_timestamp, rate = JalAsset(currency).quote(timestamp, target_currency)
    rate_timestamp = _rate_age(currency, target_currency, timestamp, rate_timestamp)
    # A rate of zero is not a rate. JalAsset.quote() reports "nothing found" in two different shapes: (0, 0) when it
    # found no quote at all, and (the moment asked about, 0) when it tried to build a cross-rate through the base
    # currency and one of its two halves was missing. The second one carries a timestamp that looks perfectly
    # current, so without this both the staleness and the completeness of the answer would be decided on a rate that
    # doesn't exist - and a value of zero would be offered as if it had been computed.
    if not rate:
        rate_timestamp = 0
    stale = bool(rate_timestamp) and (timestamp - rate_timestamp) > STALE_RATE_LIMIT
    return {
        'qty': matched,
        'short': qty - matched,
        'lots': lots,
        'basis': basis,
        'currency': currency,
        'rate': rate,
        'rate_timestamp': rate_timestamp,
        'stale': stale,
        'value': basis * rate,
        'complete': matched >= qty and bool(rate_timestamp) and not stale
    }
