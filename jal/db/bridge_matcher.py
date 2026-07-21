from decimal import Decimal
from PySide6.QtWidgets import QApplication
from jal.db.db import JalDB


class BridgeMatchError(Exception):
    pass


# ----------------------------------------------------------------------------------------------------------------------
# Pairs the two half-bridges of one cross-chain move (a send on the source chain and a receive on the destination
# chain) that were imported separately and possibly in either order (see the Bridge operation). Works entirely on the
# 'bridges' table: a pending half is a row with exactly one leg present. Matching fills the send-half's receive leg
# from the receive-half and drops the receive-half, leaving one complete bridge; the caller then rebuilds the ledger.
#
# Only same-asset moves are matched here: "same asset across chains" is one JAL asset_id (cross-chain token unification
# already merges a token's per-chain listings into one asset). Asset-changing cross-chain exchanges (a real disposal)
# belong with the Swap operation and are intentionally left pending - they are never auto-resolved into a bridge.
class BridgeMatcher(JalDB):
    # Heuristics for a *confident* automatic match. A manual match (BridgeMatcher.match) is not bound by them - the
    # user may pair any two halves that form a valid bridge (same asset, different accounts, received <= sent, receive
    # not before send).
    TIME_WINDOW = 3 * 24 * 60 * 60      # a receive is auto-matched only to a send at most 3 days older
    QTY_TOLERANCE = Decimal('0.05')     # ... and only if it received at least 95% of what was sent (bridge fee margin)

    def __init__(self):
        super().__init__()

    def tr(self, text):
        return QApplication.translate("BridgeMatcher", text)

    # All pending half-bridges (exactly one leg present), each as a dict describing its present leg
    def _pending_halves(self) -> list:
        halves = []
        query = self._exec(
            "SELECT b.oid, "
            "CASE WHEN b.out_account_id IS NOT NULL THEN 1 ELSE 0 END AS is_out, "
            "COALESCE(b.out_account_id, b.in_account_id) AS account_id, "
            "s.asset_id AS asset_id, "
            "COALESCE(b.out_qty, b.in_qty) AS qty, "
            "COALESCE(b.out_timestamp, b.in_timestamp) AS timestamp "
            "FROM bridges b JOIN asset_symbol s ON s.id=COALESCE(b.out_symbol_id, b.in_symbol_id) "
            "WHERE (b.out_account_id IS NULL)<>(b.in_account_id IS NULL)")   # exactly one leg present
        while query.next():
            oid, is_out, account_id, asset_id, qty, timestamp = self._read_record(
                query, cast=[int, int, int, int, Decimal, int])
            halves.append({'oid': oid, 'is_out': bool(is_out), 'account_id': account_id,
                           'asset_id': asset_id, 'qty': qty, 'timestamp': timestamp})
        return halves

    @staticmethod
    def _find(halves, oid):
        for h in halves:
            if h['oid'] == oid:
                return h
        return None

    # A pair is a valid bridge if it moves one asset between two different accounts and receives no more than was sent
    @staticmethod
    def _valid_pair(out_h, in_h) -> bool:
        return (out_h['account_id'] != in_h['account_id']
                and out_h['asset_id'] == in_h['asset_id']      # same asset only (asset-changing bridges are deferred)
                and out_h['timestamp'] <= in_h['timestamp']    # a receive can't precede its send
                and in_h['qty'] <= out_h['qty'])               # can't receive more than was sent

    # A pair is transparent (safe to auto-match) if it is valid AND arrives within the time window having lost no more
    # than the fee tolerance to the bridge
    def _transparent(self, out_h, in_h) -> bool:
        return (self._valid_pair(out_h, in_h)
                and in_h['timestamp'] <= out_h['timestamp'] + self.TIME_WINDOW
                and in_h['qty'] >= out_h['qty'] * (Decimal('1') - self.QTY_TOLERANCE))

    # oids of pending halves that could be matched to the pending half 'oid' (hard validity only; the UI ranks by
    # amount/time proximity). Empty if 'oid' isn't a pending half.
    def candidates(self, oid) -> list:
        halves = self._pending_halves()
        target = self._find(halves, oid)
        if target is None:
            return []
        result = []
        for h in halves:
            if h['oid'] == oid or h['is_out'] == target['is_out']:
                continue
            out_h, in_h = (target, h) if target['is_out'] else (h, target)
            if self._valid_pair(out_h, in_h):
                result.append(h['oid'])
        return result

    # oids of existing asset Transfers that could complete the pending half 'oid' via match_with_transfer (the manual
    # escape hatch for a bridge leg the fetcher imported as a plain transfer). Same asset, right direction, and forming
    # a valid bridge; the UI ranks them by amount/time proximity.
    def transfer_candidates(self, oid) -> list:
        half = self._find(self._pending_halves(), oid)
        if half is None:
            return []
        result = []
        query = self._exec(
            "SELECT t.oid, t.withdrawal_timestamp, t.withdrawal_account, t.withdrawal, t.deposit_timestamp, "
            "t.deposit_account, s.asset_id FROM transfers t JOIN asset_symbol s ON s.id=t.symbol_id "
            "WHERE s.asset_id=:asset", [(":asset", half['asset_id'])])
        while query.next():
            toid, w_ts, w_acc, w_qty, d_ts, d_acc, asset_id = self._read_record(
                query, cast=[int, int, int, Decimal, int, int, int])
            if half['is_out']:   # the transfer's deposit (arrival) side would become the receive leg
                other = {'account_id': d_acc, 'asset_id': asset_id, 'qty': w_qty, 'timestamp': d_ts}
                ok = self._valid_pair(half, other)
            else:                # the transfer's withdrawal (departure) side would become the send leg
                other = {'account_id': w_acc, 'asset_id': asset_id, 'qty': w_qty, 'timestamp': w_ts}
                ok = self._valid_pair(other, half)
            if ok:
                result.append(toid)
        return result

    # Automatically matches every pending half that has EXACTLY ONE transparent counterpart which, in turn, has only
    # this half as its transparent counterpart (mutually unambiguous). Ambiguous or unmatched halves are left pending
    # for manual matching - a wrong automatic pairing would mis-book money, so ambiguity always defers to the user.
    # Returns the number of bridges completed; the caller must rebuild the ledger afterwards.
    def auto_match(self) -> int:
        halves = self._pending_halves()
        outs = [h for h in halves if h['is_out']]
        ins = [h for h in halves if not h['is_out']]
        used = set()
        matched = 0
        for o in outs:
            if o['oid'] in used:
                continue
            o_cands = [i for i in ins if i['oid'] not in used and self._transparent(o, i)]
            if len(o_cands) != 1:
                continue
            i = o_cands[0]
            i_cands = [oo for oo in outs if oo['oid'] not in used and self._transparent(oo, i)]
            if len(i_cands) != 1:   # the receive must be unambiguous too
                continue
            self.match(o['oid'], i['oid'])
            used.add(o['oid'])
            used.add(i['oid'])
            matched += 1
        return matched

    # Fuses two complementary pending halves into one complete bridge: fills the send-half's receive leg from the
    # receive-half and deletes the receive-half. Works whichever of 'oid_a'/'oid_b' is the send or the receive.
    # Raises BridgeMatchError if they don't form a valid bridge. Returns the oid of the surviving complete bridge;
    # the caller must rebuild the ledger afterwards.
    def match(self, oid_a, oid_b) -> int:
        halves = self._pending_halves()
        a = self._find(halves, oid_a)
        b = self._find(halves, oid_b)
        if a is None or b is None:
            raise BridgeMatchError(self.tr("Both operations must be pending half-bridges to be matched"))
        if a['is_out'] == b['is_out']:
            raise BridgeMatchError(self.tr("A bridge is matched from one send half and one receive half"))
        out_h, in_h = (a, b) if a['is_out'] else (b, a)
        if not self._valid_pair(out_h, in_h):
            raise BridgeMatchError(self.tr("These half-bridges don't match by asset, account, amount or dates"))
        leg = self._read("SELECT in_timestamp, in_account_id, in_symbol_id, in_qty, in_tx_hash "
                         "FROM bridges WHERE oid=:oid", [(":oid", in_h['oid'])], named=True)
        self._exec("UPDATE bridges SET in_timestamp=:ts, in_account_id=:acc, in_symbol_id=:sym, in_qty=:qty, "
                   "in_tx_hash=:hash WHERE oid=:oid",
                   [(":ts", leg['in_timestamp']), (":acc", leg['in_account_id']), (":sym", leg['in_symbol_id']),
                    (":qty", leg['in_qty']), (":hash", leg['in_tx_hash']), (":oid", out_h['oid'])], commit=True)
        self._exec("DELETE FROM bridges WHERE oid=:oid", [(":oid", in_h['oid'])], commit=True)
        return out_h['oid']

    # Completes a pending half-bridge from an existing asset Transfer instead of another half. This is the manual path
    # for a bridge whose receive leg the fetcher couldn't recognize as a bridge (a relayer delivered it, so it was
    # imported as a plain incoming transfer): the user points the pending send-half at that transfer. It is symmetric -
    # a pending receive-half can adopt an outgoing transfer as its send leg. The relevant side of the transfer fills
    # the half's missing leg and the whole transfer is removed (both its legs collapse into the completed bridge).
    # Raises BridgeMatchError if the half isn't pending, the operation isn't an asset transfer, or they don't form a
    # valid bridge. Returns the oid of the completed bridge; the caller must rebuild the ledger afterwards.
    def match_with_transfer(self, half_oid, transfer_oid) -> int:
        half = self._find(self._pending_halves(), half_oid)
        if half is None:
            raise BridgeMatchError(self.tr("The bridge to complete must be a pending half-bridge"))
        t = self._read("SELECT withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, "
                       "deposit_account, symbol_id, number FROM transfers WHERE oid=:oid",
                       [(":oid", transfer_oid)], named=True)
        if not t or not t['symbol_id']:   # a money transfer has no symbol - only an asset transfer can be a bridge leg
            raise BridgeMatchError(self.tr("A bridge leg can only be adopted from an asset transfer"))
        asset_id = self._read("SELECT asset_id FROM asset_symbol WHERE id=:sym", [(":sym", t['symbol_id'])])
        # For an asset transfer the moved quantity is carried by 'withdrawal' on both legs; 'deposit' holds the cost
        # basis, which a bridge re-derives itself. The half decides which side of the transfer becomes its missing leg.
        side = {'asset_id': int(asset_id), 'qty': Decimal(t['withdrawal']), 'symbol_id': t['symbol_id'],
                'tx_hash': t['number']}
        if half['is_out']:   # pending send-half needs a receive leg -> take the transfer's deposit (arrival) side
            side['account_id'], side['timestamp'] = t['deposit_account'], t['deposit_timestamp']
            out_h, in_h, leg_prefix = half, side, 'in'
        else:                # pending receive-half needs a send leg -> take the transfer's withdrawal (departure) side
            side['account_id'], side['timestamp'] = t['withdrawal_account'], t['withdrawal_timestamp']
            out_h, in_h, leg_prefix = side, half, 'out'
        if not self._valid_pair(out_h, in_h):
            raise BridgeMatchError(self.tr("This transfer doesn't match the bridge by asset, account, amount or dates"))
        self._exec(f"UPDATE bridges SET {leg_prefix}_timestamp=:ts, {leg_prefix}_account_id=:acc, "
                   f"{leg_prefix}_symbol_id=:sym, {leg_prefix}_qty=:qty, {leg_prefix}_tx_hash=:hash WHERE oid=:oid",
                   [(":ts", side['timestamp']), (":acc", side['account_id']), (":sym", side['symbol_id']),
                    (":qty", t['withdrawal']), (":hash", side['tx_hash']), (":oid", half_oid)], commit=True)
        self._exec("DELETE FROM transfers WHERE oid=:oid", [(":oid", transfer_oid)], commit=True)
        return half_oid
