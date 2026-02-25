from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from .schemas import FactoryDetails, GroupSummary, ItemDetails, ProductionLineDetails, RecipeDetails, RecipeUsageEntry, ResourceNodeDetails

from .database import Building, Factory, Group, Item, ProductionLine, Recipe, RecipeIngredient, ResourceNode


# --- Helpers ---

def _serialize_item(item: Item) -> ItemDetails:
    """
    Serializes an Item ORM object into an ItemDetails dict.

    Args:
        item: The Item ORM instance to serialize.

    Returns:
        An ItemDetails dict containing the item's id, name, form, stack_size, and sink_points.
    """
    return {
        "id": item.id,
        "name": item.name,
        "form": item.form,
        "stack_size": item.stack_size,
        "sink_points": item.sink_points
    }


# --- Item Queries ---

def get_item(session: Session, item_id: int) -> Optional[Item]:
    """
    Retrieves a single Item by its ID.

    Args:
        session: An active SQLAlchemy Session.
        item_id: The primary key of the Item to retrieve.

    Returns:
        The matching Item ORM instance, or None if not found.
    """
    return session.execute(select(Item).where(Item.id == item_id)).scalar()

def get_all_items(session: Session) -> list[ItemDetails]:
    """
    Retrieves all items in the database as serialized dicts.

    Args:
        session: An active SQLAlchemy Session.

    Returns:
        A list of ItemDetails dicts for every Item in the database.
    """
    return [_serialize_item(item) for item in session.execute(select(Item)).scalars().all()]

def get_item_recipe_usage(
    session: Session,
    item_id: int,
    *,
    is_output: bool = False,
) -> list[RecipeUsageEntry]:
    """
    Retrieves all recipes that use a given item, either as an input or output.

    Args:
        session: An active SQLAlchemy Session.
        item_id: The primary key of the Item to look up.
        is_output: If True, returns recipes where the item is an output.
                   If False (default), returns recipes where the item is an input.

    Returns:
        A list of RecipeUsageEntry dicts containing the recipe name, building, and quantity.
    """
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


# --- Recipe Queries ---

def get_recipe(session: Session, recipe_id: int) -> Optional[Recipe]:
    """
    Retrieves a single Recipe by its ID.

    Args:
        session: An active SQLAlchemy Session.
        recipe_id: The primary key of the Recipe to retrieve.

    Returns:
        The matching Recipe ORM instance, or None if not found.
    """
    return session.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar()

def get_recipe_details(recipe: Recipe) -> RecipeDetails:
    """
    Serializes a Recipe ORM object into a RecipeDetails dict, separating
    ingredients into inputs and outputs.

    Args:
        recipe: The Recipe ORM instance to serialize.

    Returns:
        A RecipeDetails dict containing the recipe's id, name, building, crafting_time,
        and categorized lists of inputs and outputs.
    """
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

def get_all_recipes(session: Session) -> list[RecipeDetails]:
    """
    Retrieves all recipes in the database as serialized dicts.

    Args:
        session: An active SQLAlchemy Session.

    Returns:
        A list of RecipeDetails dicts for every Recipe in the database.
    """
    return [
        get_recipe_details(recipe) for recipe in 
            session.execute(select(Recipe)).scalars().all()
    ]

def get_recipes_for_item(session: Session, item_id: int) -> list[Recipe]:
    """
    Retrieves all recipes that produce a given item as an output.

    Args:
        session: An active SQLAlchemy Session.
        item_id: The primary key of the Item to find recipes for.

    Returns:
        A list of Recipe ORM instances that output the specified item.
        Returns an empty list if the item has no producing recipes (i.e. it is a raw material).
    """
    return session.execute(select(Recipe)
                           .join(Recipe.ingredients)
                           .where(
                               RecipeIngredient.item_id == item_id,
                               RecipeIngredient.is_output.is_(True)
                           )).scalars().all()


# --- Building Queries ---

def get_all_buildings(session: Session) -> list[str]:
    """
    Retrieves the names of all buildings in the database.

    Args:
        session: An active SQLAlchemy Session.

    Returns:
        A list of building name strings.
    """
    return list(session.execute(select(Building.name)).scalars().all())


# --- Group Queries ---

def get_group(session: Session, group_id: int) -> Optional[Group]:
    """
    Retrieves a single Group by its ID.

    Args:
        session: An active SQLAlchemy Session.
        group_id: The primary key of the Group to retrieve.

    Returns:
        The matching Group ORM instance, or None if not found.
    """
    return session.execute(select(Group).where(Group.id == group_id)).scalar()

def get_all_groups(session: Session) -> list[GroupSummary]:
    """
    Retrieves all groups with aggregate counts for production lines and resource nodes.

    Args:
        session: An active SQLAlchemy Session.

    Returns:
        A list of GroupSummary dicts for every Group in the database.
    """
    groups = session.execute(select(Group)).scalars().all()
    return [
        {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "production_line_count": len(group.production_lines),
            "resource_node_count": len(group.resource_nodes)
        }
        for group in groups
    ]


# --- Production Line Queries ---

def get_production_line(session: Session, production_line_id: int) -> Optional[ProductionLine]:
    """
    Retrieves a single ProductionLine by its ID.

    Args:
        session: An active SQLAlchemy Session.
        production_line_id: The primary key of the ProductionLine to retrieve.

    Returns:
        The matching ProductionLine ORM instance, or None if not found.
    """
    return session.execute(
        select(ProductionLine).where(ProductionLine.id == production_line_id)
    ).scalar()

def get_production_lines_for_group(session: Session, group_id: int) -> list[ProductionLineDetails]:
    """
    Retrieves all production lines belonging to a group as serialized dicts.

    Args:
        session: An active SQLAlchemy Session.
        group_id: The primary key of the Group to query.

    Returns:
        A list of ProductionLineDetails dicts for every ProductionLine in the group.
    """
    lines = session.execute(
        select(ProductionLine).where(ProductionLine.group_id == group_id)
    ).scalars().all()

    return [
        {
            "id": line.id,
            "name": line.name,
            "target_item_id": line.target_item_id,
            "target_item_name": line.target_item.name,
            "target_rate": line.target_rate,
            "is_active": line.is_active,
            "group_id": line.group_id
        }
        for line in lines
    ]

def get_factories_for_production_line(session: Session, production_line_id: int) -> list[FactoryDetails]:
    """
    Retrieves all factories within a production line, ordered by their processing order.

    Args:
        session: An active SQLAlchemy Session.
        production_line_id: The primary key of the ProductionLine to query.

    Returns:
        A list of FactoryDetails dicts ordered by the Factory's order field.
    """
    factories = session.execute(
        select(Factory)
        .where(Factory.production_line_id == production_line_id)
        .order_by(Factory.order)
    ).scalars().all()

    return [
        {
            "id": factory.id,
            "name": factory.name,
            "recipe_id": factory.recipe_id,
            "recipe_name": factory.recipe.name,
            "building_name": factory.recipe.building.name,
            "building_count": factory.building_count,
            "clock_speed": factory.clock_speed,
            "order": factory.order
        }
        for factory in factories
    ]


# --- Resource Node Queries ---

def get_resource_nodes_for_group(session: Session, group_id: int) -> list[ResourceNodeDetails]:
    """
    Retrieves all resource nodes in a group.

    Args:
        session: An active SQLAlchemy Session.
        group_id: The primary key of the Group to query.

    Returns:
        A flat list of ResourceNodeDetails dicts for every ResourceNode in the group.
    """
    nodes = session.execute(
        select(ResourceNode)
        .where(ResourceNode.group_id == group_id)
    ).scalars().all()

    return [
        {
            "id": node.id,
            "name": node.name,
            "item_id": node.item_id,
            "item_name": node.item.name,
            "purity": node.purity,
            "extraction_rate": node.extraction_rate
        }
        for node in nodes
    ]
