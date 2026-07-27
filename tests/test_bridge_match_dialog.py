import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
from jal.db.bridge_matcher import BridgeMatcher
from jal.net.arrival_reconciler import ArrivalReconciler
from jal.net.route_resolvers import RouteResolvers
from jal.widgets.bridge_match_dialog import BridgeMatchDialog

ETH, USDC = 4, 5
ACC1, ACC2, ACC3 = 1, 2, 3


# The dialog asks whoever routed the move what arrived, and here nobody did: these operations have no transaction
# hash to ask about, and what is under test is the choice the USER is offered. Handing it a reconciler with no
# sources behind it is how that is said - and it is the same injection a caller that already asked would use.
def _dialog(half_oid) -> BridgeMatchDialog:
    return BridgeMatchDialog(half_oid, reconciler=ArrivalReconciler(RouteResolvers([])))


@pytest.fixture
def accounts(prepare_db):
    for name in ('Chain1', 'Chain2', 'Chain3'):
        JalAccountCreator(currency_id=2, number='', name=name, investing=1, organization=1,
                          account_type=PredefinedAccountType.Broker).commit()
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0),      # ID = 4
                   ('USDC', 'USD Coin', '', 2, PredefinedAsset.Crypto, 0)])     # ID = 5
    create_actions([(d2t(210101), ACC1, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


def _open_qty(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0'))


def _open_basis(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) * lot.open_price(adjusted=True) for lot in lots), Decimal('0'))


# The dialog offers the incoming transfers that could be the arrival; adopting one completes the bridge and consumes it.
def test_dialog_adopts_a_transfer(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])[0]
    create_transfers([(d2t(210104), ACC3, 2, ACC2, 0, ETH)])   # a plain incoming transfer that is the bridge arrival

    dialog = _dialog(send_oid)
    assert len(dialog._options) == 1
    dialog._list.setCurrentRow(0)
    dialog.accept()

    Ledger().rebuild(from_timestamp=0)
    assert len(BridgeMatcher()._pending_halves()) == 0
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')


# An arrival of another asset is offered by the same picker, but labelled as what it really makes - a cross-chain
# swap - and accepting it creates that swap instead of a bridge.
def test_dialog_offers_and_creates_a_cross_chain_swap(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    create_quotes(ETH, 2, [(d2t(210103), 1200.0)])
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])[0]
    create_transfers([(d2t(210104), ACC3, 2400, ACC2, 0, USDC)])   # 2400 USDC arrived instead of the ETH sent

    dialog = _dialog(send_oid)
    assert len(dialog._options) == 1
    assert dialog._options[0][2].endswith(dialog.tr("cross-chain swap"))
    dialog._list.setCurrentRow(0)
    dialog.accept()

    Ledger().rebuild(from_timestamp=0)
    assert len(BridgeMatcher()._pending_halves()) == 0
    assert JalDB._read("SELECT COUNT(*) FROM swaps") == 1
    lots = JalAccount(ACC2).open_trades_list(JalAsset(USDC))
    assert len(lots) == 1 and lots[0].open_qty() == Decimal('2400')
