import pytest
import sqlparse

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_stocks, create_dividends, operation_id, nth_operation
from jal.db.db import JalDB
from jal.db.operations import LedgerTransaction
from jal.db.tax_override import JalTaxOverride, TaxOverride

_MIGRATION_FROM = "-- TAX OVERRIDES:"
_MIGRATION_TO = "-- Set new DB schema version"


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_86.sql", encoding='utf-8') as delta:
        text = delta.read()
    for statement in sqlparse.split(text[text.index(_MIGRATION_FROM):text.index(_MIGRATION_TO)]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue
        assert JalDB._exec(statement.strip(), commit=True) is not None, f"Migration statement failed: {statement}"


def _table_sql(name) -> str:
    return JalDB._read("SELECT sql FROM sqlite_master WHERE name=:name", [(":name", name)])


# Two dividends of stock A (id 4) on account 1
def _two_dividends() -> tuple:
    create_stocks([('A', 'Asset A')], currency_id=2)
    create_dividends([(d2t(240301), 1, 4, 10.0, 1.5, "Dividend 1"), (d2t(240601), 1, 4, 20.0, 3.0, "Dividend 2")])
    return operation_id(LedgerTransaction.AssetPayment, 1), operation_id(LedgerTransaction.AssetPayment, 2)


# A schema-85 database has no table; the delta creates the same one jal_init.sql does
def test_delta_86_upgrade(prepare_db, project_root):
    table, index = _table_sql('tax_overrides'), _table_sql('tax_overrides_uniqueness')
    JalDB._exec("DROP TABLE tax_overrides", commit=True)
    assert _table_sql('tax_overrides') is None

    _run_migration(project_root)

    strip = lambda sql: ' '.join(sqlparse.format(sql, strip_comments=True).split())
    assert strip(_table_sql('tax_overrides')) == strip(table)
    assert _table_sql('tax_overrides_uniqueness') == index


def test_tax_override_set_get_delete(prepare_db_taxes):
    first, second = _two_dividends()
    assert JalTaxOverride.for_operation(first) == []
    assert JalTaxOverride.for_jurisdiction('ru') == {}

    JalTaxOverride.set('ru', first, TaxOverride.Treaty, TaxOverride.NoTreaty, " Broker lost its status ")
    JalTaxOverride.set('pt', first, TaxOverride.NotTaxEvent, '', "Return of capital")
    JalTaxOverride.set('ru', second, TaxOverride.NotTaxEvent, '', "Booked twice by the broker")
    assert JalTaxOverride.for_operation(first) == [
        {'jurisdiction': 'pt', 'kind': TaxOverride.NotTaxEvent, 'value': '', 'note': "Return of capital"},
        {'jurisdiction': 'ru', 'kind': TaxOverride.Treaty, 'value': '0', 'note': "Broker lost its status"}]
    assert JalTaxOverride.for_jurisdiction('ru') == {
        (first, TaxOverride.Treaty): ('0', "Broker lost its status"),
        (second, TaxOverride.NotTaxEvent): ('', "Booked twice by the broker")}

    JalTaxOverride.set('ru', first, TaxOverride.Treaty, TaxOverride.TreatyApplies, "Treaty credit")   # replaces
    assert JalTaxOverride.for_jurisdiction('ru')[(first, TaxOverride.Treaty)] == ('1', "Treaty credit")
    assert JalDB._read("SELECT COUNT(*) FROM tax_overrides") == 3

    JalTaxOverride.delete('ru', first, TaxOverride.Treaty)
    assert JalTaxOverride.for_operation(first) == [
        {'jurisdiction': 'pt', 'kind': TaxOverride.NotTaxEvent, 'value': '', 'note': "Return of capital"}]


@pytest.mark.parametrize("kind, value, note", [(3, '', "x"), (TaxOverride.Treaty, '', "x"),
                                               (TaxOverride.NotTaxEvent, '1', "x"), (TaxOverride.NotTaxEvent, '', " ")])
def test_tax_override_rejects(prepare_db_taxes, kind, value, note):
    first, _ = _two_dividends()
    with pytest.raises(ValueError):
        JalTaxOverride.set('ru', first, kind, value, note)
    assert JalDB._read("SELECT COUNT(*) FROM tax_overrides") == 0


# Deleting the operation deletes its overrides
def test_tax_override_cascade(prepare_db_taxes):
    first, second = _two_dividends()
    JalTaxOverride.set('ru', first, TaxOverride.NotTaxEvent, '', "Not income")
    JalTaxOverride.set('ru', second, TaxOverride.NotTaxEvent, '', "Not income")
    nth_operation(LedgerTransaction.AssetPayment, 1).delete()
    assert list(JalTaxOverride.for_jurisdiction('ru')) == [(second, TaxOverride.NotTaxEvent)]
