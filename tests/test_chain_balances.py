from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedAccountType, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.chain_balance import JalChainBalance
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.staking import JalStakingBox
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
