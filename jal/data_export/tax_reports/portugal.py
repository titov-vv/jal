import logging

from jal.db.operations import Dividend
from jal.db.asset import JalAsset
from jal.db.country import JalCountry
from jal.data_export.taxes import TaxReport


class TaxesPortugal(TaxReport):
    currency_name = 'EUR'
    def __init__(self):
        super().__init__()
        self._processed_trade_qty = {}  # It will handle {trade_id: qty} records to keep track of already processed qty
        self.reports = {
            "Dividends": (self.prepare_dividends, "tax_prt_dividends.json")
        }

    def prepare_dividends(self):
        currency = JalAsset(self.account.currency())
        dividends_report = []
        dividends = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockDividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockVesting)
        dividends = [x for x in dividends if self.year_begin <= x.timestamp() <= self.year_end]  # Only in given range
        for dividend in dividends:
            amount = dividend.amount()
            rate = currency.quote(dividend.timestamp(), self._currency_id)[1]
            price = dividend.asset().quote(dividend.timestamp(), currency.id())[1]
            country = JalCountry(dividend.asset().country())
            tax_treaty = "Y" if country.has_tax_treaty() else "N"
            note = ''
            if dividend.subtype() == Dividend.StockDividend:
                if not price:
                    logging.error(self.tr("No price data for stock dividend: ") + f"{dividend}")
                    continue
                amount = amount * price
                note = "Stock dividend"
            if dividend.subtype() == Dividend.StockVesting:
                if not price:
                    logging.error(self.tr("No price data for stock vesting: ") + f"{dividend}")
                    continue
                amount = amount * price
                note = "Stock vesting"
            amount_rub = amount * rate
            tax_rub = dividend.tax() * rate
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
                'note': note
            }
            dividends_report.append(line)
        self.insert_totals(dividends_report, ["amount", "amount_rub", "tax", "tax_rub"])
        return dividends_report
