[← Contents](README.md) | [Next: Installing and starting JAL →](02-install.md)

# 1. What JAL is, and how it thinks

## What it does

JAL keeps a complete history of your money: every payment you make, every salary that arrives, every
transfer between your own accounts, and — if you invest — every share you buy, every dividend you
receive and every price those shares have had.

From that history it can tell you, for any day you care to name:

* how much money you have, in every account, and what that adds up to in one currency;
* what you spent, on what, and on whom;
* what your investments are worth and how much of that is profit;
* what a tax authority in Portugal or Russia would want to know about your investment account.

## What it does not do

* **It does not connect to your bank.** JAL never asks for your online-banking password and cannot
  log in anywhere on your behalf. You type your everyday spending in yourself, or import a file that
  your bank or broker gives you.
* **It does not send your data anywhere.** Everything lives in one file on your computer. The only
  time JAL goes online is when you ask it to download share prices, exchange rates, or the contents
  of a blockchain wallet — and even then it sends no personal information.
* **It is not a budgeting app.** JAL records what happened; it does not set spending limits or nag you.

## The five ideas you need

Nearly everything in JAL is built from five things. It is worth two minutes to learn them, because
the rest of the program then explains itself.

### 1. Accounts

An **account** is any place your money sits: a bank account, a wallet in your pocket, a credit card, a
brokerage account, a savings deposit, a crypto wallet. Each account holds **exactly one currency**.
If you have a bank account in euros and another in dollars, that is two accounts in JAL — even if
your bank shows them on one page.

Accounts have a type (*Cash*, *Bank account*, *Card*, *Broker account*, *Wallet*, *Crypto exchange*),
which is used to group them on screen and to decide what JAL offers you to do with them.

### 2. Operations

An **operation** is one thing that happened. JAL has eight kinds:

| Operation | What it records |
|---|---|
| **Income / Spending** | Money arriving from, or going to, the outside world |
| **Transfer** | Money moving between two of *your own* accounts |
| **Buy / Sell** | A trade: money turns into an asset, or an asset back into money |
| **Asset Payment** | A dividend, a bond coupon, a staking reward — an asset paying you |
| **Corporate Action** | A company changing your shares: a split, a merger, a spin-off |
| **Conversion** | One asset becoming another with the price you paid carried across |
| **Swap** | One asset exchanged for another, on one account, at a market price |
| **Bridge** | The same asset moving from one blockchain to another |

The last three matter almost only to crypto users; see [chapter 8](08-crypto.md). Most people
use the first four and nothing else.

### 3. The ledger

You enter operations; JAL keeps a **ledger** behind the scenes. The ledger is the running total of
everything: how much is in each account on each day, how many shares you hold, what each of them cost
you, what you have earned and what you have spent.

You never edit the ledger. It is recalculated whenever you add, change or delete an operation, and it
is what every balance and every report is read from. If it ever looks wrong, you can have JAL build it
again from scratch — see [chapter 12](12-settings-and-maintenance.md).

### 4. The reporting currency

Your accounts may hold euros, dollars and bitcoin, but a question like *"how much do I have?"* needs
one answer in one currency. That currency is your **reporting currency**, and JAL takes it from where
and when you live — see *Residence* in [chapter 3](03-first-steps.md).

To convert one currency into another, JAL needs exchange rates, and to value shares it needs prices.
Both are downloaded on request; see [chapter 9](09-importing.md).

### 5. Labels: categories, peers and tags

Three separate labels can be attached to what you record, and they answer three different questions:

* **Category** — *what was the money for?* (Groceries, Rent, Salary…). Categories form a tree, so
  `Spending → Groceries` adds up into `Spending`.
* **Peer** — *who was on the other side?* (a shop, an employer, a landlord).
* **Tag** — *what does this belong to?* — a free label that cuts across categories, such as
  `Holiday` or `Car`. One holiday can contain a flight (Transport), a hotel (Leisure) and a dinner
  (Eating out); the tag brings the three back together.

## Where everything is kept

A single file called `jal.sqlite`. Your accounts, your operations, your settings, the prices JAL has
downloaded — all of it. Copy that one file and you have copied your entire ledger; that is all a
backup is. [Chapter 2](02-install.md) says where the file lives, and
[chapter 12](12-settings-and-maintenance.md) explains backups.

---

[← Contents](README.md) | [Next: Installing and starting JAL →](02-install.md)
