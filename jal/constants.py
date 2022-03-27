from PySide6.QtGui import QColor

class Setup:
    DB_PATH = "jal.sqlite"
    DB_CONNECTION = "JAL.DB"
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
    TEMPLATE_PATH = "templates"
    UPDATE_PREFIX = 'jal_delta_'
    TARGET_SCHEMA = 32
    CALC_TOLERANCE = 1e-10
    DISP_TOLERANCE = 1e-4


class BookAccount:  # PREDEFINED BOOK ACCOUNTS
    Costs = 1
    Incomes = 2
    Money = 3
    Assets = 4
    Liabilities = 5
    Transfers = 6


class PredefindedAccountType:
    Cash = 1
    Bank = 2
    Card = 3
    Investment = 4
    Savings = 5
    Loans = 6
    eWallet = 7


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


class PredefinedAsset:   # Aligned with 'asset_types' table
    Money = 1
    Stock = 2
    Bond = 3
    ETF = 4
    Commodity = 5
    Derivative = 6
    Forex = 7
    Fund = 8


class AssetData:
    RegistrationCode = 1
    ExpiryDate = 2
    PrincipalValue = 3


class PredefinedPeer:
    Financial = 1


class MarketDataFeed:
    NA = -1
    CBR = 0
    RU = 1
    US = 2
    EU = 3
    CA = 4
    GB = 5
    FRA = 6


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

