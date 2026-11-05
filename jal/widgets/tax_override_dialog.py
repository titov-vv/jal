from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QLabel, QComboBox, QLineEdit

from jal.db.country import JalCountry
from jal.db.operations import LedgerTransaction
from jal.db.basis_policy import Basis
from jal.db.tax_override import JalTaxOverride, TaxOverride
from jal.data_export.taxes import TaxReport
from jal.widgets.icons import JalIcon
from jal.widgets.helpers import ts2dt


# ----------------------------------------------------------------------------------------------------------------------
# The user's decision on how each jurisdiction's tax report treats one operation: one row per jurisdiction, a decision,
# the price it takes if any and the note the report prints with it. Ok writes the rows; a row without a decision
# removes its overrides.
class TaxOverrideDialog(QDialog):
    KINDS = (TaxOverride.NotTaxEvent, TaxOverride.Treaty, TaxOverride.AssetSource, TaxOverride.TaxEvent,
             TaxOverride.PricePerShare)   # one of them per jurisdiction

    def __init__(self, otype: int, oid: int, parent=None):
        super().__init__(parent)
        self._oid = oid
        operation = LedgerTransaction.get_operation(otype, oid)
        choices = [(None, None), (TaxOverride.NotTaxEvent, '')]   # index 0: no override
        if TaxOverride.takes_treaty(operation):
            choices += [(TaxOverride.Treaty, TaxOverride.TreatyApplies), (TaxOverride.Treaty, TaxOverride.NoTreaty)]
        self._choices = {}   # {jurisdiction: [(kind, value)]}
        for code in TaxReport.jurisdictions:
            self._choices[code] = list(choices)
            if TaxOverride.takes_asset_source(operation) and TaxReport.report_class(code).asset_source_override:
                self._choices[code].append((TaxOverride.AssetSource, TaxOverride.AssetCountry))
            if TaxOverride.takes_tax_event(operation) and self._carried(code, operation):
                self._choices[code].append((TaxOverride.TaxEvent, ''))
            if TaxOverride.takes_price(operation):
                self._choices[code].append((TaxOverride.PricePerShare, None))
        stored = {(x['jurisdiction'], x['kind']): x for x in JalTaxOverride.for_operation(oid)}
        self.setWindowTitle(self.tr("Tax treatment"))
        layout = QGridLayout(self)
        heading = f"{ts2dt(operation.timestamp(), operation.timestamp_is_day())}  {operation.name()}\n" \
                  f"{operation.account_name()}  {operation.asset_name()}"
        layout.addWidget(QLabel(heading.strip(), self), 0, 0, 1, 4)
        layout.addWidget(QLabel(self.tr("Jurisdiction"), self), 1, 0, 1, 2)
        layout.addWidget(QLabel(self.tr("Decision"), self), 1, 2)
        layout.addWidget(QLabel(self.tr("Price"), self), 1, 3)
        layout.addWidget(QLabel(self.tr("Note, printed in the report"), self), 1, 4)
        self._rows = {}
        for row, code in enumerate(TaxReport.jurisdictions, start=2):
            flag = QLabel(self)
            flag.setPixmap(JalIcon.country_flag(code).pixmap(16, 16))
            name = QLabel(JalCountry(data={'code': code}, search=True).name(), self)
            decision = QComboBox(self)
            decision.addItem(self.tr("As the report decides"))
            for kind, value in self._choices[code][1:]:
                decision.addItem(TaxOverride.label(kind, '' if value is None else value))
            price = QLineEdit(self)
            note = QLineEdit(self)
            override = next((stored[(code, x)] for x in self.KINDS if (code, x) in stored), None)
            if override is not None:
                key = (override['kind'], None if override['kind'] == TaxOverride.PricePerShare else override['value'])
                if key in self._choices[code]:
                    decision.setCurrentIndex(self._choices[code].index(key))
                    note.setText(override['note'])
                    if override['kind'] == TaxOverride.PricePerShare:
                        price.setText(override['value'])
            decision.currentIndexChanged.connect(self._validate)
            price.textChanged.connect(self._validate)
            note.textChanged.connect(self._validate)
            layout.addWidget(flag, row, 0)
            layout.addWidget(name, row, 1)
            layout.addWidget(decision, row, 2)
            layout.addWidget(price, row, 3)
            layout.addWidget(note, row, 4)
            self._rows[code] = (decision, price, note)
        layout.setColumnStretch(4, 1)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons, len(self._rows) + 2, 0, 1, 5)
        self.setMinimumWidth(720)
        self._validate()

    # True if the jurisdiction's own rule carries the exchange, so that a decision may make it a tax event
    @staticmethod
    def _carried(code: str, operation) -> bool:
        policy = TaxReport.create_report(code).basis_policy()
        if operation.type() == LedgerTransaction.CorporateAction:
            return any(policy.action_result(operation, x).basis == Basis.CARRY
                       for x in TaxOverride.exchange_results(operation))
        return policy.treatment(operation).basis == Basis.CARRY

    # Ok needs a note beside every decision and a price beside a decision that takes one; the price field is open then
    def _validate(self):
        ready = True
        for code, (decision, price, note) in self._rows.items():
            kind, _ = self._choices[code][decision.currentIndex()]
            price.setEnabled(kind == TaxOverride.PricePerShare)
            if kind is not None and not note.text().strip():
                ready = False
            if kind == TaxOverride.PricePerShare and TaxOverride.price(price.text().strip()) is None:
                ready = False
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(ready)

    def accept(self):
        for code, (decision, price, note) in self._rows.items():
            kind, value = self._choices[code][decision.currentIndex()]
            for stored_kind in self.KINDS:
                if stored_kind != kind:
                    JalTaxOverride.delete(code, self._oid, stored_kind)
            if kind is not None:
                JalTaxOverride.set(code, self._oid, kind, price.text().strip() if value is None else value, note.text())
        super().accept()
