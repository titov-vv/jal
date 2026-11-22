from decimal import Decimal

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QTreeView

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_stocks, create_trades, create_dividends, create_quotes
from jal.constants import AccountStatus, PredefinedAgents
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.holdings_model import HoldingsModel
from jal.db.ledger import Ledger
from jal.db.peer import JalPeer

USD, EUR, S = 2, 3, 4
T1, T2, T3 = d2t(220101), d2t(220201), d2t(220301)
PAYER, HOLDER, SECOND, ELSEWHERE = 1, 2, 3, 4


# A broker's USD account that receives dividends, its EUR account and a second EUR account that hold the stock, and
# an account at no broker; a dollar is half a euro
@pytest.fixture
def broker(prepare_db):
    broker_id = JalPeer(data={'name': "Broker", 'parent': 0}, create=True).id()
    for name, currency, organization in [("Broker", USD, broker_id), ("Broker [EUR]", EUR, broker_id),
                                         ("Broker 2", EUR, broker_id), ("Elsewhere", EUR, PredefinedAgents.Empty)]:
        JalAccountCreator(currency_id=currency, number=name, name=name, investing=1, organization=organization).commit()
    create_stocks([('S', 'Stock S')], currency_id=EUR)
    create_quotes(USD, EUR, [(T1, Decimal('0.5'))])
    create_trades(HOLDER, [(T1, T1, S, 10.0, 100.0, 0.0)])
    yield


def _linked(account_id) -> Decimal:
    return JalAccount(account_id).linked_payments_amount(JalAsset(S), T1, T3)


def test_a_payment_into_another_account_of_the_broker_goes_to_the_holder(broker):
    create_dividends([(T2, PAYER, S, Decimal('30'), Decimal('3'), 'dividend')])
    Ledger().rebuild(from_timestamp=0)
    assert _linked(HOLDER) == Decimal('15')
    assert _linked(PAYER) == Decimal('0')
    model = HoldingsModel(QTreeView())
    model.updateView(currency_id=EUR, date=QDate(2022, 3, 1), grouping='', min_status=AccountStatus.Active)
    assert [x['paid'] for x in model._account_records(JalAccount(HOLDER)) if x['asset_id'] == S] == [Decimal('15')]


# 10 and 30 held: the 40 USD paid (20 EUR) is shared 5 : 15
def test_holders_share_a_linked_payment_by_quantity(broker):
    create_trades(SECOND, [(T1, T1, S, 30.0, 100.0, 0.0)])
    create_dividends([(T2, PAYER, S, Decimal('40'), Decimal('0'), 'dividend')])
    Ledger().rebuild(from_timestamp=0)
    assert _linked(HOLDER) == Decimal('5')
    assert _linked(SECOND) == Decimal('15')


def test_a_payer_holding_the_asset_keeps_its_payment(broker):
    create_trades(PAYER, [(T1, T1, S, 5.0, 50.0, 0.0)])
    create_dividends([(T2, PAYER, S, Decimal('30'), Decimal('0'), 'dividend')])
    Ledger().rebuild(from_timestamp=0)
    assert _linked(HOLDER) == Decimal('0')


def test_accounts_of_another_broker_or_of_none_are_not_linked(broker):
    create_trades(ELSEWHERE, [(T1, T1, S, 10.0, 100.0, 0.0)])
    create_dividends([(T2, PAYER, S, Decimal('30'), Decimal('0'), 'dividend')])
    Ledger().rebuild(from_timestamp=0)
    assert _linked(ELSEWHERE) == Decimal('0')
    assert _linked(HOLDER) == Decimal('15')


def test_a_payment_outside_the_holding_period_is_not_counted(broker):
    create_dividends([(T3 + 86400, PAYER, S, Decimal('30'), Decimal('0'), 'dividend')])
    Ledger().rebuild(from_timestamp=0)
    assert _linked(HOLDER) == Decimal('0')
