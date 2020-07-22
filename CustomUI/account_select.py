import logging
from datetime import datetime

from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex, QEvent
from PySide2.QtSql import QSqlRelationalTableModel, QSqlRelation, QSqlRelationalDelegate, QSqlTableModel
from PySide2.QtWidgets import QDialog, QWidget, QHBoxLayout, QLineEdit, QPushButton, QMenu, QCompleter, QHeaderView

from CustomUI.asset_select import CurrencySelector
from UI.ui_account_choice_dlg import Ui_AccountChoiceDlg
from UI.ui_account_type_dlg import Ui_AccountTypesDlg


########################################################################################################################
#  Predefined Account Types Editor
########################################################################################################################
class AccountTypeEditDlg(QDialog, Ui_AccountTypesDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)

        self.AddAccTypeBtn.clicked.connect(self.OnAdd)
        self.RemoveAccTypeBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)

    @Slot()
    def OnAdd(self):
        assert self.Model.insertRows(0, 1)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.AccountTypeList.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.Model.removeRow(selected_row)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.Model.submitAll():
            logging.fatal(self.tr("Action submit failed: ") + self.Model.lastError().text())
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.Model.revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlTableModel(db=self.db)
        self.Model.setTable("account_types")
        self.Model.setSort(self.Model.fieldIndex("name"), Qt.AscendingOrder)
        self.Model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.Model.setHeaderData(self.Model.fieldIndex("name"), Qt.Horizontal, "Account Type")

        self.AccountTypeList.setModel(self.Model)
        self.AccountTypeList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.AccountTypeList.horizontalHeader().setSectionResizeMode(self.Model.fieldIndex("name"), QHeaderView.Stretch)
        font = self.AccountTypeList.horizontalHeader().font()
        font.setBold(True)
        self.AccountTypeList.horizontalHeader().setFont(font)
        self.Model.select()

########################################################################################################################
#  Account Choice and Edit
########################################################################################################################

class AccountChoiceDlg(QDialog, Ui_AccountChoiceDlg):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)
        self.account_id = 0
        self.type_id = 0
        self.active_only = 1

        self.AccountTypeCombo.currentIndexChanged.connect(self.OnTypeChange)
        self.ShowInactive.stateChanged.connect(self.OnInactiveChange)
        self.AddAccountBtn.clicked.connect(self.OnAdd)
        self.RemoveAccountBtn.clicked.connect(self.OnRemove)
        self.CommitBtn.clicked.connect(self.OnCommit)
        self.RevertBtn.clicked.connect(self.OnRevert)

    def getAccountName(self):
        if self.account_id == 0:
            return "ALL"
        else:
            return self.p_account_name

    def setAccountName(self, account_id):
        pass

    @Signal
    def account_name_changed(self):
        pass

    AccountName = Property(str, getAccountName, setAccountName, notify=account_name_changed)

    def init_DB(self, db):
        self.db = db
        self.Model = QSqlRelationalTableModel(db=self.db)
        self.Model.setTable("accounts")
        self.Model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.Model.setJoinMode(QSqlRelationalTableModel.LeftJoin)   # to work correctly with NULL values in OrgId
        type_idx = self.Model.fieldIndex("type_id")
        self.Model.setRelation(type_idx, QSqlRelation("account_types", "id", "name"))
        currency_id = self.Model.fieldIndex("currency_id")
        self.Model.setRelation(currency_id, QSqlRelation("assets", "id", "name"))
        org_id = self.Model.fieldIndex("organization_id")
        self.Model.setRelation(org_id, QSqlRelation("agents", "id", "name"))
        self.Model.setHeaderData(self.Model.fieldIndex("type_id"), Qt.Horizontal, "Type")
        self.Model.setHeaderData(self.Model.fieldIndex("name"), Qt.Horizontal, "Name")
        self.Model.setHeaderData(self.Model.fieldIndex("currency_id"), Qt.Horizontal, "Currency")
        self.Model.setHeaderData(self.Model.fieldIndex("active"), Qt.Horizontal, "Act")
        self.Model.setHeaderData(self.Model.fieldIndex("number"), Qt.Horizontal, "Account #")
        self.Model.setHeaderData(self.Model.fieldIndex("reconciled_on"), Qt.Horizontal, "Reconciled @")
        self.Model.setHeaderData(self.Model.fieldIndex("organization_id"), Qt.Horizontal, "Bank")

        self.AccountsList.setModel(self.Model)
        self.AccountsList.setItemDelegate(AccountDelegate(self.AccountsList))
        self.AccountsList.setColumnHidden(self.Model.fieldIndex("id"), True)
        self.AccountsList.setColumnHidden(self.Model.fieldIndex("type_id"), True)
        self.AccountsList.setColumnWidth(self.Model.fieldIndex("active"), 32)
        self.AccountsList.setColumnWidth(self.Model.fieldIndex("reconciled_on"), self.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
        self.AccountsList.horizontalHeader().setSectionResizeMode(self.Model.fieldIndex("name"), QHeaderView.Stretch)
        font = self.AccountsList.horizontalHeader().font()
        font.setBold(True)
        self.AccountsList.horizontalHeader().setFont(font)

        self.AccountTypeCombo.setModel(self.Model.relationModel(type_idx))
        self.AccountTypeCombo.setModelColumn(self.Model.relationModel(type_idx).fieldIndex("name"))

        self.AccountsList.selectionModel().selectionChanged.connect(self.OnAccountChosen)
        self.Model.dataChanged.connect(self.OnDataChanged)
        self.Model.select()

    @Slot()
    def OnInactiveChange(self, state):
        if (state == 0):
            self.active_only = 1
        else:
            self.active_only = 0
        self.setAccountFilter()

    @Slot()
    def OnTypeChange(self, list_id):
        model = self.AccountTypeCombo.model()
        self.type_id = model.data(model.index(list_id, model.fieldIndex("id")))
        self.setAccountFilter()

    def setAccountFilter(self):
        account_filter = ""
        if self.type_id:
            account_filter = f"accounts.type_id={self.type_id}"
            if self.active_only:
                account_filter = account_filter + " AND  "
        if self.active_only:
            account_filter = account_filter + "accounts.active=1"
        self.AccountsList.model().setFilter(account_filter)

    @Slot()
    def OnAccountChosen(self, selected, _deselected):
        idx = selected.indexes()
        if idx:
            selected_row = idx[0].row()
            self.account_id = self.AccountsList.model().record(selected_row).value(0)
            self.p_account_name = self.AccountsList.model().record(selected_row).value(2)

    @Slot()
    def OnDataChanged(self):
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnAdd(self):
        new_record = self.AccountsList.model().record()
        new_record.setValue(1, self.type_id)    # set current type
        new_record.setValue(4, 1)               # set active
        assert self.AccountsList.model().insertRows(0, 1)
        self.AccountsList.model().setRecord(0, new_record)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnRemove(self):
        idx = self.AccountsList.selectionModel().selection().indexes()
        selected_row = idx[0].row()
        assert self.AccountsList.model().removeRow(selected_row)
        self.CommitBtn.setEnabled(True)
        self.RevertBtn.setEnabled(True)

    @Slot()
    def OnCommit(self):
        if not self.Model.submitAll():
            logging.fatal(self.tr("Action submit failed: ") + self.Model.lastError().text())
            return
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

    @Slot()
    def OnRevert(self):
        self.Model.revertAll()
        self.CommitBtn.setEnabled(False)
        self.RevertBtn.setEnabled(False)

########################################################################################################################
#  UI Button to choose accounts
########################################################################################################################
class AccountButton(QPushButton):
    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.p_account_id = 0
        self.setText("ALL")

        self.Menu = QMenu()
        self.Menu.addAction('Choose account', self.ChooseAccount)
        self.Menu.addAction('Any account', self.ClearAccount)
        self.setMenu(self.Menu)

        self.dialog = AccountChoiceDlg()

    def getId(self):
        return self.p_account_id

    def setId(self, account_id):
        self.p_account_id = account_id

    @Signal
    def account_id_changed(self):
        pass

    account_id = Property(int, getId, setId, notify=account_id_changed)

    @Signal
    def account_id_changed(self):
        pass

    def init_DB(self, db):
        self.dialog.init_DB(db)
        self.setText(self.dialog.AccountName)

    def ChooseAccount(self):
        ref_point = self.mapToGlobal(self.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setAccountFilter()
        res = self.dialog.exec_()
        if res:
            self.account_id = self.dialog.account_id
            self.setText(self.dialog.AccountName)
            self.clicked.emit()

    def ClearAccount(self):
        self.account_id = 0
        self.setText("ALL")
        self.clicked.emit()

########################################################################################################################
#  Custom UI account Editor
########################################################################################################################
class AccountSelector(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.p_account_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.name = QLineEdit()
        self.name.setText("")
        self.layout.addWidget(self.name)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.setFocusProxy(self.name)

        self.button.clicked.connect(self.OnButtonClicked)

        self.dialog = AccountChoiceDlg()

    def getId(self):
        return self.p_account_id

    def setId(self, account_id):
        if (self.p_account_id == account_id):
            return
        self.p_account_id = account_id
        self.dialog.Model.setFilter(f"accounts.id={account_id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        account_name = self.dialog.Model.record(row_idx).value(2)
        self.name.setText(account_name)
        self.dialog.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    account_id = Property(int, getId, setId, notify=changed, user=True)

    def init_DB(self, db):
        self.dialog.init_DB(db)
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex("name"))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.OnCompletion)

    def OnButtonClicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setAccountFilter()
        res = self.dialog.exec_()
        if res:
            self.account_id = self.dialog.account_id

    @Slot(QModelIndex)
    def OnCompletion(self, index):
        model = index.model()
        self.account_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)

####################################################################################################################3
# Delegate to display custom editors
####################################################################################################################3
class AccountDelegate(QSqlRelationalDelegate):
    def __init__(self, parent=None):
        QSqlRelationalDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        # Paint '*' for active account and nothing for inactive
        if (index.column() == 4):  # 'active' column
            painter.save()
            model = index.model()
            active = model.data(index, Qt.DisplayRole)
            if active:
                text = " * "
            else:
                text = ""
            painter.drawText(option.rect, Qt.AlignHCenter, text)
            painter.restore()
        # Format unixtimestamp into readable form
        elif (index.column() == 6):  # 'timestamp' column
            painter.save()
            model = index.model()
            timestamp = model.data(index, Qt.DisplayRole)
            if timestamp:
                text = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
            else:
                text = ""
            painter.drawText(option.rect, Qt.AlignLeft, text)
            painter.restore()
        else:
            QSqlRelationalDelegate.paint(self, painter, option, index)

    def editorEvent(self, event, model, option, index):
        if index.column() != 4:
            return False
        # Only for 'active' column
        if event.type() == QEvent.MouseButtonPress:
            if model.data(index, Qt.DisplayRole):   # Toggle 'active' value - from 1 to 0 and from 0 to 1
                model.setData(index, 0)
            else:
                model.setData(index, 1)
        return True

    def createEditor(self, aParent, option, index):
        if index.column() != 3:
            return QSqlRelationalDelegate.createEditor(self, aParent, option, index)

        currency_selector = CurrencySelector(aParent)
        currency_selector.init_DB(index.model().database())
        return currency_selector

    def setModelData(self, editor, model, index):
        if index.column() != 3:
            return QSqlRelationalDelegate.setModelData(self, editor, model, index)
        model.setData(index, editor.asset_id)