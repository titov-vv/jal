from decimal import Decimal

import pytest
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_corporate_actions
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.operations import CorporateAction
from jal.db.tax_estimator import TaxEstimator
from jal.widgets.price_chart import ChartWindow

USD, A, B = 2, 4, 5


# A position that a corporate action has been through: 20 A bought at 100 became 5 B, so the account holds 5 shares
# that cost 400 apiece - and neither of those two numbers is the one the opening trade was made at.
@pytest.fixture
def split_position(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=USD)
    create_trades(1, [(d2t(220101), d2t(220101), A, Decimal('20'), Decimal('100'), Decimal('0'))])
    create_corporate_actions(1, [(d2t(220201), CorporateAction.Split, A, Decimal('20'), 'Split 20 A -> 5 B',
                                  [(B, Decimal('5'), Decimal('1'))])])
    create_quotes(B, USD, [(d2t(220301), 500.0)])       # what a share of B is worth now
    create_quotes(USD, 1, [(d2t(211231), 100.0)])       # and what a USD is worth in the tax currency
    Ledger().rebuild(from_timestamp=0)
    yield


# The estimate is made of the position as it stands: 5 shares that cost 400, not the 20 at 100 that were bought.
def test_tax_estimator_uses_the_adjusted_position(split_position):
    parent = QWidget()
    estimator = TaxEstimator('ru', 1, B, Decimal('5'), parent=parent)
    assert estimator.ready
    positions = estimator.dataframe.to_dict('records')

    assert len(positions) == 2                                       # the position and the TOTAL line
    assert positions[0]['qty'] == Decimal('5')
    assert positions[0]['o_price'] == Decimal('400')
    assert positions[0]['profit'] == Decimal('500')                  # 5 * (500 - 400)
    assert positions[0]['profit_rub'] == Decimal('50000')            # at 100 RUB/USD on both ends
    assert positions[0]['tax'] == Decimal('6500')                    # 13% of it
    assert positions[1]['qty'] == Decimal('5')                       # TOTAL of the single position
    assert positions[1]['o_price'] == Decimal('400')


# The chart marks the position where it really sits: 5 shares at 400, on the price series of B.
def test_price_chart_marks_the_adjusted_position(split_position):
    parent = QWidget()
    chart = ChartWindow(1, B, USD, d2t(220401), parent=parent)
    assert chart.ready
    assert [(x['qty'], x['price']) for x in chart.trades] == [(Decimal('5'), Decimal('400'))]
