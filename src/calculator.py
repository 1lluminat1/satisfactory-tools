from sqlalchemy.orm import Session

from .types import InputItem, OutputItem, ProductionNode, RecipeRequirements
from .database import Recipe
from .queries import get_item, get_recipe, get_recipes_for_item


SECONDS_PER_MINUTE = 60


class ProductionCalculator:
    """
    Calculates the full production chain for a given item and target output rate.

    Recursively resolves dependencies, accumulating building counts and raw material
    requirements across the entire chain. Instantiate once per calculation to ensure
    building_summary and raw_materials are scoped to a single run.

    Attributes:
        session: Active SQLAlchemy database session.
        building_summary: Aggregated building counts across the entire production chain.
        raw_materials: Aggregated raw material rates across the entire production chain.
    """
    def __init__(self, session: Session):
        """
        Initializes the calculator with a database session and empty accumulators.

        Args:
            session: An active SQLAlchemy Session used for all database queries.
        """
        self.session = session
        self.building_summary: dict[str, float] = {}
        self.raw_materials: dict[str, float] = {}

    def _resolve_recipes(self, recipes: list[Recipe]) -> Recipe:
        """
        Selects a recipe from a list of candidates.

        Currently returns the first recipe. Intended as an extension point for
        alternate recipe selection logic in the future.

        Args:
            recipes: A non-empty list of Recipe candidates for an item.

        Returns:
            The selected Recipe to use for calculation.
        """
        return recipes[0]
    
    def _process_dependencies(self, inputs: list[InputItem]) -> dict[str, ProductionNode]:
        """
        Recursively calculates production chains for all input ingredients.

        For each input, calls calculate() and accumulates the results into
        self.building_summary and self.raw_materials.

        Args:
            inputs: List of input items required by a recipe, each with item_id and rate.

        Returns:
            A dictionary mapping item names to their resolved ProductionNode.
        """
        dependencies = {}
        for item in inputs:
            dep = self.calculate(item['item_id'], item['rate'])
            dependencies[item['item_name']] = dep

            if dep.get('is_raw_material'):
                self.raw_materials[dep['item_name']] = self.raw_materials.get(dep['item_name'], 0) + item['rate']
            else:
                for building, count in dep['building_summary'].items():
                    self.building_summary[building] = self.building_summary.get(building, 0) + count
                for name, count in dep['raw_materials'].items():
                    self.raw_materials[name] = self.raw_materials.get(name, 0) + count
        return dependencies

    def calculate(self, item_id: int, target_rate: float) -> ProductionNode:
        """
        Recursively calculates the production chain for an item at a target rate.

        If the item has no recipes in the database, it is treated as a raw material
        and returned as a terminal node. Otherwise, resolves the recipe, calculates
        requirements, and recurses into all input dependencies.

        Args:
            item_id: The database ID of the item to produce.
            target_rate: The desired output rate in items per minute.

        Returns:
            A ProductionNode representing the full production chain for this item.
        """
        recipes: list[Recipe] = get_recipes_for_item(self.session, item_id)

        if not recipes:
            item = get_item(self.session, item_id)
            return {
                "item_id": item_id,
                "item_name": item.name,
                "required_rate": target_rate,
                "is_raw_material": True
            }
        
        recipe: Recipe = self._resolve_recipes(recipes)
        requirements = calculate_recipe_requirements(self.session, recipe.id, item_id, target_rate)
        dependencies = self._process_dependencies(requirements['inputs'])

        key = requirements['building_name']
        self.building_summary[key] = self.building_summary.get(key, 0) + requirements['num_buildings']

        return {
            "target": {
                "item": recipe.name,
                "rate": target_rate,
                "recipe": f"{recipe.name} ({recipe.building.name})"
            },
            "requirements": requirements,
            "dependencies": dependencies,
            "raw_materials": self.raw_materials,
            "building_summary": self.building_summary
        }

def _find_output(recipe: Recipe, item_id: int, target_rate: float) -> tuple[OutputItem, float]:
    """
    Finds the matching output ingredient in a recipe and calculates the number of buildings needed.

    Args:
        recipe: The Recipe to search for the output ingredient.
        item_id: The item ID of the desired output.
        target_rate: The desired output rate in items per minute.

    Returns:
        A tuple of (OutputItem, num_buildings) where num_buildings is the number of
        buildings required to achieve the target rate.

    Raises:
        ValueError: If no output ingredient matching item_id is found in the recipe.
    """
    for ingredient in recipe.ingredients:
        if ingredient.is_output and ingredient.item_id == item_id:
            num_buildings = target_rate / (
                (SECONDS_PER_MINUTE / recipe.crafting_time) * ingredient.quantity
            )
            output: OutputItem = {
                "item_id": item_id,
                "item_name": ingredient.item.name,
                "rate": target_rate
            }
            return output, num_buildings
    raise ValueError(f"No output found for item {item_id} in recipe {recipe.id}")

def _collect_inputs_and_byproducts(recipe: Recipe, item_id: int, num_buildings: int) -> tuple[list[InputItem], list[InputItem]]:
    """
    Separates a recipe's ingredients into inputs and byproducts at the given building count.

    Args:
        recipe: The Recipe whose ingredients will be categorized.
        item_id: The primary output item ID, used to exclude it from byproducts.
        num_buildings: The number of buildings running, used to calculate actual rates.

    Returns:
        A tuple of (inputs, byproducts), each a list of InputItems with calculated rates.
    """
    inputs = []
    byproducts = []
    for ingredient in recipe.ingredients:
        entry: InputItem = {
            "item_id": ingredient.item_id,
            "item_name": ingredient.item.name,
            "rate": _calc_rate(recipe.crafting_time, ingredient.quantity, num_buildings)
        }
        if ingredient.is_output:
            if ingredient.item_id != item_id:
                byproducts.append(entry)
        else:
            inputs.append(entry)
    return inputs, byproducts

def _calc_rate(crafting_time: int, quantity: int, num_buildings: int) -> float:
    """
    Calculates the item rate per minute for a given crafting setup.

    Args:
        crafting_time: Time in seconds to complete one crafting cycle.
        quantity: Number of items produced or consumed per cycle.
        num_buildings: Number of buildings running in parallel.

    Returns:
        Items per minute produced or consumed across all buildings.
    """
    return ((SECONDS_PER_MINUTE / crafting_time) * quantity) * num_buildings

def calculate_recipe_requirements(session: Session, recipe_id: int, item_id: int, target_rate: float) -> RecipeRequirements:
    """
    Calculates the full input, output, and byproduct requirements for a recipe at a target rate.

    Args:
        session: An active SQLAlchemy Session used for database queries.
        recipe_id: The database ID of the recipe to evaluate.
        item_id: The database ID of the item being produced.
        target_rate: The desired output rate in items per minute.

    Returns:
        A RecipeRequirements dict containing the recipe name, building name, number of
        buildings, output item, list of inputs, and list of byproducts.

    Raises:
        ValueError: If no output matching item_id is found in the recipe.
    """
    recipe: Recipe = get_recipe(session, recipe_id)
    output, num_buildings = _find_output(recipe, item_id, target_rate)
    inputs, byproducts = _collect_inputs_and_byproducts(recipe, item_id, num_buildings)

    return {
        "recipe_name": recipe.name,
        "building_name": recipe.building.name,
        "num_buildings": num_buildings,
        "output": output,
        "inputs": inputs,
        "byproducts": byproducts
    }