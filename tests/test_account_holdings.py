import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QTreeView

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_actions, create_assets, create_quotes, create_trades, symbol_id_for
from jal.constants import PredefinedAsset, PredefinedAccountType, AccountStatus, AccountData, AssetData, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.chain_balance import JalChainBalance
from jal.db.db import JalDB
from jal.db.holdings_model import HoldingsModel
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.receivable import JalReceivable
from jal.db.staking import JalStakingBox
from jal.db.transfer_settlement import TransferSettlement

EUR = 1
USD = 2
LINK = 4
ARB = 5
WALLET = 1
POOL = '0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea'
DISTRIBUTOR = '0x7060fe0dd3e31be01efac6b28c8d38018fd163b0'
DATE = QDate(2021, 3, 1)
NOW = d2t(210301)


# A USD wallet that bought 100 LINK at 10, so it holds 100 LINK and owes 1,000 in money. LINK is quoted at 12 and a
# dollar at half a euro, so every figure below can be worked out by hand.
@pytest.fixture
def wallet(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='ETH wallet', investing=1, organization=1, precision=18,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '2' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_assets([('LINK', 'ChainLink Token', '', USD, PredefinedAsset.Crypto, 0),
                   ('ARB', 'Arbitrum', '', USD, PredefinedAsset.Crypto, 0)])
    create_quotes(LINK, USD, [(d2t(210101), Decimal('12'))])
    create_quotes(ARB, USD, [(d2t(210101), Decimal('0.5'))])
    create_quotes(USD, EUR, [(d2t(210101), Decimal('0.5'))])
    create_trades(WALLET, [(d2t(210101), d2t(210101), LINK, Decimal('100'), Decimal('10'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    yield


# Moves 60 LINK from the wallet into a new staking box
def _stake() -> JalStakingBox:
    box = JalStakingBox.create(JalAccount(WALLET), "LINK pool", protocol='stake.link',
                               chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)
    LedgerTransaction.create_new(LedgerTransaction.Transfer, {
        'withdrawal_timestamp': d2t(210201), 'withdrawal_account': WALLET, 'withdrawal': '60',
        'deposit_timestamp': d2t(210201), 'deposit_account': None, 'deposit': '0', 'number': '0x' + 'b' * 64,
        'note': '', 'counterparty_address': POOL, 'symbol_id': symbol_id_for(LINK)})
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)
    JalAccount(WALLET).invalidate_cache()
    return box


def _claim(amount='4'):
    JalReceivable().store(NOW, WALLET, ARB, DISTRIBUTOR, Decimal(amount))
    JalAccount(WALLET).invalidate_cache()


# ----------------------------------------------------------------------------------------------------------------------
# What the Asset Portfolio report shows, pinned before its model was split so the account view could share it
def _portfolio(grouping='') -> HoldingsModel:
    model = HoldingsModel(QTreeView())
    model.updateView(currency_id=EUR, date=DATE, grouping=grouping, min_status=AccountStatus.Active)
    return model


def _children(item) -> list:
    return [item.getChild(i) for i in range(item.childrenCount())]


def test_portfolio_lists_a_position_and_money_in_every_field_it_shows(wallet):
    position, money = [x.details() for x in _children(_portfolio()._root)]
    assert position['header'] == 'USD: ETH wallet: LINK'
    assert position['asset_name'] == 'ChainLink Token'
    assert position['qty'] == Decimal('100')
    assert position['since'] == d2t(210101)
    assert position['open_quote'] == Decimal('10')
    assert position['quote'] == Decimal('12')
    assert position['value'] == Decimal('1200')
    assert position['value_common'] == Decimal('600')
    assert position['p/l'] == Decimal('200')
    assert position['p/l%'] == Decimal('20')
    assert money['header'] == 'USD: ETH wallet: USD'
    assert money['qty'] == Decimal('-1000')
    assert money['open_quote'] is None
    assert money['value'] == Decimal('-1000')
    assert money['value_common'] == Decimal('-500')
    assert money['p/l'] == Decimal('0')


def test_portfolio_groups_keep_their_totals_and_header(wallet):
    group = _children(_portfolio("currency_id;account_id")._root)[0]
    assert group.details()['header'] == 'USD'
    assert group.details()['value'] == Decimal('200')
    account = _children(group)[0]
    assert account.details()['header'] == 'ETH wallet'
    assert account.details()['value_common'] == Decimal('100')
    assert [x.details()['header'] for x in _children(account)] == ['LINK', 'USD']


def test_portfolio_keeps_all_its_columns(wallet):
    assert [x['field'] for x in _portfolio()._columns] == ['header', 'asset_name', 'qty', 'since', 'open_quote', 'quote',
                                                           'share', 'p/l%', 'p/l', 'paid', 'value', 'value_common']


# ----------------------------------------------------------------------------------------------------------------------
# The account view
def _account_view(account_id=WALLET, date=DATE):
    from jal.db.holdings_model import AccountHoldingsModel
    model = AccountHoldingsModel(QTreeView())
    model.showAccount(account_id, EUR, date)
    return model


def _rows(model) -> list:
    return [(x.details()['header'], x.details()['value']) for x in _children(model._root)]


def _total(model, name) -> tuple:
    row = [x.details() for x in _children(model._root) if x.details()['header'] == name][0]
    return row['value'], row['value_common']


ON_ACCOUNT = "On this account (equals Balance)"
INCLUDING = "Including staked"


def test_position_and_money_add_up_to_the_balance(wallet):
    model = _account_view()
    # 100 LINK at 12 less the 1,000 paid for them
    assert _total(model, ON_ACCOUNT) == (Decimal('200'), Decimal('100'))
    assert JalAccount(WALLET).balance(NOW + 86399) == Decimal('200')
    assert [x.details()['header'] for x in _children(model._root)] == ['LINK', 'USD', ON_ACCOUNT]


def test_an_accrual_and_a_claim_count_in_the_total_as_they_do_in_the_balance(wallet):
    JalChainBalance().store(NOW, WALLET, LINK, Decimal('100.5'))
    _claim('4')
    model = _account_view()
    # 100.5 LINK at 12 = 1,206, less 1,000, plus 4 ARB at 0.5 = 2
    assert _total(model, ON_ACCOUNT) == (Decimal('208'), Decimal('104'))
    assert JalAccount(WALLET).balance(NOW + 86399) == Decimal('208')
    assert [x.details()['header'] for x in _children(model._root)] == [
        'LINK', 'USD', "Claimable (earned, not yet paid)", ON_ACCOUNT]
    group = _children(model._root)[2]
    claim = _children(group)[0].details()
    assert (claim['header'], claim['qty'], claim['value']) == ('ARB', Decimal('4'), Decimal('2'))
    assert claim['mark'] == 'FluidMerkleDistributor'


def test_a_stake_stays_out_of_the_balance_total_and_gets_a_total_of_its_own(wallet):
    box = _stake()
    JalChainBalance().store(NOW, box.id(), LINK, Decimal('60.5'))
    model = _account_view()
    # 40 LINK left at 12 = 480, less 1,000 = -520. The stake is 60.5 LINK at 12 = 726, which makes 206.
    assert _total(model, ON_ACCOUNT) == (Decimal('-520'), Decimal('-260'))
    assert JalAccount(WALLET).balance(NOW + 86399) == Decimal('-520')
    assert _total(model, INCLUDING) == (Decimal('206'), Decimal('103'))
    headers = [x.details()['header'] for x in _children(model._root)]
    assert headers == ['LINK', 'USD', ON_ACCOUNT, "Staked from this account (separate accounts, not in Balance)", INCLUDING]
    staked = _children(_children(model._root)[3])[0].details()
    assert (staked['account_id'], staked['qty'], staked['value']) == (box.id(), Decimal('60.5'), Decimal('726'))
    assert staked['asset_name'] == 'LINK pool · stake.link'
    assert staked['since'] == d2t(210201)
    assert model.hasPositions()


def test_a_box_lists_its_own_holding_and_names_the_wallet(wallet):
    box = _stake()
    model = _account_view(box.id())
    assert model.stakedFrom() == ['ETH wallet']
    assert _total(model, ON_ACCOUNT) == (Decimal('720'), Decimal('360'))
    assert JalAccount(box.id()).balance(NOW + 86399) == Decimal('720')
    position = _children(model._root)[0].details()
    assert (position['qty'], position['open_quote'], position['p/l']) == (Decimal('60'), Decimal('10'), Decimal('120'))


def test_only_the_wallet_a_box_was_filled_from_lists_it(wallet):
    other = JalAccountCreator(currency_id=USD, number='', name='Other wallet', investing=1, organization=1, precision=18,
                              account_type=PredefinedAccountType.Wallet, address='0x' + '3' * 40,
                              chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_trades(other.id(), [(d2t(210102), d2t(210102), LINK, Decimal('1'), Decimal('10'), Decimal('0'))])
    _stake()
    model = _account_view(other.id())
    assert INCLUDING not in [x.details()['header'] for x in _children(model._root)]
    assert model.stakedFrom() == []


def test_money_alone_is_not_a_position_list(wallet):
    create_trades(WALLET, [(d2t(210102), d2t(210102), LINK, Decimal('-100'), Decimal('12'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    JalAccount(WALLET).invalidate_cache()
    model = _account_view()
    assert not model.hasPositions()
    assert _rows(model) == [('USD', Decimal('200')), (ON_ACCOUNT, Decimal('200'))]


def test_a_claim_alone_is_a_position_list(wallet):
    create_trades(WALLET, [(d2t(210102), d2t(210102), LINK, Decimal('-100'), Decimal('12'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    _claim('4')
    assert _account_view().hasPositions()


def test_no_account_shows_nothing(wallet):
    model = _account_view(0)
    assert model._root.childrenCount() == 0
    assert not model.hasPositions()


def test_nothing_newer_than_the_date_is_listed(wallet):
    box = _stake()
    _claim('4')
    JalChainBalance().store(NOW, box.id(), LINK, Decimal('60.5'))
    model = _account_view(date=QDate(2021, 1, 15))
    assert [x.details()['header'] for x in _children(model._root)] == ['LINK', 'USD', ON_ACCOUNT]
    assert _total(model, ON_ACCOUNT)[0] == Decimal('200')


# An account that isn't an investing one, holding only money, with a credit limit that Balances adds for display only
def test_a_bank_account_shows_its_money_without_the_credit_limit(wallet):
    bank = JalAccountCreator(currency_id=USD, number='', name='Bank', investing=0, organization=1,
                             account_type=PredefinedAccountType.Bank).commit()
    bank.set_data(AccountData.Credit, '500')
    create_actions([(d2t(210102), bank.id(), 1, [(5, Decimal('250'))])])
    Ledger().rebuild(from_timestamp=0)
    JalAccount(bank.id()).invalidate_cache()
    model = _account_view(bank.id())
    assert _rows(model) == [('USD', Decimal('250')), (ON_ACCOUNT, Decimal('250'))]
    assert not model.hasPositions()


def test_a_wrapped_token_is_a_position_with_its_protocol_marked(wallet):
    JalDB()._exec("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) VALUES(:a, :dt, :v)",
                  [(":a", LINK), (":dt", AssetData.Protocol), (":v", 'Aave v3')], commit=True)
    JalAsset(LINK).invalidate_cache()
    position = _children(_account_view()._root)[0].details()
    assert (position['kind'], position['mark']) == ('held', 'Aave v3')


def test_a_position_alone_shows_a_profit(wallet):
    box = _stake()
    _claim('4')
    model = _account_view()
    pl = model.fieldIndex('p/l')
    root = model.index(0, pl)
    assert model.data(root) == Decimal('80')   # 40 LINK bought at 10, now at 12
    labels = [x['field'] for x in model._columns]
    assert labels == ['header', 'asset_name', 'qty', 'since', 'open_quote', 'quote', 'p/l%', 'p/l', 'value', 'value_common']
    for row in range(1, model._root.childrenCount()):   # money, the claim heading, the totals, the stake heading
        assert model.data(model.index(row, pl)) is None
    claims = model.index(2, 0)
    assert model.data(model.index(0, pl, claims)) is None
    assert model.data(model.index(0, model.fieldIndex('value'), claims)) == Decimal('2')
    assert model.data(model.index(2, model.fieldIndex('value'))) is None   # a heading shows no subtotal
    assert model.data(claims) == "Claimable (earned, not yet paid)"
