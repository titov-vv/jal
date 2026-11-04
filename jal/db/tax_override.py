from PySide6.QtWidgets import QApplication
from jal.db.db import JalDB
from jal.db.country import JalCountry
from jal.db.operations import LedgerTransaction, AssetPayment, AssetIncome


# Kinds of a tax override and the values they take
class TaxOverride:
    NotTaxEvent = 1   # The operation is not a tax event in this jurisdiction; value unused
    Treaty = 2        # A tax treaty applies to this dividend (value '1') or doesn't ('0')

    TreatyApplies = '1'
    NoTreaty = '0'

    @staticmethod
    def tr(text):
        return QApplication.translate("TaxOverride", text)

    # The decision as the user reads it
    @staticmethod
    def label(kind: int, value: str) -> str:
        labels = {(TaxOverride.NotTaxEvent, ''): TaxOverride.tr("Not a tax event"),
                  (TaxOverride.Treaty, TaxOverride.TreatyApplies): TaxOverride.tr("Tax treaty applies"),
                  (TaxOverride.Treaty, TaxOverride.NoTreaty): TaxOverride.tr("No tax treaty")}
        return labels.get((kind, value), '')

    # True for the operations a report reads as dividends - the only ones a treaty decision applies to
    @staticmethod
    def takes_treaty(operation) -> bool:
        if operation.type() == LedgerTransaction.AssetPayment:
            return operation.subtype() == AssetPayment.Dividend
        if operation.type() == LedgerTransaction.AssetIncome:
            return operation.subtype() in (AssetIncome.StockDividend, AssetIncome.StockVesting)
        return False


# ----------------------------------------------------------------------------------------------------------------------
# Access to 'tax_overrides': the user's decision on how one jurisdiction's tax report treats one operation.
# Report input only, the ledger never reads it.
class JalTaxOverride(JalDB):
    _VALUES = {TaxOverride.NotTaxEvent: ('',), TaxOverride.Treaty: (TaxOverride.TreatyApplies, TaxOverride.NoTreaty)}

    # Every override of the operation, as a list of {'jurisdiction', 'kind', 'value', 'note'}
    @classmethod
    def for_operation(cls, operation_id: int) -> list:
        query = cls._exec("SELECT jurisdiction, kind, value, note FROM tax_overrides WHERE operation_id=:oid "
                          "ORDER BY jurisdiction, kind", [(":oid", operation_id)])
        overrides = []
        while query.next():
            jurisdiction, kind, value, note = cls._read_record(query, cast=[str, int, str, str])
            overrides.append({'jurisdiction': jurisdiction, 'kind': kind, 'value': value, 'note': note})
        return overrides

    # Every override of the jurisdiction, as {(operation_id, kind): (value, note)}
    @classmethod
    def for_jurisdiction(cls, jurisdiction: str) -> dict:
        query = cls._exec("SELECT operation_id, kind, value, note FROM tax_overrides WHERE jurisdiction=:code",
                          [(":code", jurisdiction)])
        overrides = {}
        while query.next():
            operation_id, kind, value, note = cls._read_record(query, cast=[int, int, str, str])
            overrides[(operation_id, kind)] = (value, note)
        return overrides

    # Stores the override, replacing one of the same operation, jurisdiction and kind
    @classmethod
    def set(cls, jurisdiction: str, operation_id: int, kind: int, value: str, note: str) -> None:
        if kind not in cls._VALUES:
            raise ValueError(f"Unknown tax override kind: {kind}")
        if value not in cls._VALUES[kind]:
            raise ValueError(f"Invalid value '{value}' for tax override kind {kind}")
        if not jurisdiction or not note.strip():
            raise ValueError("A tax override needs a jurisdiction and a note")
        cls._exec("INSERT INTO tax_overrides (operation_id, jurisdiction, kind, value, note) "
                  "VALUES (:oid, :code, :kind, :value, :note) "
                  "ON CONFLICT (operation_id, jurisdiction, kind) DO UPDATE SET value=excluded.value, note=excluded.note",
                  [(":oid", operation_id), (":code", jurisdiction), (":kind", kind), (":value", value),
                   (":note", note.strip())], commit=True)

    @classmethod
    def delete(cls, jurisdiction: str, operation_id: int, kind: int) -> None:
        cls._exec("DELETE FROM tax_overrides WHERE operation_id=:oid AND jurisdiction=:code AND kind=:kind",
                  [(":oid", operation_id), (":code", jurisdiction), (":kind", kind)], commit=True)

    # One line per override of the operation: "<country>: <decision> - <note>"
    @classmethod
    def describe(cls, operation_id: int) -> str:
        lines = []
        for item in cls.for_operation(operation_id):
            country = JalCountry(data={'code': item['jurisdiction']}, search=True).name()
            lines.append(f"{country}: {TaxOverride.label(item['kind'], item['value'])} - {item['note']}")
        return "\n".join(lines)
