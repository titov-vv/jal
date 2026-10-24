from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from jal.constants import BookAccount, Setup, AssetLocation
from jal.db.db import JalDB, JalDBError
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount
from jal.db.operations import CorporateAction, LedgerError
from tests.helpers import d2t, dt2t, create_stocks, create_quotes, create_trades, create_corporate_actions, symbol_id_for
from PySide6.QtWidgets import QWidget, QMessageBox
from jal.db.asset import JalAsset
from jal.widgets.corporate_action_widget import CorporateActionWidget


def test_spin_off(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5

    test_corp_actions = [
        (dt2t(2106011200), CorporateAction.SpinOff, 4, 100.0, 'Spin-off 5 B from 100 A', [(4, 100.0, 1.0), (5, 5.0, 0.0)]),
        (dt2t(2108011200), CorporateAction.Split, 4, 104.0, 'Split A 104 -> 13', [(4, 13.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210503), 4, 100.0, 14.0, 0.0),        # Buy 100 A x 14.00 01/05/2021
        (d2t(210701), d2t(210703), 4, 4.0, 13.0, 0.0),          # Buy   4 A x 13.00 01/07/2021
        (dt2t(2108151700), d2t(210817), 4, -13.0, 150.0, 0.0)   # Sell 13 A x 150.00 15/08/2021
    ]
    create_trades(1, test_trades)

    create_quotes(2, 2, [(d2t(210301), 70.0)])
    create_quotes(4, 2, [(d2t(210401), 15.0)])
    create_quotes(5, 2, [(d2t(210401), 2.0)])
    create_quotes(4, 2, [(d2t(210811), 100.0)])

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # Check ledger amounts before selling
    op_timestamp = LedgerAmounts("timestamp", timestamp=d2t(210810))
    amount = LedgerAmounts("amount", timestamp=d2t(210810))
    total_amount = LedgerAmounts("amount_acc", timestamp=d2t(210810))
    total_value = LedgerAmounts("value_acc", timestamp=d2t(210810))

    assert op_timestamp[(BookAccount.Money, 1, 2)] == d2t(210701)
    assert amount[(BookAccount.Money, 1, 2)] == Decimal('-52')
    assert total_amount[(BookAccount.Money, 1, 2)] == Decimal('8548')
    assert total_value[(BookAccount.Money, 1, 2)] == Decimal('0')

    assert op_timestamp[(BookAccount.Assets, 1, 4)] == dt2t(2108011200)
    assert amount[(BookAccount.Assets, 1, 4)] == Decimal('13')
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('13')
    assert total_value[(BookAccount.Assets, 1, 4)] == Decimal('1452')

    assert op_timestamp[(BookAccount.Assets, 1, 5)] == dt2t(2106011200)
    assert amount[(BookAccount.Assets, 1, 5)] == Decimal('5')
    assert total_amount[(BookAccount.Assets, 1, 5)] == Decimal('5')
    assert total_value[(BookAccount.Assets, 1, 5)] == Decimal('0')

    trades = [x for x in JalAccount(1).closed_trades_list() if x.close_operation().timestamp() >= dt2t(2108151700)]
    assert len(trades) == 2
    assert [x.profit() for x in trades] == [Decimal('475'), Decimal('23')]


def test_symbol_change(prepare_db_fifo):
    # Prepare trades and corporate actions setup
    test_assets = [
        ('A', 'A SHARE'),  # id = 4
        ('B', 'B SHARE')   # id = 5
    ]
    create_stocks(test_assets, currency_id=2)

    test_corp_actions = [
        (d2t(210601), CorporateAction.SymbolChange, 4, 100.0, 'Symbol change 100 A -> 100 B', [(5, 100.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210501), 4, 100.0, 10.0, 0.0),      # Buy  100 A x 10.00 01/05/2021
        (d2t(210701), d2t(210701), 5, -100.0, 20.0, 0.0)      # Sell 100 B x 20.00 01/07/2021
    ]
    create_trades(1, test_trades)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    trades = JalAccount(1).closed_trades_list()
    assert trades[0].dump() == ['B', d2t(210501), d2t(210701), Decimal('1E+1'), Decimal('2E+1'), Decimal('1E+2'), Decimal('0'), Decimal('1000'), Decimal('100')]


def test_delisting(prepare_db_fifo):
    create_stocks([('A', 'A SHARE')], currency_id=2)  # ID = 4

    test_corp_actions = [
        (d2t(210801), CorporateAction.Delisting, 4, 100.0, 'Delisting 100 A', [])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210501), 4, 100.0, 10.0, 0.0)      # Buy  100 A x 10.00 01/05/2021
    ]
    create_trades(1, test_trades)

    # Build ledger
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    trades = JalAccount(1).closed_trades_list()
    assert len(trades) == 0

    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Costs, 1, 2)] == Decimal('1E+3')
    assert amounts[(BookAccount.Money, 1, 2)] == Decimal('9E+3')
    assert amounts[(BookAccount.Assets, 1, 4)] == Decimal('0')

    values = LedgerAmounts("value_acc")
    assert values[(BookAccount.Assets, 1, 4)] == Decimal('0')


# ----------------------------------------------------------------------------------------------------------------------
# A split of a short position: its lots stay short, each with twice the quantity at half the price
def test_split_of_short_position(prepare_db_fifo):
    create_stocks([('A', 'A SHARE')], currency_id=2)  # id = 4

    test_corp_actions = [
        (d2t(210701), CorporateAction.Split, 4, -100.0, 'Split A -100 -> -200', [(4, -200.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210503), 4, -60.0, 20.0, 1.0),      # Sell 60 A x 20.00 01/05/2021
        (d2t(210601), d2t(210603), 4, -40.0, 30.0, 2.0),      # Sell 40 A x 30.00 01/06/2021
        (d2t(210801), d2t(210803), 4, 150.0, 8.0, 0.0),       # Buy 150 A x  8.00 01/08/2021
        (d2t(210901), d2t(210903), 4, 50.0, 5.0, 0.0)         # Buy  50 A x  5.00 01/09/2021
    ]
    create_trades(1, test_trades)

    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    # The position right after the split: -200 pieces that keep the value they were sold for (60 x 20 + 40 x 30)
    total_amount = LedgerAmounts("amount_acc", timestamp=d2t(210710))
    total_value = LedgerAmounts("value_acc", timestamp=d2t(210710))
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('-200')
    assert total_value[(BookAccount.Assets, 1, 4)] == Decimal('-2400')

    # 120 x (10 - 8) - 1 | 30 x (15 - 8) - 2 x 30/80 | 50 x (15 - 5) - 2 x 50/80
    trades = JalAccount(1).closed_trades_list()
    assert [(x.qty(), x.open_qty(), x.open_price(adjusted=True)) for x in trades] == [
        (Decimal('-120'), Decimal('-60'), Decimal('10')),
        (Decimal('-30'), Decimal('-15'), Decimal('15')),
        (Decimal('-50'), Decimal('-25'), Decimal('15'))
    ]
    assert [x.profit() for x in trades] == [Decimal('239'), Decimal('209.25'), Decimal('498.75')]
    assert all(x.modified_by()[0].type() == CorporateAction._otype for x in trades)

    total_amount = LedgerAmounts("amount_acc")
    total_value = LedgerAmounts("value_acc")
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert total_value[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert total_amount[(BookAccount.Money, 1, 2)] == Decimal('10947')   # 10000 + 1199 + 1198 - 1200 - 250


# A short position moves to another symbol with its lots
def test_symbol_change_of_short_position(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5

    test_corp_actions = [
        (d2t(210601), CorporateAction.SymbolChange, 4, -100.0, 'Symbol change -100 A -> -100 B', [(5, -100.0, 1.0)])
    ]
    create_corporate_actions(1, test_corp_actions)

    test_trades = [
        (d2t(210501), d2t(210501), 4, -100.0, 20.0, 0.0),     # Sell 100 A x 20.00 01/05/2021
        (d2t(210701), d2t(210701), 5, 100.0, 15.0, 0.0)       # Buy  100 B x 15.00 01/07/2021
    ]
    create_trades(1, test_trades)

    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)

    total_amount = LedgerAmounts("amount_acc", timestamp=d2t(210610))
    total_value = LedgerAmounts("value_acc", timestamp=d2t(210610))
    assert total_amount[(BookAccount.Assets, 1, 4)] == Decimal('0')
    assert total_amount[(BookAccount.Assets, 1, 5)] == Decimal('-100')
    assert total_value[(BookAccount.Assets, 1, 5)] == Decimal('-2000')

    trades = JalAccount(1).closed_trades_list()
    assert [(x.symbol(), x.qty(), x.profit()) for x in trades] == [('B', Decimal('-100'), Decimal('500'))]


# Only a split and a symbol change are carried out for a short position, and they keep it short
@pytest.mark.parametrize("action", [
    (CorporateAction.SpinOff, 4, -100.0, 'Spin-off', [(4, -100.0, 0.9), (5, -5.0, 0.1)]),
    (CorporateAction.Merger, 4, -100.0, 'Merger', [(5, -50.0, 1.0)]),
    (CorporateAction.Delisting, 4, -100.0, 'Delisting', []),
    (CorporateAction.Split, 4, -100.0, 'Split that turns the position long', [(4, 200.0, 1.0)]),
    (CorporateAction.Split, 4, 100.0, 'Split of a long position that is short', [(4, 200.0, 1.0)])
])
def test_unsupported_action_on_short_position_halts_the_ledger(prepare_db_fifo, action):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5
    create_trades(1, [(d2t(210501), d2t(210501), 4, -100.0, 20.0, 0.0)])
    create_corporate_actions(1, [(d2t(210601),) + action])
    with pytest.raises(LedgerError):
        Ledger().rebuild(from_timestamp=0)


# ----------------------------------------------------------------------------------------------------------------------
# Delta 81 backfills which results keep the original purchase date, replayed from the shipped file on
# a database taken back to version 80 by hand
def test_delta_81_backfills_which_results_keep_the_date(prepare_db_fifo, project_root):
    create_stocks([('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], currency_id=2)   # id = 4..7
    create_corporate_actions(1, [
        (d2t(210101), CorporateAction.Split, 4, 10.0, 'split', [(4, 20.0, 1.0)]),
        (d2t(210201), CorporateAction.SymbolChange, 4, 20.0, 'redomiciliation', [(5, 20.0, 1.0)]),
        (d2t(210301), CorporateAction.SpinOff, 5, 20.0, 'spin-off', [(5, 20.0, 0.9), (6, 2.0, 0.1)]),
        (d2t(210401), CorporateAction.Merger, 6, 2.0, 'merger', [(7, 1.0, 1.0)])])
    assert JalDB._exec("ALTER TABLE asset_action_results DROP COLUMN keep_date", commit=True) is not None
    assert JalDB._exec("ALTER TABLE trades_opened DROP COLUMN acquired", commit=True) is not None
    JalDB._exec("UPDATE settings SET value=80 WHERE name='SchemaVersion'", commit=True)

    assert JalDB().run_sql_script(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}81.sql").code == JalDBError.NoError
    assert JalDB._read("SELECT value FROM settings WHERE name='SchemaVersion'") == '81'
    flags = JalDB._read_to_list("SELECT a.note, s.asset_id, r.keep_date FROM asset_action_results r "
                                "JOIN asset_actions a ON a.oid=r.action_id JOIN asset_symbol s ON s.id=r.symbol_id "
                                "ORDER BY a.timestamp, s.asset_id")
    assert [tuple(x) for x in flags] == [('split', 4, 1), ('redomiciliation', 5, 1),
                                         ('spin-off', 5, 1), ('spin-off', 6, 0), ('merger', 7, 0)]


# ----------------------------------------------------------------------------------------------------------------------
# The editor: a new result takes the rule's 'Keeps date' when its asset is chosen, a flag toggled by hand stays as set,
# and a stored result is never recomputed
def test_editor_defaults_keeps_date_of_a_new_result(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE'), ('C', 'C SHARE')], currency_id=2)  # id = 4, 5, 6
    parent = QWidget()
    widget = CorporateActionWidget(parent)
    widget.createNew(account_id=1)
    widget.model.setData(widget.model.index(0, widget.model.fieldIndex("type")), CorporateAction.SpinOff)
    widget.model.setData(widget.model.index(0, widget.model.fieldIndex("symbol_id")), symbol_id_for(4))
    results = widget.results_model
    symbol, flag = results.fieldIndex("symbol_id"), results.fieldIndex("keep_date")
    widget.addResult()
    widget.addResult()
    results.setData(results.index(0, symbol), symbol_id_for(4))   # the parent keeps its date
    results.setData(results.index(1, symbol), symbol_id_for(5))   # the spun-off company doesn't
    assert [results.data(results.index(x, flag)) for x in (0, 1)] == [1, 0]

    results.setData(results.index(1, flag), 1)                    # set by hand ...
    results.setData(results.index(1, symbol), symbol_id_for(6))   # ... survives another asset
    assert results.data(results.index(1, flag)) == 1

    for row, share in ((0, 0.9), (1, 0.1)):
        results.setData(results.index(row, results.fieldIndex("qty")), 10)
        results.setData(results.index(row, results.fieldIndex("value_share")), share)
    widget._save()
    assert JalDB._read_to_list("SELECT symbol_id, keep_date FROM asset_action_results ORDER BY id") == \
           [[symbol_id_for(4), 1], [symbol_id_for(6), 1]]

    widget.set_id(JalDB._read("SELECT oid FROM asset_actions"))
    results.setData(results.index(1, symbol), symbol_id_for(5))   # a stored result keeps what it has
    assert results.data(results.index(1, flag)) == 1


# A copy of an action with two results is saved as a new action with two new results
def test_editor_copies_an_action_with_two_results(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5
    create_corporate_actions(1, [(d2t(210601), CorporateAction.SpinOff, 4, 100.0, 'Spin-off',
                                  [(4, 100.0, 0.9), (5, 5.0, 0.1)])])
    parent = QWidget()
    widget = CorporateActionWidget(parent)
    widget.set_id(JalDB._read("SELECT oid FROM asset_actions"))
    widget.copyNew()
    widget._save()
    assert JalDB._read("SELECT count(*) FROM asset_actions") == 2
    assert JalDB._read_to_list("SELECT symbol_id, keep_date FROM asset_action_results ORDER BY id") == \
           [[symbol_id_for(4), 1], [symbol_id_for(5), 0]] * 2


# The editor accepts a split whose result is another listing of the same asset, and refuses one onto another asset
def test_editor_split_stays_inside_one_asset(prepare_db_fifo, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[3]) or QMessageBox.Ok)
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=2)  # id = 4, 5
    new_listing = JalAsset(4).add_symbol('A2', 2, AssetLocation.NASDAQ_EXCHANGE)
    parent = QWidget()
    widget = CorporateActionWidget(parent)
    widget.createNew(account_id=1)
    widget.model.setData(widget.model.index(0, widget.model.fieldIndex("type")), CorporateAction.Split)
    widget.model.setData(widget.model.index(0, widget.model.fieldIndex("symbol_id")), symbol_id_for(4))
    widget.addResult()
    results = widget.results_model
    for field, value in (('symbol_id', new_listing), ('qty', 10), ('value_share', 1)):
        results.setData(results.index(0, results.fieldIndex(field)), value)
    assert widget._validated() and warnings == []
    results.setData(results.index(0, results.fieldIndex('symbol_id')), symbol_id_for(5))
    assert not widget._validated() and warnings == ["You can't change asset during Split"]
