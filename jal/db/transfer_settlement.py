import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from jal.db.db import JalDB
from jal.db.helpers import remove_exponent


# ----------------------------------------------------------------------------------------------------------------------
# Settles one-legged transfers by pairing the two records of one and the same movement.
#
# A transfer may be stored knowing only one of its ends (see the description of 'transfers' in jal_init.sql): the
# import doesn't ask which account the other end is, it records that it isn't known. The counterpart usually turns up
# later - as the fetch of the wallet on the other side, or as the statement of the exchange that sent the money - and
# then JAL holds two one-legged records of one movement, each knowing the end the other doesn't.
#
# What makes them mergeable without guessing is the TRANSACTION HASH. Amount and date proximity is a heuristic and
# stays the user's decision (that is the manual matcher), but two records that name the same transaction and the same
# asset are records of the same movement - that is proof, not a resemblance. So this pass runs automatically after
# every import that can vouch for its 'number' being a transaction hash
# (Statement._transfers_are_unique_per_transaction), and it commits what it finds without asking.
#
# The rule is deliberately narrow, because the one thing a transaction hash does NOT identify is a single movement:
# one transaction may pay several addresses, and a multisend from the user's wallet leaves one pending leg per
# recipient it couldn't resolve. A group is therefore settled only when the transaction moved that asset EXACTLY
# TWICE as far as JAL can see - once out of an account with no known destination, once into an account with no known
# source - and the two agree on the quantity. Anything more ambiguous is left for the user to pair by hand.
#
# The other shape of the same problem - a record that knows BOTH ends meeting a stored pending leg - cannot be settled
# here, because within one import "A -> ?" and "A -> B" of the same transaction and amount is exactly what a multisend
# to two addresses looks like. It is handled at import time instead, bounded to legs stored by an EARLIER import:
# Transfer.find_pending_counterpart() and Statement._transfer_completes_pending().
class TransferSettlement(JalDB):
    def __init__(self):
        super().__init__()

    def tr(self, text):
        return QApplication.translate("TransferSettlement", text)

    # Pairs every unambiguous pair of pending legs in the database. Returns the number of transfers settled.
    def settle_all(self) -> int:
        settled = 0
        for records in self._movements_with_a_pending_leg():
            pair = self._pairable(records)
            if pair is None:
                continue
            self._merge(*pair)
            settled += 1
        return settled

    # Records of movements at least one of whose legs is pending, grouped by the transaction and the asset they moved:
    # one transaction may deliver several assets at once (a token plus a gas top-up) and each of those is a movement of
    # its own. Only records that name a transaction and an asset take part - a money transfer's 'number' is a free-form
    # reference, which identifies nothing.
    def _movements_with_a_pending_leg(self) -> list:
        groups = {}
        query = self._exec(
            "SELECT oid, withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, deposit_account, "
            "deposit, fee_account, fee, fee_symbol_id, number, symbol_id, note FROM transfers AS t "
            "WHERE t.number!='' AND NOT t.symbol_id IS NULL AND EXISTS "
            "(SELECT 1 FROM transfers AS p WHERE p.number=t.number AND p.symbol_id=t.symbol_id "
            "AND (p.withdrawal_account IS NULL OR p.deposit_account IS NULL)) ORDER BY t.oid")
        while query.next():
            record = self._read_record(query, named=True)
            groups.setdefault((record['number'], record['symbol_id']), []).append(record)
        return list(groups.values())

    # The (sending, arriving) pair the records of one movement form, or None if they don't form one unambiguously.
    def _pairable(self, records: list):
        if len(records) != 2:
            if len(records) > 2:
                logging.info(self.tr("Transaction moved the same asset more than once, settle it by hand: ")
                             + f"{records[0]['number']}")
            return None
        sent = [x for x in records if x['withdrawal_account'] and not x['deposit_account']]
        arrived = [x for x in records if x['deposit_account'] and not x['withdrawal_account']]
        if len(sent) != 1 or len(arrived) != 1:
            return None   # both records miss the same end, or one of them is complete - neither is a pair to settle
        sent, arrived = sent[0], arrived[0]
        return None if self._refusal(sent, arrived) else (sent, arrived)

    # Why the two pending legs cannot be folded into one transfer, or '' when they can. It is a sentence rather than a
    # flag because the caller that pairs legs on a HASH has already proved they belong together: a refusal there is
    # not "these are unrelated" but "this movement is not what a transfer can express", and the user has to be told
    # which of the two it was.
    def _refusal(self, sent: dict, arrived: dict) -> str:
        # One wallet may both send and receive the same asset in one transaction (a contract passing money through
        # it), and those two legs are not a transfer of the account to itself
        if int(sent['withdrawal_account']) == int(arrived['deposit_account']):
            return self.tr("both legs are on the same account")
        if Decimal(sent['withdrawal']) != Decimal(arrived['withdrawal']):
            # A transfer carries ONE quantity - what left is what arrived. A move that delivers less than it was sent
            # is a bridge (which has a leg of its own for each side) and must be booked as one.
            return self.tr("what arrived isn't what was sent, so this is not a transfer: ") \
                + f"{remove_exponent(Decimal(sent['withdrawal']))} -> {remove_exponent(Decimal(arrived['withdrawal']))}"
        if int(sent['withdrawal_timestamp']) > int(arrived['deposit_timestamp']):
            return self.tr("the arrival precedes the departure")
        return ''

    # ------------------------------------------------------------------------------------------------------------------
    # The two ends of a CROSS-CHAIN move are two different transactions, so the pass above can never pair them: each
    # leg names its own chain's transaction and nothing on either chain points at the other. Only whoever routed the
    # move knows they belong together, and the three methods below are how that answer is applied - see
    # ArrivalReconciler.settle_pending_transfers(), which is the only caller and the only place that asks a network.

    # Pending SENDING legs - the money left, where it went is unknown - that name the transaction they left in and
    # could be paired with something, each as {'oid', 'number', 'asset_id'}. A money transfer's 'number' identifies
    # nothing, so it doesn't take part.
    #
    # "Could be paired with something" is a pending ARRIVING leg of the same asset existing at all, and it is what
    # keeps the cost of asking bounded: every leg in this list costs a network request per source, the list is swept
    # again after every fetch, and a leg whose counterpart has never been imported has nothing to be joined to no
    # matter what any source answers about it. Unlike the swap audit there is no cursor to remember instead - a leg
    # that was hopeless last time becomes settleable the moment its other end is fetched.
    def pending_sending_legs(self) -> list:
        legs = []
        query = self._exec("SELECT t.oid, t.number, s.asset_id FROM transfers AS t "
                           "JOIN asset_symbol AS s ON s.id=t.symbol_id "
                           "WHERE t.deposit_account IS NULL AND t.number!='' AND EXISTS "
                           "(SELECT 1 FROM transfers AS p JOIN asset_symbol AS ps ON ps.id=p.symbol_id "
                           "WHERE p.withdrawal_account IS NULL AND ps.asset_id=s.asset_id) ORDER BY t.oid")
        while query.next():
            oid, number, asset_id = self._read_record(query, cast=[int, str, int])
            legs.append({'oid': oid, 'number': number, 'asset_id': asset_id})
        return legs

    # The oid of the pending ARRIVING leg of the given transaction and asset, or None when there is no single one.
    # The asset - not the symbol - is what is matched: the two ends of a cross-chain move are two listings of one
    # token (cross-chain unification merges them), so the symbols differ and the asset doesn't. The hash is compared
    # as it is stored, without case folding: chains disagree on the case of a hash and a wrong pair is worse than a
    # missed one.
    def pending_arrival_of(self, tx_hash: str, asset_id: int):
        oid = self._read("SELECT t.oid FROM transfers AS t JOIN asset_symbol AS s ON s.id=t.symbol_id "
                         "WHERE t.withdrawal_account IS NULL AND t.number=:hash AND s.asset_id=:asset",
                         [(":hash", tx_hash), (":asset", asset_id)], check_unique=True)
        return int(oid) if oid else None

    # Settles two pending legs that a route source named as the two ends of one movement. Returns '' when they were
    # merged, and otherwise why they were not - the pair is proven, so a refusal is something to tell the user about
    # rather than to pass over in silence.
    def settle_linked(self, sending_oid: int, arriving_oid: int) -> str:
        sent = self._pending_leg(sending_oid, 'deposit_account')
        arrived = self._pending_leg(arriving_oid, 'withdrawal_account')
        if not sent or not arrived:
            return self.tr("one of the legs is no longer pending")
        refusal = self._refusal(sent, arrived)
        if refusal:
            return refusal
        self._merge(sent, arrived)
        return ''

    # One transfer record, but only while the named end of it is still unknown - what was true when the sources were
    # asked may have been settled by anything else since.
    def _pending_leg(self, oid: int, unknown_end: str):
        return self._read("SELECT oid, withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, "
                          "deposit_account, deposit, fee_account, fee, fee_symbol_id, number, symbol_id, note "
                          f"FROM transfers WHERE oid=:oid AND {unknown_end} IS NULL", [(":oid", oid)], named=True)

    # ------------------------------------------------------------------------------------------------------------------
    # Folds the arriving record into the sending one, which is the record to keep: the gas of an on-chain movement is
    # paid by the sender, so that is the side that carries the fee and the earlier of the two timestamps.
    def _merge(self, sent: dict, arrived: dict) -> None:
        # 'deposit' of an asset transfer is a cost basis, not an amount, and only a cross-currency pair reads it (see
        # Transfer.processAssetTransfer). Neither leg of a fetched movement states one, so it stays 0 - and a
        # cross-currency pair then opens its destination lots at ZERO cost basis, which is visible in every holdings
        # and deals report rather than being a quietly converted guess.
        # FIXME Deriving the basis from the quote of the moved asset at the moment of the transfer would settle such a
        #  pair properly; revisit together with the cost-basis handling of the tax reports.
        deposit = Decimal(sent['deposit']) or Decimal(arrived['deposit'])
        self._exec("UPDATE transfers SET deposit_account=:account, deposit_timestamp=:timestamp, deposit=:deposit, "
                   "note=:note WHERE oid=:oid",
                   [(":account", int(arrived['deposit_account'])), (":timestamp", int(arrived['deposit_timestamp'])),
                    (":deposit", deposit), (":note", sent['note'] if sent['note'] else arrived['note']),
                    (":oid", int(sent['oid']))])
        # A fee an earlier record didn't know about is adopted rather than dropped with the row that brought it - the
        # same reason Transfer.update_fee() exists. An existing fee is never overwritten: a movement has one, whoever
        # recorded it.
        if not sent['fee'] and arrived['fee']:
            self._exec("UPDATE transfers SET fee=:fee, fee_account=:fee_account, fee_symbol_id=:fee_symbol_id "
                       "WHERE oid=:oid",
                       [(":fee", Decimal(arrived['fee'])), (":fee_account", self._or_null(arrived['fee_account'])),
                        (":fee_symbol_id", self._or_null(arrived['fee_symbol_id'])), (":oid", int(sent['oid']))])
        self._exec("DELETE FROM transfers WHERE oid=:oid", [(":oid", int(arrived['oid']))], commit=True)
        logging.info(self.tr("Transfer settled by transaction hash: ") + f"{sent['number']}, "
                     + f"{remove_exponent(Decimal(sent['withdrawal']))} "
                     + self._account_name(int(sent['withdrawal_account'])) + " -> "
                     + self._account_name(int(arrived['deposit_account'])))
        if self._currency_of(int(sent['withdrawal_account'])) != self._currency_of(int(arrived['deposit_account'])):
            logging.warning(self.tr("Settled transfer crosses currencies, so it has no cost basis and the arrived "
                                    "asset opens at zero: ") + f"{sent['number']}")

    # _read_record() gives '' for a SQL NULL, which no INTEGER column may be written back
    @staticmethod
    def _or_null(value):
        return value if value != '' else None

    def _currency_of(self, account_id: int) -> int:
        return int(self._read("SELECT currency_id FROM accounts WHERE id=:id", [(":id", account_id)]))

    def _account_name(self, account_id: int) -> str:
        return self._read("SELECT name FROM accounts WHERE id=:id", [(":id", account_id)]) or f"#{account_id}"
