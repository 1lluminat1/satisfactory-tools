import streamlit as st

from src.queries import get_all_groups


# Top third — global stats
st.header("Global Overview")
# total resource nodes, total production lines, global building summary, etc.

# Bottom two thirds — group viewer
st.header("Groups")
groups = get_all_groups(session)
tabs = st.tabs([g.name for g in groups])

for tab, group in zip(tabs, groups):
    with tab:
        # resource nodes in this group
        # production lines in this group, each expandable
        # surplus/deficit analysis