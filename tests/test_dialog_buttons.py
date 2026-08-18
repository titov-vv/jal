import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QPushButton, QWidget

from tests.fixtures import project_root, data_path, prepare_db
from jal.widgets.account_dialog import AccountDialog
from jal.widgets.symbol_dialog import SymbolDialog


# Every dialog here is built with a parent, which is how the application builds them - and is not optional in a
# test process. A parentless dialog leaves its whole object graph to Python's cyclic collector, which frees Qt
# objects in an order Qt does not survive: a view outliving the model it is connected to, or a child sending its
# ChildRemoved event to a parent that has already gone. Either way the process aborts, at whatever unrelated point
# the collection happened to run. Give the dialog a parent and Qt owns the tree and takes it down in its own order.
@pytest.fixture
def owner(prepare_db):
    parent = QWidget()
    yield parent
    parent.deleteLater()


# Both dialogs used to lay out OK and Cancel by hand, which left the platform out of the decision in three ways:
# the two forms disagreed on the order (Account showed OK first, Asset showed Cancel first), neither could follow
# the reversed macOS convention, and QDialog picked the default button by child order - so Enter pressed
# 'add attribute' in the Account dialog and Cancel in the Asset one. A QDialogButtonBox answers all three.
def _edit_dialog(owner, index):
    dialog = (AccountDialog, SymbolDialog)[index](owner)
    dialog.createNewRecord()
    return dialog


@pytest.mark.parametrize("index", (0, 1))
def test_standard_buttons_are_wired(owner, index):
    dialog = _edit_dialog(owner, index)
    box = dialog.ui.DialogButtonBox
    assert box.button(QDialogButtonBox.Ok) is not None
    assert box.button(QDialogButtonBox.Cancel) is not None

    accepted, rejected = [], []
    dialog.accepted.connect(lambda: accepted.append(True))
    dialog.rejected.connect(lambda: rejected.append(True))
    box.button(QDialogButtonBox.Cancel).click()
    assert (accepted, rejected) == ([], [True])


# Enter must commit the dialog, not trigger whichever button happens to come first in the form's XML.
@pytest.mark.parametrize("index", (0, 1))
def test_enter_activates_ok(owner, index):
    dialog = _edit_dialog(owner, index)
    dialog.show()
    defaults = [b for b in dialog.findChildren(QPushButton) if b.isDefault()]
    assert defaults == [dialog.ui.DialogButtonBox.button(QDialogButtonBox.Ok)]
    dialog.hide()


# The order of the row is the style's to decide - the forms must not hard-code one. Both Linux styles ask for
# OK first; the macOS style reverses it, and the button box is what makes that possible without touching the form.
@pytest.mark.parametrize("index", (0, 1))
def test_button_order_follows_the_style(owner, index):
    dialog = _edit_dialog(owner, index)
    dialog.show()
    box = dialog.ui.DialogButtonBox
    visual = [b.text() for b in sorted(box.buttons(), key=lambda button: button.x())]
    expected = [box.button(QDialogButtonBox.Ok).text(), box.button(QDialogButtonBox.Cancel).text()]
    assert visual == expected, f"{QApplication.style().objectName()} laid the row out as {visual}"
    dialog.hide()


# ----------------------------------------------------------------------------------------------------------------------
# The reference lists had no accept or close button at all - the only way out was the window's cross. They do two
# jobs, so the box says which one is running, and both exits go through close() because closeEvent() is what stores
# the window geometry and the column layout.
def _list_dialog(owner, index):
    from jal.widgets.assets_dialogs import SymbolListDialog
    from jal.widgets.reference_dialogs import TagsListDialog
    return (SymbolListDialog, TagsListDialog)[index](owner)


@pytest.mark.parametrize("index", (0, 1))
def test_reference_list_offers_close_when_managing(owner, index):
    dialog = _list_dialog(owner, index)
    dialog.selection_enabled = False
    dialog._setup_dialog_buttons()
    box = dialog.ui.DialogButtonBox
    assert box.button(QDialogButtonBox.Close) is not None
    assert box.button(QDialogButtonBox.Ok) is None


@pytest.mark.parametrize("index", (0, 1))
def test_reference_list_offers_ok_cancel_when_picking(owner, index):
    dialog = _list_dialog(owner, index)
    dialog.selection_enabled = True
    dialog._setup_dialog_buttons()
    box = dialog.ui.DialogButtonBox
    assert box.button(QDialogButtonBox.Cancel) is not None
    # nothing is picked yet, so there is no answer to return
    assert not box.button(QDialogButtonBox.Ok).isEnabled()


def test_picking_a_row_enables_ok_and_returns_it(owner):
    from jal.widgets.assets_dialogs import SymbolListDialog
    dialog = SymbolListDialog(owner)
    picked = {}

    def act():
        view = dialog.ui.DataView
        view.setCurrentIndex(view.model().index(0, 1))
        button = dialog.ui.DialogButtonBox.button(QDialogButtonBox.Ok)
        picked['enabled'] = button.isEnabled()
        button.click()
        if dialog.isVisible():          # the click failed to close it - bail out rather than hang the suite
            dialog.done(QDialog.Rejected)

    QTimer.singleShot(0, act)
    result = dialog.exec(enable_selection=True)
    assert picked['enabled']
    assert result == QDialog.Accepted
    assert dialog.selected_id > 0


# ----------------------------------------------------------------------------------------------------------------------
# 'Clear' and 'Add' are not exits: one throws the loaded receipt away, the other writes an operation and leaves the
# window open. They keep their words and gain the roles that place them.
def test_receipt_import_button_roles(owner):
    from jal.data_import.shop_receipt import ImportReceiptDialog
    dialog = ImportReceiptDialog(owner)
    box = dialog.ui.DialogButtonBox
    roles = {button.text(): box.buttonRole(button) for button in box.buttons()}
    assert roles[dialog.clear_button.text()] == QDialogButtonBox.ResetRole
    assert roles[dialog.add_operation_button.text()] == QDialogButtonBox.ActionRole
    assert box.buttonRole(box.button(QDialogButtonBox.Close)) == QDialogButtonBox.RejectRole


# ----------------------------------------------------------------------------------------------------------------------
# 'Login' is the affirmative action but not an unconditional accept - it has to reach the server first. So it carries
# AcceptRole (which places it and makes it the default) while the box's accepted() runs the login rather than
# accept(). Two of the three dialogs had no reject path at all before this change.
LOGIN_DIALOGS = (("jal.data_import.receipt_api.pt_pingo_doce", "LoginPingoDoce", ("DialogButtonBox",)),
                 ("jal.data_import.receipt_api.ru_fns", "LoginFNS", ("SMSButtonBox", "FNSButtonBox", "ESIAButtonBox")),
                 ("jal.data_import.receipt_api.eu_lidl_plus", "LoginLidlPlus", ("DialogButtonBox",)))


@pytest.mark.parametrize("module_name,class_name,boxes", LOGIN_DIALOGS)
def test_every_login_row_can_be_dismissed(owner, module_name, class_name, boxes):
    import importlib
    dialog = getattr(importlib.import_module(module_name), class_name)(owner)
    for box_name in boxes:
        box = getattr(dialog.ui, box_name)
        rejects = [b for b in box.buttons() if box.buttonRole(b) == QDialogButtonBox.RejectRole]
        assert len(rejects) == 1, f"{class_name}.{box_name} offers no way out"


def test_login_buttons_do_not_accept_by_themselves(owner):
    from jal.data_import.receipt_api.ru_fns import LoginFNS
    dialog = LoginFNS(owner)
    for box_name, button in (("SMSButtonBox", dialog.sms_login_button), ("FNSButtonBox", dialog.fns_login_button)):
        assert getattr(dialog.ui, box_name).buttonRole(button) == QDialogButtonBox.AcceptRole

    # accepted() has to reach the login handler, never QDialog.accept() - a refused login must leave the dialog open
    closed = []
    dialog.accepted.connect(lambda: closed.append(True))
    reached = []
    dialog.ui.SMSButtonBox.accepted.disconnect()
    dialog.ui.SMSButtonBox.accepted.connect(lambda: reached.append(True))
    dialog.sms_login_button.click()
    assert reached == [True]
    assert closed == [], "the dialog must not close before the login has succeeded"
