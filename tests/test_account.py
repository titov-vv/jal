import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtSql import QSqlTableModel

import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AccountData, Setup
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.db import JalDB
from jal.db.tag import JalTag
from jal.db.common_models import AccountListModel, AccountDataModel


# ----------------------------------------------------------------------------------------------------------------------
# Fields number/credit/country/precision live in the 'account_data' table (not 'accounts' columns) since schema v61.
def test_account_data_roundtrip(prepare_db):
    # A bank account with an explicit number, country (code 'us') and non-default precision
    account = JalAccountCreator(currency_id=2, number='40817', name='Bank', investing=0,
                                organization=1, country='us', precision=4,
                                account_type=PredefinedAccountType.Bank).commit()
    assert account.id() == 1
    assert account.account_type() == PredefinedAccountType.Bank
    assert account.type_name() == "Bank account"
    assert account.number() == '40817'
    assert account.precision() == 4
    assert account.country().code() == 'us'
    # Raw attribute accessor
    assert account.get_data(AccountData.Number) == '40817'
    assert account.get_data(AccountData.Precision) == '4'
    # Only non-default attributes are materialized (credit stays default -> no row, no credit limit)
    assert account.credit_limit() == Decimal('0')
    assert account.get_data(AccountData.Credit) is None

    # A plain cash account with all defaults writes no account_data rows at all
    cash = JalAccountCreator(currency_id=2, number='', name='Petty cash').commit()
    assert cash.account_type() == PredefinedAccountType.Cash
    assert cash.number() == ''
    assert cash.precision() == Setup.DEFAULT_ACCOUNT_PRECISION
    assert cash.country().id() == 0


# find() locates an account by its number even though 'number' now lives in account_data
def test_find_by_number(prepare_db):
    JalAccountCreator(currency_id=2, number='U7654321', name='Broker', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()
    found = JalAccount.find({'number': 'U7654321', 'currency': 2})
    assert found.id() == 1
    assert found.account_type() == PredefinedAccountType.Broker
    missing = JalAccount.find({'number': 'NOPE', 'currency': 2})
    assert missing.id() == 0


# Creating an account with the same number under a new currency clones it, carrying account_data across
def test_clone_similar_account_copies_attributes(prepare_db):
    JalAccountCreator(currency_id=2, number='40817', name='Bank.USD', country='us', precision=4,
                      account_type=PredefinedAccountType.Bank).commit()
    clone = JalAccountCreator(currency_id=1, number='40817').commit()  # same number, different currency -> clone
    assert clone.id() == 2
    assert clone.currency() == 1
    assert clone.account_type() == PredefinedAccountType.Bank
    assert clone.number() == '40817'
    assert clone.precision() == 4
    assert clone.country().code() == 'us'


# get_all_types reports only the account types actually in use
def test_get_all_types(prepare_db):
    JalAccountCreator(currency_id=2, number='A', account_type=PredefinedAccountType.Bank).commit()
    JalAccountCreator(currency_id=2, number='B', account_type=PredefinedAccountType.Broker).commit()
    types = JalAccount.get_all_types()
    assert types == {PredefinedAccountType.Bank: "Bank account",
                     PredefinedAccountType.Broker: "Broker account"}


# The accounts reference grid exposes 'account_type' (not tag_id) and no longer selects moved columns
def test_account_list_model_shape(prepare_db):
    JalAccountCreator(currency_id=2, number='X', account_type=PredefinedAccountType.Bank).commit()
    model = AccountListModel()
    model.select()
    assert model.fieldIndex("account_type") >= 0
    for gone in ("tag_id", "number", "country_id", "precision", "credit"):
        assert model.fieldIndex(gone) == -1
    # the stored value of the account_type cell is the enum id (rendered to a name by the delegate)
    assert model.data(model.index(0, model.fieldIndex("account_type")), Qt.EditRole) == PredefinedAccountType.Bank


# Adding/editing a row in the account-details grid writes through to 'account_data' and JalAccount reads it back
def test_account_data_model_roundtrip(prepare_db):
    acc = JalAccountCreator(currency_id=2, number='', account_type=PredefinedAccountType.Cash).commit()
    model = AccountDataModel()
    model.setEditStrategy(QSqlTableModel.OnFieldChange)
    model.filterBy("account_id", acc.id())
    model.addElement(model.index(0, 0))          # default attribute = Number, account_id from filter
    model.submitAll()
    model.select()
    model.setData(model.index(0, model.fieldIndex("value")), "ACC-123")
    model.submitAll()
    model.select()
    JalAccount.db_cache.clear_cache()
    reloaded = JalAccount(acc.id())
    assert reloaded.number() == "ACC-123"
    assert reloaded.get_data(AccountData.Number) == "ACC-123"


# ----------------------------------------------------------------------------------------------------------------------
# An account may carry a tag (AccountData.Tag), stored in 'account_data' the way an asset's tag is stored in
# 'asset_data'. It is what the balances and holdings trees group accounts by.
def test_account_tag_roundtrip(prepare_db):
    cash = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")
    account = JalAccountCreator(currency_id=2, number='U1', name='Wallet', organization=1).commit()

    assert account.tag().id() == 0            # an account carries none until one is put on it
    assert account.get_data(AccountData.Tag) is None

    account.set_tag(cash)
    assert account.tag().id() == cash
    assert account.tag().name() == 'Cash'
    assert JalAccount(account.id()).tag().id() == cash          # ... and it survives a reload through the cache

    account.set_tag(0)                        # clearing it removes the row rather than storing a zero
    assert account.tag().id() == 0
    assert account.get_data(AccountData.Tag) is None


# A tag is deleted from under the accounts that carried it, which no foreign key can express - the
# 'tags_after_delete' trigger drops those attribute rows the same way it drops an asset's.
def test_deleting_a_tag_takes_it_off_the_accounts(prepare_db):
    cash = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")
    account = JalAccountCreator(currency_id=2, number='U1', name='Wallet', organization=1).commit()
    account.set_tag(cash)
    assert JalAccount(account.id()).tag().id() == cash

    JalDB._exec("DELETE FROM tags WHERE id=:id", [(":id", cash)], commit=True)
    JalDB().invalidate_cache()

    assert JalDB._read("SELECT value FROM account_data WHERE account_id=:id AND datatype=:type",
                       [(":id", account.id()), (":type", AccountData.Tag)]) is None
    assert JalAccount(account.id()).tag().id() == 0


# Replacing a tag with another one carries the accounts over to it, beside the assets and the operations
def test_replacing_a_tag_repoints_the_accounts(prepare_db):
    cash = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")
    card = JalDB._read("SELECT id FROM tags WHERE tag='Card'")
    account = JalAccountCreator(currency_id=2, number='U1', name='Wallet', organization=1).commit()
    account.set_tag(cash)

    JalTag(cash).replace_with(card)

    assert JalAccount(account.id()).tag().id() == card


# ----------------------------------------------------------------------------------------------------------------------
# The 66 -> 67 migration, run from the shipped delta file rather than copied here, so this test breaks if the
# migration text stops doing what it says: it is the trigger that takes a deleted tag off the accounts.
_MIGRATION_FROM = "-- AN ACCOUNT MAY CARRY A TAG"
_MIGRATION_TO = "-- Set new DB schema version"

# The trigger schema 66 shipped - it knew about an asset's tag but not about an account's
_OLD_SCHEMA = """
DROP TRIGGER tags_after_delete;
CREATE TRIGGER tags_after_delete AFTER DELETE ON tags FOR EACH ROW
BEGIN
    DELETE FROM ledger WHERE timestamp >= (SELECT MIN(timestamp) FROM ledger WHERE tag_id=OLD.id);
    DELETE FROM asset_data WHERE datatype=1 AND value=OLD.id;
END;
"""


def test_account_tag_migration(prepare_db, project_root):
    for statement in sqlparse.split(_OLD_SCHEMA):
        assert JalDB._exec(statement.strip()) is not None, f"Can't restore the old schema: {statement}"
    cash = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")
    account = JalAccountCreator(currency_id=2, number='U1', name='Wallet', organization=1).commit()
    account.set_tag(cash)

    with open(project_root + "/jal/updates/jal_delta_67.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_FROM), text.index(_MIGRATION_TO)
    for statement in sqlparse.split(text[start:end]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue   # a run of comment lines is not a statement
        assert JalDB._exec(statement.strip()) is not None, f"Migration statement failed: {statement}"

    # The account keeps the tag the migration found on it ...
    JalDB().invalidate_cache()
    assert JalAccount(account.id()).tag().id() == cash
    # ... and the rebuilt trigger now takes it away with the tag itself
    JalDB._exec("DELETE FROM tags WHERE id=:id", [(":id", cash)], commit=True)
    assert JalDB._read("SELECT COUNT(*) FROM account_data WHERE datatype=:type", [(":type", AccountData.Tag)]) == 0
