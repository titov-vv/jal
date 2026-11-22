from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.tag import JalTag
from jal.db.portfolio import JalPortfolio


def _tag(name) -> int:
    return JalDB._read("SELECT id FROM tags WHERE tag=:tag", [(":tag", name)])


def _lots(asset_id=4) -> list:
    return JalAccount(1).open_trades_list(JalAsset(asset_id))


# Two buys of one stock on one account, each opening a lot of its own
def _two_lots():
    create_stocks([('A', 'A SHARE')], currency_id=2)
    create_trades(1, [(d2t(220101), d2t(220101), 4, 10.0, 100.0, 0.0),
                      (d2t(220201), d2t(220201), 4, 5.0, 110.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    return _lots()


def test_nothing_assigned_is_unassigned(prepare_db_fifo):
    lots = _two_lots()
    portfolio = JalPortfolio()
    assert [portfolio.of_lot(x) for x in lots] == [JalPortfolio.Unassigned] * 2
    assert JalPortfolio.assignments() == {}


def test_a_lot_takes_the_portfolio_of_its_opening_operation(prepare_db_fifo):
    first, second = _two_lots()
    JalPortfolio.assign(second.open_operation().id(), _tag('Cash'))
    portfolio = JalPortfolio()
    assert portfolio.of_lot(first) == JalPortfolio.Unassigned
    assert portfolio.of_lot(second) == _tag('Cash')
    assert portfolio.of_operation(second.open_operation()) == _tag('Cash')


def test_assigning_again_replaces_and_unassigned_drops(prepare_db_fifo):
    lot = _two_lots()[0]
    oid = lot.open_operation().id()
    JalPortfolio.assign(oid, _tag('Cash'))
    JalPortfolio.assign(oid, _tag('Card'))
    assert JalPortfolio.assignments() == {oid: _tag('Card')}
    JalPortfolio.assign(oid, JalPortfolio.Unassigned)
    assert JalPortfolio.assignments() == {}


# A snapshot answers as of its creation: a later assignment needs a new one
def test_a_snapshot_keeps_what_it_read(prepare_db_fifo):
    lot = _two_lots()[0]
    portfolio = JalPortfolio()
    JalPortfolio.assign(lot.open_operation().id(), _tag('Cash'))
    assert portfolio.of_lot(lot) == JalPortfolio.Unassigned
    assert JalPortfolio().of_lot(lot) == _tag('Cash')


# A short lot belongs to no portfolio, even when the sale that opened it is assigned
def test_a_short_lot_is_unassigned(prepare_db_fifo):
    create_stocks([('A', 'A SHARE')], currency_id=2)
    create_trades(1, [(d2t(220101), d2t(220101), 4, -10.0, 100.0, 0.0)])
    Ledger().rebuild(from_timestamp=0)
    lot = _lots()[0]
    JalPortfolio.assign(lot.open_operation().id(), _tag('Cash'))
    portfolio = JalPortfolio()
    assert portfolio.of_operation(lot.open_operation()) == _tag('Cash')
    assert portfolio.of_lot(lot) == JalPortfolio.Unassigned


def test_a_tag_merge_moves_the_assignments(prepare_db_fifo):
    lot = _two_lots()[0]
    oid = lot.open_operation().id()
    JalPortfolio.assign(oid, _tag('Cash'))
    JalTag(_tag('Cash')).replace_with(_tag('Card'))
    assert JalPortfolio.assignments() == {oid: _tag('Card')}


def test_deleting_the_tag_or_the_operation_drops_the_assignment(prepare_db_fifo):
    first, second = _two_lots()
    JalPortfolio.assign(first.open_operation().id(), _tag('Cash'))
    JalPortfolio.assign(second.open_operation().id(), _tag('Card'))
    JalDB._exec("DELETE FROM tags WHERE id=:tag", [(":tag", _tag('Cash'))], commit=True)
    assert JalPortfolio.assignments() == {second.open_operation().id(): _tag('Card')}
    LedgerTransaction.get_operation(LedgerTransaction.Trade, second.open_operation().id()).delete()
    assert JalPortfolio.assignments() == {}
