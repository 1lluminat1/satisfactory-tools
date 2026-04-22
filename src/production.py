import math
from typing import Union

from sqlalchemy.orm import Session

from .database import Factory, Group, Item, ProductionLine, Purity, ResourceNode
from .queries import get_group, get_production_lines_for_group, get_resource_nodes_for_group, get_production_line, get_all_groups
from .calculator import ProductionCalculator
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

def get_max_output(session: Session, group_id: int, item_id: int) -> float:
    """
    Calculates the maximum achievable output rate for an item given a group's available resource nodes.

    Runs the production calculator at a rate of 1/min to determine raw material ratios,
    then finds the bottleneck material by comparing available supply against required rates.

    Args:
        session: An active SQLAlchemy Session.
        group_id: The primary key of the Group whose resource nodes will be used.
        item_id: The primary key of the Item to calculate max output for.

    Returns:
        The maximum achievable output rate in items/min as a float.
        Returns 0.0 if the group is missing one or more required raw materials entirely.
    """
    calculator = ProductionCalculator(session)
    result = []
    group_totals = get_group_resource_totals(session, group_id)
    node = calculator.calculate(item_id, 1.0)

    for resource in node['raw_materials']:
        if resource not in group_totals:
            return 0.0 # group is missing required raw materials for item
        result.append(group_totals[resource] / node['raw_materials'][resource])
    
    return min(result)

def get_resource_balance(session: Session, production_line_id: int) -> dict:
    """
    Calculates the resource balance for a production line against its group's available supply.

    For each raw material required by the production line, compares the group's total
    extraction rate against what the line consumes, returning the surplus or deficit.

    Args:
        session: An active SQLAlchemy Session.
        production_line_id: The primary key of the ProductionLine to evaluate.

    Returns:
        A dict mapping raw material name to a balance entry containing:
            - required (float): Rate consumed by the production line in items/min.
            - available (float): Rate supplied by the group's resource nodes in items/min.
            - balance (float): Surplus (positive) or deficit (negative) in items/min.
    """
    balance = {}
    calculator = ProductionCalculator(session)
    production_line = get_production_line(session, production_line_id)
    group_totals = get_group_resource_totals(session, production_line.group_id)
    raw_materials = calculator.calculate(
        production_line.target_item_id, production_line.target_rate
    )['raw_materials']

    for resource in raw_materials:
        balance[resource] = {
            'required': raw_materials[resource],
            'available': group_totals.get(resource, 0.0),
            'balance': group_totals.get(resource, 0.0) - raw_materials[resource]
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

    for line in get_production_lines_for_group(session, group.id):
        balance = get_resource_balance(session, line['id'])
        lines.append({
            "details": line,
            "balance": balance
        })

        for mat in balance:
            overall_balance[mat] = overall_balance.get(mat, 0) - balance[mat]['required']

    return {
        "id": group.id,
        "name": group.name,
        "resource_totals": group_totals,
        "production_lines": lines,
        "overall_balance": overall_balance
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
    for summary in summaries:
        for mat, rate in summary['resource_totals'].items():
            global_totals[mat] = global_totals.get(mat, 0.0) + rate
        for mat, bal in summary['overall_balance'].items():
            global_balance[mat] = global_balance.get(mat, 0.0) + bal

    return {
        "groups": summaries,
        "global_resource_totals": global_totals,
        "global_balance": global_balance,
    }


# --- Helpers ---

def _collect_factory_specs(chain: ProductionNode) -> list[dict]:
    """
    Walks a production chain and aggregates per-recipe building requirements.

    Recipes that appear in multiple branches of the chain have their building counts
    summed. The returned list is ordered from deepest-dependency first (closest to
    raw materials) to the final target recipe last, so order values match processing
    flow.

    Args:
        chain: A production chain produced by ProductionCalculator.calculate().

    Returns:
        A list of dicts, each containing recipe_id, recipe_name, and num_buildings,
        sorted by processing order (earliest step first).
    """
    specs: dict[int, dict] = {}

    def visit(node: ProductionNode, depth: int) -> None:
        if node.get('is_raw_material'):
            return
        req = node['requirements']
        rid = req['recipe_id']
        if rid in specs:
            specs[rid]['num_buildings'] += req['num_buildings']
            specs[rid]['depth'] = max(specs[rid]['depth'], depth)
        else:
            specs[rid] = {
                'recipe_id': rid,
                'recipe_name': req['recipe_name'],
                'num_buildings': req['num_buildings'],
                'depth': depth,
            }
        for dep in node.get('dependencies', {}).values():
            visit(dep, depth + 1)

    visit(chain, 0)
    return sorted(specs.values(), key=lambda s: -s['depth'])

def _build_factories(session: Session, line: ProductionLine) -> None:
    """
    Runs the production calculator for a line and persists Factory rows for each step.

    Does not commit — the caller owns the transaction boundary.

    Args:
        session: An active SQLAlchemy Session.
        line: The ProductionLine to generate factories for. Must already be persisted
              (i.e. have an id).
    """
    calculator = ProductionCalculator(session)
    chain = calculator.calculate(line.target_item_id, line.target_rate)

    for order, spec in enumerate(_collect_factory_specs(chain), start=1):
        session.add(Factory(
            name=f"{spec['recipe_name']} ({line.name})",
            production_line_id=line.id,
            recipe_id=spec['recipe_id'],
            building_count=math.ceil(spec['num_buildings']),
            clock_speed=100.0,
            order=order,
        ))


# --- Creation ---

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
    purity: Union[str, Purity],
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