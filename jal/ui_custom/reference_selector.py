from abc import ABC, abstractmethod

from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QCompleter

from jal.ui_custom.helpers import g_tr
import jal.ui_custom.reference_data as ui               # Full import due to "cyclic" reference


# To solve metaclass conflict
class SelectorMeta(type(ABC), type(QWidget)):
    pass


class AbstractReferenceSelector(ABC, QWidget, metaclass=SelectorMeta):
    changed = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.completer = None
        self.p_selected_id = 0

        self.layout = QHBoxLayout()
        self.layout.setMargin(0)
        self.name = QLineEdit()
        self.name.setText("")
        self.layout.addWidget(self.name)
        self.details = QLabel()
        self.details.setText("")
        self.details.setVisible(False)
        self.layout.addWidget(self.details)
        self.button = QPushButton("...")
        self.button.setFixedWidth(self.button.fontMetrics().width("XXXX"))
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        self.setFocusProxy(self.name)

        self.button.clicked.connect(self.on_button_clicked)

        self.table = None
        self.selector_field = None
        self.details_field = None
        self.dialog = None

    def getId(self):
        return self.p_selected_id

    def setId(self, selected_id):
        if self.p_selected_id == selected_id:
            return
        self.p_selected_id = selected_id
        self.dialog.Model.setFilter(f"{self.table}.id={selected_id}")
        row_idx = self.dialog.Model.index(0, 0).row()
        name = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex(self.selector_field))
        self.name.setText(name)
        if self.details_field:
            details = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex(self.details_field))
            self.details.setText(details)
        self.dialog.Model.setFilter("")

    selected_id = Property(int, getId, setId, notify=changed, user=True)

    def on_button_clicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        res = self.dialog.exec_(enable_selection=True)
        if res:
            self.selected_id = self.dialog.selected_id
            self.changed.emit()

    @abstractmethod
    def init_db(self, db):
        pass

    def init_db(self, table, selector_field, details_field=None):
        self.table = table
        self.selector_field = selector_field
        if details_field:
            self.name.setFixedWidth(self.name.fontMetrics().width("X") * 15)
            self.details_field = details_field
            self.details.setVisible(True)
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex(self.selector_field))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.on_completion)

    @Slot(QModelIndex)
    def on_completion(self, index):
        model = index.model()
        self.selected_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)
        self.changed.emit()

    def isCustom(self):
        return True


class AccountSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db):
        self.dialog = ui.ReferenceDataDialog(db, "accounts",
                                          [("id", None, 0, None, None),
                                           ("name", g_tr('AccountSelector', "Name"), -1, Qt.AscendingOrder, None),
                                           ("type_id", None, 0, None, None),
                                           ("currency_id", "Currency", None, None, ui.ReferenceLookupDelegate),
                                           ("active", "Act", 32, None, ui.ReferenceBoolDelegate),
                                           ("number", "Account #", None, None, None),
                                           ("reconciled_on", "Reconciled @",
                                            self.fontMetrics().width("00/00/0000 00:00:00") * 1.1,
                                            None, ui.ReferenceTimestampDelegate),
                                           ("organization_id", "Bank", None, None, ui.ReferencePeerDelegate),
                                           ("country_id", g_tr('TableViewConfig', "CC"), 50, None, ui.ReferenceLookupDelegate)],
                                          title=g_tr('AccountSelector', "Accounts"), search_field="full_name", toggle=("active", "Show inactive"),
                                          relations=[("type_id", "account_types", "id", "name", "Account type:"),
                                                     ("currency_id", "currencies", "id", "name", None),
                                                     ("organization_id", "agents", "id", "name", None),
                                                     ("country_id", "countries", "id", "code", None)])
        super().init_db("accounts", "name")


class AssetSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db):
        self.dialog = ui.ReferenceDataDialog(db, "assets",
                                          [("id", None, 0, None, None),
                                           ("name", "Symbol", None, Qt.AscendingOrder, None),
                                           ("type_id", None, 0, None, None),
                                           ("full_name", "Name", -1, None, None),
                                           ("isin", "ISIN", None, None, None),
                                           ("country_id", g_tr('TableViewConfig', "Country"), None, None, ui.ReferenceLookupDelegate),
                                           ("src_id", "Data source", None, None, ui.ReferenceLookupDelegate)],
                                          title="Assets", search_field="full_name",
                                          relations=[("type_id", "asset_types", "id", "name", "Asset type:"),
                                                     ("country_id", "countries", "id", "name", None),
                                                     ("src_id", "data_sources", "id", "name", None)])
        super().init_db("assets", "name", "full_name")


class PeerSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db):
        self.dialog = ui.ReferenceDataDialog(db, "agents_ext",
                                          [("id", " ", 16, None, ui.ReferenceTreeDelegate),
                                           ("pid", None, 0, None, None),
                                           ("name", "Name", -1, Qt.AscendingOrder, None),
                                           ("location", "Location", None, None, None),
                                           ("actions_count", "Docs count", None, None, ui.ReferenceIntDelegate),
                                           ("children_count", None, None, None, None)],
                                          title="Choose peer", search_field="name", tree_view=True)
        super().init_db("agents_ext", "name")


class CategorySelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db):
        self.dialog = ui.ReferenceDataDialog(db, "categories_ext",
                                             [("id", " ", 16, None, ui.ReferenceTreeDelegate),
                                              ("pid", None, 0, None, None),
                                              ("name", "Name", -1, Qt.AscendingOrder, None),
                                              ("often", "Often", None, None, ui.ReferenceBoolDelegate),
                                              ("special", None, 0, None, None),
                                              ("children_count", None, None, None, None)],
                                             title="Choose category", search_field="name", tree_view=True)
        super().init_db("categories_ext", "name")


class TagSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db):
        self.dialog = ui.ReferenceDataDialog(db, "tags",
                                             [("id", None, 0, None, None),
                                              ("tag", "Tag", -1, Qt.AscendingOrder, None)],
                                             title="Choose tag", search_field="tag")
        super().init_db("tags", "tag")
