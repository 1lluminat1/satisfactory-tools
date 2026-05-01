# satisfactory-tools

[![CI](https://github.com/1lluminat1/satisfactory-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/1lluminat1/satisfactory-tools/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Factory-planning tools for the game **Satisfactory**. A Streamlit app over a SQLite/SQLAlchemy
database that calculates production chains, tracks resource nodes and factories across groups
of bases, and shows real-time balance / power / building totals.

> _Screenshot placeholder — capture the dashboard with at least one group + production line
> seeded (the **Load demo data** button on first run gives you a clean shot)._
>
> ![Dashboard](docs/screenshots/dashboard.png)

> _Screenshot placeholder — Forward Calculator showing the Sankey diagram for an interesting
> chain (Reinforced Iron Plate or Modular Frame works well)._
>
> ![Production Calculator](docs/screenshots/calculator.png)

## What this demonstrates

- **Recursive pure-functional algorithms.** `calculate_chain` walks the recipe graph,
  aggregating per-subtree totals (raw materials, byproducts, building counts, power)
  with a visited-set to guard cycles. Switchable alternate recipes via
  `preferred_recipes={item_id: recipe_id}`.
- **SQLAlchemy 2.x ORM** with relationships, cascades, and an ETL pipeline that
  parses Satisfactory's `Docs.json` into a normalized schema.
- **Streamlit multipage app** with `st.dialog` modals for create/edit/delete,
  `st.session_state` for persistent UI state, `@st.cache_data` for read-only queries,
  and a Plotly Sankey for chain visualization.
- **Pytest** with in-memory SQLite fixtures: 29 tests cover calculator math
  (clock-speed rounding, byproducts, alt-recipe switching, subtree totals) and the
  full CRUD layer (create / rename / delete cascades, import-export round-trip,
  summary rollups).
- **Production-quality polish.** Ruff-clean codebase, typed with `TypedDict`,
  GitHub Actions CI, MIT licensed.

## Features

**Recipe Browser** — filter 226 recipes by name or building, drill into details.

**Item Explorer** — filter 130 items by form, see what produces and consumes each.

**Production Calculator**

- _Forward_: pick an item + rate → full recipe chain, building summary,
  raw materials, power draw, and a Sankey flow diagram.
- _Reverse_: enter available inputs, get max output + leftovers + suggestions
  for what to increase.
- _Max Output_: pick a group, pick an item, see the bottleneck material.
- _Alternate-recipe picker_: per-item override of the default recipe.

**Factory Dashboard**

- Global metrics: groups, lines, buildings, power, raw materials.
- Sidebar group picker with search, "+ New Group" modal, JSON import/export,
  "Load demo data" for first-run.
- Per-group view: resource totals, overall balance, production lines with
  factory breakdown (recipe, building, count, clock %), per-line raw-material
  balance with bottleneck labels.
- Modal-based create / edit / delete for groups, production lines, and
  resource nodes (with confirm gates on destructive ops).
- Belt-tier warnings when a line's output exceeds what a belt can carry.
- Extractor auto-fill: pick a miner tier + purity, rate is suggested from
  the in-game extraction table.

## Quickstart

```bash
git clone https://github.com/1lluminat1/satisfactory-tools.git
cd satisfactory-tools
pip install -r requirements.txt

# One-time: populate satisfactory.db from data/Docs.json
DATABASE_URL=sqlite:///satisfactory.db python -m src.etl

# Launch
streamlit run streamlit_app.py
```

Configuration is read from `.env` (a `DATABASE_URL` entry is all that's needed).
A pre-built `satisfactory.db` is committed for convenience, so you can skip the ETL
step on first run.

## Tests

```bash
pytest          # full suite, ~0.5s, no DB or Docs.json required
ruff check src tests
```

CI runs both on every push and PR (see `.github/workflows/ci.yml`).

## Project layout

```
streamlit_app.py           Entry-point dashboard
pages/                     Streamlit auto-discovers these
    1_Recipe_Browser.py
    2_Item_Explorer.py
    3_Production_Calculator.py
src/
    database.py            SQLAlchemy models + session helpers
    schemas.py             TypedDicts for calculator / query outputs
    queries.py             Read-only DB queries
    calculator.py          Pure-functional production-chain calculator
    production.py          CRUD + aggregation for groups / lines / nodes
    etl.py                 Loads Docs.json into SQLite
    cache.py               Streamlit-cached query wrappers + DB-ready guard
    formatters.py          UI-side string formatting helpers
    game_constants.py      Miner / belt / purity game tables
tests/                     Pytest suite (in-memory SQLite, no ETL needed)
data/Docs.json             Game-data extract (source of truth for ETL)
```

## Development notes

- **Schema additions require a re-ETL.** The DB is generated from SQLAlchemy
  models on `create_tables`; rerun `python -m src.etl` to pick up new columns.
  For incremental SQLite migrations, `ALTER TABLE` is fine — see commit history
  around `Building.power_mw` for an example.
- **Calculator is pure-functional.** `calculate_chain` returns per-subtree totals;
  avoid reintroducing instance-state accumulators.
- **Recipe display names aren't unique** — alternates share their name. Always
  key by `recipe_id`.
- **Item forms are stored as `.name`** (string) in serialized outputs so
  Streamlit's Arrow-based dataframes don't choke on Python enums.

## License

[MIT](LICENSE)
