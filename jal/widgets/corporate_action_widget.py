from datetime import datetime
from dateutil import tz

from PySide2.QtCore import Qt, QStringListModel, QByteArray
from PySide2.QtWidgets import QLabel, QDateTimeEdit, QLineEdit, QComboBox
from jal.widgets.helpers import g_tr
from jal.widgets.abstract_operation_details import AbstractOperationDetails
from jal.widgets.reference_selector import AccountSelector, AssetSelector
from jal.widgets.amount_editor import AmountEdit
from jal.widgets.delegates import WidgetMapperDelegateBase


# ----------------------------------------------------------------------------------------------------------------------
class CorporateActionWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, parent=None):
        WidgetMapperDelegateBase.__init__(self, parent)
        self.delegates = {1: self.timestamp_delegate,
                             6: self.float_delegate,
                             8: self.float_delegate,
                             9: self.float_delegate}


# ----------------------------------------------------------------------------------------------------------------------
class CorporateActionWidget(AbstractOperationDetails):
    def __init__(self, parent=None):
        AbstractOperationDetails.__init__(self, parent)
        self.name = "Corporate action"
        self.combo_model = None

        self.date_label = QLabel(self)
        self.account_label = QLabel(self)
        self.type_label = QLabel(self)
        self.number_label = QLabel(self)
        self.before_label = QLabel(self)
        self.asset_b_label = QLabel(self)
        self.qty_b_label = QLabel(self)
        self.after_label = QLabel(self)
        self.asset_a_label = QLabel(self)
        self.qty_a_label = QLabel(self)
        self.ratio_label = QLabel(self)
        self.comment_label = QLabel(self)
        self.arrow_asset = QLabel(self)
        self.arrow_amount = QLabel(self)

        self.main_label.setText(g_tr("CorpActionWidget", "Corporate Action"))
        self.date_label.setText(g_tr("CorpActionWidget", "Date/Time"))
        self.account_label.setText(g_tr("CorpActionWidget", "Account"))
        self.type_label.setText(g_tr("CorpActionWidget", "Type"))
        self.number_label.setText(g_tr("CorpActionWidget", "#"))
        self.asset_b_label.setText(g_tr("CorpActionWidget", "Asset"))
        self.qty_b_label.setText(g_tr("CorpActionWidget", "Qty"))
        self.asset_a_label.setText(g_tr("CorpActionWidget", "Asset"))
        self.qty_a_label.setText(g_tr("CorpActionWidget", "Qty"))
        self.ratio_label.setText(g_tr("CorpActionWidget", "% of basis"))
        self.comment_label.setText(g_tr("CorpActionWidget", "Note"))
        self.arrow_asset.setText(" ➜ ")
        self.arrow_amount.setText(" ➜ ")

        self.timestamp_editor = QDateTimeEdit(self)
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)
        self.timestamp_editor.setFixedWidth(self.timestamp_editor.fontMetrics().width("00/00/0000 00:00:00") * 1.25)
        self.timestamp_editor.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
        self.type = QComboBox(self)
        self.account_widget = AccountSelector(self)
        self.asset_b_widget = AssetSelector(self)
        self.asset_a_widget = AssetSelector(self)
        self.qty_b_edit = AmountEdit(self)
        self.qty_a_edit = AmountEdit(self)
        self.ratio_edit = AmountEdit(self)
        self.number = QLineEdit(self)
        self.comment = QLineEdit(self)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.type_label, 2, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.number_label, 3, 0, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.comment_label, 5, 0, 1, 6, Qt.AlignLeft)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 1)
        self.layout.addWidget(self.type, 2, 1, 1, 1)
        self.layout.addWidget(self.number, 3, 1, 1, 1)
        self.layout.addWidget(self.comment, 5, 1, 1, 6)

        self.layout.addWidget(self.account_label, 1, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.asset_b_label, 2, 2, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.qty_b_label, 3, 2, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.account_widget, 1, 3, 1, 4)
        self.layout.addWidget(self.asset_b_widget, 2, 3, 1, 1)
        self.layout.addWidget(self.qty_b_edit, 3, 3, 1, 1)

        self.layout.addWidget(self.arrow_asset, 2, 4, 1, 1)
        self.layout.addWidget(self.arrow_amount, 3, 4, 1, 1)

        self.layout.addWidget(self.asset_a_label, 2, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.qty_a_label, 3, 5, 1, 1, Qt.AlignRight)
        self.layout.addWidget(self.ratio_label, 4, 5, 1, 1, Qt.AlignRight)

        self.layout.addWidget(self.asset_a_widget, 2, 6, 1, 1)
        self.layout.addWidget(self.qty_a_edit, 3, 6, 1, 1)
        self.layout.addWidget(self.ratio_edit, 4, 6, 1, 1)

        self.layout.addWidget(self.commit_button, 0, 8, 1, 1)
        self.layout.addWidget(self.revert_button, 0, 9, 1, 1)

        self.layout.addItem(self.verticalSpacer, 6, 0, 1, 1)
        self.layout.addItem(self.horizontalSpacer, 1, 7, 1, 1)

        super()._init_db("corp_actions")
        self.combo_model = QStringListModel([g_tr("CorpActionWidget", "N/A"),
                                             g_tr("CorpActionWidget", "Merger"),
                                             g_tr("CorpActionWidget", "Spin-Off"),
                                             g_tr("CorpActionWidget", "Symbol change"),
                                             g_tr("CorpActionWidget", "Split"),
                                             g_tr("CorpActionWidget", "Stock dividend")])
        self.type.setModel(self.combo_model)

        self.mapper.setItemDelegate(CorporateActionWidgetDelegate(self.mapper))

        self.account_widget.changed.connect(self.mapper.submit)
        self.asset_b_widget.changed.connect(self.mapper.submit)
        self.asset_a_widget.changed.connect(self.mapper.submit)

        self.mapper.addMapping(self.timestamp_editor, self.model.fieldIndex("timestamp"))
        self.mapper.addMapping(self.account_widget, self.model.fieldIndex("account_id"))
        self.mapper.addMapping(self.asset_b_widget, self.model.fieldIndex("asset_id"))
        self.mapper.addMapping(self.asset_a_widget, self.model.fieldIndex("asset_id_new"))
        self.mapper.addMapping(self.number, self.model.fieldIndex("number"))
        self.mapper.addMapping(self.qty_b_edit, self.model.fieldIndex("qty"))
        self.mapper.addMapping(self.qty_a_edit, self.model.fieldIndex("qty_new"))
        self.mapper.addMapping(self.ratio_edit, self.model.fieldIndex("basis_ratio"))
        self.mapper.addMapping(self.comment, self.model.fieldIndex("note"))
        self.mapper.addMapping(self.type, self.model.fieldIndex("type"), QByteArray().setRawData("currentIndex", 12))

        self.model.select()

    def prepareNew(self, account_id):
        new_record = self.model.record()
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        new_record.setValue("account_id", account_id)
        new_record.setValue("type", 0)
        new_record.setValue("asset_id", 0)
        new_record.setValue("qty", 0)
        new_record.setValue("asset_id_new", 0)
        new_record.setValue("qty_new", 0)
        new_record.setValue("note", None)
        return new_record

    def copyToNew(self, row):
        new_record = self.model.record(row)
        new_record.setNull("id")
        new_record.setValue("timestamp", int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
        new_record.setValue("number", '')
        return new_record
