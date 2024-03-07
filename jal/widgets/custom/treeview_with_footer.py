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
        self._footer = FooterView(self, self.header())

    def footer(self) -> FooterView:
        return self._footer

    # Create a bottom margin for footer placement (mirror of a top header margin)
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        margins = self.viewportMargins()
        self.setViewportMargins(margins.left(), margins.top(), margins.right(), margins.top())
        self._footer.on_header_geometry()

    def setModel(self, model: QAbstractItemModel) -> None:
        super().setModel(model)
        self._footer.setModel(model)

    def setColumnHidden(self, idx: int, hidden: bool) -> None:
        super().setColumnHidden(idx, hidden)
        self._footer.setSectionHidden(idx, hidden)
