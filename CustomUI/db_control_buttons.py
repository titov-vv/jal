from PySide2.QtWidgets import QWidget, QHBoxLayout, QSpacerItem, QPushButton, QSizePolicy, QLabel
from PySide2.QtCore import Slot
from PySide2 import QtCore
from PySide2.QtSql import QSqlQuery

class DbControlButtons(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        spacer_width = parent.geometry().width() - 25*4
        self.spacer = QSpacerItem(spacer_width, 25, QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.layout.addItem(self.spacer)
        self.not_saved_flag = QLabel()
        self.not_saved_flag.setText("")
        self.layout.addWidget(self.not_saved_flag)
        self.new_button = QPushButton("New")
        self.layout.addWidget(self.new_button)
        self.del_button = QPushButton("Delete")
        self.layout.addWidget(self.del_button)
        self.copy_button = QPushButton("Copy")
        self.layout.addWidget(self.copy_button)
        self.commit_button = QPushButton("Commit")
        self.layout.addWidget(self.commit_button)
        self.setLayout(self.layout)

        self.new_button.clicked.connect(self.OnNewClicked)
        self.del_button.clicked.connect(self.OnDeleteClicked)
        self.copy_button.clicked.connect(self.OnCopyClicked)
        self.commit_button.clicked.connect(self.OnCommitClicked)

    def InitDB(self, db, operations_view, mapper):
        self.db = db
        self.operations_view = operations_view
        self.mapper = mapper

    @Slot()
    def OnDeleteClicked(self):
        index = self.operations_view.currentIndex()
        type = self.operations_view.model().data(self.operations_view.model().index(index.row(), 0))
        id = self.operations_view.model().data(self.operations_view.model().index(index.row(), 1))
        transfer_id = self.operations_view.model().data(self.operations_view.model().index(index.row(), 12))
        query = QSqlQuery(self.db)
        if (type == 1):
            if (transfer_id != 0):
                query.prepare("DELETE FROM actions AS a "
                              "WHERE a.id = (SELECT from_id FROM transfers AS t WHERE t.id = :transfer_id) "
                              "OR a.id = (SELECT to_id FROM transfers AS t WHERE t.id = :transfer_id)) "
                              "OR a.id = (SELECT fee_id FROM transfers AS t WHERE t.id = :transfer_id))")
                query.bindValue(":transfer_id", id)
                query.exec_()
                query.prepare("DELETE FROM transfers WHERE transfers.id = :transfer_id")
                query.bindValue(":transfer_id", id)
            else:
                query.prepare("DELETE FROM action_details AS a WHERE a.pid = :action_id")
                query.bindValue(":action_id", id)
                query.exec_()
                query.prepare("DELETE FROM actions WHERE actions.id = :action_id")
                query.bindValue(":action_id", id)
        elif (type == 2):
            query.prepare("DELETE FROM dividends WHERE dividends.id = :dividend_id")
            query.bindValue(":dividend_id", id)
        elif (type == 3):
            query.prepare("DELETE FROM trades WHERE trades.id = :trade_id")
            query.bindValue(":trade_id", id)
        else:
            print("SQL: Unknown typeof operation for deletion")
        if not query.exec_():
            print(f"SQL: Operation type {type} and id #{id} delete failed")
        self.operations_view.model().select()

    @Slot()
    def OnNewClicked(self):
        self.mapper.submit()
        new_record = self.mapper.model().record()
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        self.mapper.model().insertRecord(-1, new_record)
        self.mapper.toLast()
        self.not_saved_flag.setText(" * ")
        # if self.ChooseAccountBtn.account_id != 0:
        #     self.DividendAccountWidget.account_id = self.ChooseAccountBtn.account_id

    @Slot()
    def OnCopyClicked(self):
        row = self.mapper.currentIndex()
        new_record = self.mapper.model().record(row)
        self.mapper.submit()
        new_record.setNull("id")
        new_record.setValue("timestamp", QtCore.QDateTime.currentSecsSinceEpoch())
        self.mapper.model().insertRecord(-1, new_record)
        self.mapper.toLast()
        self.not_saved_flag.setText(" * ")

    @Slot()
    def OnCommitClicked(self):
        self.mapper.submit()
        self.mapper.model().submitAll()
        self.operations_view.model().select()
        self.not_saved_flag.setText("")