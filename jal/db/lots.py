from decimal import Decimal
from jal.db.db import JalDB
from jal.db.helpers import format_decimal
import jal.db.operations


# ----------------------------------------------------------------------------------------------------------------------
# Where lots and deals live: every statement on 'trades_opened' / 'trades_closed' of the ledger rebuild.
# Works on ids and decimals, returns rows; building lot objects and their FIFO order stay with the callers.
class LedgerLotStore(JalDB):
    # Stores a state of a lot; a NULL 'slice_id' makes the trades_opened_set_slice trigger give it the row's own id
    def open(self, timestamp: int, otype: int, oid: int, m_otype: int, m_oid: int, account_id: int, asset_id: int,
             price: Decimal, qty: Decimal, c_price: Decimal, c_qty: Decimal, c_fx: Decimal, slice_id, acquired: int):
        _ = self._exec(
            "INSERT INTO trades_opened(timestamp, otype, oid, m_otype, m_oid, account_id, asset_id, "
            "price, remaining_qty, c_price, c_qty, c_fx, slice_id, acquired) "
            "VALUES(:timestamp, :otype, :oid, :m_otype, :m_oid, :account_id, :asset_id, :price, "
            ":remaining_qty, :c_price, :c_qty, :c_fx, :slice_id, :acquired)",
            [(":timestamp", timestamp), (":otype", otype), (":oid", oid), (":m_otype", m_otype), (":m_oid", m_oid),
             (":account_id", account_id), (":asset_id", asset_id), (":price", format_decimal(price)),
             (":remaining_qty", format_decimal(qty)), (":c_price", format_decimal(c_price)),
             (":c_qty", format_decimal(c_qty)), (":c_fx", format_decimal(c_fx)),
             (":slice_id", slice_id), (":acquired", acquired)])

    # The latest state of every non-empty slice of a position at 'timestamp', unordered:
    # (otype, oid, price, qty, c_price, c_qty, c_fx, slice_id, acquired)
    def lots(self, account_id: int, asset_id: int, timestamp: int) -> list:
        lots = []
        query = self._exec("WITH open_trades_numbered AS "
                           "(SELECT timestamp, otype, oid, price, remaining_qty, c_price, c_qty, c_fx, slice_id, acquired, "
                           "ROW_NUMBER() OVER (PARTITION BY slice_id ORDER BY timestamp DESC, id DESC) AS row_no "
                           "FROM trades_opened WHERE account_id=:account AND asset_id=:asset AND timestamp<=:timestamp) "
                           "SELECT otype, oid, price, remaining_qty, c_price, c_qty, c_fx, slice_id, acquired "
                           "FROM open_trades_numbered WHERE row_no=1 AND remaining_qty!=:zero ",
                           [(":account", account_id), (":asset", asset_id),
                            (":timestamp", timestamp), (":zero", format_decimal(Decimal('0')))])
        while query.next():
            lots.append(self._read_record(query, cast=[int, int, Decimal, Decimal, Decimal, Decimal, Decimal, int, int]))
        return lots

    # Latest quantity of every non-empty slice of every position: (account_id, asset_id, qty), the quantity unsigned
    def latest_quantities(self) -> list:
        quantities = []
        query = self._exec("WITH open_trades_numbered AS "
                           "(SELECT account_id, asset_id, remaining_qty, "
                           "ROW_NUMBER() OVER (PARTITION BY slice_id ORDER BY timestamp DESC, id DESC) AS row_no "
                           "FROM trades_opened) "
                           "SELECT account_id, asset_id, remaining_qty FROM open_trades_numbered "
                           "WHERE row_no=1 AND remaining_qty!=:zero", [(":zero", format_decimal(Decimal('0')))])
        while query.next():
            quantities.append(self._read_record(query, cast=[int, int, Decimal]))
        return quantities

    # What the lots of a position hold now, negative for a short one: a lot keeps an unsigned quantity and is short
    # when the trade that opened it sold
    def position(self, account_id: int, asset_id: int) -> Decimal:
        query = self._exec("WITH open_trades_numbered AS "
                           "(SELECT o.remaining_qty, CASE WHEN o.otype=:trade AND CAST(t.qty AS REAL)<0 THEN -1 ELSE 1 "
                           "END AS side, ROW_NUMBER() OVER (PARTITION BY o.slice_id ORDER BY o.timestamp DESC, o.id DESC) "
                           "AS row_no FROM trades_opened AS o LEFT JOIN trades AS t ON o.otype=:trade AND t.oid=o.oid "
                           "WHERE o.account_id=:account AND o.asset_id=:asset) "
                           "SELECT remaining_qty, side FROM open_trades_numbered WHERE row_no=1",
                           [(":trade", jal.db.operations.LedgerTransaction.Trade), (":account", account_id),
                            (":asset", asset_id)])
        position = Decimal('0')
        while query.next():
            qty, side = self._read_record(query, cast=[Decimal, int])
            position += qty * side
        return position

    # Stores a deal
    def close(self, account_id: int, asset_id: int, open_otype: int, open_oid: int, open_timestamp: int,
              open_price: Decimal, open_qty: Decimal, close_otype: int, close_oid: int, close_timestamp: int,
              close_price: Decimal, close_qty: Decimal, c_price: Decimal, c_qty: Decimal, c_fx: Decimal):
        _ = self._exec(
            "INSERT INTO trades_closed(account_id, asset_id, open_otype, open_oid, open_timestamp, open_price, "
            "open_qty, close_otype, close_oid, close_timestamp, close_price, close_qty, c_price, c_qty, c_fx) "
            "VALUES(:account_id, :asset_id, :open_otype, :open_oid, :open_timestamp, :open_price, :open_qty, "
            ":close_otype, :close_oid, :close_timestamp, :close_price, :close_qty, :c_price, :c_qty, :c_fx)",
            [(":account_id", account_id), (":asset_id", asset_id), (":open_otype", open_otype),
             (":open_oid", open_oid), (":open_timestamp", open_timestamp), (":open_price", format_decimal(open_price)),
             (":open_qty", format_decimal(open_qty)), (":close_otype", close_otype), (":close_oid", close_oid),
             (":close_timestamp", close_timestamp), (":close_price", format_decimal(close_price)),
             (":close_qty", format_decimal(close_qty)), (":c_price", format_decimal(c_price)),
             (":c_qty", format_decimal(c_qty)), (":c_fx", format_decimal(c_fx))])

    # The stored deal 'deal_id' as a dict of its columns, None if there is none
    def deal(self, deal_id: int):
        return self._read("SELECT account_id, asset_id, open_otype, open_oid, open_timestamp, open_price, "
                          "open_qty, close_otype, close_oid, close_timestamp, close_price, close_qty, c_price, c_qty, "
                          "c_fx FROM trades_closed WHERE id=:id", [(":id", deal_id)], named=True)

    # Ids of the deals of an account (of one asset if given) closed by operations of 'close_otypes'
    def deals(self, account_id: int, asset_id, close_otypes) -> list:
        otypes = ','.join(str(int(x)) for x in close_otypes)
        if asset_id is None:
            query = self._exec(f"SELECT id FROM trades_closed WHERE close_otype IN ({otypes}) AND account_id=:account",
                               [(":account", account_id)])
        else:
            query = self._exec(f"SELECT id FROM trades_closed WHERE close_otype IN ({otypes}) AND account_id=:account AND asset_id=:asset",
                               [(":account", account_id), (":asset", asset_id)])
        return self._ids(query)

    # Ids of the deals operation (otype, oid) closed in a position
    def deals_closed_by(self, otype: int, oid: int, account_id: int, asset_id: int) -> list:
        query = self._exec("SELECT id FROM trades_closed WHERE close_otype=:otype AND close_oid=:oid "
                           "AND account_id=:account AND asset_id=:asset",
                           [(":otype", otype), (":oid", oid), (":account", account_id), (":asset", asset_id)])
        return self._ids(query)

    # (otype, oid) of the operations other than trades that stored a state of the lots opened by (otype, oid)
    def modifiers(self, otype: int, oid: int) -> list:
        query = self._exec("SELECT DISTINCT m_otype, m_oid FROM trades_opened "
                           "WHERE otype=:otype AND oid=:oid AND m_otype!=:trade",
                           [(":otype", otype), (":oid", oid), (":trade", jal.db.operations.LedgerTransaction.Trade)])
        modifiers = []
        while query.next():
            modifiers.append(self._read_record(query))
        return modifiers

    # Removes the deals closed and the lot states stored at or after 'frontier'
    def wipe_from(self, frontier: int):
        _ = self._exec("DELETE FROM trades_closed WHERE close_timestamp >= :frontier", [(":frontier", frontier)])
        _ = self._exec("DELETE FROM trades_opened WHERE timestamp >= :frontier", [(":frontier", frontier)])

    def _ids(self, query) -> list:
        ids = []
        while query.next():
            ids.append(self._read_record(query, cast=[int]))
        return ids
