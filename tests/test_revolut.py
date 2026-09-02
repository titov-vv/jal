import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import datetime
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import dt2t

from jal.constants import PredefinedCategory, PredefinedAccountType
from jal.data_import.card_match import CardMatcher
from jal.data_import.statement import JSF, Statement_ImportError
from jal.data_import.broker_statements.revolut import (StatementRevolut, REVOLUT_CURRENT_ACCOUNT_SETTING,
                                                       REVOLUT_DEPOSIT_ACCOUNT_SETTING)
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction
from jal.db.peer import JalPeer
from jal.db.settings import JalSettings

STATEMENT = 'revolut_statement_pt.csv'
EUR = 3
# Every moment of the fixture is in March, before the EU clocks go forward, so Lisbon keeps UTC there and the
# expected timestamps are the digits of the file. test_revolut_timezone() covers the half of the year that shifts.
NOTHING = {'import': False, 'peer': 0, 'category': 0, 'description': ''}


# ----------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def prepare_db_revolut(prepare_db):
    bank = JalPeer(data={'name': 'Revolut'}, create=True).id()
    current = JalAccountCreator(currency_id=EUR, number='REV-CURRENT', name='Revolut', organization=bank,
                                account_type=PredefinedAccountType.Card).commit()
    savings = JalAccountCreator(currency_id=EUR, number='REV-SAVINGS', name='Revolut Boosted', organization=bank,
                                account_type=PredefinedAccountType.Deposit).commit()
    JalSettings().setValue(REVOLUT_CURRENT_ACCOUNT_SETTING, current.id())
    JalSettings().setValue(REVOLUT_DEPOSIT_ACCOUNT_SETTING, savings.id())
    yield current.id(), savings.id()


def data_path_of(filename: str) -> str:
    return os.path.dirname(os.path.abspath(__file__)) + os.sep + "test_data" + os.sep + filename


def load_statement() -> StatementRevolut:
    statement = StatementRevolut()
    statement.load(data_path_of(STATEMENT))
    return statement


# Records a card purchase the way the user types one in: an account, a peer and one category line
def store_operation(account_id, timestamp, amount, peer_name, category_id=PredefinedCategory.Spending):
    peer_id = JalPeer(data={'name': peer_name}, search=True, create=True).id()
    return LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, {
        "timestamp": timestamp, "account_id": account_id, "peer_id": peer_id,
        "lines": [{"category_id": category_id, "amount": Decimal(amount), "note": "Purchase"}]})


# A refund carries the name of the merchant that issued it, so a name alone can stand for two rows - 'paid' tells
# the purchase from the money that came back.
def reviewed_of(statement, merchant: str, paid: bool = True) -> dict:
    found = [x for x in statement._card_rows
             if x['merchant'] == merchant and ((x['amount'] < 0) == paid)]
    assert len(found) == 1, f"{len(found)} reviewed rows named '{merchant}'"
    return found[0]


def operation_of(statement, statement_id: int) -> dict:
    return [x for x in statement._data[JSF.INCOME_SPENDING] if x['id'] == statement_id][0]


# ----------------------------------------------------------------------------------------------------------------------
def test_revolut_parsing(prepare_db_revolut):
    statement = load_statement()
    data = statement._data

    # One file, two accounts - the 'Product' column is what tells them apart, and neither carries a number
    assert len(data[JSF.ACCOUNTS]) == 2
    assert all('number' not in x for x in data[JSF.ACCOUNTS])
    assert set(statement._account_ids) == {StatementRevolut.CURRENT, StatementRevolut.DEPOSIT}

    # The period is that of the completed rows: the pending purchase of Mar 14 is not part of it
    assert data[JSF.PERIOD] == [dt2t(2603021000), dt2t(2603130800)]

    # Money moved between the two accounts is ONE transfer, built from the two rows that describe it
    assert len(data[JSF.TRANSFERS]) == 2
    current, savings = statement._account_ids[StatementRevolut.CURRENT], statement._account_ids[StatementRevolut.DEPOSIT]
    into_pocket = [x for x in data[JSF.TRANSFERS] if x['withdrawal'] == Decimal('400')][0]
    assert into_pocket['account'][:2] == [current, savings]
    assert into_pocket['timestamp'] == dt2t(2603061100)
    out_of_pocket = [x for x in data[JSF.TRANSFERS] if x['withdrawal'] == Decimal('50')][0]
    assert out_of_pocket['account'][:2] == [savings, current]

    # Interest: the gross Revolut credited and the tax it withheld beside it, as the deposits of this ledger do
    interest = [x for x in data[JSF.INCOME_SPENDING] if x['account'] == savings]
    assert len(interest) == 3
    taxed = [x for x in interest if x['timestamp'] == dt2t(2603070120)][0]
    assert [(l['amount'], l['category']) for l in taxed['lines']] == [
        (Decimal('0.03'), PredefinedCategory.Interest), (Decimal('-0.01'), PredefinedCategory.Taxes)]
    untaxed = [x for x in interest if x['timestamp'] == dt2t(2603080120)][0]
    assert len(untaxed['lines']) == 1        # a zero tax is not a line of its own
    assert untaxed['lines'][0]['amount'] == Decimal('0.02')

    # Purchases, refunds and rewards are parsed with no peer and no category - neither exists in the statement
    assert len(statement._card_rows) == 6
    assert all(x['peer'] == 0 and x['lines'][0]['category'] == 0
               for x in data[JSF.INCOME_SPENDING] if x['account'] == current)
    # A card fee is money that left on top of the purchase and is kept inside it, the way it is recorded today
    assert reviewed_of(statement, 'Coffee house')['amount'] == Decimal('-7.30')
    assert reviewed_of(statement, 'Coffee house', paid=False)['amount'] == Decimal('7.30')
    assert reviewed_of(statement, 'Green grocer')['amount'] == Decimal('-18.40')
    # Revolut states no merchant category at all
    assert all(x['merchant_category'] == '' for x in statement._card_rows)

    # Nothing is dropped silently: what the file states and this module doesn't place is counted and reported
    skipped = statement.skipped()
    assert sum(skipped.values()) == 4
    assert [v for k, v in skipped.items() if 'not completed' in k] == [2]     # the reverted and the pending row
    assert [v for k, v in skipped.items() if "other end" in k] == [2]         # the top-up and the transfer to a peer


# ----------------------------------------------------------------------------------------------------------------------
# Revolut writes its timestamps on the wall clock of the account's country. March keeps UTC in Lisbon, July doesn't.
def test_revolut_timezone(prepare_db_revolut):
    statement = StatementRevolut()
    winter = statement._timestamp({'started': '2026-03-03 12:15:30'})
    summer = statement._timestamp({'started': '2026-07-03 12:15:30'})
    assert winter == dt2t(2603031215) + 30
    assert summer == dt2t(2607031115) + 30      # WEST is one hour ahead of UTC


# ----------------------------------------------------------------------------------------------------------------------
def test_revolut_review_and_import(prepare_db_revolut):
    current_id, savings_id = prepare_db_revolut
    # What the user typed by hand: the same purchases, on a clock that doesn't quite agree
    store_operation(current_id, dt2t(2603031216), '-18.40', 'Green grocer')          # a minute apart
    store_operation(current_id, dt2t(2603041005), '-7.30', 'Coffee house')           # an hour apart
    store_operation(current_id, dt2t(2603071400), '7.30', 'Coffee house', PredefinedCategory.Income)

    statement = load_statement()
    stored = CardMatcher.stored_operations(current_id, *statement.period(), incomes=True)
    assert len(stored) == 3          # the refund is a candidate as much as the two purchases
    proposal = CardMatcher.propose(statement._card_rows, stored)
    matched = {row['merchant']: match for row, match in zip(statement._card_rows, proposal)}
    assert matched['Green grocer'] is not None
    assert matched['Coffee house'] is not None
    assert matched['Recompensa por convite'] is None      # nothing of that amount was ever typed in
    # A refund of 7.30 and a purchase of 7.30 are not the same operation - only equal amounts pair, sign included
    refund = [(row, match) for row, match in zip(statement._card_rows, proposal) if row['amount'] > 0]
    assert len(refund) == 2 and refund[0][1]['amount'] == Decimal('7.30')

    stored_actions = JalDB._read("SELECT COUNT(*) FROM actions")
    statement = load_statement()
    grocer = JalPeer(data={'name': 'Green grocer'}, search=True).id()
    # Everything the user already typed in is left out; the reward is the one thing that is taken
    statement._card_decisions_for_tests = [
        NOTHING if x['merchant'] != 'Recompensa por convite'
        else {'import': True, 'peer': grocer, 'category': PredefinedCategory.Income, 'description': 'Referral'}
        for x in statement._card_rows]
    statement.match_db_ids()
    statement.import_into_db()

    # Two transfers, three interest operations and the single reward
    assert JalDB._read("SELECT COUNT(*) FROM transfers") == 2
    assert JalDB._read("SELECT COUNT(*) FROM actions") == stored_actions + 4
    assert JalDB._read("SELECT COUNT(*) FROM action_details WHERE category_id=:tax",
                       [(":tax", PredefinedCategory.Taxes)]) == 2
    reward = JalDB._read("SELECT oid FROM actions WHERE note='Referral'")
    assert JalDB._read("SELECT note FROM action_details WHERE pid=:oid", [(":oid", reward)]) == ''
    # Interest is recorded against the bank, taken from the account it was paid into
    interest_peer = JalDB._read("SELECT a.peer_id FROM actions AS a JOIN action_details AS d ON d.pid=a.oid "
                                "WHERE a.account_id=:account AND d.category_id=:interest LIMIT 1",
                                [(":account", savings_id), (":interest", PredefinedCategory.Interest)])
    assert interest_peer == JalAccount(savings_id).organization()
    assert JalDB._read("SELECT SUM(CAST(amount AS REAL)) FROM action_details AS d JOIN actions AS a ON a.oid=d.pid "
                       "WHERE a.account_id=:account", [(":account", savings_id)]) == pytest.approx(0.06)


# ----------------------------------------------------------------------------------------------------------------------
# An interest payment carries nothing that identifies it and is never shown to the user, so the day it was paid on
# is what keeps a second import from storing it twice.
def test_revolut_interest_is_not_stored_twice(prepare_db_revolut):
    current_id, savings_id = prepare_db_revolut
    statement = load_statement()
    statement._card_decisions_for_tests = [NOTHING] * len(statement._card_rows)
    statement.match_db_ids()
    statement.import_into_db()
    assert JalDB._read("SELECT COUNT(*) FROM actions") == 3

    again = load_statement()
    again._card_decisions_for_tests = [NOTHING] * len(again._card_rows)
    again.match_db_ids()
    assert [v for k, v in again.skipped().items() if 'in the database already' in k and 'interest' in k] == [3]
    again.import_into_db()
    assert JalDB._read("SELECT COUNT(*) FROM actions") == 3
    assert JalDB._read("SELECT COUNT(*) FROM transfers") == 2      # a transfer identifies itself


# ----------------------------------------------------------------------------------------------------------------------
def test_revolut_refusals(tmp_path, prepare_db_revolut):
    lines = open(data_path_of(STATEMENT), encoding='utf-8').read().splitlines()
    header, body = lines[0], lines[1:]

    def statement_of(rows) -> str:
        path = str(tmp_path / "revolut.csv")
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(rows))
        return path

    # A kind of operation this module doesn't know is named and stops the import - a currency exchange lands here,
    # and guessing how money moved is exactly what must not happen
    unknown = statement_of([header, 'Câmbio,Atual,2026-03-02 10:00:00,2026-03-02 10:00:00,USD,-10.00,0.00,EUR,'
                                    'CONCLUÍDA,100.00'])
    with pytest.raises(Statement_ImportError, match="Câmbio"):
        StatementRevolut().load(unknown)

    # A column beyond the ones this module knows may be money that belongs to an operation
    extra = statement_of([header + ',Imposto', body[0] + ',0.50'])
    with pytest.raises(Statement_ImportError, match="Imposto"):
        StatementRevolut().load(extra)

    # A file whose own balances don't follow from its own amounts is not a file to import
    broken = statement_of([header, body[0], body[1].replace('481.60', '481.61')])
    with pytest.raises(Statement_ImportError, match="balance"):
        StatementRevolut().load(broken)

    # A movement of the savings pocket whose counterpart isn't in the file would leave its balance wrong. The
    # pocket's own balances still follow from its own rows here, so this is not the check above under another name.
    orphan = statement_of([header] + [x for x in body if ',Depósito,' in x])
    with pytest.raises(Statement_ImportError, match="counterpart"):
        StatementRevolut().load(orphan)

    # A second currency means an account per currency, and the file says nothing about which is which
    two_currencies = statement_of([header, body[0], body[1].replace(',EUR,', ',USD,')])
    with pytest.raises(Statement_ImportError, match="currency"):
        StatementRevolut().load(two_currencies)


# ----------------------------------------------------------------------------------------------------------------------
def test_revolut_account_settings(prepare_db_revolut):
    current_id, savings_id = prepare_db_revolut

    statement = load_statement()
    JalSettings().setValue(REVOLUT_DEPOSIT_ACCOUNT_SETTING, 0)
    with pytest.raises(Statement_ImportError, match="Preferences"):
        statement.match_db_ids()

    # An account in another currency is not this statement's account, whatever the setting says
    other = JalAccountCreator(currency_id=2, number='USD-ACC', name='USD account').commit()
    JalSettings().setValue(REVOLUT_DEPOSIT_ACCOUNT_SETTING, other.id())
    with pytest.raises(Statement_ImportError, match="currency"):
        statement.match_db_ids()


# ----------------------------------------------------------------------------------------------------------------------
def test_revolut_accounts_are_set_in_preferences(prepare_db_revolut):
    from PySide6.QtWidgets import QWidget
    from jal.db.settings_registry import SettingsRegistry
    from jal.widgets.preferences_dialog import PreferencesDialog

    current_id, savings_id = prepare_db_revolut
    # The module registers its settings itself, so importing it is what puts them into the dialog
    keys = [x.key for x in SettingsRegistry.settings_of_page('Import')]
    assert REVOLUT_CURRENT_ACCOUNT_SETTING in keys and REVOLUT_DEPOSIT_ACCOUNT_SETTING in keys

    parent = QWidget()
    dialog = PreferencesDialog(parent)
    assert dialog._editors[REVOLUT_CURRENT_ACCOUNT_SETTING].selected_id == current_id
    assert dialog._editors[REVOLUT_DEPOSIT_ACCOUNT_SETTING].selected_id == savings_id
    parent.close()
