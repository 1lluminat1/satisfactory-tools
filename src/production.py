import math

from sqlalchemy.orm import Session

from .calculator import calculate_chain
from .database import Factory, Group, Item, ProductionLine, Purity, ResourceNode
from .queries import (
    get_all_groups,
    get_group,
    get_production_line,
    get_production_lines_for_group,
    get_resource_nodes_for_group,
)
from .schemas import ProductionNode


def get_group_resource_totals(session: Session, group_id: int) -> dict[str, float]:
    """
    Sums the extraction rates of all resource nodes in a group, grouped by item name.

    This is the foundation for max output and balance calculations — it tells you
    how much of each raw material is flowing into the group per minute.

    Args:
        session: An active SQLAlchemy Session.
        group_id: The primary key of the Group to aggregate.

    Returns:
        A dict mapping item name to total extraction rate (items/min) across all
        resource nodes in the group.
    """
    nodes = get_resource_nodes_for_group(session, group_id)
    totals: dict[str, float] = {}

    for node in nodes:
        totals[node['item_name']] = totals.get(node['item_name'], 0) + node['extraction_rate']

    return totals

def get_max_output(
    session: Session,
    group_id: int,
    item_id: int,
    preferred_recipes: dict[int, int] | None = None,
) -> dict:
    """
    Max achievable output rate for an item given a group's available resource nodes.

    Runs the calculator at 1/min to get raw-material ratios, then finds the limiting
    material (bottleneck) among the group's extraction totals.

    Returns:
        A dict with:
            - max_rate (float): Items/min achievable. 0.0 if any required raw material
              is missing from the group entirely.
            - bottleneck (Optional[str]): Name of the limiting material, or None if
              the item has no raw-material requirements, or the name of the first
              missing material if max_rate is 0.
            - missing (list[str]): Raw materials the group doesn't supply at all.
    """
    group_totals = get_group_resource_totals(session, group_id)
    node = calculate_chain(session, item_id, 1.0, preferred_recipes=preferred_recipes)
    raw = node['raw_materials']

    missing = [r for r in raw if r not in group_totals]
    if missing:
        return {"max_rate": 0.0, "bottleneck": missing[0], "missing": missing}

    if not raw:
        return {"max_rate": float('inf'), "bottleneck": None, "missing": []}

    ratios = {r: group_totals[r] / raw[r] for r in raw}
    bottleneck = min(ratios, key=ratios.get)
    return {"max_rate": ratios[bottleneck], "bottleneck": bottleneck, "missing": []}

def get_resource_balance(session: Session, production_line_id: int) -> dict:
    """
    Per-material balance for a production line vs. its group's supply.

    Returns a dict keyed by raw-material name with {required, available, balance}
    entries; the special key "__line__" carries line-level totals: power_mw,
    building_count, and bottleneck (the most-deficient material, or None).
    """
    balance: dict = {}
    production_line = get_production_line(session, production_line_id)
    group_totals = get_group_resource_totals(session, production_line.group_id)

    chain = calculate_chain(
        session, production_line.target_item_id, production_line.target_rate
    )
    raw_materials = chain['raw_materials']

    for resource, required in raw_materials.items():
        available = group_totals.get(resource, 0.0)
        balance[resource] = {
            'required': required,
            'available': available,
            'balance': available - required,
        }

    bottleneck = None
    if balance:
        bottleneck = min(balance, key=lambda m: balance[m]['balance'])

    balance['__line__'] = {
        'power_mw': chain['power_mw_total'],
        'building_count': sum(math.ceil(c) for c in chain['building_summary'].values()),
        'bottleneck': bottleneck,
    }
    return balance

def get_group_summary(session: Session, group_id: int) -> dict:
    """
    Aggregates all production and resource data for a group into a single summary dict.

    Args:
        session: An active SQLAlchemy Session.
        group_id: The primary key of the Group to summarize.

    Returns:
        A dict containing:
            - id (int): The group's primary key.
            - name (str): The group's name.
            - resource_totals (dict[str, float]): Total extraction rate per raw material
                across all resource nodes in the group.
            - production_lines (list): Each entry contains:
                - details (ProductionLineDetails): The production line's details.
                - balance (dict): Per-material required, available, and surplus/deficit.
            - overall_balance (dict[str, float]): Group resource totals minus combined
                consumption of all production lines. Positive = surplus, negative = deficit.
    """
    group = get_group(session, group_id)
    group_totals = get_group_resource_totals(session, group.id)
    lines = []
    overall_balance = group_totals.copy()
    total_power_mw = 0.0
    total_buildings = 0

    for line in get_production_lines_for_group(session, group.id):
        balance = get_resource_balance(session, line['id'])
        line_meta = balance.pop('__line__', {'power_mw': 0.0, 'building_count': 0, 'bottleneck': None})
        lines.append({
            "details": line,
            "balance": balance,
            "power_mw": line_meta['power_mw'],
            "building_count": line_meta['building_count'],
            "bottleneck": line_meta['bottleneck'],
        })

        for mat, entry in balance.items():
            overall_balance[mat] = overall_balance.get(mat, 0) - entry['required']

        if line['is_active']:
            total_power_mw += line_meta['power_mw']
            total_buildings += line_meta['building_count']

    return {
        "id": group.id,
        "name": group.name,
        "resource_totals": group_totals,
        "production_lines": lines,
        "overall_balance": overall_balance,
        "total_power_mw": total_power_mw,
        "total_buildings": total_buildings,
    }

def get_global_summary(session: Session) -> dict:
    """
    Aggregates summaries for every group into a single global view.

    Args:
        session: An active SQLAlchemy Session.

    Returns:
        A dict containing:
            - groups (list): Per-group summaries from get_group_summary.
            - global_resource_totals (dict[str, float]): Sum of each raw material's
                extraction rate across all groups.
            - global_balance (dict[str, float]): Sum of each group's overall_balance,
                i.e. network-wide surplus (positive) or deficit (negative) per material.
    """
    summaries = [get_group_summary(session, g['id']) for g in get_all_groups(session)]

    global_totals: dict[str, float] = {}
    global_balance: dict[str, float] = {}
    total_power_mw = 0.0
    total_buildings = 0
    for summary in summaries:
        for mat, rate in summary['resource_totals'].items():
            global_totals[mat] = global_totals.get(mat, 0.0) + rate
        for mat, bal in summary['overall_balance'].items():
            global_balance[mat] = global_balance.get(mat, 0.0) + bal
        total_power_mw += summary.get('total_power_mw', 0.0)
        total_buildings += summary.get('total_buildings', 0)

    return {
        "groups": summaries,
        "global_resource_totals": global_totals,
        "global_balance": global_balance,
        "total_power_mw": total_power_mw,
        "total_buildings": total_buildings,
    }


# --- Helpers ---

def _collect_factory_specs(chain: ProductionNode) -> list[dict]:
    """
    Walks a production chain and aggregates per-recipe building requirements.

    When a recipe appears in multiple subtrees, its ideal building count is summed
    and the highest depth wins for ordering. Returned list is ordered from deepest
    (closest to raw) first to the target recipe last.
    """
    specs: dict[int, dict] = {}

    def visit(node: ProductionNode, depth: int) -> None:
        if node.get('is_raw_material'):
            return
        req = node['recipe']
        rid = req['recipe_id']
        if rid in specs:
            specs[rid]['num_ideal'] += req['num_buildings_ideal']
            specs[rid]['depth'] = max(specs[rid]['depth'], depth)
        else:
            specs[rid] = {
                'recipe_id': rid,
                'recipe_name': req['recipe_name'],
                'num_ideal': req['num_buildings_ideal'],
                'depth': depth,
            }
        for dep in node.get('dependencies', {}).values():
            visit(dep, depth + 1)

    visit(chain, 0)
    return sorted(specs.values(), key=lambda s: -s['depth'])

def _build_factories(
    session: Session,
    line: ProductionLine,
    preferred_recipes: dict[int, int] | None = None,
) -> None:
    """
    Runs the calculator for a line and persists Factory rows for each step.

    For each recipe in the chain, creates a Factory with `building_count` = ceil of the
    ideal count and `clock_speed` = the fractional percentage needed so the rounded
    count hits the exact target rate. Does not commit.
    """
    from .calculator import calculate_chain

    chain = calculate_chain(
        session,
        line.target_item_id,
        line.target_rate,
        preferred_recipes=preferred_recipes,
    )

    for order, spec in enumerate(_collect_factory_specs(chain), start=1):
        num_ideal = spec['num_ideal']
        num_rounded = max(1, math.ceil(num_ideal))
        clock_speed = 100.0 * num_ideal / num_rounded
        session.add(Factory(
            name=f"{spec['recipe_name']} ({line.name})",
            production_line_id=line.id,
            recipe_id=spec['recipe_id'],
            building_count=num_rounded,
            clock_speed=clock_speed,
            order=order,
        ))


# --- Creation ---

def create_group(
    session: Session,
    name: str,
    description: str = "",
) -> Group:
    """
    Creates a group to organize production lines and resource nodes.

    Args:
        session: An active SQLAlchemy Session.
        name: Human-readable group name (e.g. "North Base").
        description: Optional free-form description.

    Returns:
        The newly created and committed Group.
    """
    group = Group(name=name, description=description)
    session.add(group)
    session.commit()
    return group

def create_production_line(
    session: Session,
    group_id: int,
    name: str,
    item_id: int,
    target_rate: float,
) -> ProductionLine:
    """
    Creates a production line in a group and persists its factory chain.

    Runs the production calculator to expand the target item into a full production
    chain, then persists one Factory row per recipe (aggregating duplicates) ordered
    from raw-adjacent to final step. Building counts are rounded up to whole buildings.

    Args:
        session: An active SQLAlchemy Session.
        group_id: The Group to attach the new production line to.
        name: Human-readable name for the production line.
        item_id: The target output item.
        target_rate: Desired output rate in items per minute.

    Returns:
        The newly created and committed ProductionLine.
    """
    line = ProductionLine(
        name=name,
        target_item_id=item_id,
        target_rate=target_rate,
        group_id=group_id,
        is_active=True,
    )
    session.add(line)
    session.flush()

    _build_factories(session, line)
    session.commit()
    return line

def add_resource_node(
    session: Session,
    group_id: int,
    name: str,
    item_id: int,
    purity: str | Purity,
    extraction_rate: float,
) -> ResourceNode:
    """
    Adds a resource node to a group.

    Args:
        session: An active SQLAlchemy Session.
        group_id: The Group the resource node belongs to.
        name: User-assigned name (e.g. "Iron Node Alpha").
        item_id: The Item extracted by this node.
        purity: Node purity. Accepts the Purity enum or one of "IMPURE", "NORMAL", "PURE".
        extraction_rate: Extraction rate in items per minute.

    Returns:
        The newly created and committed ResourceNode.
    """
    node = ResourceNode(
        name=name,
        item_id=item_id,
        purity=Purity(purity) if isinstance(purity, str) else purity,
        extraction_rate=extraction_rate,
        group_id=group_id,
    )
    session.add(node)
    session.commit()
    return node


# --- Modification ---

def update_production_line_rate(
    session: Session,
    production_line_id: int,
    new_rate: float,
) -> ProductionLine:
    """
    Updates a production line's target rate and regenerates its factory chain.

    Deletes all existing Factory rows for the line, then reruns the calculator at
    the new rate and persists fresh factories.

    Args:
        session: An active SQLAlchemy Session.
        production_line_id: The ProductionLine to update.
        new_rate: New target output rate in items per minute.

    Returns:
        The updated ProductionLine.
    """
    line = get_production_line(session, production_line_id)
    for factory in list(line.factories):
        session.delete(factory)
    session.flush()

    line.target_rate = new_rate
    _build_factories(session, line)
    session.commit()
    return line

def set_production_line_active(
    session: Session,
    production_line_id: int,
    is_active: bool,
) -> ProductionLine:
    """
    Toggles a production line's active flag.

    Args:
        session: An active SQLAlchemy Session.
        production_line_id: The ProductionLine to update.
        is_active: New active state.

    Returns:
        The updated ProductionLine.
    """
    line = get_production_line(session, production_line_id)
    line.is_active = is_active
    session.commit()
    return line

# --- Rename / update ---

def rename_group(
    session: Session,
    group_id: int,
    name: str,
    description: str | None = None,
) -> Group:
    """Rename a group and optionally update its description."""
    group = get_group(session, group_id)
    group.name = name
    if description is not None:
        group.description = description
    session.commit()
    return group

def rename_production_line(session: Session, production_line_id: int, name: str) -> ProductionLine:
    """Rename a production line."""
    line = get_production_line(session, production_line_id)
    line.name = name
    session.commit()
    return line

def update_resource_node(
    session: Session,
    node_id: int,
    *,
    name: str | None = None,
    purity: str | Purity | None = None,
    extraction_rate: float | None = None,
) -> ResourceNode:
    """Update any subset of a resource node's mutable fields."""
    node = session.get(ResourceNode, node_id)
    if node is None:
        raise ValueError(f"ResourceNode {node_id} not found")
    if name is not None:
        node.name = name
    if purity is not None:
        node.purity = Purity(purity) if isinstance(purity, str) else purity
    if extraction_rate is not None:
        node.extraction_rate = extraction_rate
    session.commit()
    return node


# --- Delete ---

def delete_group(session: Session, group_id: int) -> None:
    """
    Delete a group and everything it owns: production lines (+ their factories) and
    resource nodes. Safe even if the group has no children.
    """
    group = get_group(session, group_id)
    if group is None:
        return
    for line in list(group.production_lines):
        for factory in list(line.factories):
            session.delete(factory)
        session.delete(line)
    for node in list(group.resource_nodes):
        session.delete(node)
    session.delete(group)
    session.commit()

def delete_production_line(session: Session, production_line_id: int) -> None:
    """Delete a production line and its factories."""
    line = get_production_line(session, production_line_id)
    if line is None:
        return
    for factory in list(line.factories):
        session.delete(factory)
    session.delete(line)
    session.commit()

def delete_resource_node(session: Session, node_id: int) -> None:
    """Delete a resource node."""
    node = session.get(ResourceNode, node_id)
    if node is None:
        return
    session.delete(node)
    session.commit()


# --- Import / export ---

def export_factory_state(session: Session) -> dict:
    """
    Serialize all user-created state (groups, production lines, resource nodes) to
    a JSON-safe dict. Items/recipes/buildings are left out - they come from ETL.

    Items are referenced by class_name so imports are portable across re-ETLs.
    """
    groups_out = []
    for group in session.query(Group).all():
        groups_out.append({
            "name": group.name,
            "description": group.description or "",
            "production_lines": [
                {
                    "name": line.name,
                    "target_item_class": line.target_item.class_name,
                    "target_rate": line.target_rate,
                    "is_active": line.is_active,
                }
                for line in group.production_lines
            ],
            "resource_nodes": [
                {
                    "name": node.name,
                    "item_class": node.item.class_name,
                    "purity": node.purity.name if node.purity else "NORMAL",
                    "extraction_rate": node.extraction_rate,
                }
                for node in group.resource_nodes
            ],
        })
    return {"version": 1, "groups": groups_out}


def import_factory_state(session: Session, data: dict) -> dict:
    """
    Import groups/lines/nodes from an export dict. Appends to existing state
    (does not wipe). Returns a summary of what was imported or skipped.
    """
    summary = {"groups": 0, "lines": 0, "nodes": 0, "skipped_items": []}
    for group_data in data.get("groups", []):
        group = create_group(
            session, group_data["name"], group_data.get("description", "")
        )
        summary["groups"] += 1

        for node_data in group_data.get("resource_nodes", []):
            item = session.query(Item).filter_by(class_name=node_data["item_class"]).first()
            if item is None:
                summary["skipped_items"].append(node_data["item_class"])
                continue
            add_resource_node(
                session, group.id, node_data["name"], item.id,
                node_data.get("purity", "NORMAL"),
                node_data.get("extraction_rate", 0.0),
            )
            summary["nodes"] += 1

        for line_data in group_data.get("production_lines", []):
            item = session.query(Item).filter_by(
                class_name=line_data["target_item_class"]
            ).first()
            if item is None:
                summary["skipped_items"].append(line_data["target_item_class"])
                continue
            line = create_production_line(
                session, group.id, line_data["name"], item.id,
                line_data.get("target_rate", 60.0),
            )
            if not line_data.get("is_active", True):
                set_production_line_active(session, line.id, False)
            summary["lines"] += 1

    return summary


# --- Starter data ---

def create_starter_data(session: Session) -> Group | None:
    """
    Seed a small demo group with iron + copper extraction and an Iron Plate line.

    No-op if any groups already exist.

    Returns the new Group, or None if groups already exist or needed items
    are missing from the ETL-loaded database.
    """
    if session.query(Group).count() > 0:
        return None

    iron_ore = session.query(Item).filter_by(class_name='Desc_OreIron_C').first()
    copper_ore = session.query(Item).filter_by(class_name='Desc_OreCopper_C').first()
    iron_plate = session.query(Item).filter_by(class_name='Desc_IronPlate_C').first()
    if not (iron_ore and iron_plate):
        return None

    group = create_group(session, "Demo Base", "Starter setup - feel free to edit or delete.")
    add_resource_node(session, group.id, "Iron Node A", iron_ore.id, "PURE", 240.0)
    if copper_ore:
        add_resource_node(session, group.id, "Copper Node A", copper_ore.id, "NORMAL", 120.0)
    create_production_line(session, group.id, "Iron Plates x60", iron_plate.id, 60.0)
    return group
