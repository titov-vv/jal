import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_conversions
from constants import AccountData
from jal.db.account import JalAccount
from jal.db.db import JalDB
from jal.db.operations import LedgerAssetShortage
from jal.widgets.main_window import MainWindow


# A ledger that halts on a rebasing residue can be completed, and the halt carries the numbers to do it with. It used
# to be offered only as the tail of a chain import, so a ledger stopped by any other route - a rebuild by hand, an
# edited operation, the start of the application - stayed stopped with nothing saying it could be helped. These hold
# the main window's side of that: the halt raises the question, and the answer decides whether anything is booked.
@pytest.fixture
def halted_ledger(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)   # every ledger posting is rounded to it
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.880296'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.880296', 5, '50246.880296')])
    create_conversions(1, [(t_exit, 5, '50246.880299', 4, '50251.319007')])
    yield t_exit


# A shortage of a quantity rather than of a crumb - a supply that was never imported. The ledger stops on it just the
# same, and there is nothing to offer.
@pytest.fixture
def halted_on_missing_transaction(prepare_db_fifo):
    JalAccount(1).set_data(AccountData.Precision, 18)
    create_stocks([('USDG', 'Stablecoin'), ('aEthUSDG', 'Lending receipt')], currency_id=2)
    t_buy, t_supply, t_exit = d2t(220101), d2t(220201), d2t(220301)
    create_trades(1, [(t_buy, t_buy, 4, Decimal('50246.880296'), Decimal('1'), Decimal('0'))])
    create_conversions(1, [(t_supply, 4, '50246.880296', 5, '50246.880296')])
    create_conversions(1, [(t_exit, 5, '50247', 4, '50251.319007')])
    yield t_exit


@pytest.fixture
def window(prepare_db_fifo):
    main_window = MainWindow(None)
    yield main_window
    main_window.close()
    main_window.deleteLater()


# A halted rebuild emits 'updated' like any other and the live path reaches that emit after logging where it stopped,
# but under pytest rebuild() re-raises before it - so the signal is given here the way the application gives it.
def _halt(window):
    with pytest.raises(LedgerAssetShortage):
        window.ledger.rebuild(from_timestamp=0)
    window.ledger.updated.emit()
    QApplication.processEvents()   # the offer is connected queued, so it is delivered here

def _answer(monkeypatch, answer) -> list:
    asked = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: (asked.append(args), answer)[1])
    return asked


# ----------------------------------------------------------------------------------------------------------------------
def test_a_halt_on_a_residue_is_offered_and_repaired(window, halted_ledger, monkeypatch):
    asked = _answer(monkeypatch, QMessageBox.Yes)
    _halt(window)

    assert len(asked) == 1
    # The question names what the halt was about, so it can be answered without reading the log
    question = [arg for arg in asked[0] if isinstance(arg, str) and 'missing' in arg][0]
    assert 'aEthUSDG' in question and '0.000003' in question
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments") == 1
    assert JalAccount(1).get_asset_amount(halted_ledger, 5) == Decimal('0')          # the ledger ran to the end
    assert JalAccount(1).get_asset_amount(halted_ledger, 4) == Decimal('50251.319007')


def test_a_declined_offer_books_nothing(window, halted_ledger, monkeypatch):
    asked = _answer(monkeypatch, QMessageBox.No)
    _halt(window)

    assert len(asked) == 1
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments") == 0
    assert JalAccount(1).get_asset_amount(halted_ledger, 5) != Decimal('0')          # still stopped short of the exit


def test_a_halt_on_something_else_is_not_offered(window, halted_on_missing_transaction, monkeypatch):
    asked = _answer(monkeypatch, QMessageBox.Yes)
    _halt(window)

    assert asked == []
    assert JalDB._read("SELECT COUNT(*) FROM asset_payments") == 0
