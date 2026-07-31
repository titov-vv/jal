import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest
from PySide6.QtCore import Qt, QDate, QModelIndex
from PySide6.QtWidgets import QWidget, QMessageBox

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_actions, create_quotes, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedAccountType, PredefinedCategory, AssetLocation
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.operations import LedgerTransaction, Transfer
from jal.db.ledger import Ledger
from jal.db.pending_transfers_model import PendingTransfersModel
from jal.db.transfer_settlement import TransferSettlement
from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter
from jal.reports.reports import Reports
from jal.reports.unsettled_transfers import UnsettledTransfersReportWindow

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
