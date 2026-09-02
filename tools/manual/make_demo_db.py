#!/usr/bin/env python
# Builds the database every screenshot in the manual is taken from.
# Everything it writes is invented: the people, the companies, the account numbers, the prices and the dates
# have nothing to do with any real ledger. Run it again at any time - it starts from an empty database.
import os
import sys
from decimal import Decimal
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from demo_env import prepare_environment, assert_demo_database, DEMO_DIR

prepare_environment()

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from jal.db.db import JalDB, JalDBError
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.symbol import JalSymbol
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.category import JalCategory
from jal.db.peer import JalPeer
from jal.db.tag import JalTag
from jal.db.deposit import JalDepositBox
from jal.db.operations import LedgerTransaction, AssetPayment
from jal.db.ledger import Ledger
from jal.db.residence import JalResidence
from jal.db.settings import JalSettings
from jal.constants import (PredefinedCategory, PredefinedAsset, PredefinedAccountType, AssetLocation,
                           SymbolId, AssetData, AccountData, AccountStatus)

EUR, USD, RUB = 3, 2, 1


def ts(text: str) -> int:    # "2026-03-05 14:30" or "2026-03-05" -> unix timestamp
    fmt = "%Y-%m-%d %H:%M" if len(text) > 10 else "%Y-%m-%d"
    return int(datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).timestamp())


def rebuild_database() -> None:
    path = assert_demo_database()
    if os.path.isfile(path):
        os.remove(path)
    error = JalDB().init_db()
    if error.code != JalDBError.NoError:
        raise RuntimeError(f"Can't initialize demo database: {error.message} {error.details}")
    assert_demo_database()


def sid(asset_id: int, currency_id: int = None) -> int:   # asset -> its listing (asset_symbol) id
    if currency_id is not None:
        found = JalDB._read("SELECT id FROM asset_symbol WHERE asset_id=:a AND currency_id=:c ORDER BY id LIMIT 1",
                            [(":a", asset_id), (":c", currency_id)])
        if found:
            return found
    return JalDB._read("SELECT id FROM asset_symbol WHERE asset_id=:a ORDER BY id LIMIT 1", [(":a", asset_id)])


# The initialization script seeds the three built-in currencies with Russian names; the manual is in English.
def rename_currencies() -> None:
    for asset_id, name in ((RUB, "Russian Rouble"), (USD, "US Dollar"), (EUR, "Euro")):
        JalDB._exec("UPDATE assets SET full_name=:name WHERE id=:id",
                    [(":name", name), (":id", asset_id)], commit=True)
    JalAsset.db_cache.clear_cache()


def set_residence() -> None:
    JalDB._exec("INSERT INTO residence (since_timestamp, currency_id, country_id, timezone) "
                "VALUES (:since, :currency, (SELECT id FROM countries WHERE code='de'), :zone)",
                [(":since", ts("2024-01-01")), (":currency", EUR), (":zone", "Europe/Berlin")], commit=True)
    JalResidence.invalidate_cache()


def create_peers() -> dict:
    names = ["Bright Path Studio", "Lindenhof Rentals", "Sonnenmarkt", "City Energy",
             "Isarbank", "Northgate Securities", "Café Kastanie", "Apotheke am Markt", "Nimbus Mobile",
             "Stadtlinie Transit"]
    peers = {}
    for name in names:
        peers[name] = JalPeer(data={'name': name}, search=True, create=True).id()
    return peers


def create_categories() -> dict:
    tree = {PredefinedCategory.Income: ["Salary", "Freelance"],
            PredefinedCategory.Spending: ["Groceries", "Rent", "Utilities", "Transport",
                                          "Eating out", "Health", "Leisure"]}
    categories = {}
    for parent, children in tree.items():
        for name in children:
            query = JalDB._exec("INSERT INTO categories (pid, name) VALUES (:pid, :name)",
                                [(":pid", parent), (":name", name)], commit=True)
            categories[name] = query.lastInsertId()
    return categories


def create_tags() -> dict:
    tags = {}
    for name in ["Holiday", "Car", "Home"]:
        query = JalDB._exec("INSERT INTO tags (pid, tag) VALUES (0, :tag)", [(":tag", name)], commit=True)
        tags[name] = query.lastInsertId()
    return tags


def create_accounts(peers: dict) -> dict:
    accounts = {}
    accounts['cash'] = JalAccountCreator(currency_id=EUR, number='', name="Pocket Cash",
                                         account_type=PredefinedAccountType.Cash).id()
    accounts['bank'] = JalAccountCreator(currency_id=EUR, number="DE44 5001 0517 4297 3061 88",
                                         name="Isarbank Current", organization=peers["Isarbank"],
                                         country='de', account_type=PredefinedAccountType.Bank).id()
    accounts['card'] = JalAccountCreator(currency_id=EUR, number="4571 ** ** 3092", name="Everyday Card",
                                         organization=peers["Isarbank"], country='de',
                                         account_type=PredefinedAccountType.Card).id()
    accounts['broker'] = JalAccountCreator(currency_id=USD, number="U3456789", name="Northgate Trading",
                                           investing=1, organization=peers["Northgate Securities"],
                                           country='us', account_type=PredefinedAccountType.Broker).id()
    accounts['cex'] = JalAccountCreator(currency_id=USD, number="VX-77104", name="Vertex Exchange",
                                        investing=1, precision=8,
                                        account_type=PredefinedAccountType.CEX).id()
    accounts['wallet'] = JalAccountCreator(
        currency_id=USD, number='', name="Cold Wallet", investing=1, precision=10,
        account_type=PredefinedAccountType.Wallet, chain=AssetLocation.ETH_BLOCKCHAIN,
        address="0x71c9f4b2a5d8e30617ab4c9d2f5083ea6b1d47c0").id()
    JalDB._exec("INSERT INTO account_data (account_id, datatype, value) VALUES (:id, :type, :value)",
                [(":id", accounts['card']), (":type", AccountData.Credit), (":value", "1500")], commit=True)
    JalAccount.db_cache.update_data(JalAccount._load_account_data, (accounts['card'],))
    # The exchange account is emptied into the wallet and keeps a few dollars of change - money that is still real
    # and needs no daily attention. It is the demo's background account, so that the balances panel and the
    # portfolio report show the folded group the manual describes.
    JalAccount(accounts['cex']).set_status(AccountStatus.Background)
    return accounts


def create_assets() -> dict:
    assets = {}
    definitions = [
        ('acme', PredefinedAsset.Stock, "Acme Industries Inc.", 'us', "ACME", USD,
         AssetLocation.NYSE_EXCHANGE, SymbolId.ISIN, "US0000000017"),
        ('wldx', PredefinedAsset.ETF, "Global Index ETF", 'ie', "WLDX", USD,
         AssetLocation.NYSE_EXCHANGE, SymbolId.ISIN, "IE0000000024"),
        ('mrail', PredefinedAsset.Bond, "Meridian Rail 4.4% 2031", 'us', "MRAIL31", USD,
         AssetLocation.NYSE_EXCHANGE, SymbolId.ISIN, "US0000000031"),
        ('btc', PredefinedAsset.Crypto, "Bitcoin", '', "BTC", USD, AssetLocation.CEX_EXCHANGE, None, None),
        ('eth', PredefinedAsset.Crypto, "Ethereum", '', "ETH", USD, AssetLocation.ETH_BLOCKCHAIN,
         SymbolId.ETH_ADDRESS, ''),
        ('usdc', PredefinedAsset.Crypto, "USD Coin", '', "USDC", USD, AssetLocation.ETH_BLOCKCHAIN,
         SymbolId.ETH_ADDRESS, "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
    ]
    for key, type_id, name, country, symbol, currency, location, id_type, id_value in definitions:
        creator = JalAssetCreator(type_id, name, country=country)
        symbol_id = creator.add_symbol(symbol, currency, location_id=location)
        if id_type is not None and id_value:
            creator.add_identifier(symbol_id, id_type, id_value)
        assets[key] = creator.commit().id()
    JalAsset(assets['mrail']).update_data({AssetData.PrincipalValue: '1000'})
    return assets


# Monthly closing prices, invented. The list is walked month by month from 'start'.
def set_quotes(asset_id: int, currency_id: int, start: str, prices: list) -> None:
    moment = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    quotes = []
    for price in prices:
        quotes.append({'timestamp': int(moment.timestamp()), 'quote': Decimal(str(price))})
        moment = (moment.replace(day=28) + timedelta(days=8)).replace(day=1)
    JalAsset(asset_id).set_quotes(quotes, currency_id)


def create_quotes(assets: dict) -> None:
    # EUR value of one USD, twenty months from January 2025
    set_quotes(USD, EUR, "2025-01-01",
               [0.958, 0.962, 0.951, 0.939, 0.928, 0.921, 0.916, 0.924, 0.931, 0.927, 0.918, 0.912,
                0.905, 0.899, 0.893, 0.902, 0.897, 0.888, 0.881, 0.876])
    set_quotes(assets['acme'], USD, "2025-01-01",
               [116.40, 118.75, 121.30, 119.60, 123.85, 126.10, 124.55, 128.90, 131.25, 129.70, 133.40, 136.15,
                134.80, 138.20, 137.05, 141.60, 144.35, 142.90, 147.20, 149.85])
    set_quotes(assets['wldx'], USD, "2025-01-01",
               [91.20, 92.45, 93.80, 92.15, 94.60, 96.05, 95.30, 97.85, 99.10, 98.40, 100.75, 102.30,
                101.55, 103.90, 103.20, 105.60, 107.15, 106.40, 108.95, 110.50])
    # A bond is held in whole pieces here, so its quote is the price of one piece and not a per cent of the principal
    set_quotes(assets['mrail'], USD, "2025-01-01",
               [972.0, 975.5, 981.0, 978.0, 983.5, 989.0, 991.5, 987.0, 994.0, 998.5, 1002.0, 1000.5,
                997.5, 1003.0, 1006.0, 1001.5, 1008.0, 1011.0, 1009.5, 1014.0])
    set_quotes(assets['eth'], USD, "2025-01-01",
               [2380, 2455, 2310, 2520, 2610, 2545, 2680, 2790, 2705, 2860, 2975, 2890,
                3040, 3125, 3060, 3210, 3305, 3240, 3380, 3455])
    set_quotes(assets['usdc'], USD, "2025-01-01", [1] * 20)
    set_quotes(assets['btc'], USD, "2025-01-01",
               [42800, 44150, 41900, 45600, 47300, 46050, 48900, 51200, 49700, 52800, 55100, 53400,
                56900, 58300, 57100, 60400, 62800, 61200, 64500, 66900])


def spend(timestamp: int, account: int, peer: int, lines: list) -> None:
    details = [{"category_id": category, "amount": Decimal(str(amount)), "note": note}
               for category, amount, note in lines]
    LedgerTransaction.create_new(LedgerTransaction.IncomeSpending,
                                 {'timestamp': timestamp, 'account_id': account, 'peer_id': peer, 'lines': details})


def transfer(timestamp: int, from_account: int, amount, to_account: int, received, fee=None, note='') -> None:
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account,
            'withdrawal': Decimal(str(amount)), 'deposit_timestamp': timestamp,
            'deposit_account': to_account, 'deposit': Decimal(str(received)), 'note': note}
    if fee is not None:
        data['fee_account'] = from_account
        data['fee'] = Decimal(str(fee))
    LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


def trade(timestamp: int, account: int, asset_id: int, qty, price, fee, number='') -> None:
    LedgerTransaction.create_new(LedgerTransaction.Trade,
                                 {'timestamp': timestamp, 'settlement': timestamp + 2 * 24 * 60 * 60,
                                  'account_id': account, 'symbol_id': sid(asset_id, USD),
                                  'qty': Decimal(str(qty)), 'price': Decimal(str(price)),
                                  'fee': Decimal(str(fee)), 'number': number})


def payment(timestamp: int, ptype: int, account: int, asset_id: int, amount, tax=0, note='', number='') -> None:
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment,
                                 {'timestamp': timestamp, 'type': ptype, 'account_id': account,
                                  'symbol_id': sid(asset_id, USD), 'amount': Decimal(str(amount)),
                                  'tax': Decimal(str(tax)), 'note': note, 'number': number})


def months(first: str, count: int):
    moment = datetime.strptime(first, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    for _ in range(count):
        yield moment
        moment = (moment.replace(day=28) + timedelta(days=8)).replace(day=1)


def create_household_operations(accounts: dict, peers: dict, categories: dict, tags: dict) -> None:
    spend(ts("2025-01-01"), accounts['bank'], 1, [(PredefinedCategory.StartingBalance, '6200.00', '')])
    spend(ts("2025-01-01"), accounts['cash'], 1, [(PredefinedCategory.StartingBalance, '120.00', '')])
    salary = ['2450.00'] * 12 + ['2530.00'] * 8
    groceries = [78.40, 64.15, 91.80, 55.60]
    card_spending = Decimal('0')       # repaid in full at the 20th of the next month
    for index, month in enumerate(months("2025-01-01", 20)):
        day = lambda number, hour=12: int(month.replace(day=number, hour=hour).timestamp())

        def card(timestamp, peer, lines):
            nonlocal card_spending
            card_spending -= sum(Decimal(str(amount)) for _, amount, _ in lines)
            spend(timestamp, accounts['card'], peer, lines)

        if card_spending:
            transfer(day(20, 10), accounts['bank'], card_spending, accounts['card'], card_spending,
                     note="Card balance repayment")
            card_spending = Decimal('0')
        spend(day(5, 9), accounts['bank'], peers["Bright Path Studio"],
              [(categories["Salary"], salary[index], "Monthly salary")])
        spend(day(3, 8), accounts['bank'], peers["Lindenhof Rentals"],
              [(categories["Rent"], f"-{980 + 10 * (index // 12)}.00", '')])
        spend(day(12, 18), accounts['bank'], peers["City Energy"],
              [(categories["Utilities"], f"-{74 + (index % 5) * 6}.35", "Electricity and water")])
        card(day(14, 19), peers["Nimbus Mobile"], [(categories["Utilities"], '-19.99', "Mobile plan")])
        for week, amount in enumerate(groceries):
            card(day(4 + 7 * week, 17), peers["Sonnenmarkt"],
                 [(categories["Groceries"], f"-{amount + index % 7}", '')])
        card(day(9, 13), peers["Café Kastanie"], [(categories["Eating out"], '-24.50', '')])
        transfer(day(22, 15), accounts['bank'], '100.00', accounts['cash'], '100.00', note="ATM withdrawal")
        spend(day(16, 11), accounts['cash'], peers["Sonnenmarkt"],
              [(categories["Groceries"], f"-{28 + (index % 4) * 3}.60", "Street market")])
        spend(day(26, 9), accounts['cash'], peers["Stadtlinie Transit"],
              [(categories["Transport"], '-40.00', "Monthly transport pass")])
        if index % 3 == 0:
            spend(day(17, 11), accounts['cash'], peers["Apotheke am Markt"],
                  [(categories["Health"], '-32.80', '')])
        if index % 4 == 2:
            card(day(24, 20), peers["Café Kastanie"],
                 [(categories["Leisure"], '-46.00', "Weekend trip"), (categories["Transport"], '-31.20', '')])
    # The split operation the manual points at as an example gets a tag on one of its lines
    JalDB._exec("UPDATE action_details SET tag_id=:tag WHERE note='Weekend trip'",
                [(":tag", tags["Holiday"])], commit=True)


def create_investments(accounts: dict, assets: dict, peers: dict) -> None:
    broker = accounts['broker']
    transfer(ts("2025-01-13 10:00"), accounts['bank'], '5000.00', broker, '5219.21',
             note="Funding of the trading account")
    trade(ts("2025-01-20 15:30"), broker, assets['acme'], '25', '117.60', '2.50', number="T-100241")
    trade(ts("2025-02-10 16:05"), broker, assets['wldx'], '20', '92.85', '2.50', number="T-100388")
    payment(ts("2025-04-11"), AssetPayment.Dividend, broker, assets['acme'], '18.00', '2.70',
            note="ACME quarterly dividend", number="D-4417")
    payment(ts("2025-10-10"), AssetPayment.Dividend, broker, assets['acme'], '18.40', '2.76',
            note="ACME quarterly dividend", number="D-5109")
    transfer(ts("2025-11-04 10:00"), accounts['bank'], '2500.00', broker, '2723.31',
             note="Funding of the trading account")
    trade(ts("2025-11-06 15:10"), broker, assets['wldx'], '10', '101.40', '2.50', number="T-104417")
    trade(ts("2025-11-20 14:40"), broker, assets['mrail'], '2', '983.50', '1.20', number="T-104980")
    payment(ts("2026-01-15"), AssetPayment.BondInterest, broker, assets['mrail'], '44.00', '6.60',
            note="MRAIL31 coupon", number="C-3184")
    trade(ts("2026-03-05 16:20"), broker, assets['acme'], '-10', '138.90', '2.50', number="T-108845")
    payment(ts("2026-04-10"), AssetPayment.Dividend, broker, assets['acme'], '13.75', '2.06',
            note="ACME quarterly dividend", number="D-6023")
    transfer(ts("2026-05-12 10:00"), accounts['bank'], '3000.00', broker, '3342.25',
             note="Funding of the trading account")
    trade(ts("2026-06-16 15:55"), broker, assets['btc'], '0.05', '61400.00', '30.70', number="T-112097")
    payment(ts("2026-07-15"), AssetPayment.BondInterest, broker, assets['mrail'], '44.00', '6.60',
            note="MRAIL31 coupon", number="C-4021")
    trade(ts("2026-07-21 15:05"), broker, assets['wldx'], '-10', '106.20', '2.50', number="T-113640")
    trade(ts("2026-08-11 17:40"), broker, assets['btc'], '-0.02', '65800.00', '6.58', number="T-114882")


# Every account is marked reconciled up to a recent date, the way a user who checks their statements keeps them -
# except the trading account, left behind on purpose so that the manual can show what an unreconciled balance
# looks like in the balances panel.
def reconcile_accounts(accounts: dict) -> None:
    JalAccount(accounts['bank']).reconcile(ts("2026-08-22 12:00"))
    JalAccount(accounts['card']).reconcile(ts("2026-08-25 12:00"))
    JalAccount(accounts['cash']).reconcile(ts("2026-08-26 12:00"))
    JalAccount(accounts['broker']).reconcile(ts("2026-03-31 12:00"))
    JalAccount(accounts['cex']).reconcile(ts("2026-08-20 12:00"))
    JalAccount(accounts['wallet']).reconcile(ts("2026-08-20 12:00"))


def asset_transfer(timestamp: int, from_account: int, to_account: int, asset_id: int, qty,
                   to_timestamp: int = None, note: str = '') -> None:
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': Decimal(str(qty)),
            'deposit_timestamp': to_timestamp if to_timestamp else timestamp, 'deposit_account': to_account,
            'deposit': Decimal(str(qty)), 'symbol_id': sid(asset_id, USD), 'note': note}
    if to_account is None:
        data['deposit_account'] = None
    LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


def create_crypto(accounts: dict, assets: dict) -> None:
    cex, wallet = accounts['cex'], accounts['wallet']
    transfer(ts("2025-09-08 11:00"), accounts['bank'], '1000.00', cex, '1082.20',
             note="Funding of the exchange account")
    LedgerTransaction.create_new(LedgerTransaction.Trade,
                                 {'timestamp': ts("2025-09-09 12:20"), 'settlement': ts("2025-09-09 12:20"),
                                  'account_id': cex, 'symbol_id': sid(assets['eth'], USD), 'qty': Decimal('0.4'),
                                  'price': Decimal('2670.00'), 'fee': Decimal('5.34'), 'number': "VX-880314"})
    asset_transfer(ts("2025-10-02 19:15"), cex, wallet, assets['eth'], '0.4',
                   note="Withdrawal from the exchange to the wallet")
    LedgerTransaction.create_new(LedgerTransaction.Swap,
                                 {'timestamp': ts("2026-02-14 16:40"), 'account_id': wallet,
                                  'tx_hash': "0x9d41c7ab5e2f08b3c6d95174ae0b23f8c1470de6",
                                  'out_symbol_id': sid(assets['eth'], USD), 'out_qty': Decimal('0.15'),
                                  'in_symbol_id': sid(assets['usdc'], USD), 'in_qty': Decimal('468.75'),
                                  'fee_symbol_id': sid(assets['eth'], USD), 'fee_qty': Decimal('0.0021'),
                                  'note': "Swapped on a decentralized exchange"})
    payment(ts("2026-05-06"), AssetPayment.GasFee, wallet, assets['eth'], '0.0008',
            note="Token approval")
    # A withdrawal whose far end is not known yet - what the Unsettled transfers report is worked through
    asset_transfer(ts("2026-08-18 21:05"), wallet, None, assets['eth'], '0.05',
                   note="Sent out, destination not recorded yet")


def create_deposit(accounts: dict, peers: dict) -> None:
    from jal.widgets.deposit_dialogs import move_money, record_interest
    box = JalDepositBox.create("Isarbank 12M Savings", EUR, peers["Isarbank"],
                               end_date=ts("2027-02-01"), rate=Decimal('3.1'))
    move_money(accounts['bank'], box.id(), Decimal('4000.00'), ts("2026-02-02"))
    record_interest(box, ts("2026-05-02"), Decimal('31.00'), Decimal('8.68'))
    record_interest(box, ts("2026-08-02"), Decimal('31.00'), Decimal('8.68'))
    box.account().reconcile(ts("2026-08-02 12:00"))


def main() -> None:
    rebuild_database()
    rename_currencies()
    set_residence()
    peers = create_peers()
    categories = create_categories()
    tags = create_tags()
    accounts = create_accounts(peers)
    assets = create_assets()
    create_quotes(assets)
    create_household_operations(accounts, peers, categories, tags)
    create_investments(accounts, assets, peers)
    create_crypto(accounts, assets)
    create_deposit(accounts, peers)
    reconcile_accounts(accounts)
    JalSettings().setValue('WindowGeometry', '')
    ledger = Ledger()
    ledger.rebuild(from_timestamp=0)
    print("Demo database written to", assert_demo_database())


if __name__ == "__main__":
    main()
