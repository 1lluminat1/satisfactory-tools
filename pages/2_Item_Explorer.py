import os

import streamlit as st
from dotenv import load_dotenv

from src.cache import cached_all_items
from src.database import get_engine, get_session
from src.queries import get_item_recipe_usage


load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

try:
    all_items = cached_all_items(session)

    st.title("Satisfactory Item Explorer")

    st.header("Filters")
    search_query = st.text_input("Search items by name:").lower()

    unique_forms = sorted({item['form'] for item in all_items if item['form']})
    form_filter = st.selectbox("Filter by form:", ["All"] + unique_forms)

    st.header("Items")
    filtered_items = [
        item for item in all_items
        if search_query in item['name'].lower()
        and (form_filter == 'All' or form_filter == item['form'])
    ]
    st.dataframe(filtered_items, use_container_width=True)

    st.header("Item Details")
    item_labels = {f"{i['name']} [id={i['id']}]": i['id'] for i in all_items}
    selected_label = st.selectbox("Select an item:", list(item_labels.keys()))
    if selected_label:
        selected_item_id = item_labels[selected_label]
        selected = next(item for item in all_items if item['id'] == selected_item_id)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Form", selected['form'] or "N/A")
        with col2:
            st.metric("Stack Size", selected['stack_size'] or "N/A")
        with col3:
            st.metric("Sink Points", selected['sink_points'] or "N/A")

        st.subheader("Used In (Recipes that consume this item)")
        recipes_using = get_item_recipe_usage(session, selected_item_id, is_output=False)
        if recipes_using:
            st.dataframe(recipes_using, use_container_width=True)
        else:
            st.write("This item is not used as an input in any recipes.")

        st.subheader("Produced By (Recipes that produce this item)")
        recipes_producing = get_item_recipe_usage(session, selected_item_id, is_output=True)
        if recipes_producing:
            st.dataframe(recipes_producing, use_container_width=True)
        else:
            st.write("This item is not produced by any recipes.")

finally:
    session.close()
