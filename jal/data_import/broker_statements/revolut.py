import csv
import logging
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QT_TRANSLATE_NOOP
from PySide6.QtWidgets import QApplication, QMessageBox

from jal.constants import PredefinedCategory
from jal.data_import.card_match import CardMatcher
from jal.data_import.statement import JSF, Statement, Statement_ImportError
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.db import JalDB
from jal.db.peer import JalPeer
from jal.db.settings import JalSettings
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor, SettingType

JAL_STATEMENT_CLASS = "StatementRevolut"

# The accounts a Revolut statement belongs to. The export names none of them - it has no account number, no IBAN and
# no header block, only a 'Product' column that says which of the user's Revolut pockets a row belongs to. So the
# accounts are named by the user, once, in Settings->Preferences->Import, one setting per product.
REVOLUT_CURRENT_ACCOUNT_SETTING = "RevolutCurrentAccount"
REVOLUT_DEPOSIT_ACCOUNT_SETTING = "RevolutDepositAccount"

SettingsRegistry.register(SettingDescriptor(
    key=REVOLUT_CURRENT_ACCOUNT_SETTING,
    page=QT_TRANSLATE_NOOP("Preferences", "Import"),
    label=QT_TRANSLATE_NOOP("Preferences", "Revolut current account"),
    type=SettingType.Account, default=0,
    tooltip=QT_TRANSLATE_NOOP("Preferences",
                              "The account the 'Current' rows of a Revolut statement are imported into. Such an "
                              "export names no account, so the import can't tell which one a file belongs to and "
                              "asks here instead.")))
SettingsRegistry.register(SettingDescriptor(
    key=REVOLUT_DEPOSIT_ACCOUNT_SETTING,
    page=QT_TRANSLATE_NOOP("Preferences", "Import"),
    label=QT_TRANSLATE_NOOP("Preferences", "Revolut savings account"),
    type=SettingType.Account, default=0,
    tooltip=QT_TRANSLATE_NOOP("Preferences",
                              "The account the 'Deposit' rows of a Revolut statement are imported into - the "
                              "interest of the savings pocket and the money moved into and out of it.")))


# ----------------------------------------------------------------------------------------------------------------------
# Revolut hands its history over as a single flat CSV: a header line and one row per event. One file covers SEVERAL
# accounts - the 'Product' column tells the current account from the savings pocket - and both ends of a movement
# between them are in it, which is what lets such a movement be stored as one transfer.
#
# The file is written in the language the Revolut app is set to, and there is no way to ask it for another one. Only
# three things are localized: the header, the 'Type' and the 'State'; everything the module decides is decided from
# those, never from a description. Revolut writes descriptions in a mixture of languages within one and the same
# file ("Transferência para ..." next to "From Flexible Cash Funds"), so a description is shown to the user and is
# never read by the code.
#
# What the module does NOT import is money whose other end the file doesn't name: a top-up, a transfer to a person
# or to a pocket that isn't one of the two accounts above. The file states the amount but never the account it came
# from or went to, and this ledger records those against a specific account of its own - so they are counted and
# reported as skipped, and stay the user's to enter. See _classify_current().
class StatementRevolut(Statement):
    # Revolut writes its timestamps on the wall clock of the account's country, not in UTC: matching four years of
    # this ledger against the file shows an offset of exactly zero from November to March and exactly one hour from
    # April to October, which is WET/WEST. The zone belongs to the account rather than to the file, so an account
    # opened in another country would need this to follow it.
    source_timezone = 'Europe/Lisbon'
    BrokerName = "Revolut"   # the peer the operations of such an account are recorded against

    CURRENT = 'current'      # the products this module knows, as the keys everything below is written against
    DEPOSIT = 'deposit'

    # Canonical column keys and the headers that carry them. A file whose header holds anything else is refused:
    # an unknown column may be money that belongs to an operation, and a missing one is a format that changed.
    # The Portuguese spellings are taken from a real export; the English ones are Revolut's own names for the same
    # columns. An unrecognized header stops the import by name rather than being guessed at.
    Columns = ('type', 'product', 'started', 'completed', 'description', 'amount', 'fee', 'currency', 'state',
               'balance')
    Headers = {
        'Type': 'type', 'Tipo': 'type',
        'Product': 'product', 'Produto': 'product',
        'Started Date': 'started', 'Data de início': 'started',
        'Completed Date': 'completed', 'Data de Conclusão': 'completed',
        'Description': 'description', 'Descrição': 'description',
        'Amount': 'amount', 'Montante': 'amount',
        'Fee': 'fee', 'Comissão': 'fee',
        'Currency': 'currency', 'Moeda': 'currency',
        'State': 'state', 'Estado': 'state',
        'Balance': 'balance', 'Saldo': 'balance'
    }
    Products = {'Current': CURRENT, 'Atual': CURRENT, 'Deposit': DEPOSIT, 'Depósito': DEPOSIT}
    # Only a completed row moved money - a reverted or a pending one carries no balance at all and is skipped.
    COMPLETED = 'completed'
    States = {'COMPLETED': COMPLETED, 'CONCLUÍDA': COMPLETED,
              'REVERTED': 'reverted', 'REVERTIDA': 'reverted',
              'PENDING': 'pending', 'PENDENTE': 'pending',
              'DECLINED': 'declined', 'RECUSADA': 'declined'}
    # Operation kinds. The value is what _classify_current() dispatches on; an unknown 'Type' stops the import.
    CARD_PAYMENT, TRANSFER, TOPUP, INTEREST = 'card_payment', 'transfer', 'topup', 'interest'
    ATM, FEE, REFUND, CASHBACK = 'atm', 'fee', 'refund', 'cashback'
    Types = {
        'CARD_PAYMENT': CARD_PAYMENT, 'Pagamento com cartão': CARD_PAYMENT,
        'TRANSFER': TRANSFER, 'Transferência': TRANSFER,
        'TOPUP': TOPUP, 'Carregamento': TOPUP,
        'INTEREST': INTEREST, 'Juros': INTEREST,
        'ATM': ATM,
        'FEE': FEE, 'Taxa': FEE,
        'CARD_REFUND': REFUND, 'Devolução do cartão de débito': REFUND,
        'CARD_CHARGEBACK': REFUND, 'Estorno de pagamento com cartão': REFUND,
        'CASHBACK': CASHBACK, 'Recompensa': CASHBACK,
        'REVOLUT_PAYMENT': CARD_PAYMENT, 'Pagamento Revolut': CARD_PAYMENT
    }
    # The kinds that become one spending or income each, reviewed by the user before anything is stored. They are
    # all money that left or reached the account without a second account of this ledger on the other end.
    ReviewedTypes = (CARD_PAYMENT, ATM, FEE, REFUND, CASHBACK)
    # ... and the kinds that state an amount and nothing about the other end of the movement. See _classify_current().
    UnplaceableTypes = (TOPUP, TRANSFER)
    DateTimeFormat = "%Y-%m-%d %H:%M:%S"

    # What a test puts here instead of opening CardImportDialog - the same arrangement Trading 212 uses.
    _card_decisions_for_tests = None

    def __init__(self):
        super().__init__()
        self.name = self.tr("R&evolut")   # '&R' belongs to "T&rading 212" and '&V' to "&VTB Investments"
        self.icon_name = "revolut.png"
        self.filename_filter = self.tr("Revolut statement (*.csv)")
        self._currency = ''
        self._account_ids = {}      # product -> statement-local account id, for the products the file holds
        self._card_rows = []        # statement-local ids of the reviewed operations, in file order
        self._interest_rows = []    # {'id', 'product', 'day'} of the interest operations, to drop the stored ones

    # ------------------------------------------------------------------------------------------------------------------
    def load(self, filename: str) -> None:
        self._reset_id_map()
        self._data = {JSF.PERIOD: [None, None], JSF.ACCOUNTS: [], JSF.ASSETS: [],
                      JSF.TRANSFERS: [], JSF.INCOME_SPENDING: []}
        self._card_rows = []
        self._interest_rows = []
        self._account_ids = {}
        rows = self._read_csv(filename)
        self._currency = self._statement_currency(rows)
        self._check_balances(rows)
        rows = self._completed_only(rows)
        if not rows:
            raise Statement_ImportError(self.tr("Statement has no completed operations: ") + filename)
        self._create_accounts(rows)
        self._data[JSF.PERIOD] = [min(x['timestamp'] for x in rows), max(x['timestamp'] for x in rows)]
        for row in self._load_internal_transfers(rows):
            if row['product'] == self.DEPOSIT:
                self._classify_deposit(row)
            else:
                self._classify_current(row)
        logging.info(self.tr("Statement loaded successfully: ") + self.name)

    # Reads the file into rows whose columns, product, state and type are the canonical values of this module.
    # Everything the file says that this module doesn't know stops the import here, naming what it was.
    def _read_csv(self, filename: str) -> list:
        try:
            with open(filename, 'r', encoding='utf-8-sig', newline='') as csv_file:
                reader = csv.DictReader(csv_file)
                if reader.fieldnames is None:
                    raise Statement_ImportError(self.tr("Statement file is empty: ") + filename)
                columns = {}
                for header in [x.strip() for x in reader.fieldnames]:
                    if header not in self.Headers:
                        raise Statement_ImportError(self.tr("Statement has a column this module doesn't know: ")
                                                    + header)
                    columns[header] = self.Headers[header]
                missing = [x for x in self.Columns if x not in columns.values()]
                if missing:
                    raise Statement_ImportError(self.tr("Statement misses mandatory column(s): ") + f"{missing}")
                rows = [{columns[key.strip()]: (value or '').strip()
                         for key, value in row.items() if key is not None} for row in reader]
        except OSError as err:
            raise Statement_ImportError(self.tr("Failed to read file: ") + str(err))
        except csv.Error as err:
            raise Statement_ImportError(self.tr("Failed to parse CSV file: ") + str(err))
        if not rows:
            raise Statement_ImportError(self.tr("Statement has no operations: ") + filename)
        for row in rows:
            row['product'] = self._known(self.Products, row['product'], self.tr("Unknown Revolut product: "))
            row['state'] = self._known(self.States, row['state'], self.tr("Unknown Revolut operation state: "))
            row['type'] = self._known(self.Types, row['type'], self.tr("Unsupported Revolut operation: "))
            row['amount'] = self._amount(row, 'amount')
            row['fee'] = self._amount(row, 'fee')
            row['timestamp'] = self._timestamp(row)
        return rows

    @staticmethod
    def _known(vocabulary: dict, value: str, complaint: str):
        try:
            return vocabulary[value]
        except KeyError:
            raise Statement_ImportError(complaint + f"'{value}'")

    # Revolut states a moment twice: when the operation started and when it was completed, a day or two later. The
    # one that matters is when it STARTED - that is when the card was used, which is the moment the user typed in
    # and the only one a hand-entered purchase can be recognized by (see CardMatcher).
    def _timestamp(self, row: dict) -> int:
        try:
            return self._moment(datetime.strptime(row['started'], self.DateTimeFormat))
        except ValueError:
            raise Statement_ImportError(self.tr("Can't read operation timestamp: ") + f"{row['started']}")

    def _amount(self, row: dict, column: str) -> Decimal:
        value = row[column]
        if not value:
            return Decimal('0')
        try:
            return Decimal(value)
        except InvalidOperation:
            raise Statement_ImportError(self.tr("Can't read a number: ") + f"'{column}'='{value}'")

    # The single currency the file is denominated in - it is the currency of every account it is about.
    def _statement_currency(self, rows: list) -> str:
        currencies = sorted({row['currency'] for row in rows if row['currency']})
        if len(currencies) != 1:
            raise Statement_ImportError(self.tr("Statement must have exactly one currency, found: ") + f"{currencies}")
        return currencies[0]

    # What every row of this file says about itself: the balance it left behind is the previous one plus the amount
    # less the fee. Checking it is what makes the two meanings of the fee column safe to rely on - it is a card
    # charge on a purchase and a withholding tax on an interest payment, and either way it is money that left on top
    # of the amount. The check is on the STEP between two rows of a product rather than on a running total, so it
    # holds for an export of one month as much as for the whole history.
    def _check_balances(self, rows: list) -> None:
        previous = {}
        for row in rows:
            if row['state'] != self.COMPLETED:
                continue    # a reverted or pending row moved nothing and states no balance
            balance = self._amount(row, 'balance')
            expected = previous.get(row['product'])
            if expected is not None and balance != expected + row['amount'] - row['fee']:
                raise Statement_ImportError(
                    self.tr("Statement balance doesn't match its own operations: ")
                    + f"{row['started']} '{row['description']}' {row['amount']}/{row['fee']} -> {balance}, "
                    + self.tr("expected ") + f"{expected + row['amount'] - row['fee']}")
            previous[row['product']] = balance

    def _completed_only(self, rows: list) -> list:
        completed = []
        for row in rows:
            if row['state'] == self.COMPLETED:
                completed.append(row)
            else:
                self._skip(self.tr("operations that were not completed"), row['description'])
        return completed

    # One account record per product the file holds. No 'number': the file names no account, so there is nothing to
    # match one by - _resolve_accounts() maps these records onto the accounts the user chose.
    def _create_accounts(self, rows: list) -> None:
        for product in sorted({row['product'] for row in rows}):
            account_id = self._next_id(JSF.ACCOUNTS)
            self._account_ids[product] = account_id
            self._data[JSF.ACCOUNTS].append({"id": account_id, "name": f"{self.BrokerName} {product}",
                                             "currency": self.currency_id(self._currency)})

    # ------------------------------------------------------------------------------------------------------------------
    # Money moved between the current account and the savings pocket appears TWICE in the file - once on each side,
    # at the very same second and with opposite amounts - and the two rows are one movement of the ledger. They are
    # paired here and stored as a transfer; what is left is returned for the per-product classification.
    #
    # A pocket row that finds no counterpart is refused rather than skipped: the pocket has no other source of money
    # than the current account, so a movement of it that this file can't place would leave the imported balance
    # wrong without anything saying so.
    def _load_internal_transfers(self, rows: list) -> list:
        pocket_legs = [i for i, x in enumerate(rows) if x['product'] == self.DEPOSIT and x['type'] == self.TRANSFER]
        available = {}
        for index, row in enumerate(rows):
            if row['product'] == self.CURRENT and row['type'] == self.TRANSFER:
                available.setdefault((row['timestamp'], row['amount']), []).append(index)
        paired = set(pocket_legs)
        for index in pocket_legs:
            leg = rows[index]
            key = (leg['timestamp'], -leg['amount'])
            if not available.get(key):
                raise Statement_ImportError(self.tr("Savings pocket movement has no counterpart in the statement: ")
                                            + f"{leg['started']} '{leg['description']}' {leg['amount']}")
            paired.add(available[key].pop())
            self._add_transfer(leg)
        # Rows are picked out by their POSITION rather than by their content: two rows of a statement may well hold
        # the very same values, and dropping both because one of them was paired would lose an operation.
        return [row for index, row in enumerate(rows) if index not in paired]

    def _add_transfer(self, leg: dict) -> None:
        symbol = self._single_symbol_record_of(self.currency_id(self._currency))['id']
        into_pocket = leg['amount'] > 0
        source = self.CURRENT if into_pocket else self.DEPOSIT
        target = self.DEPOSIT if into_pocket else self.CURRENT
        self._data[JSF.TRANSFERS].append({
            "id": self._next_id(JSF.TRANSFERS),
            "account": [self._account_ids[source], self._account_ids[target], 0],
            "symbol": [symbol, symbol],
            "timestamp": leg['timestamp'],
            "withdrawal": abs(leg['amount']),
            "deposit": abs(leg['amount']),
            "fee": Decimal('0'),
            "number": '',
            "description": leg['description']
        })

    # The savings pocket earns interest and holds nothing else - every other movement of it was paired away as a
    # transfer, so anything left here is a kind of row this module has never seen on such an account.
    def _classify_deposit(self, row: dict) -> None:
        if row['type'] != self.INTEREST:
            raise Statement_ImportError(self.tr("Unsupported operation on the savings pocket: ")
                                        + f"{row['started']} '{row['description']}' ({row['type']})")
        self._add_interest(row)

    def _classify_current(self, row: dict) -> None:
        if row['type'] == self.INTEREST:
            self._add_interest(row)
        elif row['type'] in self.ReviewedTypes:
            self._add_reviewed(row)
        elif row['type'] in self.UnplaceableTypes:
            # A top-up, or a transfer to a person or to a pocket that is not the savings account of this import.
            # The file states the amount and nothing about the other end, and this ledger books such a movement
            # against a specific account of its own - so it is counted and reported instead of being invented.
            self._skip(self.tr("movements whose other end the statement doesn't name"), row['description'])
        else:
            # A kind of row that 'Types' knows and this method was never taught to place. It is listed rather than
            # fallen through to a skip, so that adding a kind above without deciding what it is stops the import.
            raise Statement_ImportError(self.tr("Unplaced Revolut operation: ")
                                        + f"{row['started']} '{row['description']}' ({row['type']})")

    # Interest is stored the way the deposits of this ledger already store it: the gross the bank credited, and the
    # tax it withheld beside it as a line of its own. The fee column carries that tax on an interest row (the
    # balance moves by the difference, which _check_balances() has verified), so nothing here is inferred.
    def _add_interest(self, row: dict) -> None:
        operation_id = self._next_id(JSF.INCOME_SPENDING)
        lines = [{"amount": row['amount'], "category": PredefinedCategory.Interest,
                  "description": row['description']}]
        if row['fee']:
            lines.append({"amount": -row['fee'], "category": PredefinedCategory.Taxes,
                          "description": row['description']})
        self._data[JSF.INCOME_SPENDING].append({
            "id": operation_id, "timestamp": row['timestamp'],
            "account": self._account_ids[row['product']], "peer": 0, "lines": lines})
        self._interest_rows.append({"id": operation_id, "product": row['product'],
                                    "day": self._day_of(row['timestamp'])})

    # A purchase, a refund, a reward: money that moved without a second account of this ledger on the other end.
    # It carries no peer and no category of its own - the string Revolut prints is the merchant as the acquirer
    # sent it, not a peer of this ledger, and there is no category in the file at all. Both are chosen by the user
    # in CardImportDialog, for the rows that are not in the database already.
    #
    # The merchant string describes the operation and is kept as its note.
    #
    # What is stored is the amount less the fee - the money that actually left the account - which is how such a
    # purchase is already recorded here.
    def _add_reviewed(self, row: dict) -> None:
        operation_id = self._next_id(JSF.INCOME_SPENDING)
        amount = row['amount'] - row['fee']
        self._data[JSF.INCOME_SPENDING].append({
            "id": operation_id, "timestamp": row['timestamp'],
            "account": self._account_ids[row['product']], "peer": 0, "description": row['description'],
            "lines": [{"amount": amount, "category": 0, "description": ''}]})
        self._card_rows.append({"id": operation_id, "timestamp": row['timestamp'], "amount": amount,
                                "merchant": row['description'], "merchant_category": ''})

    @staticmethod
    def _day_of(timestamp: int) -> str:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

    # ------------------------------------------------------------------------------------------------------------------
    def match_db_ids(self):
        super().match_db_ids()   # currencies; the accounts match nothing, as the file names none
        self._resolve_accounts()
        self._resolve_peer()
        self._drop_stored_interest()
        self._review_operations()

    # The accounts are not matched but named - by the user, once, in the preferences. Everything else about the
    # import depends on them, so a setting that is missing or points at something else stops the import here. Only
    # the products the file actually holds are demanded: an export with no savings rows needs no savings account.
    def _resolve_accounts(self) -> None:
        settings = {self.CURRENT: (REVOLUT_CURRENT_ACCOUNT_SETTING, self.tr("Revolut current account")),
                    self.DEPOSIT: (REVOLUT_DEPOSIT_ACCOUNT_SETTING, self.tr("Revolut savings account"))}
        for product, statement_id in self._account_ids.items():
            key, title = settings[product]
            account_id = JalSettings().getInt(key)
            if not account_id:
                raise Statement_ImportError(
                    self.tr("No account is set for Revolut import - choose one in Settings, Preferences, Import: ")
                    + title)
            account = JalAccount(account_id)
            if not account.name():
                raise Statement_ImportError(self.tr("The account set for Revolut import doesn't exist: ")
                                            + f"{title}/{account_id}")
            currency = JalAsset(account.currency()).symbol()
            if currency != self._currency:
                raise Statement_ImportError(self.tr("The account set for Revolut import is in another currency: ")
                                            + f"{account.name()}/{currency} vs {self._currency}")
            self.set_mapped_id(JSF.ACCOUNTS, statement_id, account_id)

    # The bank as it is recorded on the operations of these accounts. _import_imcomes_and_spendings() falls back to
    # the organization of the account, which is only right when the account names one - and a savings account
    # created by hand usually doesn't.
    def _resolve_peer(self) -> None:
        peer_id = 0
        for product in (self.CURRENT, self.DEPOSIT):
            if product in self._account_ids and not peer_id:
                peer_id = JalAccount(self.mapped_id(JSF.ACCOUNTS, self._account_ids[product])).organization()
        if not peer_id:
            peer_id = JalPeer(data={'name': self.BrokerName}, search=True, create=True).id()
        reviewed = {x['id'] for x in self._card_rows}
        for operation in self._data[JSF.INCOME_SPENDING]:
            if operation['id'] not in reviewed:
                operation['peer'] = peer_id

    # An interest payment carries nothing that identifies it, so a re-import would store it a second time - and
    # unlike a purchase it is never shown to the user for confirmation. Revolut pays it once a day per account, so
    # the day is what identifies it: a day that already has an interest operation on that account is left alone.
    def _drop_stored_interest(self) -> None:
        if not self._interest_rows:
            return
        operations = {x['id']: x for x in self._data[JSF.INCOME_SPENDING]}
        stored = {}
        for product, statement_id in self._account_ids.items():
            stored[product] = self._stored_interest_days(self.mapped_id(JSF.ACCOUNTS, statement_id))
        remaining = []
        for record in self._interest_rows:
            if record['day'] in stored[record['product']]:
                self._skip(self.tr("interest payments that are in the database already"), record['day'])
                self._data[JSF.INCOME_SPENDING].remove(operations[record['id']])
            else:
                remaining.append(record)
        self._interest_rows = remaining

    # The days that already carry an interest operation on the given account, within the period of the statement.
    @staticmethod
    def _stored_interest_days(account_id: int) -> set:
        timestamps = JalDB._read_to_list("SELECT DISTINCT a.timestamp FROM actions AS a "
                                         "LEFT JOIN action_details AS d ON d.pid=a.oid "
                                         "WHERE a.account_id=:account_id AND d.category_id=:interest",
                                         [(":account_id", account_id), (":interest", PredefinedCategory.Interest)])
        return {StatementRevolut._day_of(int(x)) for x in timestamps}

    # The base class asks for confirmation whenever the statement period starts before the last operation stored on
    # the account. Here that is every single import - purchases are typed in on the day they happen, so the last
    # stored operation always sits inside the period the next export covers, and a question that is always asked is
    # a question that is always clicked away. What is worth asking about is a statement of a period that is wholly
    # behind the ledger, which is what is asked here instead.
    def _check_period(self, period):
        if len(period) != 2:
            raise Statement_ImportError(self.tr("Statement period is invalid"))
        for statement_id in self._account_ids.values():
            account_id = self.mapped_id(JSF.ACCOUNTS, statement_id)
            if not account_id:
                continue
            account = JalAccount(account_id)
            if period[1] < account.last_operation_date():
                if QMessageBox().warning(None, self.tr("Confirmation"),
                                         self.tr("This statement is older than what is recorded for the account ")
                                         + f'"{account.name()}"\n' + self.tr("Continue import?"),
                                         QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                    raise Statement_ImportError(self.tr("Statement import was cancelled"))
                return

    # ------------------------------------------------------------------------------------------------------------------
    # Shows the purchases, refunds and rewards of the statement next to the ones the database holds already and
    # imports what the user confirms. Everything else about this import is decided by the data; this is decided by
    # the user, because a hand-typed purchase and a statement row can only be recognized as one and the same
    # purchase by resemblance.
    def _review_operations(self) -> None:
        if not self._card_rows:
            return
        account_id = self.mapped_id(JSF.ACCOUNTS, self._account_ids[self.CURRENT])
        begin, end = self.period()
        # 'incomes' as well as spendings: a refund and a reward are money that came in, and both are reviewed here.
        stored = CardMatcher.stored_operations(account_id, begin, end, incomes=True)
        proposal = CardMatcher.propose(self._card_rows, stored)
        decisions = self._card_decisions(proposal)
        if decisions is None:
            raise Statement_ImportError(self.tr("Statement import was cancelled"))
        operations = {x['id']: x for x in self._data[JSF.INCOME_SPENDING]}
        imported = []
        for row, decision in zip(self._card_rows, decisions):
            operation = operations[row['id']]
            if not decision['import']:
                self._skip(self.tr("operations that are in the database already"), row['merchant'])
                self._data[JSF.INCOME_SPENDING].remove(operation)
                continue
            operation['peer'] = decision['peer']
            operation['description'] = decision['description']
            operation['lines'][0]['category'] = decision['category']
            imported.append(operation)
        logging.info(self.tr("Operations to import: ") + f"{len(imported)}/{len(self._card_rows)}")

    # Returns one decision per reviewed row ({'import', 'peer', 'category', 'description'}), or None if the user
    # cancelled. A test says what the dialog would have said through _card_decisions_for_tests.
    def _card_decisions(self, proposal: list):
        if "pytest" in sys.modules:
            return self._card_decisions_for_tests
        # Imported on use: every statement module is imported at start-up just to read its name, and the widget
        # layer is not needed for that.
        from jal.widgets.card_import_dialog import CardImportDialog
        dialog = CardImportDialog(self._card_rows, proposal, QApplication.activeWindow(),
                                  title=self.tr("Revolut operations"))
        return dialog.decisions() if dialog.exec() else None
