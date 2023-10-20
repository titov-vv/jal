from PySide6.QtCore import Property, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox


class Setup:
    DB_PATH = "jal.sqlite"
    DB_CONNECTION = "JAL.DB"
    DB_REQUIRED_VERSION = 50
    SQLITE_MIN_VERSION = "3.35"
    MAIN_WND_NAME = "JAL_MainWindow"
    INIT_SCRIPT_PATH = 'jal_init.sql'
    UPDATES_PATH = 'updates'
    ICONS_PATH = "img"
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


class BookAccount:  # PREDEFINED BOOK ACCOUNTS
    Costs = 1
    Incomes = 2
    Money = 3
    Assets = 4
    Liabilities = 5
    Transfers = 6


class PredefinedList:
    def __init(self):
        self._names = {}

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


class PredefinedAccountType(PredefinedList, QObject):
    Cash = 1
    Bank = 2
    Card = 3
    Investment = 4
    Savings = 5
    Loans = 6
    eWallet = 7

    def __init__(self):
        super().__init__()
        self._names = {
            self.Cash: self.tr("Cash"),
            self.Bank: self.tr("Bank accounts"),
            self.Card: self.tr("Cards"),
            self.Investment: self.tr("Investments"),
            self.Savings: self.tr("Savings"),
            self.Loans: self.tr("Debts / Loans"),
            self.eWallet: self.tr("e-Wallets")
        }


class PredefinedCategory:
    Income = 1
    Spending = 2
    Profits = 3
    StartingBalance = 4
    Fees = 5
    Taxes = 6
    Dividends = 7
    Interest = 8
    Profit = 9


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


class AssetData:
    RegistrationCode = 1
    ExpiryDate = 2
    PrincipalValue = 3
    Tag = 4


class MarketDataFeed(PredefinedList, QObject):
    NA = -1
    FX = 0
    RU = 1
    US = 2
    EU = 3
    CA = 4
    GB = 5
    FRA = 6
    SMA_VICTORIA = 7

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
            self.SMA_VICTORIA: self.tr("Victoria Seguros")
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
