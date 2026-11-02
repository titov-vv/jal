import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QWidget, QStyleOptionViewItem

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import AssetData
from jal.db.asset_models import AssetDataModel
from jal.widgets.symbol_dialog import AssetAttributeDelegate

USD, EUR = 2, 3


# A 'pegged to' value is picked from the currencies and stored as the currency's id
def test_pegged_to_is_edited_as_a_currency(prepare_db):
    parent = QWidget()
    model = QStandardItemModel(1, 2, parent)
    model.setData(model.index(0, 0), AssetData.PeggedTo)
    model.setData(model.index(0, 1), str(EUR))
    delegate = AssetAttributeDelegate(0, 1, None, None, parent=parent)
    index = model.index(0, 1)

    editor = delegate.createEditor(parent, QStyleOptionViewItem(), index)
    delegate.setEditorData(editor, index)
    assert editor.currentData() == EUR and editor.currentText() == 'EUR'

    editor.setCurrentIndex(editor.findData(USD))
    delegate.setModelData(editor, model, index)
    assert model.data(index) == str(USD)


def test_pegged_to_shows_the_currency(prepare_db):
    model = AssetDataModel()
    assert model._format_value(AssetData.PeggedTo, str(USD)) == 'USD'
    assert model._format_value(AssetData.PeggedTo, 'x') == ''
