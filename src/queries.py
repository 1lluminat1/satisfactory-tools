from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Building, Item, Recipe, RecipeIngredient


def get_recipe(session: Session, recipe_id: int) -> Optional[Recipe]:
    return session.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar()

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

def get_all_buildings(session: Session) -> list[str]:
    return list(session.execute(select(Building.name)).scalars().all())
 
def get_all_recipes(session: Session) -> list[dict]:
    return [
        get_recipe_details(recipe) for recipe in 
            session.execute(select(Recipe)).scalars().all()
    ]

def get_all_items(session: Session) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "name": item.name,
            "form": item.form,
            "stack_size": item.stack_size,
            "sink_points": item.sink_points
        } for item in session.execute(select(Item)).scalars().all()
    ]

def get_item(session: Session, item_id: int):
    return session.query(Item).filter_by(id=item_id).first()

def get_item_recipe_usage(
    session: Session,
    item_id: int,
    *,
    is_output: bool = False,
) -> list[dict[str, Any]]:
    return [
        {
            "recipe_name": recipe.name,
            "building": building.name,
            "quantity": ingredient.quantity,
        } for ingredient, recipe, building in 
            session.execute(
            select(RecipeIngredient, Recipe, Building)
            .join(RecipeIngredient.recipe)
            .join(Recipe.building)
            .where(
                RecipeIngredient.item_id == item_id,
                RecipeIngredient.is_output.is_(is_output),
            )
        ).all()
    ]

def get_recipes_for_item(session: Session, item_id: int) -> list[Recipe]:
    return session.execute(select(Recipe)
                           .join(Recipe.ingredients)
                           .where(
                               RecipeIngredient.item_id == item_id,
                               RecipeIngredient.is_output.is_(True)
                           )).scalars().all()

