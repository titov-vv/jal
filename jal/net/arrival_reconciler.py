import logging
from decimal import Decimal

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation
from jal.db.account import JalAccount
from jal.db.bridge_matcher import BridgeMatcher
from jal.db.db import JalDB
from jal.db.helpers import local_timestamp, remove_exponent
from jal.db.symbol import JalSymbol
from jal.db.transfer_settlement import TransferSettlement
from jal.net.route import Confidence
from jal.net.route_resolvers import RouteResolvers


# ----------------------------------------------------------------------------------------------------------------------
# What a route source knows about a pending leg, expressed in JAL's own terms.
#
# 'leg' is the arriving leg ready to be adopted (BridgeMatcher.match_with_leg) - or None, and then 'problem' says why
# the arrival cannot be placed although it is known: the chain it landed on, the account that received it or the token
# itself may be things JAL has no record of, or the source may be one whose numbers may not be booked at all. That is
# not a failure to be hidden - it is the most useful thing the lookup can say, because it names exactly what the user
# has to create for the operation to be completable.
# 'text' describes the arrival either way, so the user always sees what really happened to the money.
class ArrivalProposal:
    def __init__(self, route, leg=None, problem: str = '', text: str = ''):
        self.route = route            # the Route this was built from - it names its own source
        self.leg = leg                # {'account_id', 'asset_id', 'symbol_id', 'qty', 'timestamp', 'tx_hash'} or None
        self.problem = problem        # '' when the leg can be adopted as it is
        self.text = text              # human description of the arrival, whether it can be placed or not

    def is_placeable(self) -> bool:
        return self.leg is not None


# ----------------------------------------------------------------------------------------------------------------------
# Uses what a routing aggregator recorded to finish - and to check - the cross-chain operations JAL could only see one
# end of. It is the bridge between the route sources (jal/net/route_resolvers.py), which know nothing of JAL, and the
# database, which knows nothing of them: chains become accounts, contract addresses become symbols, and the UTC
# seconds a chain stamped become the local wall clock JAL stores.
#
# Three things are done with that:
#   * a pending half-bridge is completed from the reported arrival, even when the destination chain has never been
#     fetched (and even when JAL has no fetcher for it at all) - see arrival_of_half();
#   * two pending transfer legs are settled when a source names them as the two ends of one move - see
#     settle_pending_transfers(). Bridges and transfers are the two consumers of the same question, and neither the
#     question nor the sources that answer it know which of them is asking;
#   * a stored Swap is checked against the route it really was - see audit_swaps(). This is not a nicety: a route that
#     delivers on another chain commonly ALSO pays the wallet something on the SOURCE chain (a slice of the output, a
#     rebate, the remainder of a partial fill), and that payout is the only incoming asset the sending transaction has.
#     The transaction therefore looks exactly like a small same-chain swap to a classifier that sees one chain, and
#     booking it as one disposes of the whole sent amount for that payout alone, realizing a loss that never happened.
#
# Only what a transaction hash PROVES is applied without asking (settle_pending_transfers, which pairs two records JAL
# already holds). Everything that would create a leg out of what was reported is proposed and left to the user
# (BridgeMatchDialog) - a wrong counter-leg mis-books money exactly as badly as a missing one.
class ArrivalReconciler(QObject):
    def __init__(self, resolvers=None):
        super().__init__()
        self._resolvers = resolvers if resolvers is not None else RouteResolvers()

    def tr(self, text):
        return QApplication.translate("ArrivalReconciler", text)

    # ------------------------------------------------------------------------------------------------------------------
    # What the route sources report as the arrival of the pending half 'half_oid', or None when none of them has
    # anything to say about the sending transaction (it was routed by somebody else, or it is not a cross-chain move).
    def arrival_of_half(self, half_oid) -> ArrivalProposal:
        half = JalDB._read("SELECT out_tx_hash, out_timestamp, out_account_id FROM bridges "
                           "WHERE oid=:oid AND in_account_id IS NULL", [(":oid", half_oid)], named=True)
        if not half or not half['out_tx_hash']:
            return None
        route = self._resolvers.resolve(half['out_tx_hash'])
        if route is None:
            return None
        # A route that begins and ends on the same chain has no counter-leg to adopt: whatever it did happened in the
        # sending transaction alone, and a pending half standing for it is a classification to revisit, not a bridge
        # to complete. Saying so is more useful than silently offering nothing.
        if not route.is_cross_chain():
            return ArrivalProposal(route, problem=route.source + self.tr(" reports this transaction as a same-chain "
                                                                         "exchange, not a cross-chain move"),
                                   text=self._describe(route))
        return self._proposal(route)

    # Completes the pending half from what was reported and returns the oid of the resulting operation (a complete
    # bridge, or the cross-chain swap that replaces the half when the asset changed on the way). Raises
    # BridgeMatchError through BridgeMatcher if the pair cannot form a valid operation; the caller rebuilds the ledger.
    def complete_half(self, half_oid) -> int:
        proposal = self.arrival_of_half(half_oid)
        if proposal is None or not proposal.is_placeable():
            return 0
        return BridgeMatcher().match_with_leg(half_oid, proposal.leg)

    # Turns the arriving end of a route into an adoptable leg, or explains what stands in the way.
    def _proposal(self, route) -> ArrivalProposal:
        arrival = route.receiving
        text = self._describe(route)
        # A source below the REPORTED tier states what arrived only as an approximation of it - a rounded amount and
        # a time of its own workflow rather than of the block (see jal/net/route.py). Such an answer may point at
        # something JAL already holds; booking a leg out of it would write that approximation into the ledger.
        if not route.is_bookable() or not arrival.is_complete():
            return ArrivalProposal(route, problem=route.source + self.tr(" names the transaction the assets arrived "
                                                                         "in but not what arrived - only the chain "
                                                                         "itself can say that"), text=text)
        if arrival.location_id == AssetLocation.UNDEFINED:
            return ArrivalProposal(route, problem=self.tr("The assets arrived on a chain JAL doesn't know: ")
                                   + f"{arrival.chain}", text=text)
        account = self._wallet_account(arrival.location_id, route.to_address)
        if account is None:
            # The address is the arrival's own fact - a route may deliver to any address it was told to - so this is
            # equally "you have no account for this chain yet" and "this went somewhere that isn't yours". Both are
            # worth the user's attention, and neither may be guessed around.
            return ArrivalProposal(route, problem=self.tr("JAL has no wallet account for the address the assets "
                                                          "were delivered to: ") + route.to_address, text=text)
        symbol_id = self._symbol_id(arrival.location_id, arrival.address, arrival.symbol)
        if not symbol_id:
            named = f"{arrival.symbol} ({arrival.address})" if arrival.address else arrival.symbol
            return ArrivalProposal(route, problem=self.tr("JAL doesn't know the token that arrived: ") + named,
                                   text=text)
        leg = {'account_id': account.id(), 'symbol_id': symbol_id,
               'asset_id': JalSymbol(symbol_id).asset().id(), 'qty': arrival.qty,
               'timestamp': local_timestamp(arrival.timestamp), 'tx_hash': arrival.tx_hash}
        return ArrivalProposal(route, leg=leg, text=text)

    # ------------------------------------------------------------------------------------------------------------------
    # Settles the pending transfer legs whose counterpart a route source can name, and returns (settled, findings).
    #
    # A transfer stored knowing only where it went FROM waits for the record of its other end, and the two are paired
    # by the transaction they name (jal/db/transfer_settlement.py). That works when both ends are the same transaction
    # - one wallet's fetch seeing the send, another's seeing the arrival. A cross-chain move is not: it is two
    # transactions on two chains with nothing on either of them pointing at the other, so the two legs sit pending
    # forever no matter how many wallets are fetched. Only whoever routed the move can join them, and joining them is
    # all that is taken from it: what the pair moves, when and how much is what JAL already holds from the chains.
    #
    # This is applied without asking because the destination transaction hash is proof rather than a resemblance - the
    # same rule that lets TransferSettlement pair on a hash. When the two legs turn out not to form one transfer after
    # all, that is reported instead: a cross-chain route that delivers less than it was sent is a bridge, and a bridge
    # is an operation of its own that this may not silently create.
    #
    # 'progress' is called with (checked so far, total) before each leg, as one network request is made per leg.
    #
    # 'interrupted' is asked before each leg as well, and a True from it ends the pass. What was settled up to that
    # point is RETURNED rather than discarded.
    def settle_pending_transfers(self, progress=None, interrupted=None) -> tuple:
        settlement = TransferSettlement()
        pending = settlement.pending_sending_legs()
        settled, findings = 0, []
        for i, leg in enumerate(pending):
            if interrupted is not None and interrupted():
                break
            if progress is not None:
                progress(i, len(pending))
            route = self._resolvers.resolve(leg['number'])
            if route is None or not route.is_cross_chain() or not route.receiving.tx_hash:
                continue
            counterpart = settlement.pending_arrival_of(route.receiving.tx_hash, leg['asset_id'])
            if counterpart is None:
                continue
            refusal = settlement.settle_linked(leg['oid'], counterpart)
            if not refusal:
                settled += 1
                continue
            findings.append(f"{route.source} " + self.tr("routed transfers") + f" #{leg['oid']} + #{counterpart} "
                            + self.tr("as one move") + f" ({leg['number'][:12]}...), "
                            + self.tr("but they can't be settled into one: ") + refusal)
        return settled, findings

    # ------------------------------------------------------------------------------------------------------------------
    # Checks stored Swaps against the routes they really were and returns a list of complaints, each naming one swap.
    # Swaps are checked from 'from_oid' upwards so that a run only pays for what it has not seen before; the highest
    # oid examined is returned with the findings, to be stored as the next run's starting point.
    #
    # Only a swap that carries the hash of the transaction it came from can be checked at all - one entered by hand
    # names no transaction to ask about.
    #
    # 'progress' is called with (checked so far, total) before each swap: one network request is made per swap, so the
    # first run - which goes through the whole history - takes long enough that it has to say what it is doing.
    #
    # 'interrupted' is asked before each swap and ends the run when it answers True. The returned 'last_oid' then
    # covers exactly the swaps that WERE checked.
    def audit_swaps(self, from_oid: int = 0, progress=None, interrupted=None) -> tuple:
        findings = []
        last_oid = from_oid
        # The whole list is read before anything is asked over the network: the checks below run queries of their own,
        # which would invalidate a query still being stepped through.
        query = JalDB._exec("SELECT oid, tx_hash, account_id, in_account_id, in_symbol_id, in_qty, out_symbol_id, "
                            "out_qty FROM swaps WHERE oid>:oid AND tx_hash<>'' ORDER BY oid",
                            [(":oid", from_oid)])
        rows = []
        while query.next():
            rows.append(JalDB._read_record(query, named=True))
        for i, row in enumerate(rows):
            if interrupted is not None and interrupted():
                break
            if progress is not None:
                progress(i, len(rows))
            last_oid = max(last_oid, int(row['oid']))
            complaint = self._swap_complaint(row)
            if complaint:
                findings.append(complaint)
        return last_oid, findings

    # What is wrong with one stored swap according to the route it came from, or '' when the two agree (and when no
    # source knows the transaction, which is the ordinary case for a swap routed by somebody none of them covers).
    #
    # The comparison is between what a source STATES and what the ledger holds, so it is asked of the sources that
    # state it exactly and of no others: a rounded quantity would disagree with a correctly booked one and produce a
    # complaint about nothing.
    def _swap_complaint(self, row: dict) -> str:
        route = self._resolvers.resolve(row['tx_hash'], Confidence.REPORTED)
        if route is None:
            return ''
        where = self.tr("Swap") + f" #{row['oid']} ({row['tx_hash'][:12]}...)"
        booked_cross_chain = bool(row['in_account_id']) and int(row['in_account_id']) != int(row['account_id'])
        if route.is_cross_chain() and not booked_cross_chain:
            # The severe case: what the assets were exchanged for left this chain, so whatever the transaction paid
            # back here is a part of the move and not what it was exchanged for. Booked as a same-chain swap, the
            # whole sent amount is disposed of for that part alone. What the payout on the source chain IS - a slice
            # of the output, a rebate, the remainder of a partial fill - is not something either source says, and it
            # is not guessed at here: only the two amounts are stated, and they are enough to see that they disagree.
            return where + self.tr(" is booked as a same-chain exchange, but ") + route.source \
                + self.tr(" reports a cross-chain move: ") + self._describe(route) \
                + self.tr(". What is booked as received is only what the transaction paid back on the source chain")
        if route.is_cross_chain():
            return ''    # already a cross-chain swap - its arriving leg is checked when that chain is fetched
        return self._quantity_complaint(where, route, row)

    # A same-chain swap must move exactly what the route moved. A difference means the transaction did something the
    # classifier read differently, so it is reported rather than corrected - which of the two readings is right is not
    # something this can decide.
    def _quantity_complaint(self, where: str, route, row: dict) -> str:
        for leg, symbol_id, qty, side in ((route.sending, row['out_symbol_id'], row['out_qty'], self.tr("sent")),
                                          (route.receiving, row['in_symbol_id'], row['in_qty'],
                                           self.tr("received"))):
            stored_symbol = JalSymbol(symbol_id)
            if leg.qty != Decimal(qty) or (leg.symbol and leg.symbol.upper() != stored_symbol.symbol().upper()):
                return where + self.tr(" says ") + f"{remove_exponent(Decimal(qty))} {stored_symbol.symbol()} " \
                    + side + self.tr(", while ") + route.source + self.tr(" reports ") \
                    + f"{remove_exponent(leg.qty)} {leg.symbol}"
        return ''

    # ------------------------------------------------------------------------------------------------------------------
    # The wallet account holding 'address' on the given chain, or None when there is no single such account - the
    # same question a pending leg asks about the address it recorded, and answered in one place for both.
    @staticmethod
    def _wallet_account(location_id: int, address: str):
        return JalAccount.at_address(location_id, address)

    # The listing (symbol) of the arrived token on its chain: by contract address for a token - the only identity of a
    # token that can be trusted - and by ticker for the chain's own coin, which has no contract behind it and is
    # created by the fetchers under that ticker alone.
    @staticmethod
    def _symbol_id(location_id: int, address: str, ticker: str) -> int:
        if address:
            id_type = AssetLocation.address_id_of(location_id)
            if id_type is None:
                return 0
            return JalSymbol.find_by_identifier(id_type, address).id()
        if not ticker:
            return 0
        symbol_id = JalDB._read("SELECT id FROM asset_symbol WHERE location_id=:location AND symbol=:ticker",
                                [(":location", location_id), (":ticker", ticker)], check_unique=True)
        return int(symbol_id) if symbol_id else 0

    # "211.607214 USDC on Arbitrum (via relaydepository), tx 0x1444...". The tool is the liquidity source the route
    # went through, not a contract the wallet called - it is shown because it is how the user recognizes the operation
    # in the aggregator's own history, never because anything is decided by it. A source that states no quantity says
    # only which token arrived where, which is all it is allowed to be believed about.
    def _describe(self, route) -> str:
        arrival = route.receiving
        chain = AssetLocation().get_name(arrival.location_id) if arrival.location_id else f"chain {arrival.chain}"
        via = f" ({self.tr('via')} {route.tool})" if route.tool else ''
        amount = f"{remove_exponent(arrival.qty)} " if arrival.qty is not None else ''
        return f"{amount}{arrival.symbol} " + self.tr("on") + f" {chain}{via}, {arrival.tx_hash[:12]}..."


# Reports what an audit found the way the fetchers report what they could not import: through the log, so that it is
# kept, and never as an exception - a check that fails must not take a successful import down with it.
def log_findings(findings: list) -> None:
    for finding in findings:
        logging.warning(finding)
