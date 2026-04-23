from __future__ import annotations

from typing import NotRequired, Optional, TypedDict


class ResolvedItem(TypedDict):
    """An item with a calculated per-minute rate."""
    item_id: int
    item_name: str
    rate: float


# Backwards-compatible aliases used by older callers / tests.
OutputItem = ResolvedItem
InputItem = ResolvedItem


class RecipeRequirements(TypedDict):
    """Everything needed to describe one recipe running at a target rate."""
    recipe_id: int
    recipe_name: str
    building_id: int
    building_name: str
    num_buildings_ideal: float        # fractional (e.g. 1.5 Constructors)
    num_buildings_rounded: int        # ceil of ideal
    clock_speed: float                # % needed so `rounded` buildings hit target exactly
    power_mw_per_building: float
    total_power_mw: float             # includes clock_speed^1.321 scaling
    output: ResolvedItem
    inputs: list[ResolvedItem]
    byproducts: list[ResolvedItem]


class ProductionNode(TypedDict):
    """A node in the calculated production chain."""
    item_id: int
    item_name: str
    required_rate: float
    is_raw_material: bool
    recipe: NotRequired[RecipeRequirements]
    dependencies: NotRequired[dict[str, "ProductionNode"]]
    # Subtree totals — always present, even on raw nodes (empty dicts / 0).
    raw_materials: dict[str, float]
    byproducts_totals: dict[str, float]
    building_summary: dict[str, float]
    power_mw_total: float


class IngredientEntry(TypedDict):
    name: str
    quantity: int


class RecipeDetails(TypedDict):
    id: int
    name: str
    building: str
    crafting_time: float
    inputs: list[IngredientEntry]
    outputs: list[IngredientEntry]


class ItemDetails(TypedDict):
    id: int
    name: str
    form: Optional[str]
    stack_size: Optional[int]
    sink_points: Optional[int]


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
    purity: str            # serialized as enum .name for Arrow compatibility
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
