from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedAccountType, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.chain_balance import JalChainBalance
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.settings import JalSettings
from jal.db.db import JalDB
from jal.db.staking import JalStakingBox
from jal.db.symbol import JalSymbol
from jal.net.chain_balances import ChainBalanceReader

HYPE = 4                       # the asset created by the fixture below
WALLET = 1
USD = 2
HL_ADDRESS = '0x' + 'c' * 40
NOW = d2t(260805)


# A Hyperliquid wallet holding HYPE, so a staking box has a real position to be filled from
@pytest.fixture
def hl_wallet(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='Hyperliquid', investing=1, organization=1, precision=18,
                      account_type=PredefinedAccountType.Wallet, address=HL_ADDRESS,
                      chain=AssetLocation.HL_BLOCKCHAIN).commit()
    create_assets([('HYPE', 'Hyperliquid', '', USD, PredefinedAsset.Crypto, 0)])
    create_trades(WALLET, [(d2t(260101), d2t(260101), HYPE, Decimal('20'), Decimal('30'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    yield


# Fills a box from a wallet - the transfer that both moves the coins and, since no column names it, RECORDS which
# wallet the box belongs to. That is what the readers resolve an address-less venue box through.
def _stake(from_account, box_id, amount, timestamp=d2t(260201)) -> int:
    oid = LedgerTransaction.create_new(LedgerTransaction.Transfer, {
        'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
        'deposit_timestamp': timestamp, 'deposit_account': box_id, 'deposit': str(amount),
        'number': '', 'note': '', 'symbol_id': symbol_id_for(HYPE)}).oid()
    Ledger().rebuild(from_timestamp=0)
    return oid


def _new_box(name) -> JalStakingBox:
    # Address-less on purpose: a venue's internal staking balance names nothing on a chain, which is exactly the case
    # that forces the wallet to be resolved through the transfers rather than looked up by address.
    return JalStakingBox.create(JalAccount(WALLET), name, protocol='Hyperliquid',
                                chain=AssetLocation.HL_BLOCKCHAIN, address='')


# Replaces the venue call, so no test here touches the network. The recorded answer is the real shape the account
# returned on 2026-08-04, with the whole position sitting in the withdrawal queue.
def _fake_venue(monkeypatch, answer):
    asked = []

    def fake_post(self, url, request):
        asked.append(request)
        return answer
    monkeypatch.setattr(ChainBalanceReader, "_post", fake_post)
    return asked


_SUMMARY_QUEUED = {'delegated': '0.0', 'undelegated': '0.0',
                   'totalPendingWithdrawal': '11.99462482', 'nPendingWithdrawals': 2}
_SUMMARY_DELEGATED = {'delegated': '11.99388771', 'undelegated': '0.0', 'totalPendingWithdrawal': '0.0'}


# ----------------------------------------------------------------------------------------------------------------------
# The balance of a Hyperliquid box is the SUM of three fields, and this is the case that makes it matter: the whole
# position has been undelegated and put into the ~7-day withdrawal queue, so 'delegated' is zero while the coins are
# still in the box and JAL's ledger still holds them. A reader watching 'delegated' would show the box at nothing.
# Both readings below are real ones taken from the validation account.
def test_a_queued_position_is_still_in_the_box(hl_wallet, monkeypatch):
    box = _new_box("Hyperliquid staking")
    _stake(WALLET, box.id(), Decimal('11.92275902'))
    _fake_venue(monkeypatch, _SUMMARY_QUEUED)

    assert ChainBalanceReader().read_staking_boxes(NOW) == 1
    assert JalChainBalance().latest(box.id(), HYPE, NOW)['amount'] == Decimal('11.99462482')


def test_a_delegated_position_is_read_the_same_way(hl_wallet, monkeypatch):
    box = _new_box("Hyperliquid staking")
    _stake(WALLET, box.id(), Decimal('11.92275902'))
    _fake_venue(monkeypatch, _SUMMARY_DELEGATED)

    ChainBalanceReader().read_staking_boxes(NOW)
    assert JalChainBalance().latest(box.id(), HYPE, NOW)['amount'] == Decimal('11.99388771')


# The accrual this whole feature exists to show: the chain holds more than the ledger ever booked, because the venue
# compounded the rewards into the delegation without emitting anything a fetcher could import.
def test_the_snapshot_exceeds_the_ledger_by_the_accrual(hl_wallet, monkeypatch):
    box = _new_box("Hyperliquid staking")
    _stake(WALLET, box.id(), Decimal('11.92275902'))
    _fake_venue(monkeypatch, _SUMMARY_QUEUED)
    ChainBalanceReader().read_staking_boxes(NOW)

    ledger = box.holdings(NOW)[0]['amount']
    assert JalChainBalance().latest(box.id(), HYPE, NOW)['amount'] - ledger == Decimal('0.07186580')


# The venue reports ONE figure for the whole account, so it may only be attributed to a box that is alone in owning
# it. Nothing stops a second box being made for the same wallet - the new-box dialog rejects only a duplicate
# address, and a venue box has none - and then the account total would be written into both, each measured against
# its own partial ledger, multiplying the displayed accrual. The reader refuses instead of splitting what it cannot.
def test_an_account_total_is_refused_when_the_wallet_has_two_boxes(hl_wallet, monkeypatch):
    first = _new_box("Hyperliquid staking")
    second = _new_box("Hyperliquid staking #2")
    _stake(WALLET, first.id(), Decimal('6'))
    _stake(WALLET, second.id(), Decimal('5.92275902'))
    _fake_venue(monkeypatch, _SUMMARY_QUEUED)

    assert ChainBalanceReader().read_staking_boxes(NOW) == 0
    assert JalChainBalance().latest(first.id(), HYPE, NOW) is None
    assert JalChainBalance().latest(second.id(), HYPE, NOW) is None


# ...but a second box that has been EMPTIED is not a conflict: a box is emptied by unstaking and re-used by staking
# again, so an old one lying around must not stop the live one from being measured.
def test_an_emptied_sibling_box_does_not_block_the_reading(hl_wallet, monkeypatch):
    old = _new_box("Hyperliquid staking")
    live = _new_box("Hyperliquid staking #2")
    _stake(WALLET, old.id(), Decimal('3'))
    _stake(old.id(), WALLET, Decimal('3'), timestamp=d2t(260202))     # unstaked again, the box is empty
    _stake(WALLET, live.id(), Decimal('11.92275902'), timestamp=d2t(260203))
    _fake_venue(monkeypatch, _SUMMARY_QUEUED)

    assert ChainBalanceReader().read_staking_boxes(NOW) == 1
    assert JalChainBalance().latest(live.id(), HYPE, NOW)['amount'] == Decimal('11.99462482')


# A venue changing the shape of its answer must not be read as the position having shrunk. A missing field is not a
# zero - defaulting it would quietly report a smaller balance, which the reconciliation rule would then take for a
# missed withdrawal.
@pytest.mark.parametrize("answer", [
    {'delegated': '11.0', 'undelegated': '0.0'},                    # no 'totalPendingWithdrawal'
    {'delegated': '11.0', 'undelegated': '0.0', 'totalPendingWithdrawal': 'n/a'},
    [],                                                             # not a dict at all
])
def test_an_unreadable_answer_stores_nothing(hl_wallet, monkeypatch, answer):
    box = _new_box("Hyperliquid staking")
    _stake(WALLET, box.id(), Decimal('11.92275902'))
    _fake_venue(monkeypatch, answer)

    assert ChainBalanceReader().read_staking_boxes(NOW) == 0
    assert JalChainBalance().latest(box.id(), HYPE, NOW) is None


# Venue knowledge lives in the readers, not in the table: a box on a chain that has no reader is passed over in
# silence. Tron's frozen TRX pays its rewards through an explicit claim and a CEX box has no API at all, so neither
# of them should ever get a row - an absent venue is a decision, not a gap.
def test_a_box_of_an_unread_venue_is_skipped(hl_wallet, monkeypatch):
    box = JalStakingBox.create(JalAccount(WALLET), "Tron staking", protocol='Tron',
                               chain=AssetLocation.TRX_BLOCKCHAIN, address='')
    _stake(WALLET, box.id(), Decimal('11.92275902'))
    asked = _fake_venue(monkeypatch, _SUMMARY_QUEUED)

    assert ChainBalanceReader().read_staking_boxes(NOW) == 0
    assert asked == []          # the venue was not even contacted


# The chain checkboxes of the quote-update dialog are what selects the venues, so a chain the user did not tick is
# not asked. This is the whole reason the feature needs no UI of its own.
def test_locations_filter_selects_which_venues_are_asked(hl_wallet, monkeypatch):
    box = _new_box("Hyperliquid staking")
    _stake(WALLET, box.id(), Decimal('11.92275902'))
    asked = _fake_venue(monkeypatch, _SUMMARY_QUEUED)

    assert ChainBalanceReader().read_staking_boxes(NOW, locations=[AssetLocation.ETH_BLOCKCHAIN]) == 0
    assert asked == []
    assert ChainBalanceReader().read_staking_boxes(NOW, locations=[AssetLocation.HL_BLOCKCHAIN]) == 1


# The reader asks the venue about the WALLET, never about the box: a Hyperliquid staking balance is internal to the
# account and names no address of its own, so the address has to come from the wallet the box was filled from.
def test_the_venue_is_asked_about_the_wallet_address(hl_wallet, monkeypatch):
    box = _new_box("Hyperliquid staking")
    _stake(WALLET, box.id(), Decimal('11.92275902'))
    asked = _fake_venue(monkeypatch, _SUMMARY_QUEUED)
    ChainBalanceReader().read_staking_boxes(NOW)

    assert asked == [{"type": "delegatorSummary", "user": HL_ADDRESS}]


# ----------------------------------------------------------------------------------------------------------------------
# The store is append-only and answers "the latest reading AS OF a date". The date is not decoration: a snapshot is a
# "now" value, and letting today's reading into a report dated last January would rewrite history with a quantity
# that did not exist then.
def test_a_snapshot_is_invisible_to_a_report_dated_before_it(hl_wallet):
    storage = JalChainBalance()
    storage.store(d2t(260801), 1, HYPE, Decimal('10'))
    storage.store(d2t(260805), 1, HYPE, Decimal('11'))

    assert storage.latest(1, HYPE, d2t(260731)) is None
    assert storage.latest(1, HYPE, d2t(260803))['amount'] == Decimal('10')
    assert storage.latest(1, HYPE, d2t(260806))['amount'] == Decimal('11')


# Every reading is kept, so the series is the per-position yield history a growth chart needs - that is what the
# table being appended to rather than updated buys.
def test_the_series_is_kept_as_a_history(hl_wallet):
    storage = JalChainBalance()
    for day, amount in ((260801, '10'), (260802, '10.5'), (260803, '11')):
        storage.store(d2t(day), 1, HYPE, Decimal(amount))

    assert [x['amount'] for x in storage.history(1, HYPE)] == [Decimal('10'), Decimal('10.5'), Decimal('11')]


# Two readings of the very same second replace rather than duplicate - the second says nothing the first didn't.
def test_a_repeated_reading_of_one_second_replaces_it(hl_wallet):
    storage = JalChainBalance()
    storage.store(d2t(260801), 1, HYPE, Decimal('10'))
    storage.store(d2t(260801), 1, HYPE, Decimal('10.000001'))

    assert len(storage.history(1, HYPE)) == 1
    assert storage.history(1, HYPE)[0]['amount'] == Decimal('10.000001')


# Amounts survive as decimals to their last digit. A balance that passed through a float would come back wrong
# exactly in the range this feature measures - the accrual here is the 8th decimal.
def test_amounts_keep_every_decimal(hl_wallet):
    storage = JalChainBalance()
    storage.store(d2t(260801), 1, HYPE, Decimal('11.99462482'))

    assert storage.latest(1, HYPE, d2t(260801))['amount'] == Decimal('11.99462482')


# ----------------------------------------------------------------------------------------------------------------------
# Solana native staking - the same silent accrual as Hyperliquid's (epoch rewards are credited straight into the
# stake account, with no transaction and no event), read a completely different way because a stake account IS an
# address on the chain.
STAKE_A = 'StakeAcct1111111111111111111111111111111111'
STAKE_B = 'StakeAcct2222222222222222222222222222222222'
SOL_ADDRESS = 'SoLWaLLet2222222222222222222222222222222222'
STAKE_PROGRAM = 'Stake11111111111111111111111111111111111111'


# Ids are looked up rather than hardcoded: this fixture stacks on top of the Hyperliquid one, so both the account
# and the asset land on whatever number the previous fixture left free.
SOL_WALLET = 0
SOL = 0


@pytest.fixture
def sol_wallet(hl_wallet):
    global SOL_WALLET, SOL
    JalSettings().setValue("ApiKey_Helius", "test-key")
    SOL_WALLET = JalAccountCreator(currency_id=USD, number='', name='Solana wallet', investing=1, organization=1,
                                   precision=9, account_type=PredefinedAccountType.Wallet, address=SOL_ADDRESS,
                                   chain=AssetLocation.SOL_BLOCKCHAIN).commit().id()
    create_assets([('SOL', 'Solana', '', USD, PredefinedAsset.Crypto, 0)])
    SOL = JalSymbol(symbol_id_for_ticker('SOL')).asset().id()
    create_trades(SOL_WALLET, [(d2t(260101), d2t(260101), SOL, Decimal('50'), Decimal('100'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    yield


def symbol_id_for_ticker(ticker) -> int:
    return JalDB._read("SELECT id FROM asset_symbol WHERE symbol=:ticker ORDER BY id LIMIT 1", [(":ticker", ticker)])


def _sol_box(name, address) -> JalStakingBox:
    return JalStakingBox.create(JalAccount(SOL_WALLET), name, protocol='Solana staking',
                                chain=AssetLocation.SOL_BLOCKCHAIN, address=address)


def _stake_sol(box_id, amount, timestamp=d2t(260201)):
    LedgerTransaction.create_new(LedgerTransaction.Transfer, {
        'withdrawal_timestamp': timestamp, 'withdrawal_account': SOL_WALLET, 'withdrawal': str(amount),
        'deposit_timestamp': timestamp, 'deposit_account': box_id, 'deposit': str(amount),
        'number': '', 'note': '', 'symbol_id': symbol_id_for(SOL)}).oid()
    Ledger().rebuild(from_timestamp=0)


# Answers 'getAccountInfo' per address, so a test may describe a whole wallet's worth of stake accounts at once.
def _fake_rpc(monkeypatch, by_address):
    asked = []

    def fake_post(self, url, request):
        address = request['params'][0]
        asked.append(address)
        return by_address.get(address, {'jsonrpc': '2.0', 'id': 1, 'result': {'value': None}})
    monkeypatch.setattr(ChainBalanceReader, "_post", fake_post)
    return asked


def _stake_account(lamports, owner=STAKE_PROGRAM):
    return {'jsonrpc': '2.0', 'id': 1, 'result': {'value': {'lamports': lamports, 'owner': owner, 'data': ['', 'base64']}}}


# The lamports of the stake account ARE the position, and the rent-exempt reserve inside them is deliberately NOT
# deducted: the fetcher books the whole native delta when the stake is made, so the recorded principal contains the
# reserve too. Subtracting it here would invent a shortfall on every Solana box. Figures are the real shape of the
# validation wallet - a stake of 5.90228288 SOL that the chain has grown to 6.053491451.
def test_stake_account_lamports_are_the_box_balance(sol_wallet, monkeypatch):
    box = _sol_box("SOL staking", STAKE_A)
    _stake_sol(box.id(), Decimal('5.90228288'))
    _fake_rpc(monkeypatch, {STAKE_A: _stake_account(6053491451)})

    assert ChainBalanceReader().read_staking_boxes(NOW) == 1
    assert JalChainBalance().latest(box.id(), SOL, NOW)['amount'] == Decimal('6.053491451')


def test_solana_accrual_is_the_difference_from_the_ledger(sol_wallet, monkeypatch):
    box = _sol_box("SOL staking", STAKE_A)
    _stake_sol(box.id(), Decimal('5.90228288'))
    _fake_rpc(monkeypatch, {STAKE_A: _stake_account(6053491451)})
    ChainBalanceReader().read_staking_boxes(NOW)

    ledger = box.holdings(NOW)[0]['amount']
    assert JalChainBalance().latest(box.id(), SOL, NOW)['amount'] - ledger == Decimal('0.151208571')


# A Solana box is asked about ITS OWN address - a stake account is a real account on the chain, so unlike a venue's
# internal balance there is no wallet to resolve and nothing to disambiguate.
def test_a_solana_box_is_asked_about_its_own_stake_account(sol_wallet, monkeypatch):
    box = _sol_box("SOL staking", STAKE_A)
    _stake_sol(box.id(), Decimal('5.90228288'))
    asked = _fake_rpc(monkeypatch, {STAKE_A: _stake_account(6053491451)})
    ChainBalanceReader().read_staking_boxes(NOW)

    assert asked == [STAKE_A]


# The contrast with Hyperliquid, and the reason the "several boxes" guard must NOT be applied here: every stake
# account has its own address and its own balance, so a wallet staking to several validators is perfectly ordinary
# and each of its boxes is measured on its own. Applying the venue guard would silence all of them.
def test_several_solana_boxes_on_one_wallet_are_all_read(sol_wallet, monkeypatch):
    first = _sol_box("SOL staking A", STAKE_A)
    second = _sol_box("SOL staking B", STAKE_B)
    _stake_sol(first.id(), Decimal('5.90228288'))
    _stake_sol(second.id(), Decimal('2'))
    _fake_rpc(monkeypatch, {STAKE_A: _stake_account(6053491451), STAKE_B: _stake_account(2100000000)})

    assert ChainBalanceReader().read_staking_boxes(NOW) == 2
    assert JalChainBalance().latest(first.id(), SOL, NOW)['amount'] == Decimal('6.053491451')
    assert JalChainBalance().latest(second.id(), SOL, NOW)['amount'] == Decimal('2.1')


# A stake account is closed once it is emptied, and the chain then reports it as simply not existing. That is the
# ordinary end of a position, not a failure - so zero is recorded as the honest measurement rather than the box
# freezing at its last reading. It is also what lets the books be seen still holding what the chain no longer has.
def test_a_closed_stake_account_is_recorded_as_zero(sol_wallet, monkeypatch):
    box = _sol_box("SOL staking", STAKE_A)
    _stake_sol(box.id(), Decimal('5.90228288'))
    _fake_rpc(monkeypatch, {STAKE_A: {'jsonrpc': '2.0', 'id': 1, 'result': {'value': None}}})

    assert ChainBalanceReader().read_staking_boxes(NOW) == 1
    assert JalChainBalance().latest(box.id(), SOL, NOW)['amount'] == Decimal('0')


# The one check that makes reading a bare address safe. A box carries its container's address, and if that address
# were ever wrong - mistyped, or pointing at an ordinary wallet - the whole balance sitting there would be read as
# this position's staked amount. Only the stake program owning the account proves it is a stake account at all.
def test_an_address_that_is_not_a_stake_account_is_refused(sol_wallet, monkeypatch):
    box = _sol_box("SOL staking", STAKE_A)
    _stake_sol(box.id(), Decimal('5.90228288'))
    _fake_rpc(monkeypatch, {STAKE_A: _stake_account(900000000000, owner='11111111111111111111111111111111')})

    assert ChainBalanceReader().read_staking_boxes(NOW) == 0
    assert JalChainBalance().latest(box.id(), SOL, NOW) is None


# An RPC failure is an 'error' object and must never be confused with the null that means "no such account" - one is
# "we could not ask", the other is "it is genuinely gone", and only the second is a measurement.
@pytest.mark.parametrize("answer", [
    {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32603, 'message': 'Internal error'}},
    {'jsonrpc': '2.0', 'id': 1},                                       # no 'result' at all
    {'jsonrpc': '2.0', 'id': 1, 'result': {'value': {'owner': STAKE_PROGRAM}}},   # no 'lamports'
    [],                                                                # not a dict
])
def test_a_failed_stake_account_call_stores_nothing(sol_wallet, monkeypatch, answer):
    box = _sol_box("SOL staking", STAKE_A)
    _stake_sol(box.id(), Decimal('5.90228288'))
    _fake_rpc(monkeypatch, {STAKE_A: answer})

    assert ChainBalanceReader().read_staking_boxes(NOW) == 0
    assert JalChainBalance().latest(box.id(), SOL, NOW) is None


# Without a key nothing can be asked, and that is a configuration problem to be reported rather than a balance of
# zero to be recorded.
def test_no_helius_key_reads_nothing(sol_wallet, monkeypatch):
    JalSettings().setValue("ApiKey_Helius", "")
    box = _sol_box("SOL staking", STAKE_A)
    _stake_sol(box.id(), Decimal('5.90228288'))
    asked = _fake_rpc(monkeypatch, {STAKE_A: _stake_account(6053491451)})

    assert ChainBalanceReader().read_staking_boxes(NOW) == 0
    assert asked == []


# Both venues in one run, each through its own reader, into one venue-agnostic table.
def test_both_venues_are_read_in_one_pass(sol_wallet, monkeypatch):
    hl_box = _new_box("Hyperliquid staking")
    _stake(WALLET, hl_box.id(), Decimal('11.92275902'))
    sol_box = _sol_box("SOL staking", STAKE_A)
    _stake_sol(sol_box.id(), Decimal('5.90228288'))

    def fake_post(self, url, request):
        if request.get('method') == 'getAccountInfo':
            return _stake_account(6053491451)
        return _SUMMARY_QUEUED
    monkeypatch.setattr(ChainBalanceReader, "_post", fake_post)

    assert ChainBalanceReader().read_staking_boxes(NOW) == 2
    assert JalChainBalance().latest(hl_box.id(), HYPE, NOW)['amount'] == Decimal('11.99462482')
    assert JalChainBalance().latest(sol_box.id(), SOL, NOW)['amount'] == Decimal('6.053491451')
