# ledger
ledger is a project for personal finance tracking.

It was designed to keep records of personal incomes/spendings and investments with up-to-date information about multi-currency account balances and portfolio value.

### Main features
- multiple accounts with different currencies (basic currency is Russian Rouble but might be changed in future versions)
- 4 types of transactions: 
    1. Generic income/spending operations that may be splitted into several categories
    2. Transfers of money between different accounts and currencies
    3. Buy/Sell operation for securities (future plan is to support merges and splits)
    4. Dividends for stocks (Bond coupons may be recorded the same way)
- basic reports:
    1. monthly incomes/spendings splitted by category
    2. profit/loss report for investments accounts
    3. closed deals report 
- stock quotes updates for US (Yahoo), EU (Euronext) and RU (MOEX) stocks
- securities transactions import from Quik HTML-reports for russian brokers and from Interactive Brokers flex-queries
- tax report preparation for foreign investments according to Russian Tax Law

### Dependencies
ledger depends on:
* [Qt for Python (PySide2)](https://wiki.qt.io/Qt_for_Python) - GUI library
* [pandas](https://pandas.pydata.org/) - different data operations
* [requests](https://requests.readthedocs.io/) - stock quotes update from the internet
* [xlsxwriter](https://xlsxwriter.readthedocs.io/) - reports export into XLS format
* [ibflex](https://github.com/csingley/ibflex) - Interactive Brokers flex-reports import

### Screenshots
Qt have a better look on Linux out of the box. Here is main program window:
![Main Window on Linux](https://github.com/titov-vv/ledger/blob/master/screenshots/main_linux.png?raw=true)

The same window on Windows - the same functions with a bit different look:
![Main Window on Windows](https://github.com/titov-vv/ledger/blob/master/screenshots/main_windows.png?raw=true)

Accounts are be arranged in groups (Cash, Cards, Investments, etc), each account holds one currency.
Below is a view of main window where one account is chosen ('Mastercard') and account select/edit window is opened on top:
![One Account](https://github.com/titov-vv/ledger/blob/master/screenshots/one_account_view.png?raw=true)

Example of investment account view with Buy, Sell and Dividend operations recorded (there is an asset select/edit window on top):
![One Account](https://github.com/titov-vv/ledger/blob/master/screenshots/stocks_and_investment_account.png?raw=true) 