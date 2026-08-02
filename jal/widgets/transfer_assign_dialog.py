from decimal import Decimal
from PySide6.QtCore import Qt, QDateTime, QTimeZone
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QDateTimeEdit, QGroupBox,
                               QDialogButtonBox, QMessageBox, QPushButton)
from jal.constants import CustomColor, PredefinedAccountType, AssetLocation
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.db.common_models import AccountListModel
from jal.db.cost_basis import carried_basis, STALE_RATE_LIMIT
from jal.db.helpers import localize_decimal, delocalize_decimal, remove_exponent
from jal.db.operations import Transfer
from jal.db.transfer_settlement import TransferSettlement
from jal.net.chain_fetchers.protocols import protocol_names
from jal.widgets.helpers import ts2d, ts2dt
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.reference_selector import ReferenceSelectorWidget
from jal.widgets.staking_dialogs import NewStakingBoxDialog


# ----------------------------------------------------------------------------------------------------------------------
# Names the account at the end a transfer leg doesn't know.
#
# Every other way of settling a leg rests on something recorded: the transaction both ends name, the address the
# movement paid, the report of whoever routed it, or the second record of the same movement that the matcher pairs it
# with. This is for the leg where none of that exists and none of it ever will - a centralized exchange whose
# statement gives neither an address nor a transaction hash states nothing that can be matched, so the wallet on the
# other side holds the only record the movement will ever have. What the missing end is, then, only the user knows.
#
# Because it is an assertion rather than a deduction, the dialog's work is to show what the assertion would DO before
# it is made, and to refuse the ones that cannot be true: an account that never held the asset doesn't merely take
# the money from the wrong place, it stops the ledger rebuild dead (see TransferSettlement._refusal_to_supply).
#
# The cost basis is the other half of the same job. An asset that crosses between accounts kept in different
# currencies has to have what it cost restated in the currency it arrives in, and nothing that records a transfer
# knows that number - left empty it becomes a zero, and the asset is taxed as though it had been free. So it is
# computed here from what the sending account paid and the rate of the day, shown together with the age of that rate,
# and left editable: the computation is a starting point offered to the user, never an answer written behind them.
#
# 'staking' switches the account being asked for to a STAKING BOX - the container an asset was staked into, which is
# an account of a hidden type and so is missing from the ordinary chooser by design. Nothing else about the
# assignment changes: a box is an account, what moves into it is a transfer, and every refusal and every cost-basis
# rule below applies to it word for word. What the mode adds is a way to create the box on the spot, prefilled from
# the leg being settled - a position is nearly always met for the first time exactly here.
class TransferAssignDialog(QDialog):
    def __init__(self, oid: int = 0, parent=None, staking: bool = False):
        super().__init__(parent)
        self.changed = False    # the caller rebuilds the ledger on it - an assignment writes a real operation
        self._oid = oid
        self._settlement = TransferSettlement()
        self._leg = self._pending_leg(oid)
        self._user_typed = False    # a number the user has entered is theirs and is never recomputed over
        self._refusal = ''          # why the chosen account can't be that end, '' when it can - see _choice_changed()
        # Whether a number is being asked for at all. Kept here rather than read back from the widget: a widget of a
        # dialog that hasn't been shown yet reports itself invisible whatever it was told, and the Ok button is
        # decided before the dialog is shown.
        self._amount_shown = False
        self.setWindowTitle(self.tr("Assign a staked position") if staking else self.tr("Assign an account"))
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        self._description = QLabel(self._leg_description())
        self._description.setWordWrap(True)
        layout.addWidget(self._description)

        form = QGridLayout()
        form.addWidget(QLabel(self.tr("Arrived at:") if self._sending() else self.tr("Sent from:")), 0, 0)
        self._account = ReferenceSelectorWidget(self)
        # A staking box is hidden from every picker, so the chooser is asked for the hidden types and then narrowed
        # to that one: the box is what this mode assigns to, and a deposit box is not something a chain movement
        # ever ends in.
        self._account_model = AccountListModel(self, include_hidden=staking)
        self._account_dialog = AccountListDialog(self, include_hidden=staking)
        if staking:
            self._narrow_to_boxes()
            # The list the "..." button opens is a model of its own, and it rebuilds its filter from its own search
            # and grouping state on every open - so the narrowing has to go through the one condition that survives
            # that (see ReferenceDataDialog.setFilter), not through a filter set once here.
            self._account_dialog.filter_field = "accounts.account_type"
            self._account_dialog.setFilterValue(PredefinedAccountType.Staking)
        self._account.setup_selector(self._account_model, self._account_dialog)
        form.addWidget(self._account, 0, 1)
        self._account_currency = QLabel()
        form.addWidget(self._account_currency, 0, 2)
        if staking:
            self._new_box = QPushButton(self.tr("New..."), self)
            self._new_box.setToolTip(self.tr("Create the staked position this leg goes into"))
            self._new_box.pressed.connect(self._create_box)
            form.addWidget(self._new_box, 0, 3)
        form.addWidget(QLabel(self.tr("on:")), 1, 0)
        self._timestamp = QDateTimeEdit(self)
        self._timestamp.setTimeSpec(Qt.UTC)
        self._timestamp.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self._timestamp.setCalendarPopup(True)
        form.addWidget(self._timestamp, 1, 1)
        form.setColumnStretch(1, 1)
        layout.addLayout(form)

        self._amount_box = QGroupBox(self.tr("Cost basis"), self)
        basis = QGridLayout(self._amount_box)
        self._paid_label = QLabel()
        basis.addWidget(self._paid_label, 0, 0, 1, 3)
        self._rate_label = QLabel()
        self._rate_label.setWordWrap(True)
        basis.addWidget(self._rate_label, 1, 0, 1, 3)
        self._amount_label = QLabel(self.tr("Value to record:"))
        basis.addWidget(self._amount_label, 2, 0)
        self._amount = QLineEdit(self)
        self._amount.textEdited.connect(self._amount_typed)
        basis.addWidget(self._amount, 2, 1)
        self._amount_currency = QLabel()
        basis.addWidget(self._amount_currency, 2, 2)
        basis.setColumnStretch(1, 1)
        layout.addWidget(self._amount_box)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close, self)
        self._buttons.button(QDialogButtonBox.Ok).setText(self.tr("Assign"))
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._load()
        # Every way the USER can change the selector emits this; setting the property from code does not (its setter
        # has no emit of its own, whatever the property declares as its notify signal). That suits both callers here:
        # the account suggested below is put in place before this connection is made, and _choice_changed() is called
        # once at the end anyway.
        self._account.changed.connect(self._choice_changed)
        self._timestamp.dateTimeChanged.connect(lambda _datetime: self._choice_changed())
        self._choice_changed()

    # The leg being assigned, taken from the same list the report shows, or None when it isn't pending any more
    def _pending_leg(self, oid: int):
        return next((leg for leg in Transfer.pending_legs() if leg['oid'] == oid), None)

    # True when the money left a known account and where it went is unknown; False when it arrived and where from is
    def _sending(self) -> bool:
        return self._leg is not None and self._leg['opart'] == Transfer.Outgoing

    def _leg_description(self) -> str:
        if self._leg is None:
            return self.tr("This transfer is not waiting for an account any more.")
        leg = self._leg
        known = leg['account'].name()
        moved = f"{remove_exponent(leg['qty'])} {Transfer.leg_symbol(leg)}"
        if self._sending():
            what = self.tr("{} left {} on {} and where it arrived isn't known.")
        else:
            what = self.tr("{} arrived at {} on {} and where it was sent from isn't known.")
        text = what.format(moved, known, ts2dt(leg['timestamp']))
        details = [self.tr("Reference: ") + leg['number'] if leg['number'] else '',
                   self.tr("Counterparty address: ") + leg['address'] if leg['address'] else '',
                   leg['note'] if leg['note'] else '']
        return '\n'.join([text] + [x for x in details if x])

    def _load(self) -> None:
        if self._leg is None:
            self._account.setEnabled(False)
            self._timestamp.setEnabled(False)
            self._amount_box.setVisible(False)
            return
        # The address a chain fetch recorded may already name an account of the user's - see
        # TransferSettlement.address_suggestion(). It is offered as the choice rather than made silently: the chain
        # an address is resolved on is itself a deduction when the end that IS known is not a wallet.
        self._account.selected_id = self._settlement.address_suggestion(self._oid)
        # Both ends of a fetched movement carry the same moment, and one of them is all that is known here
        self._timestamp.setDateTime(QDateTime.fromSecsSinceEpoch(self._leg['timestamp'], QTimeZone(0)))

    # ------------------------------------------------------------------------------------------------------------------
    # Creates the staked position this leg goes into and chooses it, prefilled with everything the leg already says:
    # the protocol named in the description a custody import wrote, the chain the movement happened on and the
    # address the asset went to (or came from). The address is the part that matters beyond this one dialog - a box
    # that holds it settles every further stake and unstake by itself.
    def _create_box(self) -> None:
        if self._leg is None:
            return
        dialog = NewStakingBoxDialog(self._leg['account'], protocol=self._protocol_of(self._leg),
                                     chain=self._chain_of(self._leg), address=self._leg['address'] or '', parent=self)
        if not dialog.exec():
            return
        self._narrow_to_boxes()   # setting a filter re-selects the model, which is what makes the new box show up
        self._account.selected_id = dialog.box.id()
        self._choice_changed()    # setting the selector from code emits nothing, so the choice is re-read by hand

    # Both models the selector reads - the list it shows and the plain one its name field completes on - narrowed to
    # staking boxes alone
    def _narrow_to_boxes(self) -> None:
        box_only = f"accounts.account_type={PredefinedAccountType.Staking}"
        self._account_model.setFilter(box_only)
        self._account_model.completion_model.setFilter(box_only)

    # The protocol a custody import named in the leg's description, or '' when it named none. The registry's own
    # names are matched rather than the sentence around them: that sentence is translated and differs between the
    # two ends of one movement, while the name is data and is written the same way everywhere (see protocol_names).
    @staticmethod
    def _protocol_of(leg: dict) -> str:
        note = leg['note'] if leg['note'] else ''
        return next((name for name in protocol_names() if name in note), '')

    # The chain the leg moved on: the one the known end tracks, or - when that end is not a wallet at all - the one
    # the moved asset is listed on. It is the same question TransferSettlement._chain_of answers about an address.
    @staticmethod
    def _chain_of(leg: dict) -> int:
        chain = leg['account'].chain()
        if chain:
            return chain
        return JalSymbol(leg['symbol']).location() if leg['symbol'] else AssetLocation.UNDEFINED

    def _amount_typed(self, _text: str) -> None:
        self._user_typed = True
        self._update_ok_button()

    # Re-reads the choice, says what it would do and offers the value it would record
    def _choice_changed(self) -> None:
        if self._leg is None:
            self._status.setText(self.tr("This transfer is not waiting for an account any more."))
            self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        account_id = self._account.selected_id
        timestamp = self._timestamp.dateTime().toSecsSinceEpoch()
        self._account_currency.setText(JalAsset(JalAccount(account_id).currency()).symbol() if account_id else '')
        self._update_amount(account_id, timestamp)
        self._refusal = self._settlement.refusal_for_assignment(self._oid, account_id, timestamp)
        if not account_id:
            self._status.setText(self.tr("Choose the account at the end that is missing."))
        elif self._refusal:
            self._status.setText(self.tr("This account can't be that end: ") + self._refusal)
        else:
            self._status.setText(self.tr("Assigning makes this one transfer: ") + self._pair_text(account_id))
        self._update_ok_button()

    # What the assignment still lacks, decided again whenever any part of it changes. The refusal is remembered from
    # the last time the choice was read rather than asked for here: it is a query over the ledger, and this is called
    # on every keystroke in the value field, which cannot change it.
    def _update_ok_button(self) -> None:
        allowed = bool(self._account.selected_id) and not self._refusal and not self._amount_missing()
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(allowed)

    def _pair_text(self, account_id: int) -> str:
        moved = f"{remove_exponent(self._leg['qty'])} {self._leg['asset'].symbol()} "
        names = (self._leg['account'].name(), JalAccount(account_id).name())
        return moved + " -> ".join(names if self._sending() else reversed(names))

    # ------------------------------------------------------------------------------------------------------------------
    # Which account sends and which receives, once the missing one has been chosen. The cost basis is what the SENDING
    # account paid, restated in the currency of the one that RECEIVES - so which is which decides the whole sum.
    def _ends(self, account_id: int):
        chosen = JalAccount(account_id)
        return (self._leg['account'], chosen) if self._sending() else (chosen, self._leg['account'])

    # Whether the assignment has to state a number at all.
    #
    # An asset transfer moves one quantity and states it once; its 'deposit' is a cost basis that is read only when
    # the two accounts are kept in different currencies (see Transfer.processAssetTransfer), so with one currency at
    # both ends there is nothing to ask about. A money transfer converts, so each end states its own amount and the
    # end being filled in has none yet.
    def _amount_needed(self, account_id: int) -> bool:
        if not account_id:
            return False
        if self._leg['symbol'] is None:
            return True
        source, destination = self._ends(account_id)
        return source.currency() != destination.currency()

    def _amount_missing(self) -> bool:
        return self._amount_shown and not self._amount.text().strip()

    def _update_amount(self, account_id: int, timestamp: int) -> None:
        needed = self._amount_needed(account_id)
        self._amount_shown = needed
        self._amount_box.setVisible(needed)
        if not needed:
            return
        if self._leg['symbol'] is None:
            self._show_money_amount(account_id, timestamp)
        else:
            self._show_cost_basis(account_id, timestamp)

    # A money transfer converts what left into what arrived, so the end being filled in states its own amount. There
    # is no cost basis in it at all - what is offered is simply the other end's amount at the rate of the day.
    def _show_money_amount(self, account_id: int, timestamp: int) -> None:
        self._amount_box.setTitle(self.tr("Amount"))
        self._amount_label.setText(self.tr("Amount at this end:"))
        known, chosen = self._leg['account'], JalAccount(account_id)
        self._amount_currency.setText(JalAsset(chosen.currency()).symbol())
        self._paid_label.setText(self.tr("The other end of this transfer states ")
                                 + f"{remove_exponent(self._leg['qty'])} {JalAsset(known.currency()).symbol()}")
        rate_timestamp, rate = JalAsset(known.currency()).quote(timestamp, chosen.currency())
        self._show_rate(known.currency(), chosen.currency(), rate, rate_timestamp, timestamp)
        self._offer(self._leg['qty'] * rate, bool(rate_timestamp))

    # What the asset cost the account that sends it, restated in the currency of the account that receives it.
    def _show_cost_basis(self, account_id: int, timestamp: int) -> None:
        self._amount_box.setTitle(self.tr("Cost basis"))
        self._amount_label.setText(self.tr("Cost basis to record:"))
        source, destination = self._ends(account_id)
        departure = self._leg['timestamp'] if self._sending() else timestamp
        self._amount_currency.setText(JalAsset(destination.currency()).symbol())
        basis = carried_basis(source, self._leg['asset'], self._leg['qty'], departure, destination.currency())
        paid = localize_decimal(basis['basis'], precision=2) + ' ' + JalAsset(basis['currency']).symbol()
        if basis['short'] > Decimal('0'):
            # The refusal above already says this account can't have sent it; here is what is actually there
            self._paid_label.setText(self.tr("{} holds only {} of this asset - it can't have sent {}.").format(
                source.name(), remove_exponent(basis['qty']), remove_exponent(self._leg['qty'])))
        else:
            self._paid_label.setText(self.tr("{} paid {} for it, over {} lot(s).").format(
                source.name(), paid, basis['lots']))
        self._show_rate(basis['currency'], destination.currency(), basis['rate'], basis['rate_timestamp'], departure)
        self._offer(basis['value'], basis['complete'] and basis['short'] == Decimal('0'))

    # The rate the restatement rests on, always with the day it is FROM. JalAsset.quote() answers with the newest
    # rate at or before the date asked about and says nothing about how old it is, so a rate from a series that ended
    # years ago looks exactly like today's unless its own date is shown - which is the whole reason this line exists.
    def _show_rate(self, source_currency: int, target_currency: int, rate: Decimal, rate_timestamp: int,
                   timestamp: int) -> None:
        if source_currency == target_currency:
            self._rate_label.setText('')
            return
        pair = f"{JalAsset(source_currency).symbol()} -> {JalAsset(target_currency).symbol()}"
        if not rate_timestamp:
            doubtful = True
            text = self.tr("No {} rate is stored for that date, so the value has to be entered by hand "
                           "(rates are loaded from the Data menu).").format(pair)
        else:
            doubtful = (timestamp - rate_timestamp) > STALE_RATE_LIMIT
            text = self.tr("Rate {}: {}, as of {}").format(pair, localize_decimal(rate), ts2d(rate_timestamp))
            if doubtful:
                text += self.tr(" - the newest one stored, and it is not of that date")
        palette = QPalette()
        if doubtful:
            palette.setColor(QPalette.WindowText, CustomColor.DarkRed)
        self._rate_label.setPalette(palette)
        self._rate_label.setText(text)

    # Puts the computed value in front of the user, unless they have entered one of their own - what they typed is
    # their statement about the transfer and nothing here overrules it.
    def _offer(self, value: Decimal, usable: bool) -> None:
        if self._user_typed:
            return
        self._amount.setText(localize_decimal(value, precision=2) if usable else '')

    # ------------------------------------------------------------------------------------------------------------------
    def accept(self):
        account_id = self._account.selected_id
        timestamp = self._timestamp.dateTime().toSecsSinceEpoch()
        amount = delocalize_decimal(self._amount.text()) if self._amount_shown else Decimal('0')
        if self._amount_shown and amount == Decimal('0'):
            if QMessageBox().warning(self, self.tr("No value is stated"),
                                     self.tr("The asset will open at a cost basis of zero, and everything it is sold "
                                             "for later will count as gain. Assign it anyway?"),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No:
                return
        refusal = self._settlement.assign_end(self._oid, account_id, timestamp, amount)
        if refusal:
            QMessageBox().warning(self, self.tr("The account is not assigned"), refusal)
            self._leg = self._pending_leg(self._oid)
            self._choice_changed()
            return
        self.changed = True
        super().accept()
