import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import dt2t

from jal.constants import PredefinedCategory, PredefinedAccountType
from jal.data_import.statement import JSF, Statement_ImportError
from jal.data_import.card_match import CardMatcher
from jal.data_import.broker_statements.trading212 import StatementTrading212, T212_ACCOUNT_SETTING
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction
from jal.db.peer import JalPeer
from jal.db.settings import JalSettings

FIRST = 't212_from_2026-03-01_to_2026-03-31_dGVzdC1maXJzdA.csv'
SECOND = 't212_from_2026-04-01_to_2026-04-30_dGVzdC1zZWNvbmQ.csv'
EUR = 3


# ----------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def prepare_db_t212(prepare_db):
    account = JalAccountCreator(currency_id=EUR, number='TEST-212', name='Trading212 test', investing=1,
                                organization=JalPeer(data={'name': 'Trading212'}, create=True).id(),
                                precision=10, account_type=PredefinedAccountType.Broker).commit()
    assert account.id() == 1
    JalSettings().setValue(T212_ACCOUNT_SETTING, account.id())
    yield account.id()


# Records a card purchase the way the user types one in: an account, a peer and one category line
def store_card_operation(account_id, timestamp, amount, peer_name, category_id=PredefinedCategory.Spending):
    peer_id = JalPeer(data={'name': peer_name}, search=True, create=True).id()
    LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, {
        "timestamp": timestamp, "account_id": account_id, "peer_id": peer_id,
        "lines": [{"category_id": category_id, "amount": Decimal(amount), "note": "Purchase"}]})


def load_first():
    statement = StatementTrading212()
    statement.load(data_path_of(FIRST))
    return statement


def data_path_of(filename: str) -> str:
    return os.path.dirname(os.path.abspath(__file__)) + os.sep + "test_data" + os.sep + filename


def one(records, **match):
    found = [x for x in records if all(x.get(k) == v for k, v in match.items())]
    assert len(found) == 1, f"{len(found)} records match {match}"
    return found[0]


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_t212_parsing(prepare_db_t212):
    statement = load_first()
    data = statement._data

    assert data[JSF.PERIOD] == [dt2t(2603010000), dt2t(2603312359) + 59]
    assert len(data[JSF.ACCOUNTS]) == 1
    account = data[JSF.ACCOUNTS][0]
    assert 'number' not in account          # the export names no account - the user does, in the preferences
    assert account['currency'] == statement.currency_id('EUR')

    # Trades: the price is the quotient of what moved by what was bought, at 15 significant digits. Multiplying the
    # reported price by the reported quantity does NOT give the reported total, which is the whole point of it.
    assert len(data[JSF.TRADES]) == 2
    first = one(data[JSF.TRADES], number='EOF10000000001')
    assert first['quantity'] == Decimal('2.15')
    assert first['price'] == Decimal('6.31627906976744')
    assert first['fee'] == Decimal('0')
    assert first['timestamp'] == dt2t(2603050700) + 5
    second = one(data[JSF.TRADES], number='EOF10000000002')
    assert second['price'] == Decimal('6.34285714285714')

    # Dividend: gross is what reached the account plus the tax stated beside it, and the note keeps the per-share
    # rate the way every dividend of this account already spells it.
    assert len(data[JSF.ASSET_PAYMENTS]) == 1
    dividend = data[JSF.ASSET_PAYMENTS][0]
    assert dividend['type'] == JSF.PAYMENT_DIVIDEND
    assert dividend['amount'] == Decimal('20.62')
    assert dividend['tax'] == Decimal('0.00')
    assert dividend['number'] == ''
    assert dividend['description'] == 'ZETA(IE00TEST0002) CASH DIVIDEND EUR 0.412345 PER SHARE'

    # Interest and cashback come in one operation per statement row, as the statement states them
    incomes = [x for x in data[JSF.INCOME_SPENDING] if x['lines'][0]['amount'] > 0]
    assert len(incomes) == 5
    interest = [x for x in incomes if x['lines'][0]['description'] == 'Interest on cash']
    cashback = [x for x in incomes if x['lines'][0]['description'] == 'Spending cashback']
    assert len(interest) == 3 and len(cashback) == 2
    assert all(x['lines'][0]['category'] == PredefinedCategory.Interest for x in incomes)
    assert sum(x['lines'][0]['amount'] for x in interest) == Decimal('1.66')

    # Card purchases are parsed with no peer and no category - neither exists in the statement
    assert len(statement._card_rows) == 6
    assert all(x['peer'] == 0 and x['lines'][0]['category'] == 0
               for x in data[JSF.INCOME_SPENDING] if x['lines'][0]['amount'] < 0)


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_t212_card_matching(prepare_db_t212):
    account_id = prepare_db_t212
    # What the user typed by hand: the same purchase read off a receipt, on a clock that doesn't quite agree
    store_card_operation(account_id, dt2t(2603041216), '-18.40', 'Green grocer')          # a minute apart
    store_card_operation(account_id, dt2t(2603091805) + 12, '-7.25', 'Coffee house')      # an hour apart
    store_card_operation(account_id, dt2t(2603121045), '-42.00', 'Hardware depot')        # a quarter of an hour
    near = store_card_operation(account_id, dt2t(2603220912), '-9.50', 'Green grocer')
    far = store_card_operation(account_id, dt2t(2603221738), '-9.50', 'Green grocer')
    store_card_operation(account_id, dt2t(2603251100), '-33.10', 'Green grocer')          # not in the statement

    statement = load_first()
    stored = CardMatcher.stored_operations(account_id, *statement.period())
    assert len(stored) == 6
    proposal = CardMatcher.propose(statement._card_rows, stored)

    matched = {row['merchant']: match for row, match in zip(statement._card_rows, proposal)}
    # An amount whose decimals have no exact binary form must pair as surely as one that has - see stored_operations()
    assert [x for x in stored if x['amount'] == Decimal('-18.40')]
    assert matched['COFFEE HOUSE 42'] is not None       # an hour of drift is still the same purchase
    assert matched['HARDWARE DEPOT'] is not None
    assert matched['BOOK CORNER'] is None               # nothing of that amount was ever typed in

    # Two purchases of the same amount on the same day take the counterpart that is nearest in time, each its own
    same_amount = [(row['timestamp'], match) for row, match in zip(statement._card_rows, proposal)
                   if row['amount'] == Decimal('-9.50')]
    assert len(same_amount) == 2
    assert all(match is not None for _timestamp, match in same_amount)
    assert {match['oid'] for _timestamp, match in same_amount} == {x['oid'] for x in stored
                                                                   if x['amount'] == Decimal('-9.50')}
    morning = [match for timestamp, match in same_amount if timestamp == dt2t(2603220910)][0]
    assert morning['timestamp'] == dt2t(2603220912)


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_t212_import(prepare_db_t212):
    account_id = prepare_db_t212
    store_card_operation(account_id, dt2t(2603041216), '-18.40', 'Green grocer')
    store_card_operation(account_id, dt2t(2603091805) + 12, '-7.25', 'Coffee house')
    store_card_operation(account_id, dt2t(2603121045), '-42.00', 'Hardware depot')
    store_card_operation(account_id, dt2t(2603220912), '-9.50', 'Green grocer')
    store_card_operation(account_id, dt2t(2603221738), '-9.50', 'Green grocer')
    stored_before = JalDB._read("SELECT COUNT(*) FROM actions")

    book_corner = JalPeer(data={'name': 'Book corner'}, create=True).id()
    statement = StatementTrading212()
    # The one purchase that isn't in the database is the one the dialog would ask about
    statement._card_decisions_for_tests = [
        {'import': False, 'peer': 0, 'category': 0, 'description': ''},
        {'import': False, 'peer': 0, 'category': 0, 'description': ''},
        {'import': False, 'peer': 0, 'category': 0, 'description': ''},
        {'import': True, 'peer': book_corner, 'category': PredefinedCategory.Spending, 'description': 'A book'},
        {'import': False, 'peer': 0, 'category': 0, 'description': ''},
        {'import': False, 'peer': 0, 'category': 0, 'description': ''}]
    statement.load(data_path_of(FIRST))
    statement.validate_format()
    statement.match_db_ids()
    statement.import_into_db()

    assert JalDB._read("SELECT COUNT(*) FROM trades") == 2
    assert JalDB._read("SELECT price FROM trades WHERE number='EOF10000000001'") == '6.31627906976744'
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments") == 1
    # Five interest/cashback rows and exactly one of the six card purchases
    assert JalDB._read("SELECT COUNT(*) FROM actions") == stored_before + 6
    imported = JalDB._read("SELECT a.oid FROM actions AS a JOIN action_details AS d ON d.pid=a.oid "
                           "WHERE d.note='A book'")
    assert JalAccount(account_id).organization() == JalDB._read("SELECT peer_id FROM actions AS a "
                                                                "JOIN action_details AS d ON d.pid=a.oid "
                                                                "WHERE d.note='Interest on cash' LIMIT 1")
    assert JalDB._read("SELECT peer_id FROM actions WHERE oid=:oid", [(":oid", imported)]) == book_corner

    # A re-import adds no trade and no dividend - both carry what identifies them
    again = StatementTrading212()
    again._card_decisions_for_tests = [{'import': False, 'peer': 0, 'category': 0, 'description': ''}] * 6
    again.load(data_path_of(FIRST))
    again.match_db_ids()
    again.import_into_db()
    assert JalDB._read("SELECT COUNT(*) FROM trades") == 2
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments") == 1


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_t212_sell(prepare_db_t212):
    statement = StatementTrading212()
    statement.load(data_path_of(SECOND))
    trade = statement._data[JSF.TRADES][0]
    assert trade['quantity'] == Decimal('-1')
    assert trade['price'] == Decimal('6.4')


def test_statement_t212_multiple_load():
    ordered = StatementTrading212.order_statements([data_path_of(SECOND), data_path_of(FIRST)])
    assert [os.path.basename(x) for x in ordered] == [FIRST, SECOND]


# ----------------------------------------------------------------------------------------------------------------------
def test_statement_t212_refusals(tmp_path, prepare_db_t212):
    header = open(data_path_of(FIRST), encoding='utf-8').readline().rstrip('\n')

    def statement_of(lines) -> str:
        path = str(tmp_path / "from_2026-03-01_to_2026-03-31_x.csv")
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return path

    # An operation this module doesn't know is named and stops the import - a deposit or a withdrawal lands here,
    # and guessing how money moved is exactly what must not happen
    unknown = statement_of([header, 'Deposit,2026-03-02 10:00:00+00:00,,,,,ID1,,,,,100.00,"EUR",,,,'])
    with pytest.raises(Statement_ImportError, match="Deposit"):
        StatementTrading212().load(unknown)

    # A column Trading212 adds only when there was such an event is money that belongs to an operation
    extra = statement_of([header + ',Stamp duty',
                          'Card debit,2026-03-02 10:00:00+00:00,,,,,ID1,,,,,-10.00,"EUR",,,"SHOP","RETAIL_STORES",0.50'])
    with pytest.raises(Statement_ImportError, match="Stamp duty"):
        StatementTrading212().load(extra)

    # ... but an empty one is harmless
    empty_extra = statement_of([header + ',Stamp duty',
                                'Card debit,2026-03-02 10:00:00+00:00,,,,,ID1,,,,,-10.00,"EUR",,,"SHOP","RETAIL_STORES",'])
    StatementTrading212().load(empty_extra)

    # A second currency means an account per currency, and the file says nothing about which is which
    two_currencies = statement_of([header,
                                   'Card debit,2026-03-02 10:00:00+00:00,,,,,ID1,,,,,-10.00,"EUR",,,"SHOP","RETAIL_STORES"',
                                   'Card debit,2026-03-03 10:00:00+00:00,,,,,ID2,,,,,-10.00,"USD",,,"SHOP","RETAIL_STORES"'])
    with pytest.raises(Statement_ImportError, match="currency"):
        StatementTrading212().load(two_currencies)


def test_statement_t212_account_setting(prepare_db_t212):
    statement = load_first()
    statement._card_decisions_for_tests = [{'import': False, 'peer': 0, 'category': 0, 'description': ''}] * 6

    JalSettings().setValue(T212_ACCOUNT_SETTING, 0)
    with pytest.raises(Statement_ImportError, match="Preferences"):
        statement.match_db_ids()

    # An account in another currency is not this statement's account, whatever the setting says
    other = JalAccountCreator(currency_id=2, number='USD-ACC', name='USD account', investing=1).commit()
    JalSettings().setValue(T212_ACCOUNT_SETTING, other.id())
    with pytest.raises(Statement_ImportError, match="currency"):
        statement.match_db_ids()


# ----------------------------------------------------------------------------------------------------------------------
def test_t212_card_dialog(prepare_db_t212):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget, QDialogButtonBox
    from jal.widgets.card_import_dialog import CardImportDialog, CardOperationsModel

    account_id = prepare_db_t212
    store_card_operation(account_id, dt2t(2603041216), '-18.40', 'Green grocer')
    rows = [{'id': 1, 'timestamp': dt2t(2603041215) + 30, 'amount': Decimal('-18.40'),
             'merchant': 'GREEN GROCER', 'merchant_category': 'RETAIL_STORES'},
            {'id': 2, 'timestamp': dt2t(2603181620), 'amount': Decimal('-12.99'),
             'merchant': 'BOOK CORNER', 'merchant_category': 'MISCELLANEOUS'}]
    stored = CardMatcher.stored_operations(account_id, dt2t(2603010000), dt2t(2603312359))
    proposal = CardMatcher.propose(rows, stored)

    parent = QWidget()   # a dialog built without a parent aborts the process from the cyclic collector
    dialog = CardImportDialog(rows, proposal, parent)
    model = dialog._model
    ok = dialog._buttons.button(QDialogButtonBox.Ok)

    # What is in the database is proposed as 'don't import'; what isn't, as 'do' - and that one needs a peer
    assert model.data(model.index(0, CardOperationsModel.IMPORT), Qt.CheckStateRole) == Qt.Unchecked
    assert model.data(model.index(1, CardOperationsModel.IMPORT), Qt.CheckStateRole) == Qt.Checked
    assert model.data(model.index(0, CardOperationsModel.STORED)) != ''
    assert model.data(model.index(1, CardOperationsModel.STORED)) == ''
    assert not ok.isEnabled()

    peer = JalPeer(data={'name': 'Book corner'}, create=True).id()
    model.setData(model.index(1, CardOperationsModel.PEER), peer)
    assert not ok.isEnabled()      # a category is as mandatory as a peer
    model.setData(model.index(1, CardOperationsModel.CATEGORY), PredefinedCategory.Spending)
    assert ok.isEnabled()

    decisions = dialog.decisions()
    assert [x['import'] for x in decisions] == [False, True]
    assert decisions[1] == {'import': True, 'peer': peer, 'category': PredefinedCategory.Spending,
                            'description': 'BOOK CORNER'}

    # Ticking a matched purchase brings it back into the import, and it then needs a peer of its own
    model.setData(model.index(0, CardOperationsModel.IMPORT), Qt.Checked, Qt.CheckStateRole)
    assert not ok.isEnabled()

    # A column the user types into is wide enough to type into while it is still empty
    header = dialog._view.horizontalHeader()
    assert header.sectionSize(CardOperationsModel.PEER) >= header.sectionSize(CardOperationsModel.AMOUNT)
    assert header.sectionSize(CardOperationsModel.CATEGORY) >= header.sectionSize(CardOperationsModel.AMOUNT)

    # Closing stores the geometry and the column layout, and a dialog opened afterwards puts them back
    dialog.resize(900, 400)
    header.resizeSection(CardOperationsModel.MERCHANT, 275)
    dialog.close()
    assert JalSettings().getStr(CardImportDialog.GEOMETRY_KEY) != ''
    reopened = CardImportDialog(rows, proposal, parent)
    assert reopened._view.horizontalHeader().sectionSize(CardOperationsModel.MERCHANT) == 275
    reopened.close()
    parent.close()


# ----------------------------------------------------------------------------------------------------------------------
def test_t212_account_is_set_in_preferences(prepare_db_t212):
    from PySide6.QtWidgets import QWidget
    from jal.db.settings_registry import SettingsRegistry
    from jal.widgets.preferences_dialog import PreferencesDialog

    # The module registers the setting itself, so importing it is what puts the page into the dialog
    assert 'Import' in SettingsRegistry.pages()
    assert T212_ACCOUNT_SETTING in [x.key for x in SettingsRegistry.settings_of_page('Import')]

    parent = QWidget()
    dialog = PreferencesDialog(parent)
    editor = dialog._editors[T212_ACCOUNT_SETTING]
    assert editor.selected_id == prepare_db_t212      # an account selector, showing what is stored

    other = JalAccountCreator(currency_id=EUR, number='OTHER', name='Another account', investing=1).commit()
    editor.selected_id = other.id()
    dialog.accept()
    assert JalSettings().getInt(T212_ACCOUNT_SETTING) == other.id()
    parent.close()
