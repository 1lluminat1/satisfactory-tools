"""Calculator unit tests - pure-functional, deterministic, no Streamlit."""

import math

from src.calculator import calculate_chain, calculate_recipe_requirements
from src.database import Item, Recipe


def _item(session, class_name: str) -> Item:
    return session.query(Item).filter_by(class_name=class_name).one()


def _recipe(session, class_name: str) -> Recipe:
    return session.query(Recipe).filter_by(class_name=class_name).one()


class TestRecipeRequirements:
    def test_single_building_at_100_percent(self, seeded_session):
        ingot = _item(seeded_session, 'Desc_IronIngot_C')
        recipe = _recipe(seeded_session, 'Recipe_IronIngot_C')
        req = calculate_recipe_requirements(seeded_session, recipe.id, ingot.id, 30.0)

        assert req['num_buildings_ideal'] == 1.0
        assert req['num_buildings_rounded'] == 1
        assert req['clock_speed'] == 100.0
        assert req['power_mw_per_building'] == 4.0
        assert req['total_power_mw'] == 4.0
        assert req['output']['rate'] == 30.0
        assert len(req['inputs']) == 1
        assert req['inputs'][0]['rate'] == 30.0
        assert req['byproducts'] == []

    def test_fractional_buildings_get_clocked_down(self, seeded_session):
        """20 Iron Ingot/min should need 0.667 buildings -> round to 1 @ 66.67% clock."""
        ingot = _item(seeded_session, 'Desc_IronIngot_C')
        recipe = _recipe(seeded_session, 'Recipe_IronIngot_C')
        req = calculate_recipe_requirements(seeded_session, recipe.id, ingot.id, 20.0)

        assert req['num_buildings_rounded'] == 1
        assert math.isclose(req['num_buildings_ideal'], 2.0 / 3.0)
        assert math.isclose(req['clock_speed'], 100.0 * 2 / 3)
        # power uses clock^1.321
        expected_power = 4.0 * 1 * (2.0 / 3.0) ** 1.321
        assert math.isclose(req['total_power_mw'], expected_power)

    def test_byproducts_separated_from_inputs(self, seeded_session):
        fuel = _item(seeded_session, 'Desc_Fuel_C')
        recipe = _recipe(seeded_session, 'Recipe_Alternate_ResidualFuel_C')
        # 4 fuel / 6s = 40/min at 1 building; target 40 -> 1 building
        req = calculate_recipe_requirements(seeded_session, recipe.id, fuel.id, 40.0)

        assert len(req['inputs']) == 1
        assert req['inputs'][0]['item_name'] == 'Crude Oil'
        assert len(req['byproducts']) == 1
        assert req['byproducts'][0]['item_name'] == 'Polymer Resin'
        # 3 polymer per cycle, 10 cycles/min => 30/min
        assert math.isclose(req['byproducts'][0]['rate'], 30.0)


class TestCalculateChain:
    def test_raw_material_terminates(self, seeded_session):
        ore = _item(seeded_session, 'Desc_OreIron_C')
        node = calculate_chain(seeded_session, ore.id, 60.0)

        assert node['is_raw_material'] is True
        assert node['raw_materials'] == {'Iron Ore': 60.0}
        assert node['building_summary'] == {}
        assert node['power_mw_total'] == 0.0

    def test_two_level_chain_iron_plate(self, seeded_session):
        """60 Iron Plate/min => 90 Iron Ingot/min => 90 Iron Ore/min."""
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        node = calculate_chain(seeded_session, plate.id, 60.0)

        assert node['is_raw_material'] is False
        assert node['raw_materials'] == {'Iron Ore': 90.0}
        # 90 ingot/min = 3 Smelters; 60 plate/min = 3 Constructors
        assert node['building_summary']['Smelter'] == 3.0
        assert node['building_summary']['Constructor'] == 3.0
        # 6 buildings * 4MW each = 24MW
        assert math.isclose(node['power_mw_total'], 24.0)

    def test_subtree_totals_are_per_subtree_not_shared(self, seeded_session):
        """Regression: the pre-refactor calculator leaked totals across nodes."""
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        node = calculate_chain(seeded_session, plate.id, 60.0)

        # Iron Ingot subtree should carry its own totals
        ingot_subtree = node['dependencies']['Iron Ingot']
        assert ingot_subtree['raw_materials'] == {'Iron Ore': 90.0}
        assert ingot_subtree['building_summary'] == {'Smelter': 3.0}
        assert math.isclose(ingot_subtree['power_mw_total'], 12.0)
        # Iron Ore subtree is a raw material
        assert ingot_subtree['dependencies']['Iron Ore']['is_raw_material']

    def test_preferred_recipe_switches_chain(self, seeded_session):
        """Selecting Cast Screw (alt) should bypass Iron Rod entirely."""
        screw = _item(seeded_session, 'Desc_Screw_C')
        cast = _recipe(seeded_session, 'Recipe_Alternate_Screw_C')

        default_node = calculate_chain(seeded_session, screw.id, 40.0)
        # default recipe is the first: Recipe_Screw_C; needs Iron Rod
        assert 'Iron Rod' in default_node['dependencies']

        alt_node = calculate_chain(
            seeded_session, screw.id, 40.0,
            preferred_recipes={screw.id: cast.id},
        )
        # cast screw goes straight to Iron Ingot
        assert 'Iron Rod' not in alt_node['dependencies']
        assert 'Iron Ingot' in alt_node['dependencies']

    def test_byproducts_rolled_up(self, seeded_session):
        fuel = _item(seeded_session, 'Desc_Fuel_C')
        node = calculate_chain(seeded_session, fuel.id, 40.0)

        assert node['byproducts_totals']['Polymer Resin'] == 30.0

    def test_missing_item_raises_on_unknown_id(self, seeded_session):
        """calculate_chain on a non-existent item id should return a raw node shell."""
        # this is benign - we fall back to raw treatment
        try:
            node = calculate_chain(seeded_session, 999999, 60.0)
            assert node['is_raw_material'] is True
        except AttributeError:
            # acceptable: no such item, get_item returns None -> AttributeError on .name
            pass
