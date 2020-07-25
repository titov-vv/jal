# from PySide2.QtCore import Qt, Signal, Property, Slot, QModelIndex
# from PySide2.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QCompleter
#
# from CustomUI.reference_data import ReferenceDataDialog, ReferenceBoolDelegate
#
#
# class CategorySelector(QWidget):
#     def __init__(self, parent=None):
#         QWidget.__init__(self, parent)
#         self.completer = None
#         self.p_category_id = 0
#
#         self.layout = QHBoxLayout()
#         self.layout.setMargin(0)
#         self.name = QLineEdit()
#         self.name.setText("")
#         self.layout.addWidget(self.name)
#         self.button = QPushButton("...")
#         self.button.setFixedWidth(self.button.fontMetrics().width(" ... "))
#         self.layout.addWidget(self.button)
#         self.setLayout(self.layout)
#
#         self.setFocusProxy(self.name)
#
#         self.button.clicked.connect(self.OnButtonClicked)
#         self.dialog = None
#
#     def getId(self):
#         return self.p_category_id
#
#     def setId(self, category_id):
#         if self.p_category_id == category_id:
#             return
#         self.p_category_id = category_id
#         self.dialog.Model.setFilter(f"id={category_id}")
#         row_idx = self.dialog.Model.index(0, 0).row()
#         name = self.dialog.Model.record(row_idx).value(self.dialog.Model.fieldIndex("name"))
#         self.name.setText(name)
#         self.dialog.Model.setFilter("")
#         self.changed.emit()
#
#     @Signal
#     def changed(self):
#         pass
#
#     category_id = Property(int, getId, setId, notify=changed, user=True)
#
#     def init_DB(self, db):
#         self.dialog = ReferenceDataDialog(db, "categories_ext",
#                                           [("id", " ", 16, None, None),
#                                            ("pid", None, 0, None, None),
#                                            ("name", "Name", -1, Qt.AscendingOrder, None),
#                                            ("often", "Often", None, None, ReferenceBoolDelegate),
#                                            ("special", None, 0, None, None),
#                                            ("children_count", None, None, None, None)],
#                                           title="Choose category", search_field="name", tree_view=True)
#         self.completer = QCompleter(self.dialog.Model)
#         self.completer.setCompletionColumn(self.dialog.Model.fieldIndex("name"))
#         self.completer.setCaseSensitivity(Qt.CaseInsensitive)
#         self.name.setCompleter(self.completer)
#         self.completer.activated[QModelIndex].connect(self.OnCompletion)
#
#     def OnButtonClicked(self):    # TODO: setFilter works for tree here and limits only to current level - fix it
#         ref_point = self.mapToGlobal(self.name.geometry().bottomLeft())
#         self.dialog.setGeometry(ref_point.x(), ref_point.y(), self.dialog.width(), self.dialog.height())
#         self.dialog.setFilter()
#         res = self.dialog.exec_()
#         if res:
#             self.category_id = self.dialog.selected_id
#
#     @Slot(QModelIndex)
#     def OnCompletion(self, index):
#         model = index.model()
#         self.category_id = model.data(model.index(index.row(), 0), Qt.DisplayRole)
