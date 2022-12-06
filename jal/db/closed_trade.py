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

    def open_operation(self):
        return self._open_op

    def close_operation(self):
        return self._close_op

    def qty(self) -> Decimal:
        return self._qty
