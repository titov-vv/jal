# Characterization tests pinning how operations resolve their asset/symbol from the operation's symbol_id.
# They guard the JalSymbol migration of operations.py (Phase 2): the .asset()/.symbol() results and the
# null-symbol (cash transfer) behavior must stay identical before and after the refactor.
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_stocks, create_actions, create_trades, create_dividends, \
    create_corporate_actions, create_transfers
from constants import AssetLocation
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, Transfer, CorporateAction


def _last_oid(table: str) -> int:
    return JalDB._read(f"SELECT MAX(oid) FROM {table}")


# ----------------------------------------------------------------------------------------------------------------------
def test_trade_asset_resolution(prepare_db):
    JalAccountCreator(currency_id=2, number='U1', name='Acc', investing=1, organization=1).commit()
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=2)  # asset id 4
    create_trades(1, [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])

    trade = LedgerTransaction.get_operation(LedgerTransaction.Trade, _last_oid("trades"))
    assert trade.asset().id() == 4
    assert trade.asset().symbol() == 'AAPL'


# ----------------------------------------------------------------------------------------------------------------------
def test_dividend_asset_resolution(prepare_db):
    JalAccountCreator(currency_id=2, number='U1', name='Acc', investing=1, organization=1).commit()
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=2)  # asset id 4
    create_dividends([(d2t(220301), 1, 4, 5.0, 0.5, "dividend")])

    div = LedgerTransaction.get_operation(LedgerTransaction.AssetPayment, _last_oid("asset_payments"))
    assert div.asset().id() == 4
    assert div.asset().symbol() == 'AAPL'


# ----------------------------------------------------------------------------------------------------------------------
def test_cash_transfer_has_no_asset(prepare_db):
    # A cash transfer has symbol_id = NULL; the operation must resolve to an empty asset (id 0) so it is
    # rendered as a plain cash transfer (not an asset transfer).
    JalAccountCreator(currency_id=2, number='U1', name='Acc1', investing=1, organization=1).commit()
    JalAccountCreator(currency_id=2, number='U2', name='Acc2', investing=1, organization=1).commit()
    create_actions([(d2t(220101), 1, 1, [(4, 1000.0)])])
    create_transfers([(d2t(220201), 1, 100.0, 2, 100.0, None)])  # cash transfer, asset_id None -> symbol_id None

    out = LedgerTransaction.get_operation(LedgerTransaction.Transfer, _last_oid("transfers"), Transfer.Outgoing)
    assert out.asset().id() == 0
    assert out.name() == "Outgoing transfer"  # cash-transfer name (chosen by asset.id()==0), not "asset transfer"


# ----------------------------------------------------------------------------------------------------------------------
def test_asset_transfer_resolves_asset(prepare_db):
    JalAccountCreator(currency_id=2, number='U1', name='Acc1', investing=1, organization=1, precision=10).commit()
    JalAccountCreator(currency_id=1, number='U2', name='Acc2', investing=1, organization=1, precision=10).commit()
    create_actions([(d2t(220101), 1, 1, [(4, 1000.0)])])
    create_stocks([('A.USD', 'A SHARE')], currency_id=2)  # asset id 4
    JalAsset(4).add_symbol('A.RUB', 1, location_id=AssetLocation.UNDEFINED)
    create_trades(1, [(d2t(220201), d2t(220203), 4, 5.0, 100.0, 1.0)])
    create_transfers([(d2t(220207), 1, 5.0, 2, 37500.0, 4)])  # asset transfer of asset id 4

    out = LedgerTransaction.get_operation(LedgerTransaction.Transfer, _last_oid("transfers"), Transfer.Outgoing)
    assert out.asset().id() == 4


# ----------------------------------------------------------------------------------------------------------------------
def test_corporate_action_asset_resolution(prepare_db):
    JalAccountCreator(currency_id=2, number='U1', name='Acc', investing=1, organization=1).commit()
    create_stocks([('OLD', 'Old Co'), ('NEW', 'New Co')], currency_id=2)  # asset ids 4, 5
    create_actions([(d2t(220101), 1, 1, [(4, 1000.0)])])
    create_trades(1, [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])
    # Merger: OLD (id 4) -> NEW (id 5)
    create_corporate_actions(1, [(d2t(220301), CorporateAction.Merger, 4, 10.0, 'merger', [(5, 10.0, 1.0)])])

    ca = LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, _last_oid("asset_actions"))
    assert ca.asset().id() == 4
    assert ca.asset().symbol() == 'OLD'
