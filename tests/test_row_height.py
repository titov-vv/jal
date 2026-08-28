from PySide6.QtCore import QStringListModel
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import create_actions, d2t
from constants import PredefinedCategory
from jal.db.ledger import Ledger
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.helpers import set_grids_row_height, grid_row_height, RowPadding
from jal.db.settings import JalSettings
from jal.widgets.reference_dialogs import AccountListDialog, TagsListDialog


# A view reports the height of a row it has actually laid out, so the dialog has to be up before it is asked.
# A table applies the height to every row through its vertical header, while a tree computes one per row.
def open_dialogs(parent):
    accounts = AccountListDialog(parent)
    accounts.show()
    tags = TagsListDialog(parent)
    tags.show()
    return accounts, tags


def table_row_height(dialog) -> int:
    return dialog.ui.DataView.verticalHeader().defaultSectionSize()


def tree_row_height(dialog) -> int:
    return dialog.ui.TreeView.sizeHintForRow(0)


# reference_data_dlg.ui holds both a table and a tree, so the accounts dialog and the tags dialog are the same
# class showing its rows through different views - and they were 4 px apart until the tree got the table's metric
def test_tree_row_matches_table_row(prepare_db):
    parent = QWidget()
    accounts, tags = open_dialogs(parent)

    assert table_row_height(accounts) == grid_row_height(accounts.ui.DataView)
    assert tree_row_height(tags) == table_row_height(accounts)

    accounts.close()
    tags.close()
    parent.deleteLater()


# Both heights are read from the font the view uses, not frozen at a pixel count
def test_row_height_follows_the_font(prepare_db):
    parent = QWidget()
    accounts, tags = open_dialogs(parent)
    before = table_row_height(accounts)
    assert tree_row_height(tags) == before

    for dialog in (accounts, tags):
        font = QFont(dialog.font())
        font.setPointSize(font.pointSize() + 8)
        dialog.setFont(font)
        set_grids_row_height(dialog)

    assert table_row_height(accounts) > before
    assert tree_row_height(tags) == table_row_height(accounts)

    accounts.close()
    tags.close()
    parent.deleteLater()


# A tree row is as tall as the tallest of its columns asks to be, so the columns that set no delegate of their
# own have to be covered too - that is what the view-wide default delegate is installed for
def test_tree_without_own_delegates_gets_the_metric(prepare_db):
    window = QWidget()
    layout = QVBoxLayout(window)
    tree = QTreeView(window)
    tree.setModel(QStringListModel(["one", "two", "three"], tree))
    layout.addWidget(tree)
    window.show()
    assert tree.sizeHintForRow(0) < grid_row_height(tree)   # the default delegate asks for the font height alone

    set_grids_row_height(window)
    assert tree.sizeHintForRow(0) == grid_row_height(tree)

    window.close()
    window.deleteLater()


# The operations list sets the height of every row itself, from data(), so it is the one grid that can drift
# away from the metric the helper applies - it has to ask for the same height, times the lines it shows
def test_operations_rows_match_the_balances_tree(prepare_db_fifo):
    create_actions([(d2t(201102), 1, 1, [(PredefinedCategory.Taxes, -100.0)])])
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    window = OperationsWidget(parent)
    window.show()
    window.operations_model.setDateRange(0)   # the widget opens on the last week, the operation above is older
    window.balances_model.update()
    window.grab()      # the row heights are set while the rows are painted

    table = window.ui.OperationsTableView
    assert table.model().rowCount() > 0
    assert table.rowHeight(0) == grid_row_height(table)
    assert window.ui.BalancesTreeView.sizeHintForRow(0) == table.rowHeight(0)

    window.close()
    parent.deleteLater()


# The padding is a preference, so every grid follows it - and it is read once and cached, not per row
def test_row_padding_preference(prepare_db):
    parent = QWidget()
    accounts, tags = open_dialogs(parent)

    heights = {}
    for choice in (RowPadding.NONE, RowPadding.NORMAL, RowPadding.ROOMY):
        JalSettings().setValue(RowPadding.SETTINGS_KEY, choice)
        RowPadding.invalidate()
        set_grids_row_height(accounts)
        set_grids_row_height(tags)
        heights[choice] = table_row_height(accounts)
        assert tree_row_height(tags) == heights[choice]

    assert heights[RowPadding.NONE] == accounts.ui.DataView.fontMetrics().height()
    assert heights[RowPadding.NONE] < heights[RowPadding.NORMAL] < heights[RowPadding.ROOMY]
    # The padding is what grows, and it grows by the same step every time
    assert (heights[RowPadding.ROOMY] - heights[RowPadding.NORMAL]
            == heights[RowPadding.NORMAL] - heights[RowPadding.NONE])

    accounts.close()
    tags.close()
    parent.deleteLater()


# A row asks for its height on every layout, so the value may not go to the database more than once
def test_row_padding_is_read_once(prepare_db, monkeypatch):
    reads = []
    original = JalSettings.getInt
    monkeypatch.setattr(JalSettings, 'getInt',
                        lambda self, key, default=0: (reads.append(key), original(self, key, default))[1])
    RowPadding.invalidate()
    parent = QWidget()
    view = QTreeView(parent)
    view.setModel(QStringListModel(["one", "two", "three"], view))
    for _ in range(10):
        grid_row_height(view)
    assert reads.count(RowPadding.SETTINGS_KEY) == 1
    parent.deleteLater()
