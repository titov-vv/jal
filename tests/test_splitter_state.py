import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QSplitter, QVBoxLayout, QLabel

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import Setup
from jal.db.settings import JalSettings
from jal.widgets.helpers import restore_splitters, save_splitters


# Every widget built here gets a parent: a parentless one is collected by the cyclic collector at a moment
# unrelated to the test that made it, and takes the process down with it.
@pytest.fixture
def parent(prepare_db):
    holder = QWidget()
    yield holder
    holder.deleteLater()


# A host holding one named splitter of two panes, sized so that restoring a different split is visible
def _host(parent, name='TestSplitter', sizes=(100, 300)):
    host = QWidget(parent)
    layout = QVBoxLayout(host)
    splitter = QSplitter(Qt.Horizontal, host)
    splitter.setObjectName(name)
    splitter.addWidget(QLabel("left", splitter))
    splitter.addWidget(QLabel("right", splitter))
    layout.addWidget(host_splitter := splitter)
    host.resize(400, 100)
    host.show()
    host_splitter.setSizes(list(sizes))
    return host, splitter


def test_splitter_sizes_survive_a_rebuild(parent):
    host, splitter = _host(parent, sizes=(300, 100))
    saved = splitter.sizes()
    assert saved[0] > saved[1]      # the split we are about to reproduce
    save_splitters(host, Setup.SPLITTER_STATE_PREFIX)

    rebuilt_host, rebuilt = _host(parent, sizes=(100, 300))
    assert rebuilt.sizes()[0] < rebuilt.sizes()[1]    # ... built the other way round
    restore_splitters(rebuilt_host, Setup.SPLITTER_STATE_PREFIX)
    assert rebuilt.sizes() == saved


def test_unknown_splitter_is_left_at_its_designed_sizes(parent):
    host, splitter = _host(parent, name='NeverSavedSplitter', sizes=(120, 280))
    designed = splitter.sizes()
    restore_splitters(host, Setup.SPLITTER_STATE_PREFIX)
    assert splitter.sizes() == designed


# A splitter with no objectName has no key of its own and must not be written under the bare prefix,
# where it would share one value with every other unnamed splitter in the application.
def test_unnamed_splitter_is_not_stored(parent):
    host, splitter = _host(parent, name='', sizes=(150, 250))
    save_splitters(host, Setup.SPLITTER_STATE_PREFIX)
    assert JalSettings().getValue(Setup.SPLITTER_STATE_PREFIX, '') == ''


# The real thing: the operations window restores its own two splits when it is built, and saves them when it is
# closed - which is what makes the removal of BalanceFrameTop's 408 px forced width safe.
def test_operations_window_remembers_its_splits(parent):
    from jal.widgets.operations_widget import OperationsWidget

    parent.resize(1100, 620)
    parent.show()
    window = OperationsWidget(parent)
    window.resize(1100, 620)
    window.show()
    QApplication.processEvents()
    balances = window.ui.BalanceOperationsSplitter
    balances.setSizes([250, 850])
    saved = balances.sizes()
    window.close()

    reopened = OperationsWidget(parent)
    reopened.resize(1100, 620)
    reopened.show()
    QApplication.processEvents()
    assert reopened.ui.BalanceOperationsSplitter.sizes() == saved
