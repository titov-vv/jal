from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_actions
from constants import BookAccount, PredefinedCategory, PredefinedAccountType
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.common_models import AccountListModel
from jal.db.deposit import JalDepositBox
from jal.widgets.deposit_dialogs import move_money, record_interest


# A funded bank account, the one deposits are opened from. Money in it comes from a starting balance so that a
# deposit can be taken out of it without dragging credit into the picture.
@pytest.fixture
def prepare_bank_account(prepare_db):
    account = JalAccountCreator(currency_id=2, number='B1234567', name='Bank account',
                                organization=1, account_type=PredefinedAccountType.Bank).commit()
    assert account.id() == 1
    create_actions([(d2t(210101), 1, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    yield account


# ----------------------------------------------------------------------------------------------------------------------
# A deposit is an account of a hidden type: it exists, holds money and never shows up where accounts are picked.
def test_deposit_box_is_a_hidden_account(prepare_bank_account):
    box = JalDepositBox.create("Deposit A", currency_id=2, organization_id=1,
                               end_date=d2t(211231), rate=Decimal('3.5'))
    assert JalAccount(box.id()).account_type() == PredefinedAccountType.Deposit
    assert box.end_date() == d2t(211231) and box.rate() == Decimal('3.5')

    # Not returned by the default account listing, returned when asked for explicitly
    listed = [x.id() for x in JalAccount.get_all_accounts()]
    assert box.id() not in listed
    assert box.id() in [x.id() for x in JalAccount.get_all_accounts(include_hidden=True)]

    # ... and filtered out of the model every account picker in the application is built on
    model = AccountListModel()
    shown = [model.getId(model.index(row, 0)) for row in range(model.rowCount())]
    assert box.id() not in shown and 1 in shown

    # A filter set by a caller can't smuggle it back in - the baseline is AND-ed into whatever is asked for
    model.setFilter("accounts.currency_id = 2")
    shown = [model.getId(model.index(row, 0)) for row in range(model.rowCount())]
    assert box.id() not in shown and 1 in shown

    # The single opt-in, for a view that manages deposits rather than picking an account
    unfiltered = AccountListModel(include_hidden=True)
    shown = [unfiltered.getId(unfiltered.index(row, 0)) for row in range(unfiltered.rowCount())]
    assert box.id() in shown


# Putting money in, earning interest on it and taking it back out - the whole life of a deposit, made of ordinary
# transfers and one income operation. The bank account has to end up richer by exactly the interest, net of tax.
def test_deposit_box_lifecycle(prepare_bank_account):
    box = JalDepositBox.create("Deposit A", currency_id=2, organization_id=1, end_date=d2t(211231))
    t_open, t_top, t_interest, t_close = d2t(210201), d2t(210301), d2t(210401), d2t(210501)

    move_money(1, box.id(), Decimal('1000'), t_open)
    move_money(1, box.id(), Decimal('500'), t_top)
    record_interest(box, t_interest, Decimal('60'), Decimal('10'))       # 60 credited, 10 withheld
    Ledger().rebuild(from_timestamp=0)

    assert box.balance(t_open) == Decimal('1000')
    assert box.balance(t_top) == Decimal('1500')
    assert box.balance(t_interest) == Decimal('1550')                    # 1500 + 60 - 10
    assert box.accrued_interest(t_interest) == Decimal('50')             # net of the tax withheld
    assert JalAccount(1).get_asset_amount(t_interest, 2) == Decimal('8500')

    move_money(box.id(), 1, box.balance(t_interest), t_close)
    box.close()
    Ledger().rebuild(from_timestamp=0)

    assert box.balance(t_close) == Decimal('0')
    assert not box.is_active()
    # The money is back, up by the interest that was actually credited
    assert JalAccount(1).get_asset_amount(t_close, 2) == Decimal('10050')


# The interest is an income and the tax withheld from it a cost - both of them lines of ONE operation, each booked
# by its own sign. That is what makes deposit interest reach the category-based reports at all.
def test_deposit_interest_is_booked_by_category(prepare_bank_account):
    box = JalDepositBox.create("Deposit A", currency_id=2, organization_id=1)
    t_open, t_interest = d2t(210201), d2t(210401)
    move_money(1, box.id(), Decimal('1000'), t_open)
    record_interest(box, t_interest, Decimal('60'), Decimal('10'))
    Ledger().rebuild(from_timestamp=0)

    account = JalAccount(box.id())
    # 'ledger' books an income negative and a cost positive
    assert account.get_category_turnover(PredefinedCategory.Interest, 0, t_interest) == Decimal('-60')
    assert account.get_category_turnover(PredefinedCategory.Taxes, 0, t_interest) == Decimal('10')
    # The money itself sits in the ordinary Money book of the deposit - there is no Savings book any more
    amounts = LedgerAmounts("amount_acc")
    assert amounts[(BookAccount.Money, box.id(), 2)] == Decimal('1050')


# Only deposits that actually hold money at the report date are listed, and only from the moment they were funded.
def test_only_open_deposits_are_listed(prepare_bank_account):
    box = JalDepositBox.create("Deposit A", currency_id=2, organization_id=1)
    t_before, t_open, t_during, t_close, t_after = d2t(210101), d2t(210201), d2t(210301), d2t(210401), d2t(210501)
    move_money(1, box.id(), Decimal('1000'), t_open)
    move_money(box.id(), 1, Decimal('1000'), t_close)
    Ledger().rebuild(from_timestamp=0)

    assert [x.id() for x in JalDepositBox.get_deposits(t_before)] == []
    assert [x.id() for x in JalDepositBox.get_deposits(t_during)] == [box.id()]
    assert [x.id() for x in JalDepositBox.get_deposits(t_after)] == []


# The details of a deposit read as a statement: every movement with the balance it left behind.
def test_deposit_details_carry_a_running_balance(prepare_bank_account):
    box = JalDepositBox.create("Deposit A", currency_id=2, organization_id=1)
    t_open, t_top, t_interest = d2t(210201), d2t(210301), d2t(210401)
    move_money(1, box.id(), Decimal('1000'), t_open)
    move_money(1, box.id(), Decimal('500'), t_top)
    record_interest(box, t_interest, Decimal('60'), Decimal('10'))
    Ledger().rebuild(from_timestamp=0)

    details = box.details(t_interest)
    assert [x['amount'] for x in details] == [Decimal('1000'), Decimal('500'), Decimal('50')]
    assert [x['balance'] for x in details] == [Decimal('1000'), Decimal('1500'), Decimal('1550')]


# Money in a deposit is part of the balance sheet: it must be counted, and grouped under its own account type.
def test_deposit_money_reaches_the_balances(prepare_bank_account):
    box = JalDepositBox.create("Deposit A", currency_id=2, organization_id=1)
    t_open = d2t(210201)
    move_money(1, box.id(), Decimal('1000'), t_open)
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(box.id()).balance(t_open) == Decimal('1000')
    # It carries its own type, which is what groups deposits together in the balances view
    assert JalAccount(box.id()).account_type() == PredefinedAccountType.Deposit
    assert JalAccount(box.id()).type_icon() == 'tag_deposit.ico'
    # The total of the bank account and the deposit is what the bank account held before the deposit was opened
    assert JalAccount(1).balance(t_open) + JalAccount(box.id()).balance(t_open) == Decimal('10000')
