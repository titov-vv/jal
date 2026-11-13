from PySide6.QtCore import Qt, Signal, QBuffer, QByteArray, QRectF, QSize
from PySide6.QtGui import QBrush, QColor, QImageReader, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView
from jal.widgets.theme import Theme, Meaning

PAPER = QColor(Qt.white)


#-----------------------------------------------------------------------------------------------------------------------
# The page images of a scanned receipt, one under another and fitted to the widget's width; Ctrl + wheel zooms in.
# Rows of the receipt are given as (page, [x, y, width, height]) in the pixels of that page's image; pages are
# numbered from 1.
class ReceiptScanView(QGraphicsView):
    PAGE_GAP = 40               # between pages, in image pixels
    LOAD_WIDTH = 1400           # a wider image is scaled down to it when loaded, to keep the memory of a long receipt
    MARK_ALPHA = 80
    MAX_ZOOM = 4.0              # of the width-fitted picture
    row_activated = Signal(int)     # key of an offered row that was double-clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._zoom = 1.0
        self._tops = {}             # page -> y of its image in the scene
        self._marks = []            # items of the rows shown by show_rows()
        self._offers = {}           # key -> item of a row offered by offer_rows()

    def clear(self):
        self.scene().clear()
        self.scene().setSceneRect(QRectF())
        self._tops, self._marks, self._offers = {}, [], {}

    # Shows the pages given as (page, image file bytes); a page that isn't a readable image is left out
    def set_pages(self, pages: list):
        self.clear()
        self._zoom = 1.0
        top, width = 0, 0
        for page, data in pages:
            content = QByteArray(data)     # QBuffer doesn't own it
            buffer = QBuffer(content)
            buffer.open(QBuffer.ReadOnly)
            reader = QImageReader(buffer)
            size = reader.size()
            if not size.isValid() or size.isEmpty():
                continue
            if size.width() > self.LOAD_WIDTH:
                reader.setScaledSize(QSize(self.LOAD_WIDTH, round(size.height() * self.LOAD_WIDTH / size.width())))
            image = reader.read()
            if image.isNull():
                continue
            item = self.scene().addPixmap(QPixmap.fromImage(image))
            item.setTransformationMode(Qt.SmoothTransformation)
            item.setScale(size.width() / image.width())     # the scene is in the pixels of the original image
            item.setPos(0, top)
            self._tops[page] = top
            top += size.height() + self.PAGE_GAP
            width = max(width, size.width())
        if self._tops:
            self.scene().setSceneRect(QRectF(0, 0, width, top - self.PAGE_GAP))
        self._fit_width()

    def has_pages(self) -> bool:
        return bool(self._tops)

    def _rect(self, page: int, box) -> QRectF:
        return QRectF(box[0], self._tops[page] + box[1], box[2], box[3])

    # Marks the rows and scrolls to them; rows of a page that isn't shown are left out
    def show_rows(self, rows: list):
        for item in self._marks:
            self.scene().removeItem(item)
        color = QColor(Theme.text(Meaning.INFO, PAPER))
        color.setAlpha(self.MARK_ALPHA)
        rects = [self._rect(page, box) for page, box in rows if page in self._tops]
        self._marks = [self.scene().addRect(x, QPen(Qt.NoPen), QBrush(color)) for x in rects]
        if rects:
            area = rects[0]
            for x in rects[1:]:
                area = area.united(x)
            self.ensureVisible(area, 0, round(self.viewport().height() / 4))

    # Outlines the rows {key: (page, box)} that a double click activates
    def offer_rows(self, rows: dict):
        for item in self._offers.values():
            self.scene().removeItem(item)
        self._offers = {}
        pen = QPen(Theme.text(Meaning.WARNING, PAPER), 0, Qt.DashLine)
        for key, (page, box) in rows.items():
            if page in self._tops:
                self._offers[key] = self.scene().addRect(self._rect(page, box), pen)

    def withdraw_row(self, key: int):
        item = self._offers.pop(key, None)
        if item is not None:
            self.scene().removeItem(item)

    def offered_rows(self) -> list:
        return sorted(self._offers)

    def sizeHint(self) -> QSize:
        return QSize(480, 640)

    def _fit_width(self):
        width = self.scene().sceneRect().width()
        if width > 0:
            scale = self._zoom * self.viewport().width() / width
            self.setTransform(QTransform.fromScale(scale, scale))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_width()

    def wheelEvent(self, event):
        if not event.modifiers() & Qt.ControlModifier:
            super().wheelEvent(event)
            return
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._zoom = min(max(self._zoom * (1.25 if event.angleDelta().y() > 0 else 0.8), 1.0), self.MAX_ZOOM)
        self._fit_width()
        self.setTransformationAnchor(QGraphicsView.NoAnchor)

    def mouseDoubleClickEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        key = next((key for key, item in self._offers.items() if item.rect().contains(point)), None)
        if key is None:
            super().mouseDoubleClickEvent(event)
        else:
            self.row_activated.emit(key)
