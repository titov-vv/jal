import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlparse
from PySide6.QtCore import Qt, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QIcon, QImage

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_assets, symbol_id_for
from constants import IconOwner, IconSource, PredefinedAsset, PredefinedAccountType
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.icon import JalIcons

PNG = b'\x89PNG\r\n\x1a\n' + b'fake image data'


# Real PNG bytes of a plain square of the given size - the shape an icon is stored in
def _png_image(size: int = 256) -> bytes:
    image = QImage(size, size, QImage.Format_RGB32)
    image.fill(Qt.red)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _apple(prepare_db) -> int:
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0)])
    return symbol_id_for(4)


# ----------------------------------------------------------------------------------------------------------------------
# Four answers out of two facts: who wrote the row, and whether it carries an image. An element that has no row was
# never asked about, which is what lets a download ask about it exactly once ever.
def test_four_states_of_an_icon(prepare_db):
    symbol_id = _apple(prepare_db)
    assert JalIcons.image(IconOwner.Symbol, symbol_id) is None        # never asked
    assert JalIcons.stored(IconOwner.Symbol, symbol_id) is False
    assert JalIcons.has_image(IconOwner.Symbol, symbol_id) is False

    JalIcons.store(IconOwner.Symbol, symbol_id, b'', IconSource.Downloaded)   # the source has none
    assert JalIcons.image(IconOwner.Symbol, symbol_id) == b''
    assert JalIcons.stored(IconOwner.Symbol, symbol_id) is True       # ... so it is not asked again
    assert JalIcons.has_image(IconOwner.Symbol, symbol_id) is False   # ... and there is nothing to paint

    JalIcons.store(IconOwner.Symbol, symbol_id, PNG, IconSource.Downloaded)  # downloaded
    assert JalIcons.image(IconOwner.Symbol, symbol_id) == PNG
    assert JalIcons.has_image(IconOwner.Symbol, symbol_id) is True

    JalIcons.store(IconOwner.Symbol, symbol_id, b'', IconSource.User)  # the user says it shows none
    assert JalIcons.image(IconOwner.Symbol, symbol_id) == b''
    assert JalIcons.source(IconOwner.Symbol, symbol_id) == IconSource.User

    JalIcons.forget(IconOwner.Symbol, symbol_id)                      # back to 'never asked'
    assert JalIcons.image(IconOwner.Symbol, symbol_id) is None
    assert JalIcons.stored(IconOwner.Symbol, symbol_id) is False


# The rule that makes "I removed that ugly logo and the downloader put it straight back" impossible: what the user
# stored wins over any later download, both an image they picked and a deliberate "this one has none".
def test_a_download_never_writes_over_the_user(prepare_db):
    symbol_id = _apple(prepare_db)
    JalIcons.store(IconOwner.Symbol, symbol_id, b'', IconSource.User)
    assert JalIcons.store(IconOwner.Symbol, symbol_id, PNG, IconSource.Downloaded) is False
    assert JalIcons.image(IconOwner.Symbol, symbol_id) == b''
    assert JalIcons.source(IconOwner.Symbol, symbol_id) == IconSource.User

    JalIcons.store(IconOwner.Symbol, symbol_id, PNG, IconSource.User)
    assert JalIcons.store(IconOwner.Symbol, symbol_id, b'other image', IconSource.Downloaded) is False
    assert JalIcons.image(IconOwner.Symbol, symbol_id) == PNG
    # The user, on the other hand, replaces whatever is there - including what a download stored
    JalIcons.store(IconOwner.Symbol, symbol_id, b'', IconSource.Downloaded)
    assert JalIcons.store(IconOwner.Symbol, symbol_id, PNG, IconSource.User) is True
    assert JalIcons.image(IconOwner.Symbol, symbol_id) == PNG


# One store for every kind of element: the same id in two kinds is two different icons, and an element with no id
# is not something to store an icon for.
def test_icons_of_different_kinds_do_not_collide(prepare_db):
    JalIcons.store(IconOwner.Account, 1, PNG, IconSource.User)
    JalIcons.store(IconOwner.Tag, 1, b'another image', IconSource.User)
    assert JalIcons.image(IconOwner.Account, 1) == PNG
    assert JalIcons.image(IconOwner.Tag, 1) == b'another image'
    assert JalIcons.image(IconOwner.Symbol, 1) is None
    assert JalIcons.store(IconOwner.Account, 0, PNG, IconSource.User) is False


# An icon points at its owner by (entity, item_id), which no foreign key can express - so every table that has
# icons drops them itself when a row goes.
def test_a_deleted_element_leaves_no_icon_behind(prepare_db):
    symbol_id = _apple(prepare_db)
    account_id = JalAccountCreator(currency_id=2, number='ICON-1', name='Icon test',
                                   account_type=PredefinedAccountType.Bank).id()
    tag_id = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")
    for entity, item_id in ((IconOwner.Symbol, symbol_id), (IconOwner.Account, account_id), (IconOwner.Tag, tag_id)):
        JalIcons.store(entity, item_id, PNG, IconSource.User)

    JalDB._exec("DELETE FROM asset_symbol WHERE id=:id", [(":id", symbol_id)], commit=True)
    JalDB._exec("DELETE FROM accounts WHERE id=:id", [(":id", account_id)], commit=True)
    JalDB._exec("DELETE FROM tags WHERE id=:id", [(":id", tag_id)], commit=True)
    assert JalDB._read("SELECT COUNT(*) FROM icons") == 0
    JalIcons.invalidate_cache()   # a trigger writes behind the store's back, as a cascading delete always does
    assert JalIcons.has_image(IconOwner.Symbol, symbol_id) is False


# The 'who has one' set answers per row, so it must never be asked once and then believed forever
def test_the_cache_follows_what_is_stored(prepare_db, monkeypatch):
    symbol_id = _apple(prepare_db)
    assert JalIcons.has_image(IconOwner.Symbol, symbol_id) is False
    JalIcons.store(IconOwner.Symbol, symbol_id, PNG, IconSource.User)
    assert JalIcons.has_image(IconOwner.Symbol, symbol_id) is True
    JalIcons.forget(IconOwner.Symbol, symbol_id)
    assert JalIcons.has_image(IconOwner.Symbol, symbol_id) is False

    # ... and the set is read in one query no matter how many rows ask it
    JalIcons.store(IconOwner.Symbol, symbol_id, PNG, IconSource.User)
    JalIcons.invalidate_cache()
    reads = []
    original = JalDB._exec

    def counting(sql, *args, **kwargs):
        reads.append(sql)
        return original(sql, *args, **kwargs)

    monkeypatch.setattr(JalDB, '_exec', staticmethod(counting))
    for _ in range(10):
        JalIcons.has_image(IconOwner.Symbol, symbol_id)
    assert len([x for x in reads if 'FROM icons' in x]) == 1


# An icon is painted much smaller than it is stored, and the scaled image is kept: a grid asks for the same
# picture on every repaint of every row.
def test_icon_is_scaled_and_cached(prepare_db):
    symbol_id = _apple(prepare_db)
    assert JalIcons.icon(IconOwner.Symbol, symbol_id, 17).isNull()   # nothing stored - nothing to paint
    JalIcons.store(IconOwner.Symbol, symbol_id, _png_image(), IconSource.Downloaded)

    icon = JalIcons.icon(IconOwner.Symbol, symbol_id, 17)
    assert isinstance(icon, QIcon) and not icon.isNull()
    assert max(icon.availableSizes()[0].width(), icon.availableSizes()[0].height()) == 17
    assert list(JalIcons._pixmaps) == [(IconOwner.Symbol, symbol_id, 17)]
    JalIcons.icon(IconOwner.Symbol, symbol_id, 17)
    assert len(JalIcons._pixmaps) == 1                               # asked twice, decoded once
    # A different size is a different picture, and forgetting the element drops both
    assert JalIcons.icon(IconOwner.Symbol, symbol_id, 32).availableSizes()[0].width() == 32
    assert len(JalIcons._pixmaps) == 2
    JalIcons.forget(IconOwner.Symbol, symbol_id)
    assert JalIcons._pixmaps == {}
    assert JalIcons.icon(IconOwner.Symbol, symbol_id, 17).isNull()

    # What can't be decoded is not painted, and doesn't take the row down with it
    JalIcons.store(IconOwner.Symbol, symbol_id, b'this is not an image', IconSource.User)
    assert JalIcons.icon(IconOwner.Symbol, symbol_id, 17).isNull()


# ----------------------------------------------------------------------------------------------------------------------
# The 65 -> 66 migration, run from the shipped delta file rather than copied here, so this test breaks if the
# migration text stops doing what it says.
_MIGRATION_FROM = "-- ICONS MOVE OUT OF THE TABLES THEY DECORATE"
_MIGRATION_TO = "-- Set new DB schema version"

# The shape schema 65 kept icons in: a BLOB column on the listing and a package filename on the tag
_OLD_SCHEMA = """
DROP TRIGGER accounts_after_delete_icon;
DROP TRIGGER asset_symbol_after_delete_icon;
DROP TRIGGER tags_after_delete_icon;
DROP INDEX icons_uniqueness;
DROP TABLE icons;
ALTER TABLE asset_symbol ADD COLUMN icon BLOB;
ALTER TABLE tags ADD COLUMN icon_file TEXT DEFAULT ('') NOT NULL;
"""


def _run_migration(project_root):
    with open(project_root + "/jal/updates/jal_delta_66.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_FROM), text.index(_MIGRATION_TO)
    for statement in sqlparse.split(text[start:end]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue   # a run of comment lines is not a statement
        assert JalDB._exec(statement.strip()) is not None, f"Migration statement failed: {statement}"


def test_icons_migration(prepare_db, project_root):
    for statement in sqlparse.split(_OLD_SCHEMA):
        assert JalDB._exec(statement.strip()) is not None, f"Can't restore the old schema: {statement}"
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0),
                   ('NOLOGO', 'Unknown Corp.', 'US0000000001', 2, PredefinedAsset.Stock, 0),
                   ('UNASKED', 'Never Asked Ltd.', 'US0000000002', 2, PredefinedAsset.Stock, 0)])
    logo, absent, unasked = symbol_id_for(4), symbol_id_for(5), symbol_id_for(6)
    image = _png_image()
    # Bound as a QByteArray, which is how the column was written before this migration - raw bytes would be
    # bound as text and stop at the first NUL of the PNG header
    JalDB._exec("UPDATE asset_symbol SET icon=:icon WHERE id=:id", [(":icon", QByteArray(image)), (":id", logo)])
    JalDB._exec("UPDATE asset_symbol SET icon=x'' WHERE id=:id", [(":id", absent)], commit=True)

    _run_migration(project_root)

    # A stored logo comes over byte for byte, an absence stays an absence, and a listing nothing ever looked at
    # gets no row - so the downloader asks about it exactly as it did before the migration
    JalIcons.invalidate_cache()
    assert JalIcons.image(IconOwner.Symbol, logo) == image
    assert JalIcons.image(IconOwner.Symbol, absent) == b''
    assert JalIcons.image(IconOwner.Symbol, unasked) is None
    assert JalIcons.stored(IconOwner.Symbol, unasked) is False
    # Everything that could be stored until now came from a download, and is marked as such
    assert JalIcons.source(IconOwner.Symbol, logo) == IconSource.Downloaded
    assert JalIcons.source(IconOwner.Symbol, absent) == IconSource.Downloaded

    # Both columns are gone, and the tags that named a package glyph are untouched otherwise
    assert 'icon' not in [x.lower() for x in JalDB._read_to_list("SELECT name FROM pragma_table_info('asset_symbol')")]
    assert 'icon_file' not in [x.lower() for x in JalDB._read_to_list("SELECT name FROM pragma_table_info('tags')")]
    assert JalDB._read("SELECT tag FROM tags WHERE id=2") == "Cash"

    # ... and the triggers the new table needs are in place
    account_id = JalAccountCreator(currency_id=2, number='ICON-1', name='Icon test',
                                   account_type=PredefinedAccountType.Bank).id()
    JalIcons.store(IconOwner.Account, account_id, PNG, IconSource.User)
    JalDB._exec("DELETE FROM accounts WHERE id=:id", [(":id", account_id)], commit=True)
    assert JalDB._read("SELECT COUNT(*) FROM icons WHERE entity=:entity AND item_id=:id",
                       [(":entity", IconOwner.Account), (":id", account_id)]) == 0
