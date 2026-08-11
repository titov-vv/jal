#!/usr/bin/env python3
"""Render a wallet-to-wallet transaction graph from jal.sqlite.

Reads the database read-only, aggregates every move of value between crypto accounts
into one directed flow per (source, target, kind), and injects the result into
wallet_graph_template.html to produce a self-contained page.

    python3 extract_graph.py [output.html]

Set JAL_DB to point at another database.
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

# The application database, two levels up from tools/wallet_graph/. Override with JAL_DB.
DB = os.environ.get("JAL_DB", str(Path(__file__).resolve().parents[2] / "jal" / "jal.sqlite"))
TEMPLATE = "wallet_graph_template.html"
PLACEHOLDER = "/*__GRAPH__*/null"

CHAINS = {301: "Ethereum", 302: "Arbitrum", 303: "Bitcoin", 304: "Solana",
          305: "Tron", 306: "Hyperliquid", 307: "Avalanche"}
TYPES = {2: "cash", 3: "bank", 4: "card", 5: "broker", 6: "wallet", 7: "deposit",
         8: "cex", 9: "staking"}
CRYPTO = (6, 8, 9)

db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
db.row_factory = sqlite3.Row

accounts = {}
for r in db.execute("""
        SELECT a.id, a.name, a.account_type,
               MAX(CASE WHEN d.datatype=6  THEN d.value END) AS chain,
               MAX(CASE WHEN d.datatype=5  THEN d.value END) AS address,
               MAX(CASE WHEN d.datatype=11 THEN d.value END) AS protocol
        FROM accounts a LEFT JOIN account_data d ON d.account_id=a.id
        GROUP BY a.id"""):
    accounts[r["id"]] = {
        "id": r["id"], "name": r["name"], "kind": TYPES.get(r["account_type"], "other"),
        "chain": CHAINS.get(int(r["chain"]), None) if r["chain"] else None,
        "address": r["address"], "protocol": r["protocol"],
        "crypto": r["account_type"] in CRYPTO}

EXTERNAL = -1
accounts[EXTERNAL] = {"id": EXTERNAL, "name": "Outside JAL", "kind": "external",
                      "chain": None, "address": None, "protocol": None, "crypto": False}

edges = defaultdict(lambda: {"count": 0, "assets": defaultdict(Decimal),
                             "first": None, "last": None, "samples": []})


def add(src, dst, kind, ts, symbol, qty, note):
    if src is None:
        src = EXTERNAL
    if dst is None:
        dst = EXTERNAL
    if not (accounts[src]["crypto"] or accounts[dst]["crypto"]):
        return
    e = edges[(src, dst, kind)]
    e["count"] += 1
    if symbol and qty:
        try:
            e["assets"][symbol] += Decimal(qty)
        except Exception:
            pass
    e["first"] = ts if e["first"] is None else min(e["first"], ts)
    e["last"] = ts if e["last"] is None else max(e["last"], ts)
    e["samples"].append({"ts": ts, "symbol": symbol, "qty": qty, "note": note})


# ---- transfers: a move of one asset between two accounts (same chain, or fiat leg)
for r in db.execute("""
        SELECT t.withdrawal_account src, t.deposit_account dst, t.withdrawal_timestamp ts,
               t.withdrawal, t.deposit, s.symbol,
               (SELECT symbol FROM asset_symbol WHERE asset_id=wa.currency_id LIMIT 1) currency,
               t.note
        FROM transfers t
        LEFT JOIN asset_symbol s ON s.id=t.symbol_id
        LEFT JOIN accounts wa ON wa.id=t.withdrawal_account"""):
    symbol = r["symbol"] or r["currency"]
    qty = r["withdrawal"] if r["withdrawal"] and r["withdrawal"] != "0" else r["deposit"]
    kind = "custody" if (r["note"] or "").startswith("[custody]") else "transfer"
    add(r["src"], r["dst"], kind, r["ts"], symbol, qty, r["note"])

# ---- bridges: the same value moved across chains
for r in db.execute("""
        SELECT b.out_account_id src, b.in_account_id dst, b.out_timestamp ts,
               so.symbol out_sym, b.out_qty, si.symbol in_sym, b.in_qty, b.note
        FROM bridges b
        LEFT JOIN asset_symbol so ON so.id=b.out_symbol_id
        LEFT JOIN asset_symbol si ON si.id=b.in_symbol_id"""):
    note = f"{r['out_qty']} {r['out_sym']} → {r['in_qty']} {r['in_sym'] or '?'}"
    add(r["src"], r["dst"], "bridge", r["ts"], r["out_sym"], r["out_qty"], note)

# ---- swaps: one asset traded for another; only those that land in a different account
for r in db.execute("""
        SELECT s.account_id src, s.in_account_id dst, s.timestamp ts,
               so.symbol out_sym, s.out_qty, si.symbol in_sym, s.in_qty, s.note
        FROM swaps s
        LEFT JOIN asset_symbol so ON so.id=s.out_symbol_id
        LEFT JOIN asset_symbol si ON si.id=s.in_symbol_id
        WHERE s.in_account_id IS NOT NULL AND s.in_account_id <> s.account_id"""):
    note = f"{r['out_qty']} {r['out_sym']} → {r['in_qty']} {r['in_sym']}"
    add(r["src"], r["dst"], "swap", r["ts"], r["in_sym"], r["in_qty"], note)


def fmt(d: Decimal) -> str:
    d = d.normalize()
    q = abs(d)
    places = 2 if q >= 100 else (4 if q >= 1 else 8)
    s = f"{d:,.{places}f}".rstrip("0").rstrip(".")
    return s or "0"


out_edges = []
for (src, dst, kind), e in edges.items():
    out_edges.append({
        "source": src, "target": dst, "kind": kind, "count": e["count"],
        "first": e["first"], "last": e["last"],
        "assets": [{"symbol": s, "total": fmt(v)}
                   for s, v in sorted(e["assets"].items(), key=lambda kv: -abs(kv[1]))],
        "samples": sorted(e["samples"], key=lambda s: s["ts"], reverse=True)[:6]})

used = {i for e in out_edges for i in (e["source"], e["target"])}
out_nodes = [a for i, a in accounts.items() if i in used or a["crypto"]]

graph = {"nodes": out_nodes, "edges": sorted(out_edges, key=lambda e: -e["count"])}
data = json.dumps(graph, separators=(",", ":"), ensure_ascii=False)

template = Path(__file__).with_name(TEMPLATE).read_text(encoding="utf-8")
if PLACEHOLDER not in template:
    raise SystemExit(f"{TEMPLATE} has no {PLACEHOLDER} placeholder to inject into")
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("wallet_graph.html")
out.write_text(template.replace(PLACEHOLDER, data), encoding="utf-8")
print(f"{out} — {len(out_nodes)} accounts, {len(out_edges)} flows, "
      f"{sum(e['count'] for e in out_edges)} transactions")
