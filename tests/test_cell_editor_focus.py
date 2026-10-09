import pytest
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QGuiApplication, QStandardItemModel, QStandardItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTableView, QLineEdit, QAbstractItemView

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import create_actions, d2t
from jal.constants import PredefinedCategory
from jal.db.ledger import Ledger
from jal.widgets.delegates import KbSafeEditorMixin
from jal.widgets.helpers import set_grids_metrics
from jal.widgets.operations_widget import OperationsWidget
from jal.widgets.reference_dialogs import AccountListDialog, TagsListDialog, CategoryListDialog, PeerListDialog


# A window with one editable table that went through set_grids_metrics(), and a second window to take the focus away
@pytest.fixture
def edited_cell(prepare_db):
    window = QWidget()
    table = QTableView(window)
    QVBoxLayout(window).addWidget(table)
    model = QStandardItemModel(2, 2, table)
    for row in range(2):
        for column in range(2):
            model.setItem(row, column, QStandardItem("old"))
    table.setModel(model)
    set_grids_metrics(window)
    other = QWidget()
    other.show()
    window.show()
    window.activateWindow()
    assert QTest.qWaitForWindowActive(window)
    table.setFocus()
    table.edit(model.index(0, 0))
    editor = QApplication.focusWidget()
    assert isinstance(editor, QLineEdit)
    QTest.keyClicks(editor, "new")
    closed = []
    table.itemDelegate().closeEditor.connect(lambda *args: closed.append(True))
    yield window, other, model, editor, closed
    window.close()
    other.close()
    window.deleteLater()
    other.deleteLater()


# A desktop layout switcher deactivates the whole application for a moment: the edit has to survive it
def test_cell_editor_survives_application_deactivation(edited_cell, monkeypatch):
    window, other, model, editor, closed = edited_cell
    with monkeypatch.context() as patch:
        patch.setattr(QGuiApplication, "applicationState", staticmethod(lambda: Qt.ApplicationInactive))
        other.activateWindow()
        assert QTest.qWaitForWindowActive(other)
    assert closed == []
    assert model.index(0, 0).data() == "old"

    window.activateWindow()
    assert QTest.qWaitForWindowActive(window)
    assert QApplication.focusWidget() is editor
    assert editor.text() == "new" and editor.selectedText() == ""
    QTest.keyClick(editor, Qt.Key_Return)
    QApplication.processEvents()   # the delegate commits on Enter through a queued call
    assert model.index(0, 0).data() == "new"


# Another window of jal itself taking the focus still commits and closes the editor, as Qt does it
def test_cell_editor_is_committed_by_another_jal_window(edited_cell):
    window, other, model, editor, closed = edited_cell
    other.activateWindow()
    assert QTest.qWaitForWindowActive(other)
    assert closed == [True]
    assert model.index(0, 0).data() == "new"


# Every cell a user may edit has to be served by a delegate that keeps its editor
def cells_with_closing_editor(window) -> list:
    closing = []
    for view in window.findChildren(QAbstractItemView):
        model = view.model()
        if model is None or view.editTriggers() == QAbstractItemView.NoEditTriggers:
            continue
        for column in range(model.columnCount(QModelIndex())):
            delegate = view.itemDelegateForIndex(model.index(0, column, QModelIndex()))
            if delegate is not None and not isinstance(delegate, KbSafeEditorMixin):
                closing.append((view.objectName(), column, type(delegate).__name__))
    return closing


def test_operation_forms_keep_cell_editors(prepare_db_fifo):
    create_actions([(d2t(201102), 1, 1, [(PredefinedCategory.Taxes, -100.0)])])
    Ledger().rebuild(from_timestamp=0)
    parent = QWidget()
    window = OperationsWidget(parent)
    window.show()
    window.operations_model.setDateRange(0)
    assert cells_with_closing_editor(window) == []
    window.close()
    parent.deleteLater()


def test_reference_dialogs_keep_cell_editors(prepare_db):
    parent = QWidget()
    for dialog_class in (AccountListDialog, TagsListDialog, CategoryListDialog, PeerListDialog):
        dialog = dialog_class(parent)
        dialog.show()
        assert cells_with_closing_editor(dialog) == [], dialog_class.__name__
        dialog.close()
    parent.deleteLater()
