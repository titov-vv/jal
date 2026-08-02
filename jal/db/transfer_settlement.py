import logging
from decimal import Decimal
from PySide6.QtWidgets import QApplication
from jal.constants import PredefinedAccountType
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.cost_basis import carried_basis
from jal.db.db import JalDB
from jal.db.helpers import remove_exponent
from jal.db.address_match import impersonated_target
from jal.db.operations import AssetPayment, LedgerTransaction
from jal.db.symbol import JalSymbol
from jal.widgets.helpers import ts2dt


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
    #
    # The ASSET is what groups them, never the symbol: one asset has an active listing per chain and per currency, so
    # the two records of one movement routinely name two different listings of the very same thing - the two ends of a
    # bridged move are two chains, and an exchange kept in another currency lists what it holds in that currency. This
    # is the identity every other pass here uses (_asset_of, _pending_counterparts_on, pending_arrival_of), and
    # grouping by the symbol instead left such a movement as two groups of one, which is a group nothing can pair.
    #
    # Grouping by the asset only ever makes a group WIDER, and a group of more than two is refused rather than
    # settled (see _pairable), so this cannot pair anything that the narrower grouping would have refused.
    def _movements_with_a_pending_leg(self) -> list:
        groups = {}
        query = self._exec(
            "SELECT t.oid, t.withdrawal_timestamp, t.withdrawal_account, t.withdrawal, t.deposit_timestamp, "
            "t.deposit_account, t.deposit, t.fee_account, t.fee, t.fee_symbol_id, t.number, t.symbol_id, t.note, "
            "s.asset_id FROM transfers AS t JOIN asset_symbol AS s ON s.id=t.symbol_id "
            "WHERE t.number!='' AND EXISTS "
            "(SELECT 1 FROM transfers AS p JOIN asset_symbol AS ps ON ps.id=p.symbol_id "
            "WHERE p.number=t.number AND ps.asset_id=s.asset_id "
            "AND (p.withdrawal_account IS NULL OR p.deposit_account IS NULL)) ORDER BY t.oid")
        while query.next():
            record = self._read_record(query, named=True)
            groups.setdefault((record['number'], record['asset_id']), []).append(record)
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
        counterparty = JalAccount.at_address(self._chain_of(leg, known_account), leg['counterparty_address'])
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
        counterparty = JalAccount.at_address(self._chain_of(leg, known_account), leg['counterparty_address'])
        if counterparty is None or counterparty.id() == known_account:
            return 0
        return counterparty.id()

    # ------------------------------------------------------------------------------------------------------------------
    # The pending leg that looks like the other half of this one but is recorded under a DIFFERENT asset, as
    # {'oid', 'asset', 'other_asset'} - or None when there is no such leg.
    #
    # One transaction, one quantity, one leg leaving and one arriving is a movement whichever way it is read. When the
    # two records name two different assets, one of two things is true and neither is settleable: the transaction
    # moved two different things at once (a swap through a contract, which is not a transfer at all), or the same coin
    # is recorded as two assets. The second happens where a token's identity is its contract address and its ticker is
    # only a label: a coin RENAMED on one chain (Tether's 'USDT' is called 'USD₮0' on Arbitrum) matches no address and
    # collides with no ticker, so it is fetched as an asset of its own - see Statement._resolve_cross_chain_token().
    #
    # The QUANTITY is what tells the two apart, and it is why this is worth reporting at all. A swap gives back an
    # amount of the other coin, which is not the amount that went in; a transfer delivers exactly what was sent. So a
    # pair that agrees on the quantity to the last digit is one movement under two asset identities - not proof, but
    # far too specific to be coincidence, and nothing else in JAL would ever point it out. Acting on it stays the
    # user's business: merging two assets rewrites what every report counts, and only they know whether the two
    # tickers are one coin.
    def duplicate_asset_hint(self, oid: int):
        leg = self._read("SELECT oid, withdrawal_account, deposit_account, withdrawal, number, symbol_id "
                         "FROM transfers WHERE oid=:oid "
                         "AND (withdrawal_account IS NULL OR deposit_account IS NULL)", [(":oid", oid)], named=True)
        if leg is None or not leg['number'] or not leg['symbol_id']:
            return None
        sending = leg['deposit_account'] == ''    # _read() gives '' for a SQL NULL - the end with no account
        # The counterpart is pending on the side this leg knows, so that the two together make one whole movement
        missing = "t.withdrawal_account IS NULL" if sending else "t.deposit_account IS NULL"
        counterpart = self._read(
            "SELECT t.oid, s.asset_id FROM transfers AS t JOIN asset_symbol AS s ON s.id=t.symbol_id "
            f"WHERE {missing} AND t.number=:hash AND t.withdrawal=:qty AND s.asset_id<>:asset AND t.oid<>:oid",
            [(":hash", leg['number']), (":qty", leg['withdrawal']), (":oid", int(leg['oid'])),
             (":asset", JalSymbol(leg['symbol_id']).asset().id())], named=True, check_unique=True)
        if counterpart is None:
            return None
        return {'oid': int(counterpart['oid']), 'asset': JalSymbol(leg['symbol_id']).asset(),
                'other_asset': JalAsset(int(counterpart['asset_id']))}

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
    #
    # 'override' waives the one refusal that is about the two SOURCES rather than about the movement - see the
    # ordering check below - and is what the user confirming a pair by hand passes.
    def _refusal(self, sent: dict, arrived: dict, override: bool = False) -> str:
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
        # An arrival that precedes its departure is not a movement JAL can process (see Transfer.processAssetTransfer),
        # so a pair that says it does is refused - but only while the two moments are evidence of anything. Two records
        # of ONE TRANSACTION are not two events to be ordered: the movement happened once, at the moment the block
        # carrying it was mined, and everything else is bookkeeping around it (an exchange debits its own ledger
        # seconds after the block that took the coins away, and its statement states that moment). The order of two
        # such readings says nothing about the movement, so it can't refuse it; _merge() reduces them to one moment
        # instead. The same holds for a pair the user vouches for by hand, which is what 'override' carries.
        if int(sent['withdrawal_timestamp']) > int(arrived['deposit_timestamp']) \
                and not self._one_transaction(sent, arrived) and not override:
            return self.tr("the arrival precedes the departure")
        return ''

    # Whether the two legs are two records of one and the same transaction, which is what makes their disagreement
    # about the moment a disagreement of two clocks rather than of two events. The hash is compared as it is stored,
    # without case folding, exactly as everywhere else here: chains disagree on the case of a hash and a wrong pair is
    # worse than a missed one. A money transfer's 'number' identifies nothing, so it proves nothing either.
    @staticmethod
    def _one_transaction(sent: dict, arrived: dict) -> bool:
        return bool(sent['symbol_id']) and bool(sent['number']) and sent['number'] == arrived['number']

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
    #
    # 'override' is the user's word that the two are one movement despite their moments being in the wrong order (the
    # only refusal that can be overruled - see _refusal), and only a caller that showed them what it means may pass it.
    def settle_linked(self, sending_oid: int, arriving_oid: int, override: bool = False) -> str:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None:
            return self.tr("one of the legs is no longer pending")
        refusal = self._refusal(sent, arrived, override)
        if refusal:
            return refusal
        self._merge(sent, arrived)
        return ''

    # Why these two pending legs cannot be settled into one transfer, or '' when they can - the same answer
    # settle_linked() gives, asked before anything is written. It is what lets a chooser say what a pair would do
    # instead of letting the user find out by trying it. Asked with override=True it gives what the user CANNOT
    # overrule, so a chooser can tell the pairs that are impossible from the one that only needs to be confirmed.
    def refusal_for(self, sending_oid: int, arriving_oid: int, override: bool = False) -> str:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None:
            return self.tr("one of the legs is no longer pending")
        return self._refusal(sent, arrived, override)

    # The moment both legs would be stamped with if they were settled, or 0 when they keep their own - what a chooser
    # shows before asking the user to confirm a pair whose two moments are in the wrong order.
    def agreed_moment_for(self, sending_oid: int, arriving_oid: int) -> int:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None or int(sent['withdrawal_timestamp']) <= int(arrived['deposit_timestamp']):
            return 0
        return self._agreed_moment(sent, arrived)

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
        # Each side normally keeps the moment its own source stated - the two are readings of one movement by two
        # clocks and the difference between them is what the movement took. When they are in the wrong order they are
        # not a duration at all but a disagreement, and a transfer that arrives before it left can't be processed, so
        # both ends are stamped with one reading instead.
        departure, arrival = int(sent['withdrawal_timestamp']), int(arrived['deposit_timestamp'])
        if departure > arrival:
            departure = arrival = self._agreed_moment(sent, arrived)
            logging.warning(self.tr("Legs disagree about when the movement happened, both are stamped with: ")
                            + ts2dt(departure) + (f" ({sent['number']})" if sent['number'] else ''))
        # Both ends are accounts now, so neither of them is an address waiting to be resolved any more
        self._exec("UPDATE transfers SET withdrawal_timestamp=:departure, deposit_account=:account, "
                   "deposit_timestamp=:timestamp, deposit=:deposit, note=:note, counterparty_address=NULL "
                   "WHERE oid=:oid",
                   [(":departure", departure), (":account", int(arrived['deposit_account'])), (":timestamp", arrival),
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

    # The one moment two records that disagree about when their movement happened are both stamped with.
    #
    # The reading of the CHAIN is the one to keep: the block is when the movement happened, while an exchange states
    # when its own books recorded it, which is around it rather than at it (KuCoin debits its ledger some twenty
    # seconds after the block that carried the withdrawal away, and its statement carries that moment). The leg held
    # on a WALLET account is the chain's side of the pair. When both ends are wallets, or neither is, nothing tells
    # the two readings apart and the earlier one is taken - it is the departure, which is the end the ledger reads
    # first and the one that must not move forward past what it funds.
    @staticmethod
    def _agreed_moment(sent: dict, arrived: dict) -> int:
        departure, arrival = int(sent['withdrawal_timestamp']), int(arrived['deposit_timestamp'])
        on_chain = [moment for moment, account in ((departure, int(sent['withdrawal_account'])),
                                                   (arrival, int(arrived['deposit_account'])))
                    if JalAccount(account).account_type() == PredefinedAccountType.Wallet]
        return on_chain[0] if len(on_chain) == 1 else min(departure, arrival)

    # ------------------------------------------------------------------------------------------------------------------
    # Some pairs of pending legs are not a transfer at all: one asset left and ANOTHER one arrived, which is an
    # exchange rather than a movement of the same money. It reaches this report when whoever recorded the two legs
    # couldn't tell - an intent-based DEX settles a swap through a transaction the wallet never signed, and an
    # exchange's statement may report the two sides as two withdrawals/deposits - and no settlement can ever pair
    # them, because they are not two sightings of one thing but the two halves of one exchange.
    #
    # Converting them replaces the two transfer records with the single Swap operation they always were. The cost
    # basis is what makes this matter rather than being cosmetic: as transfers the disposal is never recognized and
    # the arrival opens at nothing, while a swap disposes of what left at its basis and opens what arrived at its
    # value - which is what a tax report has to see.

    # Turns the two pending legs into one Swap operation and deletes them. Returns '' when it was done, and otherwise
    # why it was not.
    def convert_to_swap(self, sending_oid: int, arriving_oid: int) -> str:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None:
            return self.tr("one of the legs is no longer pending")
        refusal = self._refusal_to_convert(sent, arrived)
        if refusal:
            return refusal
        out_account, in_account = int(sent['withdrawal_account']), int(arrived['deposit_account'])
        # 'withdrawal' holds the quantity on BOTH legs of an asset transfer - 'deposit' of one is not an amount but
        # the cost basis the arrived asset opens at (see Transfer.processAssetTransfer), which is exactly what a leg
        # recorded from a chain leaves at zero. Reading it as the quantity would swap into nothing.
        swap = {'timestamp': int(sent['withdrawal_timestamp']), 'tx_hash': sent['number'],
                'account_id': out_account,
                'out_symbol_id': int(sent['symbol_id']), 'out_qty': Decimal(sent['withdrawal']),
                'in_symbol_id': int(arrived['symbol_id']), 'in_qty': Decimal(arrived['withdrawal']),
                'note': sent['note'] if sent['note'] else arrived['note']}
        # A swap that receives on ANOTHER account is the cross-chain shape the operation already knows: the acquiring
        # leg keeps its own account, moment and transaction. Left NULL for a same-chain swap, where the acquisition
        # happens on the spot - which is what tells the two apart everywhere else in JAL (see SwapWidget).
        if in_account != out_account:
            swap.update({'in_account_id': in_account, 'in_timestamp': int(arrived['deposit_timestamp']),
                         'in_tx_hash': arrived['number']})
        fee, fee_symbol_id = self._fee_of(sent, arrived)
        if fee:
            swap.update({'fee_qty': fee, 'fee_symbol_id': fee_symbol_id})
        LedgerTransaction.create_new(LedgerTransaction.Swap, swap)
        self._exec("DELETE FROM transfers WHERE oid=:oid", [(":oid", int(sent['oid']))])
        self._exec("DELETE FROM transfers WHERE oid=:oid", [(":oid", int(arrived['oid']))], commit=True)
        logging.info(self.tr("Transfer legs converted into a swap: ")
                     + f"{remove_exponent(Decimal(sent['withdrawal']))} {JalSymbol(sent['symbol_id']).symbol()} -> "
                     + f"{remove_exponent(Decimal(arrived['withdrawal']))} {JalSymbol(arrived['symbol_id']).symbol()}")
        return ''

    # Why these two pending legs cannot be converted into one swap, or '' when they can - asked before anything is
    # written, so a chooser can say what the pair would do instead of letting the user find out by trying it.
    def refusal_to_convert(self, sending_oid: int, arriving_oid: int) -> str:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None:
            return self.tr("one of the legs is no longer pending")
        return self._refusal_to_convert(sent, arrived)

    # One leg being offered as both sides of the swap needs no check of its own: _pending_pair() asks for a row whose
    # DEPOSIT end is unknown and a row whose WITHDRAWAL end is unknown, and one row is never both.
    def _refusal_to_convert(self, sent: dict, arrived: dict) -> str:
        # A money transfer names no symbol, and the swap operation is built of two of them. Money leaving and money
        # arriving is a conversion or a trade rather than a swap, and JAL records those as their own operations.
        if not sent['symbol_id'] or not arrived['symbol_id']:
            return self.tr("a swap exchanges two assets, and one of these legs moves money")
        if self._asset_of(sent) == self._asset_of(arrived):
            return self.tr("both legs carry the same asset, so this is a transfer and not an exchange")
        if int(sent['withdrawal_timestamp']) > int(arrived['deposit_timestamp']):
            return self.tr("the asset can't be received before it was exchanged")
        if Decimal(sent['withdrawal']) <= 0 or Decimal(arrived['withdrawal']) <= 0:
            return self.tr("a swap needs a positive quantity on both sides")
        return self._refusal_over_fees(sent, arrived)

    # Why the fees the two legs carry cannot go onto the one operation they are converted into, or '' when they can.
    #
    # A swap and a bridge each carry ONE fee, charged in one asset on the account the operation happens on. A fee that
    # names no asset can't be written at all, one paid on another account would move money that was never spent there,
    # and two fees in different assets can't be added up. None of them may be quietly dropped - that is money the user
    # really spent - so a pair carrying one is left to be recorded by hand instead.
    def _refusal_over_fees(self, sent: dict, arrived: dict) -> str:
        for leg in (sent, arrived):
            if not leg['fee']:
                continue
            if not leg['fee_symbol_id']:
                return self.tr("a leg pays a fee that names no asset, which one operation can't hold")
            if leg['fee_account'] != '' and int(leg['fee_account']) != int(sent['withdrawal_account']):
                return self.tr("a leg pays its fee on another account, which one operation can't hold")
        if sent['fee'] and arrived['fee'] and int(sent['fee_symbol_id']) != int(arrived['fee_symbol_id']):
            return self.tr("the two legs pay their fees in different assets, which one operation can't hold")
        return ''

    # The fee of the swap the two legs make, as (amount, symbol id) - the sum of what they carry, which is in one and
    # the same asset by the time this is asked (see the refusals above). Zero when neither of them paid one.
    def _fee_of(self, sent: dict, arrived: dict):
        fee = (Decimal(sent['fee']) if sent['fee'] else Decimal('0')) \
              + (Decimal(arrived['fee']) if arrived['fee'] else Decimal('0'))
        symbol_id = self._or_null(sent['fee_symbol_id']) or self._or_null(arrived['fee_symbol_id'])
        return (fee, int(symbol_id)) if fee else (Decimal('0'), None)

    # ------------------------------------------------------------------------------------------------------------------
    # ... and some pairs are one asset crossing chains, which is a Bridge rather than either of them.
    #
    # JAL already completes a cross-chain move whose SENDING leg the fetcher recognized: that leg is stored as a
    # pending half-bridge and BridgeMatcher pairs it with the arriving transfer (Operations -> "Match cross-chain
    # legs..."). What lands here is the move whose sending leg was NOT recognized - the bridge contract is not in the
    # protocol registry, so both ends were imported as plain transfers and there is no half to complete.
    #
    # A transfer settlement can't rescue those either: a bridge that takes its cut delivers LESS than was sent, and
    # what arrived not being what left is precisely how _refusal() tells a bridge from a transfer and refuses to
    # merge the two legs. So without this the pair has no path at all - Match refuses it on the quantity, the swap
    # conversion refuses it on the asset, and the bridge matcher has nothing to match.
    #
    # The rules are BridgeMatcher's, deliberately: whichever way a cross-chain move is completed, the same pair has to
    # be judged the same way, and that class is where the judgement is written down.

    # Turns the two pending legs into one Bridge operation and deletes them. Returns '' when it was done, and
    # otherwise why it was not.
    def convert_to_bridge(self, sending_oid: int, arriving_oid: int) -> str:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None:
            return self.tr("one of the legs is no longer pending")
        refusal = self._refusal_to_bridge(sent, arrived)
        if refusal:
            return refusal
        # 'withdrawal' holds the quantity on both legs of an asset transfer - see convert_to_swap() on why 'deposit'
        # is not an amount
        bridge = {'out_timestamp': int(sent['withdrawal_timestamp']), 'out_account_id': int(sent['withdrawal_account']),
                  'out_symbol_id': int(sent['symbol_id']), 'out_qty': Decimal(sent['withdrawal']),
                  'out_tx_hash': sent['number'],
                  'in_timestamp': int(arrived['deposit_timestamp']), 'in_account_id': int(arrived['deposit_account']),
                  'in_symbol_id': int(arrived['symbol_id']), 'in_qty': Decimal(arrived['withdrawal']),
                  'in_tx_hash': arrived['number'],
                  'note': sent['note'] if sent['note'] else arrived['note']}
        fee, fee_symbol_id = self._fee_of(sent, arrived)
        if fee:
            bridge.update({'fee_qty': fee, 'fee_symbol_id': fee_symbol_id})
        LedgerTransaction.create_new(LedgerTransaction.Bridge, bridge)
        self._exec("DELETE FROM transfers WHERE oid=:oid", [(":oid", int(sent['oid']))])
        self._exec("DELETE FROM transfers WHERE oid=:oid", [(":oid", int(arrived['oid']))], commit=True)
        logging.info(self.tr("Transfer legs converted into a bridge: ")
                     + f"{remove_exponent(Decimal(sent['withdrawal']))} "
                     + self._account_name(int(sent['withdrawal_account'])) + " -> "
                     + f"{remove_exponent(Decimal(arrived['withdrawal']))} "
                     + self._account_name(int(arrived['deposit_account'])))
        return ''

    # Why these two pending legs cannot be converted into one bridge, or '' when they can - asked before anything is
    # written, so a chooser can say what the pair would do instead of letting the user find out by trying it.
    def refusal_to_bridge(self, sending_oid: int, arriving_oid: int) -> str:
        sent, arrived = self._pending_pair(sending_oid, arriving_oid)
        if sent is None:
            return self.tr("one of the legs is no longer pending")
        return self._refusal_to_bridge(sent, arrived)

    def _refusal_to_bridge(self, sent: dict, arrived: dict) -> str:
        if not sent['symbol_id'] or not arrived['symbol_id']:
            return self.tr("a bridge moves an asset, and one of these legs moves money")
        # The two listings of one token on two chains are one asset (the cross-chain unification merges them), so a
        # bridge is what the SAME asset does. A different one arriving means the asset changed on the way, which is a
        # cross-chain swap - a genuine disposal, and a conversion of its own.
        if self._asset_of(sent) != self._asset_of(arrived):
            return self.tr("the legs carry different assets, so this is a cross-chain swap and not a bridge")
        if int(sent['withdrawal_account']) == int(arrived['deposit_account']):
            return self.tr("both legs are on the same account, so nothing crossed anything")
        if int(sent['withdrawal_timestamp']) > int(arrived['deposit_timestamp']):
            return self.tr("the arrival precedes the departure")
        if Decimal(sent['withdrawal']) <= 0 or Decimal(arrived['withdrawal']) <= 0:
            return self.tr("a bridge needs a positive quantity on both sides")
        # What a bridge keeps back is its cut; more arriving than was sent is not a cut but a pair that doesn't belong
        # together (BridgeMatcher refuses it on the same ground)
        if Decimal(arrived['withdrawal']) > Decimal(sent['withdrawal']):
            return self.tr("more arrived than was sent, so these two are not one crossing")
        return self._refusal_over_fees(sent, arrived)

    # ------------------------------------------------------------------------------------------------------------------
    # ... and some legs are not a movement of the user's money at all - they are what somebody else pushed into the
    # wallet uninvited. Those wait for a counterpart that does not exist and never will, so they stay in the worklist
    # for good unless they can be told apart from the legs that are genuinely unfinished.
    POISONING = 'poisoning'    # the sender's address was minted to be mistaken for one of the user's own
    AIRDROP = 'airdrop'        # an asset arrived that the wallet has never dealt in otherwise

    # Why this leg looks like something nobody asked for, as {'kind', 'impersonated'}, or None when it doesn't.
    #
    # Two signals, of deliberately different strength, which is why they are kept apart rather than added together:
    #
    #   POISONING is as close to proof as this report gets. The sender's address matches one of the user's own at
    #   both ends, closely enough that chance is excluded (see jal/db/address_match.py) - it exists to be copied out
    #   of the history in place of the real one. Nothing legitimate produces that.
    #
    #   AIRDROP is an observation, not a verdict: this arrival is the ONLY thing the wallet has ever done in that
    #   asset - never bought it, never sent it, never received it again. An asset that turns up once and is never
    #   touched is what an unsolicited airdrop looks like, though a first genuine acquisition looks the same until
    #   the second one happens, so it is offered as something to look at.
    #
    # What is deliberately NOT a signal here is the value: neither "worth almost nothing" nor "can't be priced".
    # The import-time filter judges an unknown token that way (TokenFilter), and rightly - but for a leg already
    # stored, a missing quote means the quote was never downloaded, and a small amount is very often a real one. Both
    # would paint the largest genuine movements in this list as spam.
    def dust_hint(self, oid: int):
        leg = self._read("SELECT oid, withdrawal_account, deposit_account, symbol_id, counterparty_address "
                         "FROM transfers WHERE oid=:oid AND withdrawal_account IS NULL", [(":oid", oid)], named=True)
        if leg is None or not leg['symbol_id']:
            return None   # only an ARRIVAL can be unsolicited - what the user sent, the user sent
        account = JalAccount(int(leg['deposit_account']))
        if leg['counterparty_address']:
            impersonated = impersonated_target(account.chain(), leg['counterparty_address'])
            if impersonated is not None:
                return {'kind': self.POISONING, 'impersonated': impersonated}
        if self._only_operation_in_its_asset(int(leg['oid']), self._asset_of(leg)):
            return {'kind': self.AIRDROP, 'impersonated': None}
        return None

    # Whether this transfer is everything the user has ever done in the asset it brought
    def _only_operation_in_its_asset(self, oid: int, asset_id: int) -> bool:
        if not asset_id:
            return False
        for table in ("trades", "asset_payments"):
            if self._read(f"SELECT 1 FROM {table} AS o JOIN asset_symbol AS s ON s.id=o.symbol_id "
                          "WHERE s.asset_id=:asset LIMIT 1", [(":asset", asset_id)]):
                return False
        return not self._read("SELECT 1 FROM transfers AS t JOIN asset_symbol AS s ON s.id=t.symbol_id "
                              "WHERE s.asset_id=:asset AND t.oid<>:oid LIMIT 1",
                              [(":asset", asset_id), (":oid", oid)])

    # Records the leg as the dust attack it is: the coins really did arrive, so they stay in the account - what
    # changes is that they stop being half of a transfer that was never going to be completed.
    #
    # AssetPayment.DustAttack is the operation the chain fetchers already write for unsolicited native coin, and it
    # states this correctly on its own: the quantity is real, the cost basis is zero, and a zero is RIGHT here rather
    # than a gap to be filled - the coins were unsolicited and cost nothing, so their whole proceeds are a gain if
    # they are ever sold. Nothing is blacklisted by this: a blacklist is keyed by the token's contract, and poisoning
    # dust arrives as the genuine token (real USDT, in the case this was built for), so quarantining the contract
    # would throw away every future transfer of an asset the user actually holds.
    def mark_as_dust(self, oid: int) -> str:
        refusal = self.refusal_to_mark_dust(oid)
        if refusal:
            return refusal
        leg = self._read("SELECT oid, deposit_timestamp, deposit_account, withdrawal, symbol_id, number, note "
                         "FROM transfers WHERE oid=:oid", [(":oid", oid)], named=True)
        payment = {'timestamp': int(leg['deposit_timestamp']), 'number': leg['number'],
                   'type': AssetPayment.DustAttack, 'account_id': int(leg['deposit_account']),
                   'symbol_id': int(leg['symbol_id']), 'amount': Decimal(leg['withdrawal']),
                   'note': leg['note'] if leg['note'] else self.tr("Unsolicited transfer")}
        LedgerTransaction.create_new(LedgerTransaction.AssetPayment, payment)
        self._exec("DELETE FROM transfers WHERE oid=:oid", [(":oid", int(leg['oid']))], commit=True)
        logging.info(self.tr("Unsolicited transfer recorded as a dust attack: ")
                     + f"{remove_exponent(Decimal(leg['withdrawal']))} {JalSymbol(leg['symbol_id']).symbol()} "
                     + self._account_name(int(leg['deposit_account'])))
        return ''

    # Why this leg can't be written off as dust, or '' when it can
    def refusal_to_mark_dust(self, oid: int) -> str:
        leg = self._read("SELECT oid, withdrawal_account, deposit_account, withdrawal, symbol_id "
                         "FROM transfers WHERE oid=:oid", [(":oid", oid)], named=True)
        if leg is None:
            return self.tr("the transfer doesn't exist")
        # What the user SENT is theirs and went somewhere; only an arrival can be unsolicited. A settled transfer is
        # not a candidate either - both of its ends are known, so it is somebody's movement rather than a stray.
        if leg['withdrawal_account'] != '' or leg['deposit_account'] == '':
            return self.tr("only a leg that arrived from nowhere can be written off as dust")
        if not leg['symbol_id']:
            return self.tr("money can't arrive from nowhere - a dust attack is made of an asset")
        if Decimal(leg['withdrawal']) <= 0:
            return self.tr("nothing arrived to write off")
        return ''

    # _read_record() gives '' for a SQL NULL, which no INTEGER column may be written back
    @staticmethod
    def _or_null(value):
        return value if value != '' else None

    def _currency_of(self, account_id: int) -> int:
        return int(self._read("SELECT currency_id FROM accounts WHERE id=:id", [(":id", account_id)]))

    def _account_name(self, account_id: int) -> str:
        return self._read("SELECT name FROM accounts WHERE id=:id", [(":id", account_id)]) or f"#{account_id}"
