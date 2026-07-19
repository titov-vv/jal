from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_quotes
from constants import PredefinedAsset, AssetLocation
from jal.db.asset import JalAsset, JalAssetCreator

# Seeded currencies of an empty database
RUB, USD, EUR = 1, 2, 3

TS = 1600000000          # A timestamp that all quotes below precede
EARLIER, LATER = 1500000000, 1550000000


def _create_crypto(name: str, symbol: str) -> int:
    creator = JalAssetCreator(PredefinedAsset.Crypto, name)
    creator.add_symbol(symbol, USD, location_id=AssetLocation.TRX_BLOCKCHAIN)
    return creator.commit().id()


# ----------------------------------------------------------------------------------------------------------------------
def test_direct_quote_is_preferred(prepare_db):
    asset = _create_crypto("Tron", "TRX")
    create_quotes(asset, USD, [(LATER, '0.30')])
    create_quotes(asset, EUR, [(LATER, '0.25')])
    # Nothing is converted while the requested currency has a series of its own
    assert JalAsset(asset).quote(TS, USD) == (LATER, Decimal('0.30'))
    assert JalAsset(asset).quote(TS, EUR) == (LATER, Decimal('0.25'))


def test_crypto_quote_is_cross_converted(prepare_db):
    # A crypto asset quoted in USD only - which is all DeFiLlama returns - held in a EUR account
    asset = _create_crypto("Tron", "TRX")
    create_quotes(asset, USD, [(LATER, '0.30')])
    create_quotes(USD, EUR, [(LATER, '0.90')])   # 1 USD = 0.90 EUR

    timestamp, rate = JalAsset(asset).quote(TS, EUR)
    assert rate == Decimal('0.27')               # 0.30 USD * 0.90 = 0.27 EUR
    assert timestamp == LATER                    # the timestamp of the quote actually used, not the requested one


def test_latest_quote_of_any_currency_is_used(prepare_db):
    # Two series exist but neither is in the requested currency: the most recent quote wins
    asset = _create_crypto("Tron", "TRX")
    create_quotes(asset, USD, [(EARLIER, '0.20')])
    create_quotes(asset, EUR, [(LATER, '0.25')])
    create_quotes(EUR, RUB, [(LATER, '100')])

    timestamp, rate = JalAsset(asset).quote(TS, RUB)
    assert rate == Decimal('25')                 # 0.25 EUR * 100 = 25 RUB, taken from the EUR series as it is newer
    assert timestamp == LATER


def test_quote_before_requested_timestamp_only(prepare_db):
    # A quote that is newer than the requested moment must never be used to value a past holding
    asset = _create_crypto("Tron", "TRX")
    create_quotes(asset, USD, [(LATER, '0.30')])
    create_quotes(USD, EUR, [(EARLIER, '0.90'), (LATER, '0.90')])
    assert JalAsset(asset).quote(EARLIER, EUR) == (0, Decimal('0'))


def test_no_quote_at_all_returns_zero(prepare_db):
    asset = _create_crypto("Nothing", "NIL")
    assert JalAsset(asset).quote(TS, USD) == (0, Decimal('0'))


def test_missing_pivot_rate_returns_zero(prepare_db):
    # The asset is quoted, but the currency it is quoted in can't be converted into the requested one
    asset = _create_crypto("Tron", "TRX")
    create_quotes(asset, USD, [(LATER, '0.30')])
    assert JalAsset(asset).quote(TS, RUB) == (0, Decimal('0'))


def test_currency_quote_is_unchanged(prepare_db):
    # Currencies keep resolving through the base-currency cross-rate and must never enter the non-Money path:
    # two currencies quoting each other would recurse endlessly there. RUB is the seeded base currency, so
    # RUB -> EUR is 1 / (EUR -> RUB) exactly as it was before crypto cross-conversion existed.
    create_quotes(EUR, RUB, [(LATER, '100')])
    assert JalAsset(EUR).quote(TS, RUB) == (LATER, Decimal('100'))
    assert JalAsset(RUB).quote(TS, EUR) == (TS, Decimal('0.01'))
