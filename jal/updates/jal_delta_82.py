import logging
from jal.constants import AssetLocation, IconOwner
from jal.db.db import JalDB
from jal.db.asset import JalAsset

# Every column that names a listing, besides 'symbol_ids' and 'icons' that are moved by their own rules
_REFERENCES = [('fees', 'symbol_id'), ('asset_payments', 'symbol_id'), ('asset_incomes', 'symbol_id'),
               ('chain_actions', 'symbol_id'), ('asset_actions', 'symbol_id'), ('asset_action_results', 'symbol_id'),
               ('trades', 'symbol_id'), ('transfers', 'symbol_id'), ('swaps', 'out_symbol_id'), ('swaps', 'in_symbol_id'),
               ('bridges', 'out_symbol_id'), ('bridges', 'in_symbol_id'), ('conversions', 'out_symbol_id'),
               ('conversions', 'in_symbol_id')]


# Puts every crypto listing into its venue's quote currency. Listings of one asset that differed by currency only
# become one: the one already in that currency is kept, else the one with identifiers, else a live one, else the oldest.
def update() -> None:
    crypto = ','.join(str(x) for x in AssetLocation.CRYPTO_LOCATIONS)
    rows = JalDB._read_to_list(f"SELECT id, asset_id, symbol, currency_id, location_id, active, "
                               f"(SELECT COUNT(*) FROM symbol_ids WHERE symbol_id=s.id) FROM asset_symbol s "
                               f"WHERE location_id IN ({crypto}) ORDER BY id")
    groups = {}
    for row in rows:
        groups.setdefault((row[1], row[2].upper(), row[4]), []).append(row)
    moved = False
    for (asset_id, ticker, location_id), listings in groups.items():
        currency_id = JalAsset.listing_currency(0, location_id)
        if not currency_id:
            logging.warning(f"Crypto listing left in its currency, the ledger has no quote currency for it: {ticker}")
            continue
        if all(x[3] == currency_id for x in listings):
            continue
        keeper = sorted(listings, key=lambda x: (x[3] != currency_id, x[6] == 0, x[5] != 1, x[0]))[0]
        for listing in [x for x in listings if x[0] != keeper[0]]:
            _merge(listing[0], keeper[0])
            moved = True
        JalDB._exec("UPDATE asset_symbol SET currency_id=:currency, active=:active WHERE id=:id",
                    [(":currency", currency_id), (":active", max(x[5] for x in listings)), (":id", keeper[0])],
                    commit=True)
    if moved:
        JalDB._exec("INSERT OR REPLACE INTO settings(name, value) VALUES('RebuildDB', 1)", commit=True)


# Moves everything that names listing 'old' onto listing 'new' and deletes 'old'
def _merge(old: int, new: int) -> None:
    for table, column in _REFERENCES:
        JalDB._exec(f"UPDATE {table} SET {column}=:new WHERE {column}=:old", [(":new", new), (":old", old)])
    JalDB._exec("UPDATE symbol_ids SET symbol_id=:new WHERE symbol_id=:old AND id_type NOT IN "
                "(SELECT id_type FROM symbol_ids WHERE symbol_id=:new)", [(":new", new), (":old", old)])
    JalDB._exec("DELETE FROM symbol_ids WHERE symbol_id=:old", [(":old", old)])
    JalDB._exec("UPDATE icons SET item_id=:new WHERE entity=:symbol AND item_id=:old AND NOT EXISTS "
                "(SELECT 1 FROM icons WHERE entity=:symbol AND item_id=:new)",
                [(":new", new), (":old", old), (":symbol", IconOwner.Symbol)])
    JalDB._exec("DELETE FROM asset_symbol WHERE id=:old", [(":old", old)], commit=True)
