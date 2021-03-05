from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from jal.widgets.view_delegate import *
from jal.constants import ColumnWidth
from jal.ui_custom.helpers import g_tr
from jal.ui_custom.reference_data import ReferenceDataDialog, ReferenceBoolDelegate, \
    ReferenceLookupDelegate, ReferenceTimestampDelegate, ReferenceTreeDelegate, ReferenceIntDelegate


# ----------------------------------------------------------------------------------------------------------------------
class AccountTypeListDialog(ReferenceDataDialog):
    def __init__(self):
        self.columns = [("id", None, 0, None, None),
                        ("name", g_tr('ReferenceDataDialog', "Account Type"), ColumnWidth.STRETCH,
                         Qt.AscendingOrder, None)]
        self.relations = None

        ReferenceDataDialog.__init__(self)
        self.table = "account_types"
        self.setup_db_model()
        self.search_field = None
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Account Types"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class AccountListDialog(ReferenceDataDialog):
    def __init__(self):
        self.columns = [("id", None, 0, None, None),
                        ("name", g_tr('ReferenceDataDialog', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                        ("type_id", None, 0, None, None),
                        ("currency_id", g_tr('ReferenceDataDialog', "Currency"), None, None, ReferenceLookupDelegate),
                        ("active", g_tr('ReferenceDataDialog', "Act."), 32, None, ReferenceBoolDelegate),
                        ("number", g_tr('ReferenceDataDialog', "Account #"), None, None, None),
                        ("reconciled_on", g_tr('ReferenceDataDialog', "Reconciled @"), ColumnWidth.FOR_DATETIME, None,
                         ReferenceTimestampDelegate),
                        ("organization_id", g_tr('ReferenceDataDialog', "Bank"), None, None, ReferenceLookupDelegate),
                        ("country_id", g_tr('TableViewConfig', "CC"), 50, None, ReferenceLookupDelegate)]
        self.relations = [("type_id", "account_types", "id", "name", g_tr('ReferenceDataDialog', "Account type:")),
                          ("currency_id", "currencies", "id", "name", None),
                          ("organization_id", "agents", "id", "name", None),
                          ("country_id", "countries", "id", "code", None)]

        ReferenceDataDialog.__init__(self)
        self.table = "accounts"
        self.setup_db_model(with_relations=True)
        self.model.setRelation(self.model.fieldIndex("type_id"), QSqlRelation("account_types", "id", "name"))
        self.model.setRelation(self.model.fieldIndex("currency_id"), QSqlRelation("currencies", "id", "name"))
        self.model.setRelation(self.model.fieldIndex("organization_id"), QSqlRelation("agents", "id", "name"))
        self.model.setRelation(self.model.fieldIndex("country_id"), QSqlRelation("countries", "id", "code"))

        self.search_field = "full_name"
        self.tree_view = False
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Accounts"))
        self.Toggle.setVisible(True)
        self.toggle_field = "active"
        self.Toggle.setText(g_tr('ReferenceDataDialog', "Show inactive"))

# ----------------------------------------------------------------------------------------------------------------------
class AssetListDialog(ReferenceDataDialog):
    def __init__(self):
        self.columns = [("id", None, 0, None, None),
                        ("name", g_tr('ReferenceDataDialog', "Symbol"), None, Qt.AscendingOrder, None),
                        ("type_id", None, 0, None, None),
                        ("full_name", g_tr('ReferenceDataDialog', "Name"), ColumnWidth.STRETCH, None, None),
                        ("isin", g_tr('ReferenceDataDialog', "ISIN"), None, None, None),
                        ("country_id", g_tr('ReferenceDataDialog', "Country"), None, None, ReferenceLookupDelegate),
                        ("src_id", g_tr('ReferenceDataDialog', "Data source"), None, None, ReferenceLookupDelegate)]
        self.relations = [("type_id", "asset_types", "id", "name", g_tr('ReferenceDataDialog', "Asset type:")),
                          ("country_id", "countries", "id", "name", None),
                          ("src_id", "data_sources", "id", "name", None)]

        ReferenceDataDialog.__init__(self)
        self.table = "assets"
        self.setup_db_model(with_relations=True)
        self.model.setRelation(self.model.fieldIndex("type_id"), QSqlRelation("asset_types", "id", "name"))
        self.model.setRelation(self.model.fieldIndex("country_id"), QSqlRelation("countries", "id", "name"))
        self.model.setRelation(self.model.fieldIndex("src_id"), QSqlRelation("data_sources", "id", "name"))

        self.search_field = "full_name"
        self.tree_view = False
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Assets"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class PeerListDialog(ReferenceDataDialog):
    def __init__(self):
        self.columns = [("id", " ", 16, None, ReferenceTreeDelegate),
                        ("pid", None, 0, None, None),
                        ("name", g_tr('ReferenceDataDialog', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                        ("location", g_tr('ReferenceDataDialog', "Location"), None, None, None),
                        ("actions_count", g_tr('ReferenceDataDialog', "Docs count"), None, None, ReferenceIntDelegate),
                        ("children_count", None, None, None, None)]
        self.relations = None

        ReferenceDataDialog.__init__(self)
        self.table = "agents_ext"
        self.setup_db_model()

        self.search_field = "name"
        self.tree_view = True
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Peers"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class CategoryListDialog(ReferenceDataDialog):
    def __init__(self):
        self.columns = [("id", " ", 16, None, ReferenceTreeDelegate),
                        ("pid", None, 0, None, None),
                        ("name", g_tr('ReferenceDataDialog', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                        ("often", g_tr('ReferenceDataDialog', "Often"), None, None, ReferenceBoolDelegate),
                        ("special", None, 0, None, None),
                        ("children_count", None, None, None, None)]
        self.relations = None

        ReferenceDataDialog.__init__(self)
        self.table = "categories_ext"
        self.setup_db_model()

        self.search_field = "name"
        self.tree_view = True
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Categories"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class TagsListDialog(ReferenceDataDialog):
    def __init__(self):
        self.columns = [("id", None, 0, None, None),
                        ("tag", g_tr('ReferenceDataDialog', "Tag"), ColumnWidth.STRETCH, Qt.AscendingOrder, None)]
        self.relations = None

        ReferenceDataDialog.__init__(self)
        self.table = "tags"
        self.setup_db_model()

        self.search_field = "tag"
        self.tree_view = False
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Tags"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class CountryListDialog(ReferenceDataDialog):
    def __init__(self):
        self.columns = [("id", None, 0, None, None),
                        ("name", g_tr('ReferenceDataDialog', "Country"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                        ("code", g_tr('ReferenceDataDialog', "Code"), 50, None, None),
                        ("tax_treaty", g_tr('ReferenceDataDialog', "Tax Treaty"), None, None,
                         ReferenceBoolDelegate)]
        self.relations = None

        ReferenceDataDialog.__init__(self)
        self.table = "countries"
        self.setup_db_model()

        self.search_field = "name"
        self.tree_view = False
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Countries"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------
class QuotesListDialog(ReferenceDataDialog):
    def __init__(self):
        self.columns = [("id", None, 0, None, None),
                        ("timestamp", g_tr('ReferenceDataDialog', "Date"), ColumnWidth.FOR_DATETIME, None,
                         ReferenceTimestampDelegate),
                        ("asset_id", g_tr('ReferenceDataDialog', "Asset"), None, None, ReferenceLookupDelegate),
                        ("quote", g_tr('ReferenceDataDialog', "Quote"), 100, None, None)]
        self.relations = [("asset_id", "assets", "id", "name", None)]

        ReferenceDataDialog.__init__(self)
        self.table = "quotes"
        self.setup_db_model(with_relations=True)
        self.model.setRelation(self.model.fieldIndex("asset_id"), QSqlRelation("assets", "id", " name"))


        self.search_field = "name"
        self.tree_view = False
        self.setup_ui()
        self.setWindowTitle(g_tr('ReferenceDataDialog', "Quotes"))
        self.Toggle.setVisible(False)

# ----------------------------------------------------------------------------------------------------------------------

