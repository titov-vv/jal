from decimal import Decimal
from datetime import datetime, timezone
from jal.db.db import JalDB
from jal.db.operations import Dividend
from constants import PredefinedAsset


# ----------------------------------------------------------------------------------------------------------------------
# Helper that takes 2 minor digits of x numer and returns them and number without it.
# I.e. if x = 12345 then return value is (45, 123)
def pop2minor_digits(x: int) -> (int, int):
    minor = x % 100
    reminder = (x - minor) // 100
    return minor, reminder

# converts YYMMDD integer into unix timestamp that corresponds to DD/MM/20YY 00:00:00
def d2t(date_value: int) -> int:
    d, date_value = pop2minor_digits(date_value)
    m, y = pop2minor_digits( date_value)
    ts = int(datetime.strptime(f"{d:02d}/{m:02d}/{y:02d}", "%d/%m/%y").replace(tzinfo=timezone.utc).timestamp())
    return ts

# converts YYMMDDHHMM integer into unix timestamp that corresponds to DD/MM/20YY HH:MM:00
def dt2t(datetime_value: int) -> int:
    hh, datetime_value = pop2minor_digits(datetime_value)
    mm, datetime_value = pop2minor_digits(datetime_value)
    d, datetime_value = pop2minor_digits(datetime_value)
    m, y = pop2minor_digits(datetime_value)
    dt = datetime.strptime(f"{d:02d}/{m:02d}/{y:02d} {hh:02d}:{mm:02d}", "%d/%m/%y %H:%M")
    ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
    return ts

# ----------------------------------------------------------------------------------------------------------------------
# Helper functions to convert Decimals inside nested dictionaries into flaots in order to compare with stored json
def json_decimal2float(json_obj):
    if type(json_obj) == dict:
        for x in json_obj:
            if type(json_obj[x]) == list:
                for item in json_obj[x]:
                    json_decimal2float(item)
            if type(json_obj[x]) == dict:
                json_decimal2float(json_obj[x])
            if type(json_obj[x]) == Decimal:
                json_obj[x] = float(str(json_obj[x]))


# ----------------------------------------------------------------------------------------------------------------------
# Create assets in database with PredefinedAsset.Stock type : assets is a list of tuples (asset_id, symbol, full_name)
def create_stocks(assets, currency_id):
    for asset in assets:
        query = JalDB._exec("INSERT INTO assets (id, type_id, full_name) VALUES (:id, :type, :full_name)",
                            [(":id", asset[0]), (":type", PredefinedAsset.Stock),
                                   (":full_name", asset[2])], commit=True)
        asset_id = query.lastInsertId()
        assert JalDB._exec("INSERT INTO asset_tickers (asset_id, symbol, currency_id) "
                                 "VALUES (:asset_id, :symbol, :currency_id)",
                           [(":asset_id", asset_id), (":symbol", asset[1]), (":currency_id", currency_id)],
                           commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Create assets in database with PredefinedAsset.Stock type : assets is a list of tuples
# (id, symbol, full_name, isin, currency_id, asset_type, country_id)
def create_assets(assets, data=[]):
    for asset in assets:
        query = JalDB._exec("INSERT INTO assets (id, type_id, full_name, isin, country_id) "
                                  "VALUES (:id, :type, :full_name, :isin, :country_id)",
                            [(":id", asset[0]), (":type", asset[5]), (":full_name", asset[2]),
                                   (":isin", asset[3]), (":country_id", asset[6])], commit=True)
        asset_id = query.lastInsertId()
        assert JalDB._exec("INSERT INTO asset_tickers (asset_id, symbol, currency_id) "
                                 "VALUES (:asset_id, :symbol, :currency_id)",
                           [(":asset_id", asset_id), (":symbol", asset[1]), (":currency_id", asset[4])],
                           commit=True) is not None
    for item in data:
        assert JalDB._exec(
            "INSERT INTO asset_data (asset_id, datatype, value) VALUES (:asset_id, :datatype, :value)",
            [(":asset_id", item[0]), (":datatype", item[1]), (":value", item[2])],
            commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Insert quotes for asset_id, currency_id into database. Quotes is a list of (timestamp, quote) tuples
def create_quotes(asset_id, currency_id, quotes):
    for quote in quotes:
        assert JalDB._exec("INSERT OR REPLACE INTO quotes (asset_id, currency_id, timestamp, quote) "
                                 "VALUES (:asset_id, :currency_id, :timestamp, :quote)",
                           [(":asset_id", asset_id), (":currency_id", currency_id),
                                  (":timestamp", quote[0]), (":quote", quote[1])],
                           commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Create actions in database: actions is a list of tuples
# (timestamp, account, peer, [(category, amount, [note]), (category, amount, [note]), ...])
def create_actions(actions):
    for action in actions:
        query = JalDB._exec("INSERT INTO actions (timestamp, account_id, peer_id) "
                                  "VALUES (:timestamp, :account, :peer)",
                            [(":timestamp", action[0]), (":account", action[1]), (":peer", action[2])],
                            commit=True)
        assert query is not None
        action_id = query.lastInsertId()
        for detail in action[3]:
            note = detail[2] if len(detail) > 2 else ''
            assert JalDB._exec("INSERT INTO action_details (pid, category_id, amount, note) "
                                     "VALUES (:pid, :category, :amount, :note)",
                               [(":pid", action_id), (":category", detail[0]), (":amount", detail[1]),
                                      (":note", note)],
                               commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Create dividends in database: dividends is a list of dividends as tuples
# (timestamp, account, asset_id, amount, tax, note)
def create_dividends(dividends):
    for dividend in dividends:
        assert JalDB._exec("INSERT INTO dividends (timestamp, type, account_id, asset_id, amount, tax, note) "
                                 "VALUES (:timestamp, :div_type, :account_id, :asset_id, :amount, :tax, :note)",
                           [(":timestamp", dividend[0]), (":div_type", Dividend.Dividend),
                                  (":account_id", dividend[1]), (":asset_id", dividend[2]), (":amount", dividend[3]),
                                  (":tax", dividend[4]), (":note", dividend[5])], commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Create dividends with type "interest" in database: coupons is a list of interests as tuples
# (timestamp, account, asset_id, amount, tax, note, number)
def create_coupons(coupons):
    for coupon in coupons:
        assert JalDB._exec(
            "INSERT INTO dividends (timestamp, type, account_id, asset_id, amount, tax, note, number) "
            "VALUES (:timestamp, :div_type, :account_id, :asset_id, :amount, :tax, :note, :number)",
            [(":timestamp", coupon[0]), (":div_type", Dividend.BondInterest),
             (":account_id", coupon[1]), (":asset_id", coupon[2]), (":amount", coupon[3]),
             (":tax", coupon[4]), (":note", coupon[5]), (":number", coupon[6])], commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Create dividends in database: dividends is a list of dividends as tuples
# (type, timestamp, account, asset_id, qty, currency_id, quote, tax, note)
# Type = StockDividend or StockVesting
def create_stock_dividends(dividends):
    for dividend in dividends:
        create_quotes(dividend[3], dividend[5], [(dividend[1], dividend[6])])
        assert JalDB._exec("INSERT INTO dividends (timestamp, type, account_id, asset_id, amount, tax, note) "
                                 "VALUES (:timestamp, :div_type, :account_id, :asset_id, :amount, :tax, :note)",
                           [(":timestamp", dividend[1]), (":div_type", dividend[0]),
                                  (":account_id", dividend[2]), (":asset_id", dividend[3]), (":amount", dividend[4]),
                                  (":tax", dividend[7]), (":note", dividend[8])], commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Create trades for given account_id in database: trades is a list of trades as tuples
# (timestamp, settlement, asset_id, qty, price, fee, [number])
def create_trades(account_id, trades):
    for trade in trades:
        number = trade[6] if len(trade) > 6 else ''
        assert JalDB._exec(
            "INSERT INTO trades (timestamp, settlement, account_id, asset_id, qty, price, fee, number) "
            "VALUES (:timestamp, :settlement, :account_id, :asset, :qty, :price, :fee, :number)",
            [(":timestamp", trade[0]), (":settlement", trade[1]), (":account_id", account_id),
             (":asset", trade[2]), (":qty", trade[3]), (":price", trade[4]), (":fee", trade[5]),
             (":number", number)], commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Create corporate actions for given account_id in database: actions is a list of tuples
# (timestamp, type, asset_old, qty_old, note, [(asset_new1, qty_new1, share1), (asset_new2, qty_new2, share2), ...])
def create_corporate_actions(account_id, actions):
    for action in actions:
        query = JalDB._exec("INSERT INTO asset_actions (timestamp, account_id, type, asset_id, qty, note) "
                                  "VALUES (:timestamp, :account_id, :type, :asset_id, :qty, :note)",
                            [(":timestamp", action[0]), (":account_id", account_id), (":type", action[1]),
                                   (":asset_id", action[2]), (":qty", action[3]), (":note", action[4])], commit=True)
        assert query is not None
        action_id = query.lastInsertId()
        for result in action[5]:
            assert JalDB._exec("INSERT INTO action_results (action_id, asset_id, qty, value_share) "
                                     "VALUES (:action_id, :asset_id, :qty, :value_share)",
                               [(":action_id", action_id), (":asset_id", result[0]),
                                      (":qty", result[1]), (":value_share", result[2])], commit=True) is not None


# ----------------------------------------------------------------------------------------------------------------------
# Create transfers in database: transfers is a list of transfers as tuples
# (timestamp, withdrawal_account, withdrawal, deposit_account, deposit, asset_id)
def create_transfers(transfers):
    for transfer in transfers:
        assert JalDB._exec("INSERT INTO transfers (withdrawal_timestamp, withdrawal_account, withdrawal, "
                                 "deposit_timestamp, deposit_account, deposit, asset) "
                                 "VALUES (:timestamp, :from, :withdrawal, :timestamp, :to, :deposit, :asset_id)",
                           [(":timestamp", transfer[0]), (":from", transfer[1]), (":withdrawal", transfer[2]),
                                  (":to", transfer[3]), (":deposit", transfer[4]), (":asset_id", transfer[5])],
                           commit=True) is not None
