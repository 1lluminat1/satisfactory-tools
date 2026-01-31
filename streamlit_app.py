import streamlit as st
import os
from dotenv import load_dotenv
from src.database import get_engine, get_session
from src.queries import get_all_recipes, get_all_buildings, get_recipe_details, get_recipe

# Load environment and setup database
load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

# Page title
st.title("Satisfactory Recipe Browser")

# Filters section
st.header("Filters")
search_query = st.text_input("Search recipes by name:")
building_filter = st.selectbox("Filter by building:", ["All"] + [
    building for building in get_all_buildings(session)])

# Main table section
st.header("Recipes")
filtered_recipes = [recipe for recipe in get_all_recipes(session) if search_query in recipe['name']]
st.dataframe(filtered_recipes, use_container_width=True)

# Recipe detail section
st.header("Recipe Details")
selected_recipe_id = st.selectbox("Select a recipe:", [
    recipe['name'] for recipe in get_all_recipes(session)
])  # TODO: Add recipe options here
recipe_details = get_recipe_details(get_recipe(session, selected_recipe_id))
# TODO: Display recipe details

session.close()