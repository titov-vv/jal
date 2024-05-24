from decimal import Decimal
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.operations import LedgerTransaction, AssetPayment, CorporateAction
from jal.db.asset import JalAsset
from jal.db.category import JalCategory
from jal.data_export.taxes import TaxReport


# -----------------------------------------------------------------------------------------------------------------------
class TaxesRussia(TaxReport):
    currency_name = 'RUB'
    country_name = "russia"

    CorpActionText = {
        CorporateAction.SymbolChange: "Смена символа {before} {old} -> {after} {new}",
        CorporateAction.Split: "Сплит {old} {before} в {after} {new}",
        CorporateAction.SpinOff: "Выделение компании {new} из {old}; доля выделяемого актива {share:.2f}%",
        CorporateAction.Merger: "Реорганизация компании, конвертация {share:.2f}% стоимости {before} {old} в {after} {new}",
        CorporateAction.Delisting: "Делистинг"
    }

    def __init__(self):
        super().__init__()
        self.broker_name = ''
        self.broker_iso_cc = "000"
        self._processed_trade_qty = {}  # It will handle {trade_id: qty} records to keep track of already processed qty
        self.reports = {
            "Дивиденды": (self.prepare_dividends, "tax_rus_dividends.json"),
            "Акции": (self.prepare_stocks_and_etf, "tax_rus_trades.json"),
            "Облигации": (self.prepare_bonds, "tax_rus_bonds.json"),
            "ПФИ": (self.prepare_derivatives, "tax_rus_derivatives.json"),
            "Криптовалюты": (self.prepare_crypto, "tax_rus_crypto.json"),
            "Комиссии": (self.prepare_broker_fees, "tax_rus_fees.json"),
            "Проценты": (self.prepare_broker_interest, "tax_rus_interests.json")
        }

    def prepare_dividends(self):
        dividends_report = []
        dividends = self.dividends_list()
        dividends = [x for x in dividends if x.amount(self.account_currency.id()) > 0]  # Skip negative dividends
        for dividend in dividends:
            country = dividend.asset().country()
            note = ''
            if dividend.subtype() == AssetPayment.StockDividend:
                note = "Дивиденд выплачен в натуральной форме (ценными бумагами)"
            if dividend.subtype() == AssetPayment.StockVesting:
                note = "Доход получен в натуральной форме (ценными бумагами)"
            tax_rub = dividend.tax(self._currency_id)
            tax2pay = Decimal('0.13') * dividend.amount(self._currency_id)
            if self.has_tax_treaty_with(country.code()):
                if tax2pay > tax_rub:
                    tax2pay = tax2pay - tax_rub
                else:
                    tax2pay = Decimal('0.0')
            line = {
                'report_template': "dividend",
                'payment_date': dividend.timestamp(),
                'symbol': dividend.asset().symbol(self.account_currency.id()),
                'full_name': dividend.asset().name(),
                'isin': dividend.asset().isin(),
                'amount': dividend.amount(self.account_currency.id()),
                'tax': dividend.tax(),
                'rate': self.account_currency.quote(dividend.timestamp(), self._currency_id)[1],
                'country': country.name(language='ru'),
                'country_iso': country.iso_code(),  # it is required for DLSG export
                'tax_treaty': "Да" if self.has_tax_treaty_with(country.code()) else "Нет",
                'amount_rub': round(dividend.amount(self._currency_id), 2),
                'tax_rub': round(dividend.tax(self._currency_id), 2),
                'tax2pay': round(tax2pay, 2),
                'note': note
            }
            dividends_report.append(line)
        self.insert_totals(dividends_report, ["amount", "amount_rub", "tax", "tax_rub", "tax2pay"])
        return dividends_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_trades_report(self, trades_list):
        deals_report = []
        ns = not self.use_settlement
        # Prepare list of dividends withdrawn from account (due to short trades)
        dividends_withdrawn = AssetPayment.get_list(self.account.id(), subtype=AssetPayment.Dividend)
        dividends_withdrawn = [x for x in dividends_withdrawn if self.year_begin <= x.timestamp() <= self.year_end]
        dividends_withdrawn = [x for x in dividends_withdrawn if x.amount() < Decimal('0')]
        for trade in trades_list:
            corporate_actions = trade.modified_by()
            report_template = "corporate_action" if any([x.type()==LedgerTransaction.CorporateAction for x in corporate_actions]) else "trade"
            if ns:
                os_rate = self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1]
                cs_rate = self.account_currency.quote(trade.close_operation().timestamp(), self._currency_id)[1]
            else:
                os_rate = self.account_currency.quote(trade.open_operation().settlement(), self._currency_id)[1]
                cs_rate = self.account_currency.quote(trade.close_operation().settlement(), self._currency_id)[1]
            if trade.qty() >= Decimal('0'):  # Long trade
                note = ''
                income = round(trade.close_amount(no_settlement=ns), 2)
                income_rub = round(trade.close_amount(self._currency_id, no_settlement=ns), 2)
                spending = round(trade.open_amount(no_settlement=ns), 2) + round(trade.fee(), 2)
                spending_rub = round(trade.open_amount(self._currency_id, no_settlement=ns), 2) + round(trade.fee(self._currency_id), 2)
            else:                            # Short trade
                # Check were there any dividends during short position holding
                short_dividend = Decimal('0')
                short_dividend_rub = Decimal('0')
                div_list = [x for x in dividends_withdrawn if x.asset().id() == trade.asset().id()]
                div_list = [x for x in div_list if trade.open_operation().settlement() <= x.ex_date() <= trade.close_operation().settlement()]
                for dividend in div_list:
                    short_dividend -= dividend.amount()
                    short_dividend_rub -= dividend.amount(self._currency_id)  # amount is negative
                dividends_withdrawn = [x for x in dividends_withdrawn if not x in div_list]
                note = f"Удержан дивиденд: {short_dividend_rub:.2f} RUB ({short_dividend:.2f} {self.account_currency.symbol()})\n" if short_dividend_rub > Decimal('0') else ''
                income = round(trade.open_amount(no_settlement=ns), 2)
                income_rub = round(trade.open_amount(self._currency_id, no_settlement=ns), 2)
                spending = round(trade.close_amount(no_settlement=ns), 2) + round(trade.fee(), 2) + short_dividend
                spending_rub = round(trade.close_amount(self._currency_id, no_settlement=ns), 2) + round(trade.fee(self._currency_id), 2) + short_dividend_rub
            for modifier in corporate_actions:
                note = note + modifier.description() + "\n"
            line = {
                'report_template': report_template,
                'c_symbol': trade.asset().symbol(self.account_currency.id()),
                'c_isin': trade.asset().isin(),  # May be not used in template (for derivatives as example)
                'c_qty': trade.qty(),
                'o_symbol': trade.open_operation().asset().symbol(),
                'o_isin': trade.open_operation().asset().isin(),
                'o_qty': trade.open_qty(),
                'country_iso': self.account.country().iso_code(),  # this field is required for DLSG
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1],
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_price(),
                'cost_basis': Decimal('100') * trade.cost_basis(),
                'o_amount':  round(trade.open_amount(no_settlement=ns, full=True), 2),
                'o_amount_rub': round(trade.open_amount(self._currency_id, no_settlement=ns, full=True), 2),
                'o_fee': trade.open_fee(full=True),
                'o_fee_rub': round(trade.open_fee(self._currency_id, full=True), 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': self.account_currency.quote(trade.close_operation().timestamp(), self._currency_id)[1],
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': trade.close_operation().price(),
                'c_amount': round(trade.close_amount(no_settlement=ns), 2),
                'c_amount_rub': round(trade.close_amount(self._currency_id, no_settlement=ns), 2),
                'c_fee': trade.close_fee(),
                'c_fee_rub': round(trade.close_fee(self._currency_id), 2),
                'income': income,    # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub,
                'note': note
            }
            deals_report.append(line)
        self.insert_totals(deals_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return deals_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_stocks_and_etf(self):
        trades = self.trades_list([PredefinedAsset.Stock, PredefinedAsset.ETF])
        return self.prepare_trades_report(trades)

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_bonds(self):
        country = self.account.country()
        bonds_report = []
        ns = not self.use_settlement
        trades = self.trades_list([PredefinedAsset.Bond])
        for trade in trades:
            if ns:
                os_rate = self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1]
                cs_rate = self.account_currency.quote(trade.close_operation().timestamp(), self._currency_id)[1]
            else:
                os_rate = self.account_currency.quote(trade.open_operation().settlement(), self._currency_id)[1]
                cs_rate = self.account_currency.quote(trade.close_operation().settlement(), self._currency_id)[1]
            if trade.qty() >= Decimal('0'):  # Long trade
                income = round(trade.close_amount(no_settlement=ns), 2) + trade.close_operation().accrued_interest()
                income_rub = round(trade.close_amount(self._currency_id, no_settlement=ns), 2) + round(trade.close_operation().accrued_interest(self._currency_id), 2)
                spending = round(trade.open_amount(no_settlement=ns), 2) + trade.fee() - trade.open_operation().accrued_interest()
                spending_rub = round(trade.open_amount(self._currency_id, no_settlement=ns), 2) + round(trade.fee(self._currency_id), 2) - round(trade.open_operation().accrued_interest(self._currency_id), 2)
            else:                            # Short trade
                income = round(trade.open_amount(no_settlement=ns), 2) + trade.open_operation().accrued_interest()
                income_rub = round(trade.open_amount(self._currency_id, no_settlement=ns), 2) + round(trade.open_operation().accrued_interest(self._currency_id), 2)
                spending = round(trade.close_amount(no_settlement=ns), 2) + trade.fee() - trade.close_operation().accrued_interest()
                spending_rub = round(trade.close_amount(self._currency_id, no_settlement=ns), 2) + round(trade.fee(self._currency_id), 2) - round(trade.close_operation().accrued_interest(self._currency_id), 2)
            line = {
                'report_template': "bond_trade",
                'c_symbol': trade.asset().symbol(self.account_currency.id()),
                'c_isin': trade.asset().isin(),  # May be not used in template (for derivatives as example)
                'c_qty': trade.qty(),
                'o_symbol': trade.open_operation().asset().symbol(),
                'o_isin': trade.open_operation().asset().isin(),
                'o_qty': trade.open_qty(),
                'principal': trade.asset().principal(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1],
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': Decimal('100') * trade.open_price() / trade.asset().principal(),
                'o_int': -trade.open_operation().accrued_interest(),
                'o_int_rub': -round(trade.open_operation().accrued_interest(self._currency_id), 2),
                'o_amount':  round(trade.open_amount(no_settlement=ns), 2),
                'o_amount_rub': round(trade.open_amount(self._currency_id, no_settlement=ns), 2),
                'o_fee': trade.open_fee(),
                'o_fee_rub': round(trade.open_fee(self._currency_id), 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': self.account_currency.quote(trade.close_operation().timestamp(), self._currency_id)[1],
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': Decimal('100') * trade.close_operation().price() / trade.asset().principal(),
                'c_int': trade.close_operation().accrued_interest(),
                'c_int_rub': round(trade.close_operation().accrued_interest(self._currency_id), 2),
                'c_amount': round(trade.close_amount(no_settlement=ns), 2),
                'c_amount_rub': round(trade.close_amount(self._currency_id, no_settlement=ns), 2),
                'c_fee': trade.close_fee(),
                'c_fee_rub': round(trade.close_fee(self._currency_id), 2),
                'income': income,  # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub
            }
            bonds_report.append(line)
        # Second - take all bond interest payments not linked with buy/sell transactions
        currency = JalAsset(self.account.currency())
        country = self.account.country()
        interests = AssetPayment.get_list(self.account.id(), subtype=AssetPayment.BondInterest, skip_accrued=True)
        interests = [x for x in interests if self.year_begin <= x.timestamp() <= self.year_end]  # Only in given range
        for interest in interests:
            amount = interest.amount()
            rate = currency.quote(interest.timestamp(), self._currency_id)[1]
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
        trades = self.trades_list([PredefinedAsset.Derivative])
        return self.prepare_trades_report(trades)

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_crypto(self):
        country = self.account.country()
        crypto_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Crypto]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1]
            c_rate = self.account_currency.quote(trade.close_operation().timestamp(), self._currency_id)[1]
            if self.use_settlement:
                os_rate = self.account_currency.quote(trade.open_operation().settlement(), self._currency_id)[1]
                cs_rate = self.account_currency.quote(trade.close_operation().settlement(), self._currency_id)[1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            o_amount = round(trade.open_price() * abs(trade.qty()), 2)
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
                'symbol': trade.asset().symbol(self.account_currency.id()),
                'qty': trade.qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_price(),
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
        fees_report = []
        fee_operations = JalCategory(PredefinedCategory.Fees).get_operations(self.year_begin, self.year_end)
        fee_operations = [x for x in fee_operations if x.account_id() == self.account.id()]
        for operation in fee_operations:
            rate = self.account_currency.quote(operation.timestamp(), self._currency_id)[1]
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
        interests_report = []
        interest_operations = JalCategory(PredefinedCategory.Interest).get_operations(self.year_begin, self.year_end)
        interest_operations = [x for x in interest_operations if x.account_id() == self.account.id()]
        for operation in interest_operations:
            rate = self.account_currency.quote(operation.timestamp(), self._currency_id)[1]
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
            rate = self.account_currency.quote(payment['timestamp'], self._currency_id)[1]
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
