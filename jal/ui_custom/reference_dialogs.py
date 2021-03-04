from jal.widgets.view_delegate import *
from jal.constants import ColumnWidth
from jal.ui_custom.helpers import g_tr
import jal.ui_custom.reference_data as ui               # Full import due to "cyclic" reference
from jal.ui_custom.reference_data import ReferenceDataDialog, ReferenceBoolDelegate, \
    ReferenceLookupDelegate, ReferenceTimestampDelegate


# ----------------------------------------------------------------------------------------------------------------------
class AccountTypeListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "account_types",
                                     [("id", None, 0, None, None),
                                      ("name", g_tr('TableViewConfig', "Account Type"), ColumnWidth.STRETCH,
                                       Qt.AscendingOrder, None)],
                                     title=g_tr('TableViewConfig', g_tr('TableViewConfig', "Account Types")))

# ----------------------------------------------------------------------------------------------------------------------
class AccountsListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "accounts",
                                     [("id", None, 0, None, None),
                                      ("name", g_tr('AccountButton', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                                      ("type_id", None, 0, None, None),
                                      ("currency_id", g_tr('AccountButton', "Currency"), None, None, ReferenceLookupDelegate),
                                      ("active", g_tr('AccountButton', "Act."), 32, None, ReferenceBoolDelegate),
                                      ("number", g_tr('AccountButton', "Account #"), None, None, None),
                                      ("reconciled_on", g_tr('AccountButton', "Reconciled @"), ColumnWidth.FOR_DATETIME, None, ReferenceTimestampDelegate),
                                      ("organization_id", g_tr('AccountButton', "Bank"), None, None, ReferenceLookupDelegate)],
                                     title=g_tr('AccountsListDialog', "Accounts"),
                                     search_field="full_name",
                                     toggle=("active", g_tr('AccountButton', "Show inactive")),
                                     relations=[("type_id", "account_types", "id", "name",
                                                 g_tr('AccountButton', "Account type:")),
                                                ("currency_id", "currencies", "id", "name", None),
                                                ("organization_id", "agents", "id", "name", None)])

# ----------------------------------------------------------------------------------------------------------------------
class AssetListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "assets",
                                          [("id", None, 0, None, None),
                                           ("name", g_tr('TableViewConfig', "Symbol"), None, Qt.AscendingOrder, None),
                                           ("type_id", None, 0, None, None),
                                           ("full_name", g_tr('TableViewConfig', "Name"), ColumnWidth.STRETCH, None, None),
                                           ("isin", g_tr('TableViewConfig', "ISIN"), None, None, None),
                                           ("country_id", g_tr('TableViewConfig', "Country"), None, None, ui.ReferenceLookupDelegate),
                                           ("src_id", g_tr('TableViewConfig', "Data source"), None, None, ui.ReferenceLookupDelegate)],
                                          title=g_tr('TableViewConfig', "Assets"),
                                          search_field="full_name",
                                          relations=[("type_id", "asset_types", "id", "name", g_tr('TableViewConfig', "Asset type:")),
                                                     ("country_id", "countries", "id", "name", None),
                                                     ("src_id", "data_sources", "id", "name", None)])

# ----------------------------------------------------------------------------------------------------------------------
class PeerListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "agents_ext",
                                          [("id", " ", 16, None, ui.ReferenceTreeDelegate),
                                           ("pid", None, 0, None, None),
                                           ("name", g_tr('TableViewConfig', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                                           ("location", g_tr('TableViewConfig', "Location"), None, None, None),
                                           ("actions_count", g_tr('TableViewConfig', "Docs count"), None, None, ui.ReferenceIntDelegate),
                                           ("children_count", None, None, None, None)],
                                          title=g_tr('TableViewConfig', "Peers"), search_field="name", tree_view=True)

# ----------------------------------------------------------------------------------------------------------------------
class CategoryListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "categories_ext",
                                             [("id", " ", 16, None, ui.ReferenceTreeDelegate),
                                              ("pid", None, 0, None, None),
                                              ("name", g_tr('TableViewConfig', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                                              ("often", g_tr('TableViewConfig', "Often"), None, None, ui.ReferenceBoolDelegate),
                                              ("special", None, 0, None, None),
                                              ("children_count", None, None, None, None)],
                                             title=g_tr('TableViewConfig', "Categories"), search_field="name", tree_view=True)

# ----------------------------------------------------------------------------------------------------------------------
class TagsListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "tags",
                                             [("id", None, 0, None, None),
                                              ("tag", g_tr('TableViewConfig', "Tag"), ColumnWidth.STRETCH, Qt.AscendingOrder, None)],
                                             title=g_tr('TableViewConfig', "Tags"), search_field="tag")

# ----------------------------------------------------------------------------------------------------------------------
class CountryListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "countries",
                                     [("id", None, 0, None, None),
                                      ("name", g_tr('TableViewConfig', "Country"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                                      ("code", g_tr('TableViewConfig', "Code"), 50, None, None),
                                      ("tax_treaty", g_tr('TableViewConfig', "Tax Treaty"), None, None,
                                       ui.ReferenceBoolDelegate)],
                                     title=g_tr('TableViewConfig', "Countries"), search_field="name")

# ----------------------------------------------------------------------------------------------------------------------
class QuotesListDialog(ReferenceDataDialog):
    def __init__(self):
        ReferenceDataDialog.__init__(self, "quotes",
                                     [("id", None, 0, None, None),
                                      ("timestamp", g_tr('TableViewConfig', "Date"), ColumnWidth.FOR_DATETIME, None, ui.ReferenceTimestampDelegate),
                                      ("asset_id", g_tr('TableViewConfig', "Asset"), None, None, ui.ReferenceLookupDelegate),
                                      ("quote", g_tr('TableViewConfig', "Quote"), 100, None, None)],
                                     title=g_tr('TableViewConfig', "Quotes"), search_field="name",
                                     relations=[("asset_id", "assets", "id", "name", None)]
                                     )

# ----------------------------------------------------------------------------------------------------------------------

