from decimal import Decimal
from jal.constants import PredefinedAsset, PredefinedCategory, SymbolId
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, AssetPayment, AssetIncome, CorporateAction
from jal.data_export.taxes import TaxReport, GAIN, INCOME
from jal.data_export.tax_parameters import TaxParameters


class TaxesPortugal(TaxReport):
    jurisdiction = 'pt'
    currency_name = 'EUR'
    report_timezone = 'Europe/Lisbon'
    currency_suffix = '_eur'
    summary_section = ("Summary", "tax_prt_summary.json")
    uncovered_section = ("Not covered", "tax_prt_uncovered.json")
    bases = [("Category G", GAIN, ["Shares", "Bonds", "Derivatives", "Crypto < 365 days"]),
             ("Category E", INCOME, ["Dividends", "Interest"])]
    outside = ["Crypto ≥ 365 days", "Crypto income", "Fees"]
    texts = {
        'rent_return': "Token account rent returned: a refund of rent paid, not income",
        'crypto_exchange': "Crypto-for-crypto exchange: not taxed until exit to fiat (CIRS art. 10.º, n.º 20)",
        'skipped_count': "Skipped by rule: {}",
        'uncovered': "No section of this report includes this operation",
        'skipped_total': "Skipped by the jurisdiction's rule",
        'uncovered_total': "Not included in any section",
        'pending_total': "Rows marked 'pending replay'",
        'excluded': "Your decision - not a tax event in Portugal: {}",
        'decisions': "Your decisions applied in this report (tax treatment overrides)",
        'override_excluded': "Not a tax event",
        'override_treaty': "Tax treaty applies",
        'override_no_treaty': "No tax treaty",
        'override_asset_source': "Source: the asset's country",
        'income': "Disposal value",
        'spending': "Acquisition cost and expenses",
        'profit': "Gain/loss",
        'gross': "Gross income",
        'amount': "Amount",
        'value': "Value at receipt (information)",
        'base_total': "Total of the category",
        'outside': "Outside both categories - for information, not totalled",
        'parameters_unreviewed': "Warning: the tax parameters (treaties, base rates) were last reviewed for {reviewed}; "
                                 "{year} uses the latest values known",
        'parameters_missing': "Warning: there are no tax parameters for {year}; no tax treaty is assumed",
        'rates_missing': "Warning: the database has no ECB rate {pair} after {rate}; operations up to {latest} use the "
                         "rate of {rate} - download the rates and make the report again",
        'fifo': "Deals are matched FIFO within this account; deals of other accounts are not netted here",
        'one_rate': "Cost, proceeds and expenses are converted at the EUR rate of the disposal date (CIRS art. 23.º)",
        'two_rates': "Each leg is converted at the EUR rate of its own trade date - not the one-rate reading of CIRS art. 23.º",
        'trade_date': "A sale belongs to the year of its trade date (CIRS art. 44.º); the settlement date is not used",
        'native_cost': "Cost is what was paid, in the currency it was paid in: a transfer between own accounts doesn't change it",
        'short_rate': "Short sale: converted at the EUR rate of the opening sale - JAL's logical reading, not a confirmed "
                      "rule, check with a tax adviser",
        'short_year': "Short sale: reported in the year of its close - an assumption as well",
        'cost_currency': "Cost paid in {}: the EUR figures convert it from that currency",
        'crypto_fiat': "Only disposals for money are here; crypto-for-crypto exchanges and wrappings are on "
                       "'Not covered' (CIRS art. 10.º, n.º 20)",
        'crypto_365': "Held 365 days or more: excluded from tax, still to be declared",
        'crypto_pending': "'Pending replay': the lot passed through a crypto-for-crypto exchange, so its cost or holding "
                          "period may still change",
        'pending': "Pending replay: the lot passed through a crypto-for-crypto exchange",
        'reward_lot': "Received as crypto income: zero cost, taxed on disposal only (CIRS art. 5.º, n.º 11)",
        'income_not_taxed': "Crypto received as income is not taxed at receipt: it opens a lot at zero cost, taxed when "
                            "disposed of (CIRS art. 5.º, n.º 11). Values are for information",
        'no_quote': "quotation is not present in database",
        'fees_modelo3': "Modelo 3 has no yearly expense line, only per-operation 'despesas e encargos': these costs are "
                        "listed for information",
        'fees_unlinked': "No cost here is linked to a deal",
        'fee_depositary': "Depositary fee",
        'fee_financing': "Position financing",
        'fee_asset': "Other asset fee or tax",
        'fee_broker': "Broker fee",
        'home_codes': "No codes: the account is with a Portuguese bank or broker, whose income comes pre-filled",
        'quadro_94a': "Declared in Anexo J, quadro 9.4A: no code, the quadro is the classification",
        'quadro_g1': "Declared for information in Anexo G1, quadro 7: no code",
        'bond_accrued': "Accrued interest is not in the price: received, it is category E income on the Interest sheet; "
                        "paid with a purchase, it is not deducted (category E has no expenses)",
        'accrued_paid': "Accrued interest paid with a bond purchase: not deducted, category E has no expenses",
        'no_40a': "The 50% exclusion of art. 40.º-A is assumed not to apply",
        'coupon': "Bond interest"
    }
    operation_labels = {
        (LedgerTransaction.Trade, None): "Trade",
        (LedgerTransaction.Swap, None): "Crypto swap",
        (LedgerTransaction.Conversion, None): "Token wrapping",
        (LedgerTransaction.IncomeSpending, None): "Cash operation",
        (LedgerTransaction.CorporateAction, CorporateAction.Merger): "Merger",
        (LedgerTransaction.CorporateAction, CorporateAction.SpinOff): "Spin-off",
        (LedgerTransaction.CorporateAction, CorporateAction.SymbolChange): "Symbol change",
        (LedgerTransaction.CorporateAction, CorporateAction.Split): "Split",
        (LedgerTransaction.AssetPayment, AssetPayment.Dividend): "Dividend",
        (LedgerTransaction.AssetPayment, AssetPayment.BondInterest): "Bond interest",
        (LedgerTransaction.AssetPayment, AssetPayment.AssetFee): "Asset fee or tax",
        (LedgerTransaction.AssetPayment, AssetPayment.DepositaryFee): "Depositary fee",
        (LedgerTransaction.AssetPayment, AssetPayment.PositionFinancing): "Position financing",
        (LedgerTransaction.AssetIncome, AssetIncome.StockDividend): "Stock dividend",
        (LedgerTransaction.AssetIncome, AssetIncome.StockVesting): "Stock vesting",
        (LedgerTransaction.AssetIncome, AssetIncome.StakingReward): "Staking reward",
        (LedgerTransaction.AssetIncome, AssetIncome.Reward): "Reward",
        (LedgerTransaction.AssetIncome, AssetIncome.LendingInterest): "Lending interest",
        (LedgerTransaction.AssetIncome, AssetIncome.TokenRentReturn): "Token account rent returned"
    }

    def __init__(self):
        super().__init__()
        self._processed_trade_qty = {}  # It will handle {trade_id: qty} records to keep track of already processed qty
        self.one_currency_rate = True   # CIRS a.23: cost, proceeds and fees at the rate of the disposal
        self.reports = {
            "Shares": (self.prepare_stocks_and_etf, "tax_prt_shares.json"),
            "Bonds": (self.prepare_bonds, "tax_prt_bonds.json"),
            "Derivatives": (self.prepare_derivatives, "tax_prt_derivatives.json"),
            "Crypto < 365 days": (self.prepare_crypto_short, "tax_prt_crypto.json"),
            "Dividends": (self.prepare_dividends, "tax_prt_dividends.json"),
            "Interest": (self.prepare_broker_interest, "tax_prt_interests.json"),
            "Crypto ≥ 365 days": (self.prepare_crypto_long, "tax_prt_crypto_365.json"),
            "Crypto income": (self.prepare_crypto_income, "tax_prt_crypto_income.json"),
            "Fees": (self.prepare_fees, "tax_prt_fees.json")
        }

    # A trade belongs to the year of its trade date on Lisbon's clock (CIRS a.44), settlement is not read
    def trade_date(self, operation) -> int:
        return self._moment(operation.timestamp(), operation.timestamp_is_day())

    # No crypto-for-crypto exchange is a disposal until the exit to fiat; a wrapping is read the same way
    def skip_reason(self, operation):
        if operation.type() in (LedgerTransaction.Swap, LedgerTransaction.Conversion):
            return self.texts['crypto_exchange']
        if operation.type() == LedgerTransaction.AssetPayment and operation.subtype() == AssetPayment.BondInterest \
                and operation.amount() < Decimal('0'):
            return self.texts['accrued_paid']
        return super().skip_reason(operation)

    def prepare_dividends(self):
        self.add_header(self.texts['no_40a'])
        dividends_report = []
        dividends = self.dividends_list()
        dividends = [x for x in dividends if x.amount(self.account_currency.id()) > 0]  # Skip negative dividends
        for dividend in dividends:
            country = dividend.asset().country()
            note = ''
            if dividend.type() == LedgerTransaction.AssetIncome:
                if dividend.subtype() == AssetIncome.StockDividend:
                    note = "Stock dividend"
                if dividend.subtype() == AssetIncome.StockVesting:
                    note = "Stock vesting"
            rate = self.rate(self.account_currency.id(), dividend.timestamp())
            line = {
                'report_template': "dividend",
                'payment_date': self._moment(dividend.timestamp(), dividend.timestamp_is_day()),
                'symbol': dividend.symbol().symbol(),
                'full_name': dividend.asset().name(),
                'isin': dividend.symbol().identifier(SymbolId.ISIN),
                'amount': dividend.amount(self.account_currency.id()),
                'tax': dividend.tax(),
                'rate': rate,
                'country': country.name(language='en'),
                'tax_treaty': "Y" if self.has_tax_treaty_with(country.code(), dividend) else "N",
                'amount_eur': round(dividend.amount(self.account_currency.id()) * rate, 2),
                'tax_eur': round(dividend.tax() * rate, 2),
                'note': note,
                **self.coded(TaxParameters.DIVIDEND)
            }
            dividends_report.append(line)
            self.mark_printed(dividend)
        self.insert_totals(dividends_report, ["amount", "amount_eur", "tax", "tax_eur"])
        return dividends_report

    # The headers every deals section states: the matching rule, the rate rule, the year and the cost
    def _deal_headers(self):
        self.add_header(self.texts['fifo'])
        self.add_header(self.texts['one_rate'] if self.one_currency_rate else self.texts['two_rates'])
        self.add_header(self.texts['trade_date'])
        self.add_header(self.texts['native_cost'])

    # One deal: the account-currency columns are JAL's own view, the EUR ones the tax figures - the native cost converted
    # from the currency it was paid in, at the rate of the disposal (a short's opening sale) or of each leg's own date
    def _deal_row(self, trade, kind=None) -> dict:
        open_op, close_op = trade.open_operation(), trade.close_operation()
        long = trade.qty() >= Decimal('0')
        disposal = close_op if long else open_op
        o_ts = disposal.timestamp() if self.one_currency_rate else open_op.timestamp()
        c_ts = disposal.timestamp() if self.one_currency_rate else close_op.timestamp()
        open_currency = open_op.account().currency()
        o_rate = self.rate(open_currency, o_ts)
        c_rate = self.rate(self.account_currency.id(), c_ts)
        o_amount_eur = round(trade.native_open_amount() * o_rate, 2)
        o_fee_eur = trade.native_open_fee() * o_rate
        c_amount, c_fee = trade.close_amount(), trade.close_fee()
        c_amount_eur = round(c_amount * c_rate, 2)
        c_fee_eur = c_fee * c_rate
        fees_eur = round(o_fee_eur + c_fee_eur, 2)
        o_amount = round(trade.open_amount(), 2)
        fees = round(trade.fee(), 2)
        if long:
            income_eur, spending_eur = c_amount_eur, o_amount_eur + fees_eur
            profit = round(c_amount, 2) - (o_amount + fees)
        else:
            income_eur, spending_eur = o_amount_eur, c_amount_eur + fees_eur
            profit = o_amount - (round(c_amount, 2) + fees)
        notes = []
        if open_currency != self.account_currency.id():
            notes.append(self.texts['cost_currency'].format(JalAsset(open_currency).symbol()))
        if not long:
            if self.one_currency_rate:
                notes.append(self.texts['short_rate'])
            notes.append(self.texts['short_year'])
        notes += [x.description().strip() for x in self.deal_modifiers(trade) if x.description().strip()]
        return {
            'report_template': "trade",
            'symbol': close_op.symbol().symbol(),
            'isin': close_op.symbol().identifier(SymbolId.ISIN),
            'qty': trade.qty(),
            'o_type': "Aquisição" if long else "Venda",
            'o_number': open_op.number(),
            'o_date': self._moment(trade.acquired(), trade.acquired_is_day()),
            'o_rate': o_rate,
            'o_price': o_amount / abs(trade.qty()),   # per unit as held now, after a split
            'o_fee': trade.open_fee(),
            'o_fee_eur': o_fee_eur,
            'o_amount': o_amount,
            'o_amount_eur': o_amount_eur,
            'c_type': "Venda" if long else "Aquisição",
            'c_number': close_op.number(),
            'c_date': self._moment(close_op.timestamp(), close_op.timestamp_is_day()),
            'c_rate': c_rate,
            'c_price': close_op.price(),
            'c_fee': c_fee,
            'c_fee_eur': c_fee_eur,
            'c_amount': round(c_amount, 2),
            'c_amount_eur': c_amount_eur,
            'income_eur': income_eur,
            'spending_eur': spending_eur,
            'profit': profit,
            'profit_eur': income_eur - spending_eur,
            'note': "\n".join(notes),
            **({} if kind is None else self.coded(kind))
        }

    def prepare_stocks_and_etf(self):
        self._deal_headers()
        deals_report = []
        for trade in self.trades_list([PredefinedAsset.Stock, PredefinedAsset.ETF]):
            kind = TaxParameters.ETF if trade.asset().type() == PredefinedAsset.ETF else TaxParameters.STOCK
            deals_report.append(self._deal_row(trade, kind))
            self.mark_printed(trade.close_operation())
        self.insert_totals(deals_report, ["income_eur", "spending_eur", "profit_eur", "profit"])
        return deals_report

    # Sales and redemptions of bonds at their price, accrued interest left to the Interest sheet
    def prepare_bonds(self):
        self._deal_headers()
        self.add_header(self.texts['bond_accrued'])
        return self._deals_of([PredefinedAsset.Bond], TaxParameters.BOND)

    def prepare_derivatives(self):
        self._deal_headers()
        return self._deals_of([PredefinedAsset.Derivative], TaxParameters.DERIVATIVE)

    def _deals_of(self, asset_types, kind) -> list:
        deals_report = []
        for trade in self.trades_list(asset_types):
            deals_report.append(self._deal_row(trade, kind))
            self.mark_printed(trade.close_operation())
        self.insert_totals(deals_report, ["income_eur", "spending_eur", "profit_eur", "profit"])
        return deals_report

    # Disposals of crypto for money, with the holding period that decides the 365-day exclusion
    # Disposals of crypto for money held under 365 days: category G
    def prepare_crypto_short(self):
        self._crypto_headers()
        self.add_header(self.texts['quadro_94a'])
        return self._crypto_deals(long_held=False)

    # Disposals of crypto for money held 365 days or more: excluded, declared for information
    def prepare_crypto_long(self):
        self._crypto_headers()
        self.add_header(self.texts['crypto_365'])
        self.add_header(self.texts['quadro_g1'])
        return self._crypto_deals(long_held=True)

    def _crypto_headers(self):
        self._deal_headers()
        self.add_header(self.texts['crypto_fiat'])
        self.add_header(self.texts['crypto_pending'])

    # The crypto deals on one side of the 365 days, with the holding period
    def _crypto_deals(self, long_held: bool) -> list:
        deals_report = []
        for trade in self.trades_list([PredefinedAsset.Crypto]):
            line = self._deal_row(trade)
            days = (line['c_date'] - line['o_date']) // 86400
            if (days >= 365) != long_held:
                continue
            line['days'] = days
            notes = [line['note']] if line['note'] else []
            if trade.open_operation().type() == LedgerTransaction.AssetIncome:
                notes.insert(0, self.texts['reward_lot'])
            through_swap = trade.open_operation().type() == LedgerTransaction.Swap or \
                self.carried_through(trade, (LedgerTransaction.Swap, LedgerTransaction.Conversion))
            if through_swap:
                line['pending_replay'] = True
                notes.insert(0, self.texts['pending'])
            line['note'] = "\n".join(notes)
            deals_report.append(line)
            self.mark_printed(trade.close_operation())
        self.insert_totals(deals_report, ["income_eur", "spending_eur", "profit_eur", "profit"])
        return deals_report

    # Crypto received as income: not taxed at receipt, listed with its value for information
    def prepare_crypto_income(self):
        self.add_header(self.texts['income_not_taxed'])
        incomes_report = []
        incomes = []
        for subtype in (AssetIncome.StakingReward, AssetIncome.Reward, AssetIncome.LendingInterest):
            incomes += AssetIncome.get_list(self.account.id(), subtype=subtype)
        incomes = [x for x in incomes if self.in_year(self._moment(x.timestamp(), x.timestamp_is_day()))]
        for income in sorted(incomes, key=lambda x: x.timestamp()):
            if self.excluded(income):
                continue
            quoted, price = income.asset().quote(income.timestamp(), self.account_currency.id(), report_missing=False)
            if not quoted:
                price = Decimal('0')
            value = income.amount() * price
            rate = self.rate(self.account_currency.id(), income.timestamp())
            incomes_report.append({
                'report_template': "income",
                'payment_date': self._moment(income.timestamp(), income.timestamp_is_day()),
                'operation': self.operation_label(income),
                'symbol': income.symbol().symbol(),
                'qty': income.amount(),
                'price': price,
                'value': round(value, 2),
                'rate': rate,
                'value_eur': round(value * rate, 2),
                'note': '' if quoted else self.texts['no_quote']
            })
            self.mark_printed(income)
        self.insert_totals(incomes_report, ["value", "value_eur"])
        return incomes_report

    # Costs of holding, grouped by kind, and the broker's fees: none of them is linked to a deal
    def prepare_fees(self):
        self.add_header(self.texts['fees_modelo3'])
        self.add_header(self.texts['fees_unlinked'])
        fees_report = []
        kinds = ((AssetPayment.DepositaryFee, 'fee_depositary'), (AssetPayment.PositionFinancing, 'fee_financing'),
                 (AssetPayment.AssetFee, 'fee_asset'))
        for subtype, kind in kinds:
            payments = AssetPayment.get_list(self.account.id(), subtype=subtype)
            payments = [x for x in payments if self.in_year(self._moment(x.timestamp(), x.timestamp_is_day()))]
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
                    'amount_eur': round(amount * rate, 2),
                    'note': ''
                })
                self.mark_printed(payment)
        operations = [x for x in self.category_operations(PredefinedCategory.Fees) if x.account_id() == self.account.id()]
        operations = [x for x in operations if not self.excluded(x)]
        for operation in operations:
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
                    'amount_eur': round(amount * rate, 2),
                    'note': ''
                })
            if fees:
                self.mark_printed(operation)
        self.insert_totals(fees_report, ["amount", "amount_eur"])
        return fees_report

    # ------------------------------------------------------------------------------------------------------------------
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
                    'amount_eur': round(amount * rate, 2),
                    'description': interest['note'],
                    'note': '',
                    **self.coded(TaxParameters.INTEREST)
                }
                interests_report.append(line)
            if interests:
                self.mark_printed(operation)
        # Process cash payments out of corporate actions
        payments = CorporateAction.get_payments(self.account)
        payments = [x for x in payments if self.year_begin <= self._moment(x['timestamp'], x['day_only']) < self.year_end]
        for payment in payments:
            if self.excluded_id(LedgerTransaction.CorporateAction, payment['oid']):
                continue
            rate = self.rate(self.account_currency.id(), payment['timestamp'])
            line = {
                'report_template': "interest",
                'payment_date': self._moment(payment['timestamp'], payment['day_only']),
                'rate': rate,
                'amount': payment['amount'],
                'amount_eur': round(payment['amount'] * rate, 2),
                'description': payment['note'],
                'note': '',
                **self.coded(TaxParameters.INTEREST)
            }
            interests_report.append(line)
            self.mark_printed_id(LedgerTransaction.CorporateAction, payment['oid'])
        # Bond coupons and the accrued interest received on a sale; that paid on a purchase is skipped by rule
        coupons = AssetPayment.get_list(self.account.id(), subtype=AssetPayment.BondInterest)
        coupons = [x for x in coupons if self.in_year(self._moment(x.timestamp(), x.timestamp_is_day()))]
        for coupon in sorted(coupons, key=lambda x: x.timestamp()):
            if coupon.amount() <= Decimal('0') or self.excluded(coupon):
                continue
            rate = self.rate(self.account_currency.id(), coupon.timestamp())
            interests_report.append({
                'report_template': "interest",
                'payment_date': self._moment(coupon.timestamp(), coupon.timestamp_is_day()),
                'rate': rate,
                'amount': coupon.amount(),
                'amount_eur': round(coupon.amount() * rate, 2),
                'description': f"{self.texts['coupon']} {coupon.symbol().symbol()}: {coupon.note()}".strip(),
                'note': '',
                **self.coded(TaxParameters.COUPON)
            })
            self.mark_printed(coupon)
        self.insert_totals(interests_report, ["amount", "amount_eur"])
        return interests_report
