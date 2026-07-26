import logging
from decimal import Decimal

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from jal.constants import AssetLocation, PredefinedAccountType
from jal.db.account import JalAccount
from jal.db.bridge_matcher import BridgeMatcher
from jal.db.db import JalDB
from jal.db.helpers import remove_exponent
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import normalize_address
from jal.net.chain_fetchers.fetcher import local_timestamp
from jal.net.lifi import LiFiResolver


# ----------------------------------------------------------------------------------------------------------------------
# What LI.FI knows about a pending half-bridge, expressed in JAL's own terms.
#
# 'leg' is the arriving leg ready to be adopted (BridgeMatcher.match_with_leg) - or None, and then 'problem' says why
# the arrival cannot be placed although it is known: the chain it landed on, the account that received it or the token
# itself may be things JAL has no record of. That is not a failure to be hidden - it is the most useful thing the
# lookup can say, because it names exactly what the user has to create for the operation to be completable.
# 'text' describes the arrival either way, so the user always sees what really happened to the money.
class ArrivalProposal:
    def __init__(self, transfer, leg=None, problem: str = '', text: str = ''):
        self.transfer = transfer      # the LiFiTransfer this was built from
        self.leg = leg                # {'account_id', 'asset_id', 'symbol_id', 'qty', 'timestamp', 'tx_hash'} or None
        self.problem = problem        # '' when the leg can be adopted as it is
        self.text = text              # human description of the arrival, whether it can be placed or not

    def is_placeable(self) -> bool:
        return self.leg is not None


# ----------------------------------------------------------------------------------------------------------------------
# Uses what a routing aggregator recorded to finish - and to check - the cross-chain operations JAL could only see one
# end of. It is the bridge between jal/net/lifi.py, which knows nothing of JAL, and the database, which knows nothing
# of LI.FI: chain ids become accounts, contract addresses become symbols, integer amounts become quantities and UTC
# seconds become the local wall clock JAL stores.
#
# Two things are done with that:
#   * a pending half-bridge is completed from the arrival LI.FI reports, even when the destination chain has never
#     been fetched (and even when JAL has no fetcher for it at all) - see arrival_of_half();
#   * a stored Swap is checked against the route it really was - see audit_swaps(). This is not a nicety: a route that
#     delivers on another chain commonly ALSO pays the wallet something on the SOURCE chain (a slice of the output, a
#     rebate, the remainder of a partial fill), and that payout is the only incoming asset the sending transaction has.
#     The transaction therefore looks exactly like a small same-chain swap to a classifier that sees one chain, and
#     booking it as one disposes of the whole sent amount for that payout alone, realizing a loss that never happened.
#
# Nothing here books anything on its own: it proposes, and reports. What is applied is applied by the caller, which is
# the user's choice (BridgeMatchDialog) - a wrong counter-leg mis-books money exactly as badly as a missing one.
class LiFiReconciler(QObject):
    def __init__(self, resolver=None):
        super().__init__()
        self._resolver = resolver if resolver is not None else LiFiResolver()

    def tr(self, text):
        return QApplication.translate("LiFiReconciler", text)

    # ------------------------------------------------------------------------------------------------------------------
    # What LI.FI reports as the arrival of the pending half 'half_oid', or None when it has nothing to say about the
    # sending transaction (it was not routed by LI.FI, or the route is not a cross-chain one).
    def arrival_of_half(self, half_oid) -> ArrivalProposal:
        half = JalDB._read("SELECT out_tx_hash, out_timestamp, out_account_id FROM bridges "
                           "WHERE oid=:oid AND in_account_id IS NULL", [(":oid", half_oid)], named=True)
        if not half or not half['out_tx_hash']:
            return None
        transfer = self._resolver.resolve(half['out_tx_hash'])
        if transfer is None:
            return None
        # A route that begins and ends on the same chain has no counter-leg to adopt: whatever it did happened in the
        # sending transaction alone, and a pending half standing for it is a classification to revisit, not a bridge
        # to complete. Saying so is more useful than silently offering nothing.
        if not transfer.is_cross_chain():
            return ArrivalProposal(transfer, problem=self.tr("LI.FI reports this transaction as a same-chain "
                                                             "exchange, not a cross-chain move"),
                                   text=self._describe(transfer))
        return self._proposal(transfer)

    # Completes the pending half from what LI.FI reports and returns the oid of the resulting operation (a complete
    # bridge, or the cross-chain swap that replaces the half when the asset changed on the way). Raises
    # BridgeMatchError through BridgeMatcher if the pair cannot form a valid operation; the caller rebuilds the ledger.
    def complete_half(self, half_oid) -> int:
        proposal = self.arrival_of_half(half_oid)
        if proposal is None or not proposal.is_placeable():
            return 0
        return BridgeMatcher().match_with_leg(half_oid, proposal.leg)

    # Turns the arriving end of a route into an adoptable leg, or explains what stands in the way.
    def _proposal(self, transfer) -> ArrivalProposal:
        arrival = transfer.receiving
        text = self._describe(transfer)
        if arrival.location_id == AssetLocation.UNDEFINED:
            return ArrivalProposal(transfer, problem=self.tr("The assets arrived on a chain JAL doesn't know: ")
                                   + f"{arrival.chain_id}", text=text)
        account = self._wallet_account(arrival.location_id, transfer.to_address)
        if account is None:
            # The address is the arrival's own fact - a route may deliver to any address it was told to - so this is
            # equally "you have no account for this chain yet" and "this went somewhere that isn't yours". Both are
            # worth the user's attention, and neither may be guessed around.
            return ArrivalProposal(transfer, problem=self.tr("JAL has no wallet account for the address the assets "
                                                             "were delivered to: ") + transfer.to_address, text=text)
        symbol_id = self._symbol_id(arrival.location_id, arrival.address, arrival.symbol)
        if not symbol_id:
            named = f"{arrival.symbol} ({arrival.address})" if arrival.address else arrival.symbol
            return ArrivalProposal(transfer, problem=self.tr("JAL doesn't know the token that arrived: ") + named,
                                   text=text)
        leg = {'account_id': account.id(), 'symbol_id': symbol_id,
               'asset_id': JalSymbol(symbol_id).asset().id(), 'qty': arrival.qty,
               'timestamp': local_timestamp(arrival.timestamp), 'tx_hash': arrival.tx_hash}
        return ArrivalProposal(transfer, leg=leg, text=text)

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
    def audit_swaps(self, from_oid: int = 0, progress=None) -> tuple:
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
            if progress is not None:
                progress(i, len(rows))
            last_oid = max(last_oid, int(row['oid']))
            complaint = self._swap_complaint(row)
            if complaint:
                findings.append(complaint)
        return last_oid, findings

    # What is wrong with one stored swap according to LI.FI, or '' when the two agree (and when LI.FI knows nothing
    # about the transaction, which is the ordinary case for a swap routed anywhere else).
    def _swap_complaint(self, row: dict) -> str:
        transfer = self._resolver.resolve(row['tx_hash'])
        if transfer is None:
            return ''
        where = self.tr("Swap") + f" #{row['oid']} ({row['tx_hash'][:12]}...)"
        booked_cross_chain = bool(row['in_account_id']) and int(row['in_account_id']) != int(row['account_id'])
        if transfer.is_cross_chain() and not booked_cross_chain:
            # The severe case: what the assets were exchanged for left this chain, so whatever the transaction paid
            # back here is a part of the move and not what it was exchanged for. Booked as a same-chain swap, the
            # whole sent amount is disposed of for that part alone. What the payout on the source chain IS - a slice
            # of the output, a rebate, the remainder of a partial fill - is not something either source says, and it
            # is not guessed at here: only the two amounts are stated, and they are enough to see that they disagree.
            return where + self.tr(" is booked as a same-chain exchange, but LI.FI reports a cross-chain move: ") \
                + self._describe(transfer) \
                + self.tr(". What is booked as received is only what the transaction paid back on the source chain")
        if transfer.is_cross_chain():
            return ''    # already a cross-chain swap - its arriving leg is checked when that chain is fetched
        return self._quantity_complaint(where, transfer, row)

    # A same-chain swap must move exactly what the route moved. A difference means the transaction did something the
    # classifier read differently, so it is reported rather than corrected - which of the two readings is right is not
    # something this can decide.
    def _quantity_complaint(self, where: str, transfer, row: dict) -> str:
        for leg, symbol_id, qty, side in ((transfer.sending, row['out_symbol_id'], row['out_qty'], self.tr("sent")),
                                          (transfer.receiving, row['in_symbol_id'], row['in_qty'],
                                           self.tr("received"))):
            stored_symbol = JalSymbol(symbol_id)
            if leg.qty != Decimal(qty) or (leg.symbol and leg.symbol.upper() != stored_symbol.symbol().upper()):
                return where + self.tr(" says ") + f"{remove_exponent(Decimal(qty))} {stored_symbol.symbol()} " \
                    + side + self.tr(", while LI.FI reports ") + f"{remove_exponent(leg.qty)} {leg.symbol}"
        return ''

    # ------------------------------------------------------------------------------------------------------------------
    # The wallet account holding 'address' on the given chain, or None when there is no single such account. Both the
    # chain and the address must match: one address is commonly registered once per chain, and the assets a transfer
    # moves stay on the chain they arrived on (see ChainFetcher._own_wallet, which resolves the same thing for a
    # fetcher). An address matching several accounts of one chain is left unresolved - nothing here can tell which.
    @staticmethod
    def _wallet_account(location_id: int, address: str):
        address = normalize_address(location_id, address)
        if not address:
            return None
        matched = [x for x in JalAccount.get_all_accounts(active_only=True)
                   if x.account_type() == PredefinedAccountType.Wallet and x.chain() == location_id
                   and normalize_address(location_id, x.address()) == address]
        return matched[0] if len(matched) == 1 else None

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

    # "211.607214 USDC on Arbitrum (via relaydepository), tx 0x1444...". The tool is the liquidity source LI.FI routed
    # through, not a contract the wallet called - it is shown because it is how the user recognizes the operation in
    # the aggregator's own history, never because anything is decided by it.
    def _describe(self, transfer) -> str:
        arrival = transfer.receiving
        chain = AssetLocation().get_name(arrival.location_id) if arrival.location_id else f"chain {arrival.chain_id}"
        via = f" ({self.tr('via')} {transfer.tool})" if transfer.tool else ''
        return f"{remove_exponent(arrival.qty)} {arrival.symbol} " + self.tr("on") \
            + f" {chain}{via}, {arrival.tx_hash[:12]}..."


# Reports what an audit found the way the fetchers report what they could not import: through the log, so that it is
# kept, and never as an exception - a check that fails must not take a successful import down with it.
def log_findings(findings: list) -> None:
    for finding in findings:
        logging.warning(finding)
