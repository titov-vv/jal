from decimal import Decimal
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.operations import AssetPayment, CorporateAction
from jal.data_export.taxes import TaxReport
from jal.db.category import JalCategory


class TaxesPortugal(TaxReport):
    currency_name = 'EUR'
    country_name = 'portugal'

    def __init__(self):
        super().__init__()
        self._processed_trade_qty = {}  # It will handle {trade_id: qty} records to keep track of already processed qty
        self.reports = {
            "Dividends": (self.prepare_dividends, "tax_prt_dividends.json"),
            "Shares": (self.prepare_stocks_and_etf, "tax_prt_shares.json"),
            "Interest": (self.prepare_broker_interest, "tax_prt_interests.json")
        }

    def prepare_dividends(self):
        dividends_report = []
        dividends = self.dividends_list()
        dividends = [x for x in dividends if x.amount(self.account_currency.id()) > 0]  # Skip negative dividends
        for dividend in dividends:
            country = dividend.asset().country()
            note = ''
            if dividend.subtype() == AssetPayment.StockDividend:
                note = "Stock dividend"
            if dividend.subtype() == AssetPayment.StockVesting:
                note = "Stock vesting"
            line = {
                'report_template': "dividend",
                'payment_date': dividend.timestamp(),
                'symbol': dividend.asset().symbol(self.account_currency.id()),
                'full_name': dividend.asset().name(),
                'isin': dividend.asset().isin(),
                'amount': dividend.amount(self.account_currency.id()),
                'tax': dividend.tax(),
                'rate': self.account_currency.quote(dividend.timestamp(), self._currency_id)[1],
                'country': country.name(language='en'),
                'tax_treaty': "Y" if self.has_tax_treaty_with(country.code()) else "N",
                'amount_eur': round(dividend.amount(self._currency_id), 2),
                'tax_eur': round(dividend.tax(self._currency_id), 2),
                'note': note
            }
            dividends_report.append(line)
        self.insert_totals(dividends_report, ["amount", "amount_eur", "tax", "tax_eur"])
        return dividends_report

# ----------------------------------------------------------------------------------------------------------------------
    def prepare_stocks_and_etf(self):
        deals_report = []
        ns = not self.use_settlement
        trades = self.trades_list([PredefinedAsset.Stock, PredefinedAsset.ETF])
        for trade in trades:
            note = ''
            if ns:
                rate = self.account_currency.quote(trade.close_operation().timestamp(), self._currency_id)[1]
            else:
                rate = self.account_currency.quote(trade.close_operation().settlement(), self._currency_id)[1]
            if trade.qty() >= Decimal('0'):  # Long trade
                value_realization = round(trade.close_amount(no_settlement=ns), 2)
                value_acquisition = round(trade.open_amount(no_settlement=ns), 2)
            else:  # Short trade
                value_realization = round(trade.open_amount(no_settlement=ns), 2)
                value_acquisition = round(trade.close_amount(no_settlement=ns), 2)
            for modifier in trade.modified_by():
                note = note + modifier.description() + "\n"
            profit = value_realization - value_acquisition - trade.close_fee() - trade.open_fee()
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(self.account_currency.id()),
                'isin': trade.asset().isin(),
                'qty': trade.qty(),
                'o_type': "Buy" if trade.qty() >= Decimal('0') else "Sell",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'os_date': trade.open_operation().settlement(),
                'o_price': trade.open_price(),
                'o_fee': trade.open_fee(),
                'o_fee_eur': trade.open_fee() * rate,
                'o_amount': value_acquisition,
                'o_amount_eur': value_acquisition * rate,
                'c_type': "Sell" if trade.qty() >= Decimal('0') else "Buy",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'cs_date': trade.close_operation().settlement(),
                'c_price': trade.close_operation().price(),
                'c_fee': trade.close_fee(),
                'c_fee_eur': trade.close_fee() * rate,
                'c_amount': value_realization,
                'c_amount_eur': value_realization * rate,
                'profit': round(profit, 2),
                'profit_eur': round(profit * rate, 2),
                'rate': rate,
                'note': note
            }
            deals_report.append(line)
        self.insert_totals(deals_report, ["income_eur", "spending_eur", "profit_eur", "profit"])
        return deals_report

# ----------------------------------------------------------------------------------------------------------------------
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
                    'amount_eur': round(amount * rate, 2),
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
                'amount_eur': round(payment['amount'] * rate, 2),
                'note': payment['note']
            }
            interests_report.append(line)
        self.insert_totals(interests_report, ["amount", "amount_eur"])
        return interests_report
