from decimal import Decimal

import pytest
from PySide6.QtWidgets import QWidget, QMessageBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t
from jal.constants import Setup, PredefinedAsset, AssetLocation, SymbolId, IconOwner, IconSource
from jal.db.db import JalDB, JalDBError
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol
from jal.db.icon import JalIcons
from jal.db.account import JalAccountCreator
from jal.db.operations import LedgerTransaction
from jal.widgets.symbol_dialog import SymbolDialog
from jal.data_import.statement import Statement, JSF

RUB, USD, EUR = 1, 2, 3
ADDRESS = "0xdac17f958d2ee523a2206206994597c13d831ec7"


def _listing(asset_id, ticker, currency, location, active=1) -> int:   # written as SQL, the way an older JAL left it
    JalDB._exec("INSERT INTO asset_symbol (asset_id, symbol, currency_id, location_id, active) "
                "VALUES (:asset, :ticker, :currency, :location, :active)",
                [(":asset", asset_id), (":ticker", ticker), (":currency", currency), (":location", location),
                 (":active", active)], commit=True)
    return JalDB._read("SELECT MAX(id) FROM asset_symbol")


# ----------------------------------------------------------------------------------------------------------------------
# Delta 82, replayed from the shipped files on a database taken back to version 81: listings of one crypto asset that
# differed by currency only become one listing in the venue's currency, keeping everything that named any of them
def test_delta_82_puts_crypto_listings_into_their_venue_currency(prepare_db_fifo, project_root):
    JalDB._exec("DROP INDEX uniq_symbols", commit=True)
    JalDB._exec("DROP INDEX uniq_symbol_ids", commit=True)
    JalDB._exec("CREATE UNIQUE INDEX uniq_symbols ON asset_symbol (asset_id, symbol COLLATE NOCASE, currency_id, "
                "location_id)", commit=True)
    JalDB._exec("UPDATE settings SET value=81 WHERE name='SchemaVersion'", commit=True)
    usdt = JalAssetCreator(PredefinedAsset.Crypto, 'Tether USD').commit().id()
    rub = _listing(usdt, 'USDT', RUB, AssetLocation.ETH_BLOCKCHAIN)
    usd = _listing(usdt, 'USDT', USD, AssetLocation.ETH_BLOCKCHAIN)
    eur = _listing(usdt, 'usdt', EUR, AssetLocation.ETH_BLOCKCHAIN, active=0)
    JalDB._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:id, :type, :address)",
                [(":id", usd), (":type", SymbolId.ETH_ADDRESS), (":address", ADDRESS)], commit=True)
    JalIcons.store(IconOwner.Symbol, rub, b'rub', IconSource.Downloaded)
    JalIcons.store(IconOwner.Symbol, usd, b'usd', IconSource.Downloaded)
    trx = JalAssetCreator(PredefinedAsset.Crypto, 'Tron').commit().id()
    trx_rub = _listing(trx, 'TRX', RUB, AssetLocation.TRX_BLOCKCHAIN)
    stock = JalAssetCreator(PredefinedAsset.Stock, 'Some Company').commit().id()
    stock_rub = _listing(stock, 'SC', RUB, AssetLocation.MOEX_EXCHANGE)
    LedgerTransaction.create_new(LedgerTransaction.Trade, {
        'timestamp': d2t(240101), 'settlement': d2t(240101), 'account_id': 1, 'symbol_id': rub, 'qty': 10,
        'price': 1, 'fee': 0, 'number': ''})

    assert JalDB().run_sql_script(project_root + f"/jal/updates/{Setup.UPDATE_PREFIX}82.sql").code == JalDBError.NoError
    assert JalDB()._run_update_script().code == JalDBError.NoError
    JalDB().invalidate_cache()

    assert JalDB._read("SELECT value FROM settings WHERE name='SchemaVersion'") == '82'
    rows = JalDB._read_to_list("SELECT id, symbol, currency_id, active FROM asset_symbol WHERE asset_id=:a",
                               [(":a", usdt)])
    assert [tuple(x) for x in rows] == [(usd, 'USDT', USD, 1)]                  # the USD row is kept, live
    assert JalSymbol(usd).identifier(SymbolId.ETH_ADDRESS) == ADDRESS
    assert JalDB._read("SELECT symbol_id FROM trades") == usd                   # the trade follows its listing
    assert JalDB._read_to_list("SELECT item_id FROM icons WHERE entity=:e", [(":e", IconOwner.Symbol)]) == [usd]
    assert JalSymbol(trx_rub).currency() == USD                                 # a lone listing changes currency only
    assert JalSymbol(stock_rub).currency() == RUB                               # a security keeps its currency
    assert JalDB._read("SELECT value FROM settings WHERE name='RebuildDB'") == '1'


# ----------------------------------------------------------------------------------------------------------------------
# Only live listings are unique: a superseded one may repeat a live one's ticker, currency and venue, a second live
# one may not (ticker compared without case)
def test_only_live_listings_have_to_be_unique(prepare_db):
    asset = JalAssetCreator(PredefinedAsset.Stock, 'Reverse Split Corp').commit().id()
    _listing(asset, 'RSC', USD, AssetLocation.NYSE_EXCHANGE, active=0)
    _listing(asset, 'RSC', USD, AssetLocation.NYSE_EXCHANGE, active=1)
    assert JalDB._read("SELECT COUNT(*) FROM asset_symbol WHERE asset_id=:a", [(":a", asset)]) == 2
    assert JalDB._exec("INSERT INTO asset_symbol (asset_id, symbol, currency_id, location_id, active) "
                       "VALUES (:a, 'rsc', 2, :l, 1)", [(":a", asset), (":l", AssetLocation.NYSE_EXCHANGE)]) is None


# add_symbol() finds the live listing among superseded twins, keeps a crypto listing in its venue's currency and
# refuses a currency that isn't money
def test_add_symbol_rules(prepare_db):
    asset = JalAssetCreator(PredefinedAsset.Stock, 'Reverse Split Corp').commit().id()
    _listing(asset, 'RSC', USD, AssetLocation.NYSE_EXCHANGE, active=0)
    live = _listing(asset, 'RSC', USD, AssetLocation.NYSE_EXCHANGE, active=1)
    JalDB().invalidate_cache()
    assert JalAsset(asset).add_symbol('RSC', USD, AssetLocation.NYSE_EXCHANGE) == live

    token = JalAssetCreator(PredefinedAsset.Crypto, 'Tron').commit()
    listing = JalAsset(token.id()).add_symbol('TRX', EUR, AssetLocation.TRX_BLOCKCHAIN)
    assert JalSymbol(listing).currency() == USD

    with pytest.raises(ValueError):
        JalAsset(token.id()).add_symbol('TRX', asset, AssetLocation.UNDEFINED)


# A wallet kept in EUR holds a token listed in USD: the token is downloaded as its USD series
def test_active_symbols_of_a_wallet_in_another_currency(prepare_db):
    JalAccountCreator(currency_id=EUR, number='', name='EUR wallet', investing=1, organization=1).commit()
    token = JalAssetCreator(PredefinedAsset.Crypto, 'Tron').commit()
    listing = JalAsset(token.id()).add_symbol('TRX', EUR, AssetLocation.TRX_BLOCKCHAIN)
    LedgerTransaction.create_new(LedgerTransaction.Trade, {
        'timestamp': d2t(240101), 'settlement': d2t(240101), 'account_id': 1, 'symbol_id': listing, 'qty': 10,
        'price': 1, 'fee': 0, 'number': ''})
    active = [(x['symbol'].id(), x['currency']) for x in JalSymbol.get_active_symbols(0, d2t(241231))
              if x['symbol'].asset().id() == token.id()]
    assert active == [(listing, USD)]


# The asset editor refuses two active symbols with one ticker, currency and location, and says why
def test_symbol_editor_refuses_two_active_twins(prepare_db, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[3]) or QMessageBox.Ok)
    asset = JalAssetCreator(PredefinedAsset.Stock, 'Reverse Split Corp').commit().id()
    _listing(asset, 'RSC', USD, AssetLocation.NYSE_EXCHANGE, active=1)
    superseded = _listing(asset, 'RSC', USD, AssetLocation.NYSE_EXCHANGE, active=0)
    owner = QWidget()
    dialog = SymbolDialog(owner)
    dialog.setSelectedId(asset)
    model = dialog._symbols_model
    row = [x for x in range(model.rowCount()) if model.record(x).value(model.fieldIndex('id')) == superseded][0]
    model.setData(model.index(row, model.fieldIndex('active')), 1)
    dialog.accept()
    assert len(warnings) == 1 and warnings[0].endswith(': RSC')
    assert JalSymbol(superseded).active() is False


# ----------------------------------------------------------------------------------------------------------------------
# A record's identifiers belong to its own listing; a FIGI also reaches the listings of the same ISIN (one period)
def test_identifiers_stay_with_their_listing(prepare_db):
    statement = Statement()
    statement._data = {JSF.ASSETS: [{'id': 1, 'type': JSF.ASSET_STOCK, JSF.SYMBOLS: [
        {'id': 1, 'symbol': 'OLD', 'currency': 2, 'isin': 'US0000000001'}]}]}
    statement.update_asset_data(1, {'symbol': 'NEW', 'currency': 2, 'isin': 'US0000000002', 'conid': '2'})
    statement.update_asset_data(1, {'symbol': 'ALT', 'currency': 2, 'isin': 'US0000000001', 'figi': 'BBG000000001'})
    symbols = {x['symbol']: x for x in statement._data[JSF.ASSETS][0][JSF.SYMBOLS]}
    assert symbols['OLD'] == {'id': 1, 'symbol': 'OLD', 'currency': 2, 'isin': 'US0000000001', 'figi': 'BBG000000001'}
    assert symbols['NEW'] == {'id': 2, 'symbol': 'NEW', 'currency': 2, 'isin': 'US0000000002', 'conid': '2'}
    assert symbols['ALT']['figi'] == 'BBG000000001' and 'conid' not in symbols['ALT']


# A registration code on two listings of one asset still names that asset
def test_reg_code_on_two_listings_finds_the_asset(prepare_db):
    asset = JalAssetCreator(PredefinedAsset.Stock, 'Some Company').commit().id()
    for currency in (RUB, USD):
        JalDB._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:s, :t, '1-01-00001-A')",
                    [(":s", _listing(asset, 'SC', currency, AssetLocation.MOEX_EXCHANGE)), (":t", SymbolId.REG_CODE)],
                    commit=True)
    JalDB().invalidate_cache()
    assert JalAsset.find({'reg_number': '1-01-00001-A'}).id() == asset


# Listings of one ticker are told apart by their identifiers: a record finds its own period, live or superseded, and an
# ISIN no listing carries is a new period
def test_add_symbol_picks_the_period_by_identifiers(prepare_db):
    asset = JalAssetCreator(PredefinedAsset.Stock, 'Reverse Split Corp').commit().id()
    old = _listing(asset, 'RSC', USD, AssetLocation.UNDEFINED, active=0)
    new = _listing(asset, 'RSC', USD, AssetLocation.UNDEFINED, active=1)
    for listing, isin, conid in ((old, 'US0000000001', '100'), (new, 'US0000000002', '200')):
        for id_type, value in ((SymbolId.ISIN, isin), (SymbolId.CONID, conid)):
            JalDB._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:s, :t, :v)",
                        [(":s", listing), (":t", id_type), (":v", value)], commit=True)
    JalDB().invalidate_cache()
    add = lambda identifiers: JalAsset(asset).add_symbol('RSC', USD, AssetLocation.UNDEFINED, identifiers=identifiers)
    assert add({SymbolId.ISIN: 'US0000000001'}) == old
    assert add({SymbolId.CONID: '200'}) == new
    assert add({}) == new
    third = add({SymbolId.ISIN: 'US0000000003'})
    assert third not in (old, new) and JalSymbol(third).active() and not JalSymbol(new).active()
