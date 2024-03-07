from PySide6.QtCore import Qt, QAbstractItemModel, QRect
from PySide6.QtWidgets import QTreeView, QHeaderView, QStyle, QStyleOptionHeaderV2
from PySide6.QtGui import QPainter, QIcon, QFontMetrics

#-----------------------------------------------------------------------------------------------------------------------
# Class that implements Footer for custom TreeViewWithFooter and TableViewWithFooter widgets
# Model should support footerData() method that will provide required data to display in the footer.
class FooterView(QHeaderView):
    def __init__(self, parent: QTreeView, table_header: QHeaderView):
        super().__init__(Qt.Horizontal, parent)
        self._span = {}
        self._sizes = {}
        self._parent = parent
        self._model = None
        self._linked_header = table_header
        self.setSectionResizeMode(QHeaderView.Fixed)
        self._linked_header.geometriesChanged.connect(self.on_header_geometry)
        self._linked_header.sectionResized.connect(self.on_header_resize)
        self._linked_header.sectionMoved.connect(self.on_header_move)

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

    def on_header_geometry(self):
        cr = self._parent.contentsRect()
        hs = self._linked_header.geometry()
        self.setGeometry(cr.left(), cr.top() + cr.height() - hs.height() + 1, hs.width(), hs.height())

    def on_header_resize(self, section: int, _old_size: int, new_size: int) -> None:
        if section not in self._span:   # Simply set size, if section doesn't span to multiple columns
            self.resizeSection(section, new_size)
            return
        if self._span[section] != section:   # Hide, if section gives its place to another section that is spanned over it
            self.setSectionHidden(section, True)
        size = 0   # Calculate a size of section that is spanned over other columns and resize it
        for i in [k for k, v in self._span.items() if v == self._span[section]]:
            size += new_size if i == section else self._linked_header.sectionSize(i)
        self.resizeSection(self._span[section], size)

    def on_header_move(self, _section: int, old: int, new: int) -> None:
        self.moveSection(old, new)

    def on_model_update(self, top_left, bottom_right, _role) -> None:
        self.headerDataChanged(Qt.Horizontal, top_left.column(), bottom_right.column())

    def set_span(self, section: int, span: list):
        span += [section]  # protection to have section itself included into span
        for i in span:
            self._span[i] = section
