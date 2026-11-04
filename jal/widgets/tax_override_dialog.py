from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QLabel, QComboBox, QLineEdit

from jal.db.country import JalCountry
from jal.db.operations import LedgerTransaction
from jal.db.tax_override import JalTaxOverride, TaxOverride
from jal.data_export.taxes import TaxReport
from jal.widgets.icons import JalIcon
from jal.widgets.helpers import ts2dt


# ----------------------------------------------------------------------------------------------------------------------
# The user's decision on how each jurisdiction's tax report treats one operation: one row per jurisdiction, a decision
# and the note the report prints with it. Ok writes the rows; a row without a decision removes its overrides.
class TaxOverrideDialog(QDialog):
    KINDS = (TaxOverride.NotTaxEvent, TaxOverride.Treaty, TaxOverride.AssetSource)   # one of them per jurisdiction

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
        stored = {(x['jurisdiction'], x['kind']): x for x in JalTaxOverride.for_operation(oid)}
        self.setWindowTitle(self.tr("Tax treatment"))
        layout = QGridLayout(self)
        heading = f"{ts2dt(operation.timestamp(), operation.timestamp_is_day())}  {operation.name()}\n" \
                  f"{operation.account_name()}  {operation.asset_name()}"
        layout.addWidget(QLabel(heading.strip(), self), 0, 0, 1, 4)
        layout.addWidget(QLabel(self.tr("Jurisdiction"), self), 1, 0, 1, 2)
        layout.addWidget(QLabel(self.tr("Decision"), self), 1, 2)
        layout.addWidget(QLabel(self.tr("Note, printed in the report"), self), 1, 3)
        self._rows = {}
        for row, code in enumerate(TaxReport.jurisdictions, start=2):
            flag = QLabel(self)
            flag.setPixmap(JalIcon.country_flag(code).pixmap(16, 16))
            name = QLabel(JalCountry(data={'code': code}, search=True).name(), self)
            decision = QComboBox(self)
            decision.addItem(self.tr("As the report decides"))
            for kind, value in self._choices[code][1:]:
                decision.addItem(TaxOverride.label(kind, value))
            note = QLineEdit(self)
            override = next((stored[(code, x)] for x in self.KINDS if (code, x) in stored), None)
            if override is not None and (override['kind'], override['value']) in self._choices[code]:
                decision.setCurrentIndex(self._choices[code].index((override['kind'], override['value'])))
                note.setText(override['note'])
            decision.currentIndexChanged.connect(self._validate)
            note.textChanged.connect(self._validate)
            layout.addWidget(flag, row, 0)
            layout.addWidget(name, row, 1)
            layout.addWidget(decision, row, 2)
            layout.addWidget(note, row, 3)
            self._rows[code] = (decision, note)
        layout.setColumnStretch(3, 1)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons, len(self._rows) + 2, 0, 1, 4)
        self.setMinimumWidth(600)
        self._validate()

    # Ok needs a note beside every decision
    def _validate(self):
        ready = all(decision.currentIndex() == 0 or note.text().strip() for decision, note in self._rows.values())
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(ready)

    def accept(self):
        for code, (decision, note) in self._rows.items():
            kind, value = self._choices[code][decision.currentIndex()]
            for stored_kind in self.KINDS:
                if stored_kind != kind:
                    JalTaxOverride.delete(code, self._oid, stored_kind)
            if kind is not None:
                JalTaxOverride.set(code, self._oid, kind, value, note.text())
        super().accept()
