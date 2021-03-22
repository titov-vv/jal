# JAL 
Just Another Ledger is a project for personal finance tracking.

It was designed to keep records of personal incomes/spendings and investments with up-to-date information about account's balances and portfolio value.

### Main features
- multiple accounts with different currencies (base currency is russian rouble but might be changed in future versions)
- 5 types of transactions: 
    1. Generic income/spending operations that may be splitted into several categories
    2. Transfers of money between different accounts and currencies
    3. Buy/Sell operation for securities (jal supports stocks, ETFs, options, partial support of bonds and futures)
    4. Dividend for stocks and Interest payments for bonds
    5. Corporate actions for stocks (Split, Symbol change, Merger, Spin-Off, Stock dividend)
- basic reports:
    1. monthly incomes/spendings splitted by category
    2. profit/loss report for investments accounts
    3. closed deals report 
- stock/ETF quotes updates for US (Yahoo), EU (Euronext) and RU (MOEX) exchanges traded stocks
- broker statement import:
    1. Quik HTML-report (only trades, fee might be incomplete)
    2. Interactive Brokers Flex-query report
    3. Uralsib Broker zipped XLS reports (trades, cash transactions)
    4. KIT Finance XLSX-report (trades)
- tax report preparation for foreign investments according to Russian Tax Law
- *experimental* download russian electronic slips from russian tax authority:
    1. QR code may be scanned from camera, clipboard image or image file on disk
    2. Authorization via login/password to FNS personal account or ESIA/Gosuslugi (no passwords are stored in the progam, only SessionId is stored - you may check in source code)

Full description is available at Github - *[English](https://github.com/titov-vv/jal/blob/master/docs/README.md), [Русский](https://github.com/titov-vv/jal/blob/master/docs/README.ru.md)*