# Wallet flow graph

Draws every recorded movement of value between the crypto accounts of a JAL database as a
node-link diagram: accounts are nodes grouped by blockchain, and each line is one direction
of flow. An analysis tool, not part of the application — nothing here is imported by `jal/`
and nothing here is packaged by `setup.py`.

```bash
python3 extract_graph.py                             # → wallet_graph.html beside the script
python3 extract_graph.py /tmp/flows.html             # explicit output path
JAL_DB=~/other.sqlite python3 extract_graph.py       # another database
```

Standard library only, no dependencies. The database is opened read-only. The result is a
single self-contained HTML file — open it in any browser, no server needed.

## What it reads

One directed flow per (source account, target account, kind), aggregated from four sources:

| Kind | Source | Meaning |
|---|---|---|
| Transfer | `transfers` | a plain move of one asset between two accounts |
| Bridge | `bridges` | the same value carried across chains |
| Swap | `swaps` | one asset traded for another that lands in a *different* account |
| Custody | `transfers` whose note starts with `[custody]` | an asset handed to a staking box and back |

A flow is kept when either end is an account of type Wallet, CEX or Staking
(`PredefinedAccountType`), so the fiat legs that fund an exchange are included but
bank-to-bank traffic is not. Swaps that stay inside one account are trades, not movements
between wallets, and are left out.

Amounts shown are **gross per asset, not netted and not converted to a base currency** — a
bridge or swap leg is counted once, on the asset that left. Nothing in the page is a
valuation; use the reports for that.

Two grouping rules are worth knowing, because both are inferences rather than stored facts:

- accounts with no `Chain` attribute are grouped by what they are (exchange, or bank/broker);
- a staking box has no chain of its own, so it adopts the chain of its counterparties when
  they all agree on one, and the inspector marks that as inferred.

## Files

- `extract_graph.py` — the queries, the aggregation, and the build (injects the graph into
  the template at the `/*__GRAPH__*/null` placeholder).
- `wallet_graph_template.html` — the page: styling, force layout, canvas rendering,
  inspector rail and ledger table. Contains no data.

## Privacy

Both source files are data-free and safe to commit. **The generated `wallet_graph.html` is
not** — it embeds account names, on-chain addresses and extended public keys, and amounts.
It is covered by `.gitignore` here; keep it that way, and redact before sharing the page.

## Maintenance

The script reads `transfers`, `bridges`, `swaps`, `accounts` and `account_data` directly
rather than going through the ORM, so a schema migration that touches those tables — or new
values in `PredefinedAccountType`, `AccountData` or `AssetLocation.BLOCKCHAINS` — needs the
constants at the top of `extract_graph.py` updated to match.
