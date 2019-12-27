from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QAbstractItemView
from PySide2.QtSql import QSqlRelationalTableModel, QSqlRelation
from PySide2.QtCore import Signal, Property, Slot
from ui_active_choice_dlg import Ui_ActiveChoiceDlg

#TODO clean-up columns
class ActiveChoiceDlg(QDialog, Ui_ActiveChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.active_id = 0

    def Activate(self):
        self.ActiveTypeCombo.currentIndexChanged.connect(self.OnApplyFilter)
        self.ActivesList.selectionModel().selectionChanged.connect(self.OnActiveChosen)

#TODO: Make filter for inactive accounts
    @Slot()
    def OnApplyFilter(self, list_id):
        model = self.ActiveTypeCombo.model()
        id = model.data(model.index(list_id, 0))  # 0 is a field number for "id"
        self.ActivesList.model().setFilter(f"actives.type_id={id}")

    @Slot()
    def OnActiveChosen(self, selected, deselected):
        idx = selected.indexes()
        selected_row = idx[0].row()
        self.active_id = self.ActivesList.model().record(selected_row).value(0)

#TODO: Add autocomplete feature
class ActiveSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_active_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.symbol = QLineEdit()
        self.symbol.setText("Ticker")
        self.layout.addWidget(self.symbol)
        self.full_name = QLabel()
        self.full_name.setText("Full security name")
        self.layout.addWidget(self.full_name)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.button.clicked.connect(self.OnButtonClicked)

        self.dialog = ActiveChoiceDlg()

    def getId(self):
        return self.p_active_id

    def setId(self, id):
        self.p_active_id = id
        self.Model.setFilter(f"actives.id={id}")
        row_idx = self.Model.index(0, 0).row()
        symbol = self.Model.record(row_idx).value(1)
        full_name = self.Model.record(row_idx).value(3)
        self.symbol.setText(symbol)
        self.full_name.setText(full_name)
        self.Model.setFilter("")

    @Signal
    def active_id_changed(self):
        pass

    active_id = Property(int, getId, setId)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlRelationalTableModel(db=self.db)
        self.Model.setTable("actives")
        self.Model.setJoinMode(QSqlRelationalTableModel.LeftJoin)   # to work correctly with NULL values in SrcId
        type_idx = self.Model.fieldIndex("type_id")
        self.Model.setRelation(type_idx, QSqlRelation("active_types", "id", "name"))
        data_src_id = self.Model.fieldIndex("src_id")
        self.Model.setRelation(data_src_id, QSqlRelation("data_sources", "id", "name"))

        self.dialog.ActivesList.setModel(self.Model)
        self.dialog.ActivesList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.dialog.ActivesList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dialog.ActiveTypeCombo.setModel(self.Model.relationModel(type_idx))
        self.dialog.ActiveTypeCombo.setModelColumn(self.Model.relationModel(type_idx).fieldIndex("name"))
        self.Model.select()
        self.dialog.Activate()

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.symbol.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec_()
        if res:
            self.active_id = self.dialog.active_id