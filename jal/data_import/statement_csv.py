import csv
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from zipfile import ZipFile, BadZipFile

from jal.data_import.statement import Statement, JSF, Statement_ImportError


# ----------------------------------------------------------------------------------------------------------------------
# Base class for statements that a centralized crypto exchange hands over as a zip of CSV files.
#
# The zip is read entry by entry and never extracted. That is not a preference but a requirement of the format:
# Bitget names one of its entries "Export deposit/withdrawal records ....csv", so extracting silently creates a
# directory called "Export deposit" and hides the file from a flat listing, and every Bitget entry carries the export
# timestamp in its name ("...22:44:26.454.csv"), which can't be written to disk on Windows at all.
class StatementCSV(Statement):
    StatementName = ""
    DateFormat = "%Y-%m-%d %H:%M:%S"
    # An exchange writes the export moment into its file names, so a file is recognized by the label it starts with
    # and never by its full name. Subclasses map their own label -> internal key here.
    Files = {}
    # KuCoin writes this single line into a file that has no data instead of leaving it with the header alone.
    # A row consisting of it is not data and is dropped before a parser ever sees it.
    NoDataMarker = "No matching records found."
    # A crypto exchange puts fiat money and coins in the very same ledger column and never says which is which, yet
    # the two are accounted quite differently - the fiat is the currency of the account while a coin is an asset
    # held on it. The distinction is drawn by this explicit list rather than by a rule, because there is no rule: a
    # ticker looks the same either way. A statement holding a fiat that isn't listed here stops the import with a
    # message naming it, which is the only safe outcome - guessing it wrong misfiles every balance of that currency.
    FiatCurrencies = ['EUR', 'USD', 'GBP', 'CHF', 'JPY', 'CAD', 'AUD', 'PLN', 'CZK', 'SEK', 'NOK', 'DKK',
                      'HUF', 'RON', 'BGN', 'TRY', 'BRL', 'MXN', 'ZAR', 'INR', 'IDR', 'VND', 'RUB', 'UAH']

    # The single fiat currency the statement is denominated in - it becomes the currency of the JAL account, with
    # every coin held as an asset on it. Anything but exactly one is an ambiguity that has to be resolved by hand.
    def _account_currency(self, currencies) -> str:
        fiat = sorted({x for x in currencies if x.upper() in self.FiatCurrencies})
        if len(fiat) == 1:
            return fiat[0]
        if not fiat:
            raise Statement_ImportError(
                self.tr("Statement has no fiat currency to denominate the account in. Currencies found: ")
                + f"{sorted(set(currencies))}")
        raise Statement_ImportError(self.tr("Statement holds several fiat currencies, which needs one account "
                                            "per currency and isn't supported: ") + f"{fiat}")

    def __init__(self):
        super().__init__()
        self._data = {}
        self._files = {}      # internal key -> list of parsed rows (each a dict of column -> value)
        self._entries = []    # names of the archive entries, as some exchanges put data only in the file name

    # Loads every CSV of the archive into self._files, keyed by the label its name starts with.
    def load(self, filename: str) -> None:
        self._reset_id_map()
        self._data = {
            JSF.PERIOD: [None, None],
            JSF.ACCOUNTS: [],
            JSF.ASSETS: [],
            JSF.TRADES: [],
            JSF.TRANSFERS: [],
            JSF.SWAPS: [],
            JSF.ASSET_PAYMENTS: []
        }
        self._files = {}
        self._entries = []
        try:
            with ZipFile(filename) as zip_file:
                for entry in zip_file.namelist():
                    if entry.endswith('/') or not entry.lower().endswith('.csv'):
                        continue
                    self._entries.append(entry)
                    key = self._file_key(entry)
                    if key is None:
                        logging.warning(self.tr("Unknown file in statement archive was skipped: ") + entry)
                        continue
                    if key in self._files:
                        raise Statement_ImportError(self.tr("Duplicate file in statement archive: ") + entry)
                    with zip_file.open(entry) as csv_file:
                        self._files[key] = self._parse_csv(csv_file.read(), entry)
        except BadZipFile:
            raise Statement_ImportError(self.tr("Can't read statement archive: ") + filename)
        missing = [x for x in self.Files.values() if x not in self._files]
        if missing:
            logging.warning(self.tr("Statement archive has no file(s) for: ") + f"{missing}")
        self._load_statement()
        logging.info(self.tr("Statement loaded successfully: ") + f"{self.StatementName}")

    # Returns the internal key of an archive entry, or None if its label isn't a known one. Labels are matched
    # longest first so that a label that is a prefix of another one can't shadow it ("Export spot order details"
    # would otherwise be swallowed by "Export spot order"). The full entry name is tried before the last path
    # segment because a '/' in it may belong to the name rather than to a folder - Bitget really does ship an entry
    # called "Export deposit/withdrawal records ....csv".
    def _file_key(self, entry: str):
        for name in (entry, entry.rsplit('/', 1)[-1]):
            for label in sorted(self.Files, key=len, reverse=True):
                if name.startswith(label):
                    return self.Files[label]
        return None

    # Turns the raw bytes of one CSV into a list of dicts. Handles the BOM and CRLF that both exchanges write and
    # drops the "no data" sentinel. A row with more fields than the header is accepted while the surplus is empty -
    # Bitget ends some rows with a stray comma - but surplus that carries a VALUE means the file is not shaped the
    # way the parser believes, so it is refused rather than read with the columns silently misaligned.
    def _parse_csv(self, raw: bytes, entry: str) -> list:
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise Statement_ImportError(self.tr("Can't decode statement file: ") + entry)
        reader = csv.reader(StringIO(text, newline=''))
        try:
            header = next(reader)
        except StopIteration:
            logging.warning(self.tr("Statement file is empty: ") + entry)
            return []
        header = [self._clean(x) for x in header]
        rows = []
        for values in reader:
            if not values or all(not self._clean(x) for x in values):
                continue
            if len(values) == 1 and self._clean(values[0]) == self.NoDataMarker:
                continue
            if len(values) < len(header):
                raise Statement_ImportError(
                    self.tr("Statement file row has too few fields: ") + f"{entry}: {values}")
            if len(values) > len(header) and any(self._clean(x) for x in values[len(header):]):
                raise Statement_ImportError(
                    self.tr("Statement file row has unexpected data: ") + f"{entry}: {values}")
            rows.append({name: self._clean(value) for name, value in zip(header, values)})
        return rows

    # An exchange writes a long numeric id as "\t1370787868406525953" so that a spreadsheet doesn't turn it into a
    # float. That tab isn't data - it is stripped here along with any other surrounding whitespace.
    @staticmethod
    def _clean(value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    # Rows of a statement file by its internal key (empty list when the archive didn't carry that file)
    def _rows(self, key: str) -> list:
        return self._files.get(key, [])

    # Verifies that a file carries exactly the columns the parser expects. A source that silently adds or renames a
    # column is the way these statements break, and a missing column must stop the import rather than be read as an
    # empty value for every row.
    def _check_columns(self, key: str, columns: list) -> None:
        rows = self._rows(key)
        if not rows:
            return
        missing = [x for x in columns if x not in rows[0]]
        if missing:
            raise Statement_ImportError(self.tr("Column(s) not found in statement file: ")
                                        + f"{key}: {missing}")

    # Every file of the archive that carries data but that this parser has no use for. Such a file is the sign that
    # the export contains an operation the parser was never written for - a margin trade, an Earn subscription - so
    # it is refused rather than silently dropped, which would leave the imported balances wrong.
    def _refuse_unhandled(self, handled: list) -> None:
        unhandled = sorted(key for key, rows in self._files.items() if rows and key not in handled)
        if unhandled:
            raise Statement_ImportError(
                self.tr("Statement contains operations that aren't supported yet: ") + f"{unhandled}")

    def _timestamp(self, value: str) -> int:
        try:
            return int(datetime.strptime(value, self.DateFormat).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            raise Statement_ImportError(self.tr("Can't read timestamp: ") + f"'{value}'")

    # An amount is kept as Decimal: these statements carry up to 18 significant digits and a float would round the
    # balance checks away. An empty cell means the exchange wrote no value, which is zero.
    @staticmethod
    def _amount(value: str) -> Decimal:
        if value is None or value == '':
            return Decimal('0')
        try:
            return Decimal(value.replace(',', ''))
        except (InvalidOperation, AttributeError):
            raise Statement_ImportError(f"Can't read amount: '{value}'")

    def _load_statement(self):
        raise NotImplementedError("_load_statement() method is not defined in subclass of StatementCSV")
