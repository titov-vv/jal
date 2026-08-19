from PySide6.QtWidgets import QMessageBox, QWidget

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedCategory
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.db.common_models import CategoryTreeModel, TagTreeModel
from jal.widgets.reference_dialogs import CategoryListDialog


def test_tree_item_rename(prepare_db):
    model = CategoryTreeModel()
    taxes = model.locateItem(6)
    assert model.data(taxes) == "Taxes"
    assert model.setData(taxes, "Duties")
    assert model.data(taxes) == "Duties"


# Names of a tree are unique across the whole tree - a name taken in a branch that isn't even visible must be
# reported as such and not as a database failure in the log
def test_tree_duplicate_name_is_refused(prepare_db, monkeypatch):
    reported = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: (reported.append(args[3]), QMessageBox.Ok)[1])

    model = CategoryTreeModel()
    income = model.locateItem(1)
    model.addChildElement(income)                    # a new category under 'Income'...
    new_id = model._read("SELECT MAX(id) FROM categories")
    new_category = model.locateItem(new_id)
    assert not model.setData(new_category, "Taxes")  # ... can't take the name of 'Taxes' that lives under 'Spending'
    assert len(reported) == 1
    assert "Spending / Taxes" in reported[0]
    assert model.data(new_category) == model.tr("New category")
    model.revertAll()


def test_tag_tree_duplicate_name_is_refused(prepare_db, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Ok)
    model = TagTreeModel()
    cash = model.locateItem(2)                       # 'Cash' - a tag is named by the 'tag' column, not by 'name'
    assert not model.setData(cash, model.getValue(3))   # the name of 'Bank account' is taken
    assert model.data(cash) == "Cash"
    icon = model.index(cash.row(), model.fieldIndex('icon_file'), cash.parent())
    assert model.setData(icon, 'tag_bank.ico')       # only the name is unique, an icon may be shared
    model.revertAll()


# A discarded edit must leave the database as it was: saving the window state of the dialog commits, so it may
# not happen while the edit is still pending
def test_discarded_changes_are_not_stored(prepare_db, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Discard)
    parent = QWidget()
    dialog = CategoryListDialog(parent)
    dialog.OnAdd()
    added_id = JalDB()._read("SELECT MAX(id) FROM categories")
    assert added_id > PredefinedCategory.Profit
    dialog.close()
    assert JalDB()._read("SELECT name FROM categories WHERE id=:id", [(":id", added_id)]) is None


def test_tree_item_cant_be_left_without_name(prepare_db, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args, **kwargs: QMessageBox.Ok)
    model = CategoryTreeModel()
    taxes = model.locateItem(PredefinedCategory.Taxes)
    assert not model.setData(taxes, '')
    assert model.data(taxes) == "Taxes"


# An edit stays pending until the user commits or reverts it - a write that commits on its own (any settings
# write does) must not decide it on his behalf
def test_pending_edit_is_not_committed_by_others(prepare_db):
    model = CategoryTreeModel()
    model.addChildElement(model.locateItem(PredefinedCategory.Income))
    added_id = JalDB()._read("SELECT MAX(id) FROM categories")
    JalSettings().setValue('DlgGeometry_Categories', 'a window geometry')
    model.revertAll()
    assert JalDB()._read("SELECT name FROM categories WHERE id=:id", [(":id", added_id)]) is None
