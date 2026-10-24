import json
import logging
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
from jal.data_import.broker_statements.ibkr import StatementIBKR

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


# ----------------------------------------------------------------------------------------------------------------------
# Which venue a record means: its own when a live listing is there; with none named, the one live venue it can only
# mean, else a question, else the unknown venue; a venue written onto a listing that has none only when confirmed
def test_listing_venue_of_a_record(prepare_db):
    statement = Statement()
    asset = JalAssetCreator(PredefinedAsset.Stock, 'Nokia').commit().id()
    venue = lambda record, location: statement._listing_venue(JalAsset(asset), record, EUR, location)

    assert venue({'symbol': 'NOKIA'}, AssetLocation.UNDEFINED) == AssetLocation.UNDEFINED       # nothing live yet
    hel = _listing(asset, 'NOKIA', EUR, AssetLocation.HEL_EXCHANGE)
    JalDB().invalidate_cache()
    assert venue({'symbol': 'NOKIA'}, AssetLocation.UNDEFINED) == AssetLocation.HEL_EXCHANGE    # the one it can mean
    assert venue({'symbol': 'NOKIA'}, AssetLocation.FRA_EXCHANGE) == AssetLocation.FRA_EXCHANGE  # another venue
    _listing(asset, 'NOKIA', EUR, AssetLocation.FRA_EXCHANGE)
    JalDB().invalidate_cache()
    assert venue({'symbol': 'NOKIA'}, AssetLocation.UNDEFINED) == AssetLocation.UNDEFINED       # asked, default: new
    statement._venue_choice_for_tests = AssetLocation.FRA_EXCHANGE
    assert venue({'symbol': 'NOKIA'}, AssetLocation.UNDEFINED) == AssetLocation.FRA_EXCHANGE
    assert JalSymbol(hel).location() == AssetLocation.HEL_EXCHANGE


def test_venue_is_written_onto_a_listing_only_when_confirmed(prepare_db):
    statement = Statement()
    asset = JalAssetCreator(PredefinedAsset.Stock, 'Some Company').commit().id()
    unnamed = _listing(asset, 'SC', USD, AssetLocation.UNDEFINED)
    JalDB._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:s, :t, '100')",
                [(":s", unnamed), (":t", SymbolId.CONID)], commit=True)
    JalDB().invalidate_cache()
    venue = lambda record: statement._listing_venue(JalAsset(asset), record, USD, AssetLocation.NYSE_EXCHANGE)

    assert venue({'symbol': 'SC', 'conid': '100'}) == AssetLocation.NYSE_EXCHANGE       # not confirmed: left as it is
    assert JalSymbol(unnamed).location() == AssetLocation.UNDEFINED
    statement._venue_fill_for_tests = True
    assert venue({'symbol': 'SC', 'conid': '200'}) == AssetLocation.NYSE_EXCHANGE       # another conid: not asked
    assert JalSymbol(unnamed).location() == AssetLocation.UNDEFINED
    assert venue({'symbol': 'SC', 'conid': '100'}) == AssetLocation.NYSE_EXCHANGE       # confirmed: written on it
    assert JalSymbol(unnamed).location() == AssetLocation.NYSE_EXCHANGE


# A venue name JAL doesn't know is logged once per statement, and its listings are kept without a venue
def test_unknown_venue_name_is_logged_once(data_path, prepare_db_fifo, caplog):
    statement = StatementIBKR()                             # BRTX trades on PINK, a venue missing from the known ones
    statement.load(data_path + 'ibkr_ticker_drift_brtx.xml')
    statement.validate_format()
    statement.match_db_ids()
    with caplog.at_level(logging.INFO):
        statement.import_into_db()
    assert [x.message for x in caplog.records if 'venue' in x.message] == \
           ["Trading venue isn't known to JAL, its listings are kept without one: PINK"]
    assert {JalSymbol(x).location() for x in JalDB._read_to_list("SELECT id FROM asset_symbol WHERE symbol LIKE 'BRTX%'")} \
           == {AssetLocation.UNDEFINED}


# ----------------------------------------------------------------------------------------------------------------------
# A corporate action that only renames what is held keeps one asset; the importer reads it from a statement like this
def _rename_statement(tmp_path, action_type, figis=('', ''), names=('Old Name Corp', 'New Name Corp')) -> Statement:
    symbols = []
    for n, (ticker, isin, figi) in enumerate((('OLDT', 'US0000000011', figis[0]), ('NEWT', 'US0000000029', figis[1]))):
        symbol = {'id': 3 + n, 'symbol': ticker, 'currency': 2, 'isin': isin}
        if figi:
            symbol['figi'] = figi
        symbols.append(symbol)
    data = {'period': [d2t(240101), d2t(241231)],
            'accounts': [{'id': 1, 'number': 'U7654321', 'currency': 2, 'precision': 10}],
            'assets': [{'id': 2, 'type': 'money', 'name': 'USD', 'symbols': [{'id': 2, 'symbol': 'USD'}]},
                       {'id': 3, 'type': 'stock', 'name': names[0], 'symbols': [symbols[0]]},
                       {'id': 4, 'type': 'stock', 'name': names[1], 'symbols': [symbols[1]]}],
            'trades': [{'id': 1, 'account': 1, 'symbol': 3, 'timestamp': d2t(240301), 'settlement': d2t(240301),
                        'number': 'B1', 'quantity': 10, 'price': 1, 'fee': 0}],
            'corporate_actions': [{'id': 1, 'type': action_type, 'account': 1, 'timestamp': d2t(240601), 'number': 'C1',
                                   'symbol': 3, 'quantity': 10, 'outcome': [{'symbol': 4, 'quantity': 10, 'share': 1}],
                                   'description': 'OLDT -> NEWT'}]}
    path = tmp_path / 'rename.json'
    path.write_text(json.dumps(data))
    statement = Statement()
    statement.load(str(path))
    statement.validate_format()
    return statement


def _import(statement: Statement) -> list:
    statement.match_db_ids()
    statement.import_into_db()
    return [x for x in JalDB._read_to_list("SELECT DISTINCT asset_id FROM asset_symbol WHERE symbol IN ('OLDT', 'NEWT')")]


@pytest.mark.parametrize("action_type, figis, same_security, assets", [
    ('split', ('', ''), False, 1),                                        # a split is never a merger
    ('symbol_change', ('BBG000000001', 'BBG000000001'), False, 1),        # equal FIGIs: a rename, not asked
    ('symbol_change', ('', ''), True, 1),                                 # no FIGIs: the user says it is a rename
    ('symbol_change', ('', ''), False, 2),                                # ... or that it isn't
    ('split', ('BBG000000001', 'BBG000000002'), True, 2)])                # different FIGIs: two assets, whatever
def test_rename_keeps_one_asset(prepare_db_fifo, tmp_path, action_type, figis, same_security, assets):
    statement = _rename_statement(tmp_path, action_type, figis)
    statement._identity_for_tests = same_security
    assert len(_import(statement)) == assets


# An asset the ledger keeps already stays apart: a stored pair isn't merged by the next import of the same action
def test_stored_pair_is_not_merged(prepare_db_fifo, tmp_path):
    statement = _rename_statement(tmp_path, 'symbol_change')
    assert len(_import(statement)) == 2
    statement = _rename_statement(tmp_path, 'symbol_change')
    statement._identity_for_tests = True
    assert len(_import(statement)) == 2


# A stored asset is renamed at a rename only when the user agrees; a new asset takes the newer name
@pytest.mark.parametrize("agree", [False, True])
def test_rename_offers_the_new_name(prepare_db_fifo, tmp_path, agree):
    stored = JalAssetCreator(PredefinedAsset.Stock, 'Old Name Corp').commit().id()
    JalDB._exec("INSERT INTO symbol_ids (symbol_id, id_type, id_value) VALUES (:s, :t, 'US0000000011')",
                [(":s", _listing(stored, 'OLDT', USD, AssetLocation.UNDEFINED)), (":t", SymbolId.ISIN)], commit=True)
    JalDB().invalidate_cache()
    statement = _rename_statement(tmp_path, 'split')
    statement._rename_for_tests = agree
    assert _import(statement) == [stored]
    assert JalAsset(stored).name() == ('New Name Corp' if agree else 'Old Name Corp')

    fresh = _rename_statement(tmp_path, 'split', names=('Old Fresh', 'New Fresh'))
    fresh._data['assets'][1]['symbols'][0]['isin'] = 'US0000000037'      # a security the ledger doesn't have yet
    fresh._data['assets'][2]['symbols'][0]['isin'] = 'US0000000045'
    for asset in fresh._data['assets'][1:]:
        asset['symbols'][0]['symbol'] += 'X'
    fresh.match_db_ids()
    fresh.import_into_db()
    assert JalDB._read("SELECT full_name FROM assets WHERE id=(SELECT asset_id FROM asset_symbol WHERE symbol='NEWTX')") \
           == 'New Fresh'


# A new listing of an asset shows the icon the asset already has
def test_new_listing_takes_the_asset_icon(prepare_db):
    asset = JalAssetCreator(PredefinedAsset.Stock, 'Some Company').commit().id()
    old = _listing(asset, 'OLDT', USD, AssetLocation.NYSE_EXCHANGE)
    JalIcons.store(IconOwner.Symbol, old, b'logo', IconSource.User)
    JalDB().invalidate_cache()
    new = JalAsset(asset).add_symbol('NEWT', USD, AssetLocation.NYSE_EXCHANGE)
    assert JalIcons.image(IconOwner.Symbol, new) == b'logo' and JalIcons.source(IconOwner.Symbol, new) == IconSource.User
