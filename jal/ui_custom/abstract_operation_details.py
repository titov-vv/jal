import logging
from PySide2.QtCore import Qt, Slot, Signal
from PySide2.QtGui import QFont
from PySide2.QtWidgets import QWidget, QGridLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy, QDataWidgetMapper
from PySide2.QtSql import QSqlTableModel
from jal.ui_custom.helpers import g_tr


class AbstractOperationDetails(QWidget):
    dbUpdated = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.model = None
        self.table_name = ''
        self.mapper = None
        self.modified = False

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)

        self.bold_font = QFont()
        self.bold_font.setBold(True)
        self.bold_font.setWeight(75)

        self.main_label = QLabel(self)
        self.main_label.setFont(self.bold_font)
        self.layout.addWidget(self.main_label, 0, 0, 1, 1, Qt.AlignLeft)

        self.commit_button = QPushButton(self)
        self.commit_button.setEnabled(False)
        self.commit_button.setText("✔")
        self.commit_button.setFont(self.bold_font)
        self.commit_button.setFixedWidth(self.commit_button.fontMetrics().width("XXX"))
        self.revert_button = QPushButton(self)
        self.revert_button.setEnabled(False)
        self.revert_button.setText("✖️")
        self.revert_button.setFont(self.bold_font)
        self.revert_button.setFixedWidth(self.revert_button.fontMetrics().width("XXX"))

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

    def init_db(self, db, table_name):
        self.table_name = table_name
        self.model = QSqlTableModel(parent=self, db=db)
        self.model.setTable(table_name)
        self.model.setEditStrategy(QSqlTableModel.OnManualSubmit)

        self.mapper = QDataWidgetMapper(self.model)
        self.mapper.setModel(self.model)
        self.mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)

        self.model.dataChanged.connect(self.onDataChange)
        self.commit_button.clicked.connect(self.saveChanges)
        self.revert_button.clicked.connect(self.revertCanges)

    def isCustom(self):
        return True

    def setId(self, id):
        self.model.setFilter(f"{self.table_name}.id={id}")
        self.mapper.setCurrentModelIndex(self.model.index(0, 0))

    @Slot()
    def onDataChange(self, _index_start, _index_stop, _role):
        self.modified = True
        self.commit_button.setEnabled(True)
        self.revert_button.setEnabled(True)

    @Slot()
    def saveChanges(self):
        if not self.model.submitAll():
            logging.fatal(
                g_tr('AbstractOperationDetails', "Operation submit failed: ") + self.model.lastError().text())
            return
        self.modified = False
        self.commit_button.setEnabled(False)
        self.revert_button.setEnabled(False)
        self.dbUpdated.emit()

    @Slot()
    def revertCanges(self):
        self.model.revertAll()
        self.modified = False
        self.commit_button.setEnabled(False)
        self.revert_button.setEnabled(False)
