from PySide6.QtCore import Qt, QAbstractItemModel, QRect
from PySide6.QtWidgets import QTableView, QHeaderView, QStyle, QStyleOptionHeaderV2
from PySide6.QtGui import QResizeEvent, QPainter, QIcon, QFontMetrics

# ----------------------------------------------------------------------------------------------------------------------
# File implements TableViewWithFooter class that is a descendant of QTableView class with footer.
# Underlying model should support footerData(section, role) method in order to provide data for the footer.
# The footer is implemented as FooterView class that is derived from QHeaderView.
# ----------------------------------------------------------------------------------------------------------------------
class FooterView(QHeaderView):   # The same class as in treeview_with_footer.py (to keep everything in one module)
    def __init__(self, parent: QTableView):
        super().__init__(Qt.Horizontal, parent)
        self._model = None
        self.setSectionResizeMode(QHeaderView.Fixed)

    def setModel(self, model: QAbstractItemModel) -> None:
        self._model = model
        self._model.dataChanged.connect(self.on_model_update)
        super().setModel(model)

    def paintSection(self, painter: QPainter, rect: QRect, idx: int) -> None:
        painter.save()
        opt = QStyleOptionHeaderV2()
        self.initStyleOption(opt)
        self.initStyleOptionForIndex(opt, idx)
        opt.rect = rect
        text = self._model.footerData(idx, role=Qt.DisplayRole)
        opt.text = '' if text is None else text
        font = self._model.footerData(idx, role=Qt.FontRole)
        if font is not None:
            opt.fontMetrics = QFontMetrics(font)
            painter.setFont(font)
        icon = self._model.footerData(idx, role=Qt.DecorationRole)
        opt.iconAlignment = Qt.AlignVCenter
        opt.icon = QIcon() if icon is None else icon
        alignment = self._model.footerData(idx, role=Qt.TextAlignmentRole)
        opt.textAlignment = Qt.AlignCenter | Qt.AlignVCenter if alignment is None else alignment
        self.style().drawControl(QStyle.CE_Header, opt, painter, self)
        painter.restore()

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
