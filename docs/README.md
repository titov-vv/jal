# JAL (Just Another Ledger)
**Track and manage your personal finances seamlessly.**

[![image](http://img.shields.io/pypi/v/jal.svg)](https://pypi.python.org/pypi/jal/)

*[English](https://github.com/titov-vv/jal/blob/master/docs/README.md), [Русский](https://github.com/titov-vv/jal/blob/master/docs/README.ru.md)*

## 📌 Overview
JAL is tailored for those who want a clear insight into their personal incomes, expenditures, investments, and up-to-date information on account balances and portfolio values.

## ⭐️ Features
### Multiple Accounts Management
- Support for various currencies with user-selected base currency totals.
### Transaction Types
- Generic income/spending with multi-category split.
- Asset and money transfers, including currency conversion.
- Trading operations: Buy/Sell securities (stocks, ETFs, options, and more).
- Dividends for stocks and bond interest payments.
- Corporate actions for stocks.
### Reports
- Portfolio asset allocation for a given date.
- Monthly income/expenditure by category.
- Investment profit/loss.
- Closed deals summary.
### Price Updates
- Stock/ETF prices updated for major global exchanges.
- Currency exchange rates from European and Russian central banks.
### Broker Statement Imports
- Supports various Russian and international brokers.
### Tax Reports
- Assistance for tax declaration in Russia and Portugal.
- Tax burden estimation for a given asset in the portfolio.
### Experimental Features
- Electronic slips download for russian and some european shops. 
- Category recognition for goods in electronic slips using TensorFlow.

## 📥 Installation
JAL offers cross-platform compatibility and portability. Here's how to get started:
1. **From GitHub Repository**:
   - Clone repository locally with `git https://github.com/titov-vv/jal.git`
   - Ensure you have Python 3.8.1 or later and meet all dependencies in `requirements.txt`.
   - Tips Windows users: Ensure Python installation from ![the official site](https://www.python.org/) and turn on options `pip installation` and `add Python to environment variables` during the installation. Reboot to apply changes.
   - Use `run.py` to launch the application.
2. **Using pip**:
   - Install using `pip install jal`.
   - Launch with the `jal` command or alternatively `python -m jal.jal`.
3. **Hybrid Installation**:
   - Download source files and use `setup.py` for tailored installation.
  

Database will be initialized automatically with minimal required set of data, and you will be able to start use the program.

You may choose program language in menu *Languages*.

## ❗️ Upgrades
If you installed *jal* via *pip* then you may upgrade it to newer version with help of command `pip install jal -U`

## 📈 Tax report for investment account
Tax report can be prepared based on data from any broker if operations are present in JAL. Tax reports are supported for Russia and Portugal.    
You can import operations from broker statement with help of menu *Import->Statement*.  
Step-by-step example (in russian language) of Russian tax report preparation for Interactive Brokers can be found on [this page](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/taxes.md). 
Use contacts from beginning of this page if you need support regarding statements or reports.

## Screenshots
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

## 📞 Support, Feedback
If you want to ask a question, report a bug, provide help or support an author - you may use email [jal@gmx.ru](mailto:jal@gmx.ru?subject=%5BJAL%5D%20Help) or [Telegram](https://t.me/jal_support) ([Issues](https://github.com/titov-vv/jal/issues) on GitHub are always welcome also).

## ❤️ Acknowledgements
I would like to a mention people who helped me in 2022 and 2023 as I got more donations, help and feedback from users this year. 
And while I can't name every one of them I would like to confirm my appreciation for this help. They did the project better!

## [FAQ](https://github.com/titov-vv/jal/blob/master/docs/FAQ.md)

## [Description of error messages](https://github.com/titov-vv/jal/blob/master/docs/error_description.md)


 ---

[![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Ftitov-vv.github.io%2Fledger%2F&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com)
