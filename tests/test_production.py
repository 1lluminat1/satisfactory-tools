"""Integration tests for production.py CRUD + summary functions."""

import json
import math

from src.database import Factory, Group, Item, ProductionLine, Purity, ResourceNode
from src.production import (
    add_resource_node,
    create_group,
    create_production_line,
    create_starter_data,
    delete_group,
    delete_production_line,
    delete_resource_node,
    export_factory_state,
    get_global_summary,
    get_group_summary,
    get_max_output,
    import_factory_state,
    rename_group,
    rename_production_line,
    set_production_line_active,
    update_production_line_rate,
    update_resource_node,
)


def _item(session, class_name: str) -> Item:
    return session.query(Item).filter_by(class_name=class_name).one()


class TestGroupCrud:
    def test_create_and_rename(self, seeded_session):
        g = create_group(seeded_session, "North", "desc")
        assert g.id is not None
        rename_group(seeded_session, g.id, "Northern", "new desc")
        refreshed = seeded_session.get(Group, g.id)
        assert refreshed.name == "Northern"
        assert refreshed.description == "new desc"

    def test_delete_cascades(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        ore = _item(seeded_session, 'Desc_OreIron_C')
        g = create_group(seeded_session, "X", "")
        add_resource_node(seeded_session, g.id, "Node", ore.id, "NORMAL", 60.0)
        create_production_line(seeded_session, g.id, "Line", plate.id, 20.0)

        assert seeded_session.query(ProductionLine).count() == 1
        assert seeded_session.query(ResourceNode).count() == 1
        assert seeded_session.query(Factory).count() >= 1

        delete_group(seeded_session, g.id)
        assert seeded_session.query(Group).count() == 0
        assert seeded_session.query(ProductionLine).count() == 0
        assert seeded_session.query(ResourceNode).count() == 0
        assert seeded_session.query(Factory).count() == 0


class TestProductionLine:
    def test_create_persists_factories_in_order(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        g = create_group(seeded_session, "G", "")
        line = create_production_line(seeded_session, g.id, "L", plate.id, 60.0)

        factories = sorted(line.factories, key=lambda f: f.order)
        # chain: Iron Ore -> Iron Ingot (Smelter) -> Iron Plate (Constructor)
        assert [f.recipe.name for f in factories] == ["Iron Ingot", "Iron Plate"]
        assert all(f.building_count == 3 for f in factories)
        assert all(math.isclose(f.clock_speed, 100.0) for f in factories)

    def test_update_rate_rebuilds_factories(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        g = create_group(seeded_session, "G", "")
        line = create_production_line(seeded_session, g.id, "L", plate.id, 60.0)

        update_production_line_rate(seeded_session, line.id, 120.0)
        seeded_session.refresh(line)
        assert line.target_rate == 120.0
        assert all(f.building_count == 6 for f in line.factories)

    def test_set_active_toggles(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        g = create_group(seeded_session, "G", "")
        line = create_production_line(seeded_session, g.id, "L", plate.id, 60.0)

        set_production_line_active(seeded_session, line.id, False)
        seeded_session.refresh(line)
        assert line.is_active is False

    def test_rename_and_delete(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        g = create_group(seeded_session, "G", "")
        line = create_production_line(seeded_session, g.id, "Original", plate.id, 60.0)

        rename_production_line(seeded_session, line.id, "Renamed")
        seeded_session.refresh(line)
        assert line.name == "Renamed"

        delete_production_line(seeded_session, line.id)
        assert seeded_session.get(ProductionLine, line.id) is None
        # factories gone too
        assert seeded_session.query(Factory).count() == 0


class TestResourceNode:
    def test_update_and_delete(self, seeded_session):
        ore = _item(seeded_session, 'Desc_OreIron_C')
        g = create_group(seeded_session, "G", "")
        n = add_resource_node(seeded_session, g.id, "A", ore.id, "NORMAL", 60.0)

        update_resource_node(seeded_session, n.id, purity="PURE", extraction_rate=240.0)
        seeded_session.refresh(n)
        assert n.purity == Purity.PURE
        assert n.extraction_rate == 240.0

        delete_resource_node(seeded_session, n.id)
        assert seeded_session.get(ResourceNode, n.id) is None


class TestSummaries:
    def test_group_summary_balance_and_power(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        ore = _item(seeded_session, 'Desc_OreIron_C')
        g = create_group(seeded_session, "N", "")
        add_resource_node(seeded_session, g.id, "A", ore.id, "PURE", 120.0)
        create_production_line(seeded_session, g.id, "L", plate.id, 60.0)

        summary = get_group_summary(seeded_session, g.id)
        assert summary['resource_totals'] == {'Iron Ore': 120.0}
        assert math.isclose(summary['total_power_mw'], 24.0)
        assert summary['total_buildings'] == 6

        line_summary = summary['production_lines'][0]
        # needs 90 ore, has 120 -> balance is positive, bottleneck is Iron Ore
        assert line_summary['bottleneck'] == 'Iron Ore'
        assert line_summary['balance']['Iron Ore']['balance'] == 30.0

    def test_global_summary_rolls_up_groups(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        ore = _item(seeded_session, 'Desc_OreIron_C')
        for name in ["N", "S"]:
            g = create_group(seeded_session, name, "")
            add_resource_node(seeded_session, g.id, "A", ore.id, "PURE", 120.0)
            create_production_line(seeded_session, g.id, "L", plate.id, 60.0)

        gs = get_global_summary(seeded_session)
        assert len(gs['groups']) == 2
        assert math.isclose(gs['total_power_mw'], 48.0)
        assert gs['total_buildings'] == 12
        assert gs['global_resource_totals']['Iron Ore'] == 240.0

    def test_max_output_bottleneck(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        ore = _item(seeded_session, 'Desc_OreIron_C')
        g = create_group(seeded_session, "G", "")
        add_resource_node(seeded_session, g.id, "A", ore.id, "PURE", 240.0)

        result = get_max_output(seeded_session, g.id, plate.id)
        # 240 ore supports 60 plate * (240/90) == 160 plate/min
        assert math.isclose(result['max_rate'], 160.0)
        assert result['bottleneck'] == 'Iron Ore'
        assert result['missing'] == []

    def test_max_output_missing_material(self, seeded_session):
        screw = _item(seeded_session, 'Desc_Screw_C')
        g = create_group(seeded_session, "G", "")
        # no nodes -> missing Iron Ore

        result = get_max_output(seeded_session, g.id, screw.id)
        assert result['max_rate'] == 0.0
        assert 'Iron Ore' in result['missing']


class TestImportExport:
    def test_round_trip(self, seeded_session):
        plate = _item(seeded_session, 'Desc_IronPlate_C')
        ore = _item(seeded_session, 'Desc_OreIron_C')
        g = create_group(seeded_session, "N", "demo")
        add_resource_node(seeded_session, g.id, "A", ore.id, "PURE", 240.0)
        line = create_production_line(seeded_session, g.id, "L", plate.id, 60.0)
        set_production_line_active(seeded_session, line.id, False)

        exported = export_factory_state(seeded_session)
        assert exported['version'] == 1

        # round-trip through json to catch non-serializable fields
        roundtripped = json.loads(json.dumps(exported))
        assert roundtripped == exported

        # Wipe and reimport
        delete_group(seeded_session, g.id)
        summary = import_factory_state(seeded_session, exported)
        assert summary['groups'] == 1
        assert summary['lines'] == 1
        assert summary['nodes'] == 1

        reloaded = seeded_session.query(Group).one()
        assert reloaded.name == "N"
        assert reloaded.production_lines[0].is_active is False


class TestStarterData:
    def test_no_op_if_groups_exist(self, seeded_session):
        create_group(seeded_session, "existing", "")
        result = create_starter_data(seeded_session)
        assert result is None

    def test_creates_on_empty_db(self, seeded_session):
        # seeded_session has items but no groups
        assert seeded_session.query(Group).count() == 0
        result = create_starter_data(seeded_session)
        assert result is not None
        assert result.name == "Demo Base"
        assert len(result.resource_nodes) >= 1
        assert len(result.production_lines) >= 1
