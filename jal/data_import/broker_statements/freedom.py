import logging
import os
import re
import xml.etree.ElementTree as xml_tree
from datetime import datetime, timezone
from decimal import Decimal

from jal.data_import.statement import FOF, Statement, Statement_ImportError, Statement_Capabilities


JAL_STATEMENT_CLASS = "StatementFreedomFinance"


class StatementFreedomFinance(Statement):
    FilenamePattern = re.compile(
        r'.*_(?P<start>\d{4}-\d{2}-\d{2} \d{2}_\d{2}_\d{2})_'
        r'(?P<end>\d{4}-\d{2}-\d{2} \d{2}_\d{2}_\d{2})_all\.xml$',
        re.IGNORECASE
    )

    def __init__(self):
        super().__init__()
        self.name = self.tr("Freedom Broker (XML Eng)")
        self.icon_name = "freedom.png"
        self.filename_filter = self.tr("Freedom Finance statement (*.xml)")

    @staticmethod
    def capabilities() -> set:
        return {Statement_Capabilities.MULTIPLE_LOAD}

    @staticmethod
    def order_statements(statement_files) -> list:
        def sort_key(filename):
            match = StatementFreedomFinance.FilenamePattern.match(filename)
            if match is None:
                return '', 0, 0, filename
            account = os.path.basename(filename).split('_', 1)[0]
            start = int(datetime.strptime(match.group('start'), "%Y-%m-%d %H_%M_%S").replace(tzinfo=timezone.utc).timestamp())
            end = int(datetime.strptime(match.group('end'), "%Y-%m-%d %H_%M_%S").replace(tzinfo=timezone.utc).timestamp())
            return account, start, end, filename

        return sorted(statement_files, key=sort_key)

    def load(self, filename: str) -> None:
        self._data = {
            FOF.PERIOD: [None, None],
            FOF.ACCOUNTS: [],
            FOF.ASSETS: [],
            FOF.SYMBOLS: [],
            FOF.ASSETS_DATA: [],
            FOF.TRADES: [],
            FOF.TRANSFERS: [],
            FOF.CORP_ACTIONS: [],
            FOF.ASSET_PAYMENTS: [],
            FOF.INCOME_SPENDING: []
        }
        root = self._load_xml_root(filename)
        account_number = self._account_number_from_filename(filename)
        self._load_period(root)
        self._load_trades(root, account_number)
        self._load_dividends(root, account_number)
        logging.info(self.tr("Statement loaded successfully: ") + self.name)

    def _load_xml_root(self, filename: str):
        try:
            return xml_tree.parse(filename).getroot()
        except xml_tree.ParseError as err:
            raise Statement_ImportError(self.tr("Failed to parse XML file: ") + str(err))
        except OSError as err:
            raise Statement_ImportError(self.tr("Failed to read file: ") + str(err))

    def _load_period(self, root) -> None:
        start = self._parse_datetime(self._required_text(root, './date_start'))
        end = self._parse_datetime(self._required_text(root, './date_end'))
        self._data[FOF.PERIOD] = [start, end]

    def _account_number_from_filename(self, filename: str) -> str:
        account_number = os.path.basename(filename).split('_', 1)[0].strip()
        if account_number == '':
            raise Statement_ImportError(self.tr("Can't read account name from file name"))
        return account_number

    def _load_trades(self, root, account_number: str) -> None:
        count = 0
        for node in root.findall('./trades/detailed/node'):
            operation = self._text(node, 'operation').lower()
            if operation not in {'buy', 'sell'}:
                if operation:
                    raise Statement_ImportError(self.tr("Unsupported trade type: ") + operation)
                continue

            ticker = self._required_text(node, 'instr_nm')
            isin = self._text(node, 'isin') or self._text(node, 'issue_nb')
            currency = self._required_text(node, 'curr_c')
            quantity = self._to_decimal(self._required_text(node, 'q'))
            if operation == 'sell':
                quantity = -quantity
            price = self._to_decimal(self._required_text(node, 'p'))
            fee = self._to_decimal(self._text(node, 'commission'))
            timestamp = self._parse_datetime(self._required_text(node, 'date'))
            settlement = self._parse_date(self._required_text(node, 'pay_d'))
            account_id = self._find_account_id(account_number, currency)
            currency_id = self.currency_id(currency)
            asset_id = self.asset_id({
                'type': FOF.ASSET_STOCK,
                'symbol': self._normalize_symbol(ticker),
                'isin': isin,
                'currency': currency_id,
                'note': self._symbol_market(ticker),
                'search_offline': True
            })
            self._data[FOF.TRADES].append({
                'id': self._next_id(FOF.TRADES),
                'number': self._text(node, 'id') or self._text(node, 'trade_id') or self._text(node, 'order_id'),
                'timestamp': timestamp,
                'settlement': settlement,
                'account': account_id,
                'asset': asset_id,
                'quantity': float(quantity),
                'price': float(price),
                'fee': float(fee),
                'note': self._text(node, 'comment')
            })
            count += 1
        logging.info(self.tr("Trades loaded: ") + f"{count}")

    def _load_dividends(self, root, account_number: str) -> None:
        count = 0
        for node in root.findall('./corporate_actions/detailed/node'):
            payment_type = self._text(node, 'type_id').lower()
            if payment_type not in {'dividend', 'dividend_reverted'}:
                if payment_type:
                    logging.warning(self.tr("Skipped unsupported corporate action: ") + payment_type)
                continue

            ticker = self._required_text(node, 'ticker')
            isin = self._text(node, 'isin')
            currency = self._required_text(node, 'currency')
            net_amount = self._to_decimal(self._required_text(node, 'amount'))
            tax = abs(self._to_decimal(self._text(node, 'tax_amount')))
            gross_amount = net_amount + tax if net_amount >= 0 else net_amount - tax
            timestamp = self._parse_date(self._required_text(node, 'date'))
            ex_date = self._parse_date(self._required_text(node, 'ex_date'))
            account_id = self._find_account_id(account_number, currency)
            currency_id = self.currency_id(currency)
            asset_id = self.asset_id({
                'type': FOF.ASSET_STOCK,
                'symbol': self._normalize_symbol(ticker),
                'isin': isin,
                'currency': currency_id,
                'note': self._symbol_market(ticker),
                'search_offline': True
            })
            self._data[FOF.ASSET_PAYMENTS].append({
                'id': self._next_id(FOF.ASSET_PAYMENTS),
                'type': FOF.PAYMENT_DIVIDEND,
                'account': account_id,
                'timestamp': timestamp,
                'ex_date': ex_date,
                'asset': asset_id,
                'amount': float(gross_amount),
                'tax': float(tax),
                'description': self._text(node, 'comment')
            })
            count += 1
        logging.info(self.tr("Asset payments loaded: ") + f"{count}")

    def _required_text(self, node, path: str) -> str:
        value = self._text(node, path)
        if value == '':
            raise Statement_ImportError(self.tr("Mandatory field is empty: ") + path)
        return value

    def _text(self, node, path: str) -> str:
        found = node.find(path)
        if found is None or found.text is None:
            return ''
        return found.text.strip()

    def _next_id(self, section: str) -> int:
        return max([0] + [item['id'] for item in self._data[section]]) + 1

    def _find_account_id(self, number, currency):
        currency_id = self.currency_id(currency)
        match = [x for x in self._data[FOF.ACCOUNTS] if x.get('number') == number and x['currency'] == currency_id]
        if match:
            if len(match) == 1:
                return match[0]['id']
            raise Statement_ImportError(self.tr("Multiple accounts found: ") + f"{number}/{currency}")
        new_id = self._next_id(FOF.ACCOUNTS)
        self._data[FOF.ACCOUNTS].append({
            'id': new_id,
            'name': number,
            'number': number,
            'currency': currency_id
        })
        return new_id

    def _normalize_symbol(self, ticker: str) -> str:
        return ticker.split('.', 1)[0]

    def _symbol_market(self, ticker: str) -> str:
        return ticker.split('.', 1)[1].upper() if '.' in ticker else ''

    def _parse_datetime(self, value: str) -> int:
        return int(datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())

    def _parse_date(self, value: str) -> int:
        return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())

    def _to_decimal(self, value: str) -> Decimal:
        if value == '' or value == '-':
            return Decimal('0')
        normalized = value.replace(',', '.').strip()
        match = re.search(r'[-+]?\d+(?:\.\d+)?', normalized)
        if match is None:
            return Decimal('0')
        return Decimal(match.group(0))
