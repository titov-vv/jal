from decimal import Decimal
from jal.db.db import JalDB
import jal.db.account
import jal.db.asset
import jal.db.operations
from jal.db.asset import JalAsset


class JalClosedTrade(JalDB):
    def __init__(self, id: int = 0) -> None:
        super().__init__()
        self._id = id
        self._data = self._read("SELECT account_id, asset_id, open_op_type, open_op_id, open_timestamp, open_price, "
                                "close_op_type, close_op_id, close_timestamp, close_price, qty "
                                "FROM trades_closed WHERE id=:id", [(":id", self._id)], named=True)
        if self._data:
            self._account = jal.db.account.JalAccount(self._data['account_id'])
            self._asset = jal.db.asset.JalAsset(self._data['asset_id'])
            self._open_op = jal.db.operations.LedgerTransaction.get_operation(self._data['open_op_type'], self._data['open_op_id'], jal.db.operations.Transfer.Incoming)
            self._close_op = jal.db.operations.LedgerTransaction.get_operation(self._data['close_op_type'], self._data['close_op_id'], jal.db.operations.Transfer.Outgoing)
            self._open_price = Decimal(self._data['open_price'])
            self._close_price = Decimal(self._data['close_price'])
            self._qty = Decimal(self._data['qty'])
        else:
            self._account = self._asset = self._open_op = self._close_op = None
            self._open_price = self._close_price = self._qty = Decimal('0')

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
        profit = self._qty * (self._close_price - self._open_price) - self.fee()
        if percent:
            profit = Decimal('100') * profit / (self._qty * self._open_price) if self._open_price else Decimal('0')
        return profit
