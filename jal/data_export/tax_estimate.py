from datetime import datetime, timezone
from decimal import Decimal

from jal.constants import PredefinedAsset
from jal.db.asset import JalAsset
from jal.db.lots import LedgerLotStore
from jal.db.operations import LedgerTransaction
from jal.data_export.taxes import TaxReport
from jal.data_export.tax_parameters import TaxParameters


# A rough tax on selling open lots of 'asset' on 'account' at 'timestamp': the jurisdiction's base capital gain rate
# on the gain in its currency, no brackets, deductions or losses of other deals
class TaxEstimate:
    LONG_HELD_DAYS = 365   # PT: crypto held this long is excluded; shorter holdings may go into englobamento

    def __init__(self, code: str, account, asset, timestamp: int):
        self.code = code
        self._asset = asset
        self._timestamp = timestamp
        self.year = datetime.fromtimestamp(timestamp, tz=timezone.utc).year
        self.base_rate = TaxParameters(code, self.year).rate(TaxParameters.CAPITAL_GAIN)   # None if not known
        try:
            self.currency_name = TaxReport.report_class(code).currency_name
        except ValueError:
            self.currency_name = ''
        self._tax_currency = JalAsset.find({'symbol': self.currency_name, 'type_id': PredefinedAsset.Money}).id()
        self.quote = asset.quote(timestamp, account.currency())[1]
        self.rate = JalAsset(account.currency()).quote(timestamp, self._tax_currency)[1]   # tax currency per unit

    # The gain of a lot in the tax currency: PT has both legs at the disposal's rate (CIRS a.23), RU the cost at the
    # rate of the purchase's settlement
    def gain(self, lot) -> Decimal:
        open_currency = JalAsset(lot.open_operation().account().currency())
        cost_price = lot.open_price() * lot.p_adjustment()   # in the currency it was paid in
        if self.code == 'pt':
            cost_rate = open_currency.quote(self._timestamp, self._tax_currency)[1]
        else:
            cost_rate = open_currency.quote(lot.open_operation().settlement(), self._tax_currency)[1]
        return lot.open_qty() * (self.quote * self.rate - cost_price * cost_rate)

    # Days held by the jurisdiction's clock: PT restarts it at a crypto-for-crypto exchange (CIRS a.10 n.20)
    def held_days(self, lot) -> int:
        since = lot.acquired()
        if self.code == 'pt' and self._asset.type() == PredefinedAsset.Crypto:
            operation = lot.open_operation()
            since = max(since, LedgerLotStore().last_modified_by(
                operation.type(), operation.id(), self._asset.id(),
                (LedgerTransaction.Swap, LedgerTransaction.Conversion), self._timestamp))
        return (self._timestamp - since) // 86400

    # True for a lot the tax leaves out: PT crypto held 365 days or more
    def excluded(self, lot) -> bool:
        return self.code == 'pt' and self._asset.type() == PredefinedAsset.Crypto \
            and self.held_days(lot) >= self.LONG_HELD_DAYS

    # {'gain', 'tax', 'excluded', 'short_held'} of the lots: tax on a positive total gain of the lots not excluded;
    # 'excluded' counts the lots left out, 'short_held' the PT lots held under 365 days (englobamento may apply)
    def totals(self, lots: list) -> dict:
        counted = [x for x in lots if not self.excluded(x)]
        gain = sum((self.gain(x) for x in counted), Decimal('0'))
        rate = Decimal('0') if self.base_rate is None else self.base_rate
        short_held = len([x for x in counted if self.held_days(x) < self.LONG_HELD_DAYS]) if self.code == 'pt' else 0
        return {'gain': gain, 'tax': rate * gain if gain > Decimal('0') else Decimal('0'),
                'excluded': len(lots) - len(counted), 'short_held': short_held}
