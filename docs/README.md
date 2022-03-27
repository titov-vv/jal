# JAL 
Just Another Ledger is a project for personal finance tracking.

[![image](http://img.shields.io/pypi/v/jal.svg)](https://pypi.python.org/pypi/jal/)

*[English](https://github.com/titov-vv/jal/blob/master/docs/README.md), [Русский](https://github.com/titov-vv/jal/blob/master/docs/README.ru.md)*

It was designed to keep records of personal incomes/spendings and investments with up-to-date information about account's balances and portfolio value.

### Support, Feedback
If you want to ask a question, report a bug, provide help or support an author - you may use email [jal@gmx.ru](mailto:jal@gmx.ru?subject=%5BJAL%5D%20Help) or [Telegram](https://t.me/jal_support) ([Issues](https://github.com/titov-vv/jal/issues) on GitHub are always welcome also).

### [FAQ](https://github.com/titov-vv/jal/blob/master/docs/FAQ.md)

### Main features
- Multiple accounts with different currencies (base currency is russian rouble but might be changed in future versions)
- 5 types of transactions: 
    1. Generic income/spending operations that may be splitted into several categories
    2. Transfers of money between different accounts and currencies
    3. Buy/Sell operation for securities (jal supports stocks, ETFs, options, partial support of bonds and futures)
    4. Dividend for stocks and Interest payments for bonds
    5. Corporate actions for stocks (Split, Symbol change, Merger, Spin-Off, Stock dividend)
- Basic reports:
    1. monthly incomes/spendings splitted by category
    2. profit/loss report for investments accounts
    3. closed deals report 
- Stock/ETF prices are updated for NYSE, Nasdaq, LSE, Frankfurt (Yahoo), Euronext, TSX and MOEX exchanges traded stocks
- Broker statement import:
    1. Russian brokers: Uralsib broker (zipped xls), KIT Finance (xlsx), PSB broker (xls), Open broker (xml).
    2. US brokers: Interactive Brokers Flex statement (xml).
- Tax report preparation for foreign investments according to Russian Tax Code (![manual](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/taxes.md)).  
Russian tax estimation for open positions.
- *experimental* Download russian electronic slips from russian tax authority (FNS). This function requires authorization and additional dependencies to use these function - packages `pyzbar` and `Pillow`.  
You may authorize via SMS, FNS personal account or ESIA/Gosuslugi. QR code may be scanned from camera, clipboard image or image file on disk.
- *experimental* Category recognition for goods in electronic slip with help of `tensorflow`

### Installation
*jal* was created to be portable and cross-platform. Thus you have several ways to install and run the program:
- You may get file archive from [the GitHub repository](https://github.com/titov-vv/jal), unpack it into suitable directory on your PC and use `run.py` to start application.
In order to succeed this way you need to have at least Python 3.8.1 and satisfy all dependencies listed in `requirements.txt`. Let's say some words about installing python on windows-based computers, as this application becomes poplular for non-programming people. The best place to download python distro is official site, sure. Important, in installer dialogues to check boxes for installing `pip` and `Add python to environment variables`. Don't forget to reboot windows to be sure, that changes applies correctly.

- You may use installation package with `pip install jal` command. It will take care about dependencies automatically and will install `jal` entry point<sup>*</sup> to run the program. For windows-users the best and easiest way is to start windows command prompt (cmd) and run command mentioned above in it. If python set up correctly and installation succeeded you may just type `jal` to run application.
Alternatively you may use `python -m jal.jal` if you can't run application with `jal` entry point.
- You may mix two methods together - download source files from github and then use `setup.py` for preferred way of installation.

Database will be initialized automatically with minimal required set of data and you will be able to start use the program.

<sup>*</sup> - entry point location is platform dependable. Eg. on Linux it might be in `~/.local/run`, on Windows - `Scripts` directory of your python installation or `Appdata/Roaming/Python/.../Scripts/` in user profile path.

### Upgrades
If you installed *jal* via *pip* then you may upgrade it to newer version with help of command `pip install jal -U`


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
