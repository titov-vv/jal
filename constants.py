from PySide2.QtGui import QColor

class Setup:
    DB_PATH = "ledger.sqlite"
    INIT_SCRIPT_PATH = 'ledger.sql'
    TARGET_SCHEMA = 6
    CALC_TOLERANCE = 1e-10
    DISP_TOLERANCE = 1e-4


class ColumnWidth:
    STRETCH = -1
    FOR_DATETIME = -2


class BookAccount:  # PREDEFINED BOOK ACCOUNTS
    Costs = 1
    Incomes = 2
    Money = 3
    Assets = 4
    Liabilities = 5
    Transfers = 6


class TransactionType:   # PREDEFINED TRANSACTION TYPES
    Action = 1
    Dividend = 2
    Trade = 3
    Transfer = 4

class ActionSubtype:
    SingleIncome = -1
    SingleSpending = 1

class TransferSubtype:   # TRANSFER SUB-TYPES
    Fee = 0
    Outgoing = -1
    Incoming = 1


class CorporateAction:   # CORPORATE ACTIONS FOR ASSETS
    NA = 0
    Conversion = 1
    SpinOff = 2


class PredefinedCategory:
    Income = 1
    Spending = 2
    Profits = 3
    Fees = 5
    Taxes = 6
    Dividends = 7
    Interest = 8
    Profit = 9


class PredefinedAsset:
    Money = 1
    Stock = 2
    Bond = 3
    ETF = 4


class PredefinedPeer:
    Financial = 1


class MarketDataFeed:
    NA = -1
    CBR = 0
    RU = 1
    US = 2
    EU = 3


class CustomColor:
    DarkGreen = QColor(0, 100, 0)
    DarkRed = QColor(139, 0, 0)
    DarkBlue = QColor(0, 0, 139)
    Blue = QColor(0, 0, 255)
    LightBlue = QColor(150, 200, 255)
    LightPurple = QColor(200, 150, 255)
    LightGreen = QColor(127, 255, 127)
    LightRed = QColor(255, 127, 127)
    LightYellow = QColor(255, 255, 200)

