from datetime import datetime
from dateutil import tz

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QLabel, QDateTimeEdit, QLineEdit
from jal.ui_custom.helpers import g_tr
from jal.ui_custom.abstract_operation_details import AbstractOperationDetails
from jal.ui_custom.reference_selector import AccountSelector, AssetSelector
from jal.ui_custom.amount_editor import AmountEdit
from jal.widgets.mapper_delegate import MapperDelegate

class DividendWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        AbstractOperationDetails.__init__(self, parent)
        self.name = "Dividend"

        self.date_label = QLabel(self)
        self.number_label = QLabel(self)
        self.account_label = QLabel(self)
        self.symbol_label = QLabel(self)
        self.amount_label = QLabel(self)
        self.tax_label = QLabel(self)
        self.comment_label = QLabel(self)

        self.main_label.setText(g_tr("DividendWidget", "Dividend"))
        self.date_label.setText(g_tr("DividendWidget", "Date/Time"))
        self.number_label.setText(g_tr("DividendWidget", "#"))
        self.account_label.setText(g_tr("DividendWidget", "Account"))
        self.symbol_label.setText(g_tr("DividendWidget", "Asset"))
        self.amount_label.setText(g_tr("DividendWidget", "Dividend"))
        self.tax_label.setText(g_tr("DividendWidget", "Tax"))
        self.comment_label.setText(g_tr("DividendWidget", "Note"))

        self.timestamp_editor = QDateTimeEdit(self)
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)
        self.timestamp_editor.setFixedWidth(self.timestamp_editor.fontMetrics().width("00/00/0000 00:00:00") * 1.25)
        self.timestamp_editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.account_widget = AccountSelector(self)
        self.asset_widget = AssetSelector(self)
        self.dividend_edit = AmountEdit(self)
        self.dividend_edit.setAlignment(Qt.AlignRight)
        self.tax_edit = AmountEdit(self)
        self.tax_edit.setAlignment(Qt.AlignRight)
        self.number = QLineEdit(self)
        self.comment = QLineEdit(self)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.account_label, 2, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.symbol_label, 3, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.comment_label, 4, 0, 1, 1, Qt.AlignLeft)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.account_widget, 2, 1, 1, 4)
        self.layout.addWidget(self.asset_widget, 3, 1, 1, 4)
        self.layout.addWidget(self.comment, 4, 1, 1, 8)

        self.layout.addWidget(self.number_label, 1, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.amount_label, 2, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.tax_label, 3, 5, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.number, 1, 6, 1, 1)
        self.layout.addWidget(self.dividend_edit, 2, 6, 1, 1)
        self.layout.addWidget(self.tax_edit, 3, 6, 1, 1)

        self.layout.addWidget(self.commit_button, 0, 7, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 8, 1, 1)

        self.layout.addItem(self.verticalSpacer, 5, 0, 1, 1)
        self.layout.addItem(self.horizontalSpacer, 1, 6, 1, 1)

    def init_db(self, db):
        super().init_db(db, "dividends")
        self.mapper.setItemDelegate(MapperDelegate(self.mapper))

        self.account_widget.init_db(db)
        self.asset_widget.init_db(db)
        self.account_widget.changed.connect(self.mapper.submit)
        self.asset_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.asset_widget, self.model.fieldIndex("asset_id"))
        self.mapper.addMapping(self.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.dividend_edit, self.model.fieldIndex("sum"))
        self.mapper.addMapping(self.tax_edit, self.model.fieldIndex("sum_tax"))
        self.mapper.addMapping(self.comment, self.model.fieldIndex("note"))

        self.model.select()

    def prepareNew(self, account_id):
        new_record = self.model.record()
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("asset_id", 0)
        new_record.setValue("sum", 0)
        new_record.setValue("sum_tax", 0)
        new_record.setValue("note", None)
        return new_record
