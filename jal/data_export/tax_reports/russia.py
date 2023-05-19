from decimal import Decimal
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.helpers import remove_exponent
from jal.db.operations import LedgerTransaction, Dividend, CorporateAction
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
            "Корп.события": (self.prepare_corporate_actions, "tax_rus_corporate_actions.json"),
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
            if dividend.subtype() == Dividend.StockDividend:
                note = "Дивиденд выплачен в натуральной форме (ценными бумагами)"
            if dividend.subtype() == Dividend.StockVesting:
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
        dividends_withdrawn = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
        dividends_withdrawn = [x for x in dividends_withdrawn if self.year_begin <= x.timestamp() <= self.year_end]
        dividends_withdrawn = [x for x in dividends_withdrawn if x.amount() < Decimal('0')]
        for trade in trades_list:
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
                spending = round(trade.open_amount(no_settlement=ns), 2) + trade.fee()
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
                note = f"Удержан дивиденд: {short_dividend_rub:.2f} RUB ({short_dividend:.2f} {self.account_currency.symbol()})" if short_dividend_rub > Decimal('0') else ''
                income = round(trade.open_amount(no_settlement=ns), 2)
                income_rub = round(trade.open_amount(self._currency_id, no_settlement=ns), 2)
                spending = round(trade.close_amount(no_settlement=ns), 2) + trade.fee() + short_dividend
                spending_rub = round(trade.close_amount(self._currency_id, no_settlement=ns), 2) + round(trade.fee(self._currency_id), 2) + short_dividend_rub
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(self.account_currency.id()),
                'isin': trade.asset().isin(),  # May be not used in template (for derivatives as example)
                'qty': trade.qty(),
                'country_iso': self.account.country().iso_code(),  # this field is required for DLSG
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1],
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_operation().price(),
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
        trades = self.shares_trades_list()
        return self.prepare_trades_report(trades)

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_bonds(self):
        country = self.account.country()
        bonds_report = []
        ns = not self.use_settlement
        trades = self.bonds_trades_list()
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
                'symbol': trade.asset().symbol(self.account_currency.id()),
                'isin': trade.asset().isin(),
                'qty': trade.qty(),
                'principal': trade.asset().principal(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1],
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': Decimal('100') * trade.open_operation().price() / trade.asset().principal(),
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
        interests = Dividend.get_list(self.account.id(), subtype=Dividend.BondInterest, skip_accrued=True)
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
        trades = self.derivatives_trades_list()
        return self.prepare_trades_report(trades)

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_crypto(self):
        country = self.account.country()
        crypto_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Crypto]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
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
                'symbol': trade.asset().symbol(self.account_currency.id()),
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

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_corporate_actions(self):
        corporate_actions_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.CorporateAction]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        trades = sorted(trades, key=lambda x: (x.asset().symbol(self.account_currency.id()), x.close_operation().timestamp()))
        group = 1
        share = Decimal('1.0')   # This will track share of processed asset, so it starts from 100.0%
        previous_symbol = ""
        for trade in trades:
            lines = []
            sale = trade.close_operation()
            t_rate = self.account_currency.quote(sale.timestamp(), self._currency_id)[1]
            if self.use_settlement:
                s_rate = self.account_currency.quote(sale.settlement(), self._currency_id)[1]
            else:
                s_rate = t_rate
            if previous_symbol != sale.asset().symbol(self.account_currency.id()):
                # Clean processed qty records if symbol have changed
                self._processed_trade_qty = {}
                if sale.settlement() >= self.year_begin:  # Don't put sub-header of operation is out of scope
                    corporate_actions_report.append({
                        'report_template': "symbol_header",
                        'report_group': 0,
                        'description': f"Сделки по бумаге: {sale.asset().symbol(self.account_currency.id())} - {sale.asset().name()}"
                    })
                    previous_symbol = sale.asset().symbol(self.account_currency.id())
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
                    'symbol': sale.asset().symbol(self.account_currency.id()),
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
                self.proceed_corporate_action(actions, item, qty, share, level, group)
            else:
                assert False, "Unexpected opening transaction"

    def output_purchase(self, actions, purchase, proceed_qty, share, level, group):
        if proceed_qty <= Decimal('0'):
            return proceed_qty
        t_rate = self.account_currency.quote(purchase.timestamp(), self._currency_id)[1]
        if self.use_settlement:
            s_rate = self.account_currency.quote(purchase.settlement(), self._currency_id)[1]
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
                'symbol': purchase.asset().symbol(self.account_currency.id()),
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
        country = self.account.country()
        accrued_interest = operation.accrued_interest()
        if accrued_interest == Decimal('0'):
            return
        rate = self.account_currency.quote(operation.timestamp(), self._currency_id)[1]
        interest = accrued_interest if share == 1 else share * accrued_interest
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
            'symbol': operation.asset().symbol(self.account_currency.id()),
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
