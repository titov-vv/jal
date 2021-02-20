import logging
from PySide2.QtCore import Qt, Slot, Signal
from PySide2.QtGui import QFont
from PySide2.QtWidgets import QWidget, QGridLayout, QLabel, QSpacerItem, QSizePolicy, QDateTimeEdit, QDateEdit, \
    QLineEdit, QDataWidgetMapper, QPushButton
from PySide2.QtSql import QSqlTableModel
from jal.ui_custom.helpers import g_tr
from jal.ui_custom.reference_selector import AccountSelector, AssetSelector
from jal.ui_custom.amount_editor import AmountEdit
from jal.widgets.mapper_delegate import MapperDelegate

class TradeWidget(QWidget):
    dbUpdated = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.model = None
        self.mapper = None
        self.modified = False

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)

        bold_font = QFont()
        bold_font.setBold(True)
        bold_font.setWeight(75)

        self.main_label = QLabel(self)
        self.main_label.setFont(bold_font)
        self.date_label = QLabel(self)
        self.settlement_label = QLabel()
        self.number_label = QLabel(self)
        self.account_label = QLabel(self)
        self.symbol_label = QLabel(self)
        self.qty_label = QLabel(self)
        self.price_label = QLabel(self)
        self.fee_label = QLabel(self)
        self.coupon_label = QLabel(self)
        self.comment_label = QLabel(self)

        self.main_label.setText(g_tr("TradeWidget", "Buy / Sell"))
        self.date_label.setText(g_tr("TradeWidget", "Date/Time"))
        self.settlement_label.setText(g_tr("TradeWidget", "Settlement"))
        self.number_label.setText(g_tr("TradeWidget", "#"))
        self.account_label.setText(g_tr("TradeWidget", "Account"))
        self.symbol_label.setText(g_tr("TradeWidget", "Asset"))
        self.qty_label.setText(g_tr("TradeWidget", "Qty"))
        self.price_label.setText(g_tr("TradeWidget", "Price"))
        self.fee_label.setText(g_tr("TradeWidget", "Fee"))
        self.coupon_label.setText(g_tr("TradeWidget", "Coupon"))
        self.comment_label.setText(g_tr("TradeWidget", "Note"))

        self.timestamp_editor = QDateTimeEdit(self)
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)
        self.timestamp_editor.setFixedWidth(self.timestamp_editor.fontMetrics().width("00/00/0000 00:00:00") * 1.25)
        self.timestamp_editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.settlement_editor = QDateEdit(self)
        self.settlement_editor.setCalendarPopup(True)
        self.settlement_editor.setTimeSpec(Qt.UTC)
        self.settlement_editor.setFixedWidth(self.settlement_editor.fontMetrics().width("00/00/0000") * 1.25)
        self.settlement_editor.setDisplayFormat("dd/MM/yyyy")
        self.account_widget = AccountSelector(self)
        self.asset_widget = AssetSelector(self)
        self.qty_edit = AmountEdit(self)
        self.qty_edit.setAlignment(Qt.AlignRight)
        self.price_edit = AmountEdit(self)
        self.price_edit.setAlignment(Qt.AlignRight)
        self.fee_edit = AmountEdit(self)
        self.fee_edit.setAlignment(Qt.AlignRight)
        self.coupon_edit = AmountEdit(self)
        self.coupon_edit.setAlignment(Qt.AlignRight)
        self.number = QLineEdit(self)
        self.comment = QLineEdit(self)
        self.commit_button = QPushButton(self)
        self.commit_button.setEnabled(False)
        self.commit_button.setText(g_tr("DividendWidget", "✔"))
        self.commit_button.setFixedWidth(self.commit_button.fontMetrics().width("XXX"))
        self.revert_button = QPushButton(self)
        self.revert_button.setEnabled(False)
        self.revert_button.setText(g_tr("DividendWidget", "✖️"))
        self.revert_button.setFixedWidth(self.revert_button.fontMetrics().width("XXX"))

        self.layout.addWidget(self.main_label, 0, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.date_label, 1, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.account_label, 2, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.symbol_label, 3, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.comment_label, 4, 0, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.account_widget, 2, 1, 1, 4)
        self.layout.addWidget(self.asset_widget, 3, 1, 1, 4)
        self.layout.addWidget(self.comment, 4, 1, 1, 4)

        self.layout.addWidget(self.settlement_label, 1, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.settlement_editor, 1, 3, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.number_label, 1, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.qty_label, 2, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.price_label, 3, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.fee_label, 4, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.coupon_label, 5, 5, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.number, 1, 6, 1, 1)
        self.layout.addWidget(self.qty_edit, 2, 6, 1, 1)
        self.layout.addWidget(self.price_edit, 3, 6, 1, 1)
        self.layout.addWidget(self.fee_edit, 4, 6, 1, 1)
        self.layout.addWidget(self.coupon_edit, 5, 6, 1, 1)

        self.layout.addWidget(self.commit_button, 0, 8, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 9, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout.addItem(self.verticalSpacer, 6, 6, 1, 1)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.layout.addItem(self.horizontalSpacer, 1, 7, 1, 1)

    def init_db(self, db):
        self.model = QSqlTableModel(parent=self, db=db)
        self.model.setTable("trades")
        self.model.setEditStrategy(QSqlTableModel.OnManualSubmit)

        self.mapper = QDataWidgetMapper(self.model)
        self.mapper.setModel(self.model)
        self.mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self.mapper.setItemDelegate(MapperDelegate(self.mapper))

        self.account_widget.init_db(db)
        self.asset_widget.init_db(db)
        self.account_widget.changed.connect(self.mapper.submit)
        self.asset_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.settlement_editor, self.model.fieldIndex("settlement"))
        self.mapper.addMapping(self.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.asset_widget, self.model.fieldIndex("asset_id"))
        self.mapper.addMapping(self.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.qty_edit, self.model.fieldIndex("qty"))
        self.mapper.addMapping(self.price_edit, self.model.fieldIndex("price"))
        self.mapper.addMapping(self.fee_edit, self.model.fieldIndex("fee"))
        self.mapper.addMapping(self.coupon_edit, self.model.fieldIndex("coupon"))
        self.mapper.addMapping(self.comment, self.model.fieldIndex("note"))

        self.model.select()

        self.model.dataChanged.connect(self.onDataChange)
        self.commit_button.clicked.connect(self.saveChanges)
        self.revert_button.clicked.connect(self.revertCanges)

    def isCustom(self):
        return True

    def setId(self, id):
        self.model.setFilter(f"trades.id={id}")
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
                g_tr('TradeWidget', "Trade submit failed: ") + self.model.lastError().text())
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