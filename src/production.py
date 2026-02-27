from sqlalchemy.orm import Session

from .database import Factory, Group, Item, ProductionLine, ResourceNode
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
    # calls get_group_summary for every group, rolls it all up
    pass

# Creation
def create_production_line(session: Session, group_id: int, name: str, item_id: int, target_rate: float) -> ProductionLine:
    # runs calculator, persists Factory rows, commits
    pass

def add_resource_node(session: Session, production_line_id: int, name: str, item_id: int, purity: str, extraction_rate: int) -> ResourceNode:
    pass

# Modification  
def update_production_line_rate(session: Session, production_line_id: int, new_rate: float):
    # deletes old Factory rows, reruns calculator, persists new ones
    pass

def set_production_line_active(session: Session, production_line_id: int, is_active: bool):
    pass