<img src="img/jal_logo.png" alt="JAL" width="88">

# JAL (Just Another Ledger)
**Track and manage your personal finances seamlessly.**

[![image](http://img.shields.io/pypi/v/jal.svg)](https://pypi.python.org/pypi/jal/)

*[English](https://github.com/titov-vv/jal/blob/master/docs/README.md), [Русский](https://github.com/titov-vv/jal/blob/master/docs/README.ru.md)*

## 📌 Overview
JAL is tailored for those who want a clear insight into their personal incomes, expenditures, investments, and up-to-date information on account balances and portfolio values.

## ⭐️ Features
### Multiple Accounts Management
- Accounting with various currencies for different accounts.
- User-selected base currency totals.
- Account balance indication with or without credit limit.
### Transaction Types
- Generic income/spending with multi-category split.
- Asset and money transfers, including currency conversion.
- Trading operations: Buy/Sell securities (stocks, ETFs, options, and more).
- Dividends for stocks and bond interest payments (including bond amortization).
- Corporate actions for stocks.
- Basis-preserving asset conversions (crypto wrapping, lending deposits/withdrawals, liquid staking).
### Reports
- Term deposits: what is open, what each of them earned, and the actions that manage them.
- Daily history of account balance.
- Portfolio asset allocation for a given date.
- Monthly income/expenditure by category.
- Investment profit/loss and history of payments for an assets.
- Closed deals summary.
### Price Updates
- Stock/ETF/Crypto prices updated for major global exchanges.
- Currency exchange rates from European and Russian central banks.
### Broker Statement Imports
- Supports various Russian and international brokers.
- Supports centralized crypto exchange statements (KuCoin, Bitget).
- Supports bank and card statements (Revolut), where card purchases are reviewed against what is already recorded before anything is imported.
### Tax Reports
- Assistance for tax declaration in Russia and Portugal.
- Tax burden estimation for a given asset in the portfolio.
### Experimental Features
- Electronic slips download for russian and some european shops. 
- Category recognition for goods in electronic slips using TensorFlow.

## 📖 User manual
The [**User manual**](https://titov-vv.github.io/jal/manual/) explains the whole program from the first start onwards - accounts and operations, investments, crypto, statement imports, every report, taxes, backups and troubleshooting. It is also reachable from menu *Help->User manual*.

## 📥 Installation
JAL runs on Windows, macOS and Linux and needs **Python 3.9 or newer**. In a terminal:
```
pip install jal
```
Then start it with `jal`, or with `python -m jal.jal` if that command is not found. To upgrade later, use `pip install jal -U`.

To run from the sources instead: clone the repository, install the dependencies from `requirements.txt` and launch `run.py`.

The database is initialized automatically on the first start, so you can begin at once, and you may choose the program language in menu *Settings->Language*.

See [Installing and starting JAL](https://titov-vv.github.io/jal/manual/02-install) in the manual for the step-by-step version, including where the `jal.sqlite` file is kept, how to move it elsewhere with `jal.ini`, and how to back it up.

## 📈 Tax report for investment account
Tax report can be prepared based on data from any broker if operations are present in JAL. Tax reports are supported for Russia and Portugal.    
You can import operations from broker statement with help of menu *Import->Statement*.  
Step-by-step example (in russian language) of Russian tax report preparation for Interactive Brokers can be found on [this page](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/taxes.md). 
Use contacts from beginning of this page if you need support regarding statements or reports.

## Screenshots
All pictures below show an invented demo ledger, not real data. Here is the main program window:  
![Main Window](https://github.com/titov-vv/jal/blob/master/docs/manual/img/main_window.png?raw=true)

Accounts are arranged in groups (Cash, Card, Bank, Broker, Wallet, etc), each account holds one currency.
Below is a view of main window where one account is chosen ('Everyday Card') and account select/edit window is opened on top:  
![One Account](https://github.com/titov-vv/jal/blob/master/docs/img/one_account_view.png?raw=true)

Example of investment account view with Buy, Sell and Dividend operations recorded (there is an asset select/edit window on top):  
![Investment Account](https://github.com/titov-vv/jal/blob/master/docs/img/stocks_and_investment_account.png?raw=true)

The *Portfolio* report gives an overview of everything held on a given date, grouped by currency and then by account.  
![Portfolio](https://github.com/titov-vv/jal/blob/master/docs/manual/img/report_portfolio.png?raw=true)

Examples of reports are below:
Monthly incomes/spendings *(categories hierarchy is supported with sub-totals calculation)*  
![Income/Spending report](https://github.com/titov-vv/jal/blob/master/docs/manual/img/report_income_spending.png?raw=true)
Profit/Loss for investment account *(Assets value to be fixed, Returns include dividends and other payments)*  
![Profit/Loss report](https://github.com/titov-vv/jal/blob/master/docs/manual/img/report_profit_loss.png?raw=true)
List of all closed deals for investment account  
![Deals report](https://github.com/titov-vv/jal/blob/master/docs/manual/img/report_deals.png?raw=true)

## 📞 Support, Feedback
If you want to ask a question, report a bug, provide help or support an author - you may use email [jal@gmx.ru](mailto:jal@gmx.ru?subject=%5BJAL%5D%20Help) or [Telegram](https://t.me/jal_support) ([Issues](https://github.com/titov-vv/jal/issues) on GitHub are always welcome also).

## ❤️ Acknowledgements
I would like to a mention people who helped me in 2022 and 2023 as I got more donations, help and feedback from users this year. 
And while I can't name every one of them I would like to confirm my appreciation for this help. They did the project better!

## [Frequently asked questions](https://titov-vv.github.io/jal/manual/13-troubleshooting#frequently-asked-questions)

## [Description of error messages](https://github.com/titov-vv/jal/blob/master/docs/error_description.md)


 ---

<img src="https://jal.goatcounter.com/count?p=/github-readme" alt="" width="1" height="1">

