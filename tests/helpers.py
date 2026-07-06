import os
from decimal import Decimal
from datetime import datetime, timezone
from jal.db.db import JalDB
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.account import JalAccount
from jal.db.operations import LedgerTransaction, AssetPayment
from constants import PredefinedAsset, AssetLocation, SymbolId
from jal.data_export.xlsx import XLSX


# ----------------------------------------------------------------------------------------------------------------------
# Resolves an asset id (as used throughout test fixtures) into its symbol id. Test fixtures are single-symbol
# almost everywhere, so the first (oldest) symbol found for the asset is the unambiguous one - except a few
# multi-symbol fixtures that deliberately test one asset traded under different symbols per currency/account,
# where currency_id disambiguates which of the asset's symbols is meant.
def symbol_id_for(asset_id, currency_id=None):
    if asset_id is None:
        return None
    if currency_id is not None:
        symbol_id = JalDB._read("SELECT id FROM asset_symbol WHERE asset_id=:asset_id AND currency_id=:currency_id "
                                "ORDER BY id LIMIT 1", [(":asset_id", asset_id), (":currency_id", currency_id)])
        if symbol_id is not None:
            return symbol_id
    return JalDB._read("SELECT id FROM asset_symbol WHERE asset_id=:asset_id ORDER BY id LIMIT 1", [(":asset_id", asset_id)])


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
    m, y = pop2minor_digits(date_value)
    ts = int(datetime.strptime(f"{d:02d}/{m:02d}/{y:02d}", "%d/%m/%y").replace(tzinfo=timezone.utc).timestamp())
    return ts

# converts YYMMDD integer into python datetime(20YY, MM, DD, tzinfo=timezone.utc)
def d2dt(date_value: int) -> datetime:
    d, date_value = pop2minor_digits(date_value)
    m, y = pop2minor_digits(date_value)
    return datetime(2000+y, m, d, tzinfo=timezone.utc)

# converts YYMMDDHHMM integer into unix timestamp that corresponds to DD/MM/20YY HH:MM:00
def dt2t(datetime_value: int) -> int:
    mm, datetime_value = pop2minor_digits(datetime_value)
    hh, datetime_value = pop2minor_digits(datetime_value)
    d, datetime_value = pop2minor_digits(datetime_value)
    m, y = pop2minor_digits(datetime_value)
    dt = datetime.strptime(f"{d:02d}/{m:02d}/{y:02d} {hh:02d}:{mm:02d}", "%d/%m/%y %H:%M")
    ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
    return ts

# converts YYMMDDHHMM integer into python datetime(20YY, MM, DD, HH, MM, tzinfo=timezone.utc)
def dt2dt(datetime_value: int) -> datetime:
    mm, datetime_value = pop2minor_digits(datetime_value)
    hh, datetime_value = pop2minor_digits(datetime_value)
    d, datetime_value = pop2minor_digits(datetime_value)
    m, y = pop2minor_digits(datetime_value)
    return datetime(2000+y, m, d, hh, mm, tzinfo=timezone.utc)

# ----------------------------------------------------------------------------------------------------------------------
# Helper functions to convert Decimals inside nested dictionaries into floats in order to compare with stored json
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
# Create assets in database with PredefinedAsset.Stock type : assets is a list of tuples (symbol, full_name)
def create_stocks(assets, currency_id):
    for item in assets:
        creator = JalAssetCreator(PredefinedAsset.Stock, item[1])
        creator.add_symbol(item[0], currency_id, location_id=AssetLocation.UNDEFINED)
        creator.commit()


# ----------------------------------------------------------------------------------------------------------------------
# Create assets in database with PredefinedAsset.Stock type : assets is a list of tuples
# (symbol, full_name, isin, currency_id, asset_type, country_id)
def create_assets(assets, data=[]):
    for item in assets:
        creator = JalAssetCreator(item[4], item[1], country=item[5])
        symbol_id = creator.add_symbol(item[0], item[3], location_id=AssetLocation.UNDEFINED)
        if item[2]:
            creator.add_identifier(symbol_id, SymbolId.ISIN, item[2])
        creator.commit()
    for item in data:
        JalAsset(item[0], symbol_id=symbol_id_for(item[0])).update_data({item[1]: item[2]})


# ----------------------------------------------------------------------------------------------------------------------
# Insert quotes for asset_id, currency_id into database. Quotes is a list of (timestamp, quote) tuples
def create_quotes(asset_id: int, currency_id: int, quotes: list):
    JalAsset(asset_id).set_quotes([{'timestamp': x[0], 'quote': Decimal(str(x[1]))} for x in quotes], currency_id)


# ----------------------------------------------------------------------------------------------------------------------
# Create actions in database: actions is a list of tuples
# (timestamp, account, peer, [(category, amount, [note]), (category, amount, [note]), ...])
def create_actions(actions):
    for action in actions:
        details = []
        for detail in action[3]:
            note = detail[2] if len(detail) > 2 else ''
            details.append({"amount": detail[1], "category_id": detail[0], "note": note})
        data = {'timestamp': action[0], 'account_id': action[1], 'peer_id': action[2], 'lines': details}
        LedgerTransaction.create_new(LedgerTransaction.IncomeSpending, data)


# ----------------------------------------------------------------------------------------------------------------------
# Create dividends in database: dividends is a list of dividends as tuples
# (timestamp, account, asset_id, amount, tax, note)
def create_dividends(dividends):
    for dividend in dividends:
        data = {'timestamp': dividend[0], 'type': AssetPayment.Dividend, 'account_id': dividend[1],
                'symbol_id': symbol_id_for(dividend[2]), 'amount': dividend[3], 'tax': dividend[4], 'note': dividend[5]}
        LedgerTransaction.create_new(LedgerTransaction.AssetPayment, data)


# ----------------------------------------------------------------------------------------------------------------------
# Create dividends with type "interest" in database: coupons is a list of interests as tuples
# (timestamp, account, asset_id, amount, tax, note, number)
def create_coupons(coupons):
    for coupon in coupons:
        data = {'timestamp': coupon[0], 'type': AssetPayment.BondInterest, 'account_id': coupon[1],
                'symbol_id': symbol_id_for(coupon[2]), 'amount': coupon[3], 'tax': coupon[4], 'note': coupon[5],
                'number': coupon[6]}
        LedgerTransaction.create_new(LedgerTransaction.AssetPayment, data)


# ----------------------------------------------------------------------------------------------------------------------
# Create dividends in database: dividends is a list of dividends as tuples
# (type, timestamp, account, asset_id, qty, currency_id, quote, tax, note)
# Type = StockDividend or StockVesting
def create_stock_dividends(dividends):
    for dividend in dividends:
        create_quotes(dividend[3], dividend[5], [(dividend[1], dividend[6])])
        data = {'timestamp': dividend[1], 'type': dividend[0], 'account_id': dividend[2],
                'symbol_id': symbol_id_for(dividend[3]), 'amount': dividend[4], 'tax': dividend[7], 'note': dividend[8]}
        LedgerTransaction.create_new(LedgerTransaction.AssetPayment, data)


# ----------------------------------------------------------------------------------------------------------------------
# Create trades for given account_id in database: trades is a list of trades as tuples
# (timestamp, settlement, asset_id, qty, price, fee, [number])
def create_trades(account_id, trades):
    currency_id = JalAccount(account_id).currency()
    for trade in trades:
        number = trade[6] if len(trade) > 6 else ''
        data = {'timestamp': trade[0], 'settlement': trade[1], 'account_id': account_id,
                'symbol_id': symbol_id_for(trade[2], currency_id), 'qty': trade[3], 'price': trade[4], 'fee': trade[5],
                'number': number}
        LedgerTransaction.create_new(LedgerTransaction.Trade, data)


# ----------------------------------------------------------------------------------------------------------------------
# Create corporate actions for given account_id in database: actions is a list of tuples
# (timestamp, type, asset_old, qty_old, note, [(asset_new1, qty_new1, share1), (asset_new2, qty_new2, share2), ...])
def create_corporate_actions(account_id, actions):
    for action in actions:
        outcomes = []
        for result in action[5]:
            outcomes.append({"symbol_id": symbol_id_for(result[0]), "qty": result[1], "value_share": result[2]})
        data = {'timestamp': action[0], 'account_id': account_id, 'type': action[1],
                'symbol_id': symbol_id_for(action[2]), 'qty': action[3], 'note': action[4], 'outcome': outcomes}
        LedgerTransaction.create_new(LedgerTransaction.CorporateAction, data)


# ----------------------------------------------------------------------------------------------------------------------
# Create transfers in database: transfers is a list of transfers as tuples
# (timestamp, withdrawal_account, withdrawal, deposit_account, deposit, asset_id)
def create_transfers(transfers):
    for transfer in transfers:
        currency_id = JalAccount(transfer[1]).currency() if transfer[5] is not None else None
        data = {'withdrawal_timestamp': transfer[0], 'withdrawal_account': transfer[1], 'withdrawal': transfer[2],
                'deposit_timestamp': transfer[0], 'deposit_account': transfer[3], 'deposit': transfer[4],
                'symbol_id': symbol_id_for(transfer[5], currency_id)}
        LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


# ----------------------------------------------------------------------------------------------------------------------
def save_test_xls_report(path, tax_report):
    reports_xls = XLSX(str(path) + os.sep + "taxes.xls")
    templates = {
        "Акции":     "tax_rus_trades.json",
        "Облигации": "tax_rus_bonds.json",
        "Дивиденды": "tax_rus_dividends.json",
        "ПФИ":       "tax_rus_derivatives.json",
        "Комиссии":  "tax_rus_fees.json",
        "Проценты":  "tax_rus_interests.json"
    }
    parameters = {
        "period": "01.01.2022 - 31.12.2022",
        "account": "TEST U7654321 (USD)",
        "currency": "USD",
        "broker_name": "IBKR",
        "broker_iso_country": "840"
    }
    for section in tax_report:
        if section not in templates:
            continue
        reports_xls.output_data(tax_report[section], templates[section], parameters)
    reports_xls.save()
