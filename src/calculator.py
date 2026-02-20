from sqlalchemy.orm import Session

from .database import Recipe
from .queries import get_item, get_recipe, get_recipes_for_item

def calculate_recipe_requirements(
    session: Session, 
    recipe_id: int,
    item_id: int, 
    target_rate: float
) -> dict:
    
    output = { "item_id": item_id, "rate": target_rate }
    inputs = []
    byproducts = []
    num_buildings = 0

    recipe: Recipe = get_recipe(session, recipe_id)

    for ingredient in recipe.ingredients:
        if ingredient.is_output:
            if ingredient.item_id == item_id:
                output["item_name"] = ingredient.item.name
                num_buildings = target_rate / (
                    (60 / recipe.crafting_time) * ingredient.quantity
                )

    for ingredient in recipe.ingredients:
        current_entry = {
            "item_id": ingredient.item_id,
            "item_name": ingredient.item.name,
            "rate": ((60 / recipe.crafting_time) * ingredient.quantity) * num_buildings
        }

        if ingredient.is_output:
            if ingredient.item_id != item_id:
                byproducts.append(current_entry)
        else:
            inputs.append(current_entry)

    return {
        "recipe_name": recipe.name,
        "building_name": recipe.building.name,
        "num_buildings": num_buildings,
        "output": output,
        "inputs": inputs,
        "byproducts": byproducts
    }

def calc_rate(time: int, quantity: int, num_buildings: int) -> float: 
    return ((60 / time) * quantity) * num_buildings

def get_production_chain(session: Session, item_id: int, target_rate: float) -> dict:
    recipes: list[Recipe] = get_recipes_for_item(session, item_id)

    if not recipes:
        # raw material
        item = get_item(session, item_id)
        return {
            "item_id": item_id,
            "item_name": item.name,
            "required_rate": target_rate,
            "is_raw_material": True
        }
    
    recipe: Recipe = recipes[0]
    requirements = calculate_recipe_requirements(session, recipe.id, item_id, target_rate)
    dependencies = {}
    building_summary = {}
    raw_materials = {}

    for input in requirements['inputs']:
        dependencies[input['item_name']] = get_production_chain(session, 
                                                           input['item_id'], 
                                                           input['rate'])
        
        if 'building_summary' in dependencies[input['item_name']]:
            for building, count in dependencies[input['item_name']]['building_summary'].items():
                building_summary[building] = building_summary.get(building, 0) + count
        else: 
            for name, count in dependencies[input['item_name']]['raw_materials'].items():
                raw_materials[name] = raw_materials.get(name, 0) + count

    key = requirements['building_name']
    building_summary[key] = building_summary.get(key, 0) + requirements['num_buildings']

    return {
        "target": {
            "item": recipe.name,
            "rate": target_rate,
            "recipe": f"{recipe.name} ({recipe.building.name})"
        },
        "requirements": requirements,
        "dependencies": dependencies,
        "raw_materials": raw_materials,
        "building_summary": building_summary
    }