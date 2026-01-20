from PySide6.QtCore import Qt
from PySide6.QtSql import QSqlRelation
from PySide6.QtWidgets import QMessageBox
from db.category import JalCategory
from db.common_models_abstract import CmColumn, CmWidth, AbstractReferenceListModel, AbstractReferenceListReadOnlyModel, \
    SqlTreeModel, CmDelegate
from db.peer import JalPeer
from db.tag import JalTag
from jal.widgets.icons import JalIcon

# FIXME Implement SymbolsListModel
# ----------------------------------------------------------------------------------------------------------------------
class AccountListModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("name", self.tr("Name"), width=CmWidth.WIDTH_STRETCH, sort=True),
            CmColumn("currency_id", self.tr("Currency"), delegate_type=CmDelegate.LOOKUP),
            CmColumn("active", self.tr("Act."), width=64, delegate_type=CmDelegate.BOOL),
            CmColumn("investing", self.tr("Invest."), width=64, delegate_type=CmDelegate.BOOL),
            CmColumn("tag_id", self.tr("Tag"), group=True, delegate_type=CmDelegate.REFERENCE, delegate_details='tag'),
            CmColumn("number", self.tr("Account #")),
            CmColumn("reconciled_on", self.tr("Reconciled @"), width=CmWidth.WIDTH_DATETIME, delegate_type=CmDelegate.TIMESTAMP),
            CmColumn("organization_id", self.tr("Bank/Broker"), delegate_type=CmDelegate.REFERENCE, delegate_details='peer'),
            CmColumn("country_id", self.tr("Country"), width=80, delegate_type=CmDelegate.LOOKUP),
            CmColumn("precision", self.tr("Precision")),
            CmColumn("credit", self.tr("Credit limit"), delegate_type=CmDelegate.FLOAT, delegate_details='2')
        ]
        super().__init__("accounts", columns, parent)
        self.set_default_values({'active': 1, 'reconciled_on': 0, 'country_id': 0, 'precision': 2, 'credit': '0'})
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
        self.setRelation(self.fieldIndex("country_id"), QSqlRelation("countries", "id", "code"))

    def data(self, index, role=Qt.DisplayRole):   # Display tag icon as decoration role
        if not index.isValid():
            return None
        if role == Qt.DecorationRole and index.column() == self.fieldIndex('tag_id'):
            return JalIcon[JalTag(super().data(index, Qt.DisplayRole)).icon()]
        return super().data(index, role)

    def removeElement(self, index) -> bool:
        reply = QMessageBox().warning(None, self.tr("Warning"), self.tr("All transactions related with this account will be deleted.\n"
                                                                        "Do you want to delete the account anyway?"),
                                      QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        return super().removeElement(index)


# ----------------------------------------------------------------------------------------------------------------------
class SymbolsListModel(AbstractReferenceListReadOnlyModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("symbol", self.tr("Symbol"), default=True, sort=True),
            CmColumn("asset_id", self.tr("Asset")),
            CmColumn("type_id", self.tr("Asset type"), hide=True, group=True),
            CmColumn("currency_id", self.tr("Currency")),
            CmColumn("location_id", self.tr("Location")),
            CmColumn("full_name", self.tr("Name"), width=CmWidth.WIDTH_STRETCH, details=True),
            CmColumn("icon", '')
        ]
        super().__init__("symbols_ext", columns, parent)

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
    def __init__(self, parent=None):
        columns = [
            CmColumn("name", self.tr("Name"), sort=True, width=CmWidth.WIDTH_STRETCH, delegate_type=CmDelegate.GRID),
            CmColumn("location", self.tr("Location"), delegate_type=CmDelegate.GRID),
            CmColumn("actions_count", self.tr("Docs count"), delegate_type=CmDelegate.FLOAT, delegate_details='0')
        ]
        super().__init__("agents", columns, parent)
        self.set_default_values({"name": self.tr("New peer")})

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
    def __init__(self, parent=None):
        columns = [
            CmColumn("name", self.tr("Name"), sort=True, width=CmWidth.WIDTH_STRETCH, delegate_type=CmDelegate.GRID)
        ]
        super().__init__("categories", columns, parent)
        self.set_default_values({"name": self.tr("New category")})

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
    def __init__(self, parent=None):
        columns = [
            CmColumn("tag", self.tr("Tag"), sort=True, default=True, width=CmWidth.WIDTH_STRETCH, delegate_type=CmDelegate.GRID),
            CmColumn("icon_file", self.tr("Icon filename"), delegate_type=CmDelegate.GRID)
        ]
        super().__init__("tags", columns, parent)
        self.set_default_values({"tag": self.tr("New tag")})

    def data(self, index, role=Qt.DisplayRole):   # Display tag icon as decoration role
        if not index.isValid():
            return None
        if role == Qt.DecorationRole and index.column() == self.fieldIndex('icon_file'):
            return JalIcon[super().data(index, Qt.DisplayRole)]
        return super().data(index, role)


# ----------------------------------------------------------------------------------------------------------------------
class QuotesListModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("timestamp", self.tr("Date"), sort=True, width=CmWidth.WIDTH_DATETIME, delegate_type=CmDelegate.TIMESTAMP),
            CmColumn("asset_id", self.tr("Asset"), width=CmWidth.WIDTH_STRETCH, delegate_type=CmDelegate.REFERENCE, delegate_details='symbol'),
            CmColumn("currency_id", self.tr("Currency"), delegate_type=CmDelegate.LOOKUP),
            CmColumn("quote", self.tr("Quote"), default=True, width=100, delegate_type=CmDelegate.FLOAT, delegate_details='4')
        ]
        super().__init__("quotes", columns, parent)
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))


# ----------------------------------------------------------------------------------------------------------------------
class BaseCurrencyListModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("since_timestamp", self.tr("Date"), sort=True, width=CmWidth.WIDTH_DATETIME, delegate_type=CmDelegate.TIMESTAMP, delegate_details='%d/%m/%Y'),
            CmColumn("currency_id", self.tr("Currency"), width=CmWidth.WIDTH_STRETCH, default=True, delegate_type=CmDelegate.LOOKUP)
        ]
        super().__init__("base_currency", columns, parent)
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))
