# Tests of the picker (stage S3): the one import every source funnels through, and the actions that write what the
# user picked. What the four stored states MEAN is the subject of test_icon_store.py; here it is about getting into
# them from the interface.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, QBuffer, QIODevice
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_assets, symbol_id_for
from constants import IconOwner, IconSource, PredefinedAsset, Setup
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.icon import JalIcons
from jal.widgets.icon_picker import (IconImportError, IconPicker, MAX_SOURCE_SIZE, icon_from_data, icon_from_file,
                                     image_to_icon)


def _image(size: int = 256, color=Qt.red) -> QImage:
    image = QImage(size, size, QImage.Format_RGB32)
    image.fill(color)
    return image


def _saved(tmp_path, name: str, image_format: str, size: int = 256) -> str:
    path = str(tmp_path / name)
    assert _image(size).save(path, image_format)
    return path


def _account(number: str = 'U1', name: str = 'Acc'):
    return JalAccountCreator(currency_id=2, number=number, name=name, organization=1).commit()


def _listing(prepare_db) -> int:
    create_assets([('AAPL', 'Apple Inc.', 'US0378331005', 2, PredefinedAsset.Stock, 0)])
    return symbol_id_for(4, 2)


# ----------------------------------------------------------------------------------------------------------------------
# Whatever the user hands over, one format at one size lands in the database - that is what makes every consumer of
# the store able to assume PNG bytes it can decode.
@pytest.mark.parametrize("image_format, extension", [("PNG", "png"), ("JPG", "jpg"), ("BMP", "bmp")])
def test_every_accepted_format_becomes_a_png(prepare_db, tmp_path, image_format, extension):
    if image_format.lower().encode() not in [bytes(x).lower() for x in QImageReader.supportedImageFormats()]:
        pytest.skip(f"Qt here can't read {image_format}")
    stored = icon_from_file(_saved(tmp_path, f"logo.{extension}", image_format))

    assert stored.startswith(b'\x89PNG')
    decoded = QImage.fromData(stored)
    assert not decoded.isNull()
    assert max(decoded.width(), decoded.height()) == Setup.ICON_STORED_SIZE


# An image smaller than the stored size is kept as it is: scaling a 16x16 favicon up to 64x64 would store four
# times the bytes of the same blur
def test_a_small_image_is_not_blown_up(prepare_db):
    stored = image_to_icon(_image(16))
    assert QImage.fromData(stored).width() == 16


# The guards, each with a message of its own to show
def test_a_file_that_is_not_an_image_is_refused(prepare_db, tmp_path):
    path = str(tmp_path / "notes.txt")
    open(path, 'w').write("this is not a picture")
    with pytest.raises(IconImportError):
        icon_from_file(path)


def test_an_oversized_source_is_refused(prepare_db, tmp_path):
    path = str(tmp_path / "photo.png")
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + b'\0' * MAX_SOURCE_SIZE)
    with pytest.raises(IconImportError) as error:
        icon_from_file(path)
    assert "too large" in str(error.value)

    with pytest.raises(IconImportError):
        icon_from_data(b'\0' * (MAX_SOURCE_SIZE + 1))


# ----------------------------------------------------------------------------------------------------------------------
# The two answers a user can give that are NOT a picture. They are different states and only one of them stays.
def test_no_icon_and_remove_are_different_answers(prepare_db):
    listing = _listing(prepare_db)
    parent = QWidget()
    picker = IconPicker(IconOwner.Symbol, listing, parent=parent)

    picker.set_no_icon()
    assert JalIcons.image(IconOwner.Symbol, listing) == b''            # a stored absence...
    assert JalIcons.source(IconOwner.Symbol, listing) == IconSource.User   # ... that is the user's own
    assert JalIcons.stored(IconOwner.Symbol, listing)                  # so the downloader won't ask again

    picker.remove()
    assert JalIcons.image(IconOwner.Symbol, listing) is None           # nothing is known about it any more
    assert not JalIcons.stored(IconOwner.Symbol, listing)              # so the downloader may try once more
    parent.deleteLater()


# Whatever the user picks is stored as theirs, which is what keeps the next download off it
def test_what_the_picker_writes_belongs_to_the_user(prepare_db):
    account = _account()
    parent = QWidget()
    picker = IconPicker(IconOwner.Account, account.id(), parent=parent)

    picker._store(image_to_icon(_image()))
    assert JalIcons.source(IconOwner.Account, account.id()) == IconSource.User
    assert JalIcons.has_image(IconOwner.Account, account.id())
    parent.deleteLater()


# ----------------------------------------------------------------------------------------------------------------------
# The gallery is how one logo reaches five accounts. It offers each distinct image once, and only of the kind being
# decorated - an account is given the logo of another account, not one of 200 asset logos.
def test_the_gallery_lists_distinct_icons_of_its_own_kind(prepare_db):
    first, second, third = _account('U1', 'First'), _account('U2', 'Second'), _account('U3', 'Third')
    listing = _listing(prepare_db)
    logo, other = image_to_icon(_image(color=Qt.red)), image_to_icon(_image(color=Qt.blue))
    JalIcons.store(IconOwner.Account, first.id(), logo, IconSource.User)
    JalIcons.store(IconOwner.Account, second.id(), logo, IconSource.User)    # the same picture, twice
    JalIcons.store(IconOwner.Account, third.id(), other, IconSource.User)
    JalIcons.store(IconOwner.Symbol, listing, logo, IconSource.Downloaded)

    accounts = JalIcons.distinct_images(IconOwner.Account)
    assert len(accounts) == 2                                  # one entry per distinct image, not per element
    assert sorted(x[1] for x in accounts) == sorted([logo, other])
    assert [x[0] for x in accounts] == [first.id(), third.id()]   # named after the first element that carries it
    assert len(JalIcons.distinct_images(IconOwner.Symbol)) == 1   # the listing's kind is a set of its own


# ----------------------------------------------------------------------------------------------------------------------
# The menu keeps one shape wherever it is opened: what can't be done here is shown greyed out rather than missing,
# so the entries don't move about between an account and a listing.
def _actions(menu) -> dict:
    return {action.text(): action for action in menu.actions() if action.text()}


def test_only_a_listing_can_be_downloaded_again(prepare_db):
    parent = QWidget()
    listing = _listing(prepare_db)
    account = _account()

    listing_menu = _actions(IconPicker(IconOwner.Symbol, listing, parent=parent).menu(parent))
    account_menu = _actions(IconPicker(IconOwner.Account, account.id(), parent=parent).menu(parent))

    assert listing_menu["Download again"].isEnabled()
    assert "Download again" in account_menu and not account_menu["Download again"].isEnabled()
    # 'No icon' is a stored answer the downloader honours - it means nothing where nothing downloads
    assert "No icon" in listing_menu and "No icon" not in account_menu
    parent.deleteLater()


def test_nothing_to_remove_until_something_is_stored(prepare_db):
    parent = QWidget()
    account = _account()

    assert not _actions(IconPicker(IconOwner.Account, account.id(), parent=parent).menu(parent))["Remove"].isEnabled()
    JalIcons.store(IconOwner.Account, account.id(), image_to_icon(_image()), IconSource.User)
    assert _actions(IconPicker(IconOwner.Account, account.id(), parent=parent).menu(parent))["Remove"].isEnabled()
    parent.deleteLater()


# ----------------------------------------------------------------------------------------------------------------------
# Every list whose model carries icons offers to set one, and a list that has none doesn't - the dialogs say nothing
# about it, they ask the model (which is the same thing the display side does).
def test_the_context_menu_offers_an_icon_where_the_model_has_one(prepare_db):
    from PySide6.QtWidgets import QMenu
    from jal.widgets.reference_dialogs import AccountListDialog, QuotesListDialog
    parent = QWidget()
    _account()

    accounts = AccountListDialog(parent)
    menu = QMenu(accounts)
    accounts.addIconAction(menu, accounts.model.index(0, 0))
    assert [x.text() for x in menu.actions() if x.text()] == ["Icon"]

    quotes = QuotesListDialog(parent)          # quotes are not an element that carries an icon
    menu = QMenu(quotes)
    quotes.addIconAction(menu, quotes.model.index(0, 0))
    assert not menu.actions()

    accounts.close()
    quotes.close()
    parent.deleteLater()


# The same for a tree - and its hidden root ('tags' seeds a row with id 0 and no name) is not an element, so it is
# offered nothing rather than an icon that could never be stored
def test_the_tree_offers_an_icon_but_not_on_its_hidden_root(prepare_db):
    from PySide6.QtCore import QModelIndex
    from PySide6.QtWidgets import QMenu
    from jal.widgets.reference_dialogs import TagsListDialog
    parent = QWidget()
    tags = TagsListDialog(parent)

    root = tags.model.index(0, 0, QModelIndex())        # id 0 - the tree's own root, which index() refuses
    assert not root.isValid()
    menu = QMenu(tags)
    tags.addIconAction(menu, root)
    assert not menu.actions()

    tag = tags.model.index(1, 0, QModelIndex())
    assert tags.model.getId(tag)
    menu = QMenu(tags)
    tags.addIconAction(menu, tag)
    assert [x.text() for x in menu.actions() if x.text()] == ["Icon"]

    tags.close()
    parent.deleteLater()
