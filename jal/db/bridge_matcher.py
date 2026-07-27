from decimal import Decimal
from PySide6.QtWidgets import QApplication
from jal.db.db import JalDB
from jal.db.helpers import remove_exponent
from jal.db.operations import LedgerTransaction


class BridgeMatchError(Exception):
    pass


# ----------------------------------------------------------------------------------------------------------------------
# Completes a cross-chain move from its two legs, which reach JAL as two unrelated operations.
# Only the SENDING leg is recognizable at import time - it is the wallet's own transaction into a known
# bridge/aggregator - and it waits as a "pending half-bridge" (a 'bridges' row with its in_* leg still NULL). The
# ARRIVING leg is not recognizable: whoever delivers it, it looks exactly like any other incoming transfer, and
# nothing in it says what was sent for it, so it is imported as a plain transfer. Matching therefore always pairs one
# pending half with one existing transfer, and the user decides the pair - see match_with_transfer().
#
# What the pair moves decides which operation it becomes, and this is the only place that can tell:
#   * the SAME asset (one JAL asset_id - cross-chain token unification already merges a token's per-chain listings)
#     -> a Bridge: the arriving leg is filled in on the pending row, the cost basis is carried and nothing realized;
#   * a DIFFERENT asset -> a cross-chain Swap: a genuine disposal of what was sent, realized at market value, with
#     the proceeds opening the arrived asset on the destination account. The pending half is consumed by it.
# Nothing is ever paired automatically: an arriving transfer of the right asset and size may just as well be an
# unrelated receipt, and a wrong pairing mis-books money - so the choice is always the user's.
class BridgeMatcher(JalDB):
    BRIDGE = 'bridge'   # what a matched pair becomes: the same asset moved across chains
    SWAP = 'swap'       # ... or an asset-changing exchange, i.e. a cross-chain swap

    def __init__(self):
        super().__init__()

    def tr(self, text):
        return QApplication.translate("BridgeMatcher", text)

    # All pending half-bridges - a sending leg whose arrival is still awaited - each as a dict describing that leg
    def _pending_halves(self) -> list:
        halves = []
        query = self._exec(
            "SELECT b.oid, b.out_account_id AS account_id, s.asset_id AS asset_id, b.out_qty AS qty, "
            "b.out_timestamp AS timestamp "
            "FROM bridges b JOIN asset_symbol s ON s.id=b.out_symbol_id WHERE b.in_account_id IS NULL")
        while query.next():
            oid, account_id, asset_id, qty, timestamp = self._read_record(
                query, cast=[int, int, int, Decimal, int])
            halves.append({'oid': oid, 'account_id': account_id, 'asset_id': asset_id,
                           'qty': qty, 'timestamp': timestamp})
        return halves

    @staticmethod
    def _find(halves, oid):
        for h in halves:
            if h['oid'] == oid:
                return h
        return None

    # The operation a pair would become (BRIDGE or SWAP), or None if the two legs can't form one at all. Both are
    # moves between two different accounts (chains) whose arrival doesn't precede its departure; then the asset
    # decides: the same one crossed chains (a bridge, which can't deliver more than was sent), a different one was
    # acquired in exchange (a cross-chain swap, where the two quantities are unrelated).
    @staticmethod
    def _pair_kind(out_h, in_h):
        if out_h['account_id'] == in_h['account_id']:
            return None
        if out_h['timestamp'] > in_h['timestamp']:     # an arrival can't precede its departure
            return None
        if out_h['qty'] <= Decimal('0') or in_h['qty'] <= Decimal('0'):
            return None
        if out_h['asset_id'] != in_h['asset_id']:
            return BridgeMatcher.SWAP
        return BridgeMatcher.BRIDGE if in_h['qty'] <= out_h['qty'] else None   # can't receive more than was sent

    # The operation the pending half 'oid' would form with the transfer 'transfer_oid' (BRIDGE or SWAP), or None if
    # they can't be matched at all. Used by the UI to name what accepting a candidate is going to create.
    def pair_kind(self, oid, transfer_oid):
        half = self._find(self._pending_halves(), oid)
        if half is None:
            return None
        arrival = self._transfer_side(transfer_oid)
        if arrival is None:
            return None
        return self._pair_kind(half, arrival)

    # The same question for an arriving leg that is described rather than stored (see match_with_leg): what the pending
    # half 'oid' would become if that leg completed it, or None if it cannot.
    def leg_kind(self, oid, arrival: dict):
        half = self._find(self._pending_halves(), oid)
        if half is None:
            return None
        return self._pair_kind(half, arrival)

    # oids of existing asset Transfers that could complete the pending half 'oid'. Transfers of ANY asset are offered:
    # the same one completes a bridge, a different one makes the pair a cross-chain swap (pair_kind() tells which).
    # Closest in time first, as that is the likeliest counterpart.
    # A transfer whose own arriving side is still unknown ('deposit_account' NULL) has no arrival to donate, so it is
    # not a candidate - it is itself waiting to be settled.
    def transfer_candidates(self, oid) -> list:
        half = self._find(self._pending_halves(), oid)
        if half is None:
            return []
        result = []
        query = self._exec(
            "SELECT t.oid, t.withdrawal, t.deposit_timestamp, t.deposit_account, s.asset_id "
            "FROM transfers t JOIN asset_symbol s ON s.id=t.symbol_id "
            "WHERE NOT t.deposit_account IS NULL "
            "ORDER BY ABS(t.deposit_timestamp - :ts)", [(":ts", half['timestamp'])])
        while query.next():
            toid, qty, d_ts, d_acc, asset_id = self._read_record(query, cast=[int, Decimal, int, int, int])
            arrival = {'account_id': d_acc, 'asset_id': asset_id, 'qty': qty, 'timestamp': d_ts}
            if self._pair_kind(half, arrival) is not None:
                result.append(toid)
        return result

    # Completes a pending half-bridge from an existing asset Transfer - the arriving leg, which the fetcher can only
    # import as a plain transfer. The transfer's deposit (arrival) side either fills the half's missing leg, when both
    # carry the same asset, or - when the asset changed on the way - becomes the receiving leg of a new cross-chain
    # Swap that replaces the half. Either way the whole transfer is consumed (both its legs collapse into the
    # completed operation).
    # Raises BridgeMatchError if the half isn't pending, the operation isn't an asset transfer, or they don't form a
    # valid pair. Returns the oid of the resulting operation; the caller must rebuild the ledger afterwards.
    def match_with_transfer(self, half_oid, transfer_oid) -> int:
        half = self._find(self._pending_halves(), half_oid)
        if half is None:
            raise BridgeMatchError(self.tr("The operation to complete must be a pending half-bridge"))
        # A money transfer has no symbol - only an asset transfer can be a leg of a bridge or of a swap
        arrival = self._transfer_side(transfer_oid)
        if arrival is None:
            raise BridgeMatchError(self.tr("A leg can only be adopted from an asset transfer"))
        oid = self._adopt(half, half_oid, arrival)
        self._exec("DELETE FROM transfers WHERE oid=:oid", [(":oid", transfer_oid)], commit=True)
        return oid

    # Completes a pending half-bridge from an arriving leg that is DESCRIBED rather than already stored as a transfer:
    # 'arrival' holds account_id / asset_id / symbol_id / qty / timestamp / tx_hash, the same shape _transfer_side()
    # returns. It is the path for an arrival JAL has not fetched (and may never be able to fetch: the destination chain
    # can be one JAL has no fetcher for), whose facts come from the aggregator that routed the move - see
    # jal/net/arrival_reconciler.py. Nothing distinguishes the operation it produces from one matched by hand; what
    # differs is only where the arriving leg's numbers came from, and the leg carries the destination transaction hash,
    # which is what lets a later fetch of that chain recognize the arrival as already booked (see reconcile_arrival()).
    # Raises BridgeMatchError on the same terms as match_with_transfer(); returns the oid of the resulting operation.
    def match_with_leg(self, half_oid, arrival: dict) -> int:
        half = self._find(self._pending_halves(), half_oid)
        if half is None:
            raise BridgeMatchError(self.tr("The operation to complete must be a pending half-bridge"))
        return self._adopt(half, half_oid, arrival)

    # Applies an arriving leg to a pending half, whatever the leg was described by. What the pair moves decides the
    # operation: the same asset completes the bridge in place, a different one turns the half into a cross-chain swap.
    def _adopt(self, half: dict, half_oid, arrival: dict) -> int:
        kind = self._pair_kind(half, arrival)
        if kind is None:
            raise BridgeMatchError(self.tr("The arriving leg doesn't match by asset, account, amount or dates"))
        leg = {'in_timestamp': arrival['timestamp'], 'in_account_id': arrival['account_id'],
               'in_symbol_id': arrival['symbol_id'], 'in_qty': arrival['qty'], 'in_tx_hash': arrival['tx_hash']}
        if kind == self.SWAP:
            oid = self._create_swap(half_oid, leg)
            self._exec("DELETE FROM bridges WHERE oid=:oid", [(":oid", half_oid)], commit=True)
            return oid
        self._exec("UPDATE bridges SET in_timestamp=:ts, in_account_id=:acc, in_symbol_id=:sym, in_qty=:qty, "
                   "in_tx_hash=:hash WHERE oid=:oid",
                   [(":ts", leg['in_timestamp']), (":acc", leg['in_account_id']), (":sym", leg['in_symbol_id']),
                    (":qty", leg['in_qty']), (":hash", leg['in_tx_hash']), (":oid", half_oid)], commit=True)
        return half_oid

    # Builds a cross-chain Swap out of a pending SEND half (which holds the disposed asset and the gas paid for it)
    # and the arriving leg described by 'in_leg' (in_timestamp/in_account_id/in_symbol_id/in_qty/in_tx_hash).
    def _create_swap(self, out_oid, in_leg: dict) -> int:
        out = self._read("SELECT out_timestamp, out_account_id, out_symbol_id, out_qty, out_tx_hash, "
                         "fee_symbol_id, fee_qty, note FROM bridges WHERE oid=:oid", [(":oid", out_oid)], named=True)
        present = lambda v: v is not None and v != ''   # _read() returns '' (not None) for a SQL NULL
        data = {'timestamp': int(out['out_timestamp']), 'account_id': int(out['out_account_id']),
                'tx_hash': out['out_tx_hash'], 'out_symbol_id': int(out['out_symbol_id']),
                'out_qty': Decimal(out['out_qty']), 'in_timestamp': int(in_leg['in_timestamp']),
                'in_account_id': int(in_leg['in_account_id']), 'in_symbol_id': int(in_leg['in_symbol_id']),
                'in_qty': Decimal(in_leg['in_qty']), 'in_tx_hash': in_leg['in_tx_hash']}
        if present(out['fee_symbol_id']) and present(out['fee_qty']):   # the gas of the sending transaction
            data['fee_symbol_id'] = int(out['fee_symbol_id'])
            data['fee_qty'] = Decimal(out['fee_qty'])
        if present(out['note']):
            data['note'] = out['note']
        return LedgerTransaction.create_new(LedgerTransaction.Swap, data).oid()

    # ------------------------------------------------------------------------------------------------------------------
    # An arriving leg that is already booked can be met a second time, as a transaction of the chain it landed on.
    #
    # match_with_leg() books an arrival from what the routing aggregator reported, which may happen long before - or
    # instead of - the destination chain ever being fetched. When that chain IS fetched afterwards, the very same
    # arrival comes back as an ordinary incoming transfer, and storing it would credit the assets twice. The two are
    # recognized as one movement by the transaction hash of the arriving leg together with the asset it moved: one
    # transaction may deliver several assets at once (a token plus a gas top-up), and only the one that was booked
    # must be swallowed - the others are movements of their own and have to be stored.

    # The bridge or swap whose ARRIVING leg is the given transaction and asset, as {'table', 'oid', 'account_id',
    # 'qty', 'timestamp'}, or None when no operation holds it.
    def _adopted_leg(self, tx_hash: str, symbol_id):
        if not tx_hash or not symbol_id:
            return None
        for table in ('bridges', 'swaps'):
            row = self._read(f"SELECT oid, in_account_id, in_qty, in_timestamp FROM {table} "
                             "WHERE in_tx_hash=:hash AND in_symbol_id=:sym AND in_account_id IS NOT NULL",
                             [(":hash", tx_hash), (":sym", symbol_id)], named=True)
            if row:
                return {'table': table, 'oid': int(row['oid']), 'account_id': int(row['in_account_id']),
                        'qty': Decimal(row['in_qty']), 'timestamp': int(row['in_timestamp'])}
        return None

    # Recognizes a freshly fetched arrival as the leg of a cross-chain operation that is already booked, and checks
    # what was booked against what the chain now says. The chain is the authority - the aggregator's report was only
    # ever a description of it - so a quantity or a time that differs is corrected here, while a difference that
    # cannot be corrected without changing which account holds the assets is reported and left alone for the user.
    #
    # Returns (recognized, complaint): 'recognized' means the movement is already in the ledger and the transfer must
    # not be stored again; 'complaint' is '' when the two agree, and otherwise says what differed and what was done.
    def reconcile_arrival(self, tx_hash: str, symbol_id, account_id: int, qty: Decimal, timestamp: int) -> tuple:
        booked = self._adopted_leg(tx_hash, symbol_id)
        if booked is None:
            return False, ''
        where = self.tr("Arriving leg of ") + f"{booked['table']}#{booked['oid']}"
        if booked['account_id'] != int(account_id):
            # Which account holds the arrived assets decides where they are booked; changing it here would move a
            # position between accounts behind the user's back, so only the disagreement is reported.
            return True, where + self.tr(" is booked on ") + self._account_name(booked['account_id']) \
                + self.tr(" while the chain delivered it to ") + self._account_name(int(account_id)) \
                + self.tr(" - correct it by hand")
        amended = []
        if booked['qty'] != qty:
            if not self._amend_leg(booked, 'in_qty', qty):
                return True, where + self.tr(" says ") + f"{remove_exponent(booked['qty'])}" \
                    + self.tr(" while the chain reports ") + f"{remove_exponent(qty)}" \
                    + self.tr(", and the difference can't be applied - correct it by hand")
            amended.append(self.tr("quantity ") + f"{remove_exponent(booked['qty'])} -> {remove_exponent(qty)}")
        if booked['timestamp'] != int(timestamp) and self._amend_leg(booked, 'in_timestamp', int(timestamp)):
            amended.append(self.tr("time ") + f"{booked['timestamp']} -> {int(timestamp)}")
        if not amended:
            return True, ''
        return True, where + self.tr(" was corrected from the chain: ") + ", ".join(amended)

    def _account_name(self, account_id: int) -> str:
        return self._read("SELECT name FROM accounts WHERE id=:id", [(":id", account_id)]) or f"#{account_id}"

    # Writes one field of an already booked arriving leg, unless doing so would leave the operation invalid: an
    # arrival may not precede its departure, may not be empty, and a bridge may not deliver more than it was sent.
    # Returns whether the value was applied.
    def _amend_leg(self, booked: dict, field: str, value) -> bool:
        table, oid = booked['table'], booked['oid']
        if field == 'in_qty':
            if value <= Decimal('0'):
                return False
            if table == 'bridges' and value > Decimal(self._read("SELECT out_qty FROM bridges WHERE oid=:oid",
                                                                 [(":oid", oid)])):
                return False
        if field == 'in_timestamp':
            sent = self._read(f"SELECT {'out_timestamp' if table == 'bridges' else 'timestamp'} FROM {table} "
                              "WHERE oid=:oid", [(":oid", oid)])
            if int(value) < int(sent):
                return False
        self._exec(f"UPDATE {table} SET {field}=:value WHERE oid=:oid",
                   [(":value", value), (":oid", oid)], commit=True)
        return True

    # ------------------------------------------------------------------------------------------------------------------
    # The arriving (deposit) side of an existing asset transfer, described the way a pending half is, so that the two
    # can be compared. Returns None if the operation isn't an asset transfer - a money transfer can't be a leg here -
    # or if its own arriving side is still unknown, in which case there is no arrival to adopt.
    def _transfer_side(self, transfer_oid):
        t = self._read("SELECT deposit_timestamp, deposit_account, withdrawal, symbol_id, number "
                       "FROM transfers WHERE oid=:oid", [(":oid", transfer_oid)], named=True)
        if not t or not t['symbol_id'] or not t['deposit_account']:
            return None
        asset_id = self._read("SELECT asset_id FROM asset_symbol WHERE id=:sym", [(":sym", t['symbol_id'])])
        # For an asset transfer the moved quantity is carried by 'withdrawal' on both legs; 'deposit' holds the cost
        # basis, which a bridge re-derives itself and a swap replaces with the proceeds of the disposal.
        return {'account_id': t['deposit_account'], 'timestamp': t['deposit_timestamp'], 'asset_id': int(asset_id),
                'qty': Decimal(t['withdrawal']), 'symbol_id': t['symbol_id'], 'tx_hash': t['number']}
