from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_trades, symbol_id_for
from constants import BookAccount, PredefinedAsset, PredefinedCategory, PredefinedAccountType, AssetLocation
from jal.data_import.statement import Statement, JSF
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, Transfer
from jal.db.transfer_settlement import TransferSettlement
from jal.net.arrival_reconciler import ArrivalReconciler
from jal.net.route import Confidence, Route, RouteLeg, RouteResolver
from jal.net.route_resolvers import RouteResolvers

# ----------------------------------------------------------------------------------------------------------------------
# One movement reaches JAL as two records, each knowing the end the other doesn't - the wallet that sent it and the
# wallet that received it are fetched separately, and an exchange that sends coins out is a statement of its own.
# Settlement pairs those records back into one transfer, and it does so on the TRANSACTION HASH alone: amount and date
# proximity is a resemblance and stays the user's decision, while the same transaction moving the same asset is proof.
#
# What a transaction hash does NOT identify is a single movement - one transaction may pay many addresses - so the
# whole safety of this rests on the shapes it REFUSES, which is most of what is tested here.

USDT, USDC = 4, 5               # the assets created by the fixture below
WALLET_A, WALLET_B, WALLET_C = 1, 2, 3
USD, EUR = 2, 3
HASH = '0x' + 'a' * 64


@pytest.fixture
def wallets(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='ARB wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=USD, number='', name='ETH wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '2' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=EUR, number='', name='EUR wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '3' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_assets([('USDT', 'Tether USD', '', USD, PredefinedAsset.Crypto, 0),      # ID = USDT
                   ('USDC', 'USD Coin', '', USD, PredefinedAsset.Crypto, 0)])       # ID = USDC
    yield


def _transfer(from_account, to_account, amount, timestamp, asset_id=USDT, deposit=0, number=HASH,
              deposit_timestamp=None, fee=None, fee_account=None, note=''):
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
            'deposit_timestamp': timestamp if deposit_timestamp is None else deposit_timestamp,
            'deposit_account': to_account, 'deposit': str(deposit), 'number': number, 'note': note,
            'symbol_id': symbol_id_for(asset_id) if asset_id else None}
    if fee is not None:
        data['fee'] = str(fee)
        data['fee_account'] = fee_account
        data['fee_symbol_id'] = symbol_id_for(asset_id)
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


def _stored() -> list:
    query = LedgerTransaction._exec("SELECT oid, withdrawal_timestamp, withdrawal_account, withdrawal, "
                                    "deposit_timestamp, deposit_account, deposit, fee, fee_account, number, note "
                                    "FROM transfers ORDER BY oid")
    rows = []
    while query.next():
        rows.append(LedgerTransaction._read_record(query, named=True))
    return rows


def _in_transit(asset_id) -> Decimal:
    total = Ledger._read("SELECT SUM(amount) FROM ledger WHERE book_account=:book AND asset_id=:asset",
                         [(":book", BookAccount.Transfers), (":asset", asset_id)])
    return Decimal(total) if total else Decimal('0')


# ----------------------------------------------------------------------------------------------------------------------
# Two pending legs of one movement

def test_two_pending_legs_of_one_transaction_are_settled_into_one_transfer(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 400, d2t(210103))

    assert TransferSettlement().settle_all() == 1

    rows = _stored()
    assert len(rows) == 1
    assert (int(rows[0]['withdrawal_account']), int(rows[0]['deposit_account'])) == (WALLET_A, WALLET_B)
    assert not Transfer(int(rows[0]['oid']), Transfer.Outgoing).is_pending()


# The record to keep is the SENDING one: on-chain gas is paid by the sender, so that is the side that knows the fee
def test_the_sending_record_survives_with_its_fee(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), fee=Decimal('0.5'), fee_account=WALLET_A, note='sent')
    _transfer(None, WALLET_B, 400, d2t(210103), note='arrived')

    TransferSettlement().settle_all()

    rows = _stored()
    assert len(rows) == 1
    assert Decimal(rows[0]['fee']) == Decimal('0.5') and int(rows[0]['fee_account']) == WALLET_A
    assert rows[0]['note'] == 'sent'


# ... but a fee the surviving record has none of is adopted rather than dropped with the row that brought it
def test_a_fee_the_sending_record_lacks_is_adopted(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), note='')
    _transfer(None, WALLET_B, 400, d2t(210103), fee=Decimal('0.5'), fee_account=WALLET_B, note='arrived')

    TransferSettlement().settle_all()

    rows = _stored()
    assert Decimal(rows[0]['fee']) == Decimal('0.5') and int(rows[0]['fee_account']) == WALLET_B
    assert rows[0]['note'] == 'arrived'      # the note of the record that had one


# Each side states its own time - a chain fetch of the sending wallet and one of the receiving wallet agree, an
# exchange statement and the chain it landed on need not
def test_each_side_keeps_its_own_timestamp(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 400, d2t(210105))

    TransferSettlement().settle_all()

    rows = _stored()
    assert int(rows[0]['withdrawal_timestamp']) == d2t(210103)
    assert int(rows[0]['deposit_timestamp']) == d2t(210105)


# ----------------------------------------------------------------------------------------------------------------------
# What settlement refuses. A transaction hash proves that two records describe the same TRANSACTION, not that the
# transaction moved the asset only once, so everything ambiguous is left for the user to pair by hand.

# A multisend pays several addresses in one transaction: three records of one transaction and one asset are three
# movements, and no two of them can be shown to be the same one
def test_a_transaction_that_moved_the_asset_more_than_twice_is_left_alone(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(WALLET_A, None, 500, d2t(210103))
    _transfer(None, WALLET_B, 400, d2t(210103))

    assert TransferSettlement().settle_all() == 0
    assert len(_stored()) == 3


# One movement moves one quantity; records that disagree about it are records of two movements
def test_legs_of_different_quantity_are_not_paired(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 399, d2t(210103))

    assert TransferSettlement().settle_all() == 0


# One transaction may deliver several assets at once (a token plus a gas top-up) and each is a movement of its own
def test_legs_of_different_assets_are_not_paired(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), asset_id=USDT)
    _transfer(None, WALLET_B, 400, d2t(210103), asset_id=USDC)

    assert TransferSettlement().settle_all() == 0


def test_legs_of_different_transactions_are_not_paired(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number='0x' + 'b' * 64)

    assert TransferSettlement().settle_all() == 0


# A movement that names no transaction is identified by nothing - a money transfer's 'number' is a free-form
# reference, and an empty one is not even that
def test_legs_without_a_transaction_hash_are_not_paired(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number='')
    _transfer(None, WALLET_B, 400, d2t(210103), number='')

    assert TransferSettlement().settle_all() == 0


def test_money_legs_are_not_paired(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), asset_id=None, deposit=400)
    _transfer(None, WALLET_B, 400, d2t(210103), asset_id=None, deposit=400)

    assert TransferSettlement().settle_all() == 0


# Two records missing the SAME end are two movements out of one wallet, not the two sides of one movement
def test_two_legs_missing_the_same_end_are_not_paired(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(WALLET_B, None, 400, d2t(210103))

    assert TransferSettlement().settle_all() == 0


# One wallet may both send and receive the same asset in one transaction - a contract passing money through it - and
# those two legs are not a transfer of an account to itself
def test_a_wallet_that_both_sends_and_receives_is_not_paired_with_itself(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_A, 400, d2t(210103))

    assert TransferSettlement().settle_all() == 0


# An arrival can't precede its departure, and a transfer that says it does can't be processed at all: the arriving leg
# reads the value the sending leg parked in the Transfers book, which isn't there yet
def test_an_arrival_before_its_departure_is_not_paired(wallets):
    _transfer(WALLET_A, None, 400, d2t(210105))
    _transfer(None, WALLET_B, 400, d2t(210103))

    assert TransferSettlement().settle_all() == 0


# A record that already knows both of its ends is not a leg waiting for anything - and within one transaction it is
# exactly what a multisend to a resolved and an unresolved address looks like
def test_a_complete_transfer_is_never_folded_into_a_pending_leg(wallets):
    _transfer(WALLET_A, WALLET_B, 400, d2t(210103))
    _transfer(WALLET_A, None, 400, d2t(210103))

    assert TransferSettlement().settle_all() == 0
    assert len(_stored()) == 2


# ----------------------------------------------------------------------------------------------------------------------
# What settlement does to the ledger - the point of the whole thing

@pytest.fixture
def funded(wallets):
    create_actions([(d2t(210101), WALLET_A, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_trades(WALLET_A, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])   # 1000 USDT at basis 1000
    yield


# Unsettled, the two legs are 400 sent from a position that was closed and 400 arrived at zero cost basis. Settled,
# they are one movement: nothing is in transit any more and the cost basis travelled with the asset.
def test_settlement_carries_the_cost_basis_and_empties_the_transfers_book(funded):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 400, d2t(210103))
    Ledger().rebuild(from_timestamp=0)
    lots = JalAccount(WALLET_B).open_trades_list(JalAsset(USDT))
    assert lots[0].open_price(adjusted=True) == Decimal('0')       # arrived from nowhere: basis unknown
    assert _in_transit(USDT) == Decimal('0')                       # +400 sent and -400 arrived cancel by themselves

    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(WALLET_A).get_asset_amount(d2t(210201), USDT) == Decimal('600')
    assert JalAccount(WALLET_B).get_asset_amount(d2t(210201), USDT) == Decimal('400')
    assert _in_transit(USDT) == Decimal('0')
    lots = JalAccount(WALLET_B).open_trades_list(JalAsset(USDT))
    assert len(lots) == 1 and lots[0].open_price(adjusted=True) == Decimal('1')   # the lot that left A is the one here


# Nothing in the pair states a cost basis in the currency of the destination account, and none is invented: the
# arrived asset opens at zero, which is visible in every holdings and deals report. See the FIXME in
# TransferSettlement._merge().
def test_a_cross_currency_pair_is_settled_with_no_cost_basis(funded):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_C, 400, d2t(210103))      # WALLET_C is kept in EUR, WALLET_A in USD

    assert TransferSettlement().settle_all() == 1
    Ledger().rebuild(from_timestamp=0)

    assert JalAccount(WALLET_C).get_asset_amount(d2t(210201), USDT) == Decimal('400')
    lots = JalAccount(WALLET_C).open_trades_list(JalAsset(USDT))
    assert len(lots) == 1 and lots[0].open_price(adjusted=True) == Decimal('0')


# ----------------------------------------------------------------------------------------------------------------------
# The import side: a record that names BOTH ends completes a leg an EARLIER import left pending, instead of being
# stored as a second transfer of the same movement.

STATEMENT_ASSET, STATEMENT_SYMBOL = 10, 100     # ids inside the statement, mapped to the db ones


def _statement(monkeypatch) -> Statement:
    statement = Statement()
    monkeypatch.setattr(type(statement), "_transfers_are_unique_per_transaction", True)
    for statement_id, account_id in ((1, WALLET_A), (2, WALLET_B)):
        statement.set_mapped_id(JSF.ACCOUNTS, statement_id, account_id)
    statement.set_mapped_id(JSF.ASSETS, 1, USD)        # the currency the statement states its symbols in
    statement.set_mapped_id(JSF.ASSETS, STATEMENT_ASSET, USDT)
    statement.set_mapped_id(JSF.SYMBOLS, STATEMENT_SYMBOL, symbol_id_for(USDT))
    statement._data[JSF.ASSETS] = [
        {"id": STATEMENT_ASSET, "type": JSF.ASSET_CRYPTO, "name": "Tether USD",
         JSF.SYMBOLS: [{"id": STATEMENT_SYMBOL, "symbol": "USDT", "currency": 1,
                        "location": AssetLocation.UNDEFINED}]}]     # the symbol the fixture created
    statement._data[JSF.ACCOUNTS] = [{"id": 1, "number": '', "currency": STATEMENT_ASSET},
                                     {"id": 2, "number": '', "currency": STATEMENT_ASSET}]
    return statement


def _record(accounts: list, number: str = HASH, amount=Decimal('1000'), fee=Decimal('0')) -> dict:
    return {"id": 1, "account": accounts, "symbol": [STATEMENT_SYMBOL, STATEMENT_SYMBOL], "timestamp": d2t(210103),
            "withdrawal": amount, "deposit": Decimal('0'), "fee": fee, "number": number}


def _import(monkeypatch, records: list):
    statement = _statement(monkeypatch)
    for index, record in enumerate(records):
        record['id'] = index + 1
    statement._import_transfers(records)


# The counterpart of a pending leg may name both ends - the wallet on the other side was added to JAL in the meantime,
# so the fetch of it recognizes the sender. Without this the movement would be stored twice: deduplication can't
# recognize the stored leg, because an unknown end is part of its key rather than a wildcard.
@pytest.mark.parametrize("pending, complete", [([1, 0, 1], [1, 2, 1]), ([0, 2, 2], [1, 2, 1])])
def test_a_record_of_both_ends_completes_a_leg_stored_earlier(wallets, monkeypatch, pending, complete):
    _import(monkeypatch, [_record(pending)])
    _import(monkeypatch, [_record(complete)])

    rows = _stored()
    assert len(rows) == 1
    assert (int(rows[0]['withdrawal_account']), int(rows[0]['deposit_account'])) == (WALLET_A, WALLET_B)


# The gas of the movement was recorded by the leg that knew about it and is not lost when the other end arrives
def test_completing_a_leg_keeps_what_it_already_knew(wallets, monkeypatch):
    _import(monkeypatch, [_record([1, 0, 1], fee=Decimal('0.5'))])
    _import(monkeypatch, [_record([1, 2, 1])])

    rows = _stored()
    assert len(rows) == 1 and Decimal(rows[0]['fee']) == Decimal('0.5')


# ... and a fee the stored leg had none of is taken from the record that brings it
def test_completing_a_leg_adopts_a_fee_it_did_not_have(wallets, monkeypatch):
    _import(monkeypatch, [_record([0, 2, 2])])
    _import(monkeypatch, [_record([1, 2, 1], fee=Decimal('0.5'))])

    rows = _stored()
    assert len(rows) == 1 and Decimal(rows[0]['fee']) == Decimal('0.5')


# THE guard of this path: within ONE import, "A -> B" and "A -> ?" of the same transaction, asset and amount is a
# multisend paying two addresses of which only one could be resolved. Folding them together would delete a movement.
def test_two_records_of_one_import_never_complete_each_other(wallets, monkeypatch):
    _import(monkeypatch, [_record([1, 2, 1], number='0x' + 'c' * 64)])   # something stored before, so the guard is on
    _import(monkeypatch, [_record([1, 0, 1]), _record([1, 2, 1])])

    assert len(_stored()) == 3


# A movement recorded twice from the same side is the same record, and stays the deduplication's business
def test_a_repeated_record_is_still_deduplicated_not_settled(wallets, monkeypatch):
    _import(monkeypatch, [_record([1, 2, 1])])
    _import(monkeypatch, [_record([1, 2, 1])])

    assert len(_stored()) == 1


# ----------------------------------------------------------------------------------------------------------------------
# The same boundary bounds the GENERIC duplicate check of create_operation(), which had no boundary at all

# Two legs of one transaction that are identical in every stored field - a multisend to two addresses neither of which
# JAL can resolve, or a contract paying one address twice - are two movements. Unbounded, locate_operation() asks
# whether an identical row exists ANYWHERE and so swallows the second, and the money that left the wallet is then in
# no ledger at all. Bounded to what an earlier import stored, it can't see the row this import just wrote.
def test_two_identical_legs_of_one_transaction_are_both_stored(wallets, monkeypatch):
    _import(monkeypatch, [_record([1, 2, 1], number='0x' + 'c' * 64)])   # so the import boundary isn't 0
    _import(monkeypatch, [_record([1, 0, 1]), _record([1, 0, 1])])

    rows = _stored()
    assert len(rows) == 3
    assert [r['deposit_account'] for r in rows] == [WALLET_B, '', '']     # both pending legs are there


# ... and the check still does what it is for: a statement imported twice duplicates nothing
def test_a_reimported_statement_still_duplicates_nothing(wallets, monkeypatch):
    _import(monkeypatch, [_record([1, 0, 1]), _record([1, 0, 1], amount=Decimal('500'))])
    _import(monkeypatch, [_record([1, 0, 1]), _record([1, 0, 1], amount=Decimal('500'))])

    assert len(_stored()) == 2


# A statement whose 'number' identifies nothing keeps the UNBOUNDED check - it has no movement identity of its own to
# fall back on, so that check is its only guard against a re-import
def test_a_statement_without_transaction_hashes_keeps_the_unbounded_check(wallets, monkeypatch):
    statement = _statement(monkeypatch)
    monkeypatch.setattr(type(statement), "_transfers_are_unique_per_transaction", False)
    statement._import_transfers([_record([1, 2, 1], number='ref-1') | {"id": 1},
                                 _record([1, 2, 1], number='ref-1') | {"id": 2}])

    assert len(_stored()) == 1


# The pass runs at the end of every import that can vouch for its 'number', so a statement that brings the missing
# side of a leg settles it without anything else being asked
def test_the_import_settles_pending_legs_it_completes(wallets, monkeypatch):
    _transfer(WALLET_A, None, 1000, d2t(210103))
    statement = _statement(monkeypatch)
    statement._data[JSF.TRANSFERS] = [_record([0, 2, 2])]

    statement.import_into_db()

    rows = _stored()
    assert len(rows) == 1
    assert (int(rows[0]['withdrawal_account']), int(rows[0]['deposit_account'])) == (WALLET_A, WALLET_B)


# A statement whose 'number' is a free-form reference rather than a transaction hash can't identify a movement, so
# nothing is paired on it
def test_a_statement_without_transaction_hashes_settles_nothing(wallets, monkeypatch):
    _transfer(WALLET_A, None, 1000, d2t(210103))
    statement = _statement(monkeypatch)
    monkeypatch.setattr(type(statement), "_transfers_are_unique_per_transaction", False)
    statement._data[JSF.TRANSFERS] = [_record([0, 2, 2])]

    statement.import_into_db()

    assert len(_stored()) == 2


# ----------------------------------------------------------------------------------------------------------------------
# The two ends of a CROSS-CHAIN move, which the pass above can never pair
#
# Everything so far rests on the two records naming the SAME transaction. A cross-chain move has no such transaction:
# it is one on each chain, and nothing on either points at the other, so both legs stay pending however many wallets
# are fetched. Only whoever routed the move can join them - and joining is all that is taken from them, because what
# moved, when and how much is what JAL already read off the two chains.

SRC_HASH = '0x' + 'b' * 64      # what the wallet sent on one chain ...
DST_HASH = '0x' + 'c' * 64      # ... and what was delivered on the other, minutes later


# A source that answers "these two transactions are one move" and nothing more, which is the least any of them says
class _Router(RouteResolver):
    name = "Test router"
    confidence = Confidence.PROPOSED

    def __init__(self, routes: dict = None, confidence: int = None):
        super().__init__()
        self._routes = {SRC_HASH: (DST_HASH, 'chain-2')} if routes is None else routes
        self.asked = 0
        if confidence is not None:
            self.confidence = confidence

    def _request(self, tx_hash: str):
        self.asked += 1
        if tx_hash not in self._routes:
            return None
        arrival, chain = self._routes[tx_hash]
        return Route(self.name, self.confidence, RouteLeg(chain='chain-1', tx_hash=tx_hash),
                     RouteLeg(chain=chain, tx_hash=arrival))


def _settle(router=None) -> tuple:
    return ArrivalReconciler(RouteResolvers([router if router is not None else _Router()])).settle_pending_transfers()


# The ordinary case: what left one chain and what arrived on the other become one transfer, and the money stops
# being in transit - which is the whole purpose of settling it.
def test_the_two_legs_of_a_routed_move_are_settled_into_one_transfer(funded):
    _transfer(WALLET_A, None, 400, d2t(210103), number=SRC_HASH)
    _transfer(None, WALLET_B, 400, d2t(210104), number=DST_HASH)

    settled, findings = _settle()

    assert (settled, findings) == (1, [])
    rows = _stored()
    assert len(rows) == 1
    assert (int(rows[0]['withdrawal_account']), int(rows[0]['deposit_account'])) == (WALLET_A, WALLET_B)
    assert rows[0]['number'] == SRC_HASH      # the record kept is the sending one, which carries the gas
    Ledger().rebuild(from_timestamp=0)
    assert JalAccount(WALLET_B).get_asset_amount(d2t(210201), USDT) == Decimal('400')
    assert _in_transit(USDT) == Decimal('0')


# Naming the counterpart is all this needs, so the weakest kind of source is enough for it - and that is the one
# thing such a source is for. Nothing it says about quantities or times is read: those come from the two legs.
def test_a_source_that_only_names_the_transactions_is_enough(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number=SRC_HASH)
    _transfer(None, WALLET_B, 400, d2t(210104), number=DST_HASH)

    assert _settle(_Router(confidence=Confidence.PROPOSED))[0] == 1


# A route that delivers less than it was sent is a bridge - an operation with a leg of its own for each side - and a
# transfer cannot express it. The pair is proven, so this is reported rather than passed over in silence.
def test_a_route_that_lost_something_on_the_way_is_reported_not_settled(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number=SRC_HASH)
    _transfer(None, WALLET_B, 399, d2t(210104), number=DST_HASH)

    settled, findings = _settle()

    assert settled == 0 and len(findings) == 1
    assert 'not a transfer' in findings[0]
    assert len(_stored()) == 2


# An arrival that precedes its departure is refused here exactly as it is when the two name one transaction
def test_an_arrival_before_its_departure_is_reported_not_settled(wallets):
    _transfer(WALLET_A, None, 400, d2t(210104), number=SRC_HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number=DST_HASH)

    settled, findings = _settle()

    assert settled == 0 and len(findings) == 1
    assert len(_stored()) == 2


# A move nobody has a record of - most of them - leaves both legs exactly as they were
def test_a_leg_no_source_knows_is_left_alone(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number=SRC_HASH)
    _transfer(None, WALLET_B, 400, d2t(210104), number=DST_HASH)

    assert _settle(_Router(routes={}))[0] == 0
    assert len(_stored()) == 2


# The arrival was never imported: there is nothing to pair with, so the leg keeps waiting rather than being completed
# out of what was reported - and nobody is even asked about it. This sweep runs after every fetch and each leg in it
# costs a network request per source, so a leg that has no possible counterpart must not be one of them.
def test_a_leg_with_no_possible_counterpart_is_not_asked_about(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number=SRC_HASH)
    router = _Router()

    assert _settle(router)[0] == 0
    assert router.asked == 0
    assert len(_stored()) == 1


# A move that begins and ends on the same chain is not what this settles: its two records name ONE transaction and
# the pass on the hash has already had its say about them.
def test_a_same_chain_route_is_not_settled_here(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number=SRC_HASH)
    _transfer(None, WALLET_B, 400, d2t(210104), number=DST_HASH)

    assert _settle(_Router(routes={SRC_HASH: (DST_HASH, 'chain-1')}))[0] == 0


# A transfer that already knows both of its ends is not a candidate for anything - it may carry the arriving hash
# because it IS the whole movement, and adopting it would be a second copy of money already booked.
def test_a_settled_transfer_is_not_paired_again(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number=SRC_HASH)
    _transfer(WALLET_C, WALLET_B, 400, d2t(210104), number=DST_HASH)

    assert _settle()[0] == 0
    assert len(_stored()) == 2
