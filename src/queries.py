from sqlalchemy import select

from src.database import Recipe


def get_recipe_details(session, recipe_id):
    """
    {
        "recipe_name": "Iron Plate",   <- Recipe
        "crafting_time": 6.0,          <- Recipe
        "building": "Constructor",     <- Building
        "inputs": [("Iron Ingot", 3)], <- RecipeIngredient <- Item
        "outputs": [("Iron Plate", 2)] <- RecipeIngredient <- Item
    }
    """
    recipe = session.execute(select(Recipe).where(Recipe.id == recipe_id))
    