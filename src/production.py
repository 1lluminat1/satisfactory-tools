from sqlalchemy.orm import Session

from .database import Factory, Group, Item, ProductionLine, ResourceNode
from .queries import get_resource_nodes_for_group, get_production_line, get_all_groups
from .calculator import ProductionCalculator
from .types import ProductionNode


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

def get_max_output(session, group_id, item_id) -> float:
    # uses get_group_resource_totals + ProductionCalculator at rate=1
    # to find the bottleneck raw material and back-calculate max rate
    pass

def get_resource_balance(session, production_line_id) -> dict:
    # compares what resource nodes supply vs what the production line consumes
    # returns surplus/deficit per raw material
    pass

def get_group_summary(session, group_id) -> dict:
    # aggregates resource totals, all production line summaries, overall balance
    pass

def get_global_summary(session) -> dict:
    # calls get_group_summary for every group, rolls it all up
    pass

# Creation
def create_production_line(session, group_id, name, item_id, target_rate) -> ProductionLine:
    # runs calculator, persists Factory rows, commits
    pass

def add_resource_node(session, production_line_id, name, item_id, purity, extraction_rate) -> ResourceNode:
    pass

# Modification  
def update_production_line_rate(session, production_line_id, new_rate):
    # deletes old Factory rows, reruns calculator, persists new ones
    pass

def set_production_line_active(session, production_line_id, is_active):
    pass