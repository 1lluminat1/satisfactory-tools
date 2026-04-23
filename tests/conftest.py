"""
Shared pytest fixtures.

Builds a tiny in-memory SQLite database with a hand-crafted set of items, buildings,
and recipes - enough to exercise the calculator and CRUD without needing a full ETL
run on Docs.json.
"""

import pytest
from sqlalchemy.orm import sessionmaker

from src.database import (
    Base,
    Building,
    Item,
    ItemForm,
    Recipe,
    RecipeIngredient,
    get_engine,
)


@pytest.fixture()
def engine():
    """Fresh in-memory SQLite engine per test."""
    eng = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    """SQLAlchemy session bound to the in-memory engine."""
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def seeded_session(session):
    """
    Session pre-populated with a minimal vertical slice:

        Iron Ore (raw) -> Iron Ingot -> Iron Plate
        Iron Ore (raw) -> Iron Ingot -> Iron Rod -> Screw (alt: Cast Screw from Iron Ingot)

    Plus one byproduct recipe: "Fuel Alt" produces Fuel + Polymer Resin.
    """
    # Items
    iron_ore = Item(class_name='Desc_OreIron_C', name='Iron Ore', form=ItemForm.SOLID)
    iron_ingot = Item(class_name='Desc_IronIngot_C', name='Iron Ingot', form=ItemForm.SOLID)
    iron_plate = Item(class_name='Desc_IronPlate_C', name='Iron Plate', form=ItemForm.SOLID)
    iron_rod = Item(class_name='Desc_IronRod_C', name='Iron Rod', form=ItemForm.SOLID)
    screw = Item(class_name='Desc_Screw_C', name='Screw', form=ItemForm.SOLID)
    crude_oil = Item(class_name='Desc_CrudeOil_C', name='Crude Oil', form=ItemForm.LIQUID)
    fuel = Item(class_name='Desc_Fuel_C', name='Fuel', form=ItemForm.LIQUID)
    polymer = Item(class_name='Desc_PolymerResin_C', name='Polymer Resin', form=ItemForm.SOLID)
    session.add_all([iron_ore, iron_ingot, iron_plate, iron_rod, screw, crude_oil, fuel, polymer])
    session.flush()

    # Buildings (with power)
    smelter = Building(class_name='Build_SmelterMk1_C', name='Smelter', power_mw=4.0)
    constructor = Building(class_name='Build_ConstructorMk1_C', name='Constructor', power_mw=4.0)
    refinery = Building(class_name='Build_OilRefinery_C', name='Refinery', power_mw=30.0)
    session.add_all([smelter, constructor, refinery])
    session.flush()

    # Recipes
    # Iron Ingot: 1 Iron Ore -> 1 Iron Ingot in 2s (= 30/min)
    r_ingot = Recipe(
        class_name='Recipe_IronIngot_C', name='Iron Ingot',
        crafting_time=2.0, building_id=smelter.id,
    )
    # Iron Plate: 3 Iron Ingot -> 2 Iron Plate in 6s (= 20/min)
    r_plate = Recipe(
        class_name='Recipe_IronPlate_C', name='Iron Plate',
        crafting_time=6.0, building_id=constructor.id,
    )
    # Iron Rod: 1 Iron Ingot -> 1 Iron Rod in 4s (= 15/min)
    r_rod = Recipe(
        class_name='Recipe_IronRod_C', name='Iron Rod',
        crafting_time=4.0, building_id=constructor.id,
    )
    # Screw: 1 Iron Rod -> 4 Screw in 6s (= 40/min)
    r_screw = Recipe(
        class_name='Recipe_Screw_C', name='Screw',
        crafting_time=6.0, building_id=constructor.id,
    )
    # Alt: Cast Screw: 5 Iron Ingot -> 20 Screw in 24s (= 50/min)
    r_screw_alt = Recipe(
        class_name='Recipe_Alternate_Screw_C', name='Cast Screw',
        crafting_time=24.0, building_id=constructor.id,
    )
    # Fuel Alt (residual): 6 Crude Oil -> 4 Fuel + 3 Polymer Resin in 6s
    r_fuel = Recipe(
        class_name='Recipe_Alternate_ResidualFuel_C', name='Residual Fuel',
        crafting_time=6.0, building_id=refinery.id,
    )
    session.add_all([r_ingot, r_plate, r_rod, r_screw, r_screw_alt, r_fuel])
    session.flush()

    # Ingredients
    session.add_all([
        # Iron Ingot
        RecipeIngredient(recipe_id=r_ingot.id, item_id=iron_ore.id, quantity=1, is_output=False),
        RecipeIngredient(recipe_id=r_ingot.id, item_id=iron_ingot.id, quantity=1, is_output=True),
        # Iron Plate
        RecipeIngredient(recipe_id=r_plate.id, item_id=iron_ingot.id, quantity=3, is_output=False),
        RecipeIngredient(recipe_id=r_plate.id, item_id=iron_plate.id, quantity=2, is_output=True),
        # Iron Rod
        RecipeIngredient(recipe_id=r_rod.id, item_id=iron_ingot.id, quantity=1, is_output=False),
        RecipeIngredient(recipe_id=r_rod.id, item_id=iron_rod.id, quantity=1, is_output=True),
        # Screw
        RecipeIngredient(recipe_id=r_screw.id, item_id=iron_rod.id, quantity=1, is_output=False),
        RecipeIngredient(recipe_id=r_screw.id, item_id=screw.id, quantity=4, is_output=True),
        # Cast Screw (alt)
        RecipeIngredient(recipe_id=r_screw_alt.id, item_id=iron_ingot.id, quantity=5, is_output=False),
        RecipeIngredient(recipe_id=r_screw_alt.id, item_id=screw.id, quantity=20, is_output=True),
        # Residual Fuel
        RecipeIngredient(recipe_id=r_fuel.id, item_id=crude_oil.id, quantity=6, is_output=False),
        RecipeIngredient(recipe_id=r_fuel.id, item_id=fuel.id, quantity=4, is_output=True),
        RecipeIngredient(recipe_id=r_fuel.id, item_id=polymer.id, quantity=3, is_output=True),
    ])
    session.commit()

    return session
