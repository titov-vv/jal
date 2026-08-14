import logging
import re
from decimal import Decimal

from jal.constants import AssetLocation, PredefinedAccountType
from jal.data_import.statement import JSF, Statement_ImportError
from jal.data_import.statement_csv import StatementCSV

JAL_STATEMENT_CLASS = "StatementBitget"


# ----------------------------------------------------------------------------------------------------------------------
# Bitget exports the whole account history as one zip of CSV files, nearly all of which are empty for a spot-only user.
#
# "Export spot transactions" is the ledger and the spine of the import: it carries every balance movement together
# with the running balance the movement left behind, so the parser can check itself row by row rather than against a
# separate snapshot file (Bitget ships none). Trades come from the fill-level order file, which is the only place the
# traded pair and the fee appear.
#
# MIND THE FEE CONVENTION - it is the opposite of KuCoin's. Bitget's 'Amount' EXCLUDES the fee and 'Fee' is a separate
# negative number, so the balance moved by 'Amount' + 'Fee'. Reading it as KuCoin's rule (where the fee sits inside
# the amount) understates every fee-bearing movement by exactly the fee.
class StatementBitget(StatementCSV):
    StatementName = "Bitget"
    # Bitget writes "<label> <UID>-<export timestamp>.csv", so only the label is stable and files are matched by it.
    # Note the prefix is 'Export ' everywhere except the futures files, which say 'Exported ', and that the Earn
    # labels are joined by an en-dash (U+2013) rather than a hyphen.
    Files = {
        'Export spot transactions': 'ledger',
        'Export spot order details': 'fills',
        'Export spot order history': 'orders',
        'Export deposit/withdrawal records': 'transfers',
        'Export cross margin order history': 'cross_margin_orders',
        'Export cross margin transactions': 'cross_margin',
        'Export isolated margin order history': 'isolated_margin_orders',
        'Export isolated margin transactions': 'isolated_margin',
        'Export small balance conversion history': 'dust_conversion',
        'Export Onchain history': 'onchain_history',
        'Export Onchain transactions': 'onchain',
        'Export Earn–Simple Earn Flexible–subscription': 'earn_flexible_subscription',
        'Export Earn–Simple Earn Flexible–redemption': 'earn_flexible_redemption',
        'Export Earn–Simple Earn Flexible–profit': 'earn_flexible_profit',
        'Export Earn–Simple Earn Fixed–subscription': 'earn_fixed_subscription',
        'Export Earn–Simple Earn Fixed–redemption': 'earn_fixed_redemption',
        'Export Earn–Simple Earn Fixed–profit': 'earn_fixed_profit',
        'Export Earn–Simple Earn Fixed–penalty interest': 'earn_fixed_penalty',
        'Export Earn–On-chain Earn–staking': 'earn_onchain_staking',
        'Export Earn–On-chain Earn–profit': 'earn_onchain_profit',
        'Export Earn–On-chain Earn–standard redemption': 'earn_onchain_redemption',
        'Export Earn–On-chain Earn–express redemption': 'earn_onchain_express',
        'Export Earn–Dual Investment–subscription': 'earn_dual_subscription',
        'Export Earn–Dual Investment–settlement': 'earn_dual_settlement',
        'Export Earn–Dual Investment–profit': 'earn_dual_profit',
        'Export Earn–Shark Fin–subscription': 'earn_shark_subscription',
        'Export Earn–Shark Fin–settlement': 'earn_shark_settlement',
        'Export Earn–Shark Fin–profit': 'earn_shark_profit',
        'Exported USDT-M Futures order history': 'usdt_futures_orders',
        'Exported USDT-M Futures order details': 'usdt_futures_fills',
        'Exported USDT-M Futures position history': 'usdt_futures_positions',
        'Exported USDT-M Futures transactions': 'usdt_futures',
        'Exported Coin-M Futures order history': 'coin_futures_orders',
        'Exported Coin-M Futures order details': 'coin_futures_fills',
        'Exported Coin-M Futures position history': 'coin_futures_positions',
        'Exported Coin-M Futures transactions': 'coin_futures',
        'Exported USDC-M Futures order history': 'usdc_futures_orders',
        'Exported USDC-M Futures order details': 'usdc_futures_fills',
        'Exported USDC-M Futures position history': 'usdc_futures_positions',
        'Exported USDC-M Futures transactions': 'usdc_futures'
    }
    # Files this parser reads, plus the order-level trade file which only restates the fill-level one. Any other file
    # that carries data holds operations this parser was never written for and stops the import - a skipped row would
    # break the running-balance check below, which is exactly what that check exists to catch.
    HandledFiles = ['ledger', 'fills', 'orders', 'transfers']
    # The deposit/withdrawal file stamps a movement up to several minutes away from the ledger (3m15s observed) and
    # shares no id with it, so the two are joined on the coin, the gross amount and a window.
    JoinWindow = 600

    # A ledger row is dispatched by its 'Type'. None means the row is accounted elsewhere: 'Buy'/'Sell' are the two
    # legs of a trade that is imported from the fill file. Anything not listed stops the import.
    LedgerTypes = {
        'Buy': None,
        'Sell': None,
        'Deposit': '_deposit',
        'Ordinary Withdrawal': '_withdrawal',
        'Rebate rewards': '_reward'
    }
    # Withdrawal types name the movement in the deposit/withdrawal file rather than in the ledger
    TransferTypes = {'Deposit': 'Deposit', 'Ordinary Withdrawal': 'Withdraw'}
    _transfers_are_unique_per_transaction = True

    def __init__(self):
        super().__init__()
        self.name = self.tr("&Bitget")
        self.icon_name = "bitget.png"
        self.filename_filter = self.tr("Bitget statement (*.zip)")
        self._account_id = 0
        self._currency = ''

    def _load_statement(self):
        self._refuse_unhandled(self.HandledFiles)
        self._verify_columns()
        self._validate_ledger()
        self._load_account()
        self._load_assets()
        self._load_period()
        self._load_trades()
        self._load_ledger()

    def _verify_columns(self):
        self._check_columns('ledger', ['order', 'Date', 'Coin', 'Type', 'Amount', 'Fee', 'Available'])
        self._check_columns('fills', ['Date', 'Trading pair', 'Base Asset', 'Quote Asset', 'Direction', 'Price',
                                      'Amount', 'Total', 'Fee', 'Fee Coin'])
        self._check_columns('transfers', ['Date', 'Type', 'Coin', 'Quantity', 'Address', 'TxID', 'Status'])

    def _ledger(self) -> list:
        return sorted(self._rows('ledger'), key=lambda x: x['Date'])

    # What a ledger row did to the balance. Unlike KuCoin's, Bitget's 'Amount' is already signed and does NOT include
    # the fee, which stands beside it as its own (negative) number - so the movement is their sum.
    def _delta(self, row) -> Decimal:
        return self._amount(row['Amount']) + self._amount(row['Fee'])

    # The ledger carries the balance each row left behind, so replaying it proves the parser reads the rows the way
    # Bitget meant them - per row, not merely at the end. It runs before anything is imported: a statement that fails
    # here is one whose column semantics differ from what this parser assumes, and importing it would be wrong.
    def _validate_ledger(self):
        balance = {}
        for row in self._ledger():
            coin = row['Coin']
            balance[coin] = balance.get(coin, Decimal('0')) + self._delta(row)
            if balance[coin] != self._amount(row['Available']):
                raise Statement_ImportError(
                    self.tr("Replaying the statement doesn't reproduce the balance Bitget reports: ")
                    + f"{row}: {balance[coin]} != {self._amount(row['Available'])}")
        logging.info(self.tr("Statement balances verified row by row: ") + f"{sorted(balance)}")

    def _load_account(self):
        ledger = self._ledger()
        if not ledger:
            raise Statement_ImportError(self.tr("Statement has no transaction history"))
        self._currency = self._account_currency([x['Coin'] for x in ledger])
        self._account_id = 1
        # Bitget puts the UID in the file names only, never in the data, so it is read back from a file name.
        uid = self._uid()
        self._data[JSF.ACCOUNTS].append({
            "id": self._account_id, "number": uid, "currency": self.currency_id(self._currency),
            "name": f"{self.StatementName}.{uid}", "account_type": PredefinedAccountType.CEX})

    # The UID stands between the label and the export timestamp: "<label> <UID>-<YYYY-MM-DD hh:mm:ss.sss>.csv".
    # It is matched together with the date that follows it, because the account number cannot be told from the year
    # by shape alone and splitting on the last '-' lands inside the date.
    def _uid(self) -> str:
        uids = set()
        for entry in self._entries:
            found = re.search(r"\s(\d+)-\d{4}-\d{2}-\d{2}[ _]", entry)
            if found:
                uids.add(found.group(1))
        if len(uids) == 1:
            return uids.pop()
        raise Statement_ImportError(self.tr("Can't read a single account number from statement file names: ")
                                    + f"{sorted(uids)}")

    def _load_assets(self):
        for coin in sorted({x['Coin'] for x in self._ledger()}):
            if coin == self._currency:
                continue
            self.symbol_id({'type': JSF.ASSET_CRYPTO, 'symbol': coin, 'name': coin,
                            'currency': self.currency_id(self._currency), 'location': AssetLocation.CEX_EXCHANGE})

    # Bitget names no reporting period anywhere - the export file names carry the moment of the export and nothing
    # about the range that was asked for - so the statement is dated by the operations it actually contains.
    def _load_period(self):
        stamps = [x['Date'] for x in self._ledger()]
        self._data[JSF.PERIOD] = [self._timestamp(min(stamps)), self._end_of_date(self._timestamp(max(stamps)))]

    def _symbol_of(self, coin: str) -> int:
        return self.symbol_id({'type': JSF.ASSET_CRYPTO, 'symbol': coin,
                               'currency': self.currency_id(self._currency), 'should_exist': True})

    # ------------------------------------------------------------------------------------------------------------------
    # Bitget takes its fee out of the asset that is RECEIVED, so the fee is not an event of its own - it simply means
    # that less arrived. The trade is therefore recorded as what actually arrived, with no fee: on a buy the quantity
    # is the amount less the fee, on a sell it is the proceeds that are reduced instead. Which side is affected is
    # read from 'Fee Coin' rather than assumed, and a fee in a third coin (Bitget allows paying in BGB at a discount)
    # falsifies that premise and stops the import rather than being silently mis-booked.
    #
    # The consequence is that the stored price is the effective one and not the fill price Bitget printed, which is
    # why 'Price' is not used at all - the price is derived from what was actually exchanged.
    def _load_trades(self):
        count = 0
        for fill in sorted(self._rows('fills'), key=lambda x: x['Date']):
            base, quote = fill['Base Asset'], fill['Quote Asset']
            fee_coin = fill['Fee Coin']
            if fee_coin and fee_coin not in (base, quote):
                raise Statement_ImportError(self.tr("Trade fee is in neither coin of the pair: ") + f"{fill}")
            quantity = self._amount(fill['Amount'])       # always the base asset
            volume = self._amount(fill['Total'])          # always the quote asset
            fee = abs(self._amount(fill['Fee']))
            if fee_coin == base:
                quantity -= fee
            elif fee_coin == quote:
                volume -= fee
            if fill['Direction'] == 'Buy':
                sign = Decimal('1')
            elif fill['Direction'] == 'Sell':
                sign = Decimal('-1')
            else:
                raise Statement_ImportError(self.tr("Unknown trade direction: ") + f"{fill}")
            timestamp = self._timestamp(fill['Date'])
            if quote == self._currency:
                self._add_trade(fill, timestamp, base, sign * quantity, volume)
            else:
                self._add_swap(fill, timestamp, base, quantity, quote, volume, sign)
            count += 1
        logging.info(self.tr("Trades loaded: ") + f"{count}")

    def _add_trade(self, fill, timestamp: int, coin: str, quantity: Decimal, volume: Decimal) -> None:
        if not quantity:
            raise Statement_ImportError(self.tr("Trade has zero quantity: ") + f"{fill}")
        self._data[JSF.TRADES].append({
            "id": self._next_id(JSF.TRADES), "number": self._order_number(fill), "timestamp": timestamp,
            "settlement": timestamp, "account": self._account_id, "symbol": self._symbol_of(coin),
            "quantity": quantity, "price": volume / abs(quantity), "fee": Decimal('0')})

    def _add_swap(self, fill, timestamp: int, base: str, quantity: Decimal, quote: str, volume: Decimal,
                  sign: Decimal) -> None:
        if sign > 0:
            out_coin, out_qty, in_coin, in_qty = quote, volume, base, quantity
        else:
            out_coin, out_qty, in_coin, in_qty = base, quantity, quote, volume
        self._data[JSF.SWAPS].append({
            "id": self._next_id(JSF.SWAPS), "account": self._account_id, "timestamp": timestamp,
            "out_symbol": self._symbol_of(out_coin), "out_qty": out_qty,
            "in_symbol": self._symbol_of(in_coin), "in_qty": in_qty,
            "description": f"{fill['Trading pair']} {fill['Direction']} {self._order_number(fill)}".strip()})

    # The fill file has no id column of its own, so the order number is looked up in the order-level file by pair and
    # time. The ledger's 'order' column is NOT that id - it is an adjacent, different value.
    def _order_number(self, fill) -> str:
        timestamp = self._timestamp(fill['Date'])
        matched = [x for x in self._rows('orders') if x.get('Trading pair') == fill['Trading pair']
                   and abs(self._timestamp(x['Date']) - timestamp) <= self.JoinWindow]
        return matched[0].get('Order Id', '') if len(matched) == 1 else ''

    # ------------------------------------------------------------------------------------------------------------------
    def _load_ledger(self):
        count = 0
        for row in self._ledger():
            if row['Type'] not in self.LedgerTypes:
                raise Statement_ImportError(self.tr("Unsupported Bitget operation: ") + f"{row}")
            handler = self.LedgerTypes[row['Type']]
            if handler is None:
                continue
            getattr(self, handler)(row)
            count += 1
        logging.info(self.tr("Ledger operations loaded: ") + f"{count}")

    # The record of the same movement in the deposit/withdrawal file, or None. Its 'Quantity' is the GROSS account
    # movement - amount plus fee - and not the amount that travelled, so that is what it is matched on. Only the
    # transaction id is taken from it: its quantity would disagree with the wallet on the other side by the fee.
    def _details(self, row):
        # The file records on-chain movements only. Fiat has no counterpart in it at all - this export ships no fiat
        # file of any kind - so a money movement is not something whose details went missing.
        if row['Coin'] == self._currency:
            return None
        timestamp = self._timestamp(row['Date'])
        gross = abs(self._amount(row['Amount'])) + abs(self._amount(row['Fee']))
        matched = [x for x in self._rows('transfers')
                   if x['Coin'] == row['Coin'] and x['Type'] == self.TransferTypes[row['Type']]
                   and self._amount(x['Quantity']) == gross
                   and abs(self._timestamp(x['Date']) - timestamp) <= self.JoinWindow]
        if not matched:
            logging.warning(self.tr("No details found for operation: ") + f"{row}")
            return None
        if len(matched) > 1:
            raise Statement_ImportError(self.tr("Several records match one operation: ") + f"{row}: {matched}")
        if matched[0]['Status'].lower() not in ('successful', 'success'):
            raise Statement_ImportError(self.tr("Operation isn't completed: ") + f"{matched[0]}")
        return matched[0]

    # Value arriving from outside. The export carries no fiat file at all - no counterparty, no method, no reference -
    # so a fiat deposit is stored with its far end unknown and nothing invented to fill it.
    def _deposit(self, row):
        details = self._details(row)
        money = row['Coin'] == self._currency
        symbol = self.currency_symbol_id(self._currency) if money else self._symbol_of(row['Coin'])
        amount = self._amount(row['Amount'])
        fee = abs(self._amount(row['Fee']))
        transfer = {"id": self._next_id(JSF.TRANSFERS), "account": [0, self._account_id, self._account_id],
                    "symbol": [symbol, symbol], "timestamp": self._timestamp(row['Date']),
                    "withdrawal": amount, "deposit": amount if money else Decimal('0'), "fee": fee,
                    "number": details['TxID'] if details else '', "description": row['Type']}
        if fee and not money:
            transfer['fee_symbol'] = symbol
        self._data[JSF.TRANSFERS].append(transfer)

    # Value leaving for a chain. The amount is taken from the ledger and never from the deposit/withdrawal file:
    # that file reports the gross debit, so using it would record a leg larger than what actually arrived on the
    # other side by exactly the fee, and leave a phantom discrepancy on every settled withdrawal.
    def _withdrawal(self, row):
        details = self._details(row)
        money = row['Coin'] == self._currency
        symbol = self.currency_symbol_id(self._currency) if money else self._symbol_of(row['Coin'])
        amount = abs(self._amount(row['Amount']))
        fee = abs(self._amount(row['Fee']))
        transfer = {"id": self._next_id(JSF.TRANSFERS), "account": [self._account_id, 0, self._account_id],
                    "symbol": [symbol, symbol], "timestamp": self._timestamp(row['Date']),
                    "withdrawal": amount, "deposit": amount if money else Decimal('0'), "fee": fee,
                    "number": details['TxID'] if details else '', "description": row['Type']}
        if fee and not money:
            transfer['fee_symbol'] = symbol
        self._data[JSF.TRANSFERS].append(transfer)

    # Coins credited without anything given for them. Bitget's rebate arrives long after the trade it rewards and
    # after the position it was earned on may already have left the exchange, so it can't be folded back into that
    # trade the way KuCoin's trading-fee coupon can - it is income in its own right.
    def _reward(self, row):
        amount = self._delta(row)
        if amount <= Decimal('0'):
            raise Statement_ImportError(self.tr("Reward doesn't increase the balance: ") + f"{row}")
        self._data[JSF.ASSET_PAYMENTS].append({
            "id": self._next_id(JSF.ASSET_PAYMENTS), "type": JSF.PAYMENT_REWARD, "account": self._account_id,
            "timestamp": self._timestamp(row['Date']), "symbol": self._symbol_of(row['Coin']),
            "amount": amount, "description": row['Type']})
