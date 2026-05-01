"""
Streamlit-cached wrappers around read-only queries.

ETL-loaded data (items, recipes, buildings) doesn't change within a user session,
so caching these saves noticeable work on every page rerun. The session argument
is prefixed with `_` so Streamlit skips hashing it (SQLAlchemy sessions aren't
hashable).
"""

import streamlit as st

from .queries import (
    get_all_buildings as _get_all_buildings,
)
from .queries import (
    get_all_items as _get_all_items,
)
from .queries import (
    get_all_recipes as _get_all_recipes,
)
from .schemas import ItemDetails, RecipeDetails


def ensure_db_ready(engine) -> None:
    """
    Show a helpful error and halt the page if the ETL hasn't run.

    Call once at the top of each Streamlit page, right after creating the engine.
    """
    from .database import is_etl_complete

    if not is_etl_complete(engine):
        st.error("Database is not initialized.")
        st.markdown(
            "Run the ETL once to populate the database from `data/Docs.json`:"
        )
        st.code("DATABASE_URL=sqlite:///satisfactory.db python -m src.etl", language="bash")
        st.info("Then refresh this page.")
        st.stop()


@st.cache_data(ttl=3600)
def cached_all_items(_session) -> list[ItemDetails]:
    return _get_all_items(_session)


@st.cache_data(ttl=3600)
def cached_all_recipes(_session) -> list[RecipeDetails]:
    return _get_all_recipes(_session)


@st.cache_data(ttl=3600)
def cached_all_buildings(_session) -> list[str]:
    return _get_all_buildings(_session)
