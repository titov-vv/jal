from PySide6.QtCore import Qt, QAbstractItemModel, QRect
from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtGui import QResizeEvent, QPainter
from jal.constants import DataRole

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
        text = self._model.footerData(idx, role=DataRole.FOOTER_DATA)
        font = self._model.footerData(idx, role=DataRole.FOOTER_FONT)
        alignment = self._model.footerData(idx, role=DataRole.FOOTER_ALIGNMENT)
        alignment = Qt.AlignCenter | Qt.AlignVCenter if alignment is None else alignment
        painter.save()
        super().paintSection(painter, rect, idx)
        painter.restore()
        inner_rect = rect.adjusted(self.lineWidth(), self.lineWidth(), -self.lineWidth(), -self.lineWidth())
        bg_color = self.palette().color(self.backgroundRole())
        painter.fillRect(inner_rect, bg_color)  # Empty the area
        if font is not None:
            painter.setFont(font)
        painter.drawText(inner_rect, alignment, text)

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
