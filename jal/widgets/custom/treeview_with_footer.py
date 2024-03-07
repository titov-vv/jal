from PySide6.QtCore import QAbstractItemModel
from PySide6.QtWidgets import QTreeView
from PySide6.QtGui import QResizeEvent
from .table_footer import FooterView

# ----------------------------------------------------------------------------------------------------------------------
# File implements TableViewWithFooter class that is a descendant of QTableView class with footer.
# Underlying model should support footerData(section, role) method in order to provide data for the footer.
# The footer is implemented as FooterView class that is derived from QHeaderView.
# ----------------------------------------------------------------------------------------------------------------------
class TreeViewWithFooter(QTreeView):
    def __init__(self, parent_view):
        self._parent_view = parent_view
        super().__init__(parent_view)
        self._header = self.header()
        self._footer = FooterView(self, self.header())
        self._header.sectionResized.connect(self._footer.on_header_resize)
        self._header.sectionMoved.connect(self._footer.on_header_move)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        m = self.viewportMargins()
        self.setViewportMargins(m.left(), m.top(), m.right(), m.top())  # Mirror top margin to bottom
        cr = self.contentsRect()
        header_size = self._header.geometry()
        self._footer.setGeometry(cr.left(), cr.top() + cr.height() - m.top() + 1, header_size.width(), header_size.height())

    def setModel(self, model: QAbstractItemModel) -> None:
        super().setModel(model)
        self._footer.setModel(model)

    def setColumnHidden(self, idx: int, hidden: bool) -> None:
        super().setColumnHidden(idx, hidden)
        self._footer.setSectionHidden(idx, hidden)
