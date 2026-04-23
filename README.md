# satisfactory-tools

Factory-planning tools for the game Satisfactory. Built on SQLite + SQLAlchemy +
Streamlit. Calculates production chains, tracks resource nodes and factories
across groups of bases, and shows real-time balance/power/building totals.

## Features

- **Recipe Browser** – filter 226 recipes by name or building.
- **Item Explorer** – filter 130 items by form, see what produces and consumes each.
- **Production Calculator** –
    - Forward: target item + rate → full chain, building summary, raw
      materials, power draw, Sankey diagram.
    - Reverse: plug in available inputs, get max output + leftovers.
    - Max Output: pick a group, pick an item, see the bottleneck material.
    - Alternate-recipe picker: override the default recipe choice per item.
- **Factory Dashboard** –
    - Global metrics: groups, lines, buildings, power, raw materials.
    - Sidebar group picker with search and import/export.
    - Per-group view: resource totals, overall balance, production lines with
      factory breakdown (recipe, building, count, clock %), raw-material
      balance with bottleneck labels.
    - Modal-based create/edit/delete for groups, production lines, and
      resource nodes.
    - Belt-tier warnings when a line's output exceeds what a belt can carry.
    - Extractor auto-fill: pick a miner tier + purity, rate is suggested
      from the in-game table.

## Setup

```bash
pip install -r requirements.txt

# One-time: populate satisfactory.db from data/Docs.json
DATABASE_URL=sqlite:///satisfactory.db python -m src.etl

# Launch
streamlit run streamlit_app.py
```

Configuration is read from `.env` (a `DATABASE_URL` entry is all that's needed).

## Tests

```bash
pytest
```

Full suite: 29 tests covering the calculator math (clock-speed rounding,
byproducts, alternate-recipe switching, subtree totals) and the production
CRUD layer (create/rename/delete, import-export round-trip, summary rollups).

## Project layout

```
streamlit_app.py           Entry-point dashboard
pages/                     Additional Streamlit pages (auto-discovered)
    1_Recipe_Browser.py
    2_Item_Explorer.py
    3_Production_Calculator.py
src/
    database.py            SQLAlchemy models + session helpers
    schemas.py             TypedDicts for calculator / query outputs
    queries.py             Read-only DB queries
    calculator.py          Pure-functional production-chain calculator
    production.py          CRUD + aggregation for groups/lines/nodes
    etl.py                 Loads Docs.json into SQLite
    cache.py               Streamlit-cached wrappers around read-only queries
    formatters.py          UI-side string formatting helpers
    game_constants.py      Miner/belt/purity game tables
tests/                     Pytest suite (in-memory SQLite, no ETL needed)
data/Docs.json             Game data extract (source of truth for ETL)
```

## Development notes

- **Model additions require a re-ETL.** The DB schema is generated from
  SQLAlchemy models on `create_tables`; the easiest way to pick up new columns
  is to rerun `python -m src.etl`, which drops and recreates the tables. For
  incremental SQLite migrations, use `ALTER TABLE` from sqlite CLI or a
  one-off Python script – see commit history around `Building.power_mw` for
  an example.
- **Calculator is pure-functional.** `calculate_chain` returns per-subtree
  totals; avoid reintroducing instance-state accumulators.
- **Recipe names aren't unique** – alternates share their display name. Always
  key by `recipe_id`.
- **Item forms are stored as the enum member `.name`** (string) in serialized
  outputs so Streamlit's Arrow-based dataframes don't choke on Python enums.
