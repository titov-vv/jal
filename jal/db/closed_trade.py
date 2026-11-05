from decimal import Decimal
from jal.db.db import JalDB
from jal.db.helpers import is_day_marker
import jal.db.account
import jal.db.operations
import jal.db.lots
from jal.db.asset import JalAsset


# ----------------------------------------------------------------------------------------------------------------------
# Splits 'total' over 'lots' in proportion to what each of them holds, giving the LAST lot the remainder instead of
# its own scaled share. A share is a ratio of two arbitrary amounts and is almost never representable, so scaling
# every lot independently leaves the parts summing to something that isn't 'total' - taking the remainder makes them
# sum to it by construction. Used where an operation CHANGES the quantity of a position it carries over (a conversion,
# a corporate action).
def allocate_qty(lots: list, total: Decimal) -> list:
    if not lots:
        return []
    quantities = [x.qty() for x in lots]
    source_total = sum(quantities, Decimal('0'))
    shares = [total * x / source_total for x in quantities[:-1]]
    return shares + [total - sum(shares, Decimal('0'))]


# ----------------------------------------------------------------------------------------------------------------------
# Class that represents open trade and provides some methods equal to JalClosedTrades to make compatible calls
class JalOpenTrade(JalDB):
    def __init__(self, operation, price, qty, adjustments=(Decimal('1'), Decimal('1')), slice_id=None,
                 acquired=None, fx=Decimal('1')) -> None:
        super().__init__()
        self._op = operation
        self._acquired = operation.timestamp() if acquired is None else acquired   # the lot's acquisition date
        self._price = price
        self._qty = qty                    # The EFFECTIVE quantity the lot holds (trades_opened.remaining_qty)
        self._adj_price = adjustments[0]   # Historical adjustments of price and quantity that happened
        self._adj_qty = adjustments[1]     # during holding of this position
        self._fx = fx                      # Rate of every transfer between currencies the lot went through
        self._slice_id = slice_id          # Stable identity of the held slice; None until the slice is stored

    def open_operation(self):
        return self._op

    def acquired(self) -> int:
        return self._acquired

    # Identity of the held slice this trade represents (see trades_opened.slice_id). None means "not yet stored":
    # a freshly opened or carried-over slice that LotEngine stores for the DB to assign a new id to.
    def slice_id(self):
        return self._slice_id

    def open_price(self, adjusted=False) -> Decimal:
        if adjusted:
            return self._price * self._adj_price * self._fx
        else:
            return self._price

    # The quantity the lot holds. It takes no 'adjusted' flag as JalClosedTrade.open_qty() does: a lot stores what it effectively holds.
    def open_qty(self) -> Decimal:
        return self._qty

    # Method to adjust price of open position
    def set_price(self, new_price: Decimal):
        self._price = new_price

    # Method to adjust size of open position
    def set_qty(self, new_qty: Decimal):
        self._qty = new_qty

    def p_adjustment(self) -> Decimal:
        return self._adj_price

    def fx_adjustment(self) -> Decimal:
        return self._fx

    # Relates what the lot holds to the quantity of the operation that opened it (qty = c_qty * original_qty).
    # Reporting only - LotEngine needs it to express a closed deal in original units.
    def q_adjustment(self) -> Decimal:
        return self._adj_qty


# ----------------------------------------------------------------------------------------------------------------------
class JalClosedTrade(JalDB):
    def __init__(self, id: int = 0, store=None) -> None:
        super().__init__()
        self._id = id
        self._store = jal.db.lots.LedgerLotStore() if store is None else store
        self._data = self._store.deal(self._id)
        if self._data:
            self._account = jal.db.account.JalAccount(self._data['account_id'])
            self._asset = JalAsset(self._data['asset_id'])
            self._open_op = jal.db.operations.LedgerTransaction.get_operation(self._data['open_otype'], self._data['open_oid'], jal.db.operations.Transfer.Incoming)
            self._close_op = jal.db.operations.LedgerTransaction.get_operation(self._data['close_otype'], self._data['close_oid'], jal.db.operations.Transfer.Outgoing)
            self._open_price = Decimal(self._data['open_price'])
            self._open_qty = Decimal(self._data['open_qty'])
            self._close_price = Decimal(self._data['close_price'])
            self._qty = Decimal(self._data['close_qty'])
            self._adj_price = Decimal(self._data['c_price'])
            self._adj_qty = Decimal(self._data['c_qty'])
            self._fx = Decimal(self._data['c_fx'])
            self._acquired = self._data['open_timestamp']
        else:
            self._account = self._asset = self._open_op = self._close_op = None
            self._open_price = self._open_qty = self._close_price = self._qty = Decimal('0')
            self._adj_price = self._adj_qty = self._fx = Decimal('1')
            self._acquired = 0

    def dump(self) -> list:
        return [
            self._asset.symbol(self._account.currency()),
            self._open_op.timestamp(),
            self._close_op.timestamp(),
            self._open_price,
            self._close_price,
            self._qty,
            self.fee(),
            self.profit(),
            self.profit(percent=True)
        ]

    def id(self) -> int:
        return self._id

    def asset(self) -> JalAsset:
        return self._asset

    def symbol(self) -> str:
        return self._asset.symbol(self._account.currency())

    def open_operation(self):
        return self._open_op

    # A closed trade is only ever re-opened as a brand new slice on a destination account (Transfer/CorporateAction
    # carry-over), so it never preserves a slice identity - the DB assigns a fresh one.
    def slice_id(self):
        return None

    def close_operation(self):
        return self._close_op

    def open_qty(self, adjusted=False) -> Decimal:
        if adjusted:
            return self._open_qty * self._adj_qty
        else:
            return self._open_qty

    def qty(self) -> Decimal:
        return self._qty

    def open_timestamp(self) -> int:
        return self._open_op.timestamp()

    # The acquisition date: the purchase, or a corporate action that gave a new stock its own date
    def acquired(self) -> int:
        return self._acquired

    # True if the acquisition date is a day only: the purchase's own flag, or a day-marker stamp of an action
    def acquired_is_day(self) -> bool:
        if self._acquired == self._open_op.timestamp():
            return self._open_op.timestamp_is_day()
        return is_day_marker(self._acquired)

    def close_timestamp(self) -> int:
        return self._close_op.timestamp()

    def open_price(self, adjusted=False) -> Decimal:
        if adjusted:
            return self._open_price * self._adj_price * self._fx
        else:
            return self._open_price

    def close_price(self) -> Decimal:
        return self._close_price

    def p_adjustment(self) -> Decimal:
        return self._adj_price

    def q_adjustment(self) -> Decimal:
        return self._adj_qty

    def fx_adjustment(self) -> Decimal:
        return self._fx

    # Share of the opening operation's cost this deal carries, in the closing account's currency
    def cost_basis(self) -> Decimal:
        return self._adj_price * self._adj_qty * self._fx

    # The same share without the rates of transfers between currencies - in the opening account's currency
    def native_cost_basis(self) -> Decimal:
        return self._adj_price * self._adj_qty

    # Opening amount in the currency it was paid in, the opening account's - what a tax report converts by its own rule
    def native_open_amount(self) -> Decimal:
        return self.native_cost_basis() * self.open_price() * abs(self.open_qty())

    # If currency_id is different from trade account currency then adjusts value to the rate of currency for
    # given timestamp and returns it. Otherwise, simply returns unchanged value
    def adjusted(self, value: Decimal, currency_id: int, timestamp: int) -> Decimal:
        if currency_id and currency_id != self._account.currency():
            return value * JalAsset(self._account.currency()).quote(timestamp, currency_id)[1]
        else:
            return value

    # Returns opening amount of the trade (open price x qty)
    # currency_id != 0 - convert amount into given currency (using settlement date rate by default)
    # rate_ts - defines timestamp of currency rate if not zero
    # no_settlement - transaction date is used for currency conversion, not settlement date
    # full==True - provide full amount of opening trade (without correction due to corporate actions)
    def open_amount(self, currency_id: int = 0, rate_ts: int = 0, no_settlement=False, full=False) -> Decimal:
        cost_basis = Decimal('1') if full else self.cost_basis()
        timestamp = self._open_op.timestamp() if no_settlement else self._open_op.settlement()
        timestamp = rate_ts if rate_ts else timestamp
        return self.adjusted(cost_basis * self.open_price() * abs(self.open_qty()), currency_id, timestamp)

    # Returns closing amount of the trade (close price x qty)
    # currency_id != 0 - convert amount into given currency (using settlement date rate by default)
    # rate_ts - defines timestamp of currency rate if not zero
    # no_settlement - transaction date is used for currency conversion, not settlement date
    def close_amount(self, currency_id: int = 0, rate_ts: int = 0, no_settlement=False) -> Decimal:
        timestamp = self._close_op.timestamp() if no_settlement else self._close_op.settlement()
        timestamp = rate_ts if rate_ts else timestamp
        return self.adjusted(self._close_price * abs(self._qty), currency_id, timestamp)

    # Fee of opening part of the deal
    # if currency_id isn't 0 then returns fee converted into given currency
    # If full==True, then provide full fee of opening trade (without correction due to corporate actions)
    # rate_ts - defines timestamp of currency rate if not zero
    def open_fee(self, currency_id: int = 0, rate_ts: int = 0, full: bool = False) -> Decimal:
        cost_basis = Decimal('1') if full else self.cost_basis()
        if self._open_op.type() == jal.db.operations.LedgerTransaction.Trade:
            o_fee = cost_basis * self._open_op.fee() * abs(self._qty / (self._open_op.qty() * self.q_adjustment()))
            timestamp = rate_ts if rate_ts else self._open_op.timestamp()
            return self.adjusted(o_fee, currency_id, timestamp)
        else:
            return Decimal('0')

    # The same share of the opening fee without the rates of transfers between currencies - in the opening account's currency
    def native_open_fee(self) -> Decimal:
        if self._open_op.type() == jal.db.operations.LedgerTransaction.Trade:
            return self.native_cost_basis() * self._open_op.fee() * abs(self._qty / (self._open_op.qty() * self.q_adjustment()))
        return Decimal('0')

    # Fee of closing part of the deal
    # if currency_id isn't 0 then returns fee converted into given currency
    # rate_ts - defines timestamp of currency rate if not zero
    def close_fee(self, currency_id: int = 0, rate_ts: int = 0) -> Decimal:
        if self._close_op.type() == jal.db.operations.LedgerTransaction.Trade:
            c_fee = self._close_op.fee() * abs(self._qty / self._close_op.qty())
            timestamp = rate_ts if rate_ts else self._close_op.timestamp()
            return self.adjusted(c_fee, currency_id, timestamp)
        else:
            return Decimal('0')

    # Total fee for the trade
    def fee(self, currency_id: int = 0, rate_ts: int = 0) -> Decimal:
        return self.open_fee(currency_id, rate_ts) + self.close_fee(currency_id, rate_ts)

    def profit(self, percent=False) -> Decimal:
        profit = self._qty * self._close_price - self.open_price(adjusted=True) * self.open_qty(adjusted=True) - self.fee()
        if percent:
            profit = Decimal('100') * profit / (self.open_price(adjusted=True) * self.open_qty(adjusted=True)) if self._open_price else Decimal('0')
        return profit

    # Returns a list of LedgerTransactions that modified position after its opening
    # (i.e. transfers or corporate actions that happened during position lifetime)
    def modified_by(self) -> list:
        modifiers = []
        for otype, oid in self._store.modifiers(self._open_op.type(), self._open_op.id()):
            modifiers.append(jal.db.operations.LedgerTransaction.get_operation(otype, oid, jal.db.operations.Transfer.Outgoing))
        return modifiers
