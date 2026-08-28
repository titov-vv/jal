import logging
from PySide6.QtCore import Qt, QBuffer, QByteArray, QIODevice, QObject, QSize, Signal, Slot
from PySide6.QtGui import QImage, QImageReader, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QToolButton
from jal.constants import IconOwner, IconSource, Setup
from jal.db.account import JalAccount
from jal.db.icon import JalIcons
from jal.db.settings import FolderFor, JalSettings
from jal.db.symbol import JalSymbol
from jal.db.tag import JalTag
from jal.widgets.helpers import refresh_grids
from jal.widgets.icons import JalIcon


# A picture the user offers is a logo, and a logo is small. Anything above this is a photograph handed over by
# mistake - it would be scaled down to 64 px all the same, after the whole file was read into memory.
MAX_SOURCE_SIZE = 4 * 1024 * 1024


# ----------------------------------------------------------------------------------------------------------------------
# Raised by the import below when what the user picked can't become an icon. Carries the text to show them.
class IconImportError(Exception):
    pass


# ----------------------------------------------------------------------------------------------------------------------
# The one way an image gets into the database, whatever it came from: decode, scale down, re-encode as PNG.
# Every source (a file, the clipboard, a drop) funnels through it, so what is stored is always one format at one
# size no matter what the user had.
#
# Scaling is one-way on purpose: an image larger than the stored size is shrunk, a smaller one is kept as it is.
# Blowing a 16x16 favicon up to 64x64 stores four times the bytes of the same blur.
def image_to_icon(image: QImage) -> bytes:
    if image.isNull():
        raise IconImportError(QApplication.translate("IconPicker", "The image can't be read"))
    size = Setup.ICON_STORED_SIZE
    if image.width() > size or image.height() > size:
        image = image.scaled(QSize(size, size), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise IconImportError(QApplication.translate("IconPicker", "The image can't be stored as PNG"))
    return bytes(data)


# Reads what a QImageReader was opened on - a file or a buffer of bytes - and returns the icon to store.
# An animated GIF is read as its first frame, which is what read() gives without being asked for more.
def _read_icon(reader: QImageReader) -> bytes:
    if not reader.canRead():
        raise IconImportError(QApplication.translate("IconPicker", "This is not an image: ") + reader.errorString())
    image = reader.read()
    if image.isNull():
        raise IconImportError(QApplication.translate("IconPicker", "The image can't be read: ") + reader.errorString())
    return image_to_icon(image)


# The icon to store from a file of any format Qt can read here (23 of them, SVG and WebP among them)
def icon_from_file(path: str) -> bytes:
    reader = QImageReader(path)
    if reader.device() is not None and reader.device().size() > MAX_SOURCE_SIZE:
        raise IconImportError(QApplication.translate("IconPicker", "The file is too large for an icon, ")
                              + f"{reader.device().size() // 1024} KB")
    return _read_icon(reader)


# The icon to store from raw bytes - what the clipboard and a drop hand over when they carry a file rather than
# a decoded image
def icon_from_data(data: bytes) -> bytes:
    if len(data) > MAX_SOURCE_SIZE:
        raise IconImportError(QApplication.translate("IconPicker", "The image is too large for an icon, ")
                              + f"{len(data) // 1024} KB")
    buffer = QBuffer(QByteArray(bytes(data)))
    buffer.open(QIODevice.ReadOnly)
    return _read_icon(QImageReader(buffer))


# Name of the element an icon belongs to, for a menu that offers icons of other elements to copy
def element_name(entity: int, item_id: int) -> str:
    if entity == IconOwner.Account:
        return JalAccount(item_id).name()
    if entity == IconOwner.Symbol:
        return JalSymbol(item_id).symbol()
    if entity == IconOwner.Tag:
        return JalTag(item_id).name()
    return ''


# ----------------------------------------------------------------------------------------------------------------------
# The menu that gives one element its icon, and the one place that writes what the user picked. It is built for one
# element and thrown away with the menu it filled, so nothing here has to follow a selection changing underneath it.
#
# Every write goes through JalIcons with IconSource.User, which is what makes it survive the next download.
class IconPicker(QObject):
    changed = Signal()

    def __init__(self, entity: int, item_id: int, parent=None):
        super().__init__(parent=parent)
        self._entity = entity
        self._item_id = item_id
        self._menu = None

    # True where a source can be asked for this element - only a listing has one
    def _downloadable(self) -> bool:
        return self._entity == IconOwner.Symbol

    def menu(self, parent=None) -> QMenu:
        self._menu = QMenu(parent)
        self._menu.addAction(self.tr("From a file..."), self.from_file)
        clipboard = self._menu.addAction(self.tr("From the clipboard"), self.from_clipboard)
        # A clipboard that isn't there at all is not an error: an offscreen platform has none
        content = QApplication.clipboard().mimeData()
        clipboard.setEnabled(content is not None and content.hasImage())
        gallery = self._menu.addMenu(self.tr("Already used in JAL"))
        self._fill_gallery(gallery)
        # Kept in the menu of an element nothing downloads rather than hidden there, so that the menu has one shape
        # wherever it is opened
        download = self._menu.addAction(self.tr("Download again"), self.download)
        download.setEnabled(self._downloadable())
        self._menu.addSeparator()
        if self._downloadable():
            # The two are different answers for a listing: one is remembered and the downloader honours it, the
            # other hands the listing back to it. For everything else nothing downloads, so they would look alike.
            self._menu.addAction(self.tr("No icon"), self.set_no_icon)
        remove = self._menu.addAction(self.tr("Remove"), self.remove)
        remove.setEnabled(JalIcons.stored(self._entity, self._item_id))
        return self._menu

    # The icons already in the database, one entry per distinct image, named after an element that carries it.
    # Icons of the same kind only: an account is given the logo of another account, and offering it 200 asset
    # logos would bury the two it might actually want.
    def _fill_gallery(self, menu: QMenu) -> None:
        size = JalIcons.grid_size()
        for item_id, image in JalIcons.distinct_images(self._entity):
            if item_id == self._item_id:
                continue     # the icon this element already has is not something to copy onto it
            action = menu.addAction(JalIcons.icon(self._entity, item_id, size), element_name(self._entity, item_id))
            action.triggered.connect(lambda checked=False, data=image: self._store(data))
        menu.setEnabled(not menu.isEmpty())

    # Stores what was picked and lets everything that shows an icon know it has to paint again
    def _store(self, image: bytes) -> None:
        if JalIcons.store(self._entity, self._item_id, image, IconSource.User):
            refresh_grids()
            self.changed.emit()

    @Slot()
    def from_file(self) -> None:
        formats = ' '.join(f"*.{bytes(x).decode()}" for x in QImageReader.supportedImageFormats())
        path, _filter = QFileDialog.getOpenFileName(None, self.tr("Choose an image"),
                                                    JalSettings().getRecentFolder(FolderFor.Icon, '.'),
                                                    self.tr("Images") + f" ({formats})")
        if not path:
            return
        JalSettings().setRecentFolder(FolderFor.Icon, path)
        self.import_from(lambda: icon_from_file(path))

    @Slot()
    def from_clipboard(self) -> None:
        image = QApplication.clipboard().image()
        self.import_from(lambda: image_to_icon(image))

    # Puts the element back into the 'never asked' state, so the downloader may try again for a listing and an
    # account or a tag simply loses its picture
    @Slot()
    def remove(self) -> None:
        JalIcons.forget(self._entity, self._item_id)
        refresh_grids()
        self.changed.emit()

    # A deliberate absence, stored as the user's own answer - no download ever writes over it
    @Slot()
    def set_no_icon(self) -> None:
        self._store(b'')

    # Asks the source about this listing once more. It has to be forgotten first, because a listing that was
    # already asked about is not asked again (see QuoteDownloader.download_icons).
    @Slot()
    def download(self) -> None:
        from jal.net.downloader import QuoteDownloader   # deferred: the net layer pulls in a lot for one action
        JalIcons.forget(self._entity, self._item_id)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            QuoteDownloader().download_icons([JalSymbol(self._item_id)])
        finally:
            QApplication.restoreOverrideCursor()
        refresh_grids()
        self.changed.emit()

    # Runs one of the imports above and shows what went wrong instead of leaving it in the log
    def import_from(self, source) -> None:
        try:
            self._store(source())
        except IconImportError as error:
            logging.warning(str(error))
            QMessageBox().warning(None, self.tr("Can't use this image"), str(error), QMessageBox.Ok)


# ----------------------------------------------------------------------------------------------------------------------
# The picker as a field of a dialog: a button showing the icon of the element it is bound to, opening the menu above
# when it is pressed. It also takes an image dropped onto it, which is how a logo dragged out of a browser arrives.
class IconButton(QToolButton):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._entity = 0
        self._item_id = 0
        self._picker = None
        # Framed rather than flat: it sits beside the Add/Remove buttons of a grid in one dialog and beside a line
        # edit in another, and a button nobody can see until they hover it is not a way to be found.
        self.setAcceptDrops(True)
        self.setToolTip(self.tr("Set the icon of this element"))
        self.clicked.connect(self.onClicked)

    # The element this button decorates. Given after construction, because a dialog builds its widgets before it
    # knows which row it was opened on.
    def setElement(self, entity: int, item_id: int) -> None:
        self._entity = entity
        self._item_id = item_id
        self.updateIcon()

    def updateIcon(self) -> None:
        size = JalIcons.grid_size()
        self.setIconSize(QSize(size, size))
        icon = JalIcons.icon(self._entity, self._item_id, size)
        # An element with no icon of its own gets the same glyph every "opens a chooser" button in the application
        # wears, so that the button says what it does instead of looking like an empty square. A mark of its own is
        # glyph work and belongs with the rest of it (S5).
        self.setIcon(icon if not icon.isNull() else JalIcon[JalIcon.DETAILS])
        self.setEnabled(bool(self._item_id))

    @Slot()
    def onClicked(self) -> None:
        if not self._item_id:
            return
        self._picker = IconPicker(self._entity, self._item_id, parent=self)
        self._picker.changed.connect(self.onChanged)
        self._picker.menu(self).exec(self.mapToGlobal(self.rect().bottomLeft()))

    @Slot()
    def onChanged(self) -> None:
        self.updateIcon()
        self.changed.emit()

    def dragEnterEvent(self, event) -> None:
        if self._item_id and (event.mimeData().hasImage() or event.mimeData().hasUrls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        picker = IconPicker(self._entity, self._item_id, parent=self)
        picker.changed.connect(self.onChanged)
        if event.mimeData().hasImage():
            dropped = event.mimeData().imageData()   # a QImage as a rule, but a bare variant on some platforms
            image = dropped if isinstance(dropped, QImage) else QImage(dropped)
            picker.import_from(lambda: image_to_icon(image))
        elif event.mimeData().hasUrls():
            path = event.mimeData().urls()[0].toLocalFile()
            if path:
                picker.import_from(lambda: icon_from_file(path))
        event.acceptProposedAction()
