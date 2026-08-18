import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QWidget, QPushButton

from tests.fixtures import project_root, data_path, prepare_db
from jal.db.operations import LedgerTransaction
from jal.widgets.helpers import assign_shortcut
from jal.widgets.operations_widget import OperationsWidget


# Before this the whole package held exactly one keyboard shortcut, and the five actions a user repeats all day -
# new, copy and delete an operation, commit and revert the form - were unlabelled icons reachable only by mouse.
# The keys live in code rather than in the .ui files, so they cost no translatable string; what these tests hold
# in place is the part that is easy to get wrong - the scope each key answers in.
@pytest.fixture
def owner(prepare_db):
    parent = QWidget()
    yield parent
    parent.deleteLater()


@pytest.fixture
def operations(owner):
    return OperationsWidget(owner)


def _shortcuts(widget):
    return {shortcut.key().toString(): shortcut for shortcut in widget.findChildren(QShortcut)}


# ----------------------------------------------------------------------------------------------------------------------
# The helper is tested on a button of its own: firing the real ones would open the delete confirmation and the
# new-operation menu, and what needs proving here is only that the key reaches the button and respects its state.
def test_the_helper_clicks_the_button_it_was_given(owner):
    scope = QWidget(owner)
    button = QPushButton("", scope)
    button.setToolTip("Do the thing")
    shortcut = assign_shortcut(button, QKeySequence.Save, scope)

    assert shortcut.parent() is scope
    assert shortcut.context() == Qt.WidgetWithChildrenShortcut
    assert button.toolTip() == "Do the thing (Ctrl+S)"

    fired = []
    button.clicked.connect(lambda: fired.append(True))
    shortcut.activated.emit()
    assert fired == [True]

    # A disabled button ignores click(), which is what keeps Escape from reverting a form with nothing to revert
    button.setEnabled(False)
    shortcut.activated.emit()
    assert fired == [True]


# Not every standard key is defined on every platform - QKeySequence.Preferences, for one, resolves to nothing on
# Linux. An empty sequence must leave the button as it was rather than bind a key that matches everything.
def test_a_key_the_platform_does_not_define_binds_nothing(owner):
    button = QPushButton("", owner)
    button.setToolTip("Untouched")
    assert assign_shortcut(button, QKeySequence(), owner) is None
    assert button.toolTip() == "Untouched"


# ----------------------------------------------------------------------------------------------------------------------
# A QPushButton can carry a shortcut by itself, but only a window-scoped one - and this window holds all eight
# operation forms at once, so eight window-scoped Ctrl+S keys would be ambiguous and Qt would fire none of them.
@pytest.mark.parametrize("key,scope_name,context", (
        ("Ctrl+N", None, Qt.WidgetWithChildrenShortcut),
        ("Ctrl+D", None, Qt.WidgetWithChildrenShortcut),
        # Del stops at the table: the search field sits in the same window and must keep the key for editing
        ("Del", "OperationsTableView", Qt.WidgetShortcut)))
def test_operation_buttons_answer_their_key(operations, key, scope_name, context):
    shortcut = _shortcuts(operations).get(key)
    assert shortcut is not None, f"{key} is not bound anywhere in the operations window"
    assert shortcut.parent() is (operations if scope_name is None else getattr(operations.ui, scope_name))
    assert shortcut.context() == context


# The same two keys are bound once per form, each scoped to its own form, so the one holding the focus answers.
@pytest.mark.parametrize("key", ("Ctrl+S", "Esc"))
def test_every_operation_form_commits_and_reverts_by_key(operations, key):
    forms = [widget for operation, widget in operations.ui.OperationsTabs.widgets.items()
             if operation != LedgerTransaction.NA]
    assert len(forms) == 8, "an operation form was added or lost - it needs the same two keys"
    for form in forms:
        shortcut = _shortcuts(form).get(key)
        assert shortcut is not None, f"{type(form).__name__} does not bind {key}"
        assert shortcut.parent() is form
        assert shortcut.context() == Qt.WidgetWithChildrenShortcut


# An icon with no text has nowhere but the tooltip to say what key it answers to.
def test_tooltips_name_the_key(operations):
    tooltips = {name: getattr(operations.ui, name).toolTip()
                for name in ("NewOperationBtn", "CopyOperationBtn", "DeleteOperationBtn")}
    assert tooltips == {"NewOperationBtn": "New operation (Ctrl+N)",
                        "CopyOperationBtn": "Copy operation (Ctrl+D)",
                        "DeleteOperationBtn": "Delete operation (Del)"}
    form = operations.ui.OperationsTabs.widgets[LedgerTransaction.Trade]
    assert form.ui.commit_button.toolTip() == "Commit changes (Ctrl+S)"
    assert form.ui.revert_button.toolTip() == "Cancel changes (Esc)"
