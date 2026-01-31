from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import Building, Recipe


"""
"""
def get_recipe(session: Session, recipe_id: int) -> Optional[Recipe]:
    return session.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar()

"""
"""
def get_recipe_details(recipe: Recipe) -> dict[str, Any]:
    inputs = []
    outputs = []

    for ingredient in recipe.ingredients:
        entry = {"name": ingredient.item.name, "quantity": ingredient.quantity}
        if ingredient.is_output:
            outputs.append(entry)
        else:
            inputs.append(entry)

    return {
        "id": recipe.id,
        "name": recipe.name,
        "building": recipe.building.name,
        "crafting_time": recipe.crafting_time,
        "inputs": inputs,
        "outputs": outputs
    }

"""
"""
def get_all_buildings(session: Session) -> list[str]:
    return list(session.execute(select(Building.name)).scalars().all())

"""
"""    
def get_all_recipes(session: Session) -> list[dict]:
    recipes = session.execute(select(Recipe)).scalars().all()
    return [get_recipe_details(recipe) for recipe in recipes]