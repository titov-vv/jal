from decimal import Decimal
from jal.db.db import JalDB
from jal.db.helpers import format_decimal
import jal.db.account
import jal.db.asset
import jal.db.operations
from jal.db.asset import JalAsset


# ----------------------------------------------------------------------------------------------------------------------
# Class that represents open trade and provides some methods equal to JalClosedTrades to make compatible calls
class JalOpenTrade(JalDB):
    def __init__(self, operation, price, qty) -> None:
        super().__init__()
        self._op = operation
        self._price = price
        self._qty = qty

    def open_operation(self):
        return self._op

    def open_price(self) -> Decimal:
        return self._price

    def qty(self) -> Decimal:
        return self._qty


# ----------------------------------------------------------------------------------------------------------------------
class JalClosedTrade(JalDB):
    def __init__(self, id: int = 0) -> None:
        super().__init__()
        self._id = id
        self._data = self._read("SELECT account_id, asset_id, open_otype, open_oid, open_timestamp, open_price, "
                                "close_otype, close_oid, close_timestamp, close_price, qty "
                                "FROM trades_closed WHERE id=:id", [(":id", self._id)], named=True)
        if self._data:
            self._account = jal.db.account.JalAccount(self._data['account_id'])
            self._asset = jal.db.asset.JalAsset(self._data['asset_id'])
            self._open_op = jal.db.operations.LedgerTransaction.get_operation(self._data['open_otype'], self._data['open_oid'], jal.db.operations.Transfer.Incoming)
            self._close_op = jal.db.operations.LedgerTransaction.get_operation(self._data['close_otype'], self._data['close_oid'], jal.db.operations.Transfer.Outgoing)
            self._open_price = Decimal(self._data['open_price'])
            self._close_price = Decimal(self._data['close_price'])
            self._qty = Decimal(self._data['qty'])
        else:
            self._account = self._asset = self._open_op = self._close_op = None
            self._open_price = self._close_price = self._qty = Decimal('0')

    @classmethod
    def create_from_trades(cls, open_trade, close_trade, qty, open_price, close_price):
        _ = cls._exec(
            "INSERT INTO trades_closed(account_id, asset_id, open_otype, open_oid, open_timestamp, open_price, "
            "close_otype, close_oid, close_timestamp, close_price, qty) "
            "VALUES(:account_id, :asset_id, :open_otype, :open_oid, :open_timestamp, :open_price, "
            ":close_otype, :close_oid, :close_timestamp, :close_price, :qty)",
            [(":account_id", close_trade.account().id()), (":asset_id", close_trade.asset().id()),
             (":open_otype", open_trade.type()), (":open_oid", open_trade.id()),
             (":open_timestamp", open_trade.timestamp()), (":open_price", format_decimal(open_price)),
             (":close_otype", close_trade.type()), (":close_oid", close_trade.id()),
             (":close_timestamp", close_trade.timestamp()), (":close_price", format_decimal(close_price)),
             (":qty", format_decimal(qty))])

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

    def asset(self) -> jal.db.asset.JalAsset:
        return self._asset

    def symbol(self) -> str:
        return self._asset.symbol(self._account.currency())

    def open_operation(self):
        return self._open_op

    def close_operation(self):
        return self._close_op

    def qty(self) -> Decimal:
        return self._qty

    def open_timestamp(self) -> int:
        return self._open_op.timestamp()

    def close_timestamp(self) -> int:
        return self._close_op.timestamp()

    def open_price(self) -> Decimal:
        return self._open_price

    def close_price(self) -> Decimal:
        return self._close_price

    # If currency_id is different from trade account currency then adjusts value to the rate of currency for
    # given timestamp and returns it. Otherwise, simply returns unchanged value
    def adjusted(self, value: Decimal, currency_id: int, timestamp: int) -> Decimal:
        if currency_id and currency_id != self._account.currency():
            return value * JalAsset(self._account.currency()).quote(timestamp, currency_id)[1]
        else:
            return value

    # Returns opening amount of the trade (open price x qty)
    # If currency_id isn't 0 then converts amount into given currency using settlement date rate
    # If no_settlement is set to True then transaction date is used for conversion
    def open_amount(self, currency_id: int = 0, no_settlement=False) -> Decimal:
        timestamp = self._open_op.timestamp() if no_settlement else self._open_op.settlement()
        return self.adjusted(self._open_price * abs(self._qty), currency_id, timestamp)

    # Returns closing amount of the trade (close price x qty)
    # If currency_id isn't 0 then converts amount into given currency using settlement date rate
    # If no_settlement is set to True then transaction date is used for conversion
    def close_amount(self, currency_id: int = 0, no_settlement=False) -> Decimal:
        timestamp = self._close_op.timestamp() if no_settlement else self._close_op.settlement()
        return self.adjusted(self._close_price * abs(self._qty), currency_id, timestamp)

    # Fee of opening part of the deal
    # if currency_id isn't 0 then returns fee converted into given currency
    def open_fee(self, currency_id: int = 0) -> Decimal:
        if self._open_op.type() == jal.db.operations.LedgerTransaction.Trade:
            o_fee = self._open_op.fee() * abs(self._qty / self._open_op.qty())
            return self.adjusted(o_fee, currency_id, self._open_op.timestamp())
        else:
            return Decimal('0')

    # Fee of closing part of the deal
    # if currency_id isn't 0 then returns fee converted into given currency
    def close_fee(self, currency_id: int = 0) -> Decimal:
        if self._close_op.type() == jal.db.operations.LedgerTransaction.Trade:
            c_fee = self._close_op.fee() * abs(self._qty / self._close_op.qty())
            return self.adjusted(c_fee, currency_id, self._close_op.timestamp())
        else:
            return Decimal('0')

    # Total fee for the trade
    def fee(self, currency_id: int = 0) -> Decimal:
        return self.open_fee(currency_id) + self.close_fee(currency_id)

    def profit(self, percent=False) -> Decimal:
        if self._close_op.type() == jal.db.operations.LedgerTransaction.Trade:
            profit = self._qty * (self._close_price - self._open_price) - self.fee()
            if percent:
                profit = Decimal('100') * profit / (self._qty * self._open_price) if self._open_price else Decimal('0')
            return profit
        else:
            return Decimal('0')

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
