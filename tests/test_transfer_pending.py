from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, symbol_id_for
from constants import BookAccount, PredefinedAsset, PredefinedCategory, PredefinedAccountType, AssetLocation
from jal.data_import.statement import Statement, Statement_ImportError, JSF
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger, LedgerAmounts
from jal.db.operations import LedgerTransaction, Transfer

# ----------------------------------------------------------------------------------------------------------------------
# A transfer may be known by ONE LEG ONLY - "money on the way". The end a statement doesn't name is stored as NULL
# instead of being asked about at import time, which is the moment of least information, and stays visibly unsettled
# until its counterpart is met. These tests cover what that costs the ledger: the value of an unsettled leg lives in
# the Transfers book, and a settled pair cancels there exactly.

USDT = 4                       # the asset created by the fixtures below
WALLET_A, WALLET_B = 1, 2


@pytest.fixture
def wallets(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='ARB wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=2, number='', name='ETH wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '2' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_assets([('USDT', 'Tether USD', '', 2, PredefinedAsset.Crypto, 0)])   # ID = USDT
    yield


def _transfer(from_account, to_account, amount, timestamp, asset_id=USDT, deposit=0, number=''):
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
            'deposit_timestamp': timestamp, 'deposit_account': to_account, 'deposit': str(deposit),
            'number': number, 'symbol_id': symbol_id_for(asset_id) if asset_id else None}
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


def _in_transit(asset_id) -> Decimal:
    # "How much is in transit" is a question about ALL accounts at once, so it sums raw 'amount' over the Transfers
    # book: 'amount_acc' accumulates per (book, account, asset) and can't be totalled. Positive = sent but not
    # arrived, negative = arrived from a source that is still unknown.
    total = Ledger._read("SELECT SUM(amount) FROM ledger WHERE book_account=:book AND asset_id=:asset",
                         [(":book", BookAccount.Transfers), (":asset", asset_id)])
    return Decimal(total) if total else Decimal('0')


# ----------------------------------------------------------------------------------------------------------------------
# The import side: an unknown end is recorded, not asked about

STATEMENT_ASSET, STATEMENT_SYMBOL = 10, 100     # ids inside the statement, mapped to the db ones


def _import(monkeypatch, accounts: list, number: str = '0xhash', amount: Decimal = Decimal('1000')):
    statement = Statement()
    monkeypatch.setattr(type(statement), "_transfers_are_unique_per_transaction", True)
    statement.set_mapped_id(JSF.ACCOUNTS, 1, WALLET_A)
    statement.set_mapped_id(JSF.ACCOUNTS, 2, WALLET_B)
    statement.set_mapped_id(JSF.ASSETS, STATEMENT_ASSET, USDT)
    statement.set_mapped_id(JSF.SYMBOLS, STATEMENT_SYMBOL, symbol_id_for(USDT))
    statement._data[JSF.ASSETS] = [
        {"id": STATEMENT_ASSET, "type": JSF.ASSET_CRYPTO, "name": "Tether USD",
         JSF.SYMBOLS: [{"id": STATEMENT_SYMBOL, "symbol": "USDT", "currency": 1,
                        "location": AssetLocation.ARB_BLOCKCHAIN}]}]
    statement._import_transfers([
        {"id": 1, "account": accounts, "symbol": [STATEMENT_SYMBOL, STATEMENT_SYMBOL], "timestamp": d2t(210103),
         "withdrawal": amount, "deposit": Decimal('0'), "fee": Decimal('0'), "number": number}])


def _stored() -> list:
    query = LedgerTransaction._exec("SELECT oid, withdrawal_account, deposit_account FROM transfers ORDER BY oid")
    rows = []
    while query.next():
        rows.append(LedgerTransaction._read_record(query, named=True))
    return rows


# The counterparty an import can't resolve used to stop it with a modal question whose answer was unverifiable
# afterwards. It is stored as an absent leg instead - the import runs through, and nothing is guessed.
@pytest.mark.parametrize("accounts, known_side", [([1, 0, 1], 'withdrawal_account'), ([0, 1, 1], 'deposit_account')])
def test_unknown_counterparty_is_stored_as_a_pending_leg(wallets, monkeypatch, accounts, known_side):
    _import(monkeypatch, accounts)

    rows = _stored()
    assert len(rows) == 1
    unknown_side = 'deposit_account' if known_side == 'withdrawal_account' else 'withdrawal_account'
    assert int(rows[0][known_side]) == WALLET_A
    assert rows[0][unknown_side] == ''                    # SQL NULL - the end that isn't known
    assert Transfer(int(rows[0]['oid']), Transfer.Outgoing).is_pending()


# A movement with neither end known describes nothing at all and is refused rather than stored as a row that can
# never be settled
def test_transfer_with_both_ends_unknown_is_refused(wallets, monkeypatch):
    with pytest.raises(Statement_ImportError):
        _import(monkeypatch, [0, 0, 1])
    assert _stored() == []


# Re-importing a history that was fetched before must not double the transfers it holds. Deduplication keys on the
# accounts as well, so an absent end has to match an absent end - which is what a repeated fetch of the same wallet
# produces.
def test_reimport_of_a_pending_leg_is_not_duplicated(wallets, monkeypatch):
    _import(monkeypatch, [1, 0, 1])
    _import(monkeypatch, [1, 0, 1])

    assert len(_stored()) == 1


# ... but the SAME movement seen from the other wallet is a different record: it brings the account the first one
# didn't know. Dropping it here would lose that account for good, so both are stored and pairing them into one
# settled transfer is left to settlement.
def test_the_other_side_of_the_same_movement_is_kept(wallets, monkeypatch):
    _import(monkeypatch, [1, 0, 1])
    _import(monkeypatch, [0, 2, 2])

    rows = _stored()
    assert len(rows) == 2
    assert (int(rows[0]['withdrawal_account']), rows[0]['deposit_account']) == (WALLET_A, '')
    assert (rows[1]['withdrawal_account'], int(rows[1]['deposit_account'])) == ('', WALLET_B)


# ----------------------------------------------------------------------------------------------------------------------
# The ledger side: an unsettled leg is value in transit

@pytest.fixture
def funded(wallets):
    create_actions([(d2t(210101), WALLET_A, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_trades(WALLET_A, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])   # 1000 USDT at basis 1000
    yield


# An asset sent to an unknown destination leaves the source at its cost basis and waits in the Transfers book. The
# position is closed here and re-opened only when the arrival is known - which is exactly what "in transit" means.
def test_pending_outgoing_asset_transfer_parks_value_in_transit(funded):
    _transfer(WALLET_A, None, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(WALLET_A).get_asset_amount(d2t(210201), USDT) == Decimal('600')
    assert JalAccount(WALLET_B).get_asset_amount(d2t(210201), USDT) == Decimal('0')
    assert _in_transit(USDT) == Decimal('400')     # positive: sent, not arrived
    values = LedgerAmounts("value_acc")
    assert values[(BookAccount.Transfers, WALLET_A, USDT)] == Decimal('400')   # ... at the basis it left with


# An asset that arrived from a source that hasn't been imported yet has no sending leg to take a cost basis from,
# and no closed deal whose lots could be carried over. It opens a position of its own at ZERO basis instead of
# aborting the ledger rebuild on "Asset withdrawal not found" - the basis is filled in when the transfer is settled.
def test_pending_incoming_asset_transfer_opens_a_zero_basis_lot(wallets):
    _transfer(None, WALLET_B, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)            # must not raise

    assert JalAccount(WALLET_B).get_asset_amount(d2t(210201), USDT) == Decimal('400')
    lots = JalAccount(WALLET_B).open_trades_list(JalAsset(USDT))
    assert len(lots) == 1
    assert lots[0].open_qty(adjusted=True) == Decimal('400')
    assert lots[0].open_price(adjusted=True) == Decimal('0')
    assert _in_transit(USDT) == Decimal('-400')   # negative: arrived from an unknown source


# The invariant that makes the Transfers book readable at all: it is a contra-entry locus, not a pot. Its per-asset
# total over ALL accounts is the value in transit, so with every leg settled it must be exactly zero.
def test_settled_transfer_leaves_nothing_in_transit(funded):
    _transfer(WALLET_A, WALLET_B, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(WALLET_A).get_asset_amount(d2t(210201), USDT) == Decimal('600')
    assert JalAccount(WALLET_B).get_asset_amount(d2t(210201), USDT) == Decimal('400')
    assert _in_transit(USDT) == Decimal('0')
    # The cost basis travelled with the asset - the arriving lot is the one that left
    lots = JalAccount(WALLET_B).open_trades_list(JalAsset(USDT))
    assert len(lots) == 1 and lots[0].open_price(adjusted=True) == Decimal('1')


# The same holds for money, which needs no lots: an unsettled leg is money that left one account and reached none.
def test_pending_money_transfer_is_money_in_transit(wallets):
    create_actions([(d2t(210101), WALLET_A, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    usd = JalAccount(WALLET_A).currency()
    _transfer(WALLET_A, None, 1500, d2t(210103), asset_id=None, deposit=1500)
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(WALLET_A).get_asset_amount(d2t(210201), usd) == Decimal('8500')
    assert _in_transit(usd) == Decimal('1500')

    _transfer(None, WALLET_B, 1500, d2t(210104), asset_id=None, deposit=1500)
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(WALLET_B).get_asset_amount(d2t(210201), usd) == Decimal('1500')
    assert _in_transit(usd) == Decimal('0')       # two opposite pending legs cancel just as one settled pair does


# A pending leg contributes exactly one part to the ledger: 'operation_sequence' leaves out the side whose account
# is NULL, so nothing tries to process a leg that doesn't exist.
@pytest.mark.parametrize("accounts, parts", [((WALLET_A, None), [-1]), ((None, WALLET_B), [1]),
                                             ((WALLET_A, WALLET_B), [-1, 1])])
def test_only_existing_legs_are_sequenced(funded, accounts, parts):
    oid = _transfer(accounts[0], accounts[1], 400, d2t(210103)).oid()

    query = LedgerTransaction._exec("SELECT opart FROM operation_sequence WHERE otype=:otype AND oid=:oid "
                                    "ORDER BY opart", [(":otype", LedgerTransaction.Transfer), (":oid", oid)])
    sequenced = []
    while query.next():
        sequenced.append(int(LedgerTransaction._read_record(query)))
    assert sequenced == parts
