import os

import streamlit as st
from dotenv import load_dotenv

from src.cache import cached_all_buildings, cached_all_recipes
from src.database import get_engine, get_session
from src.formatters import format_recipe_for_table
from src.queries import get_recipe, get_recipe_details


load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

try:
    all_recipes = cached_all_recipes(session)
    all_buildings = cached_all_buildings(session)

    st.title("Satisfactory Recipe Browser")

    st.header("Filters")
    search_query = st.text_input("Search recipes by name:").lower()
    building_filter = st.selectbox("Filter by building:", ["All"] + all_buildings)

    st.header("Recipes")
    filtered_recipes = [
        recipe for recipe in all_recipes
        if search_query in recipe['name'].lower()
        and (building_filter == 'All' or building_filter == recipe['building'])
    ]
    formatted_recipes = [format_recipe_for_table(r) for r in filtered_recipes]
    st.dataframe(formatted_recipes, use_container_width=True)

    st.header("Recipe Details")
    # Recipe names are not unique (alternates). Disambiguate by appending building.
    recipe_labels = {
        f"{r['name']} ({r['building']}) [id={r['id']}]": r['id']
        for r in all_recipes
    }
    selected_label = st.selectbox("Select a recipe:", list(recipe_labels.keys()))
    if selected_label:
        recipe_details = get_recipe_details(get_recipe(session, recipe_labels[selected_label]))
        st.write(recipe_details)

finally:
    session.close()
