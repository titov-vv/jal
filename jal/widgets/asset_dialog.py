from PySide6.QtCore import Property
from PySide6.QtSql import QSqlTableModel
from PySide6.QtWidgets import QDialog, QDataWidgetMapper
from jal.ui.ui_asset_dlg import Ui_AssetDialog
from jal.db.helpers import db_connection


class AssetDialog(QDialog, Ui_AssetDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self._asset_id = -1
        self._model = QSqlTableModel(parent=self, db=db_connection())
        self._model.setTable("assets")

        self.type_model = QSqlTableModel(parent=self, db=db_connection())
        self.type_model.setTable('asset_types')
        self.type_model.select()
        self.TypeCombo.setModel(self.type_model)
        self.TypeCombo.setModelColumn(self.type_model.fieldIndex("name"))

        self._mapper = QDataWidgetMapper(self._model)
        self._mapper.setModel(self._model)
        self._mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)

        self._mapper.addMapping(self.NameEdit, self._model.fieldIndex("full_name"))
        self._mapper.addMapping(self.isinEdit, self._model.fieldIndex("isin"))

        self._model.select()

    def getSelectedId(self):
        return self._asset_id

    def setSelectedId(self, asset_id):
        self._asset_id = asset_id
        self._model.setFilter(f"id={self._asset_id}")
        self._mapper.toFirst()

    selected_id = Property(str, getSelectedId, setSelectedId)
