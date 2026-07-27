from jal.net.lifi import LiFiResolver
from jal.net.rango import RangoResolver
from jal.net.route import Confidence


# ----------------------------------------------------------------------------------------------------------------------
# The sources JAL can ask "what arrived for this outgoing transaction?", asked best-informed first.
#
# There is more than one because their coverage does not overlap: each aggregator knows only the routes it executed
# itself, so a move one answers 404 for is commonly one another has in full. And they are ranked rather than merged
# because they do not know it equally well - see Confidence in jal/net/route.py. The first source that has an answer
# wins, which means a weaker one is only ever reached for a transaction the stronger ones never saw, and it can
# therefore never override anything.
#
# 'min_confidence' is how a caller says what it needs the answer FOR. A question that compares stated quantities
# against booked ones (the swap audit) is meaningless below REPORTED and must not ask the sources that cannot answer
# it - which also spares the network round trip, since the weak sources are exactly the expensive ones.
class RouteResolvers:
    def __init__(self, resolvers: list = None):
        if resolvers is None:
            resolvers = [LiFiResolver(), RangoResolver()]
        self._resolvers = sorted(resolvers, key=lambda resolver: resolver.confidence, reverse=True)

    def resolve(self, tx_hash: str, min_confidence: int = Confidence.PROPOSED):
        for resolver in self._resolvers:
            if resolver.confidence < min_confidence:
                break     # sorted by confidence, so nothing below this one qualifies either
            route = resolver.resolve(tx_hash)
            if route is not None:
                return route
        return None
