from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, create_bridges, create_transfers
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.bridge_matcher import BridgeMatcher, BridgeMatchError

# Seeded currencies are RUB=1, USD=2, EUR=3; the first two created assets get ids 4, 5
ETH, USDC = 4, 5
ACC1, ACC2, ACC3 = 1, 2, 3          # all USD wallets standing in for three chains of the same owner


@pytest.fixture
def accounts(prepare_db):
    for name in ('Chain1', 'Chain2', 'Chain3'):
        JalAccountCreator(currency_id=2, number='', name=name, investing=1, organization=1,
                          account_type=PredefinedAccountType.Broker).commit()
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0),      # ID = 4
                   ('USDC', 'USD Coin', '', 2, PredefinedAsset.Crypto, 0)])     # ID = 5
    create_actions([(d2t(210101), ACC1, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


def _open_qty(account_id, asset=ETH) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(asset))
    return sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0'))


def _open_basis(account_id, asset=ETH) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(asset))
    return sum((lot.open_qty(adjusted=True) * lot.open_price(adjusted=True) for lot in lots), Decimal('0'))


# A clean, unambiguous send+receive pair is completed automatically, and the completed bridge carries the basis.
def test_auto_match_completes_unambiguous_pair(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2},   # send half
                    {'asset': ETH, 'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': '1.99'}])  # receive half (0.5% fee)
    matched = BridgeMatcher().auto_match()
    Ledger().rebuild(from_timestamp=0)

    assert matched == 1
    assert _open_qty(ACC1) == Decimal('1')
    assert _open_qty(ACC2) == Decimal('1.99')
    assert _open_basis(ACC2) == Decimal('1990')          # 1.99 * 1000, basis carried; the 0.01 fee went to Costs


# The order in which the two halves were imported must not matter (receive imported before send).
def test_auto_match_is_order_independent(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_bridges([{'asset': ETH, 'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': 2},       # receive imported first
                    {'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])    # send imported later
    matched = BridgeMatcher().auto_match()
    Ledger().rebuild(from_timestamp=0)

    assert matched == 1
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')


# When one send could pair with two receives (or vice versa), auto-match refuses and leaves everything pending.
def test_auto_match_defers_on_ambiguity(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 5.0, 1000.0, 0.0)])
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2},
                    {'asset': ETH, 'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': 2},   # both receives are plausible
                    {'asset': ETH, 'in_ts': d2t(210105), 'in_acc': ACC3, 'in_qty': 2}])  # counterparts for the send
    assert BridgeMatcher().auto_match() == 0
    assert len(BridgeMatcher()._pending_halves()) == 3   # nothing consumed


# Different assets are never auto-matched into a bridge (that would be an asset-changing exchange - deferred to Swap).
def test_auto_match_ignores_different_assets(accounts):
    create_bridges([{'asset': ETH,  'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2},
                    {'asset': USDC, 'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': 2}])
    assert BridgeMatcher().auto_match() == 0


# Amounts too far apart (beyond the fee tolerance) or arrivals outside the time window are not auto-matched.
def test_auto_match_respects_tolerance_and_window(accounts):
    create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2},
                    {'asset': ETH, 'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': '1.5'}])   # 25% gap > 5% tolerance
    assert BridgeMatcher().auto_match() == 0
    # And a receive that lands far later than the send (beyond the 3-day window)
    create_bridges([{'asset': ETH, 'out_ts': d2t(210201), 'out_acc': ACC1, 'out_qty': 1},
                    {'asset': ETH, 'in_ts': d2t(210220), 'in_acc': ACC2, 'in_qty': 1}])        # ~19 days later
    assert BridgeMatcher().auto_match() == 0


# A manual match completes a valid pair that auto-match declined (here, a large but legitimate bridge fee).
def test_manual_match_completes_pair_auto_declined(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    out_oid, in_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2},
                                      {'asset': ETH, 'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': '1.5'}])
    assert BridgeMatcher().auto_match() == 0              # 25% gap: not confident
    assert BridgeMatcher().candidates(out_oid) == [in_oid]   # but it is a valid manual candidate

    BridgeMatcher().match(out_oid, in_oid)               # user pairs them explicitly (argument order irrelevant)
    Ledger().rebuild(from_timestamp=0)
    assert _open_qty(ACC2) == Decimal('1.5') and _open_basis(ACC2) == Decimal('1500')


# Manual match rejects pairs that can't form a valid bridge.
def test_manual_match_rejects_invalid_pairs(accounts):
    same_asset_same_dir = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2},
                                          {'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC2, 'out_qty': 2}])
    with pytest.raises(BridgeMatchError):                 # two sends, no receive
        BridgeMatcher().match(same_asset_same_dir[0], same_asset_same_dir[1])

    diff_asset = create_bridges([{'asset': ETH,  'out_ts': d2t(210110), 'out_acc': ACC1, 'out_qty': 2},
                                 {'asset': USDC, 'in_ts': d2t(210111), 'in_acc': ACC2, 'in_qty': 2}])
    with pytest.raises(BridgeMatchError):                 # asset-changing: not a bridge
        BridgeMatcher().match(diff_asset[0], diff_asset[1])

    receive_more = create_bridges([{'asset': ETH, 'out_ts': d2t(210120), 'out_acc': ACC1, 'out_qty': 2},
                                   {'asset': ETH, 'in_ts': d2t(210121), 'in_acc': ACC2, 'in_qty': 3}])
    with pytest.raises(BridgeMatchError):                 # can't receive more than sent
        BridgeMatcher().match(receive_more[0], receive_more[1])


# The manual-match escape hatch (#45): a bridge receive the fetcher couldn't recognize arrived as a plain incoming
# transfer; the user adopts that transfer as the pending send-half's receive leg, and the transfer is consumed.
def test_adopt_incoming_transfer_as_receive_leg(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])[0]
    # a plain incoming transfer to ACC2 (its source account is whatever the user assigned - here ACC3, irrelevant once
    # adopted; the bridge's real source is the send-half's account)
    transfer_oid = create_transfers([(d2t(210104), ACC3, 2, ACC2, 0, ETH)])[0]

    BridgeMatcher().match_with_transfer(send_oid, transfer_oid)
    Ledger().rebuild(from_timestamp=0)

    assert JalDB._read("SELECT COUNT(*) FROM transfers WHERE oid=:o", [(":o", transfer_oid)]) == 0   # transfer consumed
    assert _open_qty(ACC1) == Decimal('1')
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')   # basis carried from ACC1


# Symmetric: a pending receive-half adopts an outgoing transfer as its send leg.
def test_adopt_outgoing_transfer_as_send_leg(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    recv_oid = create_bridges([{'asset': ETH, 'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': 2}])[0]
    transfer_oid = create_transfers([(d2t(210103), ACC1, 2, ACC3, 0, ETH)])[0]   # ACC1 sends out (its dest irrelevant)

    BridgeMatcher().match_with_transfer(recv_oid, transfer_oid)
    Ledger().rebuild(from_timestamp=0)

    assert JalDB._read("SELECT COUNT(*) FROM transfers WHERE oid=:o", [(":o", transfer_oid)]) == 0
    assert _open_qty(ACC1) == Decimal('1')
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')


# Adoption is refused when the transfer can't form a valid bridge (a different asset here).
def test_adopt_transfer_rejects_mismatch(accounts):
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])[0]
    transfer_oid = create_transfers([(d2t(210104), ACC3, 2, ACC2, 0, USDC)])[0]   # USDC, not ETH
    with pytest.raises(BridgeMatchError):
        BridgeMatcher().match_with_transfer(send_oid, transfer_oid)
