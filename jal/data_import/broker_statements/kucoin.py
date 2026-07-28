import logging
from decimal import Decimal

from jal.constants import AssetLocation, PredefinedAccountType
from jal.data_import.statement import JSF, Statement_ImportError
from jal.data_import.statement_csv import StatementCSV

JAL_STATEMENT_CLASS = "StatementKuCoin"


# ----------------------------------------------------------------------------------------------------------------------
# KuCoin exports the account history as a zip of CSV files, most of which are empty for an ordinary spot user.
#
# The spine of the import is the pair of "Account History" files (Funding/Main and HF Trading): replaying them as
# signed balance deltas reproduces "Others_Asset Snapshots.csv" exactly, so they are known to be a complete and
# self-consistent ledger and every other file is either enrichment or a redundant view. Trades are the one thing they
# cannot supply - a 'Spot' row names no trading pair and dozens of them may share one second - so those come from the
# fill-level order file instead, which carries the pair, the side and the fee of each fill.
#
# Everything the two buckets exchange between themselves is dropped: KuCoin's Main / HF Trading / Earn buckets are not
# economically distinct and are imported as one account, so a move between them is not an operation. That includes the
# Earn subscribe/redeem pair, which crosses buckets like any other internal move.
class StatementKuCoin(StatementCSV):
    StatementName = "KuCoin"
    Files = {
        'Account History_Funding Account': 'funding',
        'Account History_Trading Account': 'trading',
        'Account History_Cross Margin Account': 'cross_margin',
        'Account History_Isolated Margin Account': 'isolated_margin',
        'Spot Orders_Filled Orders (Show Order-Splitting)': 'fills',
        'Spot Orders_Filled Orders': 'orders',
        'Convert Orders_Filled Orders': 'convert',
        'Deposit_Withdrawal History_Deposit History': 'deposits',
        'Deposit_Withdrawal History_Withdrawal History': 'withdrawals',
        'Fiat Orders_Fiat Deposits': 'fiat_deposits',
        'Fiat Orders_Fiat Withdrawals': 'fiat_withdrawals',
        'Fiat Orders_Fast Trade Orders': 'fast_trade',
        'Fiat Orders_P2P Orders': 'p2p',
        'Fiat Orders_Third-Party Payment': 'third_party',
        'Earn Orders_Staking History': 'earn_staking',
        'Earn Orders_Profit History': 'earn_profit',
        'Others_Asset Snapshots': 'snapshots',
        'Others_VIP Lending': 'vip_lending'
    }
    # Files this parser reads, plus the ones it deliberately ignores because they only restate what the ledger
    # already carries: the order-level trade file is the aggregate of the fill-level one, and the two Earn files are
    # a partial view of payouts that arrive in the ledger in full. Any OTHER file that has data means the export
    # contains operations this parser was never written for, and the import stops instead of dropping them silently.
    HandledFiles = ['funding', 'trading', 'fills', 'orders', 'deposits', 'withdrawals', 'fiat_deposits',
                    'snapshots', 'earn_staking', 'earn_profit']
    # An enrichment file states the same movement as the ledger but stamps it seconds apart (up to 48s observed), so
    # the two are joined on the amount and a time window rather than on an equal timestamp.
    JoinWindow = 300
    # A fee refund is booked as part of settling the fill it belongs to, within a second of it, so it is matched in a
    # far tighter window than the one above: fills of different orders may stand less than a minute apart, and a wide
    # window would let one fill's refund be claimed by another.
    RefundWindow = 5

    # A ledger row is dispatched by its 'Type'. None means the row is accounted elsewhere and must not be imported
    # again: 'Spot' rows are the trades that come from the fill file, 'Deduction Coupon Refund' is a rebate folded
    # back into the fee of the fill it belongs to, and the rest are moves between buckets of one and the same account.
    # A 'Type' that is not listed here stops the import - an unknown operation left out would silently break balances.
    LedgerTypes = {
        'Spot': None,
        'Transfer': None,
        'KuCoin Earn Locked': None,
        'KuCoin Earn Redemptions': None,
        'Deduction Coupon Refund': None,
        'Fiat Deposit': '_fiat_deposit',
        'Deposit': '_coin_deposit',
        'Withdraw': '_coin_withdrawal',
        'Hold to Earn Earnings': '_staking_reward',
        'KuCoin Earn Profits': '_staking_reward',
        'Referral Bonus': '_staking_reward',
        'Earn Rate-Up Coupon': '_staking_reward',
        'PLATFORM_REWARD_WITHDRAW': '_reward'
    }
    # Rows that move coins into and out of a KuCoin Earn product. They are dropped like any other internal move, but
    # the amount they park has to be tracked for the balance check below - see _validate_balances().
    EarnLocked = {'KuCoin Earn Locked': Decimal('1'), 'KuCoin Earn Redemptions': Decimal('-1')}
    # A hash makes a transfer identify the movement it belongs to, so the settlement machinery may pair a withdrawal
    # to one's own wallet with the arrival fetched from the chain. Only the coin deposits and withdrawals carry one;
    # a fiat deposit is a money transfer and money transfers carry no symbol, which keeps them out of hash matching.
    _transfers_are_unique_per_transaction = True

    def __init__(self):
        super().__init__()
        self.name = self.tr("KuCoin")
        self.icon_name = "kucoin.png"
        self.filename_filter = self.tr("KuCoin statement (*.zip)")
        self._account_id = 0
        self._currency = ''
        self._coupon_refunds = []

    def _load_statement(self):
        self._refuse_unhandled(self.HandledFiles)
        self._verify_columns()
        self._load_account()
        self._load_assets()
        self._load_period()
        self._load_trades()
        self._load_ledger()
        self._validate_balances()

    def _verify_columns(self):
        self._check_columns('funding', ['UID', 'Currency', 'Side', 'Amount', 'Fee', 'Time(UTC)', 'Remark', 'Type'])
        self._check_columns('trading', ['UID', 'Currency', 'Side', 'Amount', 'Fee', 'Time(UTC)', 'Remark', 'Type'])
        self._check_columns('fills', ['Order ID', 'Symbol', 'Side', 'Avg. Filled Price', 'Filled Amount',
                                      'Filled Volume', 'Filled Time(UTC)', 'Fee', 'Fee Currency'])
        self._check_columns('deposits', ['Time(UTC)', 'Coin', 'Amount', 'Fee', 'Hash', 'Transfer Network', 'Status'])
        self._check_columns('withdrawals', ['Time(UTC)', 'Coin', 'Amount', 'Fee', 'Hash',
                                            'Withdrawal Address/Account', 'Transfer Network', 'Status'])
        self._check_columns('fiat_deposits', ['Order ID', 'Currency (Fiat)', 'Fiat Amount', 'Fee', 'Status',
                                              'Time(UTC)'])
        self._check_columns('snapshots', ['Account Name', 'Coin', 'Amount', 'Time(UTC)'])

    # All ledger rows of both buckets, oldest first. The bucket a row belongs to is not kept: the buckets are one
    # account here, so what a row did to the balance is all that matters.
    def _ledger(self) -> list:
        rows = self._rows('funding') + self._rows('trading')
        return sorted(rows, key=lambda x: x['Time(UTC)'])

    # The signed effect of a ledger row on the balance. 'Amount' is what the balance actually moved by, with the fee
    # already inside it, and 'Side' carries the direction - the column is always positive.
    def _delta(self, row) -> Decimal:
        amount = self._amount(row['Amount'])
        if row['Side'] == 'Deposit':
            return amount
        if row['Side'] == 'Withdrawal':
            return -amount
        raise Statement_ImportError(self.tr("Unknown ledger side: ") + f"{row}")

    def _load_account(self):
        ledger = self._ledger()
        if not ledger:
            raise Statement_ImportError(self.tr("Statement has no account history"))
        uids = {x['UID'] for x in ledger if x.get('UID')}
        if len(uids) != 1:
            raise Statement_ImportError(self.tr("Statement must belong to exactly one account, got UIDs: ")
                                        + f"{sorted(uids)}")
        self._currency = self._account_currency([x['Currency'] for x in ledger])
        self._account_id = 1
        uid = uids.pop()
        # The name carries the exchange (an account number alone says nothing about where it is held) and the UID,
        # which is what keeps it unique - account names are unique in the database and a user may hold more than one
        # account on the same exchange.
        self._data[JSF.ACCOUNTS].append({
            "id": self._account_id, "number": uid, "currency": self.currency_id(self._currency),
            "name": f"{self.StatementName}.{uid}", "account_type": PredefinedAccountType.CEX})

    # Every coin the statement mentions becomes a crypto asset located on the exchange. The location is what says
    # the coin is a claim on KuCoin rather than a token on a chain, and it is also what lets its quotes be
    # downloaded - see _CEX_COINS in jal/net/downloader.py.
    def _load_assets(self):
        coins = {x['Currency'] for x in self._ledger()} | {x['Coin'] for x in self._rows('snapshots')}
        for coin in sorted(coins):
            if coin == self._currency:
                continue
            self.symbol_id({'type': JSF.ASSET_CRYPTO, 'symbol': coin, 'name': coin,
                            'currency': self.currency_id(self._currency), 'location': AssetLocation.CEX_EXCHANGE})

    # The snapshot file spans the whole requested period whether or not anything happened, so it dates the statement
    # better than the operations alone do - but the ledger may reach past the last snapshot (KuCoin writes snapshots
    # up to the previous midnight while the history runs to the moment of the export), so the period is the range
    # that covers both and no operation of the statement can fall outside it.
    def _load_period(self):
        stamps = [x['Time(UTC)'] for x in self._rows('snapshots')] + [x['Time(UTC)'] for x in self._ledger()]
        self._data[JSF.PERIOD] = [self._timestamp(min(stamps)), self._end_of_date(self._timestamp(max(stamps)))]

    def _symbol_of(self, coin: str) -> int:
        return self.symbol_id({'type': JSF.ASSET_CRYPTO, 'symbol': coin,
                               'currency': self.currency_id(self._currency), 'should_exist': True})

    # ------------------------------------------------------------------------------------------------------------------
    # A fill against the account currency is a trade (an asset bought or sold for money); a fill of one coin against
    # another is a swap. Which one it is follows from the account currency alone and is not a separate judgement.
    def _load_trades(self):
        self._load_coupon_refunds()
        count = 0
        for fill in sorted(self._rows('fills'), key=lambda x: x['Filled Time(UTC)']):
            base, _, quote = fill['Symbol'].partition('-')
            if not base or not quote:
                raise Statement_ImportError(self.tr("Can't read trading pair: ") + f"{fill}")
            timestamp = self._timestamp(fill['Filled Time(UTC)'])
            quantity = self._amount(fill['Filled Amount'])
            volume = self._amount(fill['Filled Volume'])
            fee = self._amount(fill['Fee']) - self._matched_refund(fill)
            if fill['Side'] == 'BUY':
                sign = Decimal('1')
            elif fill['Side'] == 'SELL':
                sign = Decimal('-1')
            else:
                raise Statement_ImportError(self.tr("Unknown trade side: ") + f"{fill}")
            if quote == self._currency:
                self._add_trade(fill, timestamp, base, sign * quantity, volume, fee)
            else:
                self._add_swap(fill, timestamp, base, quantity, quote, volume, sign, fee)
            count += 1
        logging.info(self.tr("Trades loaded: ") + f"{count}")

    def _add_trade(self, fill, timestamp: int, coin: str, quantity: Decimal, volume: Decimal, fee: Decimal) -> None:
        if fill['Fee Currency'] != self._currency:
            raise Statement_ImportError(self.tr("Trade fee isn't in the account currency: ") + f"{fill}")
        if not quantity:
            raise Statement_ImportError(self.tr("Trade has zero quantity: ") + f"{fill}")
        self._data[JSF.TRADES].append({
            "id": self._next_id(JSF.TRADES), "number": fill['Order ID'], "timestamp": timestamp,
            "settlement": timestamp, "account": self._account_id, "symbol": self._symbol_of(coin),
            "quantity": quantity, "price": volume / abs(quantity), "fee": fee})

    # A coin-for-coin fill. 'Filled Amount' is always the base coin and 'Filled Volume' the quote one, so a BUY
    # spends the quote and receives the base while a SELL does the reverse.
    def _add_swap(self, fill, timestamp: int, base: str, quantity: Decimal, quote: str, volume: Decimal,
                  sign: Decimal, fee: Decimal) -> None:
        if sign > 0:
            out_coin, out_qty, in_coin, in_qty = quote, volume, base, quantity
        else:
            out_coin, out_qty, in_coin, in_qty = base, quantity, quote, volume
        swap = {"id": self._next_id(JSF.SWAPS), "account": self._account_id, "timestamp": timestamp,
                "out_symbol": self._symbol_of(out_coin), "out_qty": out_qty,
                "in_symbol": self._symbol_of(in_coin), "in_qty": in_qty,
                "description": f"{fill['Symbol']} {fill['Side']} {fill['Order ID']}"}
        if fee:
            if fill['Fee Currency'] not in (base, quote):
                raise Statement_ImportError(self.tr("Swap fee is in neither coin of the pair: ") + f"{fill}")
            swap["fee_symbol"] = self._symbol_of(fill['Fee Currency'])
            swap["fee_qty"] = fee
        self._data[JSF.SWAPS].append(swap)

    # 'Deduction Coupon Refund' rows give part of a trading fee back. Each observed one is exactly 20% of the fee of
    # the fill it follows within a second, but the rate is not assumed - the refund is matched to a fill by its coin
    # and its time and simply subtracted, so a different discount rate needs no change here.
    def _load_coupon_refunds(self):
        self._coupon_refunds = [x for x in self._ledger() if x['Type'] == 'Deduction Coupon Refund']

    # The part of this fill's fee that was refunded. A refund that matches no fill, or more than one, stops the
    # import: silently keeping it would leave the coin balance overstated by the refunded amount.
    def _matched_refund(self, fill) -> Decimal:
        timestamp = self._timestamp(fill['Filled Time(UTC)'])
        matched = [x for x in self._coupon_refunds if x['Currency'] == fill['Fee Currency']
                   and abs(self._timestamp(x['Time(UTC)']) - timestamp) <= self.RefundWindow]
        if not matched:
            return Decimal('0')
        if len(matched) > 1:
            raise Statement_ImportError(self.tr("Several fee refunds match one fill: ") + f"{fill}: {matched}")
        refund = self._amount(matched[0]['Amount'])
        if refund > self._amount(fill['Fee']):
            raise Statement_ImportError(self.tr("Fee refund is larger than the fee it belongs to: ") + f"{fill}")
        self._coupon_refunds.remove(matched[0])
        return refund

    # ------------------------------------------------------------------------------------------------------------------
    def _load_ledger(self):
        count = 0
        for row in self._ledger():
            if row['Type'] not in self.LedgerTypes:
                raise Statement_ImportError(self.tr("Unsupported KuCoin operation: ") + f"{row}")
            handler = self.LedgerTypes[row['Type']]
            if handler is None:
                continue
            getattr(self, handler)(row)
            count += 1
        if self._coupon_refunds:
            raise Statement_ImportError(self.tr("Fee refund doesn't belong to any trade: ")
                                        + f"{self._coupon_refunds}")
        logging.info(self.tr("Ledger operations loaded: ") + f"{count}")

    # The record of the same movement in an enrichment file, or None when there is none. The files disagree about
    # the timestamp by up to a minute and share no id at all, so the join is on the coin, the amount and a window.
    def _enrichment(self, key: str, row, amount: Decimal, coin_column: str = 'Coin'):
        timestamp = self._timestamp(row['Time(UTC)'])
        matched = [x for x in self._rows(key) if x[coin_column] == row['Currency']
                   and self._amount(x[self._amount_column(key)]) == amount
                   and abs(self._timestamp(x['Time(UTC)']) - timestamp) <= self.JoinWindow]
        if not matched:
            logging.warning(self.tr("No details found for operation: ") + f"{row}")
            return None
        if len(matched) > 1:
            raise Statement_ImportError(self.tr("Several records match one operation: ") + f"{row}: {matched}")
        if matched[0]['Status'].upper() not in ('SUCCESS', 'SUCCEEDED'):
            raise Statement_ImportError(self.tr("Operation isn't completed: ") + f"{matched[0]}")
        return matched[0]

    @staticmethod
    def _amount_column(key: str) -> str:
        return 'Fiat Amount' if key == 'fiat_deposits' else 'Amount'

    # Money arriving from outside the exchange. The ledger credits the sum net of the fee while the fiat file names
    # the gross one, so the transfer stores the gross amount together with the fee that was taken out of it - which
    # is what the balance ends up as, and it keeps the fee visible as a fee instead of a smaller deposit.
    def _fiat_deposit(self, row):
        gross = self._delta(row) + self._amount(row['Fee'])
        details = self._enrichment('fiat_deposits', row, gross, coin_column='Currency (Fiat)')
        symbol = self.currency_symbol_id(self._currency)
        self._data[JSF.TRANSFERS].append({
            "id": self._next_id(JSF.TRANSFERS), "account": [0, self._account_id, self._account_id],
            "symbol": [symbol, symbol], "timestamp": self._timestamp(row['Time(UTC)']),
            "withdrawal": gross, "deposit": gross, "fee": self._amount(row['Fee']),
            "number": details['Order ID'] if details else '',
            "description": self._note(row, details['Deposit Method'] if details else '')})

    # Coins arriving from a chain. The counterparty address is deliberately not stored: the address the file names
    # is KuCoin's own deposit address, i.e. this end of the movement, and the sender is never disclosed.
    def _coin_deposit(self, row):
        amount = self._delta(row) + self._amount(row['Fee'])
        details = self._enrichment('deposits', row, amount)
        symbol = self._symbol_of(row['Currency'])
        transfer = {"id": self._next_id(JSF.TRANSFERS), "account": [0, self._account_id, self._account_id],
                    "symbol": [symbol, symbol], "timestamp": self._timestamp(row['Time(UTC)']),
                    "withdrawal": amount, "deposit": Decimal('0'), "fee": self._amount(row['Fee']),
                    "number": details['Hash'] if details else '',
                    "description": self._note(row, details['Transfer Network'] if details else '')}
        if transfer['fee']:
            transfer['fee_symbol'] = symbol
        self._data[JSF.TRANSFERS].append(transfer)

    # Coins leaving for a chain. The ledger debit includes the withdrawal fee, so what actually travelled - and what
    # the receiving wallet will report - is the debit less that fee. Storing the debit instead would leave a
    # permanent discrepancy against the arrival on the other side.
    def _coin_withdrawal(self, row):
        fee = self._amount(row['Fee'])
        amount = -self._delta(row) - fee
        details = self._enrichment('withdrawals', row, amount)
        symbol = self._symbol_of(row['Currency'])
        transfer = {"id": self._next_id(JSF.TRANSFERS), "account": [self._account_id, 0, self._account_id],
                    "symbol": [symbol, symbol], "timestamp": self._timestamp(row['Time(UTC)']),
                    "withdrawal": amount, "deposit": Decimal('0'), "fee": fee,
                    "number": details['Hash'] if details else '',
                    "description": self._note(row, details['Transfer Network'] if details else '')}
        if fee:
            transfer['fee_symbol'] = symbol
        if details and details['Withdrawal Address/Account']:
            transfer['counterparty_address'] = details['Withdrawal Address/Account']
        self._data[JSF.TRANSFERS].append(transfer)

    def _staking_reward(self, row):
        self._add_payment(JSF.PAYMENT_STAKING_REWARD, row)

    def _reward(self, row):
        self._add_payment(JSF.PAYMENT_REWARD, row)

    # Coins credited without anything being given for them. The KuCoin operation name is written into the note:
    # several distinct kinds of payout land on one JAL payment type, and the name is the only thing that keeps them
    # apart afterwards - it is what a later re-classification would have to work from.
    def _add_payment(self, payment_type: str, row):
        amount = self._delta(row)
        if amount <= Decimal('0'):
            raise Statement_ImportError(self.tr("Reward doesn't increase the balance: ") + f"{row}")
        self._data[JSF.ASSET_PAYMENTS].append({
            "id": self._next_id(JSF.ASSET_PAYMENTS), "type": payment_type, "account": self._account_id,
            "timestamp": self._timestamp(row['Time(UTC)']), "symbol": self._symbol_of(row['Currency']),
            "amount": amount, "description": self._note(row)})

    # The operation name, whatever KuCoin remarked about it and the detail the enrichment file added (the network a
    # coin travelled over, the method a deposit came by). Repetitions are dropped - KuCoin often puts the same word
    # in the type and in the remark - while the order is kept.
    @staticmethod
    def _note(row, extra: str = '') -> str:
        parts = []
        for part in (row['Type'], row.get('Remark', ''), extra):
            if part and part not in parts:
                parts.append(part)
        return ', '.join(parts)

    # ------------------------------------------------------------------------------------------------------------------
    # A crypto exchange statement is a closed system, so the parser can be checked rather than trusted. Two
    # independent things are verified, and neither is a restatement of the other:
    #
    #  - replaying every ledger row reproduces the balance KuCoin itself reports in its snapshot file, which is what
    #    says the rows were read the way KuCoin meant them;
    #  - the fills the trades are built from move exactly what the ledger's own 'Spot' rows say was moved, which is
    #    what says the trades - the one part that does NOT come from the ledger - agree with it.
    #
    # Mind what the first check does NOT say. The imported account holds whatever currently sits inside a KuCoin Earn
    # product on top of the snapshot: the snapshots cover the Main and HF Trading buckets only, and the rows that move
    # coins into Earn are dropped as internal to the single account they are all imported into. That difference is
    # intended - the coins are owned throughout - so it is reported rather than treated as an error.
    def _validate_balances(self):
        if not self._rows('snapshots'):
            logging.warning(self.tr("Statement has no balance snapshots - import can't be verified"))
            return
        replay, locked, reported, closing = {}, {}, {}, {}
        # The snapshots stop at the last midnight while the history runs on to the moment of the export, so the
        # comparison is made as of the last snapshot and the rows that come after it are only counted into the
        # closing balance of the account.
        last_snapshot = max(x['Time(UTC)'] for x in self._rows('snapshots'))
        for row in self._ledger():
            coin = row['Currency']
            closing[coin] = closing.get(coin, Decimal('0')) + self._delta(row)
            if row['Time(UTC)'] > last_snapshot:
                continue
            replay[coin] = replay.get(coin, Decimal('0')) + self._delta(row)
            if row['Type'] in self.EarnLocked:
                locked[coin] = locked.get(coin, Decimal('0')) + \
                               self.EarnLocked[row['Type']] * self._amount(row['Amount'])
        for row in self._rows('snapshots'):
            if row['Time(UTC)'] == last_snapshot:
                reported[row['Coin']] = reported.get(row['Coin'], Decimal('0')) + self._amount(row['Amount'])
        for coin in sorted(set(replay) | set(reported)):
            if replay.get(coin, Decimal('0')) != reported.get(coin, Decimal('0')):
                raise Statement_ImportError(
                    self.tr("Replaying the statement doesn't reproduce the balance KuCoin reports: ")
                    + f"{coin}: {replay.get(coin, Decimal('0'))} != {reported.get(coin, Decimal('0'))}")
        self._validate_fills()
        held_in_earn = {coin: amount for coin, amount in locked.items() if amount}
        if held_in_earn:
            logging.info(self.tr("Held in KuCoin Earn on top of the reported balance: ") + f"{held_in_earn}")
        account = self._data[JSF.ACCOUNTS][0]
        account['cash_end'] = closing.get(self._currency, Decimal('0'))
        logging.info(self.tr("Statement balances verified against exchange snapshots: ") + f"{sorted(reported)}")

    # The ledger's 'Spot' rows and the fill file describe the same trades from two sides: the ledger says what each
    # coin balance did, the fills say which pair was traded. The trades are built from the fills, so this is what
    # proves that source right - a misread side, quantity or fee shows up here as a coin that doesn't add up.
    # Fees are taken as the fills state them, before any coupon refund: a refund is a ledger row of its own.
    def _validate_fills(self):
        from_fills, from_ledger = {}, {}
        for fill in self._rows('fills'):
            base, _, quote = fill['Symbol'].partition('-')
            sign = Decimal('1') if fill['Side'] == 'BUY' else Decimal('-1')
            for coin, amount in ((base, sign * self._amount(fill['Filled Amount'])),
                                 (quote, -sign * self._amount(fill['Filled Volume'])),
                                 (fill['Fee Currency'], -self._amount(fill['Fee']))):
                from_fills[coin] = from_fills.get(coin, Decimal('0')) + amount
        for row in self._ledger():
            if row['Type'] == 'Spot':
                from_ledger[row['Currency']] = from_ledger.get(row['Currency'], Decimal('0')) + self._delta(row)
        for coin in sorted(set(from_fills) | set(from_ledger)):
            if from_fills.get(coin, Decimal('0')) != from_ledger.get(coin, Decimal('0')):
                raise Statement_ImportError(
                    self.tr("Filled orders don't match the trades recorded in the account history: ")
                    + f"{coin}: {from_fills.get(coin, Decimal('0'))} != {from_ledger.get(coin, Decimal('0'))}")
