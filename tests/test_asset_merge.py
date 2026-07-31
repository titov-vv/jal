import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_quotes
from constants import PredefinedAsset, PredefinedAccountType, AssetData, AssetLocation, SymbolId
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction, Transfer
from jal.db.symbol import JalSymbol

# ----------------------------------------------------------------------------------------------------------------------
# One coin recorded as two assets.
#
# A token's identity is its contract address and its ticker is only a label, so a coin RENAMED on one chain (Tether's
# 'USDT' is called 'USD₮0' on Arbitrum) shares no ticker with the asset JAL already holds. The cross-chain prompt is
# offered on a ticker collision, so it never fires, and the fetch stages a second asset for a coin the user already
# has. Nothing adds the two together afterwards: a transfer moves ONE asset and refuses to settle across them, and
# every holdings and tax figure counts them apart.
#
# Merging them is possible at all because every operation references a LISTING rather than an asset - so the history
# travels with the listings and nothing that records an operation is rewritten.

USD, EUR = 2, 3
ETH_USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
ARB_USDT = "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9"


@pytest.fixture
def two_records_of_one_coin(prepare_db):
    known = JalAssetCreator(PredefinedAsset.Crypto, 'Tether USD')
    eth = known.add_symbol('USDT', USD, location_id=AssetLocation.ETH_BLOCKCHAIN)
    known.add_identifier(eth, SymbolId.ETH_ADDRESS, ETH_USDT)
    known = known.commit()
    renamed = JalAssetCreator(PredefinedAsset.Crypto, 'USD₮0')
    arb = renamed.add_symbol('USD₮0', USD, location_id=AssetLocation.ARB_BLOCKCHAIN)
    renamed.add_identifier(arb, SymbolId.ARB_ADDRESS, ARB_USDT)
    renamed = renamed.commit()
    yield known, renamed


def _listings_of(asset_id: int) -> list:
    return JalDB._read_to_list("SELECT id, symbol FROM asset_symbol WHERE asset_id=:id ORDER BY id",
                               [(":id", asset_id)], named=True)


def _asset_exists(asset_id: int) -> bool:
    return JalDB._read("SELECT COUNT(*) FROM assets WHERE id=:id", [(":id", asset_id)]) == 1


# ----------------------------------------------------------------------------------------------------------------------
# What the merge moves

def test_the_listings_of_the_merged_asset_become_the_survivors(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin
    arb_listing = JalAsset(renamed.id()).active_symbol_ids()[0]

    assert JalAsset(renamed.id()).replace_with(known.id()) == ''

    assert JalSymbol(arb_listing).asset().id() == known.id()
    assert sorted(x['symbol'] for x in _listings_of(known.id())) == sorted(['USDT', 'USD₮0'])
    assert not _asset_exists(renamed.id())


# The listing keeps its own identity - its ticker, its chain and above all the contract address that IS the token.
# Merging says the two assets are one coin; it says nothing about the listings being one listing.
def test_a_merged_listing_keeps_its_address_and_its_chain(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin
    arb_listing = JalAsset(renamed.id()).active_symbol_ids()[0]

    JalAsset(renamed.id()).replace_with(known.id())

    listing = JalSymbol(arb_listing)
    assert listing.symbol() == 'USD₮0'
    assert listing.location() == AssetLocation.ARB_BLOCKCHAIN
    assert listing.identifier(SymbolId.ARB_ADDRESS) == ARB_USDT
    # ... and the coin is now findable by either chain's address, which is what stops the next fetch from staging it
    # as a third record of the same thing
    assert JalSymbol.find_by_identifier(SymbolId.ARB_ADDRESS, ARB_USDT).asset().id() == known.id()
    assert JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, ETH_USDT).asset().id() == known.id()


# Every operation names a listing, so the history travels with the listings and no operation is rewritten - which is
# the whole reason this merge is safe to do on a database that already holds transfers, trades and swaps.
def test_the_operations_of_the_merged_asset_are_not_touched(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin
    arb_listing = JalAsset(renamed.id()).active_symbol_ids()[0]
    JalAccountCreator(currency_id=USD, number='', name='ARB wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    LedgerTransaction.create_new(LedgerTransaction.Transfer, {
        'withdrawal_timestamp': d2t(210103), 'withdrawal_account': None, 'withdrawal': '400',
        'deposit_timestamp': d2t(210103), 'deposit_account': 1, 'deposit': '0',
        'number': '0xabc', 'counterparty_address': None, 'symbol_id': arb_listing})

    JalAsset(renamed.id()).replace_with(known.id())

    leg = Transfer.pending_legs()[0]
    assert leg['symbol'].id() == arb_listing        # the operation still names the very listing it named
    assert leg['asset'].id() == known.id()          # ... which belongs to the surviving asset now


# ----------------------------------------------------------------------------------------------------------------------
# What it adopts and what it keeps

# The merged asset may be the one whose price was downloaded, so what the survivor is missing crosses over with it
def test_quotes_the_survivor_lacks_are_adopted(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin
    create_quotes(renamed.id(), USD, [(d2t(210101), 1.05)])

    JalAsset(renamed.id()).replace_with(known.id())

    assert JalAsset(known.id()).quote(d2t(210102), USD)[1] == Decimal('1.05')


# ... while a quote the survivor already states is its own: a merge joins two records of one coin, it doesn't decide
# which of two prices for one day was right
def test_a_quote_the_survivor_already_states_is_kept(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin
    create_quotes(known.id(), USD, [(d2t(210101), 1.0)])
    create_quotes(renamed.id(), USD, [(d2t(210101), 2.0)])

    JalAsset(renamed.id()).replace_with(known.id())

    assert JalAsset(known.id()).quote(d2t(210102), USD)[1] == Decimal('1.0')


def test_extra_data_the_survivor_lacks_is_adopted(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin
    JalSymbol(JalAsset(renamed.id()).active_symbol_ids()[0]).update_data({'coin_id': 'tether'})

    JalAsset(renamed.id()).replace_with(known.id())

    assert JalDB._read("SELECT value FROM asset_data WHERE asset_id=:id AND datatype=:type",
                       [(":id", known.id()), (":type", AssetData.CoinGeckoId)]) == 'tether'


def test_extra_data_the_survivor_already_states_is_kept(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin
    JalSymbol(JalAsset(known.id()).active_symbol_ids()[0]).update_data({'coin_id': 'tether'})
    JalSymbol(JalAsset(renamed.id()).active_symbol_ids()[0]).update_data({'coin_id': 'usdt0'})

    JalAsset(renamed.id()).replace_with(known.id())

    assert JalDB._read("SELECT value FROM asset_data WHERE asset_id=:id AND datatype=:type",
                       [(":id", known.id()), (":type", AssetData.CoinGeckoId)]) == 'tether'
    # ... and the value that didn't cross over went with the asset it belonged to, rather than being left behind
    assert JalDB._read("SELECT COUNT(*) FROM asset_data WHERE asset_id=:id", [(":id", renamed.id())]) == 0


# ----------------------------------------------------------------------------------------------------------------------
# What it refuses

# A currency is what accounts, quotes and the base currency are KEPT IN rather than something operations hold, so
# folding one into another rewrites what every balance is denominated in - not this operation, and not one to reach
# by way of a token that happens to share its ticker.
def test_a_currency_is_never_merged(prepare_db):
    assert JalAsset(EUR).replace_with(USD) != ''
    assert _asset_exists(EUR)


def test_an_asset_is_not_merged_into_a_currency(two_records_of_one_coin):
    _known, renamed = two_records_of_one_coin
    assert JalAsset(renamed.id()).replace_with(USD) != ''
    assert _asset_exists(renamed.id())


# Two assets of different types are not two records of one thing, whatever they are called
def test_assets_of_different_types_are_not_merged(two_records_of_one_coin):
    known, _renamed = two_records_of_one_coin
    stock = JalAssetCreator(PredefinedAsset.Stock, 'Not a coin')
    stock.add_symbol('USDT', USD, location_id=AssetLocation.UNDEFINED)
    stock = stock.commit()

    assert JalAsset(stock.id()).replace_with(known.id()) != ''
    assert _asset_exists(stock.id())


def test_an_asset_is_not_merged_into_itself(two_records_of_one_coin):
    known, _renamed = two_records_of_one_coin
    assert JalAsset(known.id()).replace_with(known.id()) != ''
    assert _asset_exists(known.id())


def test_an_asset_that_does_not_exist_is_refused(two_records_of_one_coin):
    _known, renamed = two_records_of_one_coin
    assert JalAsset(renamed.id()).replace_with(0) != ''
    assert JalAsset(renamed.id()).replace_with(999999) != ''
    assert _asset_exists(renamed.id())


# The refusal can be asked for without writing anything, so a chooser says what a merge would do instead of letting
# the user find out by trying it
def test_the_refusal_is_the_same_answer_asked_beforehand(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin

    assert JalAsset(renamed.id()).refusal_to_replace(known.id()) == ''
    assert JalAsset(renamed.id()).refusal_to_replace(USD) != ''
    assert _asset_exists(renamed.id())   # asking wrote nothing


# ----------------------------------------------------------------------------------------------------------------------
# What it discards

# The ledger cannot survive a merge. Deleting the merged asset cascades away its ledger rows, and a ledger missing
# them while its frontier still claims today is worse than no ledger at all - every later balance of that asset is
# short of what it had, and nothing says so. So it is dropped whole and the caller rebuilds.
def test_the_ledger_is_dropped_so_that_it_is_rebuilt(two_records_of_one_coin):
    known, renamed = two_records_of_one_coin
    account = JalAccountCreator(currency_id=USD, number='', name='ARB wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                                chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalDB._exec("INSERT INTO ledger (timestamp, otype, oid, opart, book_account, asset_id, account_id, amount) "
                "VALUES (:ts, 1, 1, 0, 4, :asset, :account, '1')",
                [(":ts", d2t(210103)), (":asset", known.id()), (":account", account.id())], commit=True)
    assert JalDB._read("SELECT COUNT(*) FROM ledger") == 1

    JalAsset(renamed.id()).replace_with(known.id())

    assert JalDB._read("SELECT COUNT(*) FROM ledger") == 0
    # ... and the frontier is MAX(ledger.timestamp), so an empty ledger is what makes the next rebuild a full one
    assert not JalDB._read("SELECT ledger_frontier FROM frontier")


# ----------------------------------------------------------------------------------------------------------------------
# Invoking it. The action is offered on a LISTING because that is what the assets dialog lists, and it is the listing
# that shows the problem: two rows the user knows are one coin, which nothing in the data can tell apart.

def _merge_dialog(monkeypatch, chosen_symbol_id: int, confirm=True):
    from jal.widgets.assets_dialogs import SymbolListDialog
    dialog = SymbolListDialog()

    def pick(self, enable_selection=False, selected=0):
        self.selected_id = chosen_symbol_id
        return QDialog.Accepted
    monkeypatch.setattr(SymbolListDialog, 'exec', pick)
    monkeypatch.setattr(QMessageBox, 'warning',
                        lambda *args, **kwargs: QMessageBox.Yes if confirm else QMessageBox.No)
    monkeypatch.setattr('jal.widgets.assets_dialogs.Ledger.rebuild', lambda *args, **kwargs: None)
    return dialog


def _select_listing(dialog, symbol_id: int) -> None:
    dialog.setFilter()
    row = next(i for i in range(dialog.model.rowCount()) if dialog.model.record(i).value('id') == symbol_id)
    dialog.ui.DataView.setCurrentIndex(dialog.model.index(row, dialog.model.fieldIndex("symbol")))


def test_the_dialog_merges_the_asset_of_the_chosen_listing(two_records_of_one_coin, monkeypatch):
    known, renamed = two_records_of_one_coin
    survivor_listing = JalAsset(known.id()).active_symbol_ids()[0]
    merged_listing = JalAsset(renamed.id()).active_symbol_ids()[0]
    dialog = _merge_dialog(monkeypatch, chosen_symbol_id=survivor_listing)
    _select_listing(dialog, merged_listing)

    dialog.onMergeAsset()

    assert JalSymbol(merged_listing).asset().id() == known.id()
    assert not _asset_exists(renamed.id())


# The confirmation is a real question - the ledger is dropped by a merge, and declining has to leave everything alone
def test_declining_the_confirmation_merges_nothing(two_records_of_one_coin, monkeypatch):
    known, renamed = two_records_of_one_coin
    survivor_listing = JalAsset(known.id()).active_symbol_ids()[0]
    merged_listing = JalAsset(renamed.id()).active_symbol_ids()[0]
    dialog = _merge_dialog(monkeypatch, chosen_symbol_id=survivor_listing, confirm=False)
    _select_listing(dialog, merged_listing)

    dialog.onMergeAsset()

    assert JalSymbol(merged_listing).asset().id() == renamed.id()
    assert _asset_exists(renamed.id())


# A pair that cannot be merged is refused before the question is even asked - the user is told why rather than being
# asked to confirm something that would then fail
def test_a_refused_pair_is_reported_and_nothing_is_written(two_records_of_one_coin, monkeypatch):
    _known, renamed = two_records_of_one_coin
    merged_listing = JalAsset(renamed.id()).active_symbol_ids()[0]
    currency_listing = JalAsset(USD).active_symbol_ids()[0]
    dialog = _merge_dialog(monkeypatch, chosen_symbol_id=currency_listing)
    _select_listing(dialog, merged_listing)

    dialog.onMergeAsset()

    assert _asset_exists(renamed.id())
    assert JalSymbol(merged_listing).asset().id() == renamed.id()
