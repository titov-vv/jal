from decimal import Decimal
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
                               QDialogButtonBox, QMessageBox)
from jal.db.asset import JalAsset
from jal.db.helpers import localize_decimal, remove_exponent
from jal.db.operations import Transfer
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.helpers import ts2dt


# ----------------------------------------------------------------------------------------------------------------------
# Pairs by hand the transfer legs that nothing could pair on its own.
#
# A transfer may be stored knowing only one of its ends, and every automatic settlement rests on something that is
# PROOF rather than a resemblance: the same transaction hash (TransferSettlement.settle_all), the address the
# transaction paid (settle_by_address), or the report of whoever routed a cross-chain move
# (ArrivalReconciler.settle_pending_transfers). What reaches this dialog is what none of them could state - a leg
# whose counterpart carries a different reference, arrived from an exchange with no statement, or moved through a
# route no source covers - and the only thing left to go on is that a send and an arrival look like each other.
#
# That is a resemblance, so it stays the user's decision: pairing two unrelated legs mis-books money exactly as badly
# as leaving both unsettled, and no amount of proximity makes it a fact. What the dialog does is make the comparison
# an honest one and refuse the pairs that cannot be transfers at all.
class TransferMatchDialog(QDialog):
    _DAY = 86400
    OID = Qt.UserRole

    def __init__(self, oid: int = 0, parent=None):
        super().__init__(parent)
        self.changed = False    # the caller rebuilds the ledger on it - settling writes real operations
        self._settlement = TransferSettlement()
        self._currency = JalAsset.get_base_currency()
        self._currency_name = JalAsset(self._currency).symbol()
        self.setWindowTitle(self.tr("Match transfer legs"))
        self.resize(1000, 500)   # two lists side by side need the width to be readable at all
        # The exact settlement runs first, and here rather than only after an import, because what it needs may have
        # appeared since: an address settles the moment an account holds it, and adding that account is precisely
        # what the user does when this list shows a leg they recognize.
        settled = self._settlement.settle_by_address()
        self.changed = settled > 0
        layout = QVBoxLayout(self)
        if settled:
            layout.addWidget(QLabel(self.tr("Settled from the address they recorded: ") + f"{settled}"))
        layout.addWidget(QLabel(self.tr("Choose a leg that was sent and the arrival it belongs to:")))
        panels = QHBoxLayout()
        self._sent_panel = self._panel(panels, self.tr("Sent — where it arrived isn't known"))
        self._arrived_panel = self._panel(panels, self.tr("Arrived — where it came from isn't known"))
        layout.addLayout(panels)
        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close, self)
        self._buttons.button(QDialogButtonBox.Ok).setText(self.tr("Match"))
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._legs = {}
        self._load(preselect=oid)
        self._sent_panel.itemSelectionChanged.connect(self._selection_changed)
        self._arrived_panel.itemSelectionChanged.connect(self._selection_changed)
        self._selection_changed()

    # One captioned list of legs, added to 'panels' as a column of its own; the list itself is what is returned.
    def _panel(self, panels: QHBoxLayout, title: str) -> QTreeWidget:
        tree = QTreeWidget(self)
        tree.setHeaderLabels([self.tr("Date"), self.tr("Account"), self.tr("Qty"), self.tr("Asset"),
                              self._currency_name, self.tr("Difference")])
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setAllColumnsShowFocus(True)
        tree.setUniformRowHeights(True)
        tree.setSelectionMode(QTreeWidget.SingleSelection)
        column = QVBoxLayout()
        column.addWidget(QLabel(title, self))
        column.addWidget(tree)
        panels.addLayout(column, 1)   # both sides are equally important, so they get equal width
        return tree

    # Every pending leg, valued as of the moment it moved. The value is computed here and stored nowhere: it is a
    # matching hint drawn from today's quote history, not a fact about the transfer (the same rule the downloaders
    # and the unsettled-transfers report follow).
    def _load(self, preselect: int = 0) -> None:
        self._legs = {}
        for leg in Transfer.pending_legs():
            record = leg.copy()
            record['value'] = leg['qty'] * leg['asset'].quote(leg['timestamp'], self._currency)[1]
            self._legs[leg['oid']] = record
        self._fill(self._sent_panel, self._of_side(Transfer.Outgoing), anchor=None)
        self._fill(self._arrived_panel, self._of_side(Transfer.Incoming), anchor=None)
        self._select(preselect)

    def _of_side(self, opart: int) -> list:
        return [x for x in self._legs.values() if x['opart'] == opart]

    # Fills one panel, best candidate first when the other panel has a leg selected to compare against. What the
    # panel had selected stays selected: re-ranking is a reaction to the OTHER panel and must not silently move the
    # choice that caused it (the signals are blocked for the same reason - the selection changes here are the
    # dialog's own doing, not the user's).
    def _fill(self, tree: QTreeWidget, legs: list, anchor) -> None:
        blocker = QSignalBlocker(tree)
        selected = self._selected_oid(tree)
        tree.clear()
        for leg, refusal in self._ranked(legs, anchor):
            item = QTreeWidgetItem([ts2dt(leg['timestamp']), leg['account'].name(),
                                    localize_decimal(remove_exponent(leg['qty'])),
                                    Transfer.leg_symbol(leg),
                                    localize_decimal(leg['value'], precision=2),
                                    self._difference(leg, anchor)])
            item.setData(0, self.OID, leg['oid'])
            tooltip = self._description(leg)
            if refusal:
                # A pair that cannot be a transfer is still shown - it may be what the user came for, and what stands
                # in the way is then what they need to know - but it is set apart from the pairs that could be made
                item.setToolTip(0, (self.tr("Not a transfer: ") + refusal + '\n' + tooltip).strip())
                font = item.font(0)
                font.setItalic(True)
                for column in range(tree.columnCount()):
                    item.setFont(column, font)
            else:
                item.setToolTip(0, tooltip)
            for column in (2, 4):
                item.setTextAlignment(column, Qt.AlignRight | Qt.AlignVCenter)
            tree.addTopLevelItem(item)
        for column in range(tree.columnCount()):
            tree.resizeColumnToContents(column)
        self._select_in(tree, selected)
        del blocker

    # Candidates as (leg, refusal), ordered by how close each is to the leg selected on the other side.
    #
    # What CANNOT be paired sinks to the bottom whatever it resembles: a leg carrying another asset, or a quantity
    # that doesn't match, is not a near miss but a different movement, and offering it first would be offering the
    # user a mistake. The rest are ordered by proximity, where time alone is not the measure (a move may take minutes
    # or a day) and value alone is not either - the two together are, weighed on a scale that says so: one day apart
    # counts as much as one per cent apart in value. A leg with no quote to compare states no value gap and is ranked
    # on time alone, after the legs that could be compared on both.
    def _ranked(self, legs: list, anchor) -> list:
        if anchor is None:
            return [(leg, '') for leg in sorted(legs, key=lambda x: (x['timestamp'], x['oid']))]
        def score(leg):
            gap = self._value_gap(leg, anchor)
            return (gap is None, abs(leg['timestamp'] - anchor['timestamp']) / self._DAY + (gap if gap else 0))
        candidates = [(leg, self._refusal_between(leg, anchor)) for leg in legs]
        return sorted(candidates, key=lambda x: (bool(x[1]), score(x[0]), x[0]['oid']))

    # Why this candidate and the leg selected on the other side could not be made one transfer, or '' when they could.
    # What is asked for is what the user cannot overrule (override=True): a pair whose two moments merely disagree is
    # matchable - it is confirmed rather than refused (see accept()) - and ranking it with the impossible ones would
    # bury exactly the pair that needs the user's judgement.
    def _refusal_between(self, leg, anchor) -> str:
        sending, arriving = (leg, anchor) if leg['opart'] == Transfer.Outgoing else (anchor, leg)
        return self._settlement.refusal_for(sending['oid'], arriving['oid'], override=True)

    # The difference between the two values in per cent of the larger one, or None when either of them has no quote
    @staticmethod
    def _value_gap(leg, anchor):
        biggest = max(abs(leg['value']), abs(anchor['value']))
        if not biggest:
            return None
        return float(abs(leg['value'] - anchor['value']) * Decimal('100') / biggest)

    # How far a candidate is from the leg selected on the other side, as the pair of gaps it is ranked on
    def _difference(self, leg, anchor) -> str:
        if anchor is None:
            return ''
        gap = self._value_gap(leg, anchor)
        elapsed = (leg['timestamp'] - anchor['timestamp']) / self._DAY
        difference = f"{elapsed:+.1f} " + self.tr("days")
        return difference if gap is None else difference + f", {gap:.2f}%"

    def _description(self, leg) -> str:
        parts = [self.tr("Reference: ") + leg['number'] if leg['number'] else '',
                 self.tr("Counterparty address: ") + leg['address'] if leg['address'] else '',
                 leg['note'] if leg['note'] else '']
        return '\n'.join(x for x in parts if x)

    # ------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _selected_oid(tree: QTreeWidget) -> int:
        items = tree.selectedItems()
        return items[0].data(0, TransferMatchDialog.OID) if items else 0

    @staticmethod
    def _select_in(tree: QTreeWidget, oid: int) -> None:
        for i in range(tree.topLevelItemCount()):
            if tree.topLevelItem(i).data(0, TransferMatchDialog.OID) == oid:
                tree.setCurrentItem(tree.topLevelItem(i))
                return

    def _select(self, oid: int) -> None:
        if oid in self._legs:
            self._select_in(self._sent_panel if self._legs[oid]['opart'] == Transfer.Outgoing else self._arrived_panel,
                            oid)

    # Re-ranks each panel against the leg selected in the other one and says what the current pair would do.
    def _selection_changed(self) -> None:
        sent, arrived = self._selected_oid(self._sent_panel), self._selected_oid(self._arrived_panel)
        for tree, legs, anchor in ((self._sent_panel, self._of_side(Transfer.Outgoing), self._legs.get(arrived)),
                                   (self._arrived_panel, self._of_side(Transfer.Incoming), self._legs.get(sent))):
            self._fill(tree, legs, anchor)
        refusal = self._settlement.refusal_for(sent, arrived, override=True) if sent and arrived else ''
        # The moment the pair would be stamped with, which is set only when the two legs disagree about when the
        # movement happened. Matching is still offered - the two sources of one movement never share a clock, and the
        # user is the one who knows whether these are that movement - but what it does to the dates is said first.
        moment = self._settlement.agreed_moment_for(sent, arrived) if sent and arrived and not refusal else 0
        if not sent or not arrived:
            self._status.setText(self.tr("Select one leg on each side."))
        elif refusal:
            self._status.setText(self.tr("These two are not the two ends of one transfer: ") + refusal)
        elif moment:
            self._status.setText(self.tr("These two disagree about when it happened - the arrival is dated before the "
                                         "departure. Matching stamps both ends with ") + ts2dt(moment) + ": "
                                 + self._pair_text(sent, arrived))
        else:
            self._status.setText(self.tr("Matching makes these one transfer: ") + self._pair_text(sent, arrived))
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(bool(sent and arrived and not refusal))

    def _pair_text(self, sending_oid: int, arriving_oid: int) -> str:
        sent, arrived = self._legs[sending_oid], self._legs[arriving_oid]
        return f"{remove_exponent(sent['qty'])} {Transfer.leg_symbol(sent)} " \
               + sent['account'].name() + " -> " + arrived['account'].name()

    def accept(self):
        sending_oid, arriving_oid = self._selected_oid(self._sent_panel), self._selected_oid(self._arrived_panel)
        if not sending_oid or not arriving_oid:
            return
        # An arrival dated before its departure is the one thing about a pair the user may overrule, and this is where
        # they do it: the two moments come from two different clocks (an exchange's books and a chain's block), so
        # their order is evidence about the sources rather than about the movement. What it costs is that both ends
        # lose the moment their own source stated, and that is what is confirmed here rather than done quietly.
        moment = self._settlement.agreed_moment_for(sending_oid, arriving_oid)
        if moment and QMessageBox().warning(
                self, self.tr("Legs disagree about the time"),
                self.tr("The arrival is dated before the departure, so the two sources disagree about when this "
                        "movement happened.\n\nMatch them anyway and stamp both ends with ") + ts2dt(moment) + "?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        refusal = self._settlement.settle_linked(sending_oid, arriving_oid, override=True)
        if refusal:
            QMessageBox().warning(self, self.tr("Legs are not matched"), refusal)
            self._load()
            self._selection_changed()
            return
        self.changed = True
        super().accept()
