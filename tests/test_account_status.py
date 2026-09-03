import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_actions
from constants import AccountStatus, AccountData, PredefinedAccountType, PredefinedCategory, Setup
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.balances_model import BalancesModel
from jal.db.common_models import AccountListModel, AccountRecordModel
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter


# ----------------------------------------------------------------------------------------------------------------------
# The status is ORDINAL, and everything in the application filters on 'status >= minimum'. These two facts are what
# make a three-state column as cheap as the boolean it replaced, so they are pinned here rather than assumed.
def test_the_statuses_are_ordered_and_spaced(prepare_db):
    assert AccountStatus.Closed < AccountStatus.Background < AccountStatus.Active
    # Spacing leaves room for a level between two existing ones without renumbering what is already stored
    assert AccountStatus.Background - AccountStatus.Closed > 1
    assert AccountStatus.Active - AccountStatus.Background > 1
    assert set(AccountStatus().get_all_names()) == {AccountStatus.Closed, AccountStatus.Background,
                                                    AccountStatus.Active}


# A new account is Active: an account is created to be used, and nothing else would be a sensible default
def test_a_new_account_is_active(prepare_db):
    account = JalAccountCreator(currency_id=2, number='U1', name='Broker').commit()
    assert account.status() == AccountStatus.Active
    assert account.is_active()
    assert account.is_foreground()


# 'active' and 'foreground' are two different questions, and the whole design rests on their being different:
# a background account is still in use (it takes operations and counts towards every total), it simply does not
# earn a row of its own in the day-to-day views.
def test_active_and_foreground_are_different_questions(prepare_db):
    account = JalAccountCreator(currency_id=2, number='U1', name='Broker').commit()
    account.set_status(AccountStatus.Background)
    assert account.is_active()
    assert not account.is_foreground()
    account.set_status(AccountStatus.Closed)
    assert not account.is_active()
    assert not account.is_foreground()


# set_status() writes through the shared cache, so a second JalAccount for the same id sees the new value
def test_the_status_survives_the_account_cache(prepare_db):
    account = JalAccountCreator(currency_id=2, number='U1', name='Broker').commit()
    account.set_status(AccountStatus.Background)
    assert JalAccount(account.id()).status() == AccountStatus.Background


def _three_accounts():
    active = JalAccountCreator(currency_id=2, number='U1', name='Daily').commit()
    background = JalAccountCreator(currency_id=2, number='U2', name='Sleeping').commit()
    background.set_status(AccountStatus.Background)
    closed = JalAccountCreator(currency_id=2, number='U3', name='Gone').commit()
    closed.set_status(AccountStatus.Closed)
    return active, background, closed


# Each view is a lower bound on the status, so the three of them nest rather than being independent switches
def test_get_all_accounts_reaches_down_to_the_asked_status(prepare_db):
    active, background, closed = _three_accounts()
    def names(**kwargs):
        return sorted(x.name() for x in JalAccount.get_all_accounts(**kwargs))
    assert names(min_status=AccountStatus.Active) == ['Daily']
    assert names(min_status=AccountStatus.Background) == ['Daily', 'Sleeping']
    assert names(min_status=AccountStatus.Closed) == ['Daily', 'Gone', 'Sleeping']
    # The default is "everything still in use", which is what 'active_only=True' meant when the column was a boolean
    assert names() == ['Daily', 'Sleeping']


# ----------------------------------------------------------------------------------------------------------------------
# The migration of an existing database. active=0 becomes Closed and not Background, so nothing moves on screen on
# the day of the upgrade and Background starts empty as a state the user assigns by hand.
_MIGRATION_DELTA = 68   # the delta that introduced the status column, named explicitly and not as the current version
_MIGRATION_FROM = "CREATE TABLE temp_accounts AS SELECT * FROM accounts;"
_MIGRATION_TO = "-- Set new DB schema version"


def _replay_the_migration(project_root):
    with open(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}{_MIGRATION_DELTA}.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_FROM), text.index(_MIGRATION_TO)
    # The delta turns foreign keys off around this section, outside its transaction where SQLite honours the
    # pragma. The replay has to do the same, or the DROP takes every child row of the accounts table with it.
    JalDB().enable_fk(False)
    try:
        for statement in sqlparse.split(text[start:end]):
            if not sqlparse.format(statement, strip_comments=True).strip():
                continue   # a run of comment lines is not a statement
            assert JalDB._exec(statement.strip()) is not None, f"Migration statement failed: {statement}"
    finally:
        JalDB().enable_fk(True)


def test_the_migration_maps_the_old_boolean(prepare_db, project_root):
    kept = JalAccountCreator(currency_id=2, number='U1', name='Kept').commit()
    hidden = JalAccountCreator(currency_id=2, number='U2', name='Hidden').commit()
    # Put the table back the way version 67 held it, so the delta has the column it was written against
    JalDB._exec("ALTER TABLE accounts RENAME COLUMN status TO active")
    JalDB._exec("UPDATE accounts SET active=:value WHERE id=:id", [(":value", 1), (":id", kept.id())])
    JalDB._exec("UPDATE accounts SET active=:value WHERE id=:id", [(":value", 0), (":id", hidden.id())])
    JalDB._exec("INSERT OR REPLACE INTO settings(name, value) VALUES('ShowInactiveAccountBalances', 0)", commit=True)

    _replay_the_migration(project_root)

    JalDB().invalidate_cache()
    assert JalAccount(kept.id()).status() == AccountStatus.Active
    assert JalAccount(hidden.id()).status() == AccountStatus.Closed
    # Nothing is guessed into the new state - it is opted into, one account at a time
    assert JalDB._read("SELECT COUNT(*) FROM accounts WHERE status=:s", [(":s", AccountStatus.Background)]) == 0
    # The balances view reaches down to background - which is empty right now, so it shows exactly what it showed
    # before, and a demoted account will be folded rather than dropped out of the total
    assert JalDB._read("SELECT value FROM settings WHERE name='BalancesMinAccountStatus'") == str(AccountStatus.Background)
    assert JalDB._read("SELECT COUNT(*) FROM settings WHERE name='ShowInactiveAccountBalances'") == 0


# The table is REBUILT, not altered, so that the column's DEFAULT can change with it - and a rebuild drops the
# table every operation references ON DELETE CASCADE. What must survive the drop is everything else in the file.
def test_the_migration_keeps_everything_that_hangs_off_an_account(prepare_db, project_root):
    account = JalAccountCreator(currency_id=2, number='U1', name='Kept', organization=1, precision=4).commit()
    create_actions([(d2t(210101), account.id(), 1, [(PredefinedCategory.Income, Decimal('100'))])])
    JalDB._exec("ALTER TABLE accounts RENAME COLUMN status TO active")
    attributes = JalDB._read("SELECT COUNT(*) FROM account_data WHERE account_id=:id", [(":id", account.id())])
    assert attributes > 0   # the number and the precision are rows of their own

    _replay_the_migration(project_root)

    assert JalDB._read("SELECT COUNT(*) FROM account_data WHERE account_id=:id", [(":id", account.id())]) == attributes
    assert JalDB._read("SELECT COUNT(*) FROM action_details") == 1
    assert JalDB._read("SELECT COUNT(*) FROM actions WHERE account_id=:id", [(":id", account.id())]) == 1
    # The trigger was defined on the dropped table and has to be put back with it
    assert JalDB._read("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' "
                       "AND name='accounts_after_delete_icon'") == 1
    # ... and the point of the rebuild: an INSERT that names no status gets a real one
    JalDB._exec("INSERT INTO accounts (name, currency_id, organization_id) VALUES ('probe', 2, 1)", commit=True)
    assert JalDB._read("SELECT status FROM accounts WHERE name='probe'") == AccountStatus.Active


# ----------------------------------------------------------------------------------------------------------------------
# The two lifecycle dates. They are optional, they are NOT what any view filters on, and 0 means "not known" - which
# is what every account that existed before the attributes did will carry forever.
def test_the_lifecycle_dates_are_optional_and_default_to_unknown(prepare_db):
    account = JalAccountCreator(currency_id=2, number='U1', name='Broker').commit()
    assert account.opened_on() == 0
    assert account.closed_on() == 0

    opened, closed = d2t(200101), d2t(240101)
    account.set_data(AccountData.OpenDate, str(opened))
    account.set_data(AccountData.CloseDate, str(closed))
    JalAccount.db_cache.clear_cache()
    reloaded = JalAccount(account.id())
    assert reloaded.opened_on() == opened
    assert reloaded.closed_on() == closed
    # A date says nothing about the status - the two axes are independent by design
    assert reloaded.status() == AccountStatus.Active


# ----------------------------------------------------------------------------------------------------------------------
# The accounts list is where a status is MANAGED, so background accounts are always in it; only closed ones are
# behind the toggle. The comparison has to be '>=': the old '=1' would now show background accounts alone.
def test_the_accounts_list_hides_only_closed_accounts(prepare_db):
    _three_accounts()
    parent = QWidget()
    dialog = AccountListDialog(parent)
    dialog.setFilter()
    dialog.model.select()
    listed = sorted(dialog.model.data(dialog.model.index(row, dialog.model.fieldIndex("name")), Qt.DisplayRole)
                    for row in range(dialog.model.rowCount()))
    assert listed == ['Daily', 'Sleeping']

    dialog.OnToggleChange(2)   # Qt.Checked
    dialog.model.select()
    listed = sorted(dialog.model.data(dialog.model.index(row, dialog.model.fieldIndex("name")), Qt.DisplayRole)
                    for row in range(dialog.model.rowCount()))
    assert listed == ['Daily', 'Gone', 'Sleeping']


# The list shows the status as a value of its own, not as a checkbox that would have only two of the three to say
def test_the_accounts_list_shows_the_status_value(prepare_db):
    account = JalAccountCreator(currency_id=2, number='U1', name='Daily').commit()
    account.set_status(AccountStatus.Background)
    model = AccountListModel()
    model.select()
    assert model.fieldIndex("active") == -1
    assert model.data(model.index(0, model.fieldIndex("status")), Qt.EditRole) == AccountStatus.Background


# The record model behind the account editor must name the accounts columns in PHYSICAL table order, because the
# mapper addresses them by index. A renamed column keeps its place, and this is what proves the list still lines up.
def test_the_record_model_matches_the_table_layout(prepare_db):
    model = AccountRecordModel()
    model.select()
    stored = [JalDB._read("SELECT name FROM pragma_table_info('accounts') WHERE cid=:cid", [(":cid", cid)])
              for cid in range(model.columnCount())]
    assert stored == [column.name for column in model.column_meta()]
    assert model.fieldIndex("status") >= 0
    assert model.fieldIndex("active") == -1


# ----------------------------------------------------------------------------------------------------------------------
# What the whole change is for: the background accounts collapse into ONE row that still carries their money, so the
# view gets shorter without the balance sheet getting smaller.
def _account_with_money(name, status, amount, timestamp):
    account = JalAccountCreator(currency_id=2, number=name, name=name, organization=1).commit()
    create_actions([(timestamp, account.id(), 1, [(PredefinedCategory.Income, amount)])])
    if status != AccountStatus.Active:
        account.set_status(status)
    return account


def _balances(view_parent, min_status=AccountStatus.Background):
    model = BalancesModel(TreeViewWithFooter(view_parent))
    model.setCurrency(2)
    model.setMinStatus(min_status)
    return model


def _rows(model, parent=None):
    parent = model.index(-1, -1) if parent is None else parent
    column = model.fieldIndex('account_name')
    return [model.data(model.index(row, column, parent), Qt.DisplayRole) for row in range(model.rowCount(parent))]


def test_background_accounts_become_one_group_that_keeps_their_money(prepare_db):
    ts = d2t(210101)
    _account_with_money('Daily', AccountStatus.Active, Decimal('100'), ts)
    _account_with_money('Sleeping', AccountStatus.Background, Decimal('10'), ts)
    _account_with_money('Frozen', AccountStatus.Background, Decimal('5'), ts)
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    model = _balances(parent, AccountStatus.Background)
    model.prepareData()

    groups = _rows(model)
    assert 'Background' in groups
    background = model.index(groups.index('Background'), 0, model.index(-1, -1))
    # One row stands for both accounts, and it carries exactly what they hold together
    assert model.data(background.siblingAtColumn(model.fieldIndex('value_common')), Qt.DisplayRole) == Decimal('15')
    # What is behind the fold is grouped by account type, the way what is in front of it is
    assert _rows(model, background) == ['Cash']
    by_type = model.index(0, 0, background)
    assert sorted(_rows(model, by_type)) == ['Frozen', 'Sleeping']
    # ... and the grand total has lost nothing to the folding
    assert model.footerData(model.fieldIndex('value_common'), Qt.DisplayRole) == '115.00'


# The group is folded when the tree is built, and stays open once the reader opens it - a ledger update rebuilds the
# tree on its own, and a group that snapped shut under a reader would be worse than one that never folded.
def test_the_background_group_is_folded_and_stays_open_once_opened(prepare_db):
    ts = d2t(210101)
    _account_with_money('Daily', AccountStatus.Active, Decimal('100'), ts)
    _account_with_money('Sleeping', AccountStatus.Background, Decimal('10'), ts)
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    view = TreeViewWithFooter(parent)
    model = BalancesModel(view)
    view.setModel(model)
    model.setCurrency(2)
    model.setMinStatus(AccountStatus.Background)
    model.prepareData()

    groups = _rows(model)
    background = model.index(groups.index('Background'), 0, model.index(-1, -1))
    daily = model.index(groups.index('Cash'), 0, model.index(-1, -1))
    assert not view.isExpanded(background)
    assert view.isExpanded(daily)      # every other group opens as it always did

    model.setGroupExpanded(background, True)
    model.prepareData()
    groups = _rows(model)
    assert view.isExpanded(model.index(groups.index('Background'), 0, model.index(-1, -1)))


# A view that reaches only the active accounts has no background group at all - the folding is not a permanent
# fixture of the tree, it appears when there is something to fold.
def test_no_background_group_when_the_view_does_not_reach_it(prepare_db):
    ts = d2t(210101)
    _account_with_money('Daily', AccountStatus.Active, Decimal('100'), ts)
    _account_with_money('Sleeping', AccountStatus.Background, Decimal('10'), ts)
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    model = _balances(parent, AccountStatus.Active)
    model.prepareData()
    assert 'Background' not in _rows(model)
    assert model.footerData(model.fieldIndex('value_common'), Qt.DisplayRole) == '100.00'


# ----------------------------------------------------------------------------------------------------------------------
# The same fold in the portfolio report, which reaches it through its own grouping combo rather than a computed
# field - the model was already generic enough to take one more group level.
def test_the_portfolio_folds_the_background_group(prepare_db):
    from PySide6.QtWidgets import QTreeView
    from jal.db.clock import now_dt
    from jal.db.holdings_model import HoldingsModel

    ts = d2t(210101)
    daily = JalAccountCreator(currency_id=2, number='U1', name='Daily', investing=1, organization=1).commit()
    sleeping = JalAccountCreator(currency_id=2, number='U2', name='Sleeping', investing=1, organization=1).commit()
    create_actions([(ts, daily.id(), 1, [(PredefinedCategory.StartingBalance, 100.0)]),
                    (ts, sleeping.id(), 1, [(PredefinedCategory.StartingBalance, 10.0)])])
    sleeping.set_status(AccountStatus.Background)
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    view = QTreeView(parent)
    model = HoldingsModel(view)
    view.setModel(model)
    model.updateView(currency_id=2, date=now_dt().date(), grouping="status_id;account_id",
                     min_status=AccountStatus.Background)

    column = model.fieldIndex('header')
    root = model.index(-1, -1)
    groups = {model.data(model.index(row, column, root), Qt.DisplayRole): row for row in range(model.rowCount(root))}
    assert set(groups) == {'Active', 'Background'}

    background = model.index(groups['Background'], column, root)
    assert model.data(background.siblingAtColumn(model.fieldIndex('value_common')), Qt.DisplayRole) == Decimal('10')
    assert not view.isExpanded(background)
    # Every other group opens the way it always did
    assert view.isExpanded(model.index(groups['Active'], column, root))


# ----------------------------------------------------------------------------------------------------------------------
# The status is edited through a combo and not a check box, and this is the reason: a check box writes back a
# BOOLEAN, so opening a background account and pressing OK without touching anything would quietly demote it.
def test_editing_an_account_without_changing_it_keeps_its_status(prepare_db):
    from jal.widgets.account_dialog import AccountDialog

    account = JalAccountCreator(currency_id=2, number='U1', name='Sleeping', organization=1).commit()
    account.set_status(AccountStatus.Background)

    parent = QWidget()
    dialog = AccountDialog(parent)
    dialog.setSelectedId(account.id())
    assert dialog.ui.StatusCombo.get_key() == AccountStatus.Background
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    assert JalAccount(account.id()).status() == AccountStatus.Background


# ... and picking another status in that combo does reach the database
def test_the_status_combo_writes_the_new_status(prepare_db):
    from jal.widgets.account_dialog import AccountDialog

    account = JalAccountCreator(currency_id=2, number='U1', name='Daily', organization=1).commit()

    parent = QWidget()
    dialog = AccountDialog(parent)
    dialog.setSelectedId(account.id())
    dialog.ui.StatusCombo.set_key(AccountStatus.Background)
    dialog.accept()

    JalAccount.db_cache.clear_cache()
    assert JalAccount(account.id()).status() == AccountStatus.Background


# ----------------------------------------------------------------------------------------------------------------------
# The balances context menu is the only way into this setting, so what it offers is part of the feature. The three
# views nest, which is why they are one exclusive choice and not three switches the user could combine wrongly.
def test_the_balances_menu_offers_the_three_nested_views(prepare_db):
    from PySide6.QtCore import QPoint
    from jal.widgets.operations_widget import OperationsWidget

    ts = d2t(210101)
    _account_with_money('Daily', AccountStatus.Active, Decimal('100'), ts)
    _account_with_money('Sleeping', AccountStatus.Background, Decimal('10'), ts)
    Ledger().rebuild(from_timestamp=0)

    operations = OperationsWidget(None)
    operations.balances_context_menu(QPoint(0, 0))
    # The menu is built as a child of the tree view, and the submenu is reached through the action that carries it
    menu = [child for child in operations.ui.BalancesTreeView.children()
            if child.metaObject().className() == 'QMenu'][-1]
    accounts_action = [action for action in menu.actions() if action.menu() is not None][0]
    offered = [action.text() for action in accounts_action.menu().actions()]
    assert offered == list(AccountStatus().visibility_names().values())
    # Exactly one is marked, and it is the reach the model actually has
    checked = [action for action in accounts_action.menu().actions() if action.isChecked()]
    assert len(checked) == 1
    assert checked[0].text() == AccountStatus().visibility_names()[operations.balances_model.minStatus()]

    # Choosing a wider view widens the model, and the choice is remembered in the settings
    [action for action in accounts_action.menu().actions()
     if action.text() == AccountStatus().visibility_names()[AccountStatus.Background]][0].trigger()
    assert operations.balances_model.minStatus() == AccountStatus.Background
    assert 'Background' in _rows(operations.balances_model)
    assert JalDB._read("SELECT value FROM settings WHERE name='BalancesMinAccountStatus'") \
           == str(AccountStatus.Background)


# JalAccount(0) is the "no such account" sentinel handed around all over the application. It answered is_active()
# with False when the column was a boolean, and it has to keep answering the same way.
def test_a_missing_account_is_not_active(prepare_db):
    missing = JalAccount(0)
    assert missing.status() == AccountStatus.Closed
    assert not missing.is_active()
    assert not missing.is_foreground()


# A day-to-day account takes ONE level, a background one takes two. The rule that makes that work is that an empty
# group value means "no level here" - without it every foreground account would gain an empty row of its own.
def test_the_two_halves_of_the_tree_are_nested_differently(prepare_db):
    ts = d2t(210101)
    daily = JalAccountCreator(currency_id=2, number='D', name='Daily', organization=1).commit()
    create_actions([(ts, daily.id(), 1, [(PredefinedCategory.Income, Decimal('100'))])])
    bank = JalAccountCreator(currency_id=2, number='B', name='Old bank', organization=1,
                             account_type=PredefinedAccountType.Bank).commit()
    create_actions([(ts, bank.id(), 1, [(PredefinedCategory.Income, Decimal('7'))])])
    wallet = JalAccountCreator(currency_id=2, number='W', name='Old card', organization=1,
                               account_type=PredefinedAccountType.Card).commit()
    create_actions([(ts, wallet.id(), 1, [(PredefinedCategory.Income, Decimal('3'))])])
    for account in (bank, wallet):
        account.set_status(AccountStatus.Background)
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    model = _balances(parent)
    model.prepareData()
    groups = _rows(model)
    # The foreground type group holds its accounts directly - no empty level was inserted under it
    assert _rows(model, model.index(groups.index('Cash'), 0, model.index(-1, -1))) == ['Daily']
    # The background group holds type groups, which hold the accounts
    background = model.index(groups.index('Background'), 0, model.index(-1, -1))
    assert _rows(model, background) == ['Bank account', 'Card']
    assert _rows(model, model.index(0, 0, background)) == ['Old bank']
    assert model.data(background.siblingAtColumn(model.fieldIndex('value_common')), Qt.DisplayRole) == Decimal('10')


# Demoting an account must FOLD it, never make its money disappear - so the default reach is background, not active
def test_a_demoted_account_keeps_counting_towards_the_total(prepare_db):
    ts = d2t(210101)
    _account_with_money('Daily', AccountStatus.Active, Decimal('100'), ts)
    quiet = _account_with_money('Sleeping', AccountStatus.Active, Decimal('10'), ts)
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    model = _balances(parent)   # the default reach, as a freshly opened window has it
    model.prepareData()
    assert model.footerData(model.fieldIndex('value_common'), Qt.DisplayRole) == '110.00'

    quiet.set_status(AccountStatus.Background)
    model.prepareData()
    assert 'Background' in _rows(model)
    assert model.footerData(model.fieldIndex('value_common'), Qt.DisplayRole) == '110.00'


# The portfolio report opens folded the same way, through its own grouping combo rather than a computed field
def test_the_portfolio_opens_grouped_by_status(prepare_db):
    ts = d2t(210101)
    daily = JalAccountCreator(currency_id=2, number='U1', name='Daily', investing=1, organization=1).commit()
    sleeping = JalAccountCreator(currency_id=2, number='U2', name='Sleeping', investing=1, organization=1).commit()
    create_actions([(ts, daily.id(), 1, [(PredefinedCategory.StartingBalance, 100.0)]),
                    (ts, sleeping.id(), 1, [(PredefinedCategory.StartingBalance, 10.0)])])
    sleeping.set_status(AccountStatus.Background)
    Ledger().rebuild(from_timestamp=0)

    from PySide6.QtWidgets import QTreeView
    from jal.db.clock import now_dt
    from jal.db.holdings_model import HoldingsModel
    parent = QWidget()
    view = QTreeView(parent)
    model = HoldingsModel(view)
    view.setModel(model)
    # The model's own default reach - what the report shows before anything is touched
    assert model._min_status == AccountStatus.Background
    model.updateView(currency_id=2, date=now_dt().date(), grouping="status_id;currency_id;account_id",
                     min_status=AccountStatus.Background)
    root = model.index(-1, -1)
    column = model.fieldIndex('header')
    assert [model.data(model.index(row, column, root), Qt.DisplayRole) for row in range(model.rowCount(root))] \
           == ['Active', 'Background']
