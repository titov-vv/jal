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
        # One wallet may both send and receive the same asset in one transaction (a contract passing money through
        # it), and those two legs are not a transfer of the account to itself
        if int(sent['withdrawal_account']) == int(arrived['deposit_account']):
            return None
        if Decimal(sent['withdrawal']) != Decimal(arrived['withdrawal']):
            return None   # one movement moves one quantity; a disagreement means these are two of them
        if int(sent['withdrawal_timestamp']) > int(arrived['deposit_timestamp']):
            return None   # an arrival can't precede its departure
        return sent, arrived

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
