# streamlit_item_explorer.py (or add to your existing streamlit_app.py as a new page)

import streamlit as st
import os
from dotenv import load_dotenv
from src.database import get_engine, get_session
from src.queries import get_all_items, get_item_recipe_usage

# Load environment and setup database
load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

try:
    # database queries
    all_items = get_all_items(session)

    # Page title
    st.title("Satisfactory Item Explorer")

    # Filters section
    st.header("Filters")
    search_query = st.text_input("Search items by name:").lower()
    
    # Get unique forms for filter
    unique_forms = list(set(item['form'] for item in all_items))
    form_filter = st.selectbox("Filter by form:", ["All"] + unique_forms)

    # Main table section
    st.header("Items")
    filtered_items = [
        item for item in all_items 
            if search_query in item['name'].lower() 
            and (form_filter == 'All' or str(form_filter) == str(item['form']))
    ]
    st.dataframe(filtered_items, use_container_width=True)

    # Item detail section
    st.header("Item Details")

    items_name_id = {
        item['name']: item['id'] for item in all_items
    }

    selected_item = st.selectbox("Select an item:", [
        item['name'] for item in all_items
    ])
    
    selected_item_id = items_name_id[selected_item]
    
    # Get selected item details
    selected_item_details = next(item for item in all_items if item['id'] == selected_item_id)
    
    # Display item info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Form", selected_item_details['form'].name)
    with col2:
        st.metric("Stack Size", selected_item_details['stack_size'])
    with col3:
        st.metric("Sink Points", selected_item_details['sink_points'] or "N/A")
    
    # Used In section
    st.subheader("Used In (Recipes that consume this item)")
    recipes_using = get_item_recipe_usage(session, selected_item_id, is_output=False)
    if recipes_using:
        st.dataframe(recipes_using, use_container_width=True)
    else:
        st.write("This item is not used as an input in any recipes.")
    
    # Produced By section
    st.subheader("Produced By (Recipes that produce this item)")
    recipes_producing = get_item_recipe_usage(session, selected_item_id, is_output=True)
    if recipes_producing:
        st.dataframe(recipes_producing, use_container_width=True)
    else:
        st.write("This item is not produced by any recipes.")

finally:
    session.close()