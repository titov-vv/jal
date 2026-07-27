import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from jal.net.route import Confidence, Route, RouteLeg, RouteResolver
from jal.net.route_resolvers import RouteResolvers

HASH = '0x' + 'a' * 64

# ----------------------------------------------------------------------------------------------------------------------
# Several sources are asked because their coverage doesn't overlap - each aggregator knows only the routes it executed
# itself - and they are ranked because they don't know them equally well. What that ranking has to guarantee is
# tested here: the best-informed source that has an answer is the one used, a weaker one is never asked when a
# stronger one already answered, and a caller that needs exact numbers never reaches a source that has none.


# Counts what it was asked, so that "was not reached" can be told apart from "answered nothing"
class _Source(RouteResolver):
    def __init__(self, name: str, confidence: int, knows: bool):
        super().__init__()
        self.name = name
        self.confidence = confidence
        self._knows = knows
        self.asked = 0

    def _request(self, tx_hash: str):
        self.asked += 1
        if not self._knows:
            return None
        return Route(self.name, self.confidence, RouteLeg(chain='1', tx_hash=tx_hash), RouteLeg(chain='2'))


def test_the_best_informed_source_answers_and_the_weaker_one_is_not_asked():
    weak = _Source("weak", Confidence.PROPOSED, knows=True)
    strong = _Source("strong", Confidence.REPORTED, knows=True)

    route = RouteResolvers([weak, strong]).resolve(HASH)

    assert route.source == "strong"
    assert (strong.asked, weak.asked) == (1, 0)


# Coverage is the reason there is more than one: a move the stronger source never saw is exactly when the weaker one
# is worth its round trip.
def test_a_weaker_source_answers_what_the_stronger_one_never_saw():
    weak = _Source("weak", Confidence.PROPOSED, knows=True)
    strong = _Source("strong", Confidence.REPORTED, knows=False)

    route = RouteResolvers([strong, weak]).resolve(HASH)

    assert route.source == "weak"
    assert (strong.asked, weak.asked) == (1, 1)


# A question that compares stated quantities against booked ones is meaningless below REPORTED, and asking anyway
# would both mean nothing and cost the slowest round trip there is.
def test_a_source_below_the_required_confidence_is_never_asked():
    weak = _Source("weak", Confidence.PROPOSED, knows=True)
    strong = _Source("strong", Confidence.REPORTED, knows=False)

    assert RouteResolvers([weak, strong]).resolve(HASH, Confidence.REPORTED) is None
    assert (strong.asked, weak.asked) == (1, 0)


# One transaction is asked about once per run: a sweep over the pending legs and the dialog the user then opens on
# one of them are the same question, and every source charges a network request for it.
def test_one_transaction_is_asked_about_once():
    source = _Source("source", Confidence.REPORTED, knows=True)
    resolvers = RouteResolvers([source])

    assert resolvers.resolve(HASH).source == resolvers.resolve(HASH.upper()).source
    assert source.asked == 1


# An operation entered by hand names no transaction, and there is nothing to ask about it
def test_nothing_is_asked_about_an_operation_with_no_transaction():
    source = _Source("source", Confidence.REPORTED, knows=True)

    assert RouteResolvers([source]).resolve('') is None
    assert source.asked == 0
