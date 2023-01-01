from decimal import Decimal
from jal.db.db import JalDB
import jal.db.account
import jal.db.asset
import jal.db.operations


class JalClosedTrade(JalDB):
    def __init__(self, id: int = 0) -> None:
        super().__init__()
        self._id = id
        self._data = self.readSQL("SELECT account_id, asset_id, open_op_type, open_op_id, open_timestamp, open_price, "
                                   "close_op_type, close_op_id, close_timestamp, close_price, qty "
                                   "FROM trades_closed WHERE id=:id", [(":id", self._id)], named=True)
        if self._data:
            self._account = jal.db.account.JalAccount(self._data['account_id'])
            self._asset = jal.db.asset.JalAsset(self._data['asset_id'])
            self._open_op = jal.db.operations.LedgerTransaction.get_operation(self._data['open_op_type'], self._data['open_op_id'])
            self._close_op = jal.db.operations.LedgerTransaction.get_operation(self._data['close_op_type'], self._data['close_op_id'])
            self._open_price = Decimal(self._data['open_price'])
            self._close_price = Decimal(self._data['close_price'])
            self._qty = Decimal(self._data['qty'])
        else:
            self._account = self._asset = self._open_op = self._close_op = None
            self._open_price = self._close_price = self._qty = Decimal('0')

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

    # Fee of opening part of the deal
    def open_fee(self) -> Decimal:
        if self._open_op.type() == jal.db.operations.LedgerTransaction.Trade:
            return self._open_op.fee() * abs(self._qty / self._open_op.qty())
        else:
            return Decimal('0')

    # Fee of closing part of the deal
    def close_fee(self) -> Decimal:
        if self._close_op.type() == jal.db.operations.LedgerTransaction.Trade:
            return self._close_op.fee() * abs(self._qty / self._close_op.qty())
        else:
            return Decimal('0')

    # Total fee for the trade
    def fee(self):
        return self.open_fee() + self.close_fee()

    def profit(self, percent=False) -> Decimal:
        profit = self._qty * (self._close_price - self._open_price) - self.fee()
        if percent:
            profit = Decimal('100') * profit / (self._qty * self._open_price) if self._open_price else Decimal('0')
        return profit
