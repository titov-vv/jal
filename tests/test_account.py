import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtSql import QSqlTableModel

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AccountData, Setup
from jal.db.account import JalAccount, JalAccountCreator
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
    assert cash.number() is None
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
