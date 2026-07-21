import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, create_bridges, create_transfers
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.bridge_matcher import BridgeMatcher
from jal.widgets.bridge_match_dialog import BridgeMatchDialog

ETH = 4
ACC1, ACC2, ACC3 = 1, 2, 3


@pytest.fixture
def accounts(prepare_db):
    for name in ('Chain1', 'Chain2', 'Chain3'):
        JalAccountCreator(currency_id=2, number='', name=name, investing=1, organization=1,
                          account_type=PredefinedAccountType.Broker).commit()
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0)])
    create_actions([(d2t(210101), ACC1, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


def _open_qty(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0'))


def _open_basis(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) * lot.open_price(adjusted=True) for lot in lots), Decimal('0'))


# The dialog lists a candidate half and completes the bridge when it is chosen and accepted.
def test_dialog_matches_a_candidate_half(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2},
                               {'asset': ETH, 'in_ts': d2t(210104), 'in_acc': ACC2, 'in_qty': 2}])[0]

    dialog = BridgeMatchDialog(send_oid)
    kinds = [opt[0] for opt in dialog._options]
    assert 'half' in kinds                       # the receive half is offered
    dialog._list.setCurrentRow(kinds.index('half'))
    dialog.accept()

    Ledger().rebuild(from_timestamp=0)
    assert len(BridgeMatcher()._pending_halves()) == 0
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')


# The dialog also offers an existing incoming transfer, and adopting it completes the bridge and consumes the transfer.
def test_dialog_adopts_a_transfer(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    send_oid = create_bridges([{'asset': ETH, 'out_ts': d2t(210103), 'out_acc': ACC1, 'out_qty': 2}])[0]
    create_transfers([(d2t(210104), ACC3, 2, ACC2, 0, ETH)])   # a plain incoming transfer that is the bridge arrival

    dialog = BridgeMatchDialog(send_oid)
    kinds = [opt[0] for opt in dialog._options]
    assert 'transfer' in kinds
    dialog._list.setCurrentRow(kinds.index('transfer'))
    dialog.accept()

    Ledger().rebuild(from_timestamp=0)
    assert len(BridgeMatcher()._pending_halves()) == 0
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')
