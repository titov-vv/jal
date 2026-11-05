from decimal import Decimal
from jal.constants import Setup
from jal.db.db import JalDB
from jal.db.helpers import format_decimal
import jal.db.operations
import jal.db.closed_trade
import jal.db.basis_policy
import jal.db.account


# ----------------------------------------------------------------------------------------------------------------------
# Every statement on trades_opened / trades_closed, in the main database or in an attached 'schema'.
# Ids and decimals in, rows out; LotEngine builds the lot objects and orders them.
class LedgerLotStore(JalDB):
    def __init__(self, schema=None):
        super().__init__()
        self._opened = 'trades_opened' if schema is None else f'{schema}.trades_opened'
        self._closed = 'trades_closed' if schema is None else f'{schema}.trades_closed'

    # Stores a state of a lot; a NULL 'slice_id' makes the trades_opened_set_slice trigger give it the row's own id
    def open(self, timestamp: int, otype: int, oid: int, m_otype: int, m_oid: int, account_id: int, asset_id: int,
             price: Decimal, qty: Decimal, c_price: Decimal, c_qty: Decimal, c_fx: Decimal, slice_id, acquired: int):
        _ = self._exec(
            f"INSERT INTO {self._opened}(timestamp, otype, oid, m_otype, m_oid, account_id, asset_id, "
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
                           f"FROM {self._opened} WHERE account_id=:account AND asset_id=:asset AND timestamp<=:timestamp) "
                           "SELECT otype, oid, price, remaining_qty, c_price, c_qty, c_fx, slice_id, acquired "
                           "FROM open_trades_numbered WHERE row_no=1 AND remaining_qty!=:zero ",
                           [(":account", account_id), (":asset", asset_id),
                            (":timestamp", timestamp), (":zero", format_decimal(Decimal('0')))])
        while query.next():
            lots.append(self._read_record(query, cast=[int, int, Decimal, Decimal, Decimal, Decimal, Decimal, int, int]))
        return lots

    # Latest state of every slice with its quantity signed: a lot keeps an unsigned quantity and is short when the trade
    # that opened it sold. 'where' narrows the slices by o.account_id / o.asset_id.
    _SIGNED_SLICES = ("WITH open_trades_numbered AS "
                      "(SELECT o.account_id, o.asset_id, o.remaining_qty, "
                      "CASE WHEN o.otype=:trade AND CAST(t.qty AS REAL)<0 THEN -1 ELSE 1 END AS side, "
                      "ROW_NUMBER() OVER (PARTITION BY o.slice_id ORDER BY o.timestamp DESC, o.id DESC) AS row_no "
                      "FROM {opened} AS o LEFT JOIN trades AS t ON o.otype=:trade AND t.oid=o.oid {where}) "
                      "SELECT account_id, asset_id, remaining_qty, side FROM open_trades_numbered WHERE row_no=1")

    # (account_id, asset_id, signed qty) of the latest state of every slice of every position
    def slices(self) -> list:
        query = self._exec(self._SIGNED_SLICES.format(opened=self._opened, where=""),
                           [(":trade", jal.db.operations.LedgerTransaction.Trade)])
        slices = []
        while query.next():
            account_id, asset_id, qty, side = self._read_record(query, cast=[int, int, Decimal, int])
            slices.append((account_id, asset_id, qty * side))
        return slices

    # What the lots of a position hold now, negative for a short one
    def position(self, account_id: int, asset_id: int) -> Decimal:
        query = self._exec(self._SIGNED_SLICES.format(opened=self._opened,
                                                     where="WHERE o.account_id=:account AND o.asset_id=:asset"),
                           [(":trade", jal.db.operations.LedgerTransaction.Trade), (":account", account_id),
                            (":asset", asset_id)])
        position = Decimal('0')
        while query.next():
            _, _, qty, side = self._read_record(query, cast=[int, int, Decimal, int])
            position += qty * side
        return position

    # Stores a deal
    def close(self, account_id: int, asset_id: int, open_otype: int, open_oid: int, open_timestamp: int,
              open_price: Decimal, open_qty: Decimal, close_otype: int, close_oid: int, close_timestamp: int,
              close_price: Decimal, close_qty: Decimal, c_price: Decimal, c_qty: Decimal, c_fx: Decimal):
        _ = self._exec(
            f"INSERT INTO {self._closed}(account_id, asset_id, open_otype, open_oid, open_timestamp, open_price, "
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
                          f"c_fx FROM {self._closed} WHERE id=:id", [(":id", deal_id)], named=True)

    # Ids of the deals of an account (of one asset if given) closed by operations of 'close_otypes'
    def deals(self, account_id: int, asset_id, close_otypes) -> list:
        otypes = ','.join(str(int(x)) for x in close_otypes)
        if asset_id is None:
            query = self._exec(f"SELECT id FROM {self._closed} WHERE close_otype IN ({otypes}) AND account_id=:account",
                               [(":account", account_id)])
        else:
            query = self._exec(f"SELECT id FROM {self._closed} WHERE close_otype IN ({otypes}) AND account_id=:account AND asset_id=:asset",
                               [(":account", account_id), (":asset", asset_id)])
        return self._ids(query)

    # Ids of the deals operation (otype, oid) closed in a position
    def deals_closed_by(self, otype: int, oid: int, account_id: int, asset_id: int) -> list:
        query = self._exec(f"SELECT id FROM {self._closed} WHERE close_otype=:otype AND close_oid=:oid "
                           "AND account_id=:account AND asset_id=:asset",
                           [(":otype", otype), (":oid", oid), (":account", account_id), (":asset", asset_id)])
        return self._ids(query)

    # (otype, oid) of the operations other than trades that stored a state of the lots opened by (otype, oid)
    def modifiers(self, otype: int, oid: int) -> list:
        query = self._exec(f"SELECT DISTINCT m_otype, m_oid FROM {self._opened} "
                           "WHERE otype=:otype AND oid=:oid AND m_otype!=:trade",
                           [(":otype", otype), (":oid", oid), (":trade", jal.db.operations.LedgerTransaction.Trade)])
        modifiers = []
        while query.next():
            modifiers.append(self._read_record(query))
        return modifiers

    # (otype, oid) of the operations other than trades and (otype, oid) itself that stored a state of its lots in
    # 'asset_id', oldest first
    def lot_modifiers(self, otype: int, oid: int, asset_id: int) -> list:
        query = self._exec(f"SELECT DISTINCT m_otype, m_oid FROM {self._opened} WHERE otype=:otype AND oid=:oid "
                           "AND asset_id=:asset AND m_otype!=:trade AND NOT (m_otype=otype AND m_oid=oid) "
                           "ORDER BY timestamp",
                           [(":otype", otype), (":oid", oid), (":asset", asset_id),
                            (":trade", jal.db.operations.LedgerTransaction.Trade)])
        modifiers = []
        while query.next():
            modifiers.append(self._read_record(query))
        return modifiers

    # Ids of every asset the account has held a lot of
    def assets(self, account_id: int) -> list:
        return self._ids(self._exec(f"SELECT DISTINCT asset_id FROM {self._opened} WHERE account_id=:account",
                                    [(":account", account_id)]))

    # Removes the deals closed and the lot states stored at or after 'frontier'
    def wipe_from(self, frontier: int):
        _ = self._exec(f"DELETE FROM {self._closed} WHERE close_timestamp >= :frontier", [(":frontier", frontier)])
        _ = self._exec(f"DELETE FROM {self._opened} WHERE timestamp >= :frontier", [(":frontier", frontier)])

    def _ids(self, query) -> list:
        ids = []
        while query.next():
            ids.append(self._read_record(query, cast=[int]))
        return ids


# ----------------------------------------------------------------------------------------------------------------------
# The only code that matches lots, over a store and by a BasisPolicy (JalPolicy unless given).
# A quantity given to dispose()/carry_out() leaves the position: positive closes a long, negative a short.
class LotEngine:
    def __init__(self, store=None, policy=None):
        self.store = LedgerLotStore() if store is None else store
        self.policy = jal.db.basis_policy.JalPolicy() if policy is None else policy
        self._parked = {}

    # Open lots of a position at 'timestamp' (latest if None) in the order the policy takes them
    def lots(self, account, asset, timestamp=None) -> list:
        if timestamp is None:
            timestamp = Setup.MAX_TIMESTAMP
        lots = []
        for otype, oid, price, qty, p, q, fx, slice_id, acquired in self.store.lots(account.id(), asset.id(), timestamp):
            operation = jal.db.operations.LedgerTransaction().get_operation(otype, oid,
                                                                            jal.db.operations.Transfer.Incoming)
            lots.append(jal.db.closed_trade.JalOpenTrade(operation, price, qty, adjustments=(p, q), fx=fx,
                                                         slice_id=slice_id, acquired=acquired))
        return self.policy.order(lots)

    # What the lots of a position hold now, negative for a short one
    def position(self, account, asset) -> Decimal:
        return self.store.position(account.id(), asset.id())

    # Opens a new lot of 'qty' at 'price'; 'acquired' defaults to the operation's own time
    def acquire(self, account, asset, operation, price: Decimal, qty: Decimal, acquired=None):
        self._store(account, asset, jal.db.closed_trade.JalOpenTrade(operation, price, qty, acquired=acquired),
                    operation)

    # FIFO-closes 'qty' into deals at 'close_price'; returns the quantity matched and its basis, both unsigned
    def dispose(self, account, asset, operation, qty: Decimal, close_price: Decimal) -> (Decimal, Decimal):
        return self._match(account, asset, operation, qty, close_price, record_deals=True)

    # FIFO-closes 'qty' into deals at each lot's own price, for carry_in() to re-open; returns (quantity, basis)
    def carry_out(self, account, asset, operation, qty: Decimal) -> (Decimal, Decimal):
        return self._match(account, asset, operation, qty, None, record_deals=True)

    # The deals 'operation' closed in a position, as carry_in() takes them
    def carried(self, operation, account, asset) -> list:
        deals = self.store.deals_closed_by(operation.type(), operation.id(), account.id(), asset.id())
        return [jal.db.closed_trade.JalClosedTrade(x, store=self.store) for x in deals]

    # Keeps the value a sending leg leaves in transit, rounded as its ledger posting is, for parked() to give back
    def park(self, operation, value: Decimal):
        precision = jal.db.account.JalAccount(operation.account_id()).precision()
        self._parked[(operation.type(), operation.id())] = round(value, precision)

    # What the sending leg of 'operation' parked in this engine, None if it didn't run here
    def parked(self, operation):
        return self._parked.get((operation.type(), operation.id()))

    # Re-opens 'deals' as lots of 'asset' on 'account'. Each keeps its quantity when 'qty' is None, otherwise 'qty' is
    # allocated over them; their price takes 'price_factor', c_fx takes 'fx_factor'; 'acquired' restarts the date.
    def carry_in(self, deals, account, asset, operation, qty=None, price_factor=Decimal('1'), fx_factor=Decimal('1'),
                 acquired=None):
        quantities = [x.qty() for x in deals] if qty is None else jal.db.closed_trade.allocate_qty(deals, qty)
        for deal, lot_qty in zip(deals, quantities):
            self._store(account, asset, deal, operation, qty=lot_qty, price_adjustment=price_factor,
                        acquired=acquired, fx_adjustment=fx_factor)

    # FIFO-takes 'qty' out of the lots without deals; returns the quantity taken and its basis
    def consume(self, account, asset, operation, qty: Decimal) -> (Decimal, Decimal):
        return self._match(account, asset, operation, qty, None, record_deals=False)

    # What FIFO would take for 'qty' at 'timestamp', writing nothing: (quantity matched, basis, lots touched)
    def basis(self, account, asset, qty: Decimal, timestamp: int) -> (Decimal, Decimal, int):
        matched, basis, lots = Decimal('0'), Decimal('0'), 0
        if qty <= Decimal('0'):
            return matched, basis, lots
        for lot, taken, _ in self._walk(self.lots(account, asset, timestamp), qty):
            matched += taken
            basis += taken * lot.open_price(adjusted=True)
            lots += 1
        return matched, basis, lots

    # Steps over 'lots' for 'qty': (lot, taken, left). A difference within LOT_QTY_TOLERANCE is a rounding crumb of
    # the account precision and counts as the same number, so it neither aborts a rebuild nor leaves a dust lot.
    @staticmethod
    def _walk(lots, qty: Decimal):
        tolerance = qty * Decimal(Setup.LOT_QTY_TOLERANCE)
        taken = Decimal('0')
        for lot in lots:
            held = lot.open_qty()
            required = qty - taken
            if abs(held - required) <= tolerance:
                step, left = required, Decimal('0')
            else:
                step = held if held <= required else required
                left = held - step
            yield lot, step, left
            taken += step
            if taken == qty:
                return

    def _match(self, account, asset, operation, qty, close_price, record_deals) -> (Decimal, Decimal):
        sign = Decimal('-1') if qty < Decimal('0') else Decimal('1')
        matched, basis = Decimal('0'), Decimal('0')
        for lot, taken, left in self._walk(self.lots(account, asset), abs(qty)):
            lot.set_qty(left)
            self._store(account, asset, lot, operation)
            if record_deals:
                deal_price = lot.open_price() if close_price is None else close_price
                self._close(account, asset, lot, operation, sign * taken, deal_price)
            matched += taken
            basis += taken * lot.open_price(adjusted=True)
        return matched, basis

    # Stores a state of 'lot' changed by 'operation'. 'qty' re-sizes it (c_qty then relates it to the opening
    # quantity, for reporting only); 'price_adjustment' and 'fx_adjustment' multiply into c_price and c_fx.
    def _store(self, account, asset, lot, operation, qty=None, price_adjustment=Decimal('1'), acquired=None,
               fx_adjustment=Decimal('1')):
        opened_by = lot.open_operation()
        acquired = lot.acquired() if acquired is None else acquired
        if qty is None:
            qty, q_adjustment = lot.open_qty(), lot.q_adjustment()
        else:
            q_adjustment = qty / abs(lot.open_qty()) if lot.open_qty() else Decimal('1')   # a short deal is negative
        self.store.open(operation.timestamp(), opened_by.type(), opened_by.id(), operation.type(), operation.id(),
                        account.id(), asset.id(), lot.open_price(), qty, lot.p_adjustment() * price_adjustment,
                        q_adjustment, lot.fx_adjustment() * fx_adjustment, lot.slice_id(), acquired)

    def _close(self, account, asset, lot, operation, qty: Decimal, close_price: Decimal):
        opened_by = lot.open_operation()
        self.store.close(account.id(), asset.id(), opened_by.type(), opened_by.id(), lot.acquired(), lot.open_price(),
                         qty / lot.q_adjustment(), operation.type(), operation.id(), operation.timestamp(), close_price,
                         qty, lot.p_adjustment(), lot.q_adjustment(), lot.fx_adjustment())


# ----------------------------------------------------------------------------------------------------------------------
# A replay's own lot store: the lot tables in an in-memory database attached as 'schema', outside any transaction
class ScratchLotStore(LedgerLotStore):
    def __init__(self, schema: str = 'lots_replay'):
        super().__init__(schema)
        self._schema = schema
        self._exec(f"ATTACH DATABASE :file AS {schema}", [(":file", ':memory:')])
        self._exec(f"CREATE TABLE {schema}.trades_opened (id INTEGER PRIMARY KEY UNIQUE NOT NULL, "
                   "timestamp INTEGER NOT NULL, otype INTEGER NOT NULL, oid INTEGER NOT NULL, m_otype INTEGER NOT NULL, "
                   "m_oid INTEGER NOT NULL, account_id INTEGER NOT NULL, asset_id INTEGER NOT NULL, price TEXT NOT NULL, "
                   "remaining_qty TEXT NOT NULL, c_price TEXT NOT NULL DEFAULT ('1'), c_fx TEXT NOT NULL DEFAULT ('1'), "
                   "c_qty TEXT NOT NULL DEFAULT ('1'), slice_id INTEGER, acquired INTEGER NOT NULL DEFAULT (0))")
        self._exec(f"CREATE INDEX {schema}.open_trades_by_position ON trades_opened (account_id, asset_id, timestamp)")
        self._exec(f"CREATE TRIGGER {schema}.trades_opened_set_slice AFTER INSERT ON trades_opened "
                   "WHEN NEW.slice_id IS NULL BEGIN UPDATE trades_opened SET slice_id = NEW.id WHERE id = NEW.id; END")
        self._exec(f"CREATE TABLE {schema}.trades_closed (id INTEGER PRIMARY KEY UNIQUE NOT NULL, "
                   "account_id INTEGER NOT NULL, asset_id INTEGER NOT NULL, open_otype INTEGER NOT NULL, "
                   "open_oid INTEGER NOT NULL, open_timestamp INTEGER NOT NULL, open_price TEXT NOT NULL, "
                   "open_qty TEXT NOT NULL, close_otype INTEGER NOT NULL, close_oid INTEGER NOT NULL, "
                   "close_timestamp INTEGER NOT NULL, close_price TEXT NOT NULL, close_qty TEXT NOT NULL, "
                   "c_price TEXT NOT NULL DEFAULT ('1'), c_qty TEXT NOT NULL DEFAULT ('1'), "
                   "c_fx TEXT NOT NULL DEFAULT ('1'))")

    def schema(self) -> str:
        return self._schema

    def detach(self):
        self._exec(f"DETACH DATABASE {self._schema}")


# ----------------------------------------------------------------------------------------------------------------------
# Replays the lot half of every operation of the built sequence up to 'until' into 'store', touching no ledger;
# 'progress(done, total)' is called after each part
def replay(store, policy=None, until=None, progress=None) -> LotEngine:
    engine = LotEngine(store, policy)
    until = Setup.MAX_TIMESTAMP if until is None else until
    total = JalDB._read("SELECT COUNT(*) FROM ledger_sequence WHERE timestamp <= :until", [(":until", until)]) \
        if progress is not None else 0
    query = JalDB._exec("SELECT o.otype, s.operation_id AS oid, s.opart FROM ledger_sequence AS s "
                        "JOIN operations AS o ON o.id=s.operation_id WHERE s.timestamp <= :until ORDER BY s.seq_no",
                        [(":until", until)])
    done = 0
    try:
        while query.next():
            otype, oid, opart = JalDB._read_record(query)
            jal.db.operations.LedgerTransaction.get_operation(otype, oid, opart).process_lots(engine)
            done += 1
            if progress is not None:
                progress(done, total)
    finally:
        query.finish()   # an active statement on the store would keep it from being detached after a stop
    return engine
