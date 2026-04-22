from __future__ import annotations
from typing import NotRequired, Optional, TypedDict

from .database import Purity

class OutputItem(TypedDict):
    item_id: int
    item_name: str
    rate: float

class InputItem(TypedDict):
    item_id: int
    item_name: str
    rate: float

class RecipeRequirements(TypedDict):
    recipe_id: int
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

class GroupSummary(TypedDict):
    id: int
    name: str
    description: str
    production_line_count: int
    resource_node_count: int

class ResourceNodeDetails(TypedDict):
    id: int
    name: str
    item_id: int
    item_name: str
    purity: Purity
    extraction_rate: float

class ProductionLineDetails(TypedDict):
    id: int
    name: str
    target_item_id: int
    target_item_name: str
    target_rate: float
    is_active: bool
    group_id: Optional[int]

class FactoryDetails(TypedDict):
    id: int
    name: str
    recipe_id: int
    recipe_name: str
    building_name: str
    building_count: int
    clock_speed: float
    order: int