import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest
from PySide6.QtCore import Qt, QDate, QModelIndex
from PySide6.QtWidgets import QWidget, QMessageBox, QDialogButtonBox

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_quotes, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedAccountType, PredefinedCategory, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.db import JalDB
from jal.db.symbol import JalSymbol
from jal.db.operations import AssetPayment, LedgerTransaction, Transfer
from jal.db.ledger import Ledger
from jal.db.pending_transfers_model import PendingTransfersModel
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter
from jal.widgets.bridge_convert_dialog import BridgeConvertDialog
from jal.widgets.swap_convert_dialog import SwapConvertDialog
from jal.reports.reports import Reports
from jal.reports.unsettled_transfers import UnsettledTransfersReportWindow
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.transfer_assign_dialog import TransferAssignDialog
from jal.widgets.transfer_match_dialog import TransferMatchDialog

# ----------------------------------------------------------------------------------------------------------------------
# A transfer may be recorded knowing only one of its two ends. The report of those legs is the safety net of that
# model: the one failure mode it introduces is legs accumulating unnoticed, and this is where they are noticed.

USDT = 4                       # the asset created by the fixture below
WALLET_A, WALLET_B = 1, 2
USD, EUR = 2, 3


@pytest.fixture
def wallets(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='ARB wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=USD, number='', name='ETH wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '2' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_assets([('USDT', 'Tether USD', '', USD, PredefinedAsset.Crypto, 0)])   # ID = USDT
    yield


def _transfer(from_account, to_account, amount, timestamp, asset_id=USDT, deposit=None, number='', address=None,
              symbol_id=None):
    deposit = amount if deposit is None else deposit
    if symbol_id is None:
        symbol_id = symbol_id_for(asset_id) if asset_id else None
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
            'deposit_timestamp': timestamp, 'deposit_account': to_account, 'deposit': str(deposit),
            'number': number, 'counterparty_address': address, 'symbol_id': symbol_id}
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


# ----------------------------------------------------------------------------------------------------------------------
# The source of the list: 'transfers' rows with a NULL account, read with no ledger involved

def test_pending_legs_reports_each_open_leg_from_the_side_that_is_known(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number='0xsent')
    _transfer(None, WALLET_B, 150, d2t(210104), number='0xarrived')

    legs = Transfer.pending_legs()

    assert len(legs) == 2
    sent, arrived = legs                                    # ordered by the date of the leg that exists
    assert sent['opart'] == Transfer.Outgoing
    assert sent['account'].id() == WALLET_A and sent['qty'] == Decimal('400') and sent['number'] == '0xsent'
    assert arrived['opart'] == Transfer.Incoming
    assert arrived['account'].id() == WALLET_B and arrived['qty'] == Decimal('150')


def test_pending_legs_ignores_a_settled_transfer(wallets):
    _transfer(WALLET_A, WALLET_B, 400, d2t(210103))

    assert Transfer.pending_legs() == []


# The report is asked "what was unsettled on this date", so a leg that only appears later is not in the answer.
# Note that it is the date of the leg that EXISTS that decides - the absent side has no date of its own.
def test_pending_legs_are_bounded_by_the_date_asked_about(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 150, d2t(210204))

    assert len(Transfer.pending_legs(d2t(210103))) == 1
    assert len(Transfer.pending_legs(d2t(210201))) == 1
    assert len(Transfer.pending_legs(d2t(210204))) == 2


# An asset transfer carries the moved quantity in 'withdrawal' on BOTH legs, while a money transfer may convert
# currency and so states each side separately - the arriving side of a money leg is its own amount.
def test_pending_legs_take_the_quantity_from_the_right_side(wallets):
    _transfer(None, WALLET_B, 400, d2t(210103), deposit=0)                      # asset: cost basis unknown, qty 400
    _transfer(None, WALLET_B, 1000, d2t(210104), asset_id=None, deposit=900)    # money: 900 arrived

    legs = Transfer.pending_legs()
    assert legs[0]['qty'] == Decimal('400') and legs[0]['asset'].id() == USDT
    assert legs[1]['qty'] == Decimal('900') and legs[1]['asset'].id() == USD    # money moves the account currency


# ----------------------------------------------------------------------------------------------------------------------
# The report itself

def _model(currency_id=USD, with_basis_gaps=False):
    view = TreeViewWithFooter(QWidget())
    model = PendingTransfersModel(view)
    view.setModel(model)
    model.updateView(currency_id=currency_id, date=QDate.fromString('01/03/2021', 'dd/MM/yyyy'),
                     with_basis_gaps=with_basis_gaps)
    return model


def _column(model, name):
    return model.fieldIndex(name)


def _rows(model) -> int:
    return model.rowCount(QModelIndex())


def _row(model, row, name):
    return model.data(model.index(row, _column(model, name), QModelIndex()))


# Money that was sent and reached no account is invisible in every per-account balance - it belongs to none. This
# report is the only place it is counted, so its value is the point of the whole thing.
def test_sent_leg_is_counted_as_money_in_transit(wallets):
    create_quotes(USDT, USD, [(d2t(210101), 1.05)])
    _transfer(WALLET_A, None, 400, d2t(210103), number='0xsent')

    model = _model()

    assert _rows(model) == 1
    assert _row(model, 0, 'from') == 'ARB wallet'
    assert _row(model, 0, 'to') == '(unknown)'
    assert _row(model, 0, 'qty') == Decimal('400')
    assert _row(model, 0, 'value') == Decimal('420')          # 400 @ 1.05, valued at read time
    assert _row(model, 0, 'number') == '0xsent'


# An arriving leg has already landed: it is counted in the account it reached, so counting it here as well would
# double it. It is listed - the list has to be complete - but adds nothing to the money in flight.
def test_arrived_leg_is_listed_but_adds_no_value(wallets):
    create_quotes(USDT, USD, [(d2t(210101), 1.05)])
    _transfer(None, WALLET_B, 150, d2t(210104))

    model = _model()

    assert _rows(model) == 1
    assert _row(model, 0, 'from') == '(unknown)'
    assert _row(model, 0, 'to') == 'ETH wallet'
    assert _row(model, 0, 'qty') == Decimal('150')            # the quantity is still shown ...
    assert _row(model, 0, 'value') == Decimal('0')            # ... but it is not in transit


def test_total_is_the_money_actually_in_flight(wallets):
    create_quotes(USDT, USD, [(d2t(210101), 1.05)])
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 150, d2t(210104))
    _transfer(WALLET_A, WALLET_B, 999, d2t(210105))           # settled - not in the list at all

    model = _model()

    assert _rows(model) == 2
    assert model._root.details()['value'] == Decimal('420')   # the sent leg only
    assert model.footerData(_column(model, 'value')) == '420.00'


# Values are computed at read time from the quotes of the report date - nothing derived is stored, so the same leg
# is worth what the report currency says it is worth today.
def test_value_follows_the_report_currency(wallets):
    create_quotes(USDT, USD, [(d2t(210101), 1.05)])
    create_quotes(USD, EUR, [(d2t(210101), 0.5)])
    _transfer(WALLET_A, None, 400, d2t(210103))

    assert _row(_model(currency_id=USD), 0, 'value') == Decimal('420')
    assert _row(_model(currency_id=EUR), 0, 'value') == Decimal('210')


# The window is discovered by the report loader, so it appears in the Reports menu
def test_report_is_registered(prepare_db):
    reports = Reports(None, None)
    assert "UnsettledTransfersReportWindow" in [x['window_class'] for x in reports.items]


def test_report_window_builds(wallets):
    create_quotes(USDT, USD, [(d2t(210101), 1.05)])
    _transfer(WALLET_A, None, 400, d2t(210103))

    window = UnsettledTransfersReportWindow(Reports(None, None))

    assert window.ui.ReportTreeView.model().rowCount(QModelIndex()) == 1


# The desired state of this report is EMPTY - every leg settled - so that is the state it is most often looked at
# and saved in. Asking a tree model for an index that isn't there must give an INVALID QModelIndex, not None: None
# has no isValid(), and feeding it back into hasIndex() raises instead of simply being invalid. The same applies to
# the parent argument, whose default was None (so any index(row, column) call raised).
def test_missing_index_is_invalid_not_none(wallets, tmp_path):
    from jal.data_export.xlsx import XLSX

    model = _model()
    assert _rows(model) == 0
    assert model.index(0, 0, QModelIndex()).isValid() is False   # no rows: an index that isn't there
    assert model.index(0, 0).isValid() is False                  # ... and no parent given at all

    report = XLSX(str(tmp_path / 'unsettled.xlsx'))               # an empty report still saves
    report.output_model("Unsettled transfers", model)
    report.save()
    assert (tmp_path / 'unsettled.xlsx').exists()


# ----------------------------------------------------------------------------------------------------------------------
# The list holds rows that are settled in different ways, and each says which kind it is - the report is read as the
# few groups it is (each carrying its own background) rather than as one undifferentiated worklist.

EUR_ADDRESS = '0x' + '3' * 40


def _eur_wallet(name='EUR wallet', address=EUR_ADDRESS):
    return JalAccountCreator(currency_id=EUR, number='', name=name, investing=1, organization=1,
                             account_type=PredefinedAccountType.Wallet, address=address,
                             chain=AssetLocation.ARB_BLOCKCHAIN).commit()


def _background(model, row):
    return model.data(model.index(row, 0, QModelIndex()), Qt.BackgroundRole).color()


def test_each_kind_of_row_says_which_it_is(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 150, d2t(210104))

    model = _model()

    assert model.transfer_kind(model.index(0, 0, QModelIndex())) == PendingTransfersModel.SENT
    assert model.transfer_kind(model.index(1, 0, QModelIndex())) == PendingTransfersModel.ARRIVED
    assert _background(model, 0) != _background(model, 1)


# The address of the end that has no account is the only exact thing known about it, and what an assignment is made
# against - so it is in the row rather than only in a tooltip.
def test_the_address_a_leg_names_is_shown(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), address=EUR_ADDRESS)

    assert _row(_model(), 0, 'address') == EUR_ADDRESS


# An address that resolves to an account of the user's own turns the row from a question into a confirmation. It
# resolves here even where settlement refuses to act on it by itself - the two accounts below are kept in different
# currencies, so what the asset cost has to be restated and only the user can state it.
def test_the_account_an_address_names_is_offered_in_the_row(wallets):
    wallet = _eur_wallet()
    _transfer(WALLET_A, None, 400, d2t(210103), address=EUR_ADDRESS)

    assert _row(_model(), 0, 'suggestion') == wallet.name()


def test_a_leg_that_names_no_address_suggests_nothing(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))

    assert _row(_model(), 0, 'suggestion') == ''


# ----------------------------------------------------------------------------------------------------------------------
# The asset column names the listing the LEG names, and never the asset behind it. A token held on several chains has
# one active listing per chain in one and the same currency, so asking the asset for its ticker in the account's
# currency answered with all of them run together - 'USDTUSDT' - a ticker that exists nowhere and says nothing about
# which chain the leg moved on, which is precisely what tells the two ends of such a leg apart.
def test_the_asset_column_names_the_listing_the_leg_moved(wallets):
    arb_usdt = JalAsset(USDT).add_symbol('USDT', USD, AssetLocation.ARB_BLOCKCHAIN)  # a second chain, still active
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 150, d2t(210104), symbol_id=arb_usdt)

    model = _model()

    assert _row(model, 0, 'asset') == 'USDT'
    assert _row(model, 1, 'asset') == 'USDT'


# A money transfer names no listing at all - it moves the currency of its own account, which is a single symbol
def test_a_money_leg_is_named_by_its_currency(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), asset_id=None)

    assert _row(_model(), 0, 'asset') == JalAsset(USD).symbol()


# ----------------------------------------------------------------------------------------------------------------------
# Transfers that are settled but arrived with no cost basis. They are in no other list - the transfer is complete, so
# every settlement view is done with them - and the zero surfaces only as a gain when the asset is finally sold. A
# zero may well be right, so they are shown only when asked for.

def test_a_settled_transfer_without_a_cost_basis_is_listed_only_on_request(wallets):
    _eur_wallet()
    _transfer(WALLET_A, 3, 400, d2t(210103), deposit=0)      # USD account -> EUR account, nothing states the basis

    assert _rows(_model()) == 0
    assert _rows(_model(with_basis_gaps=True)) == 1


def test_a_transfer_without_a_cost_basis_is_shown_as_settled_and_not_in_transit(wallets):
    wallet = _eur_wallet()
    _transfer(WALLET_A, wallet.id(), 400, d2t(210103), deposit=0)

    model = _model(with_basis_gaps=True)

    assert model.transfer_kind(model.index(0, 0, QModelIndex())) == PendingTransfersModel.BASIS
    assert _row(model, 0, 'from') == 'ARB wallet' and _row(model, 0, 'to') == wallet.name()
    assert _row(model, 0, 'value') == Decimal('0')           # both ends are known: nothing about it is in flight
    assert model._root.details()['value'] == Decimal('0')


def test_one_currency_at_both_ends_has_no_cost_basis_to_miss(wallets):
    _transfer(WALLET_A, WALLET_B, 400, d2t(210103), deposit=0)   # both wallets are kept in USD

    assert _rows(_model(with_basis_gaps=True)) == 0


def test_a_transfer_that_states_its_cost_basis_is_not_listed(wallets):
    wallet = _eur_wallet()
    _transfer(WALLET_A, wallet.id(), 400, d2t(210103), deposit=350)

    assert _rows(_model(with_basis_gaps=True)) == 0


def test_a_money_transfer_is_never_listed_as_missing_a_cost_basis(wallets):
    wallet = _eur_wallet()
    _transfer(WALLET_A, wallet.id(), 400, d2t(210103), asset_id=None, deposit=0)

    assert Transfer.legs_without_cost_basis() == []


def test_transfers_without_a_cost_basis_are_bounded_by_the_date_asked_about(wallets):
    wallet = _eur_wallet()
    _transfer(WALLET_A, wallet.id(), 400, d2t(210103), deposit=0)
    _transfer(WALLET_A, wallet.id(), 500, d2t(210401), deposit=0)     # after the date the report is asked about

    assert len(Transfer.legs_without_cost_basis()) == 2
    assert len(Transfer.legs_without_cost_basis(d2t(210301))) == 1
    assert _rows(_model(with_basis_gaps=True)) == 1


# ----------------------------------------------------------------------------------------------------------------------
# The report window's actions


# Settling rebuilds the ledger through the window the report was opened from - the main window owns the one every
# editor uses, and here it is only that
class _MainWindowStub:
    def __init__(self):
        self.ledger = Ledger()


# Settling is followed by a ledger rebuild, which meets the operation it just wrote - so the account the asset leaves
# has to actually hold it, as it would in any database where these legs came from a real movement
def _funded_wallet_a():
    create_actions([(d2t(210101), WALLET_A, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_trades(WALLET_A, [(d2t(210102), d2t(210102), USDT, 1000.0, 1.0, 0.0)])


# Assigning acts on the selected row, and the rows listed for a missing cost basis are settled transfers that no
# settlement action applies to - so the button follows what is actually selected rather than clicking into nothing.
def test_the_assign_button_follows_the_selection(wallets):
    wallet = _eur_wallet()
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(WALLET_A, wallet.id(), 500, d2t(210104), deposit=0)
    window = UnsettledTransfersReportWindow(Reports(None, None))
    window.ui.BasisGapsCheck.setChecked(True)
    view = window.ui.ReportTreeView

    assert window.ui.AssignButton.isEnabled() is False        # nothing is selected yet
    view.setCurrentIndex(view.model().index(0, 0, QModelIndex()))
    assert window.ui.AssignButton.isEnabled() is True         # the leg waiting for an account
    view.setCurrentIndex(view.model().index(1, 0, QModelIndex()))
    assert window.ui.AssignButton.isEnabled() is False        # the settled one that only lacks a cost basis


# What a settlement leaves behind. The list is a worklist, so a leg that has just been settled has to leave it - and
# the report is shown for the same date in the same currency afterwards, which is exactly the case a model that
# reloads only when its display parameters change does not notice. The row stayed, listing work already done, and
# every action offered on it would be refused.
def test_a_settled_leg_leaves_the_list(wallets):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103))
    window = UnsettledTransfersReportWindow(Reports(_MainWindowStub(), None))
    view = window.ui.ReportTreeView
    view.setCurrentIndex(view.model().index(0, 0, QModelIndex()))
    assert _rows(view.model()) == 1
    assert window.ui.AssignButton.isEnabled() is True

    oid = view.model().transfer_oid(view.currentIndex())
    assert TransferSettlement().assign_end(oid, WALLET_B, d2t(210103), Decimal('0')) == ''
    window._settled(True)

    assert _rows(view.model()) == 0
    # ... and the button doesn't stay enabled over the row that is gone: resetting a model drops the selection
    # without emitting selectionChanged, so nothing else would have told it
    assert window.ui.AssignButton.isEnabled() is False


# The same reload, for the other way a leg is settled
def test_matching_two_legs_empties_the_list(wallets):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 400, d2t(210103))
    window = UnsettledTransfersReportWindow(Reports(_MainWindowStub(), None))
    assert _rows(window.ui.ReportTreeView.model()) == 2

    legs = {leg['opart']: leg['oid'] for leg in Transfer.pending_legs()}
    assert TransferSettlement().settle_linked(legs[Transfer.Outgoing], legs[Transfer.Incoming]) == ''
    window._settled(True)

    assert _rows(window.ui.ReportTreeView.model()) == 0


# Legs are also settled where this report isn't looking - an import brings in the counterpart, an operation is edited
# or deleted in the main window. All of it ends in a ledger rebuild, on which the main window refreshes every report
# it has open, and this one has to be one of them (MdiWidget.refresh() is a no-op until a window overrides it).
def test_the_report_refreshes_on_a_change_made_elsewhere(wallets):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103))
    window = UnsettledTransfersReportWindow(Reports(_MainWindowStub(), None))
    assert _rows(window.ui.ReportTreeView.model()) == 1

    assert TransferSettlement().assign_end(Transfer.pending_legs()[0]['oid'], WALLET_B, d2t(210103), Decimal('0')) == ''
    window.refresh()             # what the main window calls when the ledger is rebuilt

    assert _rows(window.ui.ReportTreeView.model()) == 0


# ----------------------------------------------------------------------------------------------------------------------
# Settling what needs nobody's judgement, started from the report rather than only by an import.
#
# The two automatic passes act on PROOF - the transaction hash two records share, the address a leg names and an
# account of the user's holds - so they commit without asking and need no dialog. What makes them worth a button is
# that an import is not the only thing that can make them able to settle something: an address settles the moment the
# account holding it is created, and a rule they follow may itself have been corrected. Without it the only way to
# re-run them over legs already stored is to import something again, which is no answer to "why is this leg here".

HASH = '0x' + 'a' * 64


def test_the_settle_button_pairs_what_needs_no_judgement(wallets, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'information', lambda *args, **kwargs: None)
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number=HASH)
    window = UnsettledTransfersReportWindow(Reports(_MainWindowStub(), None))
    assert _rows(window.ui.ReportTreeView.model()) == 2

    window.ui.SettleButton.click()

    assert _rows(window.ui.ReportTreeView.model()) == 0


# A leg nothing can pair is left exactly as it was - the button reports that it did nothing rather than doing
# something on a resemblance
def test_the_settle_button_leaves_what_it_cannot_prove(wallets, monkeypatch):
    reported = []
    monkeypatch.setattr(QMessageBox, 'information', lambda _self, _parent, _title, text: reported.append(text))
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number='0x' + 'b' * 64)   # another transaction: not a pair
    window = UnsettledTransfersReportWindow(Reports(_MainWindowStub(), None))

    window.ui.SettleButton.click()

    assert _rows(window.ui.ReportTreeView.model()) == 2
    assert len(reported) == 1 and 'Match' in reported[0]


# ----------------------------------------------------------------------------------------------------------------------
# One movement recorded under two assets.
#
# A pending leg whose counterpart is whole except that it names a DIFFERENT asset is the one shape of unsettled leg no
# settlement can ever reach: what stands in the way is not a missing end but the two assets. It happens where a coin's
# identity is its contract address and its ticker only a label - a coin renamed on one chain is fetched as an asset of
# its own - and nothing else in JAL would ever point it out.

def _second_asset_listing(symbol: str = 'USD₮0'):
    asset = JalAssetCreator(PredefinedAsset.Crypto, symbol)
    listing = asset.add_symbol(symbol, USD, location_id=AssetLocation.ARB_BLOCKCHAIN)
    asset.commit()
    return listing


# The QUANTITY is what makes this worth saying: a swap gives back an amount of the other coin, a transfer delivers
# exactly what was sent. Two records of one transaction agreeing to the last digit are one movement.
def test_a_counterpart_under_another_asset_is_pointed_out(wallets):
    other = _second_asset_listing()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number=HASH, symbol_id=other)

    model = _model()
    tooltip = model.data(model.index(0, 0, QModelIndex()), Qt.ToolTipRole)

    assert 'USDT' in tooltip and 'USD₮0' in tooltip
    assert 'two assets' in tooltip


# ... and a transaction that gave back a different amount is a swap, not one movement under two names
def test_a_counterpart_of_another_quantity_is_not_pointed_out(wallets):
    other = _second_asset_listing()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 399, d2t(210103), number=HASH, symbol_id=other)

    model = _model()

    assert 'two assets' not in model.data(model.index(0, 0, QModelIndex()), Qt.ToolTipRole)


def test_a_counterpart_of_the_same_asset_is_not_pointed_out(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number=HASH)

    model = _model()

    assert 'two assets' not in model.data(model.index(0, 0, QModelIndex()), Qt.ToolTipRole)


# One transaction paying two different assets to two accounts says nothing about either being the other, and a hint
# that named an arbitrary one of them would be worse than none
def test_an_ambiguous_transaction_is_not_pointed_out(wallets):
    _second_asset_listing()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number=HASH, symbol_id=_second_asset_listing('OTHER'))
    _transfer(None, WALLET_B, 400, d2t(210103), number=HASH, symbol_id=_second_asset_listing('THIRD'))

    model = _model()

    assert 'two assets' not in model.data(model.index(0, 0, QModelIndex()), Qt.ToolTipRole)


# ----------------------------------------------------------------------------------------------------------------------
# Converting two legs into the swap they are.
#
# One asset leaving and ANOTHER arriving is an exchange, not a movement of the same money - no settlement can ever pair
# such legs, and left as transfers they misstate the money twice: the disposal is never recognized and what arrived
# opens at no cost basis. It reaches the report because whoever recorded it couldn't tell (an intent-based DEX settles
# through a transaction the wallet never signed), so the user is the one who says what it was.

# The row the conversion wrote, read back as it is stored - a swap has no accessor for every field it holds
def _stored_swap():
    return JalDB()._read("SELECT timestamp, tx_hash, account_id, out_symbol_id, out_qty, in_timestamp, in_account_id, "
                         "in_symbol_id, in_qty, fee_symbol_id, fee_qty FROM swaps ORDER BY oid DESC LIMIT 1",
                         named=True)


def _swap_pair(quantity_in=350):
    other = _second_asset_listing()
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_A, quantity_in, d2t(210103), number=HASH, symbol_id=other, deposit=0)
    legs = {leg['opart']: leg['oid'] for leg in Transfer.pending_legs()}
    return legs[Transfer.Outgoing], legs[Transfer.Incoming], other


def test_conversion_replaces_both_legs_with_one_swap(wallets):
    sent, arrived, other = _swap_pair()

    assert TransferSettlement().convert_to_swap(sent, arrived) == ''

    assert Transfer.pending_legs() == []                 # the two rows are gone, not merely hidden
    swap = _stored_swap()
    assert int(swap['account_id']) == WALLET_A and swap['in_account_id'] == ''   # same-chain: it receives on the spot
    assert int(swap['out_symbol_id']) == symbol_id_for(USDT) and Decimal(swap['out_qty']) == Decimal('400')
    assert swap['tx_hash'] == HASH


# The quantity of the arrived asset lives in 'withdrawal' on BOTH legs - 'deposit' of an asset transfer is the cost
# basis it opens at, which a leg recorded from a chain leaves at zero. Reading it as the quantity swaps into nothing.
def test_the_received_quantity_is_not_read_from_the_cost_basis(wallets):
    sent, arrived, other = _swap_pair(quantity_in=350)

    assert TransferSettlement().convert_to_swap(sent, arrived) == ''

    swap = _stored_swap()
    assert int(swap['in_symbol_id']) == other and Decimal(swap['in_qty']) == Decimal('350')


def test_conversion_refuses_two_legs_of_the_same_asset(wallets):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number=HASH)
    legs = {leg['opart']: leg['oid'] for leg in Transfer.pending_legs()}

    refusal = TransferSettlement().convert_to_swap(legs[Transfer.Outgoing], legs[Transfer.Incoming])

    assert 'same asset' in refusal
    assert len(Transfer.pending_legs()) == 2             # ... and nothing was written


def test_conversion_refuses_an_arrival_that_precedes_the_exchange(wallets):
    other = _second_asset_listing()
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210104), number=HASH)
    _transfer(None, WALLET_A, 350, d2t(210103), number=HASH, symbol_id=other, deposit=0)
    legs = {leg['opart']: leg['oid'] for leg in Transfer.pending_legs()}

    refusal = TransferSettlement().convert_to_swap(legs[Transfer.Outgoing], legs[Transfer.Incoming])

    assert 'received before' in refusal


def test_conversion_refuses_a_money_leg(wallets):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), asset_id=None, number=HASH)   # money, so it names no symbol
    _transfer(None, WALLET_A, 350, d2t(210103), number=HASH, deposit=0)
    legs = {leg['opart']: leg['oid'] for leg in Transfer.pending_legs()}

    refusal = TransferSettlement().convert_to_swap(legs[Transfer.Outgoing], legs[Transfer.Incoming])

    assert 'moves money' in refusal


# The legs may sit on two accounts - one asset given on one chain, another received on another. The Swap operation
# already knows that shape and keeps the acquiring leg's own account and moment.
def test_legs_on_two_accounts_become_a_cross_chain_swap(wallets):
    other = _second_asset_listing()
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 350, d2t(210104), number='0xbbbb', symbol_id=other, deposit=0)
    legs = {leg['opart']: leg['oid'] for leg in Transfer.pending_legs()}

    assert TransferSettlement().convert_to_swap(legs[Transfer.Outgoing], legs[Transfer.Incoming]) == ''

    swap = _stored_swap()
    assert int(swap['account_id']) == WALLET_A and int(swap['in_account_id']) == WALLET_B
    assert int(swap['timestamp']) == d2t(210103) and int(swap['in_timestamp']) == d2t(210104)


# A fee a leg paid is money that was really spent, so it moves onto the swap rather than vanishing with the row
def test_the_fee_of_a_leg_is_carried_onto_the_swap(wallets):
    sent, arrived, _other = _swap_pair()
    JalDB()._exec("UPDATE transfers SET fee=:fee, fee_account=:account, fee_symbol_id=:symbol WHERE oid=:oid",
                  [(":fee", Decimal('0.5')), (":account", WALLET_A), (":symbol", symbol_id_for(USDT)),
                   (":oid", sent)], commit=True)

    assert TransferSettlement().convert_to_swap(sent, arrived) == ''

    swap = _stored_swap()
    assert Decimal(swap['fee_qty']) == Decimal('0.5') and int(swap['fee_symbol_id']) == symbol_id_for(USDT)


def test_refusal_to_convert_answers_before_anything_is_written(wallets):
    sent, arrived, _other = _swap_pair()
    settlement = TransferSettlement()

    assert settlement.refusal_to_convert(sent, arrived) == ''
    # ... and the same leg offered as both sides of the exchange is not a pair at all
    assert 'no longer pending' in settlement.refusal_to_convert(sent, sent)
    assert len(Transfer.pending_legs()) == 2


# ----------------------------------------------------------------------------------------------------------------------
def test_the_swap_button_follows_the_selection(wallets):
    wallet = _eur_wallet()
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(WALLET_A, wallet.id(), 500, d2t(210104), deposit=0)
    window = UnsettledTransfersReportWindow(Reports(None, None))
    window.ui.BasisGapsCheck.setChecked(True)
    view = window.ui.ReportTreeView

    assert window.ui.SwapButton.isEnabled() is False       # nothing is selected yet
    view.setCurrentIndex(view.model().index(0, 0, QModelIndex()))
    assert window.ui.SwapButton.isEnabled() is True        # the leg waiting for an account
    view.setCurrentIndex(view.model().index(1, 0, QModelIndex()))
    assert window.ui.SwapButton.isEnabled() is False       # the settled one that only lacks a cost basis


# The dialog offers the legs of the other side, puts the one sharing a transaction reference first - that is proof the
# two moved together - and refuses to convert what cannot be a swap.
def test_the_swap_dialog_offers_the_counterpart_of_the_same_transaction(wallets):
    other = _second_asset_listing()
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_A, 350, d2t(210110), number='0xelse', symbol_id=_second_asset_listing('OTHER'), deposit=0)
    _transfer(None, WALLET_A, 350, d2t(210103), number=HASH, symbol_id=other, deposit=0)
    sending = [leg['oid'] for leg in Transfer.pending_legs() if leg['opart'] == Transfer.Outgoing][0]

    dialog = SwapConvertDialog(sending)

    assert dialog._candidates.topLevelItemCount() == 2
    first = dialog._candidates.topLevelItem(0)
    assert HASH in first.toolTip(0)                        # the one that names the same transaction leads
    dialog._candidates.setCurrentItem(first)
    assert dialog._buttons.button(QDialogButtonBox.Ok).isEnabled() is True

    dialog.accept()

    assert dialog.changed is True
    # the pair became a swap; the unrelated leg of another transaction is untouched and still waiting
    assert [leg['number'] for leg in Transfer.pending_legs()] == ['0xelse']


def test_the_swap_dialog_refuses_a_pair_that_is_a_transfer(wallets):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), number=HASH)
    _transfer(None, WALLET_B, 400, d2t(210103), number=HASH)   # the same asset - a transfer, not an exchange
    sending = [leg['oid'] for leg in Transfer.pending_legs() if leg['opart'] == Transfer.Outgoing][0]

    dialog = SwapConvertDialog(sending)

    assert dialog._candidates.topLevelItemCount() == 1
    dialog._candidates.setCurrentItem(dialog._candidates.topLevelItem(0))
    assert dialog._buttons.button(QDialogButtonBox.Ok).isEnabled() is False
    assert 'same asset' in dialog._status.text()


# The conversion writes a real disposal, so the ledger has to be able to process what it wrote - a swap that breaks
# the next rebuild would be worse than the two transfers it replaced
def test_the_ledger_processes_the_converted_swap(wallets):
    sent, arrived, other = _swap_pair()
    create_quotes(JalSymbol(other).asset().id(), USD, [(d2t(210103), 1.1)])

    assert TransferSettlement().convert_to_swap(sent, arrived) == ''
    Ledger().rebuild(from_timestamp=0)

    assert JalDB()._read("SELECT COUNT(*) FROM ledger WHERE otype=:swap",
                         [(":swap", LedgerTransaction.Swap)]) != '0'



# A fee is money that was really spent, so a pair whose fees one swap cannot hold is refused rather than converted
# with part of it dropped
def test_conversion_refuses_fees_one_swap_cannot_hold(wallets):
    sent, arrived, other = _swap_pair()
    JalDB()._exec("UPDATE transfers SET fee=:fee, fee_account=:account, fee_symbol_id=:symbol WHERE oid=:oid",
                  [(":fee", Decimal('0.5')), (":account", WALLET_A), (":symbol", symbol_id_for(USDT)), (":oid", sent)])
    JalDB()._exec("UPDATE transfers SET fee=:fee, fee_account=:account, fee_symbol_id=:symbol WHERE oid=:oid",
                  [(":fee", Decimal('0.5')), (":account", WALLET_A), (":symbol", other), (":oid", arrived)],
                  commit=True)

    assert 'different assets' in TransferSettlement().convert_to_swap(sent, arrived)
    assert len(Transfer.pending_legs()) == 2


def test_conversion_refuses_a_fee_charged_on_another_account(wallets):
    sent, arrived, _other = _swap_pair()
    JalDB()._exec("UPDATE transfers SET fee=:fee, fee_account=:account, fee_symbol_id=:symbol WHERE oid=:oid",
                  [(":fee", Decimal('0.5')), (":account", WALLET_B), (":symbol", symbol_id_for(USDT)), (":oid", sent)],
                  commit=True)

    assert 'another account' in TransferSettlement().convert_to_swap(sent, arrived)


# ----------------------------------------------------------------------------------------------------------------------
# Converting two legs into the bridge they are.
#
# JAL completes a crossing whose SENDING leg the fetcher recognized - that one is a pending half-bridge, matched from
# the Operations list. What reaches this conversion is the crossing the fetcher did NOT recognize, imported as two
# plain transfers: Match refuses it as soon as the bridge kept a cut (what arrived isn't what was sent), the swap
# conversion refuses it on the asset, and the bridge matcher has nothing to match - so it has no other path at all.

def _crossing(quantity_in=395):
    other = _second_asset_listing()   # the same asset would do; a second listing is what a real crossing arrives as
    JalDB()._exec("UPDATE asset_symbol SET asset_id=:asset WHERE id=:sym",
                  [(":asset", USDT), (":sym", other)], commit=True)
    JalAsset.db_cache.clear_cache()
    JalSymbol.db_cache.clear_cache()
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103), number='0xsent')
    _transfer(None, WALLET_B, quantity_in, d2t(210104), number='0xarrived', symbol_id=other, deposit=0)
    legs = {leg['opart']: leg['oid'] for leg in Transfer.pending_legs()}
    return legs[Transfer.Outgoing], legs[Transfer.Incoming]


def _stored_bridge():
    return JalDB()._read("SELECT out_timestamp, out_account_id, out_symbol_id, out_qty, out_tx_hash, in_timestamp, "
                         "in_account_id, in_symbol_id, in_qty, in_tx_hash, fee_symbol_id, fee_qty "
                         "FROM bridges ORDER BY oid DESC LIMIT 1", named=True)


def test_a_crossing_that_kept_a_cut_becomes_a_bridge(wallets):
    sent, arrived = _crossing(quantity_in=395)
    # This is the pair that has nowhere else to go: a transfer settlement refuses it outright
    assert 'not a transfer' in TransferSettlement().refusal_for(sent, arrived)

    assert TransferSettlement().convert_to_bridge(sent, arrived) == ''

    assert Transfer.pending_legs() == []
    bridge = _stored_bridge()
    assert int(bridge['out_account_id']) == WALLET_A and Decimal(bridge['out_qty']) == Decimal('400')
    assert int(bridge['in_account_id']) == WALLET_B and Decimal(bridge['in_qty']) == Decimal('395')
    assert bridge['out_tx_hash'] == '0xsent' and bridge['in_tx_hash'] == '0xarrived'
    assert int(bridge['out_timestamp']) == d2t(210103) and int(bridge['in_timestamp']) == d2t(210104)


def test_the_bridge_keeps_each_leg_own_listing(wallets):
    # The two ends are two listings of one token, one per chain - the bridge records the listing each side actually
    # moved, not one of them twice
    sent, arrived = _crossing()
    out_symbol = JalDB()._read("SELECT symbol_id FROM transfers WHERE oid=:oid", [(":oid", sent)])
    in_symbol = JalDB()._read("SELECT symbol_id FROM transfers WHERE oid=:oid", [(":oid", arrived)])

    assert TransferSettlement().convert_to_bridge(sent, arrived) == ''

    bridge = _stored_bridge()
    assert int(bridge['out_symbol_id']) == int(out_symbol) and int(bridge['in_symbol_id']) == int(in_symbol)
    assert bridge['out_symbol_id'] != bridge['in_symbol_id']


def test_bridge_refuses_more_arriving_than_was_sent(wallets):
    sent, arrived = _crossing(quantity_in=401)

    refusal = TransferSettlement().convert_to_bridge(sent, arrived)

    assert 'more arrived than was sent' in refusal
    assert len(Transfer.pending_legs()) == 2


def test_bridge_refuses_two_different_assets(wallets):
    other = _second_asset_listing()          # left on an asset of its own - the asset changed on the way
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103))
    _transfer(None, WALLET_B, 395, d2t(210104), symbol_id=other, deposit=0)
    legs = {leg['opart']: leg['oid'] for leg in Transfer.pending_legs()}

    refusal = TransferSettlement().convert_to_bridge(legs[Transfer.Outgoing], legs[Transfer.Incoming])

    assert 'cross-chain swap' in refusal


def test_bridge_refuses_both_legs_on_one_account(wallets):
    sent, arrived = _crossing()
    JalDB()._exec("UPDATE transfers SET deposit_account=:acc WHERE oid=:oid",
                  [(":acc", WALLET_A), (":oid", arrived)], commit=True)

    assert 'same account' in TransferSettlement().convert_to_bridge(sent, arrived)


def test_the_ledger_processes_the_converted_bridge(wallets):
    sent, arrived = _crossing()

    assert TransferSettlement().convert_to_bridge(sent, arrived) == ''
    Ledger().rebuild(from_timestamp=0)

    assert JalDB()._read("SELECT COUNT(*) FROM ledger WHERE otype=:bridge",
                         [(":bridge", LedgerTransaction.Bridge)]) != '0'


# ----------------------------------------------------------------------------------------------------------------------
# A pending half-bridge is the same money in flight as a pending sending leg - it left an account and reached none.
# Which of the two a movement became depends only on whether the fetcher recognized the contract, so a worklist that
# listed one and not the other would answer "what money of mine is in flight" with a number leaving the other out.

def _pending_half(qty=300, timestamp=None):
    data = {'out_timestamp': d2t(210103) if timestamp is None else timestamp, 'out_account_id': WALLET_A,
            'out_symbol_id': symbol_id_for(USDT), 'out_qty': str(qty), 'out_tx_hash': '0xcrossing',
            'note': 'Sent through a bridge'}
    return LedgerTransaction.create_new(LedgerTransaction.Bridge, data)


def test_a_pending_half_bridge_is_listed_and_counted_as_money_in_transit(wallets):
    create_quotes(USDT, USD, [(d2t(210103), 1.0)])
    _funded_wallet_a()
    _pending_half(qty=300)

    model = _model()

    assert _rows(model) == 1
    assert model.transfer_kind(model.index(0, 0, QModelIndex())) == PendingTransfersModel.BRIDGE
    assert _row(model, 0, 'qty') == Decimal('300')
    assert _row(model, 0, 'value') == Decimal('300')     # in flight: it left WALLET_A and reached nothing


def test_a_completed_bridge_is_not_listed(wallets):
    _funded_wallet_a()
    half = _pending_half()
    JalDB()._exec("UPDATE bridges SET in_account_id=:acc, in_timestamp=:ts, in_symbol_id=:sym, in_qty=:qty "
                  "WHERE oid=:oid",
                  [(":acc", WALLET_B), (":ts", d2t(210104)), (":sym", symbol_id_for(USDT)), (":qty", Decimal('295')),
                   (":oid", half.oid())], commit=True)

    assert _rows(_model()) == 0


def test_a_half_bridge_later_than_the_report_date_is_not_listed(wallets):
    _funded_wallet_a()
    _pending_half(timestamp=d2t(210304))       # _model() reports as of 01/03/2021

    assert _rows(_model()) == 0


# The settlements act on 'transfers' oids. A half-bridge names an oid in 'bridges', which is a perfectly valid number
# in the wrong table - handing it to one of them would settle a different operation entirely.
def test_the_transfer_actions_never_reach_a_half_bridge_row(wallets):
    _funded_wallet_a()
    _pending_half()
    window = UnsettledTransfersReportWindow(Reports(None, None))
    view = window.ui.ReportTreeView
    view.setCurrentIndex(view.model().index(0, 0, QModelIndex()))

    assert window._pending_oid(view.currentIndex()) == 0        # not offered to Assign/Match/Swap/Bridge
    assert window._pending_bridge_oid(view.currentIndex()) != 0  # ... and offered to the bridge matcher instead
    assert window.ui.AssignButton.isEnabled() is False
    assert window.ui.SwapButton.isEnabled() is False
    assert window.ui.BridgeButton.isEnabled() is False


def test_the_bridge_button_follows_the_selection(wallets):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103))
    window = UnsettledTransfersReportWindow(Reports(None, None))
    view = window.ui.ReportTreeView

    assert window.ui.BridgeButton.isEnabled() is False
    view.setCurrentIndex(view.model().index(0, 0, QModelIndex()))
    assert window.ui.BridgeButton.isEnabled() is True


# The dialog warns when the arrival it is about to consume is one a pending half-bridge could be waiting for: both
# paths end at the same Bridge, and taking it here would leave that half stranded with its send still on the books.
def test_the_bridge_dialog_warns_about_a_half_bridge_that_wants_the_same_arrival(wallets):
    sent, arrived = _crossing(quantity_in=395)
    _pending_half(qty=400, timestamp=d2t(210103))

    dialog = BridgeConvertDialog(sent)
    notes, _emphasize = dialog.marks(dict(oid=arrived, opart=Transfer.Incoming))

    assert notes and 'recorded twice' in notes[0]
    assert 'Match cross-chain legs' in notes[0]


def test_the_bridge_dialog_is_silent_when_no_half_bridge_wants_it(wallets):
    sent, arrived = _crossing(quantity_in=395)

    dialog = BridgeConvertDialog(sent)

    assert dialog.marks(dict(oid=arrived, opart=Transfer.Incoming)) == ([], False)


# ----------------------------------------------------------------------------------------------------------------------
# The same settlements, offered where the user happens to be standing: the Operations list already opens the bridge
# matcher on a pending half-bridge, and a one-legged transfer is the same kind of unfinished thing.

def test_operations_offers_the_settlements_on_a_pending_transfer_leg(wallets):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103))
    widget = OperationsWidget()
    names = [action.text() for action in widget._pending_transfer_actions()]

    assert names == ['Assign an account…', 'Match with another leg…', 'Convert into a swap…',
                     'Convert into a bridge…']


# _settle_pending_transfer() opens each of them the same way, so they have to agree on the shape it relies on:
# constructed from (oid, parent), and reporting through 'changed' whether anything was written.
@pytest.mark.parametrize("dialog_class",
                         [TransferAssignDialog, TransferMatchDialog, SwapConvertDialog, BridgeConvertDialog])
def test_every_settlement_dialog_takes_a_leg_and_reports_what_it_did(wallets, dialog_class):
    _funded_wallet_a()
    _transfer(WALLET_A, None, 400, d2t(210103))
    oid = Transfer.pending_legs()[0]['oid']

    dialog = dialog_class(oid, parent=None)

    assert dialog.changed is False


# ----------------------------------------------------------------------------------------------------------------------
# Legs nobody sent. An arrival from an address minted to imitate one of the user's own is an address-poisoning attack:
# it is not half of anything, so no settlement will ever complete it and it sits in this worklist for good. Worse, the
# address it puts in the history is the whole point of the attack - it is there to be copied into a real transfer.

POISONED = '0x6da64f4a6e15251d4c689ce1c3c90c1e7e457e63'   # imitates WALLET_A's address below at both ends
STRANGER = '0x6357d3843d715496257e338a878ab0b72040a918'


def _poisoning_leg(address=POISONED):
    return _transfer(None, WALLET_B, Decimal('0.001'), d2t(210103), address=address)


def test_a_poisoning_arrival_is_marked_and_named(wallets):
    JalDB()._exec("UPDATE account_data SET value=:addr WHERE account_id=:acc AND value LIKE '0x%'",
                  [(":addr", '0x6da6708a1b5946cade863f7f5792084731c57e63'), (":acc", WALLET_A)], commit=True)
    JalAccount.db_cache.clear_cache() if hasattr(JalAccount, 'db_cache') else None
    _poisoning_leg()

    model = _model()
    index = model.index(0, 0, QModelIndex())

    assert model.transfer_kind(index) == PendingTransfersModel.POISONING
    tooltip = model.data(index, Qt.ToolTipRole)
    assert 'ADDRESS POISONING' in tooltip
    assert 'ARB wallet' in tooltip          # it names WHICH wallet is being imitated
    assert 'Never copy this address' in tooltip


def test_an_arrival_from_a_stranger_is_an_ordinary_pending_leg(wallets):
    _funded_wallet_a()      # so the asset it brings is one the wallet really deals in
    _transfer(None, WALLET_B, 400, d2t(210103), address=STRANGER)

    model = _model()

    assert model.transfer_kind(model.index(0, 0, QModelIndex())) == PendingTransfersModel.ARRIVED


# The second, weaker signal: an asset that arrived once and that the wallet has never otherwise dealt in
def test_an_asset_the_wallet_never_dealt_in_is_marked_as_an_airdrop(wallets):
    _transfer(None, WALLET_B, 400, d2t(210103), symbol_id=_second_asset_listing('SPAM'))

    model = _model()
    index = model.index(0, 0, QModelIndex())

    assert model.transfer_kind(index) == PendingTransfersModel.AIRDROP
    assert 'has ever dealt in' in model.data(index, Qt.ToolTipRole)


# ... which must not fire on an asset the wallet really trades. This is the case that made the value-based rules
# unusable: an asset can be perfectly real and still have no quote and a tiny amount.
def test_an_asset_the_wallet_trades_is_not_an_airdrop(wallets):
    _funded_wallet_a()                       # buys USDT, so the wallet has dealt in it
    _transfer(None, WALLET_B, Decimal('0.000001'), d2t(210103))

    model = _model()

    assert model.transfer_kind(model.index(0, 0, QModelIndex())) == PendingTransfersModel.ARRIVED


def test_a_sent_leg_is_never_unsolicited(wallets):
    # What the user sent, the user sent - only an arrival can come from nowhere
    _transfer(WALLET_A, None, 400, d2t(210103), address=POISONED, symbol_id=_second_asset_listing('SPAM'))

    model = _model()

    assert model.transfer_kind(model.index(0, 0, QModelIndex())) == PendingTransfersModel.SENT
    assert TransferSettlement().dust_hint(Transfer.pending_legs()[0]['oid']) is None


# ----------------------------------------------------------------------------------------------------------------------
def test_writing_off_dust_keeps_the_coins_and_drops_the_leg(wallets):
    _poisoning_leg()
    oid = Transfer.pending_legs()[0]['oid']

    assert TransferSettlement().mark_as_dust(oid) == ''

    assert Transfer.pending_legs() == []          # it stops waiting for a sender it never had ...
    payment = JalDB()._read("SELECT type, account_id, symbol_id, amount FROM asset_payments ORDER BY oid DESC LIMIT 1",
                            named=True)
    assert int(payment['type']) == AssetPayment.DustAttack
    assert int(payment['account_id']) == WALLET_B          # ... and the coins stay where they really arrived
    assert Decimal(payment['amount']) == Decimal('0.001')


def test_dust_refuses_a_leg_that_was_sent(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))
    oid = Transfer.pending_legs()[0]['oid']

    assert 'arrived from nowhere' in TransferSettlement().mark_as_dust(oid)
    assert len(Transfer.pending_legs()) == 1


def test_dust_refuses_a_settled_transfer(wallets):
    _funded_wallet_a()
    transfer = _transfer(WALLET_A, WALLET_B, 400, d2t(210103))

    assert 'arrived from nowhere' in TransferSettlement().mark_as_dust(transfer.oid())


def test_the_ledger_processes_a_written_off_leg(wallets):
    _poisoning_leg()

    assert TransferSettlement().mark_as_dust(Transfer.pending_legs()[0]['oid']) == ''
    Ledger().rebuild(from_timestamp=0)

    assert JalDB()._read("SELECT COUNT(*) FROM ledger WHERE otype=:t",
                         [(":t", LedgerTransaction.AssetPayment)]) != '0'


def test_the_dust_button_follows_the_selection(wallets):
    _transfer(WALLET_A, None, 400, d2t(210103))      # sent - Dust doesn't apply
    _poisoning_leg()                                  # arrived from nowhere - it does
    window = UnsettledTransfersReportWindow(Reports(None, None))
    view = window.ui.ReportTreeView

    assert window.ui.DustButton.isEnabled() is False
    view.setCurrentIndex(view.model().index(0, 0, QModelIndex()))
    assert window.ui.DustButton.isEnabled() is False
    view.setCurrentIndex(view.model().index(1, 0, QModelIndex()))
    assert window.ui.DustButton.isEnabled() is True
