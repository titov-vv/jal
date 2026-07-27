import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from tests.fixtures import project_root, data_path
from constants import AssetLocation
from jal.net.rango import RangoResolver
from jal.net.route import Confidence

# The hashes of the recorded route, after anonymization - see tests/test_data/rango_swap.html
SEND_HASH = "0xf1" + "0" * 62      # what the wallet sent on Arbitrum, the only hash the explorer is searchable by
ARRIVE_HASH = "0xf2" + "0" * 62    # what was delivered on Avalanche, which exists only inside an explorer URL
WALLET = "0x1111111111111111111111111111111111111111"

# What the explorer answers for a transaction it has no record of: HTTP 200 and a page with no route object in it,
# which is also what a page whose format changed looks like. Both mean the same thing and both must mean "no answer".
_NOT_FOUND = '<!DOCTYPE html><html><body><h1>Page Not Found</h1>' \
             '<script>self.__next_f.push([1,"0:{\\"b\\":\\"buildId\\"}\\n"])</script></body></html>'


@pytest.fixture
def page(data_path):
    with open(data_path + "rango_swap.html", 'r', encoding='utf-8') as f:
        yield f.read()


# Answers every lookup with the given page, so that everything above the HTTP call itself - the flight parsing, the
# identity check, the refusals - is what runs.
def _resolver(monkeypatch, page: str) -> RangoResolver:
    def answer(self, tx_hash):
        record = self._route_object(page)
        return self._validated(record, tx_hash) if record is not None else None

    monkeypatch.setattr(RangoResolver, "_request", answer)
    return RangoResolver()


# The same, for a route object that differs from the recorded one in one field. The variant is built out of what was
# recorded rather than by hand, so that a test of a refusal cannot drift away from the shape it refuses.
def _resolver_with(monkeypatch, page: str, field: str, value) -> RangoResolver:
    record = RangoResolver()._route_object(page)
    record[field] = value

    monkeypatch.setattr(RangoResolver, "_request", lambda self, tx_hash: self._validated(record, tx_hash))
    return RangoResolver()


# ----------------------------------------------------------------------------------------------------------------------
# The two transaction hashes are the whole point: they are what no other source has for a route LI.FI never saw, and
# the destination one exists only inside a rendered block-explorer link.
def test_both_ends_of_the_route_are_read_from_the_page(monkeypatch, page):
    route = _resolver(monkeypatch, page).resolve(SEND_HASH)

    assert route.source == "Rango"
    assert route.sending.tx_hash == SEND_HASH
    assert route.receiving.tx_hash == ARRIVE_HASH
    assert route.is_cross_chain()
    assert route.to_address == WALLET


# A chain Rango names and JAL knows becomes JAL's own; one it doesn't stays what Rango called it, which is what the
# user has to be told. The recorded route delivers on Avalanche, which JAL has no account type for at all.
def test_chains_are_translated_where_jal_knows_them(monkeypatch, page):
    route = _resolver(monkeypatch, page).resolve(SEND_HASH)

    assert route.sending.location_id == AssetLocation.ARB_BLOCKCHAIN
    assert route.receiving.location_id == AssetLocation.UNDEFINED
    assert route.receiving.chain == 'AVAX_CCHAIN'


# Nothing that would have to be believed is read at all. The page states both amounts and a time; they are floats
# already short of the chain by 296 wei on this very route, and moments of Rango's workflow rather than block times.
def test_no_quantity_and_no_time_are_taken_from_the_page(monkeypatch, page):
    route = _resolver(monkeypatch, page).resolve(SEND_HASH)

    assert route.sending.qty is None and route.receiving.qty is None
    assert route.sending.timestamp == 0 and route.receiving.timestamp == 0
    assert not route.receiving.is_complete()      # ... so no leg can be built out of it
    assert route.confidence == Confidence.PROPOSED and not route.is_bookable()


# A native coin has no address key at all in the page, which is exactly how JAL keeps it; a token has its contract
def test_the_native_coin_of_a_chain_has_no_address(monkeypatch, page):
    route = _resolver(monkeypatch, page).resolve(SEND_HASH)

    assert route.receiving.symbol == 'AVAX' and route.receiving.address == ''
    assert route.sending.symbol == 'GHO' and route.sending.address == "0xcccc000000000000000000000000000000000001"


# A search answers about whatever route it redirected to. Only the one that names the transaction asked about may be
# used - the same guard LiFiResolver makes, against a different way of ending up with somebody else's move.
def test_a_page_about_another_transaction_is_refused(monkeypatch, page):
    assert _resolver(monkeypatch, page).resolve("0xdead" + "0" * 60) is None


# Rango's index records what a client TOLD it, not what a chain did - records exist for transactions that were never
# mined. A route that didn't succeed has no arrival to point at, whatever it claims about itself.
@pytest.mark.parametrize("status", ['failed', 'running'])
def test_a_route_that_did_not_succeed_is_refused(monkeypatch, page, status):
    assert _resolver_with(monkeypatch, page, 'status', status).resolve(SEND_HASH) is None


# When a route ends in something other than what it set out to deliver, the asset the user actually holds is named in
# a field of its own - a shape no observed record has, so it is refused rather than read wrongly.
def test_a_route_that_delivered_another_asset_is_refused(monkeypatch, page):
    assert _resolver_with(monkeypatch, page, 'outputToken', {'symbol': 'ETH'}).resolve(SEND_HASH) is None


# The destination hash is not a field: it is split out of a rendered URL, and it fails by finding nothing. What is
# left is a route that names no arrival, which is refused by everything downstream rather than half-applied.
def test_a_route_with_no_outbound_link_names_no_arrival(monkeypatch, page):
    inbound = [{'url': f"https://arbiscan.io/tx/{SEND_HASH}", 'description': 'Inbound'}]
    route = _resolver_with(monkeypatch, page, 'explorerUrls', inbound).resolve(SEND_HASH)

    assert route is not None and route.receiving.tx_hash == ''


# ... and so does an Outbound link that points at something which is not a transaction: its last path segment would
# otherwise be compared against the stored hashes as though it were one.
def test_an_outbound_link_without_a_transaction_names_no_arrival(monkeypatch, page):
    stray = [{'url': "https://snowtrace.dev/", 'description': 'Outbound'}]
    route = _resolver_with(monkeypatch, page, 'explorerUrls', stray).resolve(SEND_HASH)

    assert route is not None and route.receiving.tx_hash == ''


# A transaction Rango never saw is answered with 200 and a page that simply has no route in it. So is a page whose
# undocumented format changed under us - and that is the whole reason nothing here may be believed about amounts:
# the failure of this parser is silence, not a wrong number.
def test_a_page_without_a_route_says_nothing(monkeypatch):
    assert _resolver(monkeypatch, _NOT_FOUND).resolve(SEND_HASH) is None
    assert _resolver(monkeypatch, '').resolve(SEND_HASH) is None
