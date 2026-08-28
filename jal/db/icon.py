import logging
from PySide6.QtCore import Qt, QByteArray, QSize
from PySide6.QtGui import QFontMetrics, QIcon, QPixmap
from PySide6.QtWidgets import QApplication
from jal.constants import IconOwner, IconSource
from jal.db.db import JalDB
from jal.db.settings import JalSettings


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
    _pixmaps = {}       # (entity, item_id, size) -> QPixmap, decoded once and painted many times
    _indent = None      # cached value of the preference below - it is asked once per row painted

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

    # The set of elements that have an image to paint. One query for the whole application, so the answer that
    # nearly every row gets - "this one has none" - never reaches the database.
    @classmethod
    def _known(cls) -> set:
        if cls._present is None:
            if cls._cached is None:
                cls._cached = cls(cached=True)   # registers this class for cache invalidation, once
            cls._present = set()
            query = cls._exec("SELECT entity, item_id FROM icons WHERE length(image)>0")
            while query.next():
                cls._present.add(tuple(cls._read_record(query)))
        return cls._present

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
        cls._remember(entity, item_id, bool(image))
        return True

    # Drops everything stored about this element, so that it is 'never asked about' again. For a listing that
    # hands it back to the downloader - a deliberate second chance, useful when a source has published a better
    # logo since; for an element nothing downloads it simply clears the picture.
    @classmethod
    def forget(cls, entity: int, item_id: int) -> None:
        cls._exec("DELETE FROM icons WHERE entity=:entity AND item_id=:id",
                  [(":entity", entity), (":id", item_id)], commit=True)
        cls._remember(entity, item_id, False)

    # Puts what was just written into the cache instead of re-reading the whole 'who has one' set for one row,
    # and drops what was decoded from the image this element used to have. A set that isn't loaded is left alone -
    # it reads the truth when it is first asked.
    @classmethod
    def _remember(cls, entity: int, item_id: int, has_image: bool) -> None:
        if cls._present is not None:
            if has_image:
                cls._present.add((entity, item_id))
            else:
                cls._present.discard((entity, item_id))
        cls._pixmaps = {key: value for key, value in cls._pixmaps.items() if key[:2] != (entity, item_id)}

    # The icon of one element scaled to the given square size, or an empty QIcon if it has none. Images are
    # stored at Setup.ICON_STORED_SIZE and painted much smaller, so the result is cached per element and size:
    # a grid asks for the same picture once per row on every repaint.
    @classmethod
    def icon(cls, entity: int, item_id: int, size: int) -> QIcon:
        if not cls.has_image(entity, item_id):
            return QIcon()
        key = (entity, item_id, size)
        if key not in cls._pixmaps:
            pixmap = QPixmap()
            if not pixmap.loadFromData(cls.image(entity, item_id)):
                logging.warning(f"Can't decode the icon stored for element {item_id} of kind {entity}")
                return QIcon()
            cls._pixmaps[key] = pixmap.scaled(QSize(size, size), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QIcon(cls._pixmaps[key])

    # What a cell of an icon-carrying column shows: the icon of this element, or the empty space of one when it has
    # none - and nothing at all if the user asked for no such space (see rows_are_indented).
    @classmethod
    def decoration(cls, entity: int, item_id: int, size: int):
        icon = cls.icon(entity, item_id, size)
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
