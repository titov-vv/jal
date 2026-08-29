import logging
from PySide6.QtCore import Qt, QByteArray, QRectF, QSize
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication
from jal.constants import IconOwner, IconSource, PredefinedAsset
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.widgets.icons import JalIcon
from jal.widgets.theme import Theme


# WCAG contrast ratio of two opaque colours, 1.0 (identical) to 21.0 (black on white). The same formula
# jal.widgets.theme derives every colour with - repeated here because this module measures rather than derives.
def _luminance(color: QColor) -> float:
    def channel(value: int) -> float:
        value = value / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def _contrast(first: QColor, second: QColor) -> float:
    lighter, darker = max(_luminance(first), _luminance(second)), min(_luminance(first), _luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


# ----------------------------------------------------------------------------------------------------------------------
# The store behind the 'icons' table: the picture of one particular element - this account, this listing, this tag -
# as opposed to a glyph, which marks a kind of thing and lives as a file in the package (see jal.widgets.icons).
#
# An element is described by the kind of thing it is (IconOwner) and its id inside that kind's table, so an entity
# that wants icons later needs no schema change - only a value of IconOwner and an AFTER DELETE trigger to take its
# icons with it.
#
# Two orthogonal facts carry four answers, which is what keeps the user's decision safe from the next download:
#   no row              nothing has ever looked for an icon of this element
#   b'' + Downloaded    the source was asked and had none - so it is not asked again
#   b'' + User          the user decided this element shows no icon
#   bytes + <source>    here it is
#
# Everything here is a classmethod: there is one store, not one per element, and a caller that paints a grid must
# not pay for an object per row. The single instance behind _cached exists only to put this class into the list
# JalDB.invalidate_cache() walks, which is kept by instance and not by class.
class JalIcons(JalDB):
    _cached = None      # the one instance that carries this class into JalDB's cache invalidation
    _present = None     # {(entity, item_id)} of the elements that have an image, read in one query
    _blank = None       # {(entity, item_id)} of the elements the user decided show no picture at all
    _currencies = None  # {listing id: ticker} of every listing of a currency, read in one query
    _pixmaps = {}       # (entity, item_id, size) -> QPixmap, decoded once and painted many times
    _indent = None      # cached value of the preference below - it is asked once per row painted
    _palette = None     # the palette the pixmaps above were made for: they carry a ground-dependent treatment

    # A picture that can't be told from the ground it is painted on is given a plate to sit on, and nothing else
    # is touched. The measurement below decides which is which, on the pixmap that will actually be drawn.
    #
    # 'Told from the ground' is not lightness alone: an orange logo on white has a WCAG contrast of 2.2 and is
    # perfectly visible, because the eye separates it by COLOUR. Both are therefore allowed to count as ink, and
    # that is what keeps every saturated logo off the plate - measured over the live collection at the size a row
    # paints, 6 pictures of 202 need one on a dark row and none does on a light one.
    _INK_CONTRAST = 3.0        # WCAG ratio at which ink is told from its ground by lightness
    _INK_DISTANCE = 90         # ... or by colour, across the RGB cube (of 441)
    _INK_MINIMUM = 0.02        # less ink than this share of the box and there is nothing to see at all

    # Whether a row whose element has no icon still keeps the space one would take. With it the names of a list
    # start at one and the same place whether or not the thing they name carries a logo; without it a column of
    # elements that mostly have none isn't made narrower for the few that do. It is the user's call, so it is a
    # preference (see the settings registry) rather than a decision taken here.
    INDENT_KEY = "AlignRowsByIcons"
    INDENT_DEFAULT = True

    # The kind of element a row of a table stands for - all a table needs to join the icon-carrying columns of the
    # interface, together with an AFTER DELETE trigger of its own. A table that is absent from here has no icons.
    _ENTITY_OF_TABLE = {
        "accounts": IconOwner.Account,
        "asset_symbol": IconOwner.Symbol,
        "tags": IconOwner.Tag
    }

    # The kind of element the rows of the given table are, or None if that table has no icons
    @classmethod
    def entity_of_table(cls, table: str):
        return cls._ENTITY_OF_TABLE.get(table)

    # A classmethod so that it can be called on the class as well as on the instance JalDB.invalidate_cache() holds
    @classmethod
    def invalidate_cache(cls) -> None:
        cls._present = None
        cls._blank = None
        cls._currencies = None
        cls._pixmaps = {}
        cls._indent = None   # another database has preferences of its own

    # Drops the cached preference, so that the next row painted reads it from the database again
    @classmethod
    def invalidate_indent(cls) -> None:
        cls._indent = None

    # True if a row with no icon keeps the space of one (see INDENT_KEY above)
    @classmethod
    def rows_are_indented(cls) -> bool:
        if cls._indent is None:
            try:
                cls._indent = JalSettings().getBool(cls.INDENT_KEY, cls.INDENT_DEFAULT)
            except RuntimeError:
                return cls.INDENT_DEFAULT   # No database open yet - a view may be built before it is
        return cls._indent

    # JalIcons maintains single cache available for all instances
    @classmethod
    def class_cache(cls) -> True:
        return True

    # Puts this class into the list JalDB.invalidate_cache() walks, once - everything cached below is dropped by it
    @classmethod
    def _register(cls) -> None:
        if cls._cached is None:
            cls._cached = cls(cached=True)

    # The set of elements that have an image to paint. One query for the whole application, so the answer that
    # nearly every row gets - "this one has none" - never reaches the database. The elements the user asked to
    # show nothing at all are separated out by the same pass: they are the same rows, told apart by 'source'.
    @classmethod
    def _known(cls) -> set:
        if cls._present is None:
            cls._register()
            cls._present, cls._blank = set(), set()
            query = cls._exec("SELECT entity, item_id, length(image), source FROM icons")
            while query.next():
                entity, item_id, length, source = cls._read_record(query)
                if length:
                    cls._present.add((entity, item_id))
                elif source == IconSource.User:
                    cls._blank.add((entity, item_id))
        return cls._present

    # The set of elements the user decided show no picture at all - the b'' + User of the four states above.
    # It is not "has no icon": that is nearly every element, and it is the one answer a fallback may fill in.
    @classmethod
    def _declined(cls) -> set:
        cls._known()    # both sets are read by one query
        return cls._blank

    # {listing id: ticker} of every listing of a currency.
    @classmethod
    def _currency_tickers(cls) -> dict:
        if cls._currencies is None:
            cls._register()
            cls._currencies = {}
            query = cls._exec("SELECT s.id, s.symbol FROM asset_symbol AS s "
                              "LEFT JOIN assets AS a ON a.id=s.asset_id WHERE a.type_id=:money",
                              [(":money", PredefinedAsset.Money)])
            while query is not None and query.next():
                listing_id, ticker = cls._read_record(query)
                cls._currencies[listing_id] = ticker
        return cls._currencies

    # True if this element has an image stored. Answered from the cache above, so it is free to ask per row.
    @classmethod
    def has_image(cls, entity: int, item_id: int) -> bool:
        return (entity, item_id) in cls._known()

    # The stored image as bytes, b'' if the element is known to have none, or None if it was never asked about.
    # The three answers are different things and callers are expected to keep them apart.
    @classmethod
    def image(cls, entity: int, item_id: int):
        image = cls._read("SELECT image FROM icons WHERE entity=:entity AND item_id=:id",
                          [(":entity", entity), (":id", item_id)])
        if image is None:
            return None
        # A zero-length BLOB is reported as an empty string by the QSQLITE driver, so it arrives here as '' and
        # not as b'' - which is the answer meant by it, and not the 'never asked' that None stands for.
        return bytes(image) if image else b''

    # Who wrote the row of this element (see IconSource), or None if there is no row.
    @classmethod
    def source(cls, entity: int, item_id: int):
        return cls._read("SELECT source FROM icons WHERE entity=:entity AND item_id=:id",
                         [(":entity", entity), (":id", item_id)])

    # True if this element was already asked about, no matter what the answer was. A download uses it to ask
    # about a listing exactly once ever, whether the source had an icon or not.
    @classmethod
    def stored(cls, entity: int, item_id: int) -> bool:
        return cls.source(entity, item_id) is not None

    # Stores the image of one element, replacing whatever it had. Empty data means "this element has no icon"
    # and is a stored answer like any other, not an erasure - see forget() for that.
    # A download never writes over what the user stored, neither an image nor a deliberate absence: the user
    # picked that, and a source publishing something new later is not a reason to undo it.
    # Returns True if the row was written.
    @classmethod
    def store(cls, entity: int, item_id: int, image: bytes, source: int) -> bool:
        if not item_id:
            # JalDB.tr() is an instance method and there is no instance here - the context is spelled out instead
            logging.error(QApplication.translate("JalDB", "Can't store an icon of an unknown element"))
            return False
        if source == IconSource.Downloaded and cls.source(entity, item_id) == IconSource.User:
            return False
        query = cls._exec("INSERT OR REPLACE INTO icons (entity, item_id, image, source) "
                          "VALUES (:entity, :id, :image, :source)",
                          [(":entity", entity), (":id", item_id),
                           (":image", QByteArray(bytes(image))), (":source", source)], commit=True)
        if query is None:
            return False
        cls._remember(entity, item_id, image, source)
        return True

    # Drops everything stored about this element, so that it is 'never asked about' again. For a listing that
    # hands it back to the downloader - a deliberate second chance, useful when a source has published a better
    # logo since; for an element nothing downloads it simply clears the picture.
    @classmethod
    def forget(cls, entity: int, item_id: int) -> None:
        cls._exec("DELETE FROM icons WHERE entity=:entity AND item_id=:id",
                  [(":entity", entity), (":id", item_id)], commit=True)
        cls._remember(entity, item_id, b'')

    # Puts what was just written into the cached sets instead of re-reading them for one row, and drops what was
    # decoded from the image this element used to have. 'source' is None where the row was deleted rather than
    # written. Sets that aren't loaded are left alone - they read the truth when they are first asked.
    @classmethod
    def _remember(cls, entity: int, item_id: int, image: bytes, source=None) -> None:
        if cls._present is not None:
            cls._present.discard((entity, item_id))
            cls._blank.discard((entity, item_id))
            if image:
                cls._present.add((entity, item_id))
            elif source == IconSource.User:
                cls._blank.add((entity, item_id))
        cls._pixmaps = {key: value for key, value in cls._pixmaps.items() if key[:2] != (entity, item_id)}

    # The icon of one element scaled to the given square size, or an empty QIcon if it has none. Images are
    # stored at Setup.ICON_STORED_SIZE and painted much smaller, so the result is cached per element and size:
    # a grid asks for the same picture once per row on every repaint.
    @classmethod
    def icon(cls, entity: int, item_id: int, size: int) -> QIcon:
        if not cls.has_image(entity, item_id):
            return QIcon()
        cls._forget_stale_palette()
        key = (entity, item_id, size)
        if key not in cls._pixmaps:
            pixmap = QPixmap()
            if not pixmap.loadFromData(cls.image(entity, item_id)):
                logging.warning(f"Can't decode the icon stored for element {item_id} of kind {entity}")
                return QIcon()
            pixmap = pixmap.scaled(QSize(size, size), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            cls._pixmaps[key] = pixmap if cls._is_readable(pixmap) else cls._on_plate(pixmap, size)
        return QIcon(cls._pixmaps[key])

    # Everything cached above was made to be painted on one particular ground, so a change of palette - the user
    # switching the desktop between light and dark - drops it all.
    @classmethod
    def _forget_stale_palette(cls) -> None:
        palette = QApplication.palette().cacheKey()
        if cls._palette != palette:
            cls._palette = palette
            cls._pixmaps = {}

    # True if enough of this picture can be told from the ground a row paints it on. Measured on the pixmap that
    # will be drawn - a few hundred pixels, once per picture and size - and never on the stored image, which is
    # larger and is not what the eye gets.
    @classmethod
    def _is_readable(cls, pixmap: QPixmap) -> bool:
        ground = QApplication.palette().base().color()
        image = pixmap.toImage()
        area = image.width() * image.height()
        if not area:
            return True
        ink = 0
        for y in range(image.height()):
            for x in range(image.width()):
                pixel = image.pixelColor(x, y)
                weight = pixel.alphaF()
                blended = QColor(round(pixel.red() * weight + ground.red() * (1 - weight)),
                                 round(pixel.green() * weight + ground.green() * (1 - weight)),
                                 round(pixel.blue() * weight + ground.blue() * (1 - weight)))
                distance = ((blended.red() - ground.red()) ** 2 + (blended.green() - ground.green()) ** 2
                            + (blended.blue() - ground.blue()) ** 2) ** 0.5
                if _contrast(blended, ground) >= cls._INK_CONTRAST or distance >= cls._INK_DISTANCE:
                    ink += 1
        return ink / area >= cls._INK_MINIMUM

    # The same picture on a plate of the ground's opposite, rounded so that it reads as a chip rather than a patch.
    # The picture keeps its size - the plate is the box the row already reserved, and the row does not grow.
    @classmethod
    def _on_plate(cls, pixmap: QPixmap, size: int) -> QPixmap:
        plated = QPixmap(QSize(size, size))
        plated.fill(Qt.transparent)
        painter = QPainter(plated)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size, size), size / 5, size / 5)
        painter.fillPath(path, Theme.plate())
        inset = max(1, size // 8)
        picture = pixmap.scaled(QSize(size - 2 * inset, size - 2 * inset), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap(round((size - picture.width()) / 2), round((size - picture.height()) / 2), picture)
        painter.end()
        return plated

    # The sign a currency listing wears where no picture is stored for it.
    @classmethod
    def _currency_sign(cls, entity: int, item_id: int) -> QIcon:
        if entity != IconOwner.Symbol or (entity, item_id) in cls._declined():
            return QIcon()
        ticker = cls._currency_tickers().get(item_id, '')
        return JalIcon.money_glyph(ticker) if ticker else QIcon()

    # What a cell of an icon-carrying column shows: the icon of this element, the sign of the currency it is if it
    # is one and has no icon, or the empty space of an icon - and nothing at all if the user asked for no such
    # space (see rows_are_indented).
    @classmethod
    def decoration(cls, entity: int, item_id: int, size: int):
        icon = cls.icon(entity, item_id, size)
        if icon.isNull():
            icon = cls._currency_sign(entity, item_id)
        return icon if not icon.isNull() else cls.spacer(size)

    # One entry per distinct image stored for elements of the given kind, as (item_id, image) of the first element
    # that carries it - what the picker offers when an icon already in the database is to be given to one more
    # element. Distinct by the image itself, so five accounts sharing one logo are offered once.
    @classmethod
    def distinct_images(cls, entity: int) -> list:
        images = []
        query = cls._exec("SELECT MIN(item_id) AS item_id, image FROM icons "
                          "WHERE entity=:entity AND length(image)>0 GROUP BY image ORDER BY item_id",
                          [(":entity", entity)])
        while query is not None and query.next():
            item_id, image = cls._read_record(query)
            images.append((int(item_id), bytes(image)))
        return images

    # The place an icon would take, for a row that has none to show: an invisible pixmap while rows are indented,
    # and nothing when they are not.
    @classmethod
    def spacer(cls, size: int):
        return cls.blank(size) if cls.rows_are_indented() else None

    # The size a grid paints an icon at: the height of the application font, which is the number
    # set_grids_metrics() gives every view as its icon size. Asked by the models, which see no view of their own -
    # a view whose font is not the application's gets an icon smaller than the space it reserved, never a larger
    # one, so a row can't grow because of this.
    @classmethod
    def grid_size(cls) -> int:
        return QFontMetrics(QApplication.font()).height()

    # An empty square of the given size, cached like the images beside it. The key can't collide with a real
    # element's - those are keyed by an integer kind and an integer id.
    @classmethod
    def blank(cls, size: int) -> QIcon:
        key = (None, None, size)
        if key not in cls._pixmaps:
            pixmap = QPixmap(QSize(size, size))
            pixmap.fill(Qt.transparent)
            cls._pixmaps[key] = pixmap
        return QIcon(cls._pixmaps[key])
