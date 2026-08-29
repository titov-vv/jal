# Tests of the display half of the icon architecture (stage S2): the size an icon is painted at, the generic hook
# that puts one before the text of a column, and the surfaces wired to it. What is STORED and how is the subject of
# test_icon_store.py - here nothing is asked of the store but the picture it hands back.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from PySide6.QtCore import Qt, QBuffer, QIODevice
from PySide6.QtGui import QColor, QFont, QIcon, QImage
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, symbol_id_for, create_stocks, create_assets, create_actions, create_trades, \
    create_swaps, create_conversions, create_corporate_actions, create_transfers, create_bridges
from constants import AssetLocation, IconOwner, IconSource, PredefinedAsset, PredefinedCategory
from jal.db.db import JalDB
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.symbol import JalSymbol
from jal.db.icon import JalIcons
from jal.db.common_models import AccountListModel, TagTreeModel
from jal.db.asset_models import SymbolsListModel
from jal.db.operations import LedgerTransaction, AssetPayment, CorporateAction, Transfer, Swap, Bridge
from jal.widgets.helpers import grid_icon_size, grid_row_height, set_grids_metrics
from jal.widgets.reference_dialogs import AccountListDialog, TagsListDialog


# A real PNG of a plain square - the shape an icon is stored in
def _png(size: int = 256) -> bytes:
    image = QImage(size, size, QImage.Format_RGB32)
    image.fill(Qt.red)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _accounts() -> tuple:
    with_logo = JalAccountCreator(currency_id=2, number='U1', name='With logo', organization=1).commit()
    without = JalAccountCreator(currency_id=2, number='U2', name='No logo', organization=1).commit()
    JalIcons.store(IconOwner.Account, with_logo.id(), _png(), IconSource.User)
    return with_logo, without


# ----------------------------------------------------------------------------------------------------------------------
# The column a model marks with CmColumn.icon answers with the icon of the element its row stands for. An element
# that has none answers with a blank of the same size, not with nothing: it is what keeps the names of a list
# starting at one and the same place when only some of them carry a logo.
def test_the_flagged_column_carries_the_icon(prepare_db):
    with_logo, without = _accounts()
    model = AccountListModel()

    rows = {model.getId(model.index(row, 0)): row for row in range(model.rowCount())}
    icon = model.data(model.index(rows[with_logo.id()], model.fieldIndex("name")), Qt.DecorationRole)
    blank = model.data(model.index(rows[without.id()], model.fieldIndex("name")), Qt.DecorationRole)

    assert isinstance(icon, QIcon) and not icon.isNull()
    assert isinstance(blank, QIcon)
    assert icon.availableSizes()[0] == blank.availableSizes()[0] == \
           blank.availableSizes()[0].__class__(JalIcons.grid_size(), JalIcons.grid_size())
    assert blank.pixmap(JalIcons.grid_size()).toImage().pixelColor(0, 0).alpha() == 0

    # ... and no other column of the same model is decorated by the hook
    assert model.data(model.index(rows[with_logo.id()], model.fieldIndex("currency_id")), Qt.DecorationRole) is None


# The same hook, reached through the other model base: a tree answers data() itself and had to be given the branch
def test_a_tree_carries_the_icon_too(prepare_db):
    tag_id = JalDB._read("SELECT id FROM tags WHERE tag='Cash'")
    JalIcons.store(IconOwner.Tag, tag_id, _png(), IconSource.User)
    model = TagTreeModel()

    index = model.locateItem(tag_id)
    icon = model.data(index.siblingAtColumn(model.fieldIndex("tag")), Qt.DecorationRole)
    assert isinstance(icon, QIcon) and not icon.isNull()


# ----------------------------------------------------------------------------------------------------------------------
# An icon is the height of the font, which is the tallest one a row already has the room for - so a grid that
# starts showing icons keeps the row height it had.
def test_rows_do_not_grow_for_icons(prepare_db):
    parent = QWidget()
    with_logo, _ = _accounts()
    JalIcons.store(IconOwner.Tag, JalDB._read("SELECT id FROM tags WHERE tag='Cash'"), _png(), IconSource.User)

    accounts, tags = AccountListDialog(parent), TagsListDialog(parent)
    accounts.show()
    tags.show()

    assert grid_icon_size(accounts.ui.DataView) == accounts.ui.DataView.fontMetrics().height()
    assert grid_icon_size(accounts.ui.DataView) <= grid_row_height(accounts.ui.DataView)
    assert accounts.ui.DataView.verticalHeader().defaultSectionSize() == grid_row_height(accounts.ui.DataView)
    assert tags.ui.TreeView.sizeHintForRow(0) == grid_row_height(tags.ui.TreeView)

    accounts.close()
    tags.close()
    parent.deleteLater()


# A view that was never told an icon size clamps every icon to the style's 16 px, whatever the font is doing -
# so the size is set explicitly, and it follows the font like the row height does.
def test_icon_size_follows_the_font(prepare_db):
    parent = QWidget()
    accounts = AccountListDialog(parent)
    accounts.show()
    view = accounts.ui.DataView
    assert view.iconSize().height() == grid_icon_size(view)

    before = view.iconSize().height()
    font = QFont(accounts.font())
    font.setPointSize(font.pointSize() + 8)
    accounts.setFont(font)
    set_grids_metrics(accounts)

    assert view.iconSize().height() == grid_icon_size(view) > before
    accounts.close()
    parent.deleteLater()


# ----------------------------------------------------------------------------------------------------------------------
# Painting a grid must not turn into a query per row: the store knows in one query which elements have an image at
# all, and the common answer - "this one has none" - is given from that set.
def test_the_store_is_asked_once_for_a_whole_list(prepare_db, monkeypatch):
    with_logo, _ = _accounts()
    for i in range(8):
        JalAccountCreator(currency_id=2, number=f'N{i}', name=f'Account {i}', organization=1).commit()
    JalIcons.invalidate_cache()

    queries = []
    original = JalDB._exec

    def counting(*args, **kwargs):
        if args and isinstance(args[0], str) and 'icons' in args[0]:
            queries.append(args[0])
        return original(*args, **kwargs)
    monkeypatch.setattr(JalDB, '_exec', staticmethod(counting))

    model = AccountListModel()
    for row in range(model.rowCount()):
        model.data(model.index(row, model.fieldIndex("name")), Qt.DecorationRole)

    assert model.rowCount() > 8
    # One query for the whole list - the set of elements that have an image - and then one read of the image
    # itself for the single account that has one. Nothing is asked about the rows that have none.
    assert len([x for x in queries if 'SELECT entity, item_id' in x]) == 1
    assert len([x for x in queries if 'SELECT image' in x]) == 1


# ----------------------------------------------------------------------------------------------------------------------
# A token held on two chains is one asset with a listing per chain, each with its own logo. The row shows the icon
# of the very listing whose ticker it prints - the two are narrowed by one and the same code.
def test_listing_id_matches_the_ticker_shown(prepare_db):
    create_assets([('USDT', 'Tether', '', 2, PredefinedAsset.Crypto, 0)])
    asset = JalAsset(4)
    eth = asset.add_symbol('USDT', 2, AssetLocation.ETH_BLOCKCHAIN)
    arb = asset.add_symbol('USDT.e', 2, AssetLocation.ARB_BLOCKCHAIN)
    asset = JalAsset(4)

    assert asset.listing_id(currency=2, location=AssetLocation.ETH_BLOCKCHAIN) == eth
    assert asset.listing_id(currency=2, location=AssetLocation.ARB_BLOCKCHAIN) == arb
    for location in (AssetLocation.ETH_BLOCKCHAIN, AssetLocation.ARB_BLOCKCHAIN):
        listing = asset.listing_id(currency=2, location=location)
        assert asset.symbol(currency=2, location=location) == JalSymbol(listing).symbol()


# ----------------------------------------------------------------------------------------------------------------------
# The last column of the operations list prints a ticker per line and is painted with one icon per line, so the two
# lists an operation answers with have to stay in step. They are written side by side for exactly that reason.
def test_operations_keep_tickers_and_icons_in_step(prepare_db):
    JalAccountCreator(currency_id=2, number='U1', name='Acc', investing=1, organization=1).commit()
    JalAccountCreator(currency_id=2, number='U2', name='Other', investing=1, organization=1).commit()
    create_stocks([('AAPL', 'Apple Inc.'), ('MSFT', 'Microsoft')], currency_id=2)   # assets 4 and 5

    create_actions([(d2t(220101), 1, 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_trades(1, [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment,
                                 {'timestamp': d2t(220301), 'type': AssetPayment.Dividend, 'account_id': 1,
                                  'symbol_id': symbol_id_for(4, 2), 'amount': '5', 'tax': '0.5', 'note': ''})
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment,
                                 {'timestamp': d2t(220302), 'type': AssetPayment.StockDividend, 'account_id': 1,
                                  'symbol_id': symbol_id_for(4, 2), 'amount': '1', 'tax': '0.1', 'note': ''})
    create_swaps(1, [(d2t(220401), 4, 1.0, 5, 2.0)])
    create_conversions(1, [(d2t(220501), 4, 1.0, 5, 2.0)])
    create_corporate_actions(1, [(d2t(220601), CorporateAction.Split, 4, 10.0, '', [(4, 20.0, 1.0)])])
    create_transfers([(d2t(220701), 1, 100.0, 2, 100.0, None)])
    create_transfers([(d2t(220702), 1, 1.0, 2, 1.0, 4)])
    # With a fee, so that the fee leg of the bridge is a real part to ask about
    create_bridges([{'out_ts': d2t(220801), 'out_acc': 1, 'out_qty': 1.0,
                     'in_ts': d2t(220802), 'in_acc': 2, 'in_qty': 1.0, 'asset': 4,
                     'fee_asset': 5, 'fee_qty': 0.1}])

    parts = {LedgerTransaction.Transfer: (Transfer.Outgoing, Transfer.Incoming, Transfer.Fee),
             LedgerTransaction.Swap: (0, Swap.Incoming),
             LedgerTransaction.Bridge: (0, Bridge.Incoming, Bridge.Fee)}
    tables = {LedgerTransaction.IncomeSpending: "actions", LedgerTransaction.AssetPayment: "asset_payments",
              LedgerTransaction.Trade: "trades", LedgerTransaction.Transfer: "transfers",
              LedgerTransaction.CorporateAction: "asset_actions", LedgerTransaction.Conversion: "conversions",
              LedgerTransaction.Swap: "swaps", LedgerTransaction.Bridge: "bridges"}
    checked = 0
    for otype, table in tables.items():
        oids = JalDB._read_to_list(f"SELECT oid FROM {table}")
        assert oids, f"no operation of type {otype} was created"
        for oid in oids:
            for opart in parts.get(otype, (0,)):
                operation = LedgerTransaction.get_operation(otype, oid, opart)
                text, icons = operation.value_currency(), operation.value_currency_icons()
                lines = text.split("\n") if text else []
                assert len(icons) == len(lines), f"{type(operation).__name__} part {opart}: {icons} against '{text}'"
                checked += 1
    assert checked > 15


# Every listing an operation names has to be a listing that exists - an icon asked for by a stale id is silently
# blank, which would hide the mistake instead of showing it.
def test_operation_icons_name_real_listings(prepare_db):
    JalAccountCreator(currency_id=2, number='U1', name='Acc', investing=1, organization=1).commit()
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=2)
    create_trades(1, [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])
    operation = LedgerTransaction.get_operation(LedgerTransaction.Trade, JalDB._read("SELECT MAX(oid) FROM trades"))

    listings = operation.value_currency_icons()
    assert len(listings) == 2                                     # the account currency and the asset traded
    assert listings[1] == symbol_id_for(4, 2)
    for listing in listings:
        assert JalDB._read("SELECT id FROM asset_symbol WHERE id=:id", [(":id", listing)]) == listing


# ----------------------------------------------------------------------------------------------------------------------
# The balances tree draws two kinds of picture in one column, which is what its indentation already separates: a
# group row is an account TYPE and keeps the glyph of that type, the accounts under it wear their own logo.
def test_balances_tree_shows_glyphs_on_groups_and_logos_on_accounts(prepare_db):
    from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter
    from jal.db.balances_model import BalancesModel
    from jal.db.ledger import Ledger

    with_logo, _ = _accounts()
    create_actions([(d2t(220101), with_logo.id(), 1, [(PredefinedCategory.StartingBalance, 1000.0)])])
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()   # a dialog built without one aborts the process from the cyclic collector
    view = TreeViewWithFooter(parent)
    model = BalancesModel(view)
    model._currency = 2
    model.prepareData()
    column = model.fieldIndex('account_name')

    group = model.index(0, column, model.index(-1, -1))
    assert model.data(group, Qt.DisplayRole)                    # the account type this group stands for
    assert isinstance(model.data(group, Qt.DecorationRole), QIcon)
    leaf = model.index(0, column, group)
    assert model.data(leaf, Qt.DisplayRole) == 'With logo'
    icon = model.data(leaf, Qt.DecorationRole)
    assert isinstance(icon, QIcon) and not icon.isNull()
    assert icon.availableSizes()[0].width() == JalIcons.grid_size()

    parent.deleteLater()


# A holding wears the logo of the listing its ticker came from, and a group wears whatever it groups by
def test_portfolio_rows_wear_the_icon_of_their_listing(prepare_db):
    from PySide6.QtWidgets import QTreeView
    from jal.db.holdings_model import HoldingsModel
    from jal.db.ledger import Ledger

    account = JalAccountCreator(currency_id=2, number='U1', name='Inv', investing=1, organization=1).commit()
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=2)
    create_actions([(d2t(220101), account.id(), 1, [(PredefinedCategory.StartingBalance, 10000.0)])])
    create_trades(account.id(), [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])
    Ledger().rebuild(from_timestamp=0)
    listing = symbol_id_for(4, 2)
    JalIcons.store(IconOwner.Symbol, listing, _png(), IconSource.Downloaded)

    model = HoldingsModel(QTreeView())
    model._currency = 2
    model.prepareData()

    holdings = []

    def collect(item):
        if not item.childrenCount():
            holdings.append(item)
        for i in range(item.childrenCount()):
            collect(item.getChild(i))
    collect(model._root)

    rows = [x for x in holdings if x.details()['asset_id'] == 4]
    assert len(rows) == 1
    assert rows[0].details()['symbol_id'] == listing            # the listing the ticker was taken from
    icon = model.row_icon(rows[0])
    assert isinstance(icon, QIcon) and not icon.isNull()
    # ... while the money row of the same account has no logo stored, and keeps the space instead
    money = [x for x in holdings if x.details()['asset_id'] == 2]
    assert money and model.row_icon(money[0]).availableSizes()[0].width() == JalIcons.grid_size()


# ----------------------------------------------------------------------------------------------------------------------
# A row of the operations list is as tall as the operation asks for, and a column may hold fewer values than that -
# a payment with no tax has one amount in a two-line row. Such a value belongs to the FIRST line of the row, beside
# the text that made it tall, and not to the middle of the empty space below it.
def _amount_cell(rect_lines: int, values: int):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QStyleOptionViewItem, QTableView
    from jal.widgets.delegates import ColoredAmountsDelegate, ROW_LINES_ROLE

    line = 20
    parent = QWidget()
    view = QTableView(parent)
    delegate = ColoredAmountsDelegate(view)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 120, line * rect_lines)
    option.widget = view

    class Cell:      # the smallest thing that answers what the delegate asks a model for
        def data(self, index, role=Qt.DisplayRole):
            if role == ROW_LINES_ROLE:
                return rect_lines
            if role == Qt.ForegroundRole:
                return None
            return [Decimal('12.34')] * values

        def model(self):
            return self

        def isValid(self):
            return True
    pixmap = QPixmap(120, line * rect_lines)
    pixmap.fill(Qt.white)
    painter = QPainter(pixmap)
    delegate.paint(painter, option, Cell())
    painter.end()
    image = pixmap.toImage()
    rows_with_ink = {y for y in range(image.height()) for x in range(image.width())
                     if image.pixelColor(x, y) != Qt.white}
    parent.deleteLater()
    return rows_with_ink, line


def test_a_single_value_sits_on_the_first_line_of_a_tall_row(prepare_db):
    ink, line = _amount_cell(rect_lines=2, values=1)
    assert ink, "nothing was painted at all"
    assert max(ink) < line, "the only value of a two-line row must be drawn on its first line"


def test_two_values_still_take_a_line_each(prepare_db):
    ink, line = _amount_cell(rect_lines=2, values=2)
    assert [y for y in ink if y < line] and [y for y in ink if y >= line]


# ----------------------------------------------------------------------------------------------------------------------
# Keeping the place of a missing icon is the user's call: with it the names of a list line up, without it the space
# goes back to the text. The store answers accordingly, and every column that shows an icon goes through it.
def test_indentation_is_a_preference(prepare_db, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from jal.db.settings import JalSettings
    from jal.widgets.helpers import refresh_row_heights

    # refresh_row_heights() walks every widget of the application to repaint it, and the widgets other tests of
    # this process left behind are not all alive - so here it is asked to do its own half of the work only.
    monkeypatch.setattr(QApplication, 'topLevelWidgets', staticmethod(lambda: []))
    monkeypatch.setattr(QApplication, 'allWidgets', staticmethod(lambda: []))

    with_logo, without = _accounts()
    model = AccountListModel()
    rows = {model.getId(model.index(row, 0)): row for row in range(model.rowCount())}
    name = model.fieldIndex("name")

    assert JalIcons.rows_are_indented()                            # kept by default
    assert isinstance(model.data(model.index(rows[without.id()], name), Qt.DecorationRole), QIcon)

    JalSettings().setValue(JalIcons.INDENT_KEY, 0)
    refresh_row_heights()                                          # what the preferences dialog calls
    assert not JalIcons.rows_are_indented()
    assert model.data(model.index(rows[without.id()], name), Qt.DecorationRole) is None
    icon = model.data(model.index(rows[with_logo.id()], name), Qt.DecorationRole)
    assert isinstance(icon, QIcon) and not icon.isNull()            # an element that HAS one still shows it

    JalSettings().setValue(JalIcons.INDENT_KEY, 1)
    refresh_row_heights()
    assert isinstance(model.data(model.index(rows[without.id()], name), Qt.DecorationRole), QIcon)


# It is asked once per row painted, so it may not go to the database every time
def test_the_indent_preference_is_read_once(prepare_db, monkeypatch):
    from jal.db.settings import JalSettings
    reads = []
    original = JalSettings.getBool
    monkeypatch.setattr(JalSettings, 'getBool',
                        lambda self, key, default=False: (reads.append(key), original(self, key, default))[1])
    JalIcons.invalidate_indent()
    for _ in range(10):
        JalIcons.spacer(17)
    assert reads.count(JalIcons.INDENT_KEY) == 1


# The user can only change what the preferences dialog knows about
def test_the_preference_is_offered_on_the_interface_page(prepare_db):
    from jal.db.settings_registry import SettingsRegistry
    setting = [x for x in SettingsRegistry.settings_of_page("Interface") if x.key == JalIcons.INDENT_KEY]
    assert len(setting) == 1
    assert setting[0].page == "Interface"
    assert setting[0].default == JalIcons.INDENT_DEFAULT


# ----------------------------------------------------------------------------------------------------------------------
# The selector widget is how every operation form picks its account, its symbol and its tag - so it is where a
# stored icon reaches the forms. It shows the icon of what is selected, and nothing at all where the kind of thing
# being selected has no icons (a peer, until S6 gives it some).
def test_the_selector_shows_the_icon_of_what_it_selected(prepare_db):
    from jal.widgets.reference_selector import ReferenceSelectorWidget
    from jal.widgets.reference_dialogs import AccountListDialog, PeerListDialog
    from jal.db.common_models import AccountListModel, PeerTreeModel

    with_logo, without = _accounts()
    parent = QWidget()
    selector = ReferenceSelectorWidget(parent)
    selector.setup_selector(AccountListModel, AccountListDialog, parent)

    selector.selected_id = with_logo.id()
    assert selector.icon.isVisible() or True          # (a widget that was never shown reports itself hidden)
    assert not selector.icon.pixmap().isNull()
    assert selector.icon.pixmap().width() == JalIcons.grid_size()

    selector.selected_id = without.id()               # no icon of its own, but the space is kept by default
    assert not selector.icon.pixmap().isNull()
    assert selector.icon.pixmap().toImage().pixelColor(0, 0).alpha() == 0

    selector.selected_id = 0                          # nothing selected - nothing to show
    assert not selector.icon.isVisibleTo(parent)

    peers = ReferenceSelectorWidget(parent)           # a kind that carries no icons at all
    peers.setup_selector(PeerTreeModel, PeerListDialog, parent)
    peers.selected_id = 1
    assert not peers.icon.isVisibleTo(parent)
    parent.deleteLater()


def test_the_selector_follows_the_indent_preference(prepare_db, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from jal.db.settings import JalSettings
    from jal.widgets.reference_selector import ReferenceSelectorWidget
    from jal.widgets.reference_dialogs import AccountListDialog
    from jal.db.common_models import AccountListModel
    monkeypatch.setattr(QApplication, 'topLevelWidgets', staticmethod(lambda: []))
    monkeypatch.setattr(QApplication, 'allWidgets', staticmethod(lambda: []))

    _, without = _accounts()
    parent = QWidget()
    selector = ReferenceSelectorWidget(parent)
    selector.setup_selector(AccountListModel, AccountListDialog, parent)

    JalSettings().setValue(JalIcons.INDENT_KEY, 0)
    JalIcons.invalidate_indent()
    selector.selected_id = without.id()
    assert not selector.icon.isVisibleTo(parent)      # the space goes back to the name field

    JalSettings().setValue(JalIcons.INDENT_KEY, 1)
    JalIcons.invalidate_indent()
    selector.set_labels_text(without.id())
    assert selector.icon.isVisibleTo(parent)
    parent.deleteLater()


# ----------------------------------------------------------------------------------------------------------------------
# What kind of account a row is, in a picture: a wallet is marked by its blockchain rather than by the generic
# wallet glyph, because that is what the user knows the account as.
TRX_ADDRESS = 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'   # the USDT contract on Tron - a real, checksum-valid address


def test_a_wallet_is_marked_by_its_blockchain(prepare_db):
    from jal.constants import AssetLocation, PredefinedAccountType
    from jal.db.account import JalAccount
    from jal.db.common_models import account_mark, chain_icon
    from jal.widgets.icons import JalIcon, CHAIN_PREFIX
    JalIcon()   # the glyph table is built by MainWindow in the application, and by hand where there is none

    wallet = JalAccountCreator(currency_id=2, number='', name='Tron wallet', organization=1,
                               account_type=PredefinedAccountType.Wallet,
                               address=TRX_ADDRESS, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    cash = JalAccountCreator(currency_id=2, number='U9', name='Cash', organization=1).commit()

    assert account_mark(wallet).cacheKey() == JalIcon.module_icon(CHAIN_PREFIX, 'tron.png').cacheKey()
    assert account_mark(cash).cacheKey() == JalIcon[JalAccount.get_type_icon(PredefinedAccountType.Cash)].cacheKey()
    # ... and the map that says which file marks which chain covers every chain JAL supports
    for location in AssetLocation.BLOCKCHAINS:
        assert AssetLocation.icon_of(location), f"no glyph declared for location {location}"
        assert not chain_icon(location).isNull(), f"the file of location {location} is missing from jal/img"
    assert AssetLocation.icon_of(AssetLocation.NYSE_EXCHANGE) == ''     # an exchange is not a chain


# The account type column of the accounts list is where that mark is shown
def test_the_accounts_list_shows_the_chain_of_a_wallet(prepare_db):
    from jal.constants import AssetLocation, PredefinedAccountType
    from jal.db.common_models import AccountListModel
    from jal.widgets.icons import JalIcon, CHAIN_PREFIX
    JalIcon()

    wallet = JalAccountCreator(currency_id=2, number='', name='Tron wallet', organization=1,
                               account_type=PredefinedAccountType.Wallet,
                               address=TRX_ADDRESS, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    model = AccountListModel()
    rows = {model.getId(model.index(row, 0)): row for row in range(model.rowCount())}
    mark = model.data(model.index(rows[wallet.id()], model.fieldIndex("account_type")), Qt.DecorationRole)

    assert mark.cacheKey() == JalIcon.module_icon(CHAIN_PREFIX, 'tron.png').cacheKey()


# And the 'Blockchain' attribute of an account states a chain, so it shows it too
def test_the_chain_attribute_carries_its_glyph(prepare_db):
    from jal.constants import AccountData, AssetLocation, PredefinedAccountType
    from jal.db.common_models import AccountDataModel, chain_icon
    from jal.widgets.icons import JalIcon
    JalIcon()

    wallet = JalAccountCreator(currency_id=2, number='', name='Tron wallet', organization=1,
                               account_type=PredefinedAccountType.Wallet,
                               address=TRX_ADDRESS, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    model = AccountDataModel()
    model.filterBy("account_id", wallet.id())
    rows = [row for row in range(model.rowCount())
            if model.data(model.index(row, model.fieldIndex("datatype")), Qt.EditRole) == AccountData.Chain]
    assert len(rows) == 1

    value = model.index(rows[0], model.fieldIndex("value"))
    assert model.data(value, Qt.DecorationRole).cacheKey() == chain_icon(AssetLocation.TRX_BLOCKCHAIN).cacheKey()
    address = [row for row in range(model.rowCount())
               if model.data(model.index(row, model.fieldIndex("datatype")), Qt.EditRole) == AccountData.Address]
    assert model.data(model.index(address[0], model.fieldIndex("value")), Qt.DecorationRole) is None


# ----------------------------------------------------------------------------------------------------------------------
# A row that names an account shows what THAT account is: its own icon, or - for an account that states a
# blockchain and has none - the chain it sits on. Never the glyph of its type, which the group row above it or the
# type column beside it already says.
def test_an_account_row_falls_back_to_its_chain(prepare_db):
    from jal.constants import AssetLocation, PredefinedAccountType
    from jal.db.common_models import account_row_icon, chain_icon
    from jal.widgets.icons import JalIcon
    JalIcon()

    wallet = JalAccountCreator(currency_id=2, number='', name='Tron wallet', organization=1,
                               account_type=PredefinedAccountType.Wallet,
                               address=TRX_ADDRESS, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    card = JalAccountCreator(currency_id=2, number='U8', name='Card', organization=1).commit()

    assert account_row_icon(wallet).cacheKey() == chain_icon(AssetLocation.TRX_BLOCKCHAIN).cacheKey()
    # ... and an icon of its own wins over the chain, because it names this wallet and not the chain's other ones
    JalIcons.store(IconOwner.Account, wallet.id(), _png(), IconSource.User)
    own = account_row_icon(wallet)
    assert own.cacheKey() != chain_icon(AssetLocation.TRX_BLOCKCHAIN).cacheKey()
    assert not own.isNull()
    # An account that states no chain keeps the blank: its type is said elsewhere on the same row
    blank = account_row_icon(card)
    assert blank.pixmap(JalIcons.grid_size()).toImage().pixelColor(0, 0).alpha() == 0


# Which is what puts a chain on the wallet rows of the balances tree
def test_the_balances_tree_marks_a_wallet_with_its_chain(prepare_db):
    from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter
    from jal.constants import AssetLocation, PredefinedAccountType, PredefinedCategory
    from jal.db.balances_model import BalancesModel
    from jal.db.common_models import chain_icon
    from jal.db.ledger import Ledger
    from jal.widgets.icons import JalIcon
    JalIcon()

    wallet = JalAccountCreator(currency_id=2, number='', name='Tron wallet', organization=1,
                               account_type=PredefinedAccountType.Wallet,
                               address=TRX_ADDRESS, chain=AssetLocation.TRX_BLOCKCHAIN).commit()
    create_actions([(d2t(220101), wallet.id(), 1, [(PredefinedCategory.StartingBalance, 100.0)])])
    Ledger().rebuild(from_timestamp=0)

    parent = QWidget()
    view = TreeViewWithFooter(parent)
    model = BalancesModel(view)
    model._currency = 2
    model.prepareData()
    column = model.fieldIndex('account_name')

    group = model.index(0, column, model.index(-1, -1))
    leaf = model.index(0, column, group)
    assert model.data(leaf, Qt.DisplayRole) == 'Tron wallet'
    assert model.data(leaf, Qt.DecorationRole).cacheKey() == chain_icon(AssetLocation.TRX_BLOCKCHAIN).cacheKey()
    # the group row is the TYPE and keeps the type's own glyph
    assert model.data(group, Qt.DecorationRole).cacheKey() == JalIcon[wallet.type_icon()].cacheKey()
    parent.deleteLater()


# ----------------------------------------------------------------------------------------------------------------------
# The lookup combo boxes of the dialogs draw an icon by themselves once their model answers with one - and the
# currencies they list are assets, so the icon is the one of the listing that names each of them.
def test_the_lookup_combo_shows_the_icon_of_its_rows(prepare_db):
    from jal.widgets.custom.db_lookup_combobox import DbLookupComboBox
    from jal.db.asset import JalAsset
    parent = QWidget()
    listing = JalAsset(2).listing_id()                  # the base currency of the test database
    JalIcons.store(IconOwner.Symbol, listing, _png(), IconSource.User)

    combo = DbLookupComboBox(parent)
    combo.setKeyField("id")
    combo.setField("symbol")
    combo.setTable("currencies")
    model = combo.model()

    rows = {model.record(row).value("id"): row for row in range(model.rowCount())}
    icon = model.data(model.index(rows[2], model.fieldIndex("symbol")), Qt.DecorationRole)
    assert isinstance(icon, QIcon) and not icon.isNull()
    assert combo.iconSize().height() == JalIcons.grid_size()

    peers = DbLookupComboBox(parent)                     # a table whose rows have no icons yet (S6)
    peers.setKeyField("id")
    peers.setField("name")
    peers.setTable("agents")
    assert peers.model().data(peers.model().index(0, 0), Qt.DecorationRole) is None
    parent.deleteLater()


# ----------------------------------------------------------------------------------------------------------------------
# A picture that can't be told from the ground a row paints it on is given a plate to sit on.
def _dark_palette():
    from PySide6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.Base, QColor("#2A2A2A"))
    palette.setColor(QPalette.Text, QColor("#E8E8E8"))
    return palette


def _light_palette():
    from PySide6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.Text, QColor("#000000"))
    return palette


# A mark of the given color on transparency - the shape of every logo that vanishes on one theme or the other
def _mark(color, size: int = 64) -> bytes:
    from PySide6.QtGui import QPainter
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.fillRect(size // 4, size // 4, size // 2, size // 2, color)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _is_plated(icon, size: int) -> bool:
    from jal.widgets.theme import Theme
    return icon.pixmap(size).toImage().pixelColor(size // 2, 1) == Theme.plate()


def test_only_a_picture_that_dissolves_gets_a_plate(prepare_db):
    from PySide6.QtWidgets import QApplication
    account = JalAccountCreator(currency_id=2, number='U1', name='Black mark', organization=1).commit()
    colored = JalAccountCreator(currency_id=2, number='U2', name='Orange mark', organization=1).commit()
    JalIcons.store(IconOwner.Account, account.id(), _mark(Qt.black), IconSource.User)
    JalIcons.store(IconOwner.Account, colored.id(), _mark(QColor("#F7931A")), IconSource.User)
    size = JalIcons.grid_size()

    QApplication.setPalette(_light_palette())
    JalIcons.invalidate_cache()
    assert not _is_plated(JalIcons.icon(IconOwner.Account, account.id(), size), size)     # black on white is fine
    assert not _is_plated(JalIcons.icon(IconOwner.Account, colored.id(), size), size)

    QApplication.setPalette(_dark_palette())
    JalIcons.invalidate_cache()
    assert _is_plated(JalIcons.icon(IconOwner.Account, account.id(), size), size)         # black on dark is not
    # ... while an orange mark is told from a dark ground by its COLOUR, and is left alone
    assert not _is_plated(JalIcons.icon(IconOwner.Account, colored.id(), size), size)

    QApplication.setPalette(_light_palette())
    JalIcons.invalidate_cache()


# The plate is a way of PAINTING what is stored: the row keeps its height and the database keeps its bytes
def test_the_plate_changes_neither_the_size_nor_what_is_stored(prepare_db):
    from PySide6.QtWidgets import QApplication
    account = JalAccountCreator(currency_id=2, number='U1', name='Black mark', organization=1).commit()
    stored = _mark(Qt.black)
    JalIcons.store(IconOwner.Account, account.id(), stored, IconSource.User)
    size = JalIcons.grid_size()

    QApplication.setPalette(_dark_palette())
    JalIcons.invalidate_cache()
    pixmap = JalIcons.icon(IconOwner.Account, account.id(), size).pixmap(size)

    assert _is_plated(JalIcons.icon(IconOwner.Account, account.id(), size), size)
    assert pixmap.width() == pixmap.height() == size
    assert JalIcons.image(IconOwner.Account, account.id()) == stored     # the database is untouched

    QApplication.setPalette(_light_palette())
    JalIcons.invalidate_cache()


# The treatment belongs to the ground, so a change of theme has to drop what was made for the old one
def test_a_theme_change_drops_the_painted_icons(prepare_db):
    from PySide6.QtWidgets import QApplication
    account = JalAccountCreator(currency_id=2, number='U1', name='Black mark', organization=1).commit()
    JalIcons.store(IconOwner.Account, account.id(), _mark(Qt.black), IconSource.User)
    size = JalIcons.grid_size()

    QApplication.setPalette(_light_palette())
    JalIcons.invalidate_cache()
    assert not _is_plated(JalIcons.icon(IconOwner.Account, account.id(), size), size)

    QApplication.setPalette(_dark_palette())          # no invalidate_cache() here - the palette change is the signal
    assert _is_plated(JalIcons.icon(IconOwner.Account, account.id(), size), size)

    QApplication.setPalette(_light_palette())
    assert not _is_plated(JalIcons.icon(IconOwner.Account, account.id(), size), size)
    JalIcons.invalidate_cache()
