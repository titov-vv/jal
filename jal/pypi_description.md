# JAL 
Just Another Ledger is a project for personal finance tracking.

It was designed to keep records of personal incomes/spendings and investments with up-to-date information about account's balances and portfolio value.

### Main features
- multiple accounts with different currencies (base currency is russian rouble but might be changed in future versions)
- 5 types of transactions: 
    1. Generic income/spending operations that may be split into several categories
    2. Asset and money transfers between accounts (with currency conversion if required)
    3. Buy/Sell operation for securities (jal supports stocks, ETFs, options, partial support of bonds and futures)
    4. Dividend for stocks and Interest payments for bonds
    5. Corporate actions for stocks (Split, Symbol change, Merger, Spin-Off, Stock dividend)
- basic reports:
    1. monthly incomes/spendings split by category
    2. profit/loss report for investments accounts
    3. closed deals report 
- stock/ETF quotes updates for US (Yahoo), EU (Euronext), CA (TSX) and RU (MOEX) exchanges traded stocks
- Broker statement import:
    1. Russian: Uralsib broker (zipped xls), KIT Finance (xlsx), PSB broker (xls), Open broker (xml).
    2. International: Interactive Brokers Flex statement (xml), Just2Trade (xls).
- Investments report for tax declaration preparation for Russia and Portugal.  
Russian tax estimation for open positions.
- *experimental* Download russian electronic slips from russian tax authority (FNS). This function requires authorization and `pyzbar` package installation for QR recognition.  
You may authorize via SMS, FNS personal account or ESIA/Gosuslugi. QR code may be scanned from camera, clipboard image or image file on disk.

Full description is available at Github - *[English](https://github.com/titov-vv/jal/blob/master/docs/README.md), [Русский](https://github.com/titov-vv/jal/blob/master/docs/README.ru.md)*

Support: [jal@gmx.ru](mailto:jal@gmx.ru?subject=%5BJAL%5D%20Help) or [Telegram](https://t.me/jal_support)