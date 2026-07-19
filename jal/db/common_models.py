from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt
from PySide6.QtSql import QSqlRelation
from PySide6.QtWidgets import QMessageBox
from jal.constants import CmColumn, CmWidth, CmDelegate, CmReference, PredefinedAccountType, PredefinedAgents, \
    AccountData, AssetLocation
from jal.db.category import JalCategory
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.country import JalCountry
from jal.db.common_models_abstract import AbstractReferenceListModel, SqlTreeModel
from jal.db.peer import JalPeer
from jal.db.token_blacklist import JalTokenBlacklist
from jal.widgets.icons import JalIcon


# ----------------------------------------------------------------------------------------------------------------------
class AccountListModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("name", self.tr("Name"), width=CmWidth.WIDTH_STRETCH, sort=True),
            CmColumn("currency_id", self.tr("Currency"), delegate_type=CmDelegate.LOOKUP),
            CmColumn("active", self.tr("Act."), width=64, delegate_type=CmDelegate.BOOL),
            CmColumn("investing", self.tr("Invest."), width=64, delegate_type=CmDelegate.BOOL),
            CmColumn("reconciled_on", self.tr("Reconciled @"), width=CmWidth.WIDTH_DATETIME, delegate_type=CmDelegate.TIMESTAMP),
            CmColumn("organization_id", self.tr("Bank/Broker"), delegate_type=CmDelegate.REFERENCE, delegate_details=CmReference.PEER),
            CmColumn("account_type", self.tr("Type"), group=True, delegate_type=CmDelegate.CONSTANT, delegate_details=PredefinedAccountType)
        ]
        super().__init__("accounts", columns, parent)
        self.set_default_values({'active': 1, 'reconciled_on': 0, 'account_type': PredefinedAccountType.Cash})
        self.setRelation(self.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "symbol"))

    # Accounts are edited via the modal AccountDialog, not in-line - the grid is display/selection only. Marking the
    # cells non-editable makes every delegate (including BoolDelegate's click-to-toggle) honor that automatically.
    def flags(self, index):
        return super().flags(index) & ~Qt.ItemIsEditable

    def data(self, index, role=Qt.DisplayRole):   # Display account-type icon as decoration role
        if not index.isValid():
            return None
        if role == Qt.DecorationRole and index.column() == self.fieldIndex('account_type'):
            return JalIcon[JalAccount.get_type_icon(super().data(index, Qt.DisplayRole))]
        return super().data(index, role)

    def removeElement(self, index) -> bool:
        reply = QMessageBox().warning(None, self.tr("Warning"), self.tr("All transactions related with this account will be deleted.\n"
                                                                        "Do you want to delete the account anyway?"),
                                      QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        return super().removeElement(index)


# ----------------------------------------------------------------------------------------------------------------------
# Single-record model of the 'accounts' table, used by AccountDialog via a QDataWidgetMapper to edit one account.
# The column list must enumerate every 'accounts' field in physical table order, because the mapper addresses model
# sections by index (fieldIndex() returns the position within this list). No relations are set here so that the mapped
# lookup fields (currency_id, organization_id) expose their raw ids to the DbLookupComboBox editors.
class AccountRecordModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("name", self.tr("Name"), default=True, width=CmWidth.WIDTH_STRETCH),
            CmColumn("currency_id", self.tr("Currency")),
            CmColumn("active", self.tr("Active")),
            CmColumn("investing", self.tr("Investing")),
            CmColumn("reconciled_on", self.tr("Reconciled @")),
            CmColumn("organization_id", self.tr("Bank/Broker")),
            CmColumn("account_type", self.tr("Type"))
        ]
        super().__init__("accounts", columns, parent)
        self.set_default_values({'name': '', 'currency_id': JalAsset.get_base_currency(), 'active': 1,
                                 'investing': 0, 'reconciled_on': 0, 'organization_id': PredefinedAgents.Empty,
                                 'account_type': PredefinedAccountType.Cash})


# ----------------------------------------------------------------------------------------------------------------------
# Editable model of the 'account_data' table - the flexible set of per-account attributes (number/credit/country/
# precision etc). Bind it to a particular account with filterBy("account_id", account_id).
class AccountDataModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("account_id", '', hide=True),
            CmColumn("datatype", self.tr("Attribute"), default=True),
            CmColumn("value", self.tr("Value"), width=CmWidth.WIDTH_STRETCH)
        ]
        super().__init__("account_data", columns, parent)
        self._types = AccountData()
        self.set_default_values({'datatype': AccountData.Number, 'value': ''})

    # (account_id, datatype) must be unique, so adding another row with the default attribute type is refused
    # while one already exists for this account - the user has to change its type first.
    def addElement(self, index, in_group=0):
        if self._read("SELECT id FROM account_data WHERE account_id=:aid AND datatype=:dt",
                      [(":aid", self._filter_value), (":dt", self._default_values['datatype'])]) is not None:
            QMessageBox().warning(None, self.tr("Row not added"),
                                  self.tr("Please fill in the previously added attribute before adding a new one"), QMessageBox.Ok)
            return
        super().addElement(index, in_group)

    # Displays translated attribute name and value formatted according to its type
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and index.isValid():
            if index.column() == self.fieldIndex("datatype"):
                return self._types.get_name(super().data(index, role))
            if index.column() == self.fieldIndex("value"):
                datatype = super().data(index.sibling(index.row(), self.fieldIndex("datatype")), role)
                return self._format_value(datatype, super().data(index, role))
        return super().data(index, role)

    def _format_value(self, datatype, value):
        datatype_of = self._types.get_type(datatype)
        try:
            if datatype_of == "str" or datatype_of == "int":
                return value
            elif datatype_of == "float":
                return f"{Decimal(value):.2f}"
            elif datatype_of == "country":
                return JalCountry(int(value)).name()
            elif datatype_of == "chain":
                return AssetLocation().get_name(int(value))
        except (ValueError, InvalidOperation, TypeError):
            return ''
        return value


# ----------------------------------------------------------------------------------------------------------------------
class PeerTreeModel(SqlTreeModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("name", self.tr("Name"), sort=True, width=CmWidth.WIDTH_STRETCH, delegate_type=CmDelegate.GRID),
            CmColumn("location", self.tr("Location"), delegate_type=CmDelegate.GRID),
            CmColumn("actions_count", self.tr("Docs count"), delegate_type=CmDelegate.FLOAT, delegate_details=0)
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
            CmColumn("asset_id", self.tr("Asset"), width=CmWidth.WIDTH_STRETCH, delegate_type=CmDelegate.REFERENCE, delegate_details=CmReference.ASSET_VIA_SYMBOL),
            CmColumn("currency_id", self.tr("Currency"), delegate_type=CmDelegate.LOOKUP),
            CmColumn("quote", self.tr("Quote"), default=True, width=100, delegate_type=CmDelegate.FLOAT, delegate_details=4)
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


# ----------------------------------------------------------------------------------------------------------------------
# Tokens that were found in a wallet but must never be imported (see jal.data_import.token_filter).
# Deleting a row un-blacklists the token, so it will be imported by the next fetch from the blockchain.
class TokenBlacklistModel(AbstractReferenceListModel):
    def __init__(self, parent=None):
        columns = [
            CmColumn("id", '', hide=True),
            CmColumn("location_id", self.tr("Chain"), group=True, delegate_type=CmDelegate.CONSTANT, delegate_details=AssetLocation),
            CmColumn("address", self.tr("Address"), sort=True, default=True, width=CmWidth.WIDTH_STRETCH),
            CmColumn("name_hint", self.tr("Token")),
            CmColumn("added_ts", self.tr("Added @"), width=CmWidth.WIDTH_DATETIME, delegate_type=CmDelegate.TIMESTAMP),
            CmColumn("auto", self.tr("Auto"), width=64, delegate_type=CmDelegate.BOOL)
        ]
        super().__init__("token_blacklist", columns, parent)
        self.set_default_values({'location_id': AssetLocation.ETH_BLOCKCHAIN, 'address': '', 'name_hint': '', 'added_ts': 0, 'auto': 0})   # A manually added token is not an automatic one

    # The table is maintained by the token filter and by this dialog only, so the shared cache of
    # JalTokenBlacklist has to be dropped after any change made here.
    def submitAll(self):
        result = super().submitAll()
        if result:
            JalTokenBlacklist.db_cache.clear_cache()
        return result
