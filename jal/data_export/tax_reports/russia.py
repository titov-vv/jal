from decimal import Decimal
from jal.constants import PredefinedAsset, PredefinedCategory, SymbolId
from jal.db.operations import LedgerTransaction, AssetPayment, AssetIncome, CorporateAction
from jal.db.asset import JalAsset
from jal.data_export.taxes import TaxReport


# -----------------------------------------------------------------------------------------------------------------------
class TaxesRussia(TaxReport):
    currency_name = 'RUB'
    country_name = "russia"
    report_timezone = 'Europe/Moscow'
    currency_suffix = '_rub'
    summary_section = ("Сводка", "tax_rus_summary.json")
    uncovered_section = ("Не отражено", "tax_rus_uncovered.json")
    texts = {
        'rent_return': "Возврат ренты токен-аккаунта: возврат уплаченного, а не доход",
        'skipped_count': "Пропущено по правилу: {}",
        'uncovered': "Ни один раздел отчёта не отражает эту операцию",
        'skipped_total': "Пропущено по правилу юрисдикции",
        'uncovered_total': "Не отражено ни в одном разделе",
        'pending_total': "Строк «ожидает пересчёта»",
        'income': "Доходы",
        'spending': "Расходы",
        'profit': "Финансовый результат",
        'amount': "Сумма",
        'value': "Стоимость на дату получения",
        'rates_missing': "Внимание: курса ЦБ РФ {pair} нет в базе после {rate}; операции по {latest} пересчитаны по "
                         "курсу на {rate} - загрузите курсы и сформируйте отчёт заново",
        'fifo': "Сделки сопоставлены по FIFO внутри этого счёта; сделки других счетов здесь не учтены",
        'rate_settlement': "Пересчёт в рубли по курсу ЦБ РФ на дату расчётов (поставки); комиссии - на дату сделки; "
                           "где дата расчётов не указана источником - на дату сделки",
        'rate_trade': "Пересчёт в рубли по курсу ЦБ РФ на дату сделки",
        'native_cost': "Расход - фактически уплаченная сумма в валюте оплаты, по курсу на дату её оплаты; перевод "
                       "между своими счетами её не меняет",
        'cost_currency': "Расход оплачен в {}: пересчёт в рубли из этой валюты",
        'bond_price': "Цена - за одну облигацию в валюте сделки",
        'crypto_exchange': "Каждый обмен криптовалюты на криптовалюту - реализация по рыночной стоимости",
        'crypto_income_lot': "Криптовалюта, полученная как доход, учтена по стоимости на дату получения (как в разделе "
                             "«Криптодоход»)",
        'crypto_gas': "Комиссия сети за обмен уплачена в криптовалюте и в этом разделе не учтена",
        'crypto_pending': "«Ожидает пересчёта»: сумма зависит от обмена без реализации, рыночную стоимость которого "
                          "этот отчёт ещё не рассчитывает",
        'pending_closed': "Ожидает пересчёта: обмен учтён без финансового результата, хотя это реализация по рыночной "
                          "стоимости",
        'pending_carried': "Ожидает пересчёта: стоимость приобретения унаследована через обмен без реализации",
        'income_lot': "Получено как доход в криптовалюте: стоимость по котировке на дату получения",
        'income_valued': "Доход в натуральной форме: стоимость по котировке криптовалюты на дату получения, пересчитанная "
                         "по курсу ЦБ РФ на эту дату",
        'fees_choice': "Расходы, не связанные со сделками; какие группы заявлять и в какой базе (ценные бумаги или "
                       "ПФИ) - решает налогоплательщик",
        'fee_depositary': "Депозитарная комиссия",
        'fee_financing': "Плата за финансирование позиции",
        'fee_asset': "Прочая комиссия или налог по активу",
        'fee_broker': "Комиссия брокера"
    }
    operation_labels = {
        (LedgerTransaction.Trade, None): "Сделка",
        (LedgerTransaction.Swap, None): "Обмен криптовалюты",
        (LedgerTransaction.Conversion, None): "Конвертация токена",
        (LedgerTransaction.IncomeSpending, None): "Денежная операция",
        (LedgerTransaction.CorporateAction, CorporateAction.Merger): "Реорганизация",
        (LedgerTransaction.CorporateAction, CorporateAction.SpinOff): "Выделение компании",
        (LedgerTransaction.CorporateAction, CorporateAction.SymbolChange): "Смена символа",
        (LedgerTransaction.CorporateAction, CorporateAction.Split): "Сплит",
        (LedgerTransaction.AssetPayment, AssetPayment.Dividend): "Дивиденд",
        (LedgerTransaction.AssetPayment, AssetPayment.BondInterest): "Купон или НКД",
        (LedgerTransaction.AssetPayment, AssetPayment.AssetFee): "Комиссия или налог по активу",
        (LedgerTransaction.AssetPayment, AssetPayment.DepositaryFee): "Депозитарная комиссия",
        (LedgerTransaction.AssetPayment, AssetPayment.PositionFinancing): "Плата за финансирование позиции",
        (LedgerTransaction.AssetIncome, AssetIncome.StockDividend): "Дивиденд ценными бумагами",
        (LedgerTransaction.AssetIncome, AssetIncome.StockVesting): "Вестинг ценных бумаг",
        (LedgerTransaction.AssetIncome, AssetIncome.StakingReward): "Вознаграждение за стейкинг",
        (LedgerTransaction.AssetIncome, AssetIncome.Reward): "Вознаграждение",
        (LedgerTransaction.AssetIncome, AssetIncome.LendingInterest): "Проценты за предоставление криптовалюты",
        (LedgerTransaction.AssetIncome, AssetIncome.TokenRentReturn): "Возврат ренты токен-аккаунта"
    }

    CorpActionText = {
        CorporateAction.SymbolChange: "Смена символа {before} {old} -> {after} {new}",
        CorporateAction.Split: "Сплит {old} {before} в {after} {new}",
        CorporateAction.SpinOff: "Выделение компании {new} из {old}; доля выделяемого актива {share:.2f}%",
        CorporateAction.Merger: "Реорганизация компании, конвертация {share:.2f}% стоимости {before} {old} в {after} {new}",
        CorporateAction.Delisting: "Делистинг",
        CorporateAction.WriteOff: "Списание"
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
            "Криптодоход": (self.prepare_crypto_income, "tax_rus_crypto_income.json"),
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
            if dividend.type() == LedgerTransaction.AssetIncome:
                if dividend.subtype() == AssetIncome.StockDividend:
                    note = "Дивиденд выплачен в натуральной форме (ценными бумагами)"
                if dividend.subtype() == AssetIncome.StockVesting:
                    note = "Доход получен в натуральной форме (ценными бумагами)"
            rate = self.rate(self.account_currency.id(), dividend.timestamp())
            amount_rub = dividend.amount(self.account_currency.id()) * rate
            tax_rub = dividend.tax() * rate
            tax2pay = Decimal('0.13') * amount_rub
            if self.has_tax_treaty_with(country.code()):
                if tax2pay > tax_rub:
                    tax2pay = tax2pay - tax_rub
                else:
                    tax2pay = Decimal('0.0')
            line = {
                'report_template': "dividend",
                'payment_date': self._moment(dividend.timestamp(), dividend.timestamp_is_day()),
                'symbol': dividend.symbol().symbol(),
                'full_name': dividend.asset().name(),
                'isin': dividend.symbol().identifier(SymbolId.ISIN),
                'amount': dividend.amount(self.account_currency.id()),
                'tax': dividend.tax(),
                'rate': rate,
                'country': country.name(language='ru'),
                'country_iso': country.iso_code(),  # it is required for DLSG export
                'tax_treaty': "Да" if self.has_tax_treaty_with(country.code()) else "Нет",
                'amount_rub': round(amount_rub, 2),
                'tax_rub': round(tax_rub, 2),
                'tax2pay': round(tax2pay, 2),
                'note': note
            }
            dividends_report.append(line)
            self.mark_printed(dividend)
        self.insert_totals(dividends_report, ["amount", "amount_rub", "tax", "tax_rub", "tax2pay"])
        return dividends_report

    # The headers every deals section states: the matching rule, the rate rule and the cost
    def _deal_headers(self):
        self.add_header(self.texts['fifo'])
        self.add_header(self.texts['rate_settlement'] if self.use_settlement else self.texts['rate_trade'])
        self.add_header(self.texts['native_cost'])

    # The rates of a deal's two legs, official ones only: each leg's amount at its settlement (or trade date when
    # asked for or when there is none), each fee at its trade date. The opening leg is in the currency it was paid in.
    def _deal_rates(self, trade) -> dict:
        ns = not self.use_settlement
        open_op, close_op = trade.open_operation(), trade.close_operation()
        open_currency = open_op.account().currency()
        return {
            'open_currency': open_currency,
            'o_rate': self.rate(open_currency, open_op.timestamp()),
            'os_rate': self.rate(open_currency, self.rate_moment(open_op, ns)),
            'c_rate': self.rate(self.account_currency.id(), close_op.timestamp()),
            'cs_rate': self.rate(self.account_currency.id(), self.rate_moment(close_op, ns))
        }

    # Notes of the operations that changed this deal's lot, one per line
    def _modifier_notes(self, trade) -> list:
        return [x.description().strip() for x in self.deal_modifiers(trade) if x.description().strip()]

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_trades_report(self, trades_list):
        self._deal_headers()
        deals_report = []
        # Prepare list of dividends withdrawn from account (due to short trades)
        dividends_withdrawn = AssetPayment.get_list(self.account.id(), subtype=AssetPayment.Dividend)
        dividends_withdrawn = [x for x in dividends_withdrawn if self.year_begin <= self._moment(x.timestamp(), x.timestamp_is_day()) < self.year_end]
        dividends_withdrawn = [x for x in dividends_withdrawn if x.amount() < Decimal('0')]
        for trade in trades_list:
            corporate_actions = trade.modified_by()
            report_template = "corporate_action" if any([x.type()==LedgerTransaction.CorporateAction for x in corporate_actions]) else "trade"
            rates = self._deal_rates(trade)
            o_amount_rub = round(trade.native_open_amount() * rates['os_rate'], 2)
            c_amount_rub = round(trade.close_amount() * rates['cs_rate'], 2)
            fee_rub = round(trade.native_open_fee() * rates['o_rate'] + trade.close_fee() * rates['c_rate'], 2)
            notes = []
            if trade.qty() >= Decimal('0'):  # Long trade
                income = round(trade.close_amount(), 2)
                income_rub = c_amount_rub
                spending = round(trade.open_amount(), 2) + round(trade.fee(), 2)
                spending_rub = o_amount_rub + fee_rub
            else:                            # Short trade
                # Check were there any dividends during short position holding
                short_dividend = Decimal('0')
                short_dividend_rub = Decimal('0')
                div_list = [x for x in dividends_withdrawn if x.asset().id() == trade.asset().id()]
                div_list = [x for x in div_list if self.rate_moment(trade.open_operation()) <= x.ex_date() <= self.rate_moment(trade.close_operation())]
                for dividend in div_list:
                    short_dividend -= dividend.amount()
                    short_dividend_rub -= dividend.amount() * self.rate(self.account_currency.id(), dividend.timestamp())  # amount is negative
                dividends_withdrawn = [x for x in dividends_withdrawn if not x in div_list]
                for dividend in div_list:
                    self.mark_printed(dividend)
                if short_dividend_rub > Decimal('0'):
                    notes.append(f"Удержан дивиденд: {short_dividend_rub:.2f} RUB ({short_dividend:.2f} {self.account_currency.symbol()})")
                income = round(trade.open_amount(), 2)
                income_rub = o_amount_rub
                spending = round(trade.close_amount(), 2) + round(trade.fee(), 2) + short_dividend
                spending_rub = c_amount_rub + fee_rub + short_dividend_rub
            if rates['open_currency'] != self.account_currency.id():
                notes.append(self.texts['cost_currency'].format(JalAsset(rates['open_currency']).symbol()))
            notes += self._modifier_notes(trade)
            o_amount_full = round(trade.open_amount(full=True), 2)
            line = {
                'report_template': report_template,
                'c_symbol': trade.close_operation().symbol().symbol(),
                'c_isin': trade.close_operation().symbol().identifier(SymbolId.ISIN),  # May be not used in template (for derivatives as example)
                'c_qty': trade.qty(),
                'o_symbol': trade.open_operation().symbol().symbol(),
                'o_isin': trade.open_operation().symbol().identifier(SymbolId.ISIN),
                'o_qty': trade.open_qty(),
                'country_iso': self.account.country().iso_code(),  # this field is required for DLSG
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': self._moment(trade.acquired(), trade.acquired_is_day()),
                'o_rate': rates['o_rate'],
                'os_date': self.settlement_date(trade.open_operation()),
                'os_rate': rates['os_rate'],
                'o_price': trade.open_price(),
                'cost_basis': Decimal('100') * trade.native_cost_basis(),
                'o_amount': o_amount_full,
                'o_amount_rub': round(trade.open_amount(full=True) * rates['os_rate'], 2),
                'o_fee': trade.open_fee(full=True),
                'o_fee_rub': round(trade.open_fee(full=True) * rates['o_rate'], 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': self._moment(trade.close_operation().timestamp(), trade.close_operation().timestamp_is_day()),
                'c_rate': rates['c_rate'],
                'cs_date': self.settlement_date(trade.close_operation()),
                'cs_rate': rates['cs_rate'],
                'c_price': trade.close_operation().price(),
                'c_amount': round(trade.close_amount(), 2),
                'c_amount_rub': c_amount_rub,
                'c_fee': trade.close_fee(),
                'c_fee_rub': round(trade.close_fee() * rates['c_rate'], 2),
                'income': income,    # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub,
                'note': "\n".join(notes)
            }
            deals_report.append(line)
            self.mark_printed(trade.close_operation())
        self.insert_totals(deals_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return deals_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_stocks_and_etf(self):
        trades = self.trades_list([PredefinedAsset.Stock, PredefinedAsset.ETF])
        return self.prepare_trades_report(trades)

    # -----------------------------------------------------------------------------------------------------------------------
    # Accrued interest of a bond trade in RUB, at the official rate of the trade date
    def _accrued_rub(self, operation) -> Decimal:
        return round(operation.accrued_interest() * self.rate(operation.account().currency(), operation.timestamp()), 2)

    def prepare_bonds(self):
        self._deal_headers()
        self.add_header(self.texts['bond_price'])
        country = self.account.country()
        bonds_report = []
        trades = self.trades_list([PredefinedAsset.Bond])
        for trade in trades:
            rates = self._deal_rates(trade)
            open_op, close_op = trade.open_operation(), trade.close_operation()
            o_amount_rub = round(trade.native_open_amount() * rates['os_rate'], 2)
            c_amount_rub = round(trade.close_amount() * rates['cs_rate'], 2)
            fee_rub = round(trade.native_open_fee() * rates['o_rate'] + trade.close_fee() * rates['c_rate'], 2)
            if trade.qty() >= Decimal('0'):  # Long trade
                income = round(trade.close_amount(), 2) + close_op.accrued_interest()
                income_rub = c_amount_rub + self._accrued_rub(close_op)
                spending = round(trade.open_amount(), 2) + trade.fee() - open_op.accrued_interest()
                spending_rub = o_amount_rub + fee_rub - self._accrued_rub(open_op)
            else:                            # Short trade
                income = round(trade.open_amount(), 2) + open_op.accrued_interest()
                income_rub = o_amount_rub + self._accrued_rub(open_op)
                spending = round(trade.close_amount(), 2) + trade.fee() - close_op.accrued_interest()
                spending_rub = c_amount_rub + fee_rub - self._accrued_rub(close_op)
            line = {
                'report_template': "bond_trade",
                'c_symbol': close_op.symbol().symbol(),
                'c_isin': close_op.symbol().identifier(SymbolId.ISIN),
                'c_qty': trade.qty(),
                'o_symbol': open_op.symbol().symbol(),
                'o_isin': open_op.symbol().identifier(SymbolId.ISIN),
                'o_qty': trade.open_qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': open_op.number(),
                'o_date': self._moment(trade.acquired(), trade.acquired_is_day()),
                'o_rate': rates['o_rate'],
                'os_date': self.settlement_date(open_op),
                'os_rate': rates['os_rate'],
                'o_price': trade.open_price(),
                'o_int': -open_op.accrued_interest(),
                'o_int_rub': -self._accrued_rub(open_op),
                'o_amount':  round(trade.open_amount(), 2),
                'o_amount_rub': o_amount_rub,
                'o_fee': trade.open_fee(),
                'o_fee_rub': round(trade.native_open_fee() * rates['o_rate'], 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': close_op.number(),
                'c_date': self._moment(close_op.timestamp(), close_op.timestamp_is_day()),
                'c_rate': rates['c_rate'],
                'cs_date': self.settlement_date(close_op),
                'cs_rate': rates['cs_rate'],
                'c_price': close_op.price(),
                'c_int': close_op.accrued_interest(),
                'c_int_rub': self._accrued_rub(close_op),
                'c_amount': round(trade.close_amount(), 2),
                'c_amount_rub': c_amount_rub,
                'c_fee': trade.close_fee(),
                'c_fee_rub': round(trade.close_fee() * rates['c_rate'], 2),
                'income': income,  # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub
            }
            bonds_report.append(line)
            self.mark_printed(close_op)
            for operation in (open_op, close_op):
                if operation.type() == LedgerTransaction.Trade:
                    self.mark_printed(operation.accrued_interest_payment())
        # Second - take all bond interest payments not linked with buy/sell transactions
        interests = AssetPayment.get_list(self.account.id(), subtype=AssetPayment.BondInterest, skip_accrued=True)
        interests = [x for x in interests if self.year_begin <= self._moment(x.timestamp(), x.timestamp_is_day()) < self.year_end]  # Only in given range
        for interest in interests:
            amount = interest.amount()
            rate = self.rate(self.account_currency.id(), interest.timestamp())
            amount_rub = round(amount * rate, 2)
            line = {
                'report_template': "bond_interest",
                'type': "Купон",
                'empty': '',  # to keep cell borders drawn
                'o_date': self._moment(interest.timestamp(), interest.timestamp_is_day()),
                'symbol': interest.symbol().symbol(),
                'isin': interest.symbol().identifier(SymbolId.ISIN),
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
            self.mark_printed(interest)
        self.insert_totals(bonds_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return bonds_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_derivatives(self):
        trades = self.trades_list([PredefinedAsset.Derivative])
        return self.prepare_trades_report(trades)

    # -----------------------------------------------------------------------------------------------------------------------
    # The value in RUB of an income in crypto at its receipt, per unit of the asset received: the asset's quote in the
    # receiving account's currency at the official rate of that day. None, and recorded as missing, without a quote.
    def _income_unit_value(self, income):
        currency_id = income.account().currency()
        quoted, price = income.asset().quote(income.timestamp(), currency_id, report_missing=False)
        if not quoted:
            self.missing_quote(income.symbol().symbol(), income.timestamp())
            return None, None
        return price, price * self.rate(currency_id, income.timestamp())

    CRYPTO_INCOMES = (AssetIncome.StakingReward, AssetIncome.Reward, AssetIncome.LendingInterest)

    # Every crypto deal: sold for money, or disposed of by a swap or a wrapping - each of them a disposal in RU
    def prepare_crypto(self):
        self._deal_headers()
        self.add_header(self.texts['crypto_exchange'])
        self.add_header(self.texts['crypto_income_lot'])
        self.add_header(self.texts['crypto_gas'])
        self.add_header(self.texts['crypto_pending'])
        country = self.account.country()
        crypto_report = []
        otypes = (LedgerTransaction.Trade, LedgerTransaction.Swap, LedgerTransaction.Conversion)
        for trade in self.trades_list([PredefinedAsset.Crypto], close_otypes=otypes):
            open_op, close_op = trade.open_operation(), trade.close_operation()
            rates = self._deal_rates(trade)
            notes = []
            o_qty = abs(trade.open_qty())
            if open_op.type() == LedgerTransaction.AssetIncome and open_op.subtype() in self.CRYPTO_INCOMES:
                price, unit_rub = self._income_unit_value(open_op)   # re-priced, or the income would be taxed twice
                if price is None:
                    continue
                o_amount, o_amount_rub = o_qty * price, round(o_qty * unit_rub, 2)
                a_open = o_amount * trade.fx_adjustment()
                rates['os_rate'] = self.rate(open_op.account().currency(), open_op.timestamp())
                notes.append(self.texts['income_lot'])
            else:
                o_amount = trade.native_open_amount()
                o_amount_rub = round(o_amount * rates['os_rate'], 2)
                a_open = trade.open_amount()
            # o_amount is in the cost currency, a_open in the account currency - the one 'income' and 'profit' use
            o_fee, a_open_fee = trade.native_open_fee(), trade.open_fee()
            c_amount, c_fee = trade.close_amount(), trade.close_fee()
            c_price = trade.close_price()
            c_amount_rub = round(c_amount * rates['cs_rate'], 2)
            pending = False
            if close_op.type() in (LedgerTransaction.Swap, LedgerTransaction.Conversion) and close_op.price() is None:
                # JAL's own figure: no result, the lot moved on at its cost - its fee stays with the deal that sells it
                c_amount_rub, o_fee, a_open_fee = o_amount_rub, Decimal('0'), Decimal('0')
                c_amount = a_open                # the stored close price is the lot's unadjusted open price
                c_price = c_amount / abs(trade.qty())
                pending = True
                notes.insert(0, self.texts['pending_closed'])
            fee_rub = round(o_fee * rates['o_rate'] + c_fee * rates['c_rate'], 2)
            if self.carried_through(trade, (LedgerTransaction.Swap, LedgerTransaction.Conversion)):
                pending = True
                notes.insert(0, self.texts['pending_carried'])
            if rates['open_currency'] != self.account_currency.id():
                notes.append(self.texts['cost_currency'].format(JalAsset(rates['open_currency']).symbol()))
            notes += self._modifier_notes(trade)
            long = trade.qty() >= Decimal('0')
            income = c_amount if long else a_open
            income_rub = c_amount_rub if long else o_amount_rub
            spending = (a_open if long else c_amount) + a_open_fee + c_fee
            spending_rub = (o_amount_rub if long else c_amount_rub) + fee_rub
            line = {
                'report_template': "trade",
                'symbol': close_op.symbol().symbol(),
                'qty': trade.qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if long else "Продажа",
                'o_number': open_op.number(),
                'o_date': self._moment(trade.acquired(), trade.acquired_is_day()),
                'o_rate': rates['o_rate'],
                'os_date': self.settlement_date(open_op),
                'os_rate': rates['os_rate'],
                'o_price': o_amount / abs(trade.qty()),   # per unit as held now
                'o_amount': round(o_amount, 2),
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * rates['o_rate'], 2),
                'c_type': "Продажа" if long else "Покупка",
                'c_number': close_op.number(),
                'c_date': self._moment(close_op.timestamp(), close_op.timestamp_is_day()),
                'c_rate': rates['c_rate'],
                'cs_date': self.settlement_date(close_op),
                'cs_rate': rates['cs_rate'],
                'c_price': c_price,
                'c_amount': round(c_amount, 2),
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * rates['c_rate'], 2),
                'income': round(income, 2),    # this field is required for DLSG
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': round(income - spending, 2),
                'profit_rub': income_rub - spending_rub,
                'note': "\n".join(notes)
            }
            if pending:
                line['pending_replay'] = True
            crypto_report.append(line)
            self.mark_printed(close_op)
        self.insert_totals(crypto_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return crypto_report

    # Crypto received as income, valued at its receipt; a missing quote stops the report
    def prepare_crypto_income(self):
        self.add_header(self.texts['income_valued'])
        incomes_report = []
        incomes = []
        for subtype in self.CRYPTO_INCOMES:
            incomes += AssetIncome.get_list(self.account.id(), subtype=subtype)
        incomes = [x for x in incomes if self.in_year(self._moment(x.timestamp(), x.timestamp_is_day()))]
        for income in sorted(incomes, key=lambda x: x.timestamp()):
            price, unit_rub = self._income_unit_value(income)
            if price is None:
                continue
            incomes_report.append({
                'report_template': "income",
                'payment_date': self._moment(income.timestamp(), income.timestamp_is_day()),
                'operation': self.operation_label(income),
                'symbol': income.symbol().symbol(),
                'qty': income.amount(),
                'price': price,
                'value': round(income.amount() * price, 2),
                'rate': self.rate(self.account_currency.id(), income.timestamp()),
                'value_rub': round(income.amount() * unit_rub, 2),
                'note': ''
            })
            self.mark_printed(income)
        self.insert_totals(incomes_report, ["value", "value_rub"])
        return incomes_report

    # -----------------------------------------------------------------------------------------------------------------------
    # Costs of holding, grouped by kind, and the broker's fees: none of them is linked to a deal
    def prepare_broker_fees(self):
        self.add_header(self.texts['fees_choice'])
        fees_report = []
        kinds = ((AssetPayment.DepositaryFee, 'fee_depositary'), (AssetPayment.PositionFinancing, 'fee_financing'),
                 (AssetPayment.AssetFee, 'fee_asset'))
        for subtype, kind in kinds:
            payments = AssetPayment.get_list(self.account.id(), subtype=subtype)
            payments = [x for x in payments if self.in_year(self._moment(x.timestamp(), x.timestamp_is_day()))]
            for payment in sorted(payments, key=lambda x: x.timestamp()):
                rate = self.rate(self.account_currency.id(), payment.timestamp())
                amount = -payment.amount()
                fees_report.append({
                    'report_template': "fee",
                    'fee_type': self.texts[kind],
                    'payment_date': self._moment(payment.timestamp(), payment.timestamp_is_day()),
                    'description': f"{payment.symbol().symbol()}: {payment.note()}",
                    'rate': rate,
                    'amount': amount,
                    'amount_rub': round(amount * rate, 2),
                    'note': ''
                })
                self.mark_printed(payment)
        fee_operations = self.category_operations(PredefinedCategory.Fees)
        fee_operations = [x for x in fee_operations if x.account_id() == self.account.id()]
        for operation in fee_operations:
            rate = self.rate(self.account_currency.id(), operation.timestamp())
            fees = [x for x in operation.lines() if x['category_id'] == PredefinedCategory.Fees]
            for fee in fees:
                amount = -Decimal(fee['amount'])
                fees_report.append({
                    'report_template': "fee",
                    'fee_type': self.texts['fee_broker'],
                    'payment_date': self._moment(operation.timestamp(), operation.timestamp_is_day()),
                    'description': fee['note'],
                    'rate': rate,
                    'amount': amount,
                    'amount_rub': round(amount * rate, 2),
                    'note': ''
                })
            if fees:
                self.mark_printed(operation)
        self.insert_totals(fees_report, ["amount", "amount_rub"])
        return fees_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_broker_interest(self):
        interests_report = []
        interest_operations = self.category_operations(PredefinedCategory.Interest)
        interest_operations = [x for x in interest_operations if x.account_id() == self.account.id()]
        for operation in interest_operations:
            rate = self.rate(self.account_currency.id(), operation.timestamp())
            interests = [x for x in operation.lines() if x['category_id'] == PredefinedCategory.Interest]
            for interest in interests:
                amount = Decimal(interest['amount'])
                line = {
                    'report_template': "interest",
                    'payment_date': self._moment(operation.timestamp(), operation.timestamp_is_day()),
                    'rate': rate,
                    'amount': amount,
                    'amount_rub': round(amount * rate, 2),
                    'tax_rub': round(Decimal('0.13') * amount * rate, 2),
                    'description': interest['note'],
                    'note': ''
                }
                interests_report.append(line)
            if interests:
                self.mark_printed(operation)
        # Process cash payments out of corporate actions
        payments = CorporateAction.get_payments(self.account)
        payments = [x for x in payments if self.year_begin <= self._moment(x['timestamp'], x['day_only']) < self.year_end]
        for payment in payments:
            rate = self.rate(self.account_currency.id(), payment['timestamp'])
            line = {
                'report_template': "interest",
                'payment_date': self._moment(payment['timestamp'], payment['day_only']),
                'rate': rate,
                'amount': payment['amount'],
                'amount_rub': round(payment['amount'] * rate, 2),
                'tax_rub': round(Decimal('0.13') * payment['amount'] * rate, 2),
                'description': payment['note'],
                'note': ''
            }
            interests_report.append(line)
            self.mark_printed_id(LedgerTransaction.CorporateAction, payment['oid'])
        self.insert_totals(interests_report, ["amount", "amount_rub", "tax_rub"])
        return interests_report
