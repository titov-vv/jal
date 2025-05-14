from PySide6.QtCore import Property, QObject, QLocale
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox


#-----------------------------------------------------------------------------------------------------------------------
# This class contains a list of predefined constants used by JAL
class Setup:
    INI_FILE = "jal.ini"
    DB_PATH = "jal.sqlite"
    DB_CONNECTION = "JAL.DB"
    DB_REQUIRED_VERSION = 59
    SQLITE_MIN_VERSION = "3.35"
    MAIN_WND_NAME = "JAL_MainWindow"
    INIT_SCRIPT_PATH = 'jal_init.sql'
    UPDATES_PATH = 'updates'
    ICONS_PATH = "img"
    NET_PATH = "net"
    IMPORT_PATH = "data_import"
    EXPORT_PATH = "data_export"
    IMPORT_SCHEMA_NAME = "import_schema.json"
    LANG_PATH = "languages"
    REPORT_PATH = "reports"
    STATEMENT_PATH = "broker_statements"
    STATEMENT_DUMP = "statement_error_log_"
    TEMPLATE_PATH = "templates"
    TAX_REPORT_PATH = "tax_reports"
    TAX_TREATY_PARAM = "tax_treaty"
    UPDATE_PREFIX = 'jal_delta_'
    DEFAULT_ACCOUNT_PRECISION = 2
    NULL_VALUE = '-.--'
    MAX_TIMESTAMP = 9999999999


#-----------------------------------------------------------------------------------------------------------------------
# This class is initialized with global values that is used by JAL
class JalGlobals:
    number_decimal_point = None
    number_group_separator = None

    def __init__(self):
        if self.number_decimal_point is None:
            JalGlobals.init_values()

    @classmethod
    def init_values(cls):
        cls.number_decimal_point = QLocale().decimalPoint()
        cls.number_group_separator = QLocale().groupSeparator()


#-----------------------------------------------------------------------------------------------------------------------
class BookAccount:  # PREDEFINED BOOK ACCOUNTS
    Costs = 1
    Incomes = 2
    Money = 3
    Assets = 4
    Liabilities = 5
    Transfers = 6
    Savings = 7


class PredefinedList:
    def __init(self):
        self._names = {}

    def __contains__(self, key) -> bool:  # Overriding 'in' operator
        return key in self._names

    def get_name(self, name_id, default='') -> str:
        try:
            return self._names[name_id]
        except KeyError:
            return default

    def get_all_names(self) -> dict:
        return self._names

    def load2combo(self, combobox):
        combobox.clear()
        for item in self._names:
            combobox.addItem(self._names[item], userData=item)


class PredefinedAgents(PredefinedList, QObject):  # These constant is linked with 'agents' table initial value and should be present in DB
    db_update_query = "UPDATE agents SET name=:name WHERE id=:id"
    Empty = 1            # Protected by trigger 'keep_predefined_agents' that should be aligned with max ID

    def __init__(self):
        super().__init__()
        self._names = {
            self.Empty: self.tr("None")
        }

class PredefinedCategory(PredefinedList, QObject):  # These constants are linked with 'categories' table initial values and should be present in DB
    db_update_query = "UPDATE categories SET name=:name WHERE id=:id"
    Income = 1             # Protected by trigger 'keep_predefined_categories' that should be aligned with max ID
    Spending = 2
    Profits = 3
    StartingBalance = 4
    Fees = 5
    Taxes = 6
    Dividends = 7
    Interest = 8
    Profit = 9

    def __init__(self):
        super().__init__()
        self._names = {
            self.Income: self.tr("Income"),
            self.Spending: self.tr("Spending"),
            self.Profits: self.tr("Profits"),
            self.StartingBalance: self.tr("Starting balance"),
            self.Fees: self.tr("Fees"),
            self.Taxes: self.tr("Taxes"),
            self.Dividends: self.tr("Dividends"),
            self.Interest: self.tr("Interest"),
            self.Profit: self.tr("Results of investments")
        }

class PredefinedTags(PredefinedList, QObject):   # These constants are linked with 'tags' table initial values but are not mandatory as not used in code
    db_update_query = "UPDATE tags SET tag=:name WHERE id=:id"
    AccountType = 1
    CashAccount = 2
    BankAccount = 3
    CardAccount = 4
    BrokerAccount = 5

    def __init__(self):
        super().__init__()
        self._names = {
            self.AccountType: self.tr("Account type"),
            self.CashAccount: self.tr("Cash"),
            self.BankAccount: self.tr("Bank account"),
            self.CardAccount: self.tr("Card"),
            self.BrokerAccount: self.tr("Broker account")
        }


class PredefinedAsset(PredefinedList, QObject):
    Money = 1
    Stock = 2
    Bond = 3
    ETF = 4
    Commodity = 5
    Derivative = 6
    Forex = 7
    Fund = 8
    Crypto = 9

    def __init__(self):
        super().__init__()
        self._names = {
            self.Money: self.tr("Money"),
            self.Stock: self.tr("Shares"),
            self.Bond: self.tr("Bonds"),
            self.ETF: self.tr("ETFs"),
            self.Commodity: self.tr("Commodities"),
            self.Derivative: self.tr("Derivatives"),
            self.Forex: self.tr("Forex"),
            self.Fund: self.tr("Funds"),
            self.Crypto: self.tr("Crypto-currency")
        }


class DepositActions(PredefinedList, QObject):
    Opening = 1                 # These constants define order of deposit operations processing
    TopUp = 2
    Renewal = 10
    InterestAccrued = 50
    TaxWithheld = 51
    PartialWithdrawal = 99
    Closing = 100

    def __init__(self):
        super().__init__()
        self._names = {
            self.Opening: self.tr("Open term deposit"),
            self.Closing: self.tr("Close term deposit"),
            self.TopUp: self.tr("Top-up term deposit"),
            self.PartialWithdrawal: self.tr("Partial withdrawal from term deposit"),
            self.Renewal: self.tr("Term deposit renewal"),
            self.InterestAccrued: self.tr("Interest accrued"),
            self.TaxWithheld: self.tr("Tax withheld")
        }


class AssetData(PredefinedList, QObject):
    FIGI = 0
    RegistrationCode = 1
    ExpiryDate = 2
    PrincipalValue = 3
    Tag = 4   # This value is used in database trigger(s) after tag deletion
    CUSIP = 5
    IbkrContractId = 6

    def __init__(self):
        super().__init__()
        self._names = {
            self.FIGI: self.tr("FIGI"),
            self.RegistrationCode: self.tr("Reg.code"),
            self.ExpiryDate: self.tr("expiry"),
            self.PrincipalValue: self.tr("principal"),
            self.Tag: self.tr("Tag"),
            self.CUSIP: self.tr("CUSIP"),
            self.IbkrContractId: self.tr("IB contract ID")
        }
        self._types = {
            self.FIGI: "str",
            self.RegistrationCode: "str",
            self.ExpiryDate: "date",
            self.PrincipalValue: "float",
            self.Tag: "tag",
            self.CUSIP: "str",
            self.IbkrContractId: "int"
        }

    def get_type(self, type_id, default='') -> str:
        try:
            return self._types[type_id]
        except KeyError:
            return default


class MarketDataFeed(PredefinedList, QObject):
    NA = -1
    FX = 0
    RU = 1  # MOEX
    US = 2
    EU = 3
    CA = 4
    GB = 5
    FRA = 6  # Frankfurt Borse
    SMA_VICTORIA = 7
    COIN = 8
    MILAN = 9  # Borsa Italiana, Milan Stock Exchange
    WSE = 10    # Warsaw Stock Exchange (WSE)

    def __init__(self):
        super().__init__()
        self._names = {
            self.NA: self.tr("None"),
            self.FX: self.tr("Central banks"),
            self.RU: self.tr("MOEX"),
            self.US: self.tr("NYSE/Nasdaq"),
            self.EU: self.tr("Euronext"),
            self.CA: self.tr("TMX TSX"),
            self.GB: self.tr("LSE"),
            self.FRA: self.tr("Frankfurt Borse"),
            self.SMA_VICTORIA: self.tr("Victoria Seguros"),
            self.COIN: self.tr("Coinbase"),
            self.MILAN: self.tr("Borsa Italiana"),
            self.WSE: self.tr("Warsaw Stock Exchange")
        }


class CustomColor:
    Black = QColor(0, 0, 0)
    DarkGreen = QColor(0, 100, 0)
    DarkRed = QColor(139, 0, 0)
    DarkBlue = QColor(0, 0, 139)
    Blue = QColor(0, 0, 255)
    Grey = QColor(127, 127, 127)
    LightBlue = QColor(150, 200, 255)
    LightPurple = QColor(200, 150, 255)
    LightGreen = QColor(127, 255, 127)
    LightRed = QColor(255, 127, 127)
    LightYellow = QColor(255, 255, 200)


class AssetTypeComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        PredefinedAsset().load2combo(self)

    def get_key(self):
        return self.currentData()

    def set_key(self, value):
        self.setCurrentIndex(self.findData(value))

    key = Property(int, get_key, set_key, user=True)
