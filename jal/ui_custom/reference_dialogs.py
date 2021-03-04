from jal.widgets.view_delegate import *
from jal.constants import ColumnWidth
from PySide2.QtCore import Slot
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
                                          title="Assets",
                                     search_field="full_name",
                                          relations=[("type_id", "asset_types", "id", "name", g_tr('TableViewConfig', "Asset type:")),
                                                     ("country_id", "countries", "id", "name", None),
                                                     ("src_id", "data_sources", "id", "name", None)])

# TODO Probably better idea is to subclass ReferenceDataDialog for each table instead of self.dialogs dictionary
class ReferenceDialogs:
    DLG_TITLE = 0
    DLG_COLUMNS = 1
    DLG_SEARCH = 2
    DLG_TOGGLE = 3
    DLG_TREE = 4
    DLG_RELATIONS = 5

    def __init__(self, parent):
        self.parent = parent
        self.dialogs = {
            "agents_ext": (
                g_tr('TableViewConfig', "Peers"),
                [("id", " ", 16, None, ui.ReferenceTreeDelegate),
                 ("pid", None, 0, None, None),
                 ("name", g_tr('TableViewConfig', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                 ("location", g_tr('TableViewConfig', "Location"), None, None, None),
                 ("actions_count", g_tr('TableViewConfig', "Docs count"), None, None, ui.ReferenceIntDelegate),
                 ("children_count", None, None, None, None)],
                "name",
                None,
                True,
                None
            ),
            "categories_ext": (
                g_tr('TableViewConfig', "Categories"),
                [("id", " ", 16, None, ui.ReferenceTreeDelegate),
                 ("pid", None, 0, None, None),
                 ("name", g_tr('TableViewConfig', "Name"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                 ("often", g_tr('TableViewConfig', "Often"), None, None, ui.ReferenceBoolDelegate),
                 ("special", None, 0, None, None),
                 ("children_count", None, None, None, None)],
                "name",
                None,
                True,
                None
            ),
            "tags": (
                g_tr('TableViewConfig', "Tags"),
                [("id", None, 0, None, None),
                 ("tag", g_tr('TableViewConfig', "Tag"), ColumnWidth.STRETCH, Qt.AscendingOrder, None)],
                "tag",
                None,
                False,
                None
            ),
            "countries": (
                g_tr('TableViewConfig', "Countries"),
                [("id", None, 0, None, None),
                 ("name", g_tr('TableViewConfig', "Country"), ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                 ("code", g_tr('TableViewConfig', "Code"), 50, None, None),
                 ("tax_treaty", g_tr('TableViewConfig', "Tax Treaty"), None, None, ui.ReferenceBoolDelegate)],
                None,
                None,
                False,
                None
            ),
            "quotes": (
                g_tr('TableViewConfig', "Quotes"),
                [("id", None, 0, None, None),
                 ("timestamp", g_tr('TableViewConfig', "Date"), ColumnWidth.FOR_DATETIME, None,
                  ui.ReferenceTimestampDelegate),
                 ("asset_id", g_tr('TableViewConfig', "Asset"), None, None, ui.ReferenceLookupDelegate),
                 ("quote", g_tr('TableViewConfig', "Quote"), 100, None, None)],
                "name",
                None,
                False,
                [("asset_id", "assets", "id", "name", None)]
            )
        }

    def tr(self, name):
        pass

    @Slot()
    def show(self, table_name):
        if table_name == "account_types":
            AccountTypeListDialog().exec_()
        elif table_name == "accounts":
            AccountsListDialog().exec_()
        elif table_name == "assets":
            AssetListDialog().exec_()
        else:
            ui.ReferenceDataDialog(table_name,
                                   self.dialogs[table_name][self.DLG_COLUMNS],
                                   title=self.dialogs[table_name][self.DLG_TITLE],
                                   search_field=self.dialogs[table_name][self.DLG_SEARCH],
                                   toggle=self.dialogs[table_name][self.DLG_TOGGLE],
                                   tree_view=self.dialogs[table_name][self.DLG_TREE],
                                   relations=self.dialogs[table_name][self.DLG_RELATIONS]
                                   ).exec_()
