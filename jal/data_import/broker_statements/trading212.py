import csv
import logging
import os
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext

from PySide6.QtCore import QT_TRANSLATE_NOOP
from PySide6.QtWidgets import QApplication, QMessageBox

from jal.constants import PredefinedCategory
from jal.data_import.statement import JSF, Statement, Statement_ImportError, Statement_Capabilities
from jal.data_import.card_match import CardMatcher
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.db.helpers import remove_exponent
from jal.db.settings import JalSettings
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor, SettingType

JAL_STATEMENT_CLASS = "StatementTrading212"

# The account a Trading212 statement belongs to. The file itself never names one - it has no account column, no
# header block, and the base64 tail of its name decodes to the millisecond the export was requested - so the only
# thing that can say which account it is about is the user, once, in Settings->Preferences->Import.
T212_ACCOUNT_SETTING = "Trading212Account"

SettingsRegistry.register(SettingDescriptor(
    key=T212_ACCOUNT_SETTING,
    page=QT_TRANSLATE_NOOP("Preferences", "Import"),
    label=QT_TRANSLATE_NOOP("Preferences", "Trading 212 account"),
    type=SettingType.Account, default=0,
    tooltip=QT_TRANSLATE_NOOP("Preferences",
                              "The account a Trading 212 statement is imported into. Such an export names no "
                              "account, so the import can't tell which one a file belongs to and asks here instead.")))


# ----------------------------------------------------------------------------------------------------------------------
# Trading212 hands its history over as a single flat CSV: a header line and one row per event, no preamble, no
# totals, no trailing newline. The header is not fixed - the fee and tax columns appear only in a month that had
# such an event - so every column is looked up by name and an unknown one that carries a value stops the import
# rather than being dropped silently out of the cost of a trade.
#
# The account is a mixed one: it trades and it has a debit card on it, so the very same file carries market buys
# and dividends next to grocery purchases. The card purchases are the reason for the review step in
# match_db_ids(): they are typed by hand as they happen, so most of them are in the database before the statement
# is ever exported - see CardMatcher for what can and cannot identify one.
class StatementTrading212(Statement):
    source_timezone = 'UTC'   # the column is named "Time (UTC)" and every row carries an explicit +00:00
    BrokerName = "Trading212"   # the peer the operations of such an account are recorded against
    # 'Total' divided by 'No. of shares' at this many SIGNIFICANT digits is the price of a trade. Trading212 reports
    # the price it quoted, rounded to 10 decimals, and quantity times that price does not give back the money that
    # actually moved - the quantity is what the amount bought, not the other way round. So the quotient is the
    # price, and this is the width the quotient is kept at.
    PRICE_PRECISION = 15
    # Columns of an export that carries the events this module knows. Every one of them must be present; a column
    # beyond them is refused as soon as any row fills it in - see _check_columns().
    Columns = ("Action", "Time (UTC)", "ISIN", "Ticker", "Name", "Notes", "ID", "No. of shares", "Price / share",
               "Currency (Price / share)", "Exchange rate", "Total", "Currency (Total)", "Withholding tax",
               "Currency (Withholding tax)", "Merchant name", "Merchant category")
    # Trading212 names the export by the period it covers and adds a nonce; the period is what MULTIPLE_LOAD sorts on.
    FilenamePattern = re.compile(r'from_(?P<start>\d{4}-\d{2}-\d{2})_to_(?P<end>\d{4}-\d{2}-\d{2})', re.IGNORECASE)
    DateTimeFormat = "%Y-%m-%d %H:%M:%S%z"
    DividendAction = "Dividend"    # the subtype follows in brackets: "Dividend (Dividend)", "(Dividend manufactured payment)", ...
    InterestNote = "Interest on cash"
    CashbackNote = "Spending cashback"

    # What a test puts here instead of opening CardImportDialog - the same arrangement select_token_action() uses.
    _card_decisions_for_tests = None

    def __init__(self):
        super().__init__()
        self.name = self.tr("T&rading 212")   # '&T' belongs to "&Tvoy Broker"
        self.icon_name = "t212.png"
        self.filename_filter = self.tr("Trading 212 statement (*.csv)")
        self._account_id = 0        # statement-local id of the single account the file is about
        self._currency = ''
        self._card_rows = []        # statement-local ids of the card operations, in file order

    @staticmethod
    def capabilities() -> set:
        return {Statement_Capabilities.MULTIPLE_LOAD}

    @staticmethod
    def order_statements(statement_files) -> list:
        def sort_key(filename):
            match = StatementTrading212.FilenamePattern.search(os.path.basename(filename))
            return (match.group('start'), match.group('end')) if match else ('', '', )

        return sorted(statement_files, key=lambda x: (sort_key(x), x))

    # ------------------------------------------------------------------------------------------------------------------
    def load(self, filename: str) -> None:
        self._reset_id_map()
        self._data = {
            JSF.PERIOD: [None, None],
            JSF.ACCOUNTS: [],
            JSF.ASSETS: [],
            JSF.TRADES: [],
            JSF.ASSET_PAYMENTS: [],
            JSF.INCOME_SPENDING: []
        }
        self._card_rows = []
        rows, columns = self._read_csv(filename)
        self._check_columns(rows, columns)
        self._currency = self._statement_currency(rows)
        self._account_id = self._next_id(JSF.ACCOUNTS)
        # No 'number': the file names no account, so there is nothing to match one by. _resolve_account() maps this
        # record onto the account the user chose before anything is written, and _import_accounts() skips a mapped one.
        self._data[JSF.ACCOUNTS].append(
            {"id": self._account_id, "name": self.BrokerName, "currency": self.currency_id(self._currency)})
        self._load_period(filename, rows)
        loaders = {"Market buy": self._load_trade, "Market sell": self._load_trade,
                   "Interest on cash": self._load_interest, "Spending cashback": self._load_cashback,
                   "Card debit": self._load_card}
        for row in rows:
            action = row["Action"].strip()
            if action.startswith(self.DividendAction):
                self._load_dividend(row)
                continue
            try:
                loader = loaders[action]
            except KeyError:
                # Deposits, withdrawals and currency conversions land here. Nothing is guessed about a movement of
                # money: the import stops with the name of what it doesn't know, and the module learns it from a
                # real example of such a row.
                raise Statement_ImportError(self.tr("Unsupported Trading 212 operation: ") + f"'{action}'")
            loader(row)
        logging.info(self.tr("Statement loaded successfully: ") + self.name)

    def _read_csv(self, filename: str) -> tuple:
        try:
            with open(filename, 'r', encoding='utf-8-sig', newline='') as csv_file:
                reader = csv.DictReader(csv_file)
                if reader.fieldnames is None:
                    raise Statement_ImportError(self.tr("Statement file is empty: ") + filename)
                columns = [x.strip() for x in reader.fieldnames]
                rows = [{key.strip(): (value or '').strip() for key, value in row.items() if key is not None}
                        for row in reader]
        except OSError as err:
            raise Statement_ImportError(self.tr("Failed to read file: ") + str(err))
        except csv.Error as err:
            raise Statement_ImportError(self.tr("Failed to parse CSV file: ") + str(err))
        if not rows:
            raise Statement_ImportError(self.tr("Statement has no operations: ") + filename)
        return rows, columns

    # Trading212 adds a column only when the month had an event that needs it - a stamp duty, a conversion fee, the
    # result of a sale. Such a column is money that belongs to an operation, so a file carrying one is refused
    # instead of being read as if the money weren't there. An empty extra column is harmless and is let through.
    def _check_columns(self, rows: list, columns: list) -> None:
        missing = [x for x in self.Columns if x not in columns]
        if missing:
            raise Statement_ImportError(self.tr("Statement misses mandatory column(s): ") + f"{missing}")
        for column in [x for x in columns if x not in self.Columns]:
            if any(row.get(column) for row in rows):
                raise Statement_ImportError(self.tr("Statement has a column this module doesn't know: ") + column)

    # The single currency the file is denominated in - it is the currency of the account it belongs to.
    def _statement_currency(self, rows: list) -> str:
        currencies = sorted({row["Currency (Total)"] for row in rows if row["Currency (Total)"]})
        if len(currencies) != 1:
            raise Statement_ImportError(self.tr("Statement must have exactly one currency, found: ") + f"{currencies}")
        return currencies[0]

    def _load_period(self, filename: str, rows: list) -> None:
        match = self.FilenamePattern.search(os.path.basename(filename))
        if match:
            begin = self._date(datetime.strptime(match.group('start'), "%Y-%m-%d"))
            end = self._end_of_date(self._date(datetime.strptime(match.group('end'), "%Y-%m-%d")))
        else:   # A file renamed by hand still states its period - by the operations it holds
            timestamps = [self._timestamp(row) for row in rows]
            begin, end = min(timestamps), max(timestamps)
        self._data[JSF.PERIOD] = [begin, end]

    # ------------------------------------------------------------------------------------------------------------------
    def _timestamp(self, row: dict) -> int:
        try:
            moment = datetime.strptime(row["Time (UTC)"], self.DateTimeFormat)
        except ValueError:
            raise Statement_ImportError(self.tr("Can't read operation timestamp: ") + f"{row['Time (UTC)']}")
        if moment.utcoffset().total_seconds() != 0:
            raise Statement_ImportError(self.tr("Operation timestamp isn't in UTC: ") + f"{row['Time (UTC)']}")
        return self._moment(moment.replace(tzinfo=None))

    def _amount(self, row: dict, column: str, mandatory: bool = True) -> Decimal:
        value = row[column]
        if not value:
            if mandatory:
                raise Statement_ImportError(self.tr("Mandatory value is empty: ") + f"'{column}' in {row}")
            return Decimal('0')
        try:
            return Decimal(value)
        except InvalidOperation:
            raise Statement_ImportError(self.tr("Can't read a number: ") + f"'{column}'='{value}'")

    # Currency of an instrument row must be the currency of the account - a trade or a dividend paid in another one
    # needs an exchange rate applied to a cost basis, and there is no example of such a row to write that against.
    def _check_row_currency(self, row: dict, column: str) -> None:
        if row[column] and row[column] != self._currency:
            raise Statement_ImportError(self.tr("Operation in a currency other than the account's: ")
                                        + f"'{column}'='{row[column]}' vs '{self._currency}'")
        rate = self._amount(row, "Exchange rate", mandatory=False)
        if rate and rate != Decimal('1'):
            raise Statement_ImportError(self.tr("Operation with a non-unity exchange rate: ") + f"{rate}")

    def _instrument_symbol(self, row: dict) -> int:
        ticker = row["Ticker"]
        if not ticker:
            raise Statement_ImportError(self.tr("Instrument operation without a ticker: ") + f"{row}")
        if not row["ISIN"]:
            raise Statement_ImportError(self.tr("Instrument operation without an ISIN: ") + f"{row}")
        # The ticker is recorded, but the ISIN is what an existing asset is recognized by - _match_assets() tries it
        # first, before it ever looks at a ticker. Trading212 lists everything it offers as a fund; an asset that
        # turns out to be something else is corrected once, by hand, and the ISIN keeps it matched afterwards.
        return self.symbol_id({
            'type': JSF.ASSET_ETF,
            'symbol': ticker,
            'isin': row["ISIN"],
            'currency': self.currency_id(self._currency),
            'name': row["Name"]
        })

    # ------------------------------------------------------------------------------------------------------------------
    def _load_trade(self, row: dict) -> None:
        self._check_row_currency(row, "Currency (Price / share)")
        quantity = self._amount(row, "No. of shares")
        if not quantity:
            raise Statement_ImportError(self.tr("Trade has zero quantity: ") + f"{row}")
        total = self._amount(row, "Total")
        # 'Total' is the money that moved and it is positive on both sides; the side is in the action name.
        if row["Action"].strip() == "Market sell":
            quantity = -quantity
        with localcontext() as context:
            context.prec = self.PRICE_PRECISION
            price = remove_exponent(abs(total) / abs(quantity))
        self._data[JSF.TRADES].append({
            "id": self._next_id(JSF.TRADES),
            "number": row["ID"],
            "timestamp": self._timestamp(row),
            "settlement": 0,      # the export states none
            "account": self._account_id,
            "symbol": self._instrument_symbol(row),
            "quantity": quantity,
            "price": price,
            "fee": Decimal('0'),
            "note": ''
        })

    def _load_dividend(self, row: dict) -> None:
        self._check_row_currency(row, "Currency (Price / share)")
        tax = self._amount(row, "Withholding tax", mandatory=False)
        if tax:
            # 'Total' is the money that reached the account and the tax is stated beside it, so the gross is their
            # sum. Every sample this module was written against had a zero tax, which is why the first non-zero one
            # is worth a look before it is trusted.
            logging.warning(self.tr("Dividend with a withholding tax - check the gross amount: ") + f"{row}")
        if row["Currency (Withholding tax)"] and row["Currency (Withholding tax)"] != self._currency:
            raise Statement_ImportError(self.tr("Withholding tax in another currency: ")
                                        + row["Currency (Withholding tax)"])
        amount = self._amount(row, "Total") + tax
        self._data[JSF.ASSET_PAYMENTS].append({
            "id": self._next_id(JSF.ASSET_PAYMENTS),
            "type": JSF.PAYMENT_DIVIDEND,
            "account": self._account_id,
            "timestamp": self._timestamp(row),
            "number": row["ID"],       # empty for a dividend, which is what the export gives
            "symbol": self._instrument_symbol(row),
            "amount": amount,
            "tax": tax,
            "description": f'{row["Ticker"]}({row["ISIN"]}) CASH DIVIDEND {self._currency} '
                           f'{row["Price / share"]} PER SHARE'
        })

    def _load_interest(self, row: dict) -> None:
        self._add_income(row, row["Notes"] or self.InterestNote)

    def _load_cashback(self, row: dict) -> None:
        self._add_income(row, row["Notes"] or self.CashbackNote)

    # Interest on the cash balance and the cashback of the card are both a payment the broker makes into the
    # account, so both are recorded the way the account already records them - an income under 'Interest', with
    # the broker as its peer. 'peer' stays 0 here and is resolved once the account is known, in _resolve_peer().
    def _add_income(self, row: dict, description: str) -> None:
        self._data[JSF.INCOME_SPENDING].append({
            "id": self._next_id(JSF.INCOME_SPENDING),
            "timestamp": self._timestamp(row),
            "account": self._account_id,
            "peer": 0,
            "lines": [{"amount": self._amount(row, "Total"),
                       "category": PredefinedCategory.Interest,
                       "description": description}]
        })

    # A card purchase carries no peer and no category of its own - the merchant string the acquirer sent is not a
    # peer of this ledger ("PASTELARIA NILO LDA" is a bakery the user calls something else), and Trading 212's
    # merchant category is an acquirer's code rather than a spending category. Both are chosen by the user in
    # CardImportDialog, for the rows that are not in the database already.
    def _load_card(self, row: dict) -> None:
        operation_id = self._next_id(JSF.INCOME_SPENDING)
        timestamp = self._timestamp(row)
        amount = self._amount(row, "Total")
        merchant = row["Merchant name"]
        self._data[JSF.INCOME_SPENDING].append({
            "id": operation_id,
            "timestamp": timestamp,
            "account": self._account_id,
            "peer": 0,
            "lines": [{"amount": amount, "category": 0, "description": merchant}]
        })
        self._card_rows.append({"id": operation_id, "timestamp": timestamp, "amount": amount,
                                "merchant": merchant, "merchant_category": row["Merchant category"]})

    # ------------------------------------------------------------------------------------------------------------------
    def match_db_ids(self):
        super().match_db_ids()   # currencies and assets; the account matches nothing, as the file names none
        self._resolve_account()
        self._resolve_peer()
        self._review_card_operations()

    # The account is not matched but named - by the user, once, in the preferences. Everything else about the
    # import depends on it, so a setting that is missing or points at something else stops the import here.
    def _resolve_account(self) -> None:
        account_id = JalSettings().getInt(T212_ACCOUNT_SETTING)
        if not account_id:
            raise Statement_ImportError(
                self.tr("No account is set for Trading 212 import - choose one in Settings, Preferences, Import"))
        account = JalAccount(account_id)
        if not account.name():
            raise Statement_ImportError(self.tr("The account set for Trading 212 import doesn't exist: ")
                                        + f"{account_id}")
        currency = JalAsset(account.currency()).symbol()
        if currency != self._currency:
            raise Statement_ImportError(self.tr("The account set for Trading 212 import is in another currency: ")
                                        + f"{account.name()}/{currency} vs {self._currency}")
        self.set_mapped_id(JSF.ACCOUNTS, self._account_id, account_id)

    # The broker as it is recorded on the operations of this account. _import_imcomes_and_spendings() falls back to
    # the organization of the account, which is only right when the account names one - and an account created
    # before that field was filled in doesn't.
    def _resolve_peer(self) -> None:
        peer_id = JalAccount(self.mapped_id(JSF.ACCOUNTS, self._account_id)).organization()
        if not peer_id:
            peer_id = JalPeer(data={'name': self.BrokerName}, search=True, create=True).id()
        card_ids = {x['id'] for x in self._card_rows}
        for operation in self._data[JSF.INCOME_SPENDING]:
            if operation['id'] not in card_ids:
                operation['peer'] = peer_id

    # The base class asks for confirmation whenever the statement period starts before the last operation stored on
    # the account. On this account that is every single import: card purchases are typed in on the day they happen,
    # so the last stored operation always sits inside the month the next statement covers, and a question that is
    # always asked is a question that is always clicked away. What it is really about - a statement of a period that
    # is already behind, whose interest and cashback rows have no way of recognizing themselves and would be stored
    # a second time - is the case where the whole period ENDS before the last stored operation, and that is what is
    # asked here instead.
    def _check_period(self, period):
        if len(period) != 2:
            raise Statement_ImportError(self.tr("Statement period is invalid"))
        account_id = self.mapped_id(JSF.ACCOUNTS, self._account_id)
        if not account_id:
            return
        account = JalAccount(account_id)
        if period[1] < account.last_operation_date():
            if QMessageBox().warning(None, self.tr("Confirmation"),
                                     self.tr("This statement is older than what is recorded for the account ")
                                     + f'"{account.name()}"\n'
                                     + self.tr("Interest and cashback rows will be stored a second time. Continue?"),
                                     QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                raise Statement_ImportError(self.tr("Statement import was cancelled"))

    # ------------------------------------------------------------------------------------------------------------------
    # Shows the card purchases of the statement next to the ones the database holds already and imports what the
    # user confirms. Everything else about this import is decided by the data; this is decided by the user, because
    # a hand-typed purchase and a statement row can only be recognized as one and the same purchase by resemblance.
    def _review_card_operations(self) -> None:
        if not self._card_rows:
            return
        account_id = self.mapped_id(JSF.ACCOUNTS, self._account_id)
        begin, end = self.period()
        stored = CardMatcher.stored_operations(account_id, begin, end)
        proposal = CardMatcher.propose(self._card_rows, stored)
        decisions = self._card_decisions(proposal)
        if decisions is None:
            raise Statement_ImportError(self.tr("Statement import was cancelled"))
        operations = {x['id']: x for x in self._data[JSF.INCOME_SPENDING]}
        imported = []
        for row, decision in zip(self._card_rows, decisions):
            operation = operations[row['id']]
            if not decision['import']:
                self._skip(self.tr("card purchase is in the database already"), row['merchant'])
                self._data[JSF.INCOME_SPENDING].remove(operation)
                continue
            operation['peer'] = decision['peer']
            operation['lines'][0]['category'] = decision['category']
            operation['lines'][0]['description'] = decision['description']
            imported.append(operation)
        logging.info(self.tr("Card purchases to import: ") + f"{len(imported)}/{len(self._card_rows)}")

    # Returns one decision per card row ({'import', 'peer', 'category', 'description'}), or None if the user
    # cancelled. A test says what the dialog would have said through _card_decisions_for_tests.
    def _card_decisions(self, proposal: list):
        if "pytest" in sys.modules:
            return self._card_decisions_for_tests
        # Imported on use: every statement module is imported at start-up just to read its name, and this one is
        # the only thing here that pulls in the widget layer.
        from jal.widgets.card_import_dialog import CardImportDialog
        dialog = CardImportDialog(self._card_rows, proposal, QApplication.activeWindow(),
                                  title=self.tr("Trading 212 card purchases"))
        return dialog.decisions() if dialog.exec() else None
