from PySide6.QtCore import Qt, QAbstractItemModel, QRect, QTimer
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
        # A horizontal scrollbar appears and disappears without the view being resized (it is the columns that
        # changed, not the widget), and it takes the strip of the contents rect the footer is placed in - so the
        # footer has to be put back above it whenever it comes or goes. rangeChanged is what says so: the bar is
        # shown exactly while its range is non-empty.
        self._parent.horizontalScrollBar().rangeChanged.connect(self.on_scroll_range)
        # ... and while it is there the view is scrolled sideways under a footer that would otherwise stay put,
        # which would put every total under the wrong column
        self._parent.horizontalScrollBar().valueChanged.connect(self.on_scroll)

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

    # The footer goes into the strip the bottom viewport margin reserves for it - the mirror of the header's strip
    # at the top. It is placed against the VIEWPORT rather than against the bottom of the contents rect, because the
    # two are not the same whenever a horizontal scrollbar is shown: the bar takes the bottom of the contents rect
    # for itself, and a footer measured from there is drawn underneath it and can't be read.
    def on_header_geometry(self):
        viewport = self._parent.viewport().geometry()
        hs = self._linked_header.geometry()
        self.setGeometry(viewport.left(), viewport.bottom() + 1, hs.width(), hs.height())
        self.setOffset(self._linked_header.offset())

    # The scrollbar has just been shown or hidden (an empty range means it is not needed), so the strip the footer
    # is placed in has changed height. The geometry is recomputed once the change has been applied, because the bar
    # is still reported visible while the range that hides it is being set.
    def on_scroll_range(self, _minimum: int, _maximum: int) -> None:
        QTimer.singleShot(0, self, self.on_header_geometry)

    # Keeps the footer aligned with the columns while the view is scrolled sideways. The offset is taken from the
    # header rather than from the scrollbar, so that it follows whichever way the view scrolls (by pixel or by
    # section) instead of assuming one of them.
    def on_scroll(self, _value: int) -> None:
        self.setOffset(self._linked_header.offset())

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
