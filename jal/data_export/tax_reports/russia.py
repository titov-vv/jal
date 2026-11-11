from decimal import Decimal
from PySide6.QtCore import QT_TRANSLATE_NOOP
from jal.constants import PredefinedAsset, PredefinedCategory, SymbolId
from jal.db.operations import LedgerTransaction, AssetPayment, AssetIncome, CorporateAction, Swap, Conversion
from jal.db.basis_policy import Basis, Clock, Treatment, JalPolicy
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.data_export.taxes import TaxReport, GAIN, INCOME
from jal.data_export.tax_parameters import TaxParameters
from jal.data_export.tax_options import TaxOption


# -----------------------------------------------------------------------------------------------------------------------
# RU: every swap and every wrapping is a disposal at market and the received asset opens at that value; crypto received
# as income opens at its quote, the value the income is taxed at. 'missing_quote(symbol, timestamp)' collects a quote
# an income lacks.
class RuPolicy(JalPolicy):
    INCOMES = (AssetIncome.StakingReward, AssetIncome.Reward, AssetIncome.LendingInterest)

    def __init__(self, missing_quote):
        self._missing_quote = missing_quote

    def treatment(self, operation) -> Treatment:
        if isinstance(operation, (Swap, Conversion)):
            return Treatment(Basis.DISPOSAL, Clock.RESTART)
        return super().treatment(operation)

    def income_cost(self, income) -> Decimal:
        if income.subtype() not in self.INCOMES:
            return super().income_cost(income)
        quoted, price = income.asset().quote(income.timestamp(), income.account().currency(), report_missing=False)
        if not quoted:
            self._missing_quote(income.symbol().symbol(), income.timestamp())
            return super().income_cost(income)
        return price


# -----------------------------------------------------------------------------------------------------------------------
class TaxesRussia(TaxReport):
    jurisdiction = 'ru'
    currency_name = 'RUB'
    report_timezone = 'Europe/Moscow'
    options = [
        TaxOption('no_settlement', QT_TRANSLATE_NOOP("TaxWidget", "Do not use settlement date for currency rates"))
    ]
    asset_source_override = True
    currency_suffix = '_rub'
    summary_section = ("Сводка", "tax_rus_summary.json")
    uncovered_section = ("Не отражено", "tax_rus_uncovered.json")
    bases = [("Ценные бумаги", GAIN, ["Акции", "Облигации"]),
             ("ПФИ", GAIN, ["ПФИ"]),
             ("Дивиденды", INCOME, ["Дивиденды"]),
             ("Проценты", INCOME, ["Проценты"]),
             ("Криптовалюты", GAIN, ["Криптовалюты"]),
             ("Криптодоход", INCOME, ["Криптодоход"])]
    outside = ["Комиссии"]
    texts = {
        'rent_return': "Возврат ренты токен-аккаунта: возврат уплаченного, а не доход",
        'skipped_count': "Пропущено по правилу: {}",
        'uncovered': "Ни один раздел отчёта не отражает эту операцию",
        'skipped_total': "Пропущено по правилу юрисдикции",
        'uncovered_total': "Не отражено ни в одном разделе",
        'estimate_dividend': "Налог к уплате - базовая оценка (курсив на цветном фоне): {rate} % от дохода, за вычетом "
                             "налога, удержанного за рубежом, только при наличии СОИДН; без прогрессивной шкалы и вычетов",
        'estimate_interest': "Налог к уплате - базовая оценка (курсив на цветном фоне): {rate} % от дохода; без "
                             "прогрессивной шкалы и вычетов",
        'estimates': "Базовая оценка налога - не сумма к уплате (без прогрессивной шкалы, вычетов и сальдирования)",
        'estimate_total': "Итого базовая оценка",
        'estimate_gain': "{base}: {rate} % от финансового результата базы, убыток - ноль; базы не сальдируются",
        'derivatives_apart': "ПФИ - отдельная база, в оценке налога не сальдируется с ценными бумагами: ст. 214.1 НК "
                             "РФ допускает это для ПФИ на ценные бумаги, но виды ПФИ в отчёте не разделены",
        'excluded': "Решение пользователя - не налоговое событие в РФ: {}",
        'decisions': "Решения пользователя, применённые в этом отчёте (переопределение налогового режима)",
        'override_excluded': "Не налоговое событие",
        'override_treaty': "Соглашение об избежании двойного налогообложения применяется",
        'override_no_treaty': "Соглашение не применяется",
        'override_asset_source': "Источник дохода - эмитент и страна актива",
        'override_tax_event': "Налоговое событие",
        'override_price': "Налоговое событие по цене {} за полученную акцию",
        'exchange': "Мена акций: реализация по рыночной стоимости",
        'exchange_price': "Мена акций по указанной пользователем цене за полученную акцию: реализация по этой стоимости",
        'exchange_decided': "Решение пользователя: реализация по рыночной стоимости, оценённой как наибольшая из "
                            "последней котировки прежних акций с учётом их доли стоимости и первой котировки новых",
        'income': "Доходы",
        'spending': "Расходы",
        'profit': "Финансовый результат",
        'gross': "Доход",
        'amount': "Сумма",
        'value': "Стоимость на дату получения",
        'base_total': "Итого по базе",
        'outside': "Вне налоговых баз - для сведения, без итога",
        'rate_sum': "Сумма баз по ставке 13/15 % (ст. 224 п. 1.1 НК РФ): ценные бумаги, ПФИ, дивиденды, криптовалюта и "
                    "проценты российских плательщиков; убыток - со своим знаком; не налог",
        'parameters_unreviewed': "Внимание: налоговые параметры (соглашения, базовые ставки) проверены по {reviewed} год; "
                                 "для {year} года взяты последние известные значения",
        'parameters_missing': "Внимание: налоговых параметров для {year} года нет; соглашения об избежании двойного "
                              "налогообложения не учтены, базовая оценка налога не рассчитана",
        'rates_missing': "Внимание: курса ЦБ РФ {pair} нет в базе после {rate}; операции по {latest} пересчитаны по "
                         "курсу на {rate} - загрузите курсы и сформируйте отчёт заново",
        'fifo': "Сделки сопоставлены по FIFO внутри этого счёта; сделки других счетов здесь не учтены",
        'fifo_netted': "Сделки сопоставлены по FIFO внутри каждого счёта; результаты счетов сложены",
        'account_block': "Счёт {number} ({currency})",
        'account_currency': "валюта счёта",
        'rate_settlement': "Пересчёт в рубли по курсу ЦБ РФ на дату расчётов (поставки); комиссии - на дату сделки; "
                           "где дата расчётов не указана источником - на дату сделки",
        'rate_trade': "Пересчёт в рубли по курсу ЦБ РФ на дату сделки",
        'native_cost': "Расход - фактически уплаченная сумма в валюте оплаты, по курсу на дату её оплаты; перевод "
                       "между своими счетами её не меняет",
        'historical_cost': "Расход - историческая стоимость приобретения: смена налогового резидентства её не меняет",
        'cost_currency': "Расход оплачен в {}: пересчёт в рубли из этой валюты",
        'bond_price': "Цена - за одну облигацию в валюте сделки",
        'crypto_exchange': "Каждый обмен криптовалюты на криптовалюту, включая обёртывание токена, его размещение в "
                           "протокол кредитования и вывод из него, - реализация по рыночной стоимости; полученный "
                           "актив учтён по этой стоимости на дату обмена",
        'crypto_income_lot': "Криптовалюта, полученная как доход, учтена по стоимости на дату получения (как в разделе "
                             "«Криптодоход»)",
        'crypto_gas': "Комиссия сети за обмен уплачена в криптовалюте и в этом разделе не учтена",
        'income_lot': "Получено как доход в криптовалюте: стоимость по котировке на дату получения",
        'income_valued': "Доход в натуральной форме: стоимость по котировке криптовалюты на дату получения, пересчитанная "
                         "по курсу ЦБ РФ на эту дату",
        'fees_choice': "Расходы, не связанные со сделками; какие группы заявлять и в какой базе (ценные бумаги или "
                       "ПФИ) - решает налогоплательщик",
        'fee_depositary': "Депозитарная комиссия",
        'fee_financing': "Плата за финансирование позиции",
        'fee_asset': "Прочая комиссия или налог по активу",
        'fee_broker': "Комиссия брокера",
        'short_open': "Короткая позиция на 31 декабря: доход от продажи отражён в году продажи без расхода на "
                      "приобретение; покупка в следующем году к вычету не принимается",
        'short_carried': "Закрытие короткой позиции, открытой в {year} году: продажа отражена в отчёте за {year} год "
                         "без расхода, эта покупка к вычету не принимается",
        'short_unhandled': "Внимание: короткая позиция {symbol} от {date} переходит через конец года - для этого вида "
                           "актива правило не реализовано, проверьте её вручную",
        'home_codes': "Коды не указаны: счёт открыт у российского брокера или банка, доход отражает налоговый агент",
        'traded': "Все ценные бумаги считаются обращающимися на организованном рынке (ст. 214.1 п. 3 НК РФ); "
                  "необращающиеся JAL не выделяет",
        'derivatives_mixed': "ПФИ на ценные бумаги и фондовые индексы не отделены от прочих ПФИ: коды 1532 / 206 "
                             "указаны для всех",
        'interest_base': "Проценты российского плательщика - база по вкладам в банках РФ; иностранного - основная "
                         "налоговая база",
        'crypto_codes': "Коды 6035 / 435 (криптовалюта) и 4800 (доход в криптовалюте) не подтверждены официальным "
                        "источником - проверьте их перед подачей декларации"
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
            "Акции": (self.prepare_stocks_and_etf, "tax_rus_trades.json"),
            "Облигации": (self.prepare_bonds, "tax_rus_bonds.json"),
            "ПФИ": (self.prepare_derivatives, "tax_rus_derivatives.json"),
            "Дивиденды": (self.prepare_dividends, "tax_rus_dividends.json"),
            "Проценты": (self.prepare_broker_interest, "tax_rus_interests.json"),
            "Криптовалюты": (self.prepare_crypto, "tax_rus_crypto.json"),
            "Криптодоход": (self.prepare_crypto_income, "tax_rus_crypto_income.json"),
            "Комиссии": (self.prepare_broker_fees, "tax_rus_fees.json")
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
            tax2pay = self.base_estimate(TaxParameters.DIVIDEND, amount_rub)
            if tax2pay is not None and self.has_tax_treaty_with(country.code(), dividend):
                if tax2pay > tax_rub:
                    tax2pay = tax2pay - tax_rub
                else:
                    tax2pay = Decimal('0.0')
            line = {
                'report_template': "dividend",
                **self.coded(TaxParameters.DIVIDEND),
                'payment_date': self._moment(dividend.timestamp(), dividend.timestamp_is_day()),
                'symbol': dividend.symbol().symbol(),
                'full_name': dividend.asset().name(),
                'isin': dividend.symbol().identifier(SymbolId.ISIN),
                'amount': dividend.amount(self.account_currency.id()),
                'tax': dividend.tax(),
                'rate': rate,
                'country': country.name(language='ru'),
                'country_iso': country.iso_code(),  # it is required for DLSG export
                'tax_treaty': "Да" if self.has_tax_treaty_with(country.code(), dividend) else "Нет",
                'amount_rub': round(amount_rub, 2),
                'tax_rub': round(tax_rub, 2),
                'tax2pay': None if tax2pay is None else round(tax2pay, 2),
                'note': note
            }
            dividends_report.append(line)
            self.mark_printed(dividend)
        self.add_estimate_header(dividends_report, self.texts['estimate_dividend'], TaxParameters.DIVIDEND)
        self.insert_totals(dividends_report, ["amount", "amount_rub", "tax", "tax_rub", "tax2pay"])
        return dividends_report

    # The headers every deals section states: the matching rule, the rate rule and the cost
    def _deal_headers(self):
        self.add_header(self.fifo_header())
        self.add_header(self.texts['rate_trade'] if self.option['no_settlement'] else self.texts['rate_settlement'])
        self.add_header(self.texts['native_cost'])
        self.add_header(self.texts['historical_cost'])

    # The rates of a deal's two legs, official ones only: each leg's amount at its settlement (or trade date when
    # asked for or when there is none), each fee at its trade date. The opening leg is in the currency it was paid in.
    def _deal_rates(self, trade) -> dict:
        ns = self.option['no_settlement']
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
        dividends_withdrawn = [x for x in dividends_withdrawn if self.in_period(self._moment(x.timestamp(), x.timestamp_is_day()))]
        dividends_withdrawn = [x for x in dividends_withdrawn if x.amount() < Decimal('0') and not self.excluded(x)]
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
                **self.coded(self.TRADE_CODES[trade.asset().type()]),
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
    TRADE_CODES = {PredefinedAsset.Stock: TaxParameters.STOCK, PredefinedAsset.ETF: TaxParameters.ETF,
                   PredefinedAsset.Derivative: TaxParameters.DERIVATIVE}

    def prepare_stocks_and_etf(self):
        trades = self.trades_list([PredefinedAsset.Stock, PredefinedAsset.ETF])
        exchanges = self.exchanges_list([PredefinedAsset.Stock, PredefinedAsset.ETF])
        deals = self.prepare_trades_report(trades + exchanges)
        deals = [x for x in deals if x['report_template'] != "totals"]
        for line, trade in zip(deals[len(trades):], exchanges):   # realized at an exchange the user decided on
            line['c_type'], line['c_price'] = "Мена", trade.close_price()
            notes = [self.exchange_note(trade.close_operation())] + ([line['note']] if line['note'] else [])
            line['note'] = "\n".join(notes)
        deals += [self._short_open_row(x) for x in self.stock_year_end_shorts()]
        self.insert_totals(deals, ["income_rub", "spending_rub", "profit_rub", "profit"])
        self.add_header(self.texts['traded'])
        return deals

    # A stock short sold in the year and open on 31 December: the proceeds at the sale's settlement rate, its fee at the
    # rate of its trade date, no acquisition cost
    def _short_open_row(self, piece) -> dict:
        sale = piece['open']
        currency = sale.account().currency()
        o_rate = self.rate(currency, sale.timestamp())
        os_rate = self.rate(currency, self.rate_moment(sale, self.option['no_settlement']))
        income, fee = round(piece['amount'], 2), piece['fee']
        income_rub, spending_rub = round(piece['amount'] * os_rate, 2), round(fee * o_rate, 2)
        return {
            'report_template': "short_open",
            **self.coded(TaxParameters.STOCK),
            'c_symbol': sale.symbol().symbol(),
            'c_isin': sale.symbol().identifier(SymbolId.ISIN),
            'c_qty': piece['qty'],
            'country_iso': self.account.country().iso_code(),
            'o_type': "Продажа",
            'o_number': sale.number(),
            'o_date': self._moment(sale.timestamp(), sale.timestamp_is_day()),
            'o_rate': o_rate,
            'os_date': self.settlement_date(sale),
            'os_rate': os_rate,
            'o_price': sale.price(),
            'cost_basis': '',
            'o_amount': income,
            'o_amount_rub': income_rub,
            'o_fee': fee,
            'o_fee_rub': spending_rub,
            'income': income,
            'income_rub': income_rub,
            'spending_rub': spending_rub,
            'profit': income - fee,
            'profit_rub': income_rub - spending_rub,
            'note': self.texts['short_open']
        }

    # -----------------------------------------------------------------------------------------------------------------------
    # Accrued interest of a bond trade in RUB, at the official rate of the trade date
    def _accrued_rub(self, operation) -> Decimal:
        return round(operation.accrued_interest() * self.rate(operation.account().currency(), operation.timestamp()), 2)

    def prepare_bonds(self):
        self._deal_headers()
        self.add_header(self.texts['bond_price'])
        self.add_header(self.texts['traded'])
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
                **self.coded(TaxParameters.BOND),
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
        interests = [x for x in interests if self.in_period(self._moment(x.timestamp(), x.timestamp_is_day()))]  # Only in given range
        interests = [x for x in interests if not self.excluded(x)]
        for interest in interests:
            amount = interest.amount()
            rate = self.rate(self.account_currency.id(), interest.timestamp())
            amount_rub = round(amount * rate, 2)
            line = {
                'report_template': "bond_interest",
                **self.coded(TaxParameters.COUPON),
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
        trades = self.prepare_trades_report(self.trades_list([PredefinedAsset.Derivative]))
        self.add_header(self.texts['derivatives_mixed'])
        self.add_header(self.texts['derivatives_apart'])
        return trades

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

    CRYPTO_INCOMES = RuPolicy.INCOMES

    def basis_policy(self):
        return RuPolicy(self.missing_quote)

    RESIDENCE_DAYS = 183   # НК РФ ст. 207 п. 2

    # The whole year with 183 days or more in Russia by the residence table, nothing with fewer
    def resident_periods(self, year: int):
        days = sum(until - since for since, until in self.resident_spans(year)) // 86400
        return [self.year_window(year)] if days >= self.RESIDENCE_DAYS else []

    # Every crypto deal: sold for money, or disposed of by a swap or a wrapping - each of them a disposal in RU
    def prepare_crypto(self):
        self._deal_headers()
        self.add_header(self.texts['crypto_exchange'])
        self.add_header(self.texts['crypto_income_lot'])
        self.add_header(self.texts['crypto_gas'])
        self.add_header(self.texts['crypto_codes'])
        country = self.account.country()
        crypto_report = []
        otypes = (LedgerTransaction.Trade, LedgerTransaction.Swap, LedgerTransaction.Conversion)
        for trade in self.trades_list([PredefinedAsset.Crypto], close_otypes=otypes):
            open_op, close_op = trade.open_operation(), trade.close_operation()
            rates = self._deal_rates(trade)
            notes = []
            if open_op.type() == LedgerTransaction.AssetIncome and open_op.subtype() in self.CRYPTO_INCOMES:
                notes.append(self.texts['income_lot'])   # the policy opened it at its quote
            # o_amount is in the cost currency, a_open in the account currency - the one 'income' and 'profit' use
            o_amount = trade.native_open_amount()
            o_amount_rub = round(o_amount * rates['os_rate'], 2)
            a_open = trade.open_amount()
            o_fee, a_open_fee = trade.native_open_fee(), trade.open_fee()
            c_amount, c_fee = trade.close_amount(), trade.close_fee()
            c_price = trade.close_price()
            c_amount_rub = round(c_amount * rates['cs_rate'], 2)
            fee_rub = round(o_fee * rates['o_rate'] + c_fee * rates['c_rate'], 2)
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
                **self.coded(TaxParameters.CRYPTO),
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
            crypto_report.append(line)
            self.mark_printed(close_op)
        self.insert_totals(crypto_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return crypto_report

    # Crypto received as income, valued at its receipt; a missing quote stops the report
    def prepare_crypto_income(self):
        self.add_header(self.texts['income_valued'])
        self.add_header(self.texts['crypto_codes'])
        incomes_report = []
        incomes = []
        for subtype in self.CRYPTO_INCOMES:
            incomes += AssetIncome.get_list(self.account.id(), subtype=subtype)
        incomes = [x for x in incomes if self.in_period(self._moment(x.timestamp(), x.timestamp_is_day()))]
        for income in sorted(incomes, key=lambda x: x.timestamp()):
            if self.excluded(income):
                continue
            price, unit_rub = self._income_unit_value(income)
            if price is None:
                continue
            incomes_report.append({
                'report_template': "income",
                **self.coded(TaxParameters.CRYPTO_INCOME),
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
            payments = [x for x in payments if self.in_period(self._moment(x.timestamp(), x.timestamp_is_day()))]
            for payment in sorted(payments, key=lambda x: x.timestamp()):
                if self.excluded(payment):
                    continue
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
        fee_operations = [x for x in fee_operations if x.account_id() == self.account.id() and not self.excluded(x)]
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

    def _interest_tax(self, amount_rub: Decimal):
        tax = self.base_estimate(TaxParameters.INTEREST, amount_rub)
        return None if tax is None else round(tax, 2)

    RATE_BASES = (("Ценные бумаги", 'profit'), ("ПФИ", 'profit'), ("Дивиденды", 'gross'), ("Криптовалюты", 'profit'))

    # The sum of the bases taxed at the rate of ст. 224 п. 1.1, each with its sign; of interest only Russian payers'
    def base_sum_rows(self, sections: dict, totals: dict) -> list:
        amount = sum(totals[base].get(figure, Decimal('0')) for base, figure in self.RATE_BASES)
        amount += sum(x['amount_rub'] for x in sections["Проценты"]
                      if x['report_template'] == "interest" and x['country_code'] == 'ru')
        return [{'report_template': "base_sum", 'label': self.texts['rate_sum'], 'amount': amount}]

    # The payer of an interest row: the account's bank or broker, in the account's country - or the operation's asset in
    # its own country if the user decided so; an asset without a country stops the report
    def _payer(self, operation=None) -> dict:
        if operation is not None and self.asset_source(operation):
            asset, country = operation.asset(), operation.asset().country()
            if not country.id():
                self.missing_country(f"{asset.symbol()} ({asset.name()})")
            return {'payer': asset.name(), 'country': country.name(language='ru'), 'country_code': country.code()}
        country = self.account.country()
        return {'payer': JalPeer(self.account.organization()).name(), 'country': country.name(language='ru'),
                'country_code': country.code()}

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_broker_interest(self):
        interests_report = []
        interest_operations = self.category_operations(PredefinedCategory.Interest)
        interest_operations = [x for x in interest_operations if x.account_id() == self.account.id() and not self.excluded(x)]
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
                    'tax2pay': self._interest_tax(amount * rate),
                    'description': interest['note'],
                    'note': '',
                    **self.coded(TaxParameters.INTEREST)
                } | self._payer()
                interests_report.append(line)
            if interests:
                self.mark_printed(operation)
        # Process cash payments out of corporate actions
        payments = CorporateAction.get_payments(self.account)
        payments = [x for x in payments if self.in_period(self._moment(x['timestamp'], x['day_only']))]
        for payment in payments:
            if self.excluded_id(LedgerTransaction.CorporateAction, payment['oid']):
                continue
            rate = self.rate(self.account_currency.id(), payment['timestamp'])
            line = {
                'report_template': "interest",
                'payment_date': self._moment(payment['timestamp'], payment['day_only']),
                'rate': rate,
                'amount': payment['amount'],
                'amount_rub': round(payment['amount'] * rate, 2),
                'tax2pay': self._interest_tax(payment['amount'] * rate),
                'description': payment['note'],
                'note': '',
                **self.coded(TaxParameters.INTEREST)
            } | self._payer(LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, payment['oid']))
            interests_report.append(line)
            self.mark_printed_id(LedgerTransaction.CorporateAction, payment['oid'])
        self.add_estimate_header(interests_report, self.texts['estimate_interest'], TaxParameters.INTEREST)
        self.add_header(self.texts['interest_base'])
        self.insert_totals(interests_report, ["amount", "amount_rub", "tax2pay"])
        return interests_report
