import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QVBoxLayout

from tests.fixtures import project_root
from jal.widgets.mdi import MdiWidget, TabbedWindowArea


# The main window used to keep its children in a QMdiArea, which put the controls of a maximized sub-window into
# the menu bar - a place macOS has no room for - and kept every sibling visible, so two forms claiming the same
# Alt+letter never cycled: the later one answered every press. A QTabWidget shows one page at a time, which is
# what the application always did anyway. These tests hold the container's side of that: what becomes a tab, what
# opens as a window of its own, and that a closed window is really closed - the operations form saves its
# splitters from closeEvent(), long before the application itself goes down.
class Window(MdiWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.closed = 0
        layout = QVBoxLayout(self)
        self.field = QLineEdit(self)
        label = QLabel("&Zone", self)
        label.setBuddy(self.field)
        layout.addWidget(label)
        layout.addWidget(self.field)

    def closeEvent(self, event):
        self.closed += 1
        super().closeEvent(event)


@pytest.fixture
def area(project_root):
    main_window = QMainWindow()
    window_area = TabbedWindowArea(main_window)
    main_window.setCentralWidget(window_area)
    main_window.resize(800, 600)
    main_window.show()
    yield window_area
    main_window.close()
    main_window.deleteLater()


def _alt(area, key):
    QApplication.sendEvent(area.window(), QKeyEvent(QEvent.KeyPress, key, Qt.AltModifier, "z"))
    QApplication.processEvents()


# ----------------------------------------------------------------------------------------------------------------------
def test_document_windows_become_tabs(area):
    first = area.addWindow(Window("Operations"))
    second = area.addWindow(Window("Report"))

    assert [area.tabText(i) for i in range(area.count())] == ["Operations", "Report"]
    assert area.windows() == [first, second]
    assert area.currentWidget() is second      # A window that was just opened is the one the user looks at
    assert not first.isVisible()               # ... and only that one is visible, which is what mnemonics rely on
    assert second.isVisible()


# A title is not a place to declare a shortcut: 'Operations & Balances' names a window, it doesn't ask for Alt+B
def test_ampersand_in_a_title_stays_a_letter(area):
    area.addWindow(Window("Operations & Balances"))

    assert area.tabText(0) == "Operations && Balances"


# The reason the MDI area had to go: both forms below claim Alt+Z, and only the one on screen may answer
def test_only_the_visible_tab_answers_a_mnemonic(area):
    first = area.addWindow(Window("Operations"))
    second = area.addWindow(Window("Report"))

    for current in (first, second):
        area.setCurrentWidget(current)
        QApplication.processEvents()
        for _ in range(2):     # Repeated presses must stay where they are, not cycle to the hidden form
            _alt(area, Qt.Key_Z)
            assert QApplication.focusWidget() is current.field


# ----------------------------------------------------------------------------------------------------------------------
# Charts, tax forms and the tax estimator are opened from the data they describe, so they are shown beside the
# tabs rather than over them - as real windows, which is also the only way to get a native frame on any platform.
def test_auxiliary_windows_open_beside_the_tabs(area):
    tab = area.addWindow(Window("Operations"))
    chart = area.addWindow(Window("Price chart"), floating=True, size=(400, 300))

    assert chart.isWindow()
    assert chart.parent() is area.window()     # Owned by the main window, so it goes down together with it
    assert chart.size().toTuple() == (400, 300)
    assert area.indexOf(chart) == -1           # It has no tab of its own ...
    assert area.windows() == [tab, chart]      # ... but a ledger rebuild still has to refresh it


def test_a_closed_free_window_leaves_the_area(area):
    chart = area.addWindow(Window("Price chart"), floating=True)

    chart.close()
    assert chart.closed == 1
    assert area.windows() == []


# The tab bar closes a window by closing the widget itself - a widget that is merely dropped from the tab bar
# gets no closeEvent(), and the operations form saves its two splitters from there.
def test_closing_a_tab_closes_the_widget_behind_it(area):
    first = area.addWindow(Window("Operations"))
    second = area.addWindow(Window("Report"))

    area.onTabCloseRequested(area.indexOf(first))
    assert first.closed == 1
    assert area.windows() == [second]
    assert [area.tabText(i) for i in range(area.count())] == ["Report"]
