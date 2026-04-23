import os

import streamlit as st
from dotenv import load_dotenv

from src.database import get_engine, get_session, Purity
from src.queries import (
    get_all_groups,
    get_all_items,
    get_resource_nodes_for_group,
)
from src.production import (
    add_resource_node,
    create_group,
    create_production_line,
    get_global_summary,
    get_group_summary,
    set_production_line_active,
    update_production_line_rate,
)


load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

try:
    st.set_page_config(page_title="Satisfactory Dashboard", layout="wide")

    groups = get_all_groups(session)
    all_items = get_all_items(session)
    items_by_name = {item['name']: item['id'] for item in all_items}
    sorted_item_names = sorted(items_by_name.keys())

    # --- Modals ---

    @st.dialog("Create Group")
    def create_group_dialog() -> None:
        name = st.text_input("Name")
        description = st.text_area("Description", "")
        if st.button("Create", key="create_group_submit"):
            if not name.strip():
                st.error("Name is required.")
            else:
                create_group(session, name.strip(), description.strip())
                st.rerun()

    @st.dialog("Add Production Line")
    def add_line_dialog(group_id: int) -> None:
        name = st.text_input("Name")
        item_name = st.selectbox("Target item:", sorted_item_names)
        target_rate = st.number_input(
            "Target rate (items/min)", min_value=0.01, value=60.0, step=10.0
        )
        if st.button("Create", key="add_line_submit"):
            if not name.strip():
                st.error("Name is required.")
            else:
                create_production_line(
                    session,
                    group_id,
                    name.strip(),
                    items_by_name[item_name],
                    target_rate,
                )
                st.rerun()

    @st.dialog("Add Resource Node")
    def add_node_dialog(group_id: int) -> None:
        name = st.text_input("Name")
        item_name = st.selectbox("Item:", sorted_item_names)
        purity = st.selectbox("Purity:", [p.name for p in Purity])
        rate = st.number_input(
            "Extraction rate (items/min)", min_value=0.01, value=60.0, step=10.0
        )
        if st.button("Add", key="add_node_submit"):
            if not name.strip():
                st.error("Name is required.")
            else:
                add_resource_node(
                    session,
                    group_id,
                    name.strip(),
                    items_by_name[item_name],
                    purity,
                    rate,
                )
                st.rerun()

    # --- Sidebar: group picker ---

    with st.sidebar:
        st.header("Groups")
        if groups:
            group_names = [g['name'] for g in groups]
            selected_name = st.radio(
                "Select a group:", group_names, key="selected_group_name"
            )
            selected_group_id = next(g['id'] for g in groups if g['name'] == selected_name)
        else:
            st.write("No groups yet.")
            selected_group_id = None

        if st.button("+ New Group", use_container_width=True):
            create_group_dialog()

    # --- Main: title + global overview ---

    st.title("Satisfactory Factory Dashboard")

    summary = get_global_summary(session)

    st.header("Global Overview")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Groups", len(summary['groups']))
    with col2:
        st.metric(
            "Production Lines",
            sum(len(g['production_lines']) for g in summary['groups']),
        )
    with col3:
        st.metric("Raw Materials", len(summary['global_resource_totals']))

    totals_col, balance_col = st.columns(2)
    with totals_col:
        st.subheader("Global Resource Totals")
        if summary['global_resource_totals']:
            st.dataframe(
                [
                    {"material": m, "rate": r}
                    for m, r in summary['global_resource_totals'].items()
                ],
                use_container_width=True,
            )
        else:
            st.write("None.")
    with balance_col:
        st.subheader("Global Balance")
        if summary['global_balance']:
            st.dataframe(
                [
                    {"material": m, "balance": b}
                    for m, b in summary['global_balance'].items()
                ],
                use_container_width=True,
            )
        else:
            st.write("None.")

    # --- Main: selected group area ---

    st.header("Group Details")

    if selected_group_id is None:
        st.info("Select a group in the sidebar, or create one with + New Group.")
    else:
        group_summary = get_group_summary(session, selected_group_id)
        st.subheader(group_summary['name'])

        action_cols = st.columns(2)
        with action_cols[0]:
            if st.button("+ Add Production Line", use_container_width=True):
                add_line_dialog(selected_group_id)
        with action_cols[1]:
            if st.button("+ Add Resource Node", use_container_width=True):
                add_node_dialog(selected_group_id)

        totals_col, overall_col = st.columns(2)
        with totals_col:
            st.markdown("**Resource Totals**")
            if group_summary['resource_totals']:
                st.dataframe(
                    [
                        {"material": m, "rate": r}
                        for m, r in group_summary['resource_totals'].items()
                    ],
                    use_container_width=True,
                )
            else:
                st.write("No resource nodes.")
        with overall_col:
            st.markdown("**Overall Balance**")
            if group_summary['overall_balance']:
                st.dataframe(
                    [
                        {"material": m, "balance": b}
                        for m, b in group_summary['overall_balance'].items()
                    ],
                    use_container_width=True,
                )
            else:
                st.write("Nothing to balance yet.")

        st.markdown("**Production Lines**")
        if not group_summary['production_lines']:
            st.write("No production lines in this group.")
        for line in group_summary['production_lines']:
            details = line['details']
            header = (
                f"{details['name']} - {details['target_item_name']} "
                f"@ {details['target_rate']}/min"
                + ("" if details['is_active'] else " (inactive)")
            )
            with st.expander(header):
                if line['balance']:
                    st.dataframe(
                        [
                            {
                                "material": mat,
                                "required": entry['required'],
                                "available": entry['available'],
                                "balance": entry['balance'],
                            }
                            for mat, entry in line['balance'].items()
                        ],
                        use_container_width=True,
                    )
                else:
                    st.write("No raw material requirements.")

                edit_rate_col, edit_active_col = st.columns(2)
                with edit_rate_col:
                    new_rate = st.number_input(
                        "New rate (items/min)",
                        min_value=0.01,
                        value=float(details['target_rate']),
                        step=10.0,
                        key=f"rate_{details['id']}",
                    )
                    if st.button("Update rate", key=f"update_rate_{details['id']}"):
                        update_production_line_rate(session, details['id'], new_rate)
                        st.rerun()
                with edit_active_col:
                    new_active = st.checkbox(
                        "Active",
                        value=details['is_active'],
                        key=f"active_{details['id']}",
                    )
                    if st.button("Apply active state", key=f"apply_active_{details['id']}"):
                        set_production_line_active(session, details['id'], new_active)
                        st.rerun()

        st.markdown("**Resource Nodes**")
        nodes = get_resource_nodes_for_group(session, selected_group_id)
        if nodes:
            st.dataframe(
                [
                    {
                        "id": n['id'],
                        "name": n['name'],
                        "item": n['item_name'],
                        "purity": n['purity'].name,
                        "extraction_rate": n['extraction_rate'],
                    }
                    for n in nodes
                ],
                use_container_width=True,
            )
        else:
            st.write("No resource nodes in this group.")

finally:
    session.close()
