from PySide6.QtCore import Qt, QAbstractItemModel, QRect
from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtGui import QResizeEvent, QPainter

# ----------------------------------------------------------------------------------------------------------------------
# File implements TableViewWithFooter class that is a descendant of QTableView class with footer.
# Underlying model should support footerData(section, role) method in order to provide data for the footer.
# The footer is implemented as FooterView class that is derived from QHeaderView.
# ----------------------------------------------------------------------------------------------------------------------
class FooterView(QHeaderView):
    def __init__(self, parent: QTableView):
        super().__init__(Qt.Horizontal, parent)
        self._model = None
        self.setSectionResizeMode(QHeaderView.Fixed)

    def setModel(self, model: QAbstractItemModel) -> None:
        self._model = model
        self._model.dataChanged.connect(self.on_model_update)
        super().setModel(model)

    def paintSection(self, painter: QPainter, rect: QRect, idx: int) -> None:
        # First make standard painting by parent QHeaderView class method
        painter.save()
        super().paintSection(painter, rect, idx)
        painter.restore()
        # Clean footer content (by default QHeaderView puts sections names there
        inner_rect = rect.adjusted(self.lineWidth(), self.lineWidth(), -self.lineWidth(), -self.lineWidth())
        bg_color = self.palette().color(self.backgroundRole())
        painter.fillRect(inner_rect, bg_color)
        # Get data from model and write text with given font and position
        text = self._model.footerData(idx, role=Qt.DisplayRole)
        if text is None:
            return
        font = self._model.footerData(idx, role=Qt.FontRole)
        if font is not None:
            painter.setFont(font)
        alignment = self._model.footerData(idx, role=Qt.TextAlignmentRole)
        alignment = Qt.AlignCenter | Qt.AlignVCenter if alignment is None else alignment
        painter.drawText(inner_rect, alignment, f" {text} ")

    def on_header_resize(self, section: int, _old_size: int, new_size: int) -> None:
        self.resizeSection(section, new_size)

    def on_header_move(self, _section: int, old: int, new: int) -> None:
        self.moveSection(old, new)

    def on_model_update(self, top_left, bottom_right, _role) -> None:
        self.headerDataChanged(Qt.Horizontal, top_left.column(), bottom_right.column())


class TableViewWithFooter(QTableView):
    def __init__(self, parent_view):
        self._parent_view = parent_view
        super().__init__(parent_view)
        self._footer = FooterView(self)
        self._header = self.horizontalHeader()
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
