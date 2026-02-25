from sqlalchemy.orm import Session

from .database import Factory, Group, Item, ProductionLine, ResourceNode
from .queries import get_resource_nodes_for_group, get_production_line, get_all_groups
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
            return 0.0
        result.append(group_totals[resource] / node['raw_materials'][resource])
    
    return min(result)

def get_resource_balance(session: Session, production_line_id: int) -> dict:
    # compares what resource nodes supply vs what the production line consumes
    # returns surplus/deficit per raw material
    pass

def get_group_summary(session: Session, group_id: int) -> dict:
    # aggregates resource totals, all production line summaries, overall balance
    pass

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