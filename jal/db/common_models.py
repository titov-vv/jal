from PySide6.QtCore import Qt
from PySide6.QtSql import QSqlRelation, QSqlRelationalDelegate
from PySide6.QtWidgets import QMessageBox

from db.category import JalCategory
from db.common_models_abstract import AbstractReferenceListModel, AbstractReferenceListReadOnlyModel, SqlTreeModel
from db.peer import JalPeer
from db.tag import JalTag
from jal.widgets.icons import JalIcon
# from jal.widgets.delegates import PeerSelectorDelegate, TimestampDelegate, BoolDelegate, TagSelectorDelegate, FloatDelegate

# FIXME Review and re-enable delegates
# FIXME Implement SymbolsListModel
# ----------------------------------------------------------------------------------------------------------------------
class AccountListModel(AbstractReferenceListModel):
    def __init__(self, parent_view=None):
        columns = [("id", ''),
                   ("name", self.tr("Name")),
                   ("currency_id", self.tr("Currency")),
                   ("active", self.tr("Act.")),
                   ("investing", self.tr("Invest.")),
                   ("tag_id", 'Tag'),
                   ("number", self.tr("Account #")),
                   ("reconciled_on", self.tr("Reconciled @")),
                   ("organization_id", self.tr("Bank/Broker")),
                   ("country_id", self.tr("Country")),
                   ("precision", self.tr("Precision")),
                   ("credit", self.tr("Credit limit"))]
        super().__init__(table="accounts", parent_view=parent_view, columns=columns, sort="name", hide=["id"], group="tag_id", stretch="name")
        self.set_default_values({'active': 1, 'reconciled_on': 0, 'country_id': 0, 'precision': 2, 'credit': '0'})
        self._lookup_delegate = None
        # self._peer_delegate = None
        self._timestamp_delegate = None
        # self._bool_delegate = None
        # self._tag_delegate = None
        self._float_delegate = None
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "code"))

    def data(self, index, role=Qt.DisplayRole):   # Display tag icon as decoration role
        if not index.isValid():
            return None
        if role == Qt.DecorationRole and index.column() == self.fieldIndex('tag_id'):
            return JalIcon[JalTag(super().data(index, Qt.DisplayRole)).icon()]
        return super().data(index, role)

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("active"), 64)
        self._view.setColumnWidth(self.fieldIndex("investing"), 64)
        self._view.setColumnWidth(self.fieldIndex("reconciled_on"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("country_id"), 80)
        self._lookup_delegate = QSqlRelationalDelegate(self._view)
        self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        # self._peer_delegate = PeerSelectorDelegate()
        # self._view.setItemDelegateForColumn(self.fieldIndex("organization_id"), self._peer_delegate)
        # self._timestamp_delegate = TimestampDelegate(parent=self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("reconciled_on"), self._timestamp_delegate)
        # self._bool_delegate = BoolDelegate(self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("active"), self._bool_delegate)
        # self._view.setItemDelegateForColumn(self.fieldIndex("investing"), self._bool_delegate)
        # self._tag_delegate = TagSelectorDelegate(self._view)
        self._view.parent().set_tag_delegate(self.fieldIndex("tag_id"))
        # self._view.setItemDelegateForColumn(self.fieldIndex("tag_id"), self._tag_delegate)
        # self._float_delegate = FloatDelegate(2, parent=self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("credit"), self._float_delegate)

    def removeElement(self, index) -> bool:
        reply = QMessageBox().warning(None, self.tr("Warning"), self.tr("All transactions related with this account will be deleted.\n"
                                                                        "Do you want to delete the account anyway?"),
                                      QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        return super().removeElement(index)


# ----------------------------------------------------------------------------------------------------------------------
class SymbolsListModel(AbstractReferenceListReadOnlyModel):
    def __init__(self, parent_view=None):
        columns = [("id", ''),
                   ("symbol", self.tr("Symbol")),
                   ("asset_id", self.tr("Asset")),
                   ("type_id", self.tr("Asset type")),
                   ("currency_id", self.tr("Currency")),
                   ("location_id", self.tr("Location")),
                   ("full_name", self.tr("Name")),
                   ("icon", '')]
        super().__init__(table="symbols_ext", parent_view=parent_view, columns=columns, default="symbol", sort="symbol", hide=["id", "type_id"],
                         group="type_id", stretch="full_name", details="full_name")

    def configureView(self):
        super().configureView()
        # self._lookup_delegate = QSqlRelationalDelegate(self._view)
        # self._constant_lookup_delegate = ConstantLookupDelegate(MarketDataFeed, self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("country_id"), self._lookup_delegate)
        # self._view.setItemDelegateForColumn(self.fieldIndex("quote_source"), self._constant_lookup_delegate)

    # def removeElement(self, index) -> bool:
    #     used_by_accounts = JalAccount().get_all_accounts(active_only=False, currency_id=self.getId(index))
    #     if len(used_by_accounts):
    #         QMessageBox().warning(None, self.tr("Warning"),
    #                               self.tr("You can't delete currency that is used by account:\n") +
    #                               '\n'.join([x.name() for i, x in enumerate(used_by_accounts) if i < 10]),  # Display first 10 accounts that use the currency
    #                               QMessageBox.Ok)
    #         return False+
    #     reply = QMessageBox().warning(None, self.tr("Warning"),
    #                                   self.tr("All transactions related with this asset will be deleted.\n"
    #                                           "Do you want to delete the asset anyway?"),
    #                                   QMessageBox.Yes, QMessageBox.No)
    #     if reply != QMessageBox.Yes:
    #         return False
    #     return super().removeElement(index)


# ----------------------------------------------------------------------------------------------------------------------
class PeerTreeModel(SqlTreeModel):
    def __init__(self, parent_view=None):
        columns = [("name", self.tr("Name")),
                   ("location", self.tr("Location")),
                   ("actions_count", self.tr("Docs count"))]
        super().__init__(table="agents", parent_view=parent_view, columns=columns, sort="name", stretch="name")
        self.set_default_values({"name": self.tr("New peer")})
        self._int_delegate = None
        self._grid_delegate = None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item_id = index.internalId()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if index.column() == self.fieldIndex("actions_count"):
                return JalPeer(item_id).number_of_documents()
            else:
                return super().data(index, role)
        return None

    def configureView(self):
        super().configureView()
        # self._grid_delegate = GridLinesDelegate(self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("name"), self._grid_delegate)
        # self._view.setItemDelegateForColumn(self.fieldIndex("location"), self._grid_delegate)
        # self._int_delegate = FloatDelegate(0, parent=self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("actions_count"), self._int_delegate)

    def removeElement(self, index) -> bool:
        peer = JalPeer(self.getId(index))
        if peer.is_predefined():
            QMessageBox().warning(None, self.tr("Warning"), self.tr("You can't delete a predefined peer."), QMessageBox.Ok)
            return False
        if peer.is_in_use():
            reply = QMessageBox().warning(None, self.tr("Warning"), self.tr("Peer or one of its child peers are in use.\n"
                                                                            "All related transactions will be deleted together with the peer.\n"
                                                                            "Do you want to delete the peer anyway?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
        return super().removeElement(index)


# ----------------------------------------------------------------------------------------------------------------------
class CategoryTreeModel(SqlTreeModel):
    def __init__(self, parent_view=None):
        super().__init__(table="categories", parent_view=parent_view, columns=[("name", self.tr("Name"))], sort="name", stretch="name")
        self.set_default_values({"name": self.tr("New category")})
        self._bool_delegate = None
        self._grid_delegate = None

    def configureView(self):
        super().configureView()
        # self._grid_delegate = GridLinesDelegate(self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("name"), self._grid_delegate)

    def removeElement(self, index) -> bool:
        category = JalCategory(self.getId(index))
        if category.is_predefined():
            QMessageBox().warning(None, self.tr("Warning"), self.tr("You can't delete a predefined category."), QMessageBox.Ok)
            return False
        if category.is_in_use():
            reply = QMessageBox().warning(None, self.tr("Warning"), self.tr("Category or one of its subcategories are in use.\n"
                                                                            "All related transactions will be deleted together with the category.\n"
                                                                            "Do you want to delete the category anyway?"),
                                          QMessageBox.Yes, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
        return super().removeElement(index)


# ----------------------------------------------------------------------------------------------------------------------
class TagTreeModel(SqlTreeModel):
    def __init__(self, parent_view=None):
        columns = [("tag", self.tr("Tag")), ("icon_file", self.tr("Icon filename"))]
        super().__init__(table="tags", parent_view=parent_view, columns=columns, sort="tag", stretch="tag", default="tag")
        self.set_default_values({"tag": self.tr("New tag")})

    def data(self, index, role=Qt.DisplayRole):   # Display tag icon as decoration role
        if not index.isValid():
            return None
        if role == Qt.DecorationRole and index.column() == self.fieldIndex('icon_file'):
            return JalIcon[super().data(index, Qt.DisplayRole)]
        return super().data(index, role)

    def configureView(self):
        super().configureView()
        # self._grid_delegate = GridLinesDelegate(self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("tag"), self._grid_delegate)
        # self._view.setItemDelegateForColumn(self.fieldIndex("icon_file"), self._grid_delegate)


# ----------------------------------------------------------------------------------------------------------------------
class QuotesListModel(AbstractReferenceListModel):
    def __init__(self, parent_view=None):
        columns = [("id", ''),
                   ("timestamp", self.tr("Date")),
                   ("asset_id", self.tr("Asset")),
                   ("currency_id", self.tr("Currency")),
                   ("quote", self.tr("Quote"))]
        super().__init__(table="quotes", parent_view=parent_view, columns=columns, sort="timestamp", hide=["id"], stretch="asset_id", default="quote")
        self._asset_delegate = None
        self._timestamp_delegate = None
        self._lookup_delegate = None
        self._float_delegate = None
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("timestamp"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000 00:00:00") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("quote"), 100)

        # self._asset_delegate = SymbolSelectorDelegate()
        # self._view.setItemDelegateForColumn(self.fieldIndex("asset_id"), self._asset_delegate)
        # self._timestamp_delegate = TimestampDelegate(parent=self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("timestamp"), self._timestamp_delegate)
        # self._lookup_delegate = QSqlRelationalDelegate(self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
        # self._float_delegate = FloatDelegate(4, allow_tail=True, parent=self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("quote"), self._float_delegate)


# ----------------------------------------------------------------------------------------------------------------------
class BaseCurrencyListModel(AbstractReferenceListModel):
    def __init__(self, parent_view=None):
        columns = [("id", ''),
                   ("since_timestamp", self.tr("Date")),
                   ("currency_id", self.tr("Currency"))]
        super().__init__(table="base_currency", parent_view=parent_view, columns=columns, sort="since_timestamp", hide=["id"], stretch="currency_id", default="currency_id")
        self._timestamp_delegate = None
        self._lookup_delegate = None
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))

    def configureView(self):
        super().configureView()
        self._view.setColumnWidth(self.fieldIndex("since_timestamp"),
                                  self._view.fontMetrics().horizontalAdvance("00/00/0000") * 1.1)
        self._view.setColumnWidth(self.fieldIndex("currency_id"), 100)

        # self._timestamp_delegate = TimestampDelegate(display_format='%d/%m/%Y', parent=self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("since_timestamp"), self._timestamp_delegate)
        # self._lookup_delegate = QSqlRelationalDelegate(self._view)
        # self._view.setItemDelegateForColumn(self.fieldIndex("currency_id"), self._lookup_delegate)
