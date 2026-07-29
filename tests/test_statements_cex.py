from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_quotes, symbol_id_for
from constants import AssetLocation, PredefinedAccountType, PredefinedAsset, PredefinedCategory
from jal.data_import.statement import JSF, Statement, Statement_ImportError
from jal.data_import.broker_statements.kucoin import StatementKuCoin
from jal.data_import.broker_statements.bitget import StatementBitget
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import AssetPayment, LedgerTransaction, Trade
from jal.db.symbol import JalSymbol
from jal.net.downloader import llama_coin_key


# The fixtures are synthetic - no figure in them belongs to a real account - but they are built to the shape of a
# real export: the same file set (18 files for KuCoin, 40 for Bitget), the same encodings and the same traps in the
# names. Every expected value below is computed by hand from the fixture in tests/test_data; the parsers additionally
# check themselves against the balances the fixtures report, so a wrong reading fails the load rather than a compare.


def _one(records, **match):
    found = [x for x in records if all(x.get(k) == v for k, v in match.items())]
    assert len(found) == 1, f"expected exactly one record matching {match}, got {found}"
    return found[0]


def _table_count(table: str) -> int:
    return int(JalDB._read(f"SELECT COUNT(*) FROM {table}"))


def _one_payment(payments, subtype):
    found = [x for x in payments if x.subtype() == subtype]
    assert len(found) == 1
    return found[0]


def _symbol_named(statement, ticker: str) -> int:
    for asset in statement._data[JSF.ASSETS]:
        for symbol in asset[JSF.SYMBOLS]:
            if symbol['symbol'] == ticker:
                return symbol['id']
    raise AssertionError(f"no symbol '{ticker}' in the statement")


# ----------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def kucoin(data_path):
    statement = StatementKuCoin()
    statement.load(data_path + 'kucoin.zip')
    return statement


@pytest.fixture
def bitget(data_path):
    statement = StatementBitget()
    statement.load(data_path + 'bitget.zip')
    return statement


# ----------------------------------------------------------------------------------------------------------------------
def test_kucoin_account_and_assets(kucoin):
    account = kucoin._data[JSF.ACCOUNTS][0]
    assert account['number'] == '100000001'
    assert account['account_type'] == PredefinedAccountType.CEX
    # EUR is the only fiat in the ledger, so it denominates the account and every coin is an asset held on it
    assert kucoin._data[JSF.ASSETS][0]['type'] == JSF.ASSET_MONEY
    assert kucoin._data[JSF.ASSETS][0][JSF.SYMBOLS][0]['symbol'] == 'EUR'
    coins = {s['symbol']: s for a in kucoin._data[JSF.ASSETS] if a['type'] == JSF.ASSET_CRYPTO
             for s in a[JSF.SYMBOLS]}
    assert sorted(coins) == ['ADA', 'USDT']
    for symbol in coins.values():
        assert symbol['location'] == AssetLocation.CEX_EXCHANGE
    # closing EUR: 999 in, 900.9 spent buying USDT, 189.81 received selling it
    assert account['cash_end'] == Decimal('287.91')


def test_kucoin_trades(kucoin):
    trades = kucoin._data[JSF.TRADES]
    assert len(trades) == 2
    buy = _one(trades, number='ORD-1')
    assert (buy['quantity'], buy['price'], buy['fee']) == (Decimal('1000'), Decimal('0.9'), Decimal('0.9'))
    # the sell side, which the real export has no example of: quantity turns negative, the fee stays positive
    sell = _one(trades, number='ORD-2')
    assert (sell['quantity'], sell['price'], sell['fee']) == (Decimal('-200'), Decimal('0.95'), Decimal('0.19'))


def test_kucoin_coin_for_coin_fill_is_a_swap_with_the_refund_folded_into_its_fee(kucoin):
    swaps = kucoin._data[JSF.SWAPS]
    assert len(swaps) == 1
    swap = swaps[0]
    assert swap['out_symbol'] == _symbol_named(kucoin, 'USDT')
    assert swap['in_symbol'] == _symbol_named(kucoin, 'ADA')
    assert (swap['out_qty'], swap['in_qty']) == (Decimal('200'), Decimal('500'))
    # the fill was charged 0.2 USDT and 0.04 of it came back as a 'Deduction Coupon Refund' one second later,
    # which is not an operation of its own - it simply means the trade cost less
    assert swap['fee_symbol'] == _symbol_named(kucoin, 'USDT')
    assert swap['fee_qty'] == Decimal('0.16')
    # and the refund must not also appear as income
    assert not [x for x in kucoin._data[JSF.ASSET_PAYMENTS] if 'Coupon' in x['description']]


def test_kucoin_transfers(kucoin):
    transfers = kucoin._data[JSF.TRANSFERS]
    assert len(transfers) == 3
    # a fiat deposit stores the gross the bank sent plus the fee taken out of it, so the balance moves by the net 999
    fiat = _one(transfers, number='FIAT-1')
    assert (fiat['withdrawal'], fiat['deposit'], fiat['fee']) == (Decimal('1000'), Decimal('1000'), Decimal('1'))
    assert fiat['account'] == [0, 1, 1]          # the far end is a bank JAL doesn't know
    assert 'counterparty_address' not in fiat
    # a withdrawal stores what actually travelled (the ledger debit less the fee), which is what the receiving
    # wallet will report - storing the debit would leave a permanent 0.5 discrepancy when the two legs are paired
    withdrawal = _one(transfers, number='0x' + 'b2' * 32)
    assert withdrawal['withdrawal'] == Decimal('100')
    assert withdrawal['fee'] == Decimal('0.5')
    assert withdrawal['fee_symbol'] == _symbol_named(kucoin, 'USDT')
    assert withdrawal['counterparty_address'] == '0x' + '22' * 20
    # a deposit names no counterparty: the address KuCoin prints is its own, and the sender is never disclosed
    deposit = _one(transfers, number='0x' + 'a1' * 32)
    assert deposit['withdrawal'] == Decimal('50')
    assert 'counterparty_address' not in deposit


def test_kucoin_payments_keep_the_source_operation_name(kucoin):
    payments = kucoin._data[JSF.ASSET_PAYMENTS]
    assert len(payments) == 3
    earning = _one(payments, amount=Decimal('0.5'))
    assert earning['type'] == JSF.PAYMENT_STAKING_REWARD
    # neither a referral bonus nor a platform grant is staking income - both are paid for something other than
    # holding coins - so both take the payment type that exists to keep promo income apart from staking yield
    referral = _one(payments, amount=Decimal('2'))
    assert referral['type'] == JSF.PAYMENT_REWARD
    platform = _one(payments, amount=Decimal('10'))
    assert platform['type'] == JSF.PAYMENT_REWARD
    # whichever type a payout lands on, the operation KuCoin called it stays readable
    assert 'PLATFORM_REWARD_WITHDRAW' in platform['description']
    assert 'Referral Bonus' in referral['description']


def test_kucoin_internal_moves_are_not_operations(kucoin):
    # 'Transfer' rows shuffle coins between the Main and HF Trading buckets and 'KuCoin Earn Locked' moves them into
    # an Earn product. All are internal to the one account they are imported into, so none becomes an operation.
    for section in (JSF.TRANSFERS, JSF.SWAPS, JSF.TRADES, JSF.ASSET_PAYMENTS):
        assert not [x for x in kucoin._data[section] if 'Transfer' in str(x.get('description', ''))]
        assert not [x for x in kucoin._data[section] if 'Earn Locked' in str(x.get('description', ''))]


def test_kucoin_period_covers_operations_past_the_last_snapshot(kucoin):
    start, end = kucoin.period()
    first = min(x['timestamp'] for x in kucoin._data[JSF.TRANSFERS])
    last = max(x['timestamp'] for x in kucoin._data[JSF.ASSET_PAYMENTS])
    assert start <= first and end >= last


def test_kucoin_refuses_an_unknown_operation(kucoin, data_path):
    # A row type the parser doesn't know must stop the import: skipping it would leave the balances quietly wrong,
    # which is precisely what the statement's own snapshots exist to catch.
    statement = StatementKuCoin()
    statement._files = dict(kucoin._files)
    statement._files['funding'] = kucoin._files['funding'] + [
        {'UID': '100000001', 'Account Type': 'mainAccount', 'Currency': 'USDT', 'Side': 'Deposit',
         'Amount': '1', 'Fee': '0', 'Time(UTC)': '2025-01-14 10:00:00', 'Remark': '', 'Type': 'Margin Interest'}]
    statement._data = {JSF.PERIOD: [None, None], JSF.ACCOUNTS: [], JSF.ASSETS: [], JSF.TRADES: [],
                       JSF.TRANSFERS: [], JSF.SWAPS: [], JSF.ASSET_PAYMENTS: []}
    with pytest.raises(Statement_ImportError, match="Unsupported KuCoin operation"):
        statement._load_statement()


# ----------------------------------------------------------------------------------------------------------------------
# An exchange that splits an order reports every fill of it under the SAME order number, in the same second and -
# when the order walked one price level - at the same price and the same size. Those fills are separate movements of
# the coin, and the generic duplicate check of create_operation() used to ask whether an identical row exists
# ANYWHERE, so it kept the first fill of such an order and dropped the rest. The position was then short by
# everything it dropped, and the first withdrawal that spent the coins failed for lack of an amount that was really
# there. Bounded to what the database held BEFORE the import started, the check can't see the fills this import has
# just written.

# One fill of an order that KuCoin split - the figures are those of the order that exposed this, which walked a
# single price level and so reports 15 fills that differ in nothing a trade stores.
def _fill(oid: int) -> dict:
    return {"id": oid, "number": 'ORD-SPLIT', "timestamp": d2t(250115), "settlement": d2t(250115),
            "account": 1, "symbol": 1, "quantity": Decimal('0.3101'), "price": Decimal('0.862'),
            "fee": Decimal('0.0002673062')}


@pytest.fixture
def split_order(prepare_db):
    JalAccountCreator(currency_id=3, number='', name='KuCoin.1', investing=1, organization=1,
                      account_type=PredefinedAccountType.CEX).commit()
    create_assets([('USDT', 'Tether USD', '', 3, PredefinedAsset.Crypto, 0)])     # ID = 4
    statement = Statement()
    statement.set_mapped_id(JSF.ACCOUNTS, 1, 1)
    statement.set_mapped_id(JSF.SYMBOLS, 1, symbol_id_for(4))
    yield statement


def test_every_fill_of_a_split_order_is_stored(split_order):
    split_order._import_trades([_fill(1), _fill(2), _fill(3)])

    assert _table_count('trades') == 3
    assert sum((Trade(oid).qty() for oid in range(1, 4)), Decimal('0')) == Decimal('0.9303')


def test_a_reimported_statement_still_duplicates_no_trade(split_order):
    split_order._import_trades([_fill(1), _fill(2)])
    split_order._import_trades([_fill(1), _fill(2)])

    assert _table_count('trades') == 2


# ----------------------------------------------------------------------------------------------------------------------
def test_bitget_reads_the_awkward_archive(bitget):
    # 40 entries, 36 of them header-only with no sentinel row; one entry has a '/' in its NAME (extracting the
    # archive would turn it into a directory and hide the file) and every name carries ':' from the export stamp.
    assert len(bitget._entries) == 40
    assert any('deposit/withdrawal records' in x for x in bitget._entries)
    assert all(':' in x for x in bitget._entries)
    assert len(bitget._rows('transfers')) == 1
    assert not bitget._rows('usdt_futures')
    # the ledger's ids are written TAB-prefixed so a spreadsheet won't round them - the tab is not data
    assert bitget._rows('ledger')[0]['order'] == '9000000000000000010'
    # and the fill rows carry a trailing comma, i.e. one field more than the header
    assert len(bitget._rows('fills')) == 2


def test_bitget_account_and_uid_from_file_names(bitget):
    account = bitget._data[JSF.ACCOUNTS][0]
    assert account['number'] == '200000002'      # Bitget puts the UID in file names only, never in the data
    assert account['account_type'] == PredefinedAccountType.CEX


def test_bitget_trade_fee_is_folded_into_the_side_it_was_charged_in(bitget):
    trades = bitget._data[JSF.TRADES]
    assert len(trades) == 2
    # buy: the fee was charged in the coin RECEIVED, so 199.8 of the 200 USDT arrived and 180 EUR were paid
    buy = _one(trades, number='9000000000000000001')
    assert buy['quantity'] == Decimal('199.8')
    assert buy['fee'] == Decimal('0')
    assert buy['quantity'] * buy['price'] == Decimal('180')
    # sell: the fee then lands in the quote asset instead, so the proceeds are what is reduced
    sell = _one(trades, number='9000000000000000002')
    assert sell['quantity'] == Decimal('-100')
    assert sell['fee'] == Decimal('0')
    assert sell['price'] == Decimal('93.906') / Decimal('100')


def test_bitget_withdrawal_amount_comes_from_the_ledger_not_the_transfer_file(bitget):
    # The deposit/withdrawal file reports 99.8 - the GROSS account debit - while 99.5 actually travelled and 0.3 was
    # the fee. Taking the file's figure would leave a phantom 0.3 discrepancy against the wallet on the other side.
    withdrawal = _one(bitget._data[JSF.TRANSFERS], number='0x' + 'c3' * 32)
    assert withdrawal['withdrawal'] == Decimal('99.5')
    assert withdrawal['fee'] == Decimal('0.3')
    assert Decimal(bitget._rows('transfers')[0]['Quantity']) == Decimal('99.8')   # what the file itself claims


def test_bitget_fiat_deposit_has_no_counterparty(bitget):
    # The export carries no fiat file at all, so where the money came from simply isn't recoverable - the far end
    # stays unknown rather than being guessed, and no transaction id is invented for it.
    deposit = _one(bitget._data[JSF.TRANSFERS], withdrawal=Decimal('500'))
    assert deposit['account'] == [0, 1, 1]
    assert deposit['number'] == ''
    assert deposit['fee'] == Decimal('0')


def test_bitget_rebate_is_a_reward(bitget):
    payment = _one(bitget._data[JSF.ASSET_PAYMENTS], amount=Decimal('0.05'))
    assert payment['type'] == JSF.PAYMENT_REWARD
    assert payment['description'] == 'Rebate rewards'


def test_bitget_refuses_a_ledger_that_does_not_reconcile(bitget):
    # 'Amount' excludes the fee and 'Fee' stands beside it as a negative number, so the balance moves by their sum.
    # Reading it KuCoin's way (fee already inside the amount) makes the running balance disagree at the first
    # fee-bearing row, and the parser must refuse rather than import balances it knows to be wrong.
    statement = StatementBitget()
    statement._files = {k: list(v) for k, v in bitget._files.items()}
    broken = dict(statement._files['ledger'][1])
    broken['Available'] = '200'      # as if the 0.2 fee had not moved the balance
    statement._files['ledger'][1] = broken
    with pytest.raises(Statement_ImportError, match="doesn't reproduce the balance"):
        statement._validate_ledger()


def test_bitget_refuses_an_unsupported_file_with_data(bitget):
    # An export that carries margin or futures rows holds operations this parser was never written for. Importing
    # the rest would silently drop them, so the whole statement is refused instead.
    statement = StatementBitget()
    statement._files = dict(bitget._files)
    statement._files['usdt_futures'] = [{'Date': '2025-02-02 10:00:00', 'Coin': 'USDT',
                                         'Type': 'Settlement', 'Amount': '5'}]
    with pytest.raises(Statement_ImportError, match="aren't supported yet"):
        statement._refuse_unhandled(StatementBitget.HandledFiles)


# ----------------------------------------------------------------------------------------------------------------------
def test_cex_coins_are_priced_by_recorded_coin_id(prepare_db):
    # A coin held on an exchange has no contract address to be keyed by: the balance is a claim on the exchange and
    # is fungible across every chain the coin exists on. It is priced through the CoinGecko passthrough, by the id
    # recorded for the asset - and by nothing else. A ticker is never turned into a key: it is not unique, and
    # borrowing the address of a wrapped version of the coin would name a different asset.
    currency = JalAsset(JalAsset.get_base_currency())
    for ticker, coin_id in (('USDT', 'tether'), ('ADA', 'cardano'), ('DOT', 'polkadot'), ('NEAR', 'near')):
        coin = JalAssetCreator(PredefinedAsset.Crypto, ticker, '').commit()
        symbol_id = coin.add_symbol(ticker, currency.id(), location_id=AssetLocation.CEX_EXCHANGE)
        assert llama_coin_key(JalSymbol(symbol_id)) == ''       # nothing is known about the coin yet
        coin.update_data({'coin_id': coin_id})
        assert llama_coin_key(JalSymbol(symbol_id)) == f"coingecko:{coin_id}"
    # A coin whose id was never recorded has no key at all, and the downloader reports it instead of guessing one
    unknown = JalAssetCreator(PredefinedAsset.Crypto, 'NOSUCHCOIN', '').commit()
    unknown_symbol = unknown.add_symbol('NOSUCHCOIN', currency.id(), location_id=AssetLocation.CEX_EXCHANGE)
    assert llama_coin_key(JalSymbol(unknown_symbol)) == ''


def test_kucoin_statement_imports_into_the_database(prepare_db, data_path):
    statement = StatementKuCoin()
    statement.load(data_path + 'kucoin.zip')
    statement.validate_format()
    statement.match_db_ids()
    statement.import_into_db()

    account = JalAccount(JalAccount.get_all_accounts()[0].id())
    assert account.account_type() == PredefinedAccountType.CEX      # the type survives the round trip through JSF
    assert account.number() == '100000001'
    # the coins landed as crypto assets located on the exchange, so they can be priced and merged with a chain
    # listing of the same coin later on
    usdt = JalAsset.find({'symbol': 'USDT', 'type': PredefinedAsset.Crypto})
    assert usdt.id()
    assert JalSymbol(usdt.active_symbol_ids()[0]).location() == AssetLocation.CEX_EXCHANGE
    # 2 trades + 1 swap + 3 transfers + 3 payments, and nothing at all for the internal bucket moves
    assert _table_count('trades') == 2
    assert _table_count('swaps') == 1
    assert _table_count('transfers') == 3
    payments = AssetPayment.get_list(account.id())
    assert sorted(x.subtype() for x in payments) == [AssetPayment.StakingReward, AssetPayment.Reward,
                                                     AssetPayment.Reward]
    # the Earn payout is the only staking income; the referral bonus and the platform grant both took the promo type
    assert _one_payment(payments, AssetPayment.StakingReward).amount() == Decimal('0.5')
    assert sorted(x.amount() for x in payments if x.subtype() == AssetPayment.Reward) == [Decimal('2'), Decimal('10')]


def test_reward_payment_is_valued_like_a_staking_reward(prepare_db):
    # AssetPayment.Reward exists only to keep a promo payout apart from staking income; it must be ACCOUNTED exactly
    # like a staking reward. That above all means valuing it at the last known quote - a crypto quote is daily and
    # would never fall on the second the payout arrived, so the stock-vesting path would refuse every reward.
    JalAccountCreator(currency_id=2, number='', name='KuCoin.1', investing=1, organization=1,
                      account_type=PredefinedAccountType.CEX).commit()
    create_assets([('USDT', 'Tether', '', 2, PredefinedAsset.Crypto, 0)])     # ID = 4
    create_actions([(d2t(210101), 1, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_quotes(4, 2, [(d2t(210201), '0.98')])
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment,
                                 {'timestamp': d2t(210202), 'type': AssetPayment.Reward, 'account_id': 1,
                                  'symbol_id': symbol_id_for(4), 'amount': '10', 'tax': '0', 'number': '',
                                  'note': 'PLATFORM_REWARD_WITHDRAW'})
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(1).get_asset_amount(d2t(210301), 4) == Decimal('10')   # the coins are on the account
    lots = JalAccount(1).open_trades_list(JalAsset(4))
    assert sum((lot.open_qty(adjusted=True) for lot in lots), Decimal('0')) == Decimal('10')
    # valued at the last known quote rather than at one stamped at its own second
    assert AssetPayment(1).price() == Decimal('0.98')
