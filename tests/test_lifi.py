import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, dt2t, create_assets, create_actions, create_trades, create_quotes, create_bridges, \
    create_swaps, create_transfers, symbol_id_for
from constants import PredefinedAsset, PredefinedAccountType, PredefinedCategory, AssetLocation, SymbolId
from jal.data_import.statement import Statement, JSF
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.bridge_matcher import BridgeMatcher
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.net import lifi
from jal.net.arrival_reconciler import ArrivalReconciler
from jal.net.lifi import LiFiResolver
from jal.net.rango import RangoResolver
from jal.net.route import Confidence, Route, RouteLeg, RouteResolver
from jal.net.route_resolvers import RouteResolvers
from jal.widgets.bridge_match_dialog import BridgeMatchDialog

# Never a real address: an on-chain address can't be anonymized afterwards (see tests/local_test_data.json.example).
# The same address is registered on both chains, which is how one wallet is normally held - and what makes the
# destination account of an arrival a question of the CHAIN it landed on, not of the address alone.
WALLET = "0x1111111111111111111111111111111111111111"
STRANGER = "0x2222222222222222222222222222222222222222"
USDC_ETH = "0xaaaa000000000000000000000000000000000001"
USDC_ARB = "0xaaaa000000000000000000000000000000000002"
GHO_ETH = "0xcccc000000000000000000000000000000000001"

ETH_WALLET, ARB_WALLET = 1, 2      # account ids created by the fixture below
USDC, GHO = 4, 5                   # asset ids

SEND_HASH = "0xf1" + "0" * 62      # the wallet's own transaction into the aggregator, on Ethereum
ARRIVE_HASH = "0xf2" + "0" * 62    # what the route delivered, on Arbitrum
SWAP_HASH = "0xf3" + "0" * 62      # a transaction booked as a same-chain swap


# ----------------------------------------------------------------------------------------------------------------------
# Answers shaped exactly as https://li.quest/v1/status returns them, cut down to the fields JAL reads.
def _leg(chain_id, tx_hash, address, symbol, decimals, amount, timestamp):
    return {"txHash": tx_hash, "chainId": chain_id, "timestamp": timestamp, "amount": amount,
            "token": {"address": address, "chainId": chain_id, "symbol": symbol, "decimals": decimals}}


def _answer(sending, receiving, to_address=WALLET, tool="across", status="DONE"):
    return {"sending": sending, "receiving": receiving, "tool": tool, "status": status,
            "fromAddress": WALLET, "toAddress": to_address}


# The move JAL sees only the start of: 100 USDC leave Ethereum, 99.5 USDC arrive on Arbitrum three minutes later.
def _usdc_bridge_answer(**kwargs):
    return _answer(_leg(1, SEND_HASH, USDC_ETH, "USDC", 6, "100000000", dt2t(2101031200)),
                   _leg(42161, ARRIVE_HASH, USDC_ARB, "USDC", 6, "99500000", dt2t(2101031203)), **kwargs)


# The same move, but what arrives is another asset - which makes the pair a cross-chain swap rather than a bridge
def _gho_to_usdc_answer(**kwargs):
    return _answer(_leg(1, SEND_HASH, GHO_ETH, "GHO", 18, "100000000000000000000", dt2t(2101031200)),
                   _leg(42161, ARRIVE_HASH, USDC_ARB, "USDC", 6, "99500000", dt2t(2101031203)), **kwargs)


@pytest.fixture
def wallets(prepare_db):
    account = JalAccountCreator(currency_id=2, number='', name='ETH wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    assert account.id() == ETH_WALLET
    account = JalAccountCreator(currency_id=2, number='', name='ARB wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    assert account.id() == ARB_WALLET
    # USDC is ONE asset listed on both chains - which is what makes a move of it a bridge and not an exchange
    usdc = JalAssetCreator(PredefinedAsset.Crypto, 'USD Coin')
    usdc.add_identifier(usdc.add_symbol('USDC', 2, AssetLocation.ETH_BLOCKCHAIN), SymbolId.ETH_ADDRESS, USDC_ETH)
    usdc.add_identifier(usdc.add_symbol('USDC', 2, AssetLocation.ARB_BLOCKCHAIN), SymbolId.ARB_ADDRESS, USDC_ARB)
    assert usdc.commit().id() == USDC
    gho = JalAssetCreator(PredefinedAsset.Crypto, 'Gho Token')
    gho.add_identifier(gho.add_symbol('GHO', 2, AssetLocation.ETH_BLOCKCHAIN), SymbolId.ETH_ADDRESS, GHO_ETH)
    assert gho.commit().id() == GHO
    create_actions([(d2t(210101), ETH_WALLET, 1, [(PredefinedCategory.StartingBalance, 100000.0)])])
    yield


# Replaces the network with recorded answers, keyed by the hash they are about. Everything above the HTTP call itself
# stays real - including the check that the answer is about the transaction that was asked for.
#
# The other sources of the registry are silenced rather than left out: what is under test is the reconciler as it is
# really assembled, and a source that knows nothing is exactly what every other one answers for these transactions.
@pytest.fixture
def lifi_answers(monkeypatch):
    answers = {}

    def fake_request(self, tx_hash):
        answer = answers.get(tx_hash.lower())
        return self._validated(answer, tx_hash) if answer is not None else None

    monkeypatch.setattr(LiFiResolver, "_request", fake_request)
    monkeypatch.setattr(RangoResolver, "_request", lambda self, tx_hash: None)
    yield answers


def _symbol_on(asset_id, location_id) -> int:
    return JalDB._read("SELECT id FROM asset_symbol WHERE asset_id=:a AND location_id=:l",
                       [(":a", asset_id), (":l", location_id)])


# ----------------------------------------------------------------------------------------------------------------------
# The API client

# An amount is an integer of the token's smallest unit and is scaled by that token's decimals, losslessly - a
# quantity that is compared against on-chain data must not be rounded on the way in.
def test_amounts_and_addresses_are_read_exactly(lifi_answers):
    lifi_answers[SEND_HASH] = _answer(
        _leg(1, SEND_HASH, GHO_ETH, "GHO", 18, "212089846867967115919", dt2t(2101031200)),
        _leg(42161, ARRIVE_HASH, USDC_ARB, "USDC", 6, "211607214", dt2t(2101031203)))
    transfer = LiFiResolver().resolve(SEND_HASH)

    assert transfer.sending.qty == Decimal('212.089846867967115919')
    assert transfer.receiving.qty == Decimal('211.607214')
    assert transfer.sending.location_id == AssetLocation.ETH_BLOCKCHAIN
    assert transfer.receiving.location_id == AssetLocation.ARB_BLOCKCHAIN
    assert transfer.receiving.address == USDC_ARB
    assert transfer.is_cross_chain()


# A chain's own coin is named by a placeholder where a contract address belongs; JAL keeps the native coin with no
# address at all, so each placeholder has to become one.
@pytest.mark.parametrize("chain_id, address, expected_location", [
    (1, "0x0000000000000000000000000000000000000000", AssetLocation.ETH_BLOCKCHAIN),
    (1151111081099710, "11111111111111111111111111111111", AssetLocation.SOL_BLOCKCHAIN),
    (20000000000001, "bitcoin", AssetLocation.BTC_BLOCKCHAIN)])
def test_native_coin_placeholders_become_no_address(lifi_answers, chain_id, address, expected_location):
    lifi_answers[SEND_HASH] = _answer(_leg(1, SEND_HASH, GHO_ETH, "GHO", 18, "1000000000000000000", dt2t(2101031200)),
                                      _leg(chain_id, ARRIVE_HASH, address, "COIN", 8, "100000", dt2t(2101031203)))
    transfer = LiFiResolver().resolve(SEND_HASH)

    assert transfer.receiving.address == ''
    assert transfer.receiving.location_id == expected_location


# The endpoint takes either a transaction hash or the aggregator's own route id in the same parameter, and answers
# 200 with an UNRELATED transfer for a value it reads as the latter. Believing such an answer would invent a
# counter-leg out of somebody else's money, so an answer is only used when it is about the transaction asked for.
def test_answer_about_another_transaction_is_refused(lifi_answers):
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()
    lifi_answers[SEND_HASH]['sending']['txHash'] = "0xdead" + "0" * 60

    assert LiFiResolver().resolve(SEND_HASH) is None


# A route still in flight may yet deliver something else than it says now, so only a completed one is used
def test_unfinished_route_is_not_used(lifi_answers):
    lifi_answers[SEND_HASH] = _usdc_bridge_answer(status="PENDING")

    assert LiFiResolver().resolve(SEND_HASH) is None


# ----------------------------------------------------------------------------------------------------------------------
# Completing a pending half from what the aggregator reported

# The arrival JAL never fetched - and here could not fetch, as nothing of the destination chain is in the database -
# completes the half into a bridge, carrying the cost basis onto the destination account.
def test_reported_arrival_completes_a_bridge(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()

    proposal = ArrivalReconciler().arrival_of_half(half)
    assert proposal.is_placeable()
    assert proposal.leg['account_id'] == ARB_WALLET
    assert proposal.leg['qty'] == Decimal('99.5')
    assert proposal.leg['tx_hash'] == ARRIVE_HASH

    assert ArrivalReconciler().complete_half(half) == half
    Ledger().rebuild(from_timestamp=0)

    assert len(BridgeMatcher()._pending_halves()) == 0
    lots = JalAccount(ARB_WALLET).open_trades_list(JalAsset(USDC))
    assert len(lots) == 1 and lots[0].open_qty() == Decimal('99.5')


# When the asset changed on the way the pair is not a bridge but an exchange, and adopting the reported arrival
# creates the cross-chain swap that realizes the disposal - the same outcome a hand-matched transfer produces.
def test_reported_arrival_of_another_asset_creates_a_cross_chain_swap(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), GHO, 300.0, 1.0, 0.0)])
    create_quotes(GHO, 2, [(dt2t(2101031200), 1.0)])
    half = create_bridges([{'asset': GHO, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _gho_to_usdc_answer()

    swap_oid = ArrivalReconciler().complete_half(half)
    Ledger().rebuild(from_timestamp=0)

    assert JalDB._read("SELECT COUNT(*) FROM bridges WHERE oid=:o", [(":o", half)]) == 0
    assert JalDB._read("SELECT in_tx_hash FROM swaps WHERE oid=:o", [(":o", swap_oid)]) == ARRIVE_HASH
    lots = JalAccount(ARB_WALLET).open_trades_list(JalAsset(USDC))
    assert len(lots) == 1 and lots[0].open_qty() == Decimal('99.5')


# An arrival delivered to an address JAL has no account for is not placed, and what stands in the way is said instead:
# a route delivers wherever it was told to, and where the assets landed decides whether they are the user's at all.
def test_arrival_to_an_unknown_address_is_reported_not_placed(wallets, lifi_answers):
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer(to_address=STRANGER)

    proposal = ArrivalReconciler().arrival_of_half(half)
    assert not proposal.is_placeable()
    assert STRANGER in proposal.problem
    assert '99.5 USDC' in proposal.text     # what happened is still shown, whether or not it can be booked


# The same for a token no listing of which is in the database - the arrival is known, but there is nothing to book it as
def test_arrival_of_an_unknown_token_is_reported_not_placed(wallets, lifi_answers):
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    answer = _usdc_bridge_answer()
    answer['receiving']['token']['address'] = "0xbbbb000000000000000000000000000000000009"
    lifi_answers[SEND_HASH] = answer

    proposal = ArrivalReconciler().arrival_of_half(half)
    assert not proposal.is_placeable()
    assert 'USDC' in proposal.problem


# A half whose sending transaction was routed by nobody LI.FI knows is left exactly as it was
def test_unknown_transaction_yields_no_proposal(wallets, lifi_answers):
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]

    assert ArrivalReconciler().arrival_of_half(half) is None
    assert ArrivalReconciler().complete_half(half) == 0


# ----------------------------------------------------------------------------------------------------------------------
# Meeting the arrival a second time, as a transaction of the chain it landed on

# The chain confirms what was booked: the movement is recognized, so it is not stored again, and there is nothing to say
def test_fetched_arrival_is_recognized_and_not_duplicated(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()
    ArrivalReconciler().complete_half(half)

    recognized, complaint = BridgeMatcher().reconcile_arrival(
        ARRIVE_HASH, _symbol_on(USDC, AssetLocation.ARB_BLOCKCHAIN), ARB_WALLET, Decimal('99.5'), dt2t(2101031203))

    assert recognized and complaint == ''


# The chain is the authority - the aggregator only described it - so a quantity that differs is corrected, and the
# correction is reported rather than applied quietly.
def test_fetched_arrival_corrects_the_booked_quantity(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()
    ArrivalReconciler().complete_half(half)

    recognized, complaint = BridgeMatcher().reconcile_arrival(
        ARRIVE_HASH, _symbol_on(USDC, AssetLocation.ARB_BLOCKCHAIN), ARB_WALLET, Decimal('99.4'), dt2t(2101031203))

    assert recognized and complaint
    assert Decimal(JalDB._read("SELECT in_qty FROM bridges WHERE oid=:o", [(":o", half)])) == Decimal('99.4')


# A correction that would leave the operation invalid is refused and only reported: a bridge may not deliver more
# than it was sent, whoever says otherwise.
def test_impossible_correction_is_refused_and_reported(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()
    ArrivalReconciler().complete_half(half)

    recognized, complaint = BridgeMatcher().reconcile_arrival(
        ARRIVE_HASH, _symbol_on(USDC, AssetLocation.ARB_BLOCKCHAIN), ARB_WALLET, Decimal('150'), dt2t(2101031203))

    assert recognized and 'by hand' in complaint
    assert Decimal(JalDB._read("SELECT in_qty FROM bridges WHERE oid=:o", [(":o", half)])) == Decimal('99.5')


# One transaction may deliver several assets at once (a token plus a gas top-up). Only the asset that was adopted is
# already in the ledger - another one arriving in the same transaction is a movement of its own and must be stored.
def test_another_asset_in_the_same_transaction_is_not_swallowed(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()
    ArrivalReconciler().complete_half(half)

    recognized, _ = BridgeMatcher().reconcile_arrival(
        ARRIVE_HASH, _symbol_on(GHO, AssetLocation.ETH_BLOCKCHAIN), ARB_WALLET, Decimal('1'), dt2t(2101031203))

    assert not recognized


# The same thing driven through the import itself: a fetched transfer of an arrival that is already booked never
# reaches the database, and the user is not asked which account it came from either.
def test_import_skips_an_arrival_that_is_already_booked(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()
    ArrivalReconciler().complete_half(half)
    transfers_before = JalDB._read("SELECT COUNT(*) FROM transfers")

    statement = Statement()
    statement._transfers_are_unique_per_transaction = True   # as every chain fetcher is - a hash identifies a movement
    arb_symbol = _symbol_on(USDC, AssetLocation.ARB_BLOCKCHAIN)
    statement._data = {JSF.ASSETS: [{"id": 10, JSF.SYMBOLS: [{"id": 100}]}]}
    statement.set_mapped_id(JSF.ASSETS, 10, USDC)
    statement.set_mapped_id(JSF.SYMBOLS, 100, arb_symbol)
    statement.set_mapped_id(JSF.ACCOUNTS, 1, ARB_WALLET)
    statement._import_transfers([{"id": 1, "account": [0, 1, 1], "symbol": [100, 100],
                                  "timestamp": dt2t(2101031203), "withdrawal": Decimal('99.5'),
                                  "deposit": Decimal('0'), "fee": Decimal('0'), "number": ARRIVE_HASH,
                                  "description": ""}])

    assert JalDB._read("SELECT COUNT(*) FROM transfers") == transfers_before


# ----------------------------------------------------------------------------------------------------------------------
# Auditing the swaps that are already stored

# A route that delivers on another chain commonly ALSO pays the wallet something on the source chain, and that payout
# is the only incoming asset the sending transaction has - so the whole move looks like a small same-chain exchange
# and is booked as one, disposing of everything sent for that payout alone. Only the aggregator can tell, and it is
# asked. (Real shape it was built from: 855 USDG sent, 0.855038 USDC paid back on the source chain, 854.175931 USDC
# delivered on the destination one - and the two amounts JAL could see made a plausible, and ruinous, small swap.)
def test_audit_finds_a_cross_chain_move_booked_as_a_same_chain_swap(wallets, lifi_answers):
    create_swaps(ETH_WALLET, [(dt2t(2101031200), GHO, 100, USDC, Decimal('0.1'))])
    JalDB._exec("UPDATE swaps SET tx_hash=:hash", [(":hash", SEND_HASH)], commit=True)
    lifi_answers[SEND_HASH] = _gho_to_usdc_answer()

    last_oid, findings = ArrivalReconciler().audit_swaps()

    assert last_oid == 1 and len(findings) == 1
    assert 'cross-chain move' in findings[0] and 'paid back on the source chain' in findings[0]


# A genuine same-chain exchange agrees with the route it came from and is not complained about
def test_audit_is_silent_on_a_matching_same_chain_swap(wallets, lifi_answers):
    create_swaps(ETH_WALLET, [(dt2t(2101031200), GHO, 100, USDC, Decimal('99.5'))])
    JalDB._exec("UPDATE swaps SET tx_hash=:hash", [(":hash", SWAP_HASH)], commit=True)
    lifi_answers[SWAP_HASH] = _answer(
        _leg(1, SWAP_HASH, GHO_ETH, "GHO", 18, "100000000000000000000", dt2t(2101031200)),
        _leg(1, SWAP_HASH, USDC_ETH, "USDC", 6, "99500000", dt2t(2101031200)))

    _, findings = ArrivalReconciler().audit_swaps()

    assert findings == []


# ... while a same-chain exchange whose quantities differ from the route's is reported. Which of the two readings is
# right is not something the audit can decide, so nothing is corrected - it is put in front of the user.
def test_audit_reports_a_same_chain_swap_with_other_quantities(wallets, lifi_answers):
    create_swaps(ETH_WALLET, [(dt2t(2101031200), GHO, 100, USDC, Decimal('12'))])
    JalDB._exec("UPDATE swaps SET tx_hash=:hash", [(":hash", SWAP_HASH)], commit=True)
    lifi_answers[SWAP_HASH] = _answer(
        _leg(1, SWAP_HASH, GHO_ETH, "GHO", 18, "100000000000000000000", dt2t(2101031200)),
        _leg(1, SWAP_HASH, USDC_ETH, "USDC", 6, "99500000", dt2t(2101031200)))

    _, findings = ArrivalReconciler().audit_swaps()

    assert len(findings) == 1 and '99.5 USDC' in findings[0]


# Swaps are checked once: a run starts above the highest oid the previous one examined, so re-fetching costs nothing
def test_audit_resumes_above_what_it_already_checked(wallets, lifi_answers):
    create_swaps(ETH_WALLET, [(dt2t(2101031200), GHO, 100, USDC, Decimal('0.1'))])
    JalDB._exec("UPDATE swaps SET tx_hash=:hash", [(":hash", SEND_HASH)], commit=True)
    lifi_answers[SEND_HASH] = _gho_to_usdc_answer()

    last_oid, findings = ArrivalReconciler().audit_swaps()
    assert findings

    _, findings = ArrivalReconciler().audit_swaps(last_oid)
    assert findings == []


# ----------------------------------------------------------------------------------------------------------------------
# The dialog, where the user decides

# With nothing fetched from the destination chain there is no transfer to adopt, and the reported arrival is what the
# dialog offers - which is the only way such a move can ever be completed.
def test_dialog_offers_the_reported_arrival_when_no_transfer_exists(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()

    dialog = BridgeMatchDialog(half)
    assert len(dialog._options) == 1 and dialog._options[0][0] == BridgeMatchDialog.LEG
    dialog._list.setCurrentRow(0)
    dialog.accept()
    Ledger().rebuild(from_timestamp=0)

    assert len(BridgeMatcher()._pending_halves()) == 0


# When the arrival IS already in the ledger as a fetched transfer, that transfer is what must be adopted - booking a
# leg beside it would leave the same movement in the ledger twice - so it is the only option offered, and it is marked.
def test_dialog_prefers_the_transfer_the_report_confirms(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    transfer_oid = create_transfers([(dt2t(2101031203), ETH_WALLET, Decimal('99.5'), ARB_WALLET, 0, USDC)])[0]
    JalDB._exec("UPDATE transfers SET number=:hash WHERE oid=:oid",
                [(":hash", ARRIVE_HASH), (":oid", transfer_oid)], commit=True)
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()

    dialog = BridgeMatchDialog(half)
    assert len(dialog._options) == 1
    assert dialog._options[0][0] == BridgeMatchDialog.TRANSFER and dialog._options[0][1] == transfer_oid
    assert 'LI.FI' in dialog._options[0][2]
    dialog._list.setCurrentRow(0)
    dialog.accept()

    assert len(BridgeMatcher()._pending_halves()) == 0
    assert JalDB._read("SELECT COUNT(*) FROM transfers WHERE oid=:o", [(":o", transfer_oid)]) == 0


# ----------------------------------------------------------------------------------------------------------------------
# The confidence tier, which is what a source of weaker data is allowed to do
#
# A source below REPORTED states which transactions belong together and nothing else that may be believed - its
# amounts are rounded and its times are moments in its own workflow. So it may point at what JAL already holds, and
# it may never produce a leg to book. Both halves of that are tested here on a stub, because they are properties of
# the reconciler rather than of any one source (jal/net/rango.py is the source that has them).

# What such a source says about the arrival, worded exactly as LI.FI would say it - and refused all the same
class _WeakResolver(RouteResolver):
    name = "Test source"
    confidence = Confidence.PROPOSED

    def _request(self, tx_hash: str):
        return Route(self.name, self.confidence,
                     RouteLeg(chain='1', location_id=AssetLocation.ETH_BLOCKCHAIN, tx_hash=tx_hash),
                     RouteLeg(chain='42161', location_id=AssetLocation.ARB_BLOCKCHAIN, tx_hash=ARRIVE_HASH,
                              symbol='USDC', address=USDC_ARB), to_address=WALLET)


def _weakly(*resolvers):
    return ArrivalReconciler(RouteResolvers(list(resolvers) or [_WeakResolver()]))


# Everything needed to place the leg is known - the chain, the account, the token - and it is still not offered,
# because what would be written into the ledger is a quantity and a time this source doesn't have.
def test_a_source_below_the_reported_tier_never_produces_a_leg(wallets, lifi_answers):
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]

    proposal = _weakly().arrival_of_half(half)
    assert not proposal.is_placeable()
    assert 'Test source' in proposal.problem
    assert _weakly().complete_half(half) == 0


# ... but naming the transaction is exactly what it is for: the arrival is already in the ledger as a fetched
# transfer, and pointing at it costs nothing that could be wrong.
def test_a_source_below_the_reported_tier_still_confirms_a_stored_transfer(wallets, lifi_answers):
    create_trades(ETH_WALLET, [(d2t(210102), d2t(210102), USDC, 300.0, 1.0, 0.0)])
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    transfer_oid = create_transfers([(dt2t(2101031203), ETH_WALLET, Decimal('99.5'), ARB_WALLET, 0, USDC)])[0]
    JalDB._exec("UPDATE transfers SET number=:hash WHERE oid=:oid",
                [(":hash", ARRIVE_HASH), (":oid", transfer_oid)], commit=True)

    dialog = BridgeMatchDialog(half, reconciler=_weakly())
    assert len(dialog._options) == 1
    assert dialog._options[0][0] == BridgeMatchDialog.TRANSFER and dialog._options[0][1] == transfer_oid
    assert 'Test source' in dialog._options[0][2]


# A stronger source answers for a transaction a weaker one also has a record of, and the weaker one is never reached -
# so it can neither contradict what was stated exactly nor cost the round trip it would take to ask it.
def test_the_best_informed_source_that_has_an_answer_is_the_one_used(wallets, lifi_answers):
    half = create_bridges([{'asset': USDC, 'out_ts': dt2t(2101031200), 'out_acc': ETH_WALLET, 'out_qty': 100,
                            'out_hash': SEND_HASH}])[0]
    lifi_answers[SEND_HASH] = _usdc_bridge_answer()

    proposal = _weakly(_WeakResolver(), LiFiResolver()).arrival_of_half(half)
    assert proposal.is_placeable()
    assert proposal.route.source == 'LI.FI'
    assert proposal.leg['qty'] == Decimal('99.5')
