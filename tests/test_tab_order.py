import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib
import pathlib
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QDialog, QMainWindow

from tests.fixtures import project_root, data_path, prepare_db

UI_ROOT = pathlib.Path(__file__).resolve().parent.parent / "jal" / "ui"


# Qt only reorders the widgets a form actually lists in <tabstops>; anything left out keeps the position its
# creation order gives it, which for uic is the order the widget appears in the XML. So a widget dropped into a
# form in Designer is not left out of the tab chain - it is silently spliced into it wherever the XML happens to
# put it, usually at the end, after the commit and revert buttons. Nothing about the form looks wrong, and the
# only way to notice is to press Tab through it. That is the regression these two tests exist to catch: the
# first says every widget the user can reach with Tab has a declared place, the second says commit and revert
# keep the last two places in the operation forms.
def _forms():
    for path in sorted(UI_ROOT.rglob("*.ui")):
        relative = path.relative_to(UI_ROOT)
        module = "jal.ui." + ".".join(relative.parts[:-1] + ("ui_" + path.stem,))
        yield pytest.param(path, module, id=str(relative))


OPERATION_FORMS = sorted((UI_ROOT / "widgets").glob("*_operation.ui"))


# A form is built on the host class it was drawn for: setupUi() calls accept()/reject() on a QDialog and
# setCentralWidget() on a QMainWindow, and a plain QWidget has neither.
HOST_CLASSES = {"QDialog": QDialog, "QMainWindow": QMainWindow}

# Two forms embed a QWebEngineView, and a bare one takes the global default profile - which cannot be torn down
# from a test process and takes the interpreter with it on the way out. Both application classes hand the view a
# page on a profile they own themselves, so these two forms are built the way the application builds them.
REAL_CLASSES = {"login_fns_dlg": ("jal.data_import.receipt_api.ru_fns", "LoginFNS"),
                "login_lidl_plus_dlg": ("jal.data_import.receipt_api.eu_lidl_plus", "LoginLidlPlus")}


# The host is given a parent for the reason spelled out in test_dialog_buttons.py: a parentless Qt window leaves
# its object graph to Python's cyclic collector, which takes it apart in an order Qt does not survive.
@pytest.fixture
def owner(prepare_db):
    parent = QWidget()
    yield parent
    parent.deleteLater()


def _build(path, module_name, owner):
    root = ET.parse(path).getroot()
    if path.stem in REAL_CLASSES:
        real_module, real_class = REAL_CLASSES[path.stem]
        return root, getattr(importlib.import_module(real_module), real_class)(owner).ui
    module = importlib.import_module(module_name)
    form_class = next(name for name in dir(module) if name.startswith("Ui_"))
    host = HOST_CLASSES.get(root.find("./widget").get("class"), QWidget)(owner)
    ui = getattr(module, form_class)()
    ui.setupUi(host)
    return root, ui


def _tabstops(root):
    return [stop.text for stop in root.findall("./tabstops/tabstop")]


@pytest.mark.parametrize("path,module_name", list(_forms()))
def test_every_widget_reachable_by_tab_has_a_declared_place(path, module_name, owner):
    root, ui = _build(path, module_name, owner)
    declared = _tabstops(root)

    # uic makes every named widget an attribute of the form class, so the widget is asked about itself rather
    # than matched by name - the composite widgets carry children of their own, some of them named the same.
    missing = []
    for element in root.iter("widget"):
        name = element.get("name")
        widget = getattr(ui, name, None) if name else None
        if isinstance(widget, QWidget) and widget.focusPolicy() & Qt.TabFocus and name not in declared:
            missing.append(name)
    assert not missing, f"{path.name} leaves {missing} out of <tabstops>, so Tab reaches them in XML order"

    named = {element.get("name") for element in root.iter("widget")}
    assert not [stop for stop in declared if stop not in named], \
        f"{path.name} lists a widget in <tabstops> that the form no longer has"


# Every operation form ends the same way - fill the fields, then commit or revert - so those two buttons are the
# last two stops on the way through. They are drawn in the top right corner, which is where a form re-tuned in
# Designer tends to put them back in the chain.
@pytest.mark.parametrize("path", OPERATION_FORMS, ids=lambda path: path.name)
def test_commit_and_revert_close_the_operation_forms(path):
    declared = _tabstops(ET.parse(path).getroot())
    assert declared[-2:] == ["commit_button", "revert_button"], \
        f"{path.name} ends its tab order with {declared[-2:]}"
