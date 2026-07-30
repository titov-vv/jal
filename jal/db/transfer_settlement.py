import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from jal.db.account import JalAccount
from jal.db.cost_basis import carried_basis
from jal.db.db import JalDB
from jal.db.helpers import remove_exponent
from jal.db.symbol import JalSymbol


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
    #
    # The transaction hash goes first because it settles the two RECORDS of one movement into one, which is what
    # keeps a movement from being counted twice; the address pass that follows works on what is left over, and part
    # of what makes it safe is that the records the hash could pair are gone by then.
    def settle_all(self) -> int:
        settled = 0
        for records in self._movements_with_a_pending_leg():
            pair = self._pairable(records)
            if pair is None:
                continue
            self._merge(*pair)
            settled += 1
        return settled + self.settle_by_address()

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

    # ------------------------------------------------------------------------------------------------------------------
    # Settles the pending legs that NAME the end they are waiting for. Returns the number of transfers settled.
    #
    # A movement fetched from a chain always states the address at its other end, and JAL keeps it
    # ('transfers.counterparty_address') for the end it has no account for. When an account with that address exists,
    # that end is not a guess to be confirmed - the transaction says the money went there, and the account says the
    # address is the user's. So this needs no transaction hash to coincide and no second record of the movement to
    # have been imported at all, which is exactly the case the hash pass above cannot reach: a wallet with no fetcher,
    # or one whose history simply hasn't been downloaded.
    #
    # The address is resolved on ONE chain - the chain of the end that IS known (see _chain_of) - and never against
    # every chain at once: an EVM address is commonly registered as a wallet on several chains, and the assets a
    # movement carries stay on the chain it moved on.
    def settle_by_address(self) -> int:
        settled = 0
        for leg in self._legs_naming_their_counterparty():
            if self._settle_from_address(leg):
                settled += 1
        return settled

    # Pending legs that state the address of the end they are missing, earliest first
    def _legs_naming_their_counterparty(self) -> list:
        legs = []
        query = self._exec(
            "SELECT oid, withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, deposit_account, "
            "deposit, fee_account, fee, fee_symbol_id, number, counterparty_address, symbol_id, note FROM transfers "
            "WHERE (withdrawal_account IS NULL OR deposit_account IS NULL) "
            "AND NOT counterparty_address IS NULL AND counterparty_address!='' ORDER BY oid")
        while query.next():
            legs.append(self._read_record(query, named=True))
        return legs

    # Settles one leg from the address it recorded, and reports whether it did.
    def _settle_from_address(self, leg: dict) -> bool:
        sending = leg['deposit_account'] == ''    # _read_record() gives '' for a SQL NULL - the end with no account
        known_account = int(leg['withdrawal_account'] if sending else leg['deposit_account'])
        counterparty = JalAccount.wallet_at(self._chain_of(leg, known_account), leg['counterparty_address'])
        if counterparty is None or counterparty.id() == known_account:
            return False   # nothing of the user's holds that address, several accounts do, or it is this very account
        # The other record of this movement, when it was imported as well. Filling the account in beside it would put
        # the same movement into the ledger twice, so the two records are folded into one instead - which is what the
        # hash pass does, and the address is what disambiguates a case it had to refuse (a multisend paying two
        # addresses leaves more than two records of one transaction and asset).
        counterparts = self._pending_counterparts_on(leg, counterparty.id(), sending)
        if len(counterparts) == 1:
            pair = (leg['oid'], counterparts[0]) if sending else (counterparts[0], leg['oid'])
            refusal = self.settle_linked(*pair)
            if refusal:
                logging.info(self.tr("Legs named by an address are not a transfer, settle them by hand: ") + refusal)
            return not refusal
        if counterparts:
            # The same transaction moved this asset to that account more than once. Which of those records is this
            # leg's other half is exactly what nothing here can tell - and filling the account in beside them would
            # book the movement a second time - so it is left for the user to pair by hand.
            logging.info(self.tr("Transaction moved the asset to that address more than once, settle it by hand: ")
                         + f"{leg['number']}")
            return False
        # A counterparty kept in another currency is not settled HERE, exactly as ChainFetcher._counterparty_account
        # leaves it: an asset transfer between two currencies takes its destination cost basis from a 'deposit' no
        # fetcher can know, so settling it silently would open the arrived lots at zero - which is what the hash pass
        # is left doing when both records of a movement exist (see the FIXME in _merge), and what puts a wrong basis
        # into the ledger where nothing points at it again.
        #
        # It is no longer a dead end, though: address_suggestion() offers the very same account in the unsettled
        # transfers report, where the user confirms it together with the cost basis. What stays true is that nothing
        # writes a cost basis on its own - the account an address resolves to is a fact, the basis is not.
        if counterparty.currency() != JalAccount(known_account).currency():
            return False
        self._fill_end(leg, counterparty.id(), sending)
        return True

    # The chain an address recorded by this leg belongs to: the chain of the account at the end that IS known, and -
    # for an end that is not a wallet at all, such as an exchange account whose statement named the address it sent
    # to - the chain the moved token is listed on. 0 when neither says, which leaves the address unresolvable.
    @staticmethod
    def _chain_of(leg: dict, known_account: int) -> int:
        chain = JalAccount(known_account).chain()
        if chain:
            return chain
        return JalSymbol(leg['symbol_id']).location() if leg['symbol_id'] else 0

    # The pending legs that record the OTHER side of this movement on the given account. It is the same transaction
    # and the same asset - the identity the hash pass uses - and additionally the account the address resolved to,
    # which is what tells the several legs of one multisend apart. There is usually none (the wallet at that address
    # has not been fetched, which is the whole point of settling on the address) or exactly one.
    def _pending_counterparts_on(self, leg: dict, account_id: int, sending: bool) -> list:
        if not leg['number'] or not leg['symbol_id']:
            return []   # a movement that names no transaction or no asset has nothing to be recognized by
        sides = "t.withdrawal_account IS NULL AND t.deposit_account=:account" if sending \
            else "t.deposit_account IS NULL AND t.withdrawal_account=:account"
        query = self._exec("SELECT t.oid FROM transfers AS t JOIN asset_symbol AS s ON s.id=t.symbol_id "
                           f"WHERE {sides} AND t.number=:hash AND s.asset_id=:asset ORDER BY t.oid",
                           [(":account", account_id), (":hash", leg['number']),
                            (":asset", JalSymbol(leg['symbol_id']).asset().id())])
        oids = []
        while query.next():
            oids.append(int(self._read_record(query, cast=[int])))
        return oids

    # Writes the account the address resolved to into the end that had none. Unlike a merge there is no second record
    # to take anything else from: what the movement is - when, how much, in what - is what the leg that exists says.
    def _fill_end(self, leg: dict, account_id: int, sending: bool) -> None:
        end = "deposit_account" if sending else "withdrawal_account"
        self._exec(f"UPDATE transfers SET {end}=:account, counterparty_address=NULL WHERE oid=:oid",
                   [(":account", account_id), (":oid", int(leg['oid']))], commit=True)
        logging.info(self.tr("Transfer settled by counterparty address: ")
                     + f"{leg['counterparty_address']}, {remove_exponent(Decimal(leg['withdrawal']))} "
                     + (self._account_name(int(leg['withdrawal_account'])) + " -> " + self._account_name(account_id)
                        if sending else
                        self._account_name(account_id) + " -> " + self._account_name(int(leg['deposit_account']))))

    # ------------------------------------------------------------------------------------------------------------------
    # The account the address a leg recorded resolves to, or 0 when nothing of the user's holds it.
    #
    # This is what settle_by_address() acts on, asked without acting: it answers for the legs that pass above as well
    # as for those it has to leave alone (a counterparty kept in another currency), which is what lets the unsettled
    # transfers report show an account the user only has to confirm instead of an address they have to recognize.
    def address_suggestion(self, oid: int) -> int:
        leg = self._read("SELECT oid, withdrawal_account, deposit_account, counterparty_address, symbol_id "
                         "FROM transfers WHERE oid=:oid "
                         "AND (withdrawal_account IS NULL OR deposit_account IS NULL)", [(":oid", oid)], named=True)
        if leg is None or not leg['counterparty_address']:
            return 0
        known_account = int(leg['withdrawal_account'] if leg['deposit_account'] == '' else leg['deposit_account'])
        counterparty = JalAccount.wallet_at(self._chain_of(leg, known_account), leg['counterparty_address'])
        if counterparty is None or counterparty.id() == known_account:
            return 0
        return counterparty.id()

    # ------------------------------------------------------------------------------------------------------------------
    # Fills in the end a leg doesn't know, from what the user knows about it. Returns '' when it did, and otherwise
    # why it did not.
    #
    # Everything above settles a leg against EVIDENCE - the transaction it moved in, the address it paid, the report
    # of whoever routed it - or against the other record of the same movement. This is what is left when there is no
    # such record and there never will be: a centralized exchange whose statement names neither the address it sent
    # to nor the transaction it sent in states nothing that can be matched to anything, so the wallet on the other
    # side holds the only record the movement will ever have. The account at the missing end is then not something to
    # be found but something only the user knows, and the whole act is their assertion rather than a deduction.
    #
    # Unlike a merge this deletes nothing. The row keeps everything it said and gains only the end it was missing, so
    # an assignment can be undone by clearing that end again - which matters, because the counterpart may still be
    # imported later.
    def assign_end(self, oid: int, account_id: int, timestamp: int, amount: Decimal) -> str:
        refusal = self.refusal_for_assignment(oid, account_id, timestamp)
        if refusal:
            return refusal
        leg, sending = self._pending_record(oid)
        # The address named the end that had no account; that end is an account now, so it has nothing left to name
        if sending:
            self._exec("UPDATE transfers SET deposit_account=:account, deposit_timestamp=:timestamp, "
                       "deposit=:amount, counterparty_address=NULL WHERE oid=:oid",
                       [(":account", account_id), (":timestamp", timestamp), (":amount", amount), (":oid", oid)],
                       commit=True)
        else:
            self._exec(f"UPDATE transfers SET withdrawal_account=:account, withdrawal_timestamp=:timestamp, "
                       f"{self._amount_field(leg)}=:amount, counterparty_address=NULL WHERE oid=:oid",
                       [(":account", account_id), (":timestamp", timestamp), (":amount", amount), (":oid", oid)],
                       commit=True)
        known_account = int(leg['withdrawal_account'] if sending else leg['deposit_account'])
        logging.info(self.tr("Transfer end assigned by hand: ")
                     + f"{remove_exponent(Decimal(leg['withdrawal']))} "
                     + (self._account_name(known_account) + " -> " + self._account_name(account_id) if sending else
                        self._account_name(account_id) + " -> " + self._account_name(known_account)))
        return ''

    # Why the given account cannot be the end this leg is missing, or '' when it can - the same answer assign_end()
    # gives, asked before anything is written, so that a chooser can say what an assignment would do instead of
    # letting the user find out by trying it.
    def refusal_for_assignment(self, oid: int, account_id: int, timestamp: int) -> str:
        leg, sending = self._pending_record(oid)
        if leg is None:
            return self.tr("one of the legs is no longer pending")
        if not account_id:
            return self.tr("no account is chosen for the end that is missing")
        known_account = int(leg['withdrawal_account'] if sending else leg['deposit_account'])
        if account_id == known_account:
            return self.tr("both legs are on the same account")
        departure = int(leg['withdrawal_timestamp']) if sending else timestamp
        arrival = timestamp if sending else int(leg['deposit_timestamp'])
        if departure > arrival:
            return self.tr("the arrival precedes the departure")
        if sending:
            return ''   # the account that sends is the one already recorded, and the ledger has already taken it out
        return self._refusal_to_supply(leg, account_id, departure)

    # Why the account being named as the SOURCE cannot have sent what arrived, or '' when it could have.
    #
    # This check has no counterpart among the pairing refusals, and it is the reason an assignment is checked at all:
    # pairing two legs joins two accounts that each already hold what they say they hold, while an assignment names an
    # account that may never have held the asset. Recording that doesn't merely put the money in the wrong place -
    # Transfer.processAssetTransfer() raises on it and the rebuild STOPS there, so every operation after it vanishes
    # from every report until the assignment is undone. One read here keeps that out of the database.
    def _refusal_to_supply(self, leg: dict, account_id: int, timestamp: int) -> str:
        if not leg['symbol_id']:
            return ''   # a money transfer takes credit instead of failing, exactly as any other withdrawal does
        if not self._lots_are_calculated_at(timestamp):
            return ''   # nothing to check against - see below
        asset = JalSymbol(leg['symbol_id']).asset()
        account = JalAccount(account_id)
        # The account's own currency as the target: what is asked here is the quantity, and a rate that isn't needed
        # shouldn't be able to make the answer unavailable
        short = carried_basis(account, asset, Decimal(leg['withdrawal']), timestamp, account.currency())['short']
        if short > Decimal('0'):
            return self.tr("the account didn't hold enough of the asset at that moment, it is short of ") \
                + f"{remove_exponent(short)} {asset.symbol()}"
        return ''

    # Whether the open lots of that moment have been calculated at all.
    #
    # They are read from what the ledger has already booked, so an operation it has not reached yet leaves them
    # incomplete - and an account whose lots were never calculated looks exactly like one that never held anything.
    # Refusing an assignment on that would be refusing it on no evidence, so the check stands down instead and the
    # rebuild that follows the assignment is what reports the trouble, if there is any.
    def _lots_are_calculated_at(self, timestamp: int) -> bool:
        frontier = self._read("SELECT ledger_frontier FROM frontier")
        frontier = int(frontier) if frontier else 0
        unprocessed = self._read("SELECT COUNT(*) FROM operation_sequence "
                                 "WHERE timestamp>:frontier AND timestamp<=:timestamp",
                                 [(":frontier", frontier), (":timestamp", timestamp)])
        return not int(unprocessed)

    # One transfer record while it is still pending, as (record, sending) - 'sending' telling which end it knows:
    # True when the money left an account and where it went is unknown, False when it arrived and where from is.
    # (None, False) when the leg isn't pending any more, whatever it was when it was listed.
    def _pending_record(self, oid: int):
        leg = self._read("SELECT oid, withdrawal_timestamp, withdrawal_account, withdrawal, deposit_timestamp, "
                         "deposit_account, deposit, number, counterparty_address, symbol_id, note FROM transfers "
                         "WHERE oid=:oid AND (withdrawal_account IS NULL OR deposit_account IS NULL)",
                         [(":oid", oid)], named=True)
        if leg is None:
            return None, False
        return leg, leg['deposit_account'] == ''    # _read() gives '' for a SQL NULL - the end with no account

    # The field the number that comes with an assignment belongs in, when the end being filled in is the SOURCE.
    #
    # An asset transfer moves one quantity, stated once in 'withdrawal', and uses 'deposit' for something else
    # entirely - the cost basis the arrived asset opens at, which only a cross-currency pair reads (see
    # Transfer.processAssetTransfer). A money transfer converts instead, so each end states its own amount and the
    # one that was missing is the one being supplied.
    @staticmethod
    def _amount_field(leg: dict) -> str:
        return "deposit" if leg['symbol_id'] else "withdrawal"

    # ------------------------------------------------------------------------------------------------------------------
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
        # A transfer moves ONE thing: what left is what arrived. The hash pass can't reach this - it groups the
        # records by the symbol they name - but a caller that pairs legs by hand or on somebody's word can, and two
        # listings of one token on two chains are the SAME asset while their symbols differ.
        if self._asset_of(sent) != self._asset_of(arrived):
            return self.tr("the two legs don't move the same asset")
        if Decimal(sent['withdrawal']) != Decimal(arrived['withdrawal']):
            # A transfer carries ONE quantity - what left is what arrived. A move that delivers less than it was sent
            # is a bridge (which has a leg of its own for each side) and must be booked as one.
            return self.tr("what arrived isn't what was sent, so this is not a transfer: ") \
                + f"{remove_exponent(Decimal(sent['withdrawal']))} -> {remove_exponent(Decimal(arrived['withdrawal']))}"
        if int(sent['withdrawal_timestamp']) > int(arrived['deposit_timestamp']):
            return self.tr("the arrival precedes the departure")
        return ''

    # The asset a leg moves: the one its symbol lists, or 0 for a money transfer, which carries no asset at all and
    # is measured in the currency of its own account (so two money legs are never refused on this account).
    @staticmethod
    def _asset_of(leg: dict) -> int:
        return JalSymbol(leg['symbol_id']).asset().id() if leg['symbol_id'] else 0

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

    # Settles two pending legs that a route source named as the two ends of one movement, or that the user paired by
    # hand. Returns '' when they were merged, and otherwise why they were not - whoever asked has a reason to believe
    # the two belong together, so a refusal is something to tell them about rather than to pass over in silence.
    def settle_linked(self, sending_oid: int, arriving_oid: int) -> str:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None:
            return self.tr("one of the legs is no longer pending")
        refusal = self._refusal(sent, arrived)
        if refusal:
            return refusal
        self._merge(sent, arrived)
        return ''

    # Why these two pending legs cannot be settled into one transfer, or '' when they can - the same answer
    # settle_linked() gives, asked before anything is written. It is what lets a chooser say what a pair would do
    # instead of letting the user find out by trying it.
    def refusal_for(self, sending_oid: int, arriving_oid: int) -> str:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None:
            return self.tr("one of the legs is no longer pending")
        return self._refusal(sent, arrived)

    # The two records, as (sending, arriving), while both are still pending on the sides being joined - (None, None)
    # otherwise, since what was true when they were listed may have been settled by anything else since.
    def _pending_pair(self, sending_oid: int, arriving_oid: int):
        sent = self._pending_leg(sending_oid, 'deposit_account')
        arrived = self._pending_leg(arriving_oid, 'withdrawal_account')
        return (sent, arrived) if sent and arrived else (None, None)

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
        # Both ends are accounts now, so neither of them is an address waiting to be resolved any more
        self._exec("UPDATE transfers SET deposit_account=:account, deposit_timestamp=:timestamp, deposit=:deposit, "
                   "note=:note, counterparty_address=NULL WHERE oid=:oid",
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
