from decimal import Decimal
from datetime import datetime

from jal.db.operations import Dividend
from jal.data_export.taxes import TaxReport


class TaxesPortugal(TaxReport):
    currency_name = 'EUR'
    country_name = 'portugal'

    def __init__(self):
        super().__init__()
        self._processed_trade_qty = {}  # It will handle {trade_id: qty} records to keep track of already processed qty
        self.reports = {
            "Dividends": (self.prepare_dividends, "tax_prt_dividends.json"),
            "Shares": (self.prepare_stocks_and_etf, "tax_prt_shares.json")
        }

    def prepare_dividends(self):
        dividends_report = []
        dividends = self.dividends_list()
        dividends = [x for x in dividends if x.amount(self.account_currency.id()) > 0]  # Skip negative dividends
        for dividend in dividends:
            country = dividend.asset().country()
            note = ''
            if dividend.subtype() == Dividend.StockDividend:
                note = "Stock dividend"
            if dividend.subtype() == Dividend.StockVesting:
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

    def inflation(self, timestamp: int) -> Decimal:
        year = datetime.utcfromtimestamp(timestamp).strftime('%Y')
        inflation_coefficients = self._parameters['currency_devaluation']
        try:
            coefficient = Decimal(inflation_coefficients[year])
        except KeyError:
            coefficient = Decimal('1')
        return coefficient

# ----------------------------------------------------------------------------------------------------------------------
    def prepare_stocks_and_etf(self):
        deals_report = []
        ns = not self.use_settlement
        trades = self.shares_trades_list()
        for trade in trades:
            if ns:
                os_rate = self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1]
                cs_rate = self.account_currency.quote(trade.close_operation().timestamp(), self._currency_id)[1]
            else:
                os_rate = self.account_currency.quote(trade.open_operation().settlement(), self._currency_id)[1]
                cs_rate = self.account_currency.quote(trade.close_operation().settlement(), self._currency_id)[1]
            if trade.qty() >= Decimal('0'):  # Long trade
                note = ''
                income = round(trade.close_amount(no_settlement=ns), 2)
                income_eur = round(trade.close_amount(self._currency_id, no_settlement=ns), 2)
                spending = round(trade.open_amount(no_settlement=ns), 2) + trade.fee()
                spending_eur = round(trade.open_amount(self._currency_id, no_settlement=ns), 2) + round(trade.fee(self._currency_id), 2)
            else:  # Short trade
                # Check were there any dividends during short position holding
                short_dividend_eur = Decimal('0')
                dividends = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
                dividends = [x for x in dividends if
                             trade.open_operation().settlement() <= x.ex_date() <= trade.close_operation().settlement()]
                for dividend in dividends:
                    short_dividend_eur += dividend.amount(self._currency_id)
                note = f"Dividend withheld: {short_dividend_eur} EUR" if short_dividend_eur > Decimal('0') else ''
                income = round(trade.open_amount(no_settlement=ns), 2)
                income_eur = round(trade.open_amount(self._currency_id, no_settlement=ns), 2)
                spending = round(trade.close_amount(no_settlement=ns), 2) + trade.fee() + short_dividend_eur
                spending_eur = round(trade.close_amount(self._currency_id, no_settlement=ns), 2) + round(trade.fee(self._currency_id), 2)
            inflation = self.inflation(trade.open_operation().timestamp())
            if inflation != Decimal('1'):
                spending_eur *= inflation
                note = f"Inflation coefficient: {inflation:.2f}\n" + note
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(self.account_currency.id()),
                'isin': trade.asset().isin(),
                'qty': trade.qty(),
                'o_type': "Buy" if trade.qty() >= Decimal('0') else "Sell",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': self.account_currency.quote(trade.open_operation().timestamp(), self._currency_id)[1],
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_operation().price(),
                'o_amount': round(trade.open_amount(no_settlement=ns), 2),
                'o_amount_eur': round(trade.open_amount(self._currency_id, no_settlement=ns), 2),
                'o_fee': trade.open_fee(),
                'o_fee_eur': round(trade.open_fee(self._currency_id), 2),
                'c_type': "Sell" if trade.qty() >= Decimal('0') else "Buy",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': self.account_currency.quote(trade.close_operation().timestamp(), self._currency_id)[1],
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': trade.close_operation().price(),
                'c_amount': round(trade.close_amount(no_settlement=ns), 2),
                'c_amount_eur': round(trade.close_amount(self._currency_id, no_settlement=ns), 2),
                'c_fee': trade.close_fee(),
                'c_fee_eur': round(trade.close_fee(self._currency_id), 2),
                'income_eur': income_eur,
                'spending_eur': spending_eur,
                'profit': income - spending,
                'profit_eur': income_eur - spending_eur,
                'note': note
            }
            deals_report.append(line)
        self.insert_totals(deals_report, ["income_eur", "spending_eur", "profit_eur", "profit"])
        return deals_report
