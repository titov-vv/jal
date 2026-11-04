[← Reports](10-reports.md) | [Contents](README.md) | [Next: Settings and maintenance →](12-settings-and-maintenance.md)

# 11. Tax reports

> **JAL is not a tax adviser and neither is this manual.** What follows describes the buttons and the
> files they produce. Whether the figures are the ones your tax office wants, and how they should be
> declared, is between you and the rules of your country — check the result before you file it.

JAL can prepare investment tax figures for **Portugal** and **Russia**, from the operations on one
investment account for one calendar year.

![The Tax menu](img/menu_tax.png)

## What it produces

**Tax → Investment tax report**:

![Preparing a tax report for Portugal](img/tax_forms_pt.png)

| Field | What to set |
|---|---|
| **Country** | Portugal or Russia |
| **Year** | The tax year. Defaults to last year, which is usually the one being declared. |
| **Account** | The investment account. Only investment accounts with something taxable in that year — a sale, a swap, an income, a fee — are offered. |
| **Excel file** | Where to write the detailed report. |

Press **Save Report** and JAL writes a spreadsheet with one sheet per kind of income — trades,
dividends, coupons, crypto, fees — each line showing the amounts in the account's currency,
the exchange rate used, and the amount in the tax currency. It is meant to be readable: an inspector
(or you, next year) can follow every figure back to the operation it came from. A sheet with
nothing on it is left out, and lines under a sheet's title state the rules it was built on: how
deals are matched, which rate is used, what counts as the cost.

### The sheets

| Portugal | Russia | What is on it |
|---|---|---|
| Summary | Сводка | The totals of the report, with links to the other sheets — see below. |
| Dividends | Дивиденды | Dividends and the tax withheld at source. The Russian sheet adds the tax still to pay, as a [base estimation](#base-estimation). |
| Shares | Акции | Sales of shares and funds. |
| — | Облигации | Bond sales, redemptions and coupons; the price is per bond, in the trade's currency. |
| — | ПФИ | Derivatives. |
| Crypto | Криптовалюты | Crypto deals. In Portugal only a sale for money; in Russia every exchange of one coin for another as well. |
| Crypto income | Криптодоход | Staking rewards, lending interest and other crypto received as income, valued on the day it arrived. Portugal lists it for information only: it opens a lot at zero cost and is taxed when sold. |
| Fees | Комиссии | Fees not linked to a deal — depositary (ADR) fees, position financing, other asset fees — grouped by kind. |
| Interest | Проценты | Interest the broker paid. The Russian sheet adds the tax on it, as a [base estimation](#base-estimation). |
| Not covered | Не отражено | Everything taxable that no other sheet shows — see below. |

**The cost of a deal is what was paid, in the currency it was paid in.** Moving shares or coins
between your own accounts in different currencies does not change it: a coin bought for roubles and
sold on a euro exchange costs, in the report, the roubles it was bought for, and the line says so.

### Summary and "Not covered"

The **Summary** sheet counts what the report contains and links to each sheet. Its last lines are
the ones to read before filing:

* **Skipped by the jurisdiction's rule** — operations a sheet leaves out on purpose, each with the
  reason: in Portugal a crypto-for-crypto exchange is not taxed until the coins are sold for money
  (CIRS art. 10.º, n.º 20); in both countries a returned token-account rent is a refund, not income.
* **Not included in any section** — taxable operations JAL has no sheet for yet, such as a spin-off
  or a deal in a fund. They are listed on **Not covered** so that nothing disappears silently;
  how to declare them is up to you.
* **Rows marked "pending replay"** — see below.

Below the counts come the [base estimations](#base-estimation) of tax, one line per sheet that has one,
then any warning — rates probably missing, [parameters](#tax-parameters) not reviewed for the year — and
last the list of [your decisions](#your-decisions-tax-treatment) the report applied.

### Pending replay

A crypto-for-crypto exchange or a wrapping that you recorded *without a result* moves the old coin's
cost onto the new one. Russian rules see every such exchange as a sale at market value, and JAL does
not yet recompute it that way. Lines that depend on such an exchange — the exchange itself, and later
sales of coins whose cost came through one — are marked **pending replay** (*ожидает пересчёта*):
their figures may still change when JAL learns to replay them. In Portugal the same mark flags a lot
whose cost or holding period passed through such an exchange.

### Currency rates

Each report converts with the official rates of one bank only, as the law requires: **Portugal**
uses the European Central Bank's (they equal the Bank of Portugal's), **Russia** the Central Bank of
Russia's. JAL never builds a rate from another bank's rates. Where a bank stopped publishing a
currency, its last rate stays the valid one — the ECB's rouble rate of 1 March 2022, for example.

* If a rate the report needs is not in the database at all, JAL stops and lists the missing rates
  and quotes; add them and save the report again.
* If the latest stored rate is more than two weeks older than an operation, and either that
  currency has a later rate (a hole in the series) or none of the bank's rates reach that day (they
  were not downloaded), the rate is probably missing. JAL still makes the report on the older rate,
  but warns of it in a message and on the Summary sheet; download the rates and save the report
  again. A currency the bank froze while still publishing the others is no warning.

### Tax parameters

What a report needs to know about the law of a year — which countries have a tax treaty with the
jurisdiction, the base tax rate of each kind of income — comes from a parameter file shipped with JAL,
one per country. Each value holds from the year it starts to apply until the year it changes, and the
file says up to which year it was last **reviewed** against the official sources.

* A report for a year **after** the review is still made, with the latest values known; a line on the
  Summary sheet and in the message after saving says so. The law may have changed since — check.
* A report for a year **before** the file begins assumes no treaty and computes no base estimation;
  the Summary sheet and the message say that too. The Russian file starts in 2020.

### Base estimation

Some figures are JAL's estimate rather than a fact from the broker: in the Russian report, the
dividend tax still to pay and the tax on interest; and the tax column of the
[tax estimate](06-investments.md#what-a-sale-would-cost-in-tax) window. Each of them is a **base
estimation**: the base rate of the year from the [parameters](#tax-parameters), applied to the income
and nothing more —

* no progressive bracket, no deduction, no netting with other sheets or other accounts;
* for a dividend, the tax withheld abroad is subtracted only where a tax treaty applies, and never
  below zero.

It is printed in italics on a pale amber background, the column header says *базовая оценка* /
*base estimation*, a line under the sheet's title states the rate, and the Summary sheet adds the
estimations up per sheet. It is a guide to the order of the amount, **not** the tax you owe: the
declaration computes that.

### Your decisions (tax treatment)

JAL's rules cannot know everything about an operation: a "dividend" that was really a return of
capital, a dividend on which the broker could not apply the treaty. Right-click the operation in the
operations list and choose **Tax treatment…**:

![The tax treatment dialog](img/dlg_tax_treatment.png)

There is one row per country. Choose a decision and write a note — the note is required, as it is
printed in the report next to the decision:

* **Not a tax event** — that country's report leaves the operation out of its sheet and its totals,
  and lists it last on **Not covered** with your note.
* **Tax treaty applies** / **No tax treaty** — offered for dividends only: that country's report
  takes your answer instead of its treaty list, for the treaty column and for the
  [base estimation](#base-estimation).
* **As the report decides** — removes the decision.

A decision belongs to one country: the other country's report does not see it. An operation that has
one shows the tax icon at the right end of its notes in the operations list, and the decisions in the
tooltip of its first three columns. Each report lists every decision it applied at the end of its
Summary sheet.

### The country options

**Portugal**

* **Convert at the rate of the disposal date only (CIRS art. 23)** — on by default: the cost, the
  proceeds and the expenses of a deal are all converted at the rate of the day it was sold, as
  article 23 of the CIRS describes. Unchecked, each leg is converted at the rate of its own trade
  date. A short sale is converted at the rate of the sale that opened it; that is JAL's reading,
  not a confirmed rule, and the line says so.
* **Create XML records to introduce in Modelo-3 form** — also write an XML file that can be loaded
  into the Modelo 3 declaration.

**Russia**

![Preparing a tax report for Russia](img/tax_forms_ru.png)

* **Do not use settlement date for currency rates** — take rates from the trade date instead of the
  settlement date.
* **Update only information about dividends** — fill in the dividend sections of the declaration only.
* **Use broker name as income source** — name the broker, rather than the issuer, as the source of
  income.
* **Create tax form in "Декларация 2.0" program format** — also write a declaration file for the
  official program (its extension carries the year: `.de5` for 2025, `.de6` for 2026).

## Money flow report *(Russia)*

**Tax → Foreign accounts flow report** produces the report on movements of money through a foreign
account that Russian residents must file:

![The money flow report](img/tax_money_flow.png)

Choose the year, choose where to save the spreadsheet, press **Save Report**.

## Merging declaration files

**Tax → Merge Russian tax files (\*.de5)** joins several `.de5` declaration files into one — for when
different sources of income were prepared separately and have to be filed together. Add the files
with **+**, name the output file, press OK.

## Before you file anything

* **Download prices and rates for the whole year first.** Every conversion uses a rate JAL has
  stored: a missing one stops the report, a probably missing one gives a warning (see
  [Currency rates](#currency-rates)). See [chapter 9](09-importing.md).
* **Read the Summary sheet**, and the **Not covered** one if it is there — including its warnings
  about [parameters](#tax-parameters) and the list of [your decisions](#your-decisions-tax-treatment).
* **Check that the account reconciles.** If JAL's closing balance matches your broker's, the
  underlying data is probably complete.
* **Check the corporate actions.** JAL refuses to build the ledger past a corporate action whose
  cost shares do not add up to 100 %, but it cannot tell whether shares that do are right: a wrong
  split of cost quietly produces a wrong profit, and can move it into another tax year. Compare each
  spin-off and merger with the figures the company published —
  see [chapter 6](06-investments.md#corporate-actions).
* **Read the log** after producing the report.

For Interactive Brokers there is a detailed, step-by-step example (in Russian) of preparing a Russian
declaration, in the project repository:
[docs/ru-tax-3ndfl/taxes.md](https://github.com/titov-vv/jal/blob/master/docs/ru-tax-3ndfl/taxes.md).

---

[← Reports](10-reports.md) | [Contents](README.md) | [Next: Settings and maintenance →](12-settings-and-maintenance.md)
