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


@st.cache_data(ttl=3600)
def cached_all_items(_session) -> list[dict]:
    return _get_all_items(_session)


@st.cache_data(ttl=3600)
def cached_all_recipes(_session) -> list[dict]:
    return _get_all_recipes(_session)


@st.cache_data(ttl=3600)
def cached_all_buildings(_session) -> list[str]:
    return _get_all_buildings(_session)
