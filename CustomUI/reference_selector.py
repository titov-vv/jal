from abc import ABC, abstractmethod

from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
from PySide2.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QCompleter

from CustomUI.reference_data import ReferenceDataDialog, ReferenceIntDelegate, ReferenceBoolDelegate


# To solve metaclass conflict
class SelectorMeta(type(ABC), type(QWidget)):
    pass


class AbstractReferenceSelector(ABC, QWidget, metaclass=SelectorMeta):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.completer = None
        self.p_selected_id = 0

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

        self.button.clicked.connect(self.on_button_clicked)

        self.selector_field = None
        self.dialog = None

    def getId(self):
        return self.p_selected_id

    def setId(self, selected_id):
        if self.p_selected_id == selected_id:
            return
        self.p_selected_id = selected_id
        self.dialog.Model.setFilter(f"id={selected_id}")                   ################
        row_idx = self.dialog.Model.index(0, 0).row()
        name = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex(self.selector_field))   ##############3
        self.name.setText(name)
        self.dialog.Model.setFilter("")
        self.changed.emit()

    @Signal
    def changed(self):
        pass

    selected_id = Property(int, getId, setId, notify=changed, user=True)

    def on_button_clicked(self):
        ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
        self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
        self.dialog.setFilter()               ################
        res = self.dialog.exec_()
        if res:
            self.selected_id = self.dialog.selected_id

    @abstractmethod
    def init_db(self, selector_field):
        self.selector_field = selector_field
        self.completer = QCompleter(self.dialog.Model)
        self.completer.setCompletionColumn(self.dialog.Model.fieldIndex(self.selector_field))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name.setCompleter(self.completer)
        self.completer.activated[QModelIndex].connect(self.on_completion)

    @Slot(QModelIndex)
    def on_completion(self, index):
        model = index.model()
        self.selected_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)


class PeerSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db, selector_field):
        self.dialog = ReferenceDataDialog(db, "agents_ext",
                                          [("id", " ", 16, None, None),
                                           ("pid", None, 0, None, None),
                                           ("name", "Name", -1, Qt.AscendingOrder, None),
                                           ("location", "Location", None, None, None),
                                           ("actions_count", "Docs count", None, None, ReferenceIntDelegate),
                                           ("children_count", None, None, None, None)],
                                          title="Choose peer", search_field="name", tree_view=True)
        super().init_db(selector_field)


class CategorySelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db, selector_field):
        self.dialog = ReferenceDataDialog(db, "categories_ext",
                                          [("id", " ", 16, None, None),
                                           ("pid", None, 0, None, None),
                                           ("name", "Name", -1, Qt.AscendingOrder, None),
                                           ("often", "Often", None, None, ReferenceBoolDelegate),
                                           ("special", None, 0, None, None),
                                           ("children_count", None, None, None, None)],
                                          title="Choose category", search_field="name", tree_view=True)
        super().init_db(selector_field)


class TagSelector(AbstractReferenceSelector):
    def __init__(self, parent=None):
        AbstractReferenceSelector.__init__(self, parent)

    def init_db(self, db, selector_field):
        self.dialog = ReferenceDataDialog(db, "tags",
                                          [("id", None, 0, None, None),
                                           ("tag", "Tag", -1, Qt.AscendingOrder, None)],
                                          title="Choose tag", search_field="tag")
        super().init_db(selector_field)
