<img src="https://raw.githubusercontent.com/titov-vv/jal/master/docs/img/jal_logo.png" alt="JAL" width="88">

# JAL 
Just Another Ledger is a project for personal finance tracking.

It was designed to keep records of personal incomes/spendings and investments with up-to-date information about account's balances and portfolio value.

### Main features
- multiple accounts in any number of currencies; the reporting currency (everything is converted into) is the one you set for your country of residence
- the operations it records:
    1. Generic income/spending operations that may be split into several categories
    2. Asset and money transfers between accounts (with currency conversion if required)
    3. Buy/Sell operation for securities (jal supports stocks, ETFs, options, partial support of bonds and futures)
    4. Asset payments: dividends for stocks, interest and amortization for bonds, staking and lending rewards for crypto
    5. Corporate actions for stocks (Split, Symbol change, Merger, Spin-Off, Stock dividend)
    6. Term deposits
    7. Crypto lending deposits/withdrawals and staking
    8. Swaps and cross-chain bridge transfers
- crypto wallets on Ethereum, Arbitrum, Avalanche, Bitcoin, Solana, Tron and Hyperliquid: operations are fetched from
the chain, staked positions are tracked separately and rewards that are earned but not paid out yet are reported
- reports:
    1. Daily history of account balance.
    2. Portfolio asset allocation for a given date.
    3. Monthly income/expenditure by category, peer or tag.
    4. Investment profit/loss and history of payments for an assets.
    5. Closed deals summary.
    6. Term deposits and staked positions.
- quotes updates: stocks and ETFs from Yahoo (US, LSE, Frankfurt, Warsaw, Helsinki), Euronext, TMX TSX and MOEX;
crypto from DeFiLlama; currency rates from the European and the Russian central banks
- Broker, bank and crypto exchange statement import:
    1. International: Interactive Brokers Flex statement (xml), Freedom Finance (xml), Just2Trade (xlsx), Trading 212 (csv), Revolut (csv).
    2. Russian: KIT Finance (xlsx), PSB broker (xlsx/xls), VTB Investments (xlsx), Tvoy Broker (zip).
    3. Crypto exchanges: KuCoin (zip), Bitget (zip).
- Investments report for tax declaration preparation for Russia and Portugal.  
Russian tax estimation for open positions.
- *experimental* Download russian electronic slips from russian tax authority (FNS). This function requires authorization and `pyzbar` package installation for QR recognition.  
You may authorize via SMS, FNS personal account or ESIA/Gosuslugi. QR code may be scanned from camera, clipboard image or image file on disk.

[**User manual**](https://titov-vv.github.io/jal/manual/) - the whole program explained from the first start onwards.

Full description is available at Github - *[English](https://github.com/titov-vv/jal/blob/master/docs/README.md), [Русский](https://github.com/titov-vv/jal/blob/master/docs/README.ru.md)*

Support: [jal@gmx.ru](mailto:jal@gmx.ru?subject=%5BJAL%5D%20Help) or [Telegram](https://t.me/jal_support)
