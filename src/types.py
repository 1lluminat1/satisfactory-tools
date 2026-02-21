from __future__ import annotations
from typing import NotRequired, TypedDict

class OutputItem(TypedDict):
    item_id: int
    item_name: str
    rate: float

class InputItem(TypedDict):
    item_id: int
    item_name: str
    rate: float

class RecipeRequirements(TypedDict):
    recipe_name: str
    building_name: str
    num_buildings: float
    output: OutputItem
    inputs: list[InputItem]
    byproducts: list[InputItem]

class ProductionNode(TypedDict):
    item_id: int
    item_name: str
    required_rate: float
    is_raw_material: bool
    recipe: NotRequired[RecipeRequirements]
    dependencies: NotRequired[dict[str, ProductionNode]]
    raw_materials: NotRequired[dict[str, float]]
    building_summary: NotRequired[dict[str, float]]

class IngredientEntry(TypedDict):
    name: str
    quantity: int

class RecipeDetails(TypedDict):
    id: int
    name: str
    building: str
    crafting_time: int
    inputs: list[IngredientEntry]
    outputs: list[IngredientEntry]

class ItemDetails(TypedDict):
    id: int
    name: str
    form: str
    stack_size: int
    sink_points: int

class RecipeUsageEntry(TypedDict):
    recipe_name: str
    building: str
    quantity: int