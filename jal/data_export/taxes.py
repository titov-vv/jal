import logging
from datetime import datetime, timezone
from decimal import Decimal

from PySide6.QtWidgets import QApplication
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.helpers import remove_exponent
from jal.db.operations import LedgerTransaction, Dividend, CorporateAction
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.category import JalCategory
from jal.db.country import JalCountry
from jal.db.settings import JalSettings


# -----------------------------------------------------------------------------------------------------------------------
class TaxesRus:
    BOND_PRINCIPAL = Decimal('1000')  # TODO Principal should be used from 'asset_data' table

    CorpActionText = {
        CorporateAction.SymbolChange: "Смена символа {before} {old} -> {after} {new}",
        CorporateAction.Split: "Сплит {old} {before} в {after}",
        CorporateAction.SpinOff: "Выделение компании {new} из {old}; доля выделяемого актива {share:.2f}%",
        CorporateAction.Merger: "Реорганизация компании, конвертация {share:.2f}% стоимости {before} {old} в {after} {new}",
        CorporateAction.Delisting: "Делистинг"
    }

    def __init__(self):
        self.account = None
        self.year_begin = 0
        self.year_end = 0
        self.broker_name = ''
        self.broker_iso_cc = "000"
        self.use_settlement = True
        self._processed_trade_qty = {}  # It will handle {trade_id: qty} records to keep track of already processed qty
        self.reports = {
            "Дивиденды": self.prepare_dividends,
            "Акции": self.prepare_stocks_and_etf,
            "Облигации": self.prepare_bonds,
            "ПФИ": self.prepare_derivatives,
            "Криптовалюты": self.prepare_crypto,
            "Корп.события": self.prepare_corporate_actions,
            "Комиссии": self.prepare_broker_fees,
            "Проценты": self.prepare_broker_interest
        }

    def tr(self, text):
        return QApplication.translate("TaxesRus", text)

    # Removes all keys listed in extra_keys_list from operation_dict
    def drop_extra_fields(self, operation_dict, extra_keys_list):
        for key in extra_keys_list:
            if key in operation_dict:
                del operation_dict[key]

    def prepare_tax_report(self, year, account_id, **kwargs):
        tax_report = {}
        self.account = JalAccount(account_id)
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']
        for report in self.reports:
            tax_report[report] = self.reports[report]()
        return tax_report

    # ------------------------------------------------------------------------------------------------------------------
    # Create a totals row from provided list of dictionaries
    # it calculates sum for each field in fields and adds it to return dictionary
    def insert_totals(self, list_of_values, fields):
        if not list_of_values:
            return
        totals = {"report_template": "totals"}
        for field in fields:
            totals[field] = sum([x[field] for x in list_of_values if field in x])
        list_of_values.append(totals)

    def prepare_dividends(self):
        currency = JalAsset(self.account.currency())
        dividends_report = []
        dividends = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockDividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockVesting)
        dividends = [x for x in dividends if self.year_begin <= x.timestamp() <= self.year_end]  # Only in given range
        for dividend in dividends:
            amount = dividend.amount()
            rate = currency.quote(dividend.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            price = dividend.asset().quote(dividend.timestamp(), currency.id())[1]
            country = JalCountry(dividend.asset().country())
            tax_treaty = "Да" if country.has_tax_treaty() else "Нет"
            note = ''
            if dividend.subtype() == Dividend.StockDividend:
                if not price:
                    logging.error(self.tr("No price data for stock dividend: ") + f"{dividend}")
                    continue
                amount = amount * price
                note = "Дивиденд выплачен в натуральной форме (ценными бумагами)"
            if dividend.subtype() == Dividend.StockVesting:
                if not price:
                    logging.error(self.tr("No price data for stock vesting: ") + f"{dividend}")
                    continue
                amount = amount * price
                note = "Доход получен в натуральной форме (ценными бумагами)"
            amount_rub = amount * rate
            tax_rub = dividend.tax() * rate
            tax2pay = Decimal('0.13') * amount_rub
            if tax_treaty:
                if tax2pay > tax_rub:
                    tax2pay = tax2pay - tax_rub
                else:
                    tax2pay = Decimal('0.0')
            line = {
                'report_template': "dividend",
                'payment_date': dividend.timestamp(),
                'symbol': dividend.asset().symbol(currency.id()),
                'full_name': dividend.asset().name(),
                'isin': dividend.asset().isin(),
                'amount': amount,
                'tax': dividend.tax(),
                'rate': rate,
                'country': country.name(),
                'country_iso': country.iso_code(),
                'tax_treaty': tax_treaty,
                'amount_rub': round(amount_rub, 2),
                'tax_rub': round(tax_rub, 2),
                'tax2pay': round(tax2pay, 2),
                'note': note
            }
            dividends_report.append(line)
        self.insert_totals(dividends_report, ["amount", "amount_rub", "tax", "tax_rub", "tax2pay"])
        return dividends_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_stocks_and_etf(self):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        deals_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() in [PredefinedAsset.Stock, PredefinedAsset.ETF]]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade or (
                    x.open_operation().type() == LedgerTransaction.Dividend and (
                        x.open_operation().subtype() == Dividend.StockDividend or
                        x.open_operation().subtype() == Dividend.StockVesting))]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = currency.quote(trade.open_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            c_rate = currency.quote(trade.close_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                os_rate = currency.quote(trade.open_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
                cs_rate = currency.quote(trade.close_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            short_dividend = Decimal('0')
            if trade.qty() < Decimal('0'):  # Check were there any dividends during short position holding
                dividends = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
                dividends = [x for x in dividends if
                             trade.open_operation().settlement() <= x.ex_date() <= trade.close_operation().settlement()]
                for dividend in dividends:
                    short_dividend += dividend.amount()
            note = f"Удержанный дивиденд: {short_dividend} RUB" if short_dividend > Decimal('0') else ''
            o_amount = round(trade.open_operation().price() * abs(trade.qty()), 2)
            o_amount_rub = round(o_amount * os_rate, 2)
            c_amount = round(trade.close_operation().price() * abs(trade.qty()), 2)
            c_amount_rub = round(c_amount * cs_rate, 2)
            o_fee = trade.open_operation().fee() * abs(trade.qty() / trade.open_operation().qty())
            c_fee = trade.close_operation().fee() * abs(trade.qty() / trade.close_operation().qty())
            income = c_amount if trade.qty() >= Decimal('0') else o_amount
            income_rub = c_amount_rub if trade.qty() >= Decimal('0') else o_amount_rub
            spending = o_amount if trade.qty() >= Decimal('0') else c_amount
            spending += o_fee + c_fee
            spending_rub = o_amount_rub if trade.qty() >= Decimal('0') else c_amount_rub
            spending_rub += round(o_fee * o_rate, 2) + round(c_fee * c_rate, 2) + short_dividend
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(currency.id()),
                'isin': trade.asset().isin(),
                'qty': trade.qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_operation().price(),
                'o_amount':  o_amount,
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * o_rate, 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': c_rate,
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': trade.close_operation().price(),
                'c_amount': c_amount,
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * c_rate, 2),
                'income': income,    # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub,
                's_dividend_note': note
            }
            deals_report.append(line)
        self.insert_totals(deals_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return deals_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_bonds(self):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        bonds_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Bond]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = currency.quote(trade.open_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            c_rate = currency.quote(trade.close_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                os_rate = currency.quote(trade.open_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
                cs_rate = currency.quote(trade.close_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            o_accrued_interest = trade.open_operation().get_accrued_interest()
            o_interest = -o_accrued_interest.amount() if o_accrued_interest else Decimal('0')
            o_interest_rub = round(o_interest * o_rate, 2)
            c_accrued_interest = trade.close_operation().get_accrued_interest()
            c_interest = c_accrued_interest.amount() if c_accrued_interest else Decimal('0')
            c_interest_rub = round(c_interest * c_rate, 2)
            o_amount = round(trade.open_operation().price() * abs(trade.qty()), 2)
            o_amount_rub = round(o_amount * os_rate, 2)
            c_amount = round(trade.close_operation().price() * abs(trade.qty()), 2)
            c_amount_rub = round(c_amount * cs_rate, 2)
            o_fee = trade.open_operation().fee() * abs(trade.qty() / trade.open_operation().qty())
            c_fee = trade.close_operation().fee() * abs(trade.qty() / trade.close_operation().qty())
            # FIXME accrued interest calculations for short deals is not clear - to be corrected
            income = c_amount + c_interest if trade.qty() >= Decimal('0') else o_amount
            income_rub = c_amount_rub + c_interest_rub if trade.qty() >= Decimal('0') else o_amount_rub
            spending = o_amount + o_interest if trade.qty() >= Decimal('0') else c_amount
            spending += o_fee + c_fee
            spending_rub = o_amount_rub + o_interest_rub if trade.qty() >= Decimal('0') else c_amount_rub
            spending_rub += round(o_fee * o_rate, 2) + round(c_fee * c_rate, 2)
            line = {
                'report_template': "bond_trade",
                'symbol': trade.asset().symbol(currency.id()),
                'isin': trade.asset().isin(),
                'qty': trade.qty(),
                'principal': self.BOND_PRINCIPAL,
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': Decimal('100') * trade.open_operation().price() / self.BOND_PRINCIPAL,
                'o_int': o_interest,
                'o_int_rub': o_interest_rub,
                'o_amount': o_amount,
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * o_rate, 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': c_rate,
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': Decimal('100') * trade.close_operation().price() / self.BOND_PRINCIPAL,
                'c_int': c_interest,
                'c_int_rub': c_interest_rub,
                'c_amount': c_amount,
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * c_rate, 2),
                'income': income,  # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub
            }
            bonds_report.append(line)
        # Second - take all bond interest payments not linked with buy/sell transactions
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        interests = Dividend.get_list(self.account.id(), subtype=Dividend.BondInterest, skip_accrued=True)
        interests = [x for x in interests if self.year_begin <= x.timestamp() <= self.year_end]  # Only in given range
        for interest in interests:
            amount = interest.amount()
            rate = currency.quote(interest.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            amount_rub = round(amount * rate, 2)
            line = {
                'report_template': "bond_interest",
                'type': "Купон",
                'empty': '',  # to keep cell borders drawn
                'o_date': interest.timestamp(),
                'symbol': interest.asset().symbol(currency.id()),
                'isin': interest.asset().isin(),
                'number': interest.number(),
                'interest': amount,
                'rate': rate,
                'interest_rub': amount_rub,
                'income_rub': amount_rub,
                'spending_rub': Decimal('0.0'),
                'profit': amount,
                'profit_rub': amount_rub,
                'country_iso': country.iso_code(),
            }
            bonds_report.append(line)
        self.insert_totals(bonds_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return bonds_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_derivatives(self):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        derivatives_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Derivative]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = currency.quote(trade.open_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            c_rate = currency.quote(trade.close_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                os_rate = currency.quote(trade.open_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
                cs_rate = currency.quote(trade.close_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            o_amount = round(trade.open_operation().price() * abs(trade.qty()), 2)
            o_amount_rub = round(o_amount * os_rate, 2)
            c_amount = round(trade.close_operation().price() * abs(trade.qty()), 2)
            c_amount_rub = round(c_amount * cs_rate, 2)
            o_fee = trade.open_operation().fee() * abs(trade.qty() / trade.open_operation().qty())
            c_fee = trade.close_operation().fee() * abs(trade.qty() / trade.close_operation().qty())
            income = c_amount if trade.qty() >= Decimal('0') else o_amount
            income_rub = c_amount_rub if trade.qty() >= Decimal('0') else o_amount_rub
            spending = o_amount if trade.qty() >= Decimal('0') else c_amount
            spending += o_fee + c_fee
            spending_rub = o_amount_rub if trade.qty() >= Decimal('0') else c_amount_rub
            spending_rub += round(o_fee * o_rate, 2) + round(c_fee * c_rate, 2)
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(currency.id()),
                'qty': trade.qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_operation().price(),
                'o_amount': o_amount,
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * o_rate, 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': c_rate,
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': trade.close_operation().price(),
                'c_amount': c_amount,
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * c_rate, 2),
                'income': income,   # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub
            }
            derivatives_report.append(line)
        self.insert_totals(derivatives_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return derivatives_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_crypto(self):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        crypto_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Crypto]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = currency.quote(trade.open_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            c_rate = currency.quote(trade.close_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                os_rate = currency.quote(trade.open_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
                cs_rate = currency.quote(trade.close_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            o_amount = round(trade.open_operation().price() * abs(trade.qty()), 2)
            o_amount_rub = round(o_amount * os_rate, 2)
            c_amount = round(trade.close_operation().price() * abs(trade.qty()), 2)
            c_amount_rub = round(c_amount * cs_rate, 2)
            o_fee = trade.open_operation().fee() * abs(trade.qty() / trade.open_operation().qty())
            c_fee = trade.close_operation().fee() * abs(trade.qty() / trade.close_operation().qty())
            income = c_amount if trade.qty() >= Decimal('0') else o_amount
            income_rub = c_amount_rub if trade.qty() >= Decimal('0') else o_amount_rub
            spending = o_amount if trade.qty() >= Decimal('0') else c_amount
            spending += o_fee + c_fee
            spending_rub = o_amount_rub if trade.qty() >= Decimal('0') else c_amount_rub
            spending_rub += round(o_fee * o_rate, 2) + round(c_fee * c_rate, 2)
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(currency.id()),
                'qty': trade.qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_operation().price(),
                'o_amount': o_amount,
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * o_rate, 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': c_rate,
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': trade.close_operation().price(),
                'c_amount': c_amount,
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * c_rate, 2),
                'income': income,    # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub
            }
            crypto_report.append(line)
        self.insert_totals(crypto_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return crypto_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_broker_fees(self):
        currency = JalAsset(self.account.currency())
        fees_report = []
        fee_operations = JalCategory(PredefinedCategory.Fees).get_operations(self.year_begin, self.year_end)
        for operation in fee_operations:
            rate = currency.quote(operation.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            fees = [x for x in operation.lines() if x['category_id'] == PredefinedCategory.Fees]
            for fee in fees:
                amount = -Decimal(fee['amount'])
                line = {
                    'report_template': "fee",
                    'payment_date': operation.timestamp(),
                    'rate': rate,
                    'amount': amount,
                    'amount_rub': round(amount * rate, 2),
                    'note': fee['note']
                }
                fees_report.append(line)
        self.insert_totals(fees_report, ["amount", "amount_rub"])
        return fees_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_broker_interest(self):
        currency = JalAsset(self.account.currency())
        interests_report = []
        interest_operations = JalCategory(PredefinedCategory.Interest).get_operations(self.year_begin, self.year_end)
        for operation in interest_operations:
            rate = currency.quote(operation.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            interests = [x for x in operation.lines() if x['category_id'] == PredefinedCategory.Interest]
            for interest in interests:
                amount = Decimal(interest['amount'])
                line = {
                    'report_template': "interest",
                    'payment_date': operation.timestamp(),
                    'rate': rate,
                    'amount': amount,
                    'amount_rub': round(amount * rate, 2),
                    'tax_rub': round(Decimal('0.13') * amount * rate, 2),
                    'note': interest['note']
                }
                interests_report.append(line)
        # Process cash payments out of corporate actions
        payments = CorporateAction.get_payments(self.account)
        payments = [x for x in payments if self.year_begin <= x['timestamp'] <= self.year_end]
        for payment in payments:
            rate = currency.quote(payment['timestamp'], JalSettings().getValue('BaseCurrency'))[1]
            line = {
                'report_template': "interest",
                'payment_date': payment['timestamp'],
                'rate': rate,
                'amount': payment['amount'],
                'amount_rub': round(payment['amount'] * rate, 2),
                'tax_rub': round(Decimal('0.13') * payment['amount'] * rate, 2),
                'note': payment['note']
            }
            interests_report.append(line)
        self.insert_totals(interests_report, ["amount", "amount_rub", "tax_rub"])
        return interests_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_corporate_actions(self):
        currency = JalAsset(self.account.currency())
        corporate_actions_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.CorporateAction]
        trades = [x for x in trades if x.close_operation().settlement() <= self.year_end]   # TODO Why not self.year_begin<=?
        trades = sorted(trades, key=lambda x: (x.asset().symbol(currency.id()), x.close_operation().timestamp()))
        group = 1
        share = Decimal('1.0')   # This will track share of processed asset, so it starts from 100.0%
        previous_symbol = ""
        for trade in trades:
            lines = []
            sale = trade.close_operation()
            t_rate = currency.quote(sale.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                s_rate = currency.quote(sale.settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                s_rate = t_rate
            if previous_symbol != sale.asset().symbol(currency.id()):
                # Clean processed qty records if symbol have changed
                self._processed_trade_qty = {}
                if sale.settlement() >= self.year_begin:  # Don't put sub-header of operation is out of scope
                    corporate_actions_report.append({
                        'report_template': "symbol_header",
                        'report_group': 0,
                        'description': f"Сделки по бумаге: {sale.asset().symbol(currency.id())} - {sale.asset().name()}"
                    })
                    previous_symbol = sale.asset().symbol(currency.id())
            amount = round(sale.price() * trade.qty(), 2)
            amount_rub = round(amount * s_rate, 2)
            fee_rub = round(sale.fee() * t_rate, 2)
            if sale.timestamp() < self.year_begin:    # Don't show deal that is before report year (level = -1)
                self.proceed_corporate_action(lines, trade, trade.qty(), share, -1, group)
            else:
                lines.append({
                    'report_template': "trade",
                    'report_group': group,
                    'operation': "Продажа",
                    't_date': sale.timestamp(),
                    't_rate': t_rate,
                    's_date': sale.settlement(),
                    's_rate': s_rate,
                    'symbol': sale.asset().symbol(currency.id()),
                    'isin': sale.asset().isin(),
                    'trade_number': sale.number(),
                    'price': sale.price(),
                    'qty': trade.qty(),
                    'amount': amount,
                    'amount_rub': amount_rub,
                    'fee': sale.fee(),
                    'fee_rub': fee_rub,
                    'basis_ratio': Decimal('100') * share,
                    'income_rub': amount_rub,
                    'spending_rub': fee_rub
                })
                if sale.asset().type() == PredefinedAsset.Bond:
                    self.output_accrued_interest(lines, sale, 1, 0)
                self.proceed_corporate_action(lines, trade, trade.qty(), share, 1, group)
            self.insert_totals(lines, ["income_rub", "spending_rub"])
            corporate_actions_report += lines
            group += 1
        return corporate_actions_report

    # actions - mutable list of tax records to output into json-report
    # trade - JalClosedTrade object, for which we need to proceed with opening corporate action
    # qty - amount of asset to process
    # share - value share that is being processed currently
    # level - how deep we are in a chain of events (is used for correct indents)
    # group - use for odd/even lines grouping in the report
    def proceed_corporate_action(self, actions, trade, qty, share, level, group):
        asset_id, qty, share = self.output_corp_action(actions, trade.open_operation(), trade.asset(), qty, share, level, group)
        next_level = -1 if level == -1 else (level + 1)
        self.next_corporate_action(actions, trade, qty, share, next_level, group)

    def next_corporate_action(self, actions, trade, qty, share, level, group):
        # get list of deals that were closed as result of current corporate action
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.CorporateAction]
        trades = [x for x in trades if x.close_operation().id() == trade.open_operation().id()]
        for item in trades:
            if item.open_operation().type() == LedgerTransaction.Trade:
                qty = self.output_purchase(actions, item.open_operation(), qty, share, level, group)
            elif item.open_operation().type() == LedgerTransaction.CorporateAction:
                self.proceed_corporate_action(actions, trade, qty, share, level, group)
            else:
                assert False, "Unexpected opening transaction"

    def output_purchase(self, actions, purchase, proceed_qty, share, level, group):
        currency = JalAsset(self.account.currency())
        if proceed_qty <= Decimal('0'):
            return proceed_qty
        t_rate = currency.quote(purchase.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
        if self.use_settlement:
            s_rate = currency.quote(purchase.settlement(), JalSettings().getValue('BaseCurrency'))[1]
        else:
            s_rate = t_rate
        if purchase.id() in self._processed_trade_qty:   # we have some qty processed already
            qty = purchase.qty() - self._processed_trade_qty[purchase.id()]
        else:
            qty = purchase.qty()
        if qty <= Decimal('0'):
            return proceed_qty   # This trade was fully matched during previous operations processing
        deal_qty = qty
        qty = proceed_qty if proceed_qty < deal_qty else deal_qty
        amount = round(purchase.price() * qty, 2)
        amount_rub = round(amount * s_rate, 2)
        fee = purchase.fee() * qty / deal_qty
        fee_rub = round(fee * t_rate, 2)
        # Update processed quantity for current _purchase_ operation
        self._processed_trade_qty[purchase.id()] = self._processed_trade_qty.get(purchase.id(), 0) + qty
        if level >= 0:  # Don't output if level==-1, i.e. corp action is out of report scope
            actions.append({
                'report_template': "trade",
                'report_group': group,
                'operation': ' ' * level * 3 + "Покупка",
                'trade_number': purchase.number(),
                'symbol': purchase.asset().symbol(currency.id()),
                'isin': purchase.asset().isin(),
                't_date': purchase.timestamp(),
                't_rate': t_rate,
                's_date': purchase.settlement(),
                's_rate': s_rate,
                'basis_ratio': Decimal('100') * share,
                'qty': qty,
                'price': purchase.price(),
                'amount': amount,
                'amount_rub': amount_rub,
                'fee': fee,
                'fee_rub': fee_rub,
                'income_rub': Decimal('0'),
                'spending_rub': round(share *(amount_rub + fee_rub), 2)
            })
        if purchase.asset().type() == PredefinedAsset.Bond:
            share = qty / deal_qty if qty < deal_qty else 1
            self.output_accrued_interest(actions, purchase, share, level)
        return proceed_qty - qty

    # asset - is a resulting asset that is being processed at current stage
    def output_corp_action(self, actions, action, asset, proceed_qty, share, level, group):
        currency = JalAsset(self.account.currency())
        if proceed_qty <= 0:
            return proceed_qty, share
        r_qty, r_share = action.get_result_for_asset(asset)
        share = share * r_share
        qty_before = action.qty() * proceed_qty / r_qty
        if action.subtype() == CorporateAction.SpinOff:
            action_results = action.get_results()
            spinoff = [x for x in action_results if x['asset_id'] != action.asset().id()]
            assert len(spinoff) == 1, "Multiple assets for spin-off"
            spinoff = spinoff[0]
            new_asset = JalAsset(spinoff['asset_id'])
            old_asset_name = f"{action.asset().symbol(currency.id())} ({action.asset().isin()})"
            new_asset_name = f"{new_asset.symbol(currency.id())} ({new_asset.isin()})"
            display_share = Decimal('100') * Decimal(spinoff['value_share'])
        else:
            old_asset_name = f"{action.asset().symbol(currency.id())} ({action.asset().isin()})"
            new_asset_name = f"{asset.symbol(currency.id())} ({asset.isin()})"
            display_share = Decimal('100') * r_share
        note = self.CorpActionText[action.subtype()].format(old=old_asset_name, new=new_asset_name,
                                                            before=remove_exponent(qty_before),
                                                            after=remove_exponent(proceed_qty), share=display_share)
        if level >= 0:  # Don't output if level==-1, i.e. corp action is out of report scope
            actions.append({
                'report_template': "action",
                'report_group': group,
                'operation': ' ' * level * 3 + "Корп. действие",
                'action_date': action.timestamp(),
                'action_number': action.number(),
                'symbol': action.asset().symbol(currency.id()),
                'isin': action.asset().isin(),
                'qty': action.qty(),
                'description': note
            })
        return action.asset().id(), qty_before, share

    def output_accrued_interest(self, actions, operation, share, level):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        accrued_interest = operation.get_accrued_interest()
        if not accrued_interest:
            return
        rate = currency.quote(operation.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
        interest = accrued_interest.amount() if share == 1 else share * accrued_interest.amount()
        interest_rub = abs(round(interest * rate, 2)) 
        if interest < 0:  # Accrued interest paid for purchase
            interest = -interest
            op_name = ' ' * level * 3 + "НКД уплачен"
            spending_rub = interest_rub
            income_rub = Decimal('0')
        else:                         # Accrued interest received for sale
            op_name = ' ' * level * 3 + "НКД получен"
            income_rub = interest_rub
            spending_rub = Decimal('0')
        actions.append({
            'report_template': 'bond_interest',
            'empty': '',
            'operation': op_name,
            'symbol': operation.asset().symbol(currency.id()),
            'isin': operation.asset().isin(),
            'number': operation.number(),
            'o_date': operation.timestamp(),
            'rate': rate,
            'interest': interest,
            'interest_rub': interest_rub,
            'income_rub': income_rub,
            'spending_rub': spending_rub,
            'country_iso': country.iso_code()
        })
