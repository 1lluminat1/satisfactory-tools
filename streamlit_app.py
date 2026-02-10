import streamlit as st
import os
from dotenv import load_dotenv
from src.database import get_engine, get_session
from src.formatters import format_recipe_for_table
from src.queries import get_all_recipes, get_all_buildings, get_recipe_details, get_recipe

# Load environment and setup database
load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

try:
    # database queries
    all_recipes = get_all_recipes(session)
    all_buildings = get_all_buildings(session)

    # Page title
    st.title("Satisfactory Recipe Browser")

    # Filters section
    st.header("Filters")
    search_query = st.text_input("Search recipes by name:").lower()
    building_filter = st.selectbox("Filter by building:", ["All"] + all_buildings)

    # Main table section
    st.header("Recipes")
    filtered_recipes = [
        recipe for recipe in all_recipes 
            if search_query in recipe['name'].lower() 
            and (building_filter == 'All'
            or building_filter == recipe['building'])
    ]
    formatted_recipes = [format_recipe_for_table(recipe) for recipe in filtered_recipes]
    st.dataframe(filtered_recipes, use_container_width=True)

    # Recipe detail section
    st.header("Recipe Details")

    recipes_name_id = {
        item['name']: item['id'] for item in all_recipes
    }

    selected_recipe = st.selectbox("Select a recipe:", [
        recipe['name'] for recipe in all_recipes
    ])
    recipe_details = get_recipe_details(get_recipe(session, recipes_name_id[selected_recipe]))
    st.write(recipe_details)

finally:
    session.close()