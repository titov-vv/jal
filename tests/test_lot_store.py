from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_trades, create_stocks
from jal.db.ledger import Ledger
from jal.db.lots import LedgerLotStore

ACCOUNT = 1


@pytest.fixture
def stock(prepare_db_fifo):
    create_stocks([('AAA', 'Stock A')], currency_id=2)   # ID = 4
    yield


# A position the lots hold: long after buys, reduced by a partial sale, empty when sold out
def test_position_of_a_long_lot(stock):
    create_trades(ACCOUNT, [(d2t(220101), d2t(220101), 4, 10, 100, 0), (d2t(220102), d2t(220102), 4, 5, 110, 0)])
    Ledger().rebuild(from_timestamp=0)
    assert LedgerLotStore().position(ACCOUNT, 4) == Decimal('15')

    create_trades(ACCOUNT, [(d2t(220103), d2t(220103), 4, -12, 120, 0)])
    Ledger().rebuild(from_timestamp=0)
    assert LedgerLotStore().position(ACCOUNT, 4) == Decimal('3')

    create_trades(ACCOUNT, [(d2t(220104), d2t(220104), 4, -3, 120, 0)])
    Ledger().rebuild(from_timestamp=0)
    assert LedgerLotStore().position(ACCOUNT, 4) == Decimal('0')


# A short lot stores an unsigned quantity; its position is negative because the trade that opened it sold
def test_position_of_a_short_lot(stock):
    create_trades(ACCOUNT, [(d2t(220101), d2t(220101), 4, -10, 100, 0), (d2t(220102), d2t(220102), 4, 4, 90, 0)])
    Ledger().rebuild(from_timestamp=0)
    assert LedgerLotStore().position(ACCOUNT, 4) == Decimal('-6')
