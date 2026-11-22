from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import QComboBox, QProgressDialog
from jal.db.tag import JalTag
from jal.db.portfolio import JalPortfolio, PortfolioLots


# ----------------------------------------------------------------------------------------------------------------------
# Report filter by portfolio: "All", every tag that holds an assignment, and "Unassigned"
class PortfolioCombo(QComboBox):
    All = -1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setToolTip(self.tr("Portfolio figures are for management only, tax reports are unaffected"))
        self.refresh()

    # Re-reads the portfolios in use, keeping the current choice when it is still there
    def refresh(self):
        current = self.selected()
        self.blockSignals(True)
        self.clear()
        self.addItem(self.tr("All"), self.All)
        tags = sorted([JalTag(x) for x in set(JalPortfolio.assignments().values())], key=lambda x: x.name())
        for tag in tags:
            self.addItem(tag.name(), tag.id())
        self.addItem(self.tr("Unassigned"), JalPortfolio.Unassigned)
        self.setCurrentIndex(max(self.findData(self.All if current is None else current), 0))
        self.blockSignals(False)

    def showPopup(self):
        self.refresh()
        super().showPopup()

    # The chosen portfolio's tag id, JalPortfolio.Unassigned, or None for all of them
    def selected(self):
        return None if self.currentData() in (None, self.All) else self.currentData()

    # Runs the portfolio replay when it is due, behind a progress dialog
    @staticmethod
    def prepare_lots(parent):
        if not PortfolioLots.needs_replay():
            return
        dialog = QProgressDialog(QCoreApplication.translate("PortfolioCombo", "Replaying lots by portfolio…"),
                                 None, 0, 100, parent)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        try:
            PortfolioLots.prepare(lambda done, total: dialog.setValue(100 * done // total if total else 100))
        finally:
            dialog.close()
