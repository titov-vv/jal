from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, create_bridges, create_transfers, \
    create_quotes
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.bridge_matcher import BridgeMatcher, BridgeMatchError
from jal.db.operations import LedgerTransaction

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


# The matching path (#47): a bridge arrival can't be recognized by the fetcher, so it lands as a plain incoming
# transfer; the user adopts it as the pending sending half's receiving leg, and the transfer is consumed.
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


# Adoption is refused when the pair can't form a valid operation - here the asset arrives before it was sent, and
# below it arrives on the very account it left (nothing crossed chains).
def test_adopt_transfer_rejects_mismatch(accounts):
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210105), 'out_acc': ACC1, 'out_qty': 2}])[0]
    transfer_oid = create_transfers([(d2t(210104), ACC3, 2, ACC2, 0, USDC)])[0]   # arrived a day too early
    with pytest.raises(BridgeMatchError):
        BridgeMatcher().match_with_transfer(send_oid, transfer_oid)

    back_to_source = create_transfers([(d2t(210106), ACC3, 2, ACC1, 0, ETH)])[0]   # arrived where it left from
    with pytest.raises(BridgeMatchError):
        BridgeMatcher().match_with_transfer(send_oid, back_to_source)


# ----------------------------------------------------------------------------------------------------------------------
# An asset-changing pair is not a bridge but an exchange (#44): matching it creates a cross-chain Swap instead, which
# realizes the disposal of what was sent and opens what arrived on the destination account at those proceeds.

# The usual shape: a recognized sending half plus the arriving asset, which the fetcher imported as a plain transfer.
def test_adopting_another_asset_creates_cross_chain_swap(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])   # 3 ETH @1000
    create_quotes(ETH, 2, [(d2t(210103), 1200.0)])                             # ETH is worth 1200 when sent
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])[0]
    transfer_oid = create_transfers([(d2t(210104), ACC3, 2400, ACC2, 0, USDC)])[0]   # 2400 USDC arrive on ACC2

    assert BridgeMatcher().pair_kind(send_oid, transfer_oid) == BridgeMatcher.SWAP
    swap_oid = BridgeMatcher().match_with_transfer(send_oid, transfer_oid)
    Ledger().rebuild(from_timestamp=0)

    # Both source operations are consumed and replaced by one swap
    assert JalDB._read("SELECT COUNT(*) FROM transfers WHERE oid=:o", [(":o", transfer_oid)]) == 0
    assert JalDB._read("SELECT COUNT(*) FROM bridges WHERE oid=:o", [(":o", send_oid)]) == 0
    assert JalDB._read("SELECT COUNT(*) FROM swaps WHERE oid=:o", [(":o", swap_oid)]) == 1

    assert _open_qty(ACC1) == Decimal('1')                       # 2 of the 3 ETH were disposed
    assert _open_qty(ACC2, USDC) == Decimal('2400')              # and the proceeds arrived as USDC on ACC2
    assert _open_basis(ACC2, USDC) == Decimal('2400')            # 2 * 1200 of proceeds, i.e. 1 per USDC
    # The disposal realized the gain on the source account: 2 * (1200 - 1000)
    deals = JalAccount(ACC1).closed_trades_list(close_otypes=(LedgerTransaction.Trade, LedgerTransaction.Swap))
    assert len(deals) == 1 and deals[0].profit() == Decimal('400')


# The gas paid by the sending half rides into the swap it becomes (it was burned to make that exchange happen).
def test_cross_chain_swap_keeps_the_gas_of_its_sending_half(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_quotes(ETH, 2, [(d2t(210103), 1200.0)])
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2,
                                'fee_asset': ETH, 'fee_qty': '0.01'}])[0]
    transfer_oid = create_transfers([(d2t(210104), ACC3, 2400, ACC2, 0, USDC)])[0]

    swap_oid = BridgeMatcher().match_with_transfer(send_oid, transfer_oid)
    Ledger().rebuild(from_timestamp=0)

    fee = JalDB._read("SELECT fee_qty FROM swaps WHERE oid=:o", [(":o", swap_oid)])
    assert Decimal(fee) == Decimal('0.01')
    assert _open_qty(ACC1) == Decimal('0.99')                    # 3 - 2 sent - 0.01 burned as gas


# ----------------------------------------------------------------------------------------------------------------------
# A crossing whose two ends disagree about WHEN it happened.
#
# It is what a venue that keeps its own ledger produces: a Hyperliquid withdrawal names the ARBITRUM transaction that
# released the coins on both of its ends, while the moment its own books carry is the moment HL recorded observing
# that block - 8 to 22 seconds after it, measured on every movement of the wallet this was built from, in both
# directions. On a deposit the lag is invisible (chain first, venue second); on a withdrawal it puts the arrival
# BEFORE the departure and the pair stops being offered at all.
HASH = '0x' + 'd8' * 32
OTHER_HASH = '0x' + 'ab' * 32


def test_a_pair_of_one_transaction_is_matched_despite_the_order(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    landing = d2t(210104)
    # the venue stamped its books 11 seconds AFTER the block that released the coins
    send_oid = create_bridges([{'asset': ETH, 'out_ts': landing + 11, 'out_acc': ACC1, 'out_qty': 2,
                                'out_hash': HASH}])[0]
    transfer_oid = create_transfers([(landing, ACC3, 2, ACC2, 0, ETH, HASH)])[0]

    matcher = BridgeMatcher()
    assert matcher.pair_kind(send_oid, transfer_oid) == BridgeMatcher.BRIDGE
    # Both directions have to OFFER it - the candidate list is where this was invisible, and it builds its own
    # arrival record rather than going through _transfer_side()
    assert transfer_oid in matcher.transfer_candidates(send_oid)
    assert send_oid in matcher.halves_claiming(transfer_oid)

    matcher.match_with_transfer(send_oid, transfer_oid)
    stored = JalDB._read("SELECT out_timestamp || '/' || in_timestamp FROM bridges WHERE oid=:o", [(":o", send_oid)])
    # Both ends are stamped with the EARLIER reading: a record of an event never precedes it, so of two readings of
    # one transaction the earlier is the closer to the block that carried it.
    assert stored == f"{landing}/{landing}"

    Ledger().rebuild(from_timestamp=0)      # ... and what was stored is something the ledger accepts
    assert _open_qty(ACC1) == Decimal('1')
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')


# Without the shared transaction the two moments are two EVENTS, and an arrival that precedes its departure is
# refused exactly as before - the waiver must not become a general loosening of the ordering rule.
def test_a_wrong_order_without_one_transaction_is_still_refused(accounts):
    landing = d2t(210104)
    send_oid = create_bridges([{'asset': ETH, 'out_ts': landing + 11, 'out_acc': ACC1, 'out_qty': 2,
                                'out_hash': HASH}])[0]
    transfer_oid = create_transfers([(landing, ACC3, 2, ACC2, 0, ETH, OTHER_HASH)])[0]

    matcher = BridgeMatcher()
    assert matcher.pair_kind(send_oid, transfer_oid) is None
    assert transfer_oid not in matcher.transfer_candidates(send_oid)
    assert send_oid not in matcher.halves_claiming(transfer_oid)
    with pytest.raises(BridgeMatchError):
        matcher.match_with_transfer(send_oid, transfer_oid)


# Two legs that name NO transaction are not "one transaction" either - an empty hash equals an empty hash, and
# taking that as proof would pair every hand-entered leg with every other one.
def test_legs_naming_no_transaction_are_not_one_transaction(accounts):
    landing = d2t(210104)
    send_oid = create_bridges([{'asset': ETH, 'out_ts': landing + 11, 'out_acc': ACC1, 'out_qty': 2}])[0]
    transfer_oid = create_transfers([(landing, ACC3, 2, ACC2, 0, ETH)])[0]

    matcher = BridgeMatcher()
    assert matcher.pair_kind(send_oid, transfer_oid) is None
    with pytest.raises(BridgeMatchError):
        matcher.match_with_transfer(send_oid, transfer_oid)


# A pair whose moments are in the RIGHT order is stamped with nothing agreed - each end keeps its own reading, which
# is the duration the crossing really took.
def test_a_pair_in_the_right_order_keeps_both_moments(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    departure = d2t(210103)
    send_oid = create_bridges([{'asset': ETH, 'out_ts': departure, 'out_acc': ACC1, 'out_qty': 2,
                                'out_hash': HASH}])[0]
    transfer_oid = create_transfers([(departure + 300, ACC3, 2, ACC2, 0, ETH, HASH)])[0]

    BridgeMatcher().match_with_transfer(send_oid, transfer_oid)
    stored = JalDB._read("SELECT out_timestamp || '/' || in_timestamp FROM bridges WHERE oid=:o", [(":o", send_oid)])
    assert stored == f"{departure}/{departure + 300}"


# The agreed moment reaches a cross-chain SWAP as well: an acquisition that precedes its own disposal is as wrong
# there as a bridge receive that precedes its send, and the swap is built from the half rather than updated in place.
def test_the_agreed_moment_reaches_a_cross_chain_swap(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_quotes(ETH, 2, [(d2t(210103), 1200.0)])
    landing = d2t(210104)
    send_oid = create_bridges([{'asset': ETH, 'out_ts': landing + 11, 'out_acc': ACC1, 'out_qty': 2,
                                'out_hash': HASH}])[0]
    transfer_oid = create_transfers([(landing, ACC3, 2400, ACC2, 0, USDC, HASH)])[0]

    assert BridgeMatcher().pair_kind(send_oid, transfer_oid) == BridgeMatcher.SWAP
    swap_oid = BridgeMatcher().match_with_transfer(send_oid, transfer_oid)
    stored = JalDB._read("SELECT timestamp || '/' || in_timestamp FROM swaps WHERE oid=:o", [(":o", swap_oid)])
    assert stored == f"{landing}/{landing}"

    Ledger().rebuild(from_timestamp=0)
    assert _open_qty(ACC2, USDC) == Decimal('2400')
