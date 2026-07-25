from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets
from constants import PredefinedAsset, PredefinedAccountType, AssetLocation
from jal.data_import.statement import Statement, JSF
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset

# ----------------------------------------------------------------------------------------------------------------------
# The question a statement asks when one end of a transfer is an account JAL doesn't know ("select account to deposit
# to / withdraw from") is the only place the user decides what an unmatched movement was, so what it says has to be
# exact and complete - see Statement._import_transfers.

USDC = 4                       # the asset created by the fixture below
STATEMENT_ASSET, STATEMENT_SYMBOL = 10, 100     # ids inside the statement, mapped to the db ones


@pytest.fixture
def wallet(prepare_db):
    JalAccountCreator(currency_id=2, number='', name='ARB wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    create_assets([('USDC', 'USD Coin', '', 2, PredefinedAsset.Crypto, 0)])   # ID = USDC
    yield


# A statement holding one asset transfer of 'symbol_id', from the account given (0 = unknown, which is what makes the
# import ask). Returns the statement and the list of questions its account selection was asked.
def _statement_with_transfer(monkeypatch, symbol_id: int, accounts: list, description: str,
                             amount: Decimal = Decimal('1000')):
    statement = Statement()
    statement._data[JSF.ASSETS] = [
        {"id": STATEMENT_ASSET, "type": JSF.ASSET_CRYPTO, "name": "USD Coin",
         JSF.SYMBOLS: [{"id": STATEMENT_SYMBOL, "symbol": "USDC.e", "currency": 1,
                        "location": AssetLocation.ARB_BLOCKCHAIN}]}]
    statement.set_mapped_id(JSF.ACCOUNTS, 1, 1)
    statement.set_mapped_id(JSF.ASSETS, STATEMENT_ASSET, USDC)
    statement.set_mapped_id(JSF.SYMBOLS, STATEMENT_SYMBOL, symbol_id)
    asked = []

    def fake_select(self, text, account_id, recent_account_id=0):
        asked.append(text)
        return 1
    monkeypatch.setattr(Statement, "select_account", fake_select)
    statement._import_transfers([
        {"id": 1, "account": accounts, "symbol": [STATEMENT_SYMBOL, STATEMENT_SYMBOL], "timestamp": d2t(210103),
         "withdrawal": amount, "deposit": Decimal('0'), "fee": Decimal('0'),
         "number": "0xhash", "description": description}])
    return asked


# One asset may be listed under several symbols at once - the very same token on several chains is the everyday case
# for crypto - and the transfer moves exactly one of those listings. The question must therefore name that listing
# and not the asset, whose symbol() with no currency concatenates every active symbol it has.
def test_prompt_names_the_listing_that_moves_not_every_symbol_of_the_asset(wallet, monkeypatch):
    arb_symbol = JalAsset(USDC).add_symbol('USDC.e', 2, AssetLocation.ARB_BLOCKCHAIN)
    assert JalAsset(USDC).symbol() == 'USDC,USDC.e'          # the asset really does hold two active listings
    asked = _statement_with_transfer(monkeypatch, arb_symbol, [1, 0, 1], '')

    assert len(asked) == 1
    assert 'USDC.e' in asked[0]
    assert 'USDC,USDC.e' not in asked[0]                    # ... but the question is about the one that moved


# A transfer fetched from a blockchain may be all that could be recorded of a larger operation, and its description
# carries the mark that says so (see TransferMark). That is what the account to pick depends on, so the question shows
# it - for a broker statement it shows whatever note the statement brought instead.
@pytest.mark.parametrize("accounts", [[1, 0, 1], [0, 1, 1]])
def test_prompt_shows_the_description_of_the_transfer(wallet, monkeypatch, accounts):
    note = "[custody] stake.link PriorityPool: held for the wallet"
    asked = _statement_with_transfer(monkeypatch, JalAsset(USDC).add_symbol('USDC.e', 2,
                                                                           AssetLocation.ARB_BLOCKCHAIN),
                                     accounts, note)

    assert len(asked) == 1
    assert note in asked[0]
    # The description sits between the movement and the request, so the question still ends with what to answer
    assert asked[0].splitlines()[1] == note
    assert asked[0].splitlines()[-1].endswith(':')


# A crypto quantity is what an unmatched blockchain transfer usually moves, and two decimals turn most of them into
# '0.00' - a question about nothing. The amount keeps the digits it has (see localize_amount).
@pytest.mark.parametrize("amount, digits", [(Decimal('0.00043'), '43'),                  # would have been '0.00'
                                            (Decimal('0.15468900016691433'), '15468900'),   # ... and not 18 digits
                                            (Decimal('1000'), '1')])
def test_prompt_keeps_the_digits_of_a_crypto_quantity(wallet, monkeypatch, amount, digits):
    asked = _statement_with_transfer(monkeypatch,
                                     JalAsset(USDC).add_symbol('USDC.e', 2, AssetLocation.ARB_BLOCKCHAIN),
                                     [1, 0, 1], '', amount=amount)

    assert len(asked) == 1
    quantity = asked[0].split()[2]                    # "Withdrawal of <quantity> USDC.e from ..."
    assert digits in quantity
    assert quantity.rstrip('0.,\xa0 ') != ''          # ... and it never asks about a bare zero


def test_prompt_omits_an_empty_description(wallet, monkeypatch):
    asked = _statement_with_transfer(monkeypatch, JalAsset(USDC).add_symbol('USDC.e', 2,
                                                                           AssetLocation.ARB_BLOCKCHAIN),
                                     [1, 0, 1], '')

    assert len(asked) == 1
    assert len(asked[0].splitlines()) == 2                  # the movement and the request, with no empty line between
