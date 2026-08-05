import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, create_bridges, create_transfers, \
    create_quotes
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccountCreator
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


# The dialog offers the incoming transfers that could be the arrival; adopting one completes the bridge and consumes
# it. The resulting ledger outcome (open_qty/open_basis) is already proven at the unit level in
# tests/test_bridge_matching.py::test_adopt_incoming_transfer_as_receive_leg - what belongs here is the dialog's own
# wiring: it offers exactly one option, and accepting it drives the match through to completion.
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


# An arrival of another asset is offered by the same picker, but labelled as what it really makes - a cross-chain
# swap - and accepting it creates that swap instead of a bridge. The swap's own ledger outcome is already proven at
# the unit level in tests/test_bridge_matching.py::test_adopting_another_asset_creates_cross_chain_swap - what
# belongs here is that the dialog labels the option correctly and that accepting it produces a swap, not a bridge.
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
