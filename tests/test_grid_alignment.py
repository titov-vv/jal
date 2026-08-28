from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QWidget, QAbstractItemView, QStyledItemDelegate, QStyleOptionViewItem

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import create_actions, d2t
from constants import PredefinedCategory
from jal.db.ledger import Ledger
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.reference_dialogs import AccountListDialog, TagsListDialog, CategoryListDialog, PeerListDialog


# A model that answers TextAlignmentRole with a bare Qt.AlignLeft or Qt.AlignRight replaces the whole alignment
# of the cell, and an alignment with no vertical half puts the text against the TOP of the row - which only shows
# once a row is taller than its text. The same goes for a delegate that assigns option.displayAlignment.
def cells_not_vertically_centered(window, rows=3) -> list:
    misaligned = []
    for view in window.findChildren(QAbstractItemView):
        model = view.model()
        if model is None:
            continue
        if hasattr(view, 'header'):          # a tree
            columns = view.header().count()
        elif hasattr(view, 'horizontalHeader'):   # a table
            columns = view.horizontalHeader().count()
        else:                                 # a list - the combo box popups an operation form carries
            columns = 1
        for row in range(rows):
            if not model.index(row, 0, QModelIndex()).isValid():
                break
            for column in range(columns):
                index = model.index(row, column, QModelIndex())
                if not index.isValid():
                    continue
                delegate = view.itemDelegateForIndex(index)
                if not isinstance(delegate, QStyledItemDelegate):
                    continue    # a plain QAbstractItemDelegate has no style option to align
                option = QStyleOptionViewItem()
                view.initViewItemOption(option)
                delegate.initStyleOption(option, index)
                if not int(option.displayAlignment) & int(Qt.AlignVertical_Mask):
                    misaligned.append((view.objectName(), row, column))
    return misaligned


def test_operations_and_balances_are_vertically_centered(prepare_db_fifo):
    create_actions([(d2t(201102), 1, 1, [(PredefinedCategory.Taxes, -100.0)])])
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    window = OperationsWidget(parent)
    window.show()
    window.operations_model.setDateRange(0)
    window.balances_model.update()
    window.grab()

    assert window.ui.OperationsTableView.model().rowCount() > 0
    assert cells_not_vertically_centered(window) == []

    window.close()
    parent.deleteLater()


def test_reference_dialogs_are_vertically_centered(prepare_db):
    parent = QWidget()
    for dialog_class in (AccountListDialog, TagsListDialog, CategoryListDialog, PeerListDialog):
        dialog = dialog_class(parent)
        dialog.show()
        assert cells_not_vertically_centered(dialog) == [], dialog_class.__name__
        dialog.close()
    parent.deleteLater()
