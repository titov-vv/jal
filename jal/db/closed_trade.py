from decimal import Decimal
from jal.db.db import JalDB
from jal.db.helpers import format_decimal
import jal.db.account
import jal.db.operations
from jal.db.asset import JalAsset


# ----------------------------------------------------------------------------------------------------------------------
# Class that represents open trade and provides some methods equal to JalClosedTrades to make compatible calls
class JalOpenTrade(JalDB):
    def __init__(self, operation, price, qty, adjustments=(Decimal('1'), Decimal('1'))) -> None:
        super().__init__()
        self._op = operation
        self._price = price
        self._qty = qty
        self._adj_price = adjustments[0]   # Historical adjustments of price and quantity that happened
        self._adj_qty = adjustments[1]     # during holding of this position

    def open_operation(self):
        return self._op

    def open_price(self, adjusted=False) -> Decimal:
        if adjusted:
            return self._price * self._adj_price
        else:
            return self._price

    def open_qty(self, adjusted=False) -> Decimal:
        if adjusted:
            return self._qty * self._adj_qty
        else:
            return self._qty

    # Method to adjust price of open position
    def set_price(self, new_price: Decimal):
        self._price = new_price

    # Method to adjust size of open position
    def set_qty(self, new_qty: Decimal):
        self._qty = new_qty

    def p_adjustment(self) -> Decimal:
        return self._adj_price

    def q_adjustment(self) -> Decimal:
        return self._adj_qty


# ----------------------------------------------------------------------------------------------------------------------
class JalClosedTrade(JalDB):
    def __init__(self, id: int = 0) -> None:
        super().__init__()
        self._id = id
        self._data = self._read("SELECT account_id, asset_id, open_otype, open_oid, open_timestamp, open_price, "
                                "open_qty, close_otype, close_oid, close_timestamp, close_price, close_qty, c_price, c_qty "
                                "FROM trades_closed WHERE id=:id", [(":id", self._id)], named=True)
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
        else:
            self._account = self._asset = self._open_op = self._close_op = None
            self._open_price = self._open_qty = self._close_price = self._qty = Decimal('0')
            self._adj_price = self._adj_qty = Decimal('1')

    @classmethod
    # Creates a record in 'trades_closed' table based on given data:
    # o_trade - trade JalClosedTrade that initiates the trade (may also be AssetPayment as Stock Dividend or Vesting)
    # c_operation - LedgerTransaction that closed current trade
    # o_qty and c_qty - how many items were used from opening and closing trades respectively
    def create_from_trades(cls, o_trade: JalOpenTrade, c_operation, qty):
        o_operation = o_trade.open_operation()
        o_qty = qty / o_trade.q_adjustment()   # Calculate adjusted amount for opening trade
        c_price = o_trade.open_price() if c_operation.price() is None else c_operation.price()
        _ = cls._exec(
            "INSERT INTO trades_closed(account_id, asset_id, open_otype, open_oid, open_timestamp, open_price, "
            "open_qty, close_otype, close_oid, close_timestamp, close_price, close_qty, c_price, c_qty) "
            "VALUES(:account_id, :asset_id, :open_otype, :open_oid, :open_timestamp, :open_price, :open_qty, "
            ":close_otype, :close_oid, :close_timestamp, :close_price, :close_qty, :c_price, :c_qty)",
            [(":account_id", c_operation.account().id()), (":asset_id", c_operation.asset().id()),
             (":open_otype", o_operation.type()), (":open_oid", o_operation.id()),
             (":open_timestamp", o_operation.timestamp()), (":open_price", format_decimal(o_trade.open_price())),
             (":open_qty", format_decimal(o_qty)), (":close_otype", c_operation.type()),
             (":close_oid", c_operation.id()), (":close_timestamp", c_operation.timestamp()),
             (":close_price", format_decimal(c_price)), (":close_qty", format_decimal(qty)),
             (":c_price", format_decimal(o_trade.p_adjustment())), (":c_qty", format_decimal(o_trade.q_adjustment()))])

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

    def close_timestamp(self) -> int:
        return self._close_op.timestamp()

    def open_price(self, adjusted=False) -> Decimal:
        if adjusted:
            return self._open_price * self._adj_price
        else:
            return self._open_price

    def close_price(self) -> Decimal:
        return self._close_price

    def p_adjustment(self) -> Decimal:
        return self._adj_price

    def q_adjustment(self) -> Decimal:
        return self._adj_qty

    def cost_basis(self) -> Decimal:
        return self._adj_price * self._adj_qty

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
        query = self._exec("SELECT DISTINCT m_otype, m_oid FROM trades_opened "
                           "WHERE otype=:otype AND oid=:oid AND m_otype!=:trade",
                           [(":otype", self._open_op.type()), (":oid", self._open_op.id()),
                            (":trade", jal.db.operations.LedgerTransaction.Trade)])
        modifiers = []
        while query.next():
            otype, oid = self._read_record(query)
            modifiers.append(jal.db.operations.LedgerTransaction.get_operation(otype, oid, jal.db.operations.Transfer.Outgoing))
        return modifiers
