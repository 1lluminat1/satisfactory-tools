import math
from typing import Optional

from sqlalchemy.orm import Session

from .database import Recipe
from .queries import get_item, get_recipe, get_recipes_for_item
from .schemas import ProductionNode, RecipeRequirements, ResolvedItem


SECONDS_PER_MINUTE = 60
# In-game power scaling factor for clock-speed adjustments (Satisfactory wiki).
CLOCK_POWER_EXPONENT = 1.321


def _rate_per_minute(crafting_time: float, quantity: int) -> float:
    """Items per minute produced by one building at 100% clock for this recipe."""
    return (SECONDS_PER_MINUTE / crafting_time) * quantity


def _power_for(building_power: float, num_buildings: int, clock_speed: float) -> float:
    """Total MW draw for N buildings running at clock_speed (%) using the in-game formula."""
    return building_power * num_buildings * (clock_speed / 100.0) ** CLOCK_POWER_EXPONENT


def _compute_requirements(recipe: Recipe, item_id: int, target_rate: float) -> RecipeRequirements:
    """
    Builds a RecipeRequirements for `recipe` producing `item_id` at `target_rate`/min.

    Rounds up to whole buildings and computes the clock speed needed so that the
    rounded building count hits the target rate exactly.
    """
    output_ingredient = next(
        (i for i in recipe.ingredients if i.is_output and i.item_id == item_id),
        None,
    )
    if output_ingredient is None:
        raise ValueError(f"Recipe {recipe.id} does not output item {item_id}")

    per_building_rate = _rate_per_minute(recipe.crafting_time, output_ingredient.quantity)
    num_ideal = target_rate / per_building_rate
    num_rounded = max(1, math.ceil(num_ideal))
    clock_speed = 100.0 * num_ideal / num_rounded

    building_power = recipe.building.power_mw or 0.0
    total_power = _power_for(building_power, num_rounded, clock_speed)

    inputs: list[ResolvedItem] = []
    byproducts: list[ResolvedItem] = []
    for ing in recipe.ingredients:
        # rate scales with ideal buildings (not rounded) because we clock-adjust
        rate = _rate_per_minute(recipe.crafting_time, ing.quantity) * num_ideal
        entry: ResolvedItem = {
            "item_id": ing.item_id,
            "item_name": ing.item.name,
            "rate": rate,
        }
        if ing.is_output:
            if ing.item_id != item_id:
                byproducts.append(entry)
        else:
            inputs.append(entry)

    output: ResolvedItem = {
        "item_id": item_id,
        "item_name": output_ingredient.item.name,
        "rate": target_rate,
    }

    return {
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "building_id": recipe.building.id,
        "building_name": recipe.building.name,
        "num_buildings_ideal": num_ideal,
        "num_buildings_rounded": num_rounded,
        "clock_speed": clock_speed,
        "power_mw_per_building": building_power,
        "total_power_mw": total_power,
        "output": output,
        "inputs": inputs,
        "byproducts": byproducts,
    }


def _merge_sum(dst: dict[str, float], src: dict[str, float]) -> None:
    for k, v in src.items():
        dst[k] = dst.get(k, 0.0) + v


def _raw_node(item_id: int, item_name: str, target_rate: float) -> ProductionNode:
    """Terminal node for a raw material: contributes to raw_materials, no buildings/power."""
    return {
        "item_id": item_id,
        "item_name": item_name,
        "required_rate": target_rate,
        "is_raw_material": True,
        "raw_materials": {item_name: target_rate},
        "byproducts_totals": {},
        "building_summary": {},
        "power_mw_total": 0.0,
    }


def calculate_chain(
    session: Session,
    item_id: int,
    target_rate: float,
    *,
    preferred_recipes: Optional[dict[int, int]] = None,
    _visited: Optional[frozenset[int]] = None,
) -> ProductionNode:
    """
    Pure-functional production chain calculator.

    Returns a ProductionNode whose raw_materials/byproducts_totals/building_summary/
    power_mw_total fields are the sums for that node's subtree only. Intermediate
    nodes therefore carry correct per-subtree totals, not a shared accumulator.

    Args:
        session: Active SQLAlchemy Session.
        item_id: Item to produce.
        target_rate: Desired output rate in items/min.
        preferred_recipes: Optional map of {item_id: recipe_id} to force a specific
            recipe when multiple produce the same item.
        _visited: Internal cycle-detection set. Do not pass explicitly.

    Returns:
        A ProductionNode for the requested item.
    """
    visited: frozenset[int] = _visited if _visited is not None else frozenset()

    if item_id in visited:
        # Cycle - terminate as raw to prevent infinite recursion.
        fallback = get_item(session, item_id)
        return _raw_node(item_id, fallback.name if fallback else f"item_{item_id}", target_rate)

    recipes = get_recipes_for_item(session, item_id)
    if not recipes:
        item = get_item(session, item_id)
        return _raw_node(item_id, item.name, target_rate)

    chosen_id = (preferred_recipes or {}).get(item_id)
    recipe = next((r for r in recipes if r.id == chosen_id), recipes[0])

    requirements = _compute_requirements(recipe, item_id, target_rate)

    dependencies: dict[str, ProductionNode] = {}
    raw_materials: dict[str, float] = {}
    byproducts_totals: dict[str, float] = {
        bp["item_name"]: bp["rate"] for bp in requirements["byproducts"]
    }
    building_summary: dict[str, float] = {
        requirements["building_name"]: requirements["num_buildings_ideal"]
    }
    power_total: float = requirements["total_power_mw"]

    next_visited = visited | {item_id}
    for inp in requirements["inputs"]:
        dep = calculate_chain(
            session,
            inp["item_id"],
            inp["rate"],
            preferred_recipes=preferred_recipes,
            _visited=next_visited,
        )
        dependencies[inp["item_name"]] = dep
        _merge_sum(raw_materials, dep["raw_materials"])
        _merge_sum(byproducts_totals, dep["byproducts_totals"])
        _merge_sum(building_summary, dep["building_summary"])
        power_total += dep["power_mw_total"]

    return {
        "item_id": item_id,
        "item_name": requirements["output"]["item_name"],
        "required_rate": target_rate,
        "is_raw_material": False,
        "recipe": requirements,
        "dependencies": dependencies,
        "raw_materials": raw_materials,
        "byproducts_totals": byproducts_totals,
        "building_summary": building_summary,
        "power_mw_total": power_total,
    }


class ProductionCalculator:
    """
    Thin backwards-compatible wrapper around `calculate_chain`.

    Kept so existing callers keep working. New code should call `calculate_chain`
    directly - it's pure-functional and easier to test.
    """

    def __init__(self, session: Session, preferred_recipes: Optional[dict[int, int]] = None):
        self.session = session
        self.preferred_recipes = preferred_recipes or {}

    def calculate(self, item_id: int, target_rate: float) -> ProductionNode:
        return calculate_chain(
            self.session, item_id, target_rate, preferred_recipes=self.preferred_recipes
        )


def calculate_recipe_requirements(
    session: Session, recipe_id: int, item_id: int, target_rate: float
) -> RecipeRequirements:
    """Compute the requirements block for a single recipe at a target rate."""
    recipe = get_recipe(session, recipe_id)
    if recipe is None:
        raise ValueError(f"Recipe {recipe_id} not found")
    return _compute_requirements(recipe, item_id, target_rate)
