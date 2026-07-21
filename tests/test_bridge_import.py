from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType
from jal.data_import.statement import Statement, JSF
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.bridge_matcher import BridgeMatcher

ETH = 4
ACC1, ACC2 = 1, 2          # two wallets of one owner, standing in for two chains


@pytest.fixture
def accounts(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='Chain1', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    JalAccountCreator(currency_id=2, number='', name='Chain2', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    create_assets([('ETH', 'Ethereum', '', 2, PredefinedAsset.Crypto, 0)])   # ID = 4
    create_actions([(d2t(210101), ACC1, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


def _open_qty(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0'))


def _open_basis(account_id) -> Decimal:
    lots = JalAccount(account_id).open_trades_list(JalAsset(ETH))
    return sum((lot.open_qty(adjusted=True) * lot.open_price(adjusted=True) for lot in lots), Decimal('0'))


# A send half fetched from the source chain and a receive half fetched from the destination chain import as two
# pending half-bridges and are then completed by the same auto-match the fetcher runs after an import.
def test_fetched_bridge_halves_import_and_auto_match(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    statement = Statement()
    db_symbol = symbol_id_for(ETH, 2)
    statement.set_mapped_id(JSF.ACCOUNTS, 1, ACC1)     # JSF account 1 (source chain) -> Chain1
    statement.set_mapped_id(JSF.ACCOUNTS, 2, ACC2)     # JSF account 2 (destination chain) -> Chain2
    statement.set_mapped_id(JSF.SYMBOLS, 100, db_symbol)

    halves = [   # what two separate fetches (one per chain) would each contribute for one bridge
        {"id": 1, "sending": True,  "account": 1, "symbol": 100, "qty": Decimal('2'),
         "timestamp": d2t(210103), "tx_hash": "0xsend", "description": ""},
        {"id": 2, "sending": False, "account": 2, "symbol": 100, "qty": Decimal('2'),
         "timestamp": d2t(210104), "tx_hash": "0xrecv", "description": ""},
    ]
    statement._import_bridges(halves)
    assert len(BridgeMatcher()._pending_halves()) == 2   # both landed as pending halves

    assert BridgeMatcher().auto_match() == 1             # the fetcher runs this after import
    Ledger().rebuild(from_timestamp=0)
    assert _open_qty(ACC1) == Decimal('1')
    assert _open_qty(ACC2) == Decimal('2') and _open_basis(ACC2) == Decimal('2000')


# A send half fetched with no counterpart yet stays a pending half (source balance drops, nothing auto-matched).
def test_lone_fetched_send_half_stays_pending(accounts):
    create_trades(ACC1, [(d2t(210102), d2t(210102), ETH, 3.0, 1000.0, 0.0)])
    statement = Statement()
    statement.set_mapped_id(JSF.ACCOUNTS, 1, ACC1)
    statement.set_mapped_id(JSF.SYMBOLS, 100, symbol_id_for(ETH, 2))
    statement._import_bridges([{"id": 1, "sending": True, "account": 1, "symbol": 100, "qty": Decimal('2'),
                                "timestamp": d2t(210103), "tx_hash": "0xsend", "description": ""}])

    assert BridgeMatcher().auto_match() == 0
    assert len(BridgeMatcher()._pending_halves()) == 1
    Ledger().rebuild(from_timestamp=0)
    assert _open_qty(ACC1) == Decimal('1')               # the 2 ETH left the source, value parked in transit
