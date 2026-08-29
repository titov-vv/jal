[← When something looks wrong](13-troubleshooting.md) | [Contents](README.md)

# 14. Glossary

**Account** — a place your money or assets sit: a bank account, a card, cash, a brokerage account, a
crypto wallet, a term deposit. Each holds exactly one currency.

**Asset** — anything you can own a quantity of: a share, a fund, a bond, a coin. Currencies are
assets too.

**Base currency** — see *reporting currency*.

**Bridge** — an operation recording the same asset moving from one blockchain to another. No profit
arises; the cost carries across.

**Category** — the label that says *what money was for*. Categories form a tree, and the income and
spending reports total by them.

**Closed deal** — a purchase matched with a sale, and the profit that resulted. Listed in the *Deals
by account* report.

**Conversion** — an operation recording one asset becoming another **without** realising a profit:
wrapping a coin, depositing into a lending protocol. The cost basis carries across. Compare *swap*.

**Corporate action** — a company changing your holding without a trade: a split, a merger, a
spin-off, a symbol change, a delisting.

**Cost basis** — what you actually paid for what you hold, fees included. Profit is what you sell for
minus this.

**Dust** — a crumb of a coin, usually sent to your address unsolicited to get your attention. JAL
does not import arrivals below the dust threshold.

**FIFO** — *first in, first out*: when you sell, the oldest lots you hold are the ones sold. This is
how JAL computes the profit of a deal.

**Gas fee** — what a blockchain charges to process a transaction.

**Investing account** — an account marked as able to hold assets and not only money.

**JSF** — the internal format JAL converts every broker statement into before importing it. You never
see it unless an import fails and leaves a dump behind.

**Ledger** — the running totals JAL computes from your operations: balances, holdings, costs,
incomes. Never edited by hand; rebuilt whenever operations change.

**Listing** (called *symbol* in the interface) — one way an asset is traded: a ticker, in a currency,
on an exchange. One asset may have several.

**Lot** — one purchase of an asset, with its own date and its own cost, kept separately so that FIFO
can match sales against it.

**Operation** — one recorded event: a payment, a transfer, a trade, a dividend, a corporate action, a
conversion, a swap, a bridge.

**Peer** — the other party to an operation: a shop, an employer, a bank, a person.

**Pending / unsettled** — a movement that knows only one of its two ends. Listed in the *Unsettled
transfers* report until you say what the other end was.

**Precision** — how many decimal places an account counts in. Two for money, more for crypto.

**Quote** — a price of an asset in a currency on a date. Exchange rates are quotes too.

**Realised / unrealised** — profit is *realised* when the position is closed, and *unrealised* while
you still hold it and the price has merely moved.

**Reconciled** — you have compared an account with a statement up to a certain date and they agreed.
A reminder to yourself; JAL colours balances that have not been confirmed lately.

**Reporting currency** — the currency your totals are shown in. It comes from your *residence*.

**Residence** — where and when you live: the country, the reporting currency and the time zone, as a
timeline. Set in *Data → Residence*.

**Settlement date** — when a trade actually clears, usually a day or two after it was executed. Some
tax calculations use it rather than the trade date.

**Staked position** — coins that have left your wallet into staking but are still yours. Kept as an
account of its own; see the *Staked positions* report.

**Swap** — an operation exchanging one asset for another at a market rate, on one account. It
**realises** a profit or a loss. Compare *conversion*.

**Symbol** — see *listing*.

**Tag** — a free label that cuts across categories: `Holiday`, `Car`. Set per line of an operation,
and on assets.

**Term deposit** — money placed with a bank for a fixed period at a stated rate. JAL keeps each as an
account of its own.

**Ticker** — the short code an asset trades under: `ACME`, `BTC`.

**Transfer** — money or an asset moving between two of *your own* accounts. Never income and never
spending.

**Wallet** — an account that stands for one address on one blockchain.

---

[← When something looks wrong](13-troubleshooting.md) | [Contents](README.md)
