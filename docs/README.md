# ledger
ledger is a project for personal finance tracking.

*[English](README.md), [Русский](README.ru.md)*

It was designed to keep records of personal incomes/spendings and investments with up-to-date information about account's balances and portfolio value.

### Main features
- multiple accounts with different currencies (base currency is russian rouble but might be changed in future versions)
- 4 types of transactions: 
    1. Generic income/spending operations that may be splitted into several categories
    2. Transfers of money between different accounts and currencies
    3. Buy/Sell operation for securities (future plan is to support merges and splits)
    4. Dividends for stocks (Bond coupons may be recorded the same way)
- basic reports:
    1. monthly incomes/spendings splitted by category
    2. profit/loss report for investments accounts
    3. closed deals report 
- stock quotes updates for US (Yahoo), EU (Euronext) and RU (MOEX) exchanges traded stocks
- securities transactions import from Quik HTML-reports for russian brokers and from Interactive Brokers flex-queries
- tax report preparation for foreign investments according to Russian Tax Law
- *experimental* download russian electronic slips from russian tax authority:
    1. QR code may be scanned from camera, clipboard image or image file on disk
    2. Authorization via login/password to FNS personal account or ESIA/Gosuslugi (no passwords are stored in the progam, only SessionId is stored - you may check in source code)

### Installation
ledger was created to be portable - it doesn't require specific installation instructions. All you need is to have Python 3.8.1 or higher and satisfy dependencies listed below.
Then you may download/clone code from [the GitHub repository](https://github.com/titov-vv/ledger) and start the program by running: `main.py` on Windows or `./main.py` on Linux or you may simply double click the filename if your system is setup to launch python interpreter this way.
Database will be initialized automatically with minimal required set of data and you will be able to start use of the program.

### Dependencies
ledger depends on:
* [Qt for Python (PySide2)](https://wiki.qt.io/Qt_for_Python) *>=5.15* - GUI library (versions below 5.15 may cause problems with `uic` at least)
* [pandas](https://pandas.pydata.org/) - different data operations
* [requests](https://requests.readthedocs.io/) - stock quotes update from the internet; electronic slip download
* [xlsxwriter](https://xlsxwriter.readthedocs.io/) - reports export into XLS format
* [ibflex](https://github.com/csingley/ibflex) *>=0.14* - Interactive Brokers flex-reports import 
* [pyzbar](https://github.com/NaturalHistoryMuseum/pyzbar/) <sup>*</sup> - electronic slip QR-code recognition
* [Pillow](https://pillow.readthedocs.io/en/stable/) <sup>*</sup> - work with images

<sup>*</sup> - optional dependencies (electronic slip import will be disabled)

### Screenshots
Qt have a better look on Linux out of the box. Here is main program window:  
![Main Window on Linux](https://github.com/titov-vv/ledger/blob/master/screenshots/main_linux.png?raw=true)

The same window on Windows - the same functions with a bit different look:  
![Main Window on Windows](https://github.com/titov-vv/ledger/blob/master/screenshots/main_windows.png?raw=true)

Accounts are be arranged in groups (Cash, Cards, Investments, etc), each account holds one currency.
Below is a view of main window where one account is chosen ('Mastercard') and account select/edit window is opened on top:  
![One Account](https://github.com/titov-vv/ledger/blob/master/screenshots/one_account_view.png?raw=true)

Example of investment account view with Buy, Sell and Dividend operations recorded (there is an asset select/edit window on top):  
![Investment Account](https://github.com/titov-vv/ledger/blob/master/screenshots/stocks_and_investment_account.png?raw=true)

'Holdings' tab contains portfolio overview (You display account and portfolio balances for any date).
Holdings are grouped by currencies and then by accounts.  
![Holdings](https://github.com/titov-vv/ledger/blob/master/screenshots/investment_portfolio_holdings.png?raw=true)

Examples of reports are below:
Monthly incomes/spendings *(categories hierarchy is supported with sub-totals calculation)*  
![Income/Spending report](https://github.com/titov-vv/ledger/blob/master/screenshots/report_income_spending.png?raw=true)
Profit/Loss for investment account *(Assets value to be fixed, Returns include dividends and other payments)*  
![Profit/Loss report](https://github.com/titov-vv/ledger/blob/master/screenshots/report_profit_loss.png?raw=true)
List of all closed deals for investment account  
![Deals report](https://github.com/titov-vv/ledger/blob/master/screenshots/report_deals.png?raw=true)

 ---

[![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Ftitov-vv.github.io%2Fledger%2F&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com)