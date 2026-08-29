# How the manual's pictures are made

Every screenshot in the manual is generated, not taken by hand, so the whole set can be refreshed
after a change to the interface and stays consistent with itself.

```bash
python tools/manual/make_demo_db.py       # builds the demo ledger  -> tools/manual/demo/jal.sqlite
python tools/manual/capture.py            # ~54 screenshots         -> docs/manual/img/*.png
                                          #  + 2 for the README     -> docs/img/*.png
python tools/manual/capture_first_run.py  # the empty-database ones -> docs/manual/img/first_run_*.png
```

Run them from the repository root, with the project's own environment (`.venv/bin/python` if you use
one). They need no desktop session: Qt runs on the `offscreen` platform.

## The three scripts

| File | What it does |
|---|---|
| `demo_env.py` | Points the process at `tools/manual/demo/` instead of the real ledger, and refuses to go on if the path does not resolve there. |
| `make_demo_db.py` | Builds the demo database from nothing: residence, peers, categories, tags, accounts, assets, quotes, twenty months of household operations, a trading account, a crypto wallet and a term deposit. |
| `capture.py` | Opens the real main window against that database and saves each picture the manual uses, then `capture_readme()` adds the two the project README needs on top of them. `capture_first_run.py` does the same against an empty database. |

`docs/manual/img/jal_logo.png` is the only picture that is not generated - it is a copy of
`docs/img/jal_logo.png` and has to be copied again if the images folder is ever emptied.

`docs/README.md` shows six pictures, and only two of them (`one_account_view`, `stocks_and_investment_account`)
live in `docs/img/` - a dialog composed over the window behind it, which the manual has no use for. The other
four are the manual's own and are referenced where they already are, so that no picture exists twice.

That leaves `docs/img/` holding exactly those two screenshots and four things that are not screenshots at
all: the logo, two favicons and the social preview card. Every one of them is referenced by a document, and
it is worth keeping it that way - an unreferenced picture there is one nobody will think to regenerate.

## Safety

The demo database is redirected through a private `XDG_CONFIG_HOME` holding a `jal.ini` that names
`tools/manual/demo/` as the database folder - the same mechanism a user has for moving their ledger.
`assert_demo_database()` compares the path the application actually resolved against the one the
script asked for, and raises before anything is written or deleted. **Every script that removes or
overwrites a database file must call it first**: a stale `jal.ini` would otherwise point somewhere
else, and the real ledger is one of the places it could point.

`prepare_environment()` is therefore called inside `main()` and never at import time, so that
importing `capture.py` (which `capture_first_run.py` does) cannot silently re-point the
configuration.

## The data in the pictures

All invented. The person, the bank, the shops, the employer, the brokers, the tickers, the prices,
the account numbers and the wallet address exist nowhere. Nothing is derived from a real ledger, so
no screenshot needs anonymising before it is published.

The demo folder itself (`tools/manual/demo/`) is working data, untracked by git - it can be deleted at
any time and rebuilt by re-running the first script.
