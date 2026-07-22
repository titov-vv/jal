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
