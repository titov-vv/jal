from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import SymbolId
from jal.db.asset import JalAsset
from jal.data_export.tax_parameters import TaxParameters


# The RU currency codes are those of ISO 4217 / ОКВ, as the currencies of a new database carry them
def test_ru_currency_codes_are_iso(prepare_db):
    parameters = TaxParameters('ru', 2025)
    for asset_id in (1, 2, 3):   # RUB, USD, EUR
        currency = JalAsset(asset_id)
        assert parameters.currency(currency.symbol())['code'] == currency.symbol_id(SymbolId.ISO4217_CODE)
