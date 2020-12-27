# JAL 
Just Another Ledger is a project for personal finance tracking.

[![image](http://img.shields.io/pypi/v/jal.svg)](https://pypi.python.org/pypi/jal/)

*[English](https://github.com/titov-vv/jal/blob/master/docs/README.md), [Русский](https://github.com/titov-vv/jal/blob/master/docs/README.ru.md)*

It was designed to keep records of personal incomes/spendings and investments with up-to-date information about account's balances and portfolio value.

### Main features
- multiple accounts with different currencies (base currency is russian rouble but might be changed in future versions)
- 5 types of transactions: 
    1. Generic income/spending operations that may be splitted into several categories
    2. Transfers of money between different accounts and currencies
    3. Buy/Sell operation for securities (future plan is to support merges and splits)
    4. Dividends for stocks (Bond coupons may be recorded the same way)
    5. Corporate actions for stocks (Split, Symbol change, Merger, Spin-Off, Stock dividend)
- basic reports:
    1. monthly incomes/spendings splitted by category
    2. profit/loss report for investments accounts
    3. closed deals report 
- stock quotes updates for US (Yahoo), EU (Euronext) and RU (MOEX) exchanges traded stocks
- securities transactions import from Quik HTML-reports for russian brokers (KIT-Finance, Uralsib Broker) and from Interactive Brokers flex-queries
- tax report preparation for foreign investments according to Russian Tax Law
- *experimental* download russian electronic slips from russian tax authority:
    1. QR code may be scanned from camera, clipboard image or image file on disk
    2. Authorization via login/password to FNS personal account or ESIA/Gosuslugi (no passwords are stored in the progam, only SessionId is stored - you may check in source code)

### Installation
*jal* was created to be portable and cross-platform. Thus you have several ways to install and run the program:
- You may get file archive from [the GitHub repository](https://github.com/titov-vv/jal), unpack it into suitable directory on your PC and use `run.py` to start application.
In order to succeed this way you need to have Python 3.8.1 and satisfy all dependencies listed below in *Dependencies* section.
- You may use installation package with `pip install jal` command. It will take care about dependencies automatically and will install `jal` entry point<sup>*</sup> to run the program.
Alternatively you may use `python -m jal.jal` if you can't run application with `jal` entry point.
- You may mix two methods together - download source files from github and then use `setup.py` for preferred way of installation.

Database will be initialized automatically with minimal required set of data and you will be able to start use the program.

<sup>*</sup> - entry point location is platform dependable. Eg. on Linux it might be in `~/.local/run`, on Windows - `Scripts` directory of your python installation.

### Update to newer version
You may get message _"Database schema version is outdated. Please execute update script."_ after upgrade to newer version.
In this case you need to use script `update_db_schema.py` from updates folder. Example of usage in Linux:

`./update_db_schema.py ../ledger.sqlite`

This will apply required changes to your database file (as usual it's a good idea to backup your `ledger.sqlite` before any activity)

### Dependencies
jal depends on:
* [Qt for Python (PySide2)](https://wiki.qt.io/Qt_for_Python) *>=5.15.2* - GUI library
* [pandas](https://pandas.pydata.org/) - different data operations
* [lxml](https://lxml.de/) - html/xml-files import
* [requests](https://requests.readthedocs.io/) - stock quotes update from the internet; electronic slip download
* [xlsxwriter](https://xlsxwriter.readthedocs.io/) - reports export into XLS format
* [pyzbar](https://github.com/NaturalHistoryMuseum/pyzbar/) <sup>1</sup> - electronic slip QR-code recognition
* [Pillow](https://pillow.readthedocs.io/en/stable/) <sup>1</sup> - work with images
* [tensorflow](https://www.tensorflow.org/) <sup>2</sup> - automatic category recognition 

<sup>1</sup> - optional dependencies (electronic slip import will be disabled)  
<sup>2</sup> - dependecy for experimental functionality (automatic category recognition will be disabled)

### Screenshots
Qt have a better look on Linux out of the box. Here is main program window:  
![Main Window on Linux](https://github.com/titov-vv/jal/blob/master/docs/img/main_linux.png?raw=true)

The same window on Windows - the same functions with a bit different look:  
![Main Window on Windows](https://github.com/titov-vv/jal/blob/master/docs/img/main_windows.png?raw=true)

Accounts are be arranged in groups (Cash, Cards, Investments, etc), each account holds one currency.
Below is a view of main window where one account is chosen ('Mastercard') and account select/edit window is opened on top:  
![One Account](https://github.com/titov-vv/jal/blob/master/docs/img/one_account_view.png?raw=true)

Example of investment account view with Buy, Sell and Dividend operations recorded (there is an asset select/edit window on top):  
![Investment Account](https://github.com/titov-vv/jal/blob/master/docs/img/stocks_and_investment_account.png?raw=true)

'Holdings' tab contains portfolio overview (You display account and portfolio balances for any date).
Holdings are grouped by currencies and then by accounts.  
![Holdings](https://github.com/titov-vv/jal/blob/master/docs/img/investment_portfolio_holdings.png?raw=true)

Examples of reports are below:
Monthly incomes/spendings *(categories hierarchy is supported with sub-totals calculation)*  
![Income/Spending report](https://github.com/titov-vv/jal/blob/master/docs/img/report_income_spending.png?raw=true)
Profit/Loss for investment account *(Assets value to be fixed, Returns include dividends and other payments)*  
![Profit/Loss report](https://github.com/titov-vv/jal/blob/master/docs/img/report_profit_loss.png?raw=true)
List of all closed deals for investment account  
![Deals report](https://github.com/titov-vv/jal/blob/master/docs/img/report_deals.png?raw=true)

 ---

[![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Ftitov-vv.github.io%2Fledger%2F&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com)
