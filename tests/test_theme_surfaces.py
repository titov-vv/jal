import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import logging
import pytest
from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_stocks, create_trades
from constants import PredefinedAccountType, AssetLocation
from jal.db.db import JalDB
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.helpers import now_ts
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction
from jal.db.pending_transfers_model import PendingTransfersModel
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.trade_widget import TradeWidget
from jal.widgets.custom.log_viewer import LogViewer
from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter

# ----------------------------------------------------------------------------------------------------------------------
# Every surface that draws a colour with a meaning, built and painted under three grounds: the light one the
# application was written against, a dark one, and a sepia one that is neither. Nothing here asserts a pixel - the
# colours themselves are held by test_theme.py. What this holds is that the surfaces still BUILD and PAINT when the
# palette is not the one they were written for, which is where the old absolute colours used to hide their damage.
#
# Set JAL_SHOTS to a directory to also write each surface out as a PNG - that is how the before/after sheets were
# made. The screenshots are the point of the test; the assertions are what keeps it honest when nobody looks.

SHOTS = os.environ.get('JAL_SHOTS', '')
USD = 2
WALLET_A, WALLET_B = 1, 2
STOCK = 4
DAY = 24 * 60 * 60
DAY_1, DAY_2, DAY_3 = now_ts() - 4 * DAY, now_ts() - 3 * DAY, now_ts() - 2 * DAY


def _palette(base, text, window, highlight):
    palette = QPalette()
    alternate = base.lighter(104) if base.lightness() < 128 else base.darker(104)
    for group in (QPalette.Active, QPalette.Inactive):
        palette.setColor(group, QPalette.Base, base)
        palette.setColor(group, QPalette.AlternateBase, alternate)
        palette.setColor(group, QPalette.Text, text)
        palette.setColor(group, QPalette.Window, window)
        palette.setColor(group, QPalette.WindowText, text)
        palette.setColor(group, QPalette.Button, window)
        palette.setColor(group, QPalette.ButtonText, text)
        palette.setColor(group, QPalette.Highlight, highlight)
        palette.setColor(group, QPalette.HighlightedText, QColor(255, 255, 255))
    return palette


THEMES = {
    'light': _palette(QColor(255, 255, 255), QColor(0, 0, 0), QColor(239, 239, 239), QColor(48, 140, 198)),
    'dark': _palette(QColor(30, 30, 30), QColor(224, 224, 224), QColor(45, 45, 45), QColor(38, 110, 160)),
    'sepia': _palette(QColor(244, 236, 216), QColor(60, 45, 30), QColor(232, 222, 198), QColor(150, 110, 60))
}


@pytest.fixture
def ledger(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='ARB wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '1' * 40,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    JalAccountCreator(currency_id=USD, number='', name='ETH wallet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '2' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_stocks([('AAPL', 'Apple Inc.')], USD)
    # Dated relative to today, so the operations list shows them under its default "week" range. One buy and two
    # sells, one of each sign, so both the positive and the negative colour appear in the amount columns.
    create_trades(WALLET_A, [(DAY_1, DAY_1, STOCK, Decimal('10'), Decimal('100'), Decimal('1')),
                             (DAY_2, DAY_2, STOCK, Decimal('-4'), Decimal('130'), Decimal('1')),
                             (DAY_3, DAY_3, STOCK, Decimal('-3'), Decimal('80'), Decimal('1'))])
    JalAccount(WALLET_A).reconcile(DAY_2)   # ... and the reconciled ones are marked, which is the INFO colour
    JalDB()._exec("UPDATE base_currency SET currency_id=:usd", [(":usd", USD)])
    Ledger().rebuild(from_timestamp=0)
    # Three unsettled legs, so the pending-transfers report has rows of more than one kind to tint
    _transfer(WALLET_A, None, 400, DAY_1, number='0xsent')
    _transfer(None, WALLET_B, 150, DAY_2, number='0xarrived')
    _transfer(None, WALLET_B, 9, DAY_3, address='0x' + 'f' * 40, number='0xpoison')
    yield


def _transfer(from_account, to_account, amount, timestamp, address=None, number=''):
    data = {'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
            'deposit_timestamp': timestamp, 'deposit_account': to_account, 'deposit': str(amount),
            'number': number, 'counterparty_address': address, 'symbol_id': None, 'note': ''}
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, data)


def _painted(widget, name, theme, width, height):
    widget.resize(width, height)
    widget.show()
    QApplication.processEvents()
    image = widget.grab().toImage()
    widget.hide()
    if SHOTS:
        image.save(os.path.join(SHOTS, f"{name}_{theme}.png"))
    return image


@pytest.mark.parametrize('theme', list(THEMES))
def test_every_coloured_surface_paints_on_any_ground(ledger, theme):
    app = QApplication.instance()
    original = app.palette()
    try:
        app.setPalette(THEMES[theme])

        operations = OperationsWidget(None)
        operations.ui.BalancesTreeView.model().showInactiveAccounts(True)
        operations.ui.OperationsTableView.selectRow(1)   # a selected row has to keep its highlight (P1-4)
        assert not _painted(operations, "operations", theme, 1100, 620).isNull()

        assert not _painted(TradeWidget(None), "trade", theme, 900, 240).isNull()

        view = TreeViewWithFooter(QWidget())
        model = PendingTransfersModel(view)
        view.setModel(model)
        model.updateView(currency_id=USD, date=QDate.currentDate(),
                         with_basis_gaps=False, filter_text='', grouping='', hide_unsolicited=False)
        assert not _painted(view, "pending", theme, 1100, 260).isNull()

        log = LogViewer()
        for level, text in ((logging.DEBUG, "Loading quotes for AAPL"),
                            (logging.INFO, "Ledger rebuilt: 3 operations"),
                            (logging.WARNING, "No quote for AAPL on 01/03/2021"),
                            (logging.ERROR, "Failed to download quotes from Stooq"),
                            (logging.CRITICAL, "Database schema is newer than this version")):
            log.displayMessage(level, text)   # a log viewer with no status bar attached must colour messages too
        assert not _painted(log, "log", theme, 900, 160).isNull()
    finally:
        app.setPalette(original)
