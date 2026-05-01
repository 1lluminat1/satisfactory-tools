import json
import os

import streamlit as st
from dotenv import load_dotenv

from src.cache import cached_all_items, ensure_db_ready
from src.database import get_engine, get_session, Purity
from src.game_constants import MINER_TIERS, default_extraction_rate, minimum_belt_tier
from src.queries import (
    get_all_groups,
    get_factories_for_production_line,
    get_resource_nodes_for_group,
)
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
    import_factory_state,
    rename_group,
    rename_production_line,
    set_production_line_active,
    update_production_line_rate,
    update_resource_node,
)


load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))

st.set_page_config(page_title="Satisfactory Dashboard", page_icon="🏭", layout="wide")
ensure_db_ready(engine)

session = get_session(engine)


def _balance_emoji(balance: float) -> str:
    if balance >= 0:
        return "OK"
    return "WARN"


try:
    groups = get_all_groups(session)
    all_items = cached_all_items(session)
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

    @st.dialog("Edit Group")
    def edit_group_dialog(group_id: int, group_name: str, group_description: str) -> None:
        new_name = st.text_input("Name", value=group_name)
        new_description = st.text_area("Description", value=group_description)
        save, cancel = st.columns(2)
        with save:
            if st.button("Save", key=f"edit_group_save_{group_id}", use_container_width=True):
                if not new_name.strip():
                    st.error("Name is required.")
                else:
                    rename_group(session, group_id, new_name.strip(), new_description.strip())
                    st.rerun()
        with cancel:
            if st.button("Cancel", key=f"edit_group_cancel_{group_id}", use_container_width=True):
                st.rerun()

        st.divider()
        confirm = st.checkbox(
            f"I understand this deletes the group and all its production lines and resource nodes.",
            key=f"delete_group_confirm_{group_id}",
        )
        if st.button(
            "Delete group",
            key=f"delete_group_btn_{group_id}",
            disabled=not confirm,
            type="primary",
        ):
            delete_group(session, group_id)
            if "selected_group_name" in st.session_state and st.session_state["selected_group_name"] == group_name:
                del st.session_state["selected_group_name"]
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
                    session, group_id, name.strip(),
                    items_by_name[item_name], target_rate,
                )
                st.rerun()

    @st.dialog("Edit Production Line")
    def edit_line_dialog(line_details: dict) -> None:
        line_id = line_details['id']
        new_name = st.text_input("Name", value=line_details['name'])
        new_rate = st.number_input(
            "Target rate (items/min)",
            min_value=0.01,
            value=float(line_details['target_rate']),
            step=10.0,
        )
        new_active = st.checkbox("Active", value=line_details['is_active'])
        save, cancel = st.columns(2)
        with save:
            if st.button("Save", key=f"edit_line_save_{line_id}", use_container_width=True):
                if not new_name.strip():
                    st.error("Name is required.")
                else:
                    if new_name.strip() != line_details['name']:
                        rename_production_line(session, line_id, new_name.strip())
                    if new_rate != line_details['target_rate']:
                        update_production_line_rate(session, line_id, new_rate)
                    if new_active != line_details['is_active']:
                        set_production_line_active(session, line_id, new_active)
                    st.rerun()
        with cancel:
            if st.button("Cancel", key=f"edit_line_cancel_{line_id}", use_container_width=True):
                st.rerun()

        st.divider()
        confirm = st.checkbox(
            "Confirm delete (also removes associated factory rows)",
            key=f"delete_line_confirm_{line_id}",
        )
        if st.button(
            "Delete line",
            key=f"delete_line_btn_{line_id}",
            disabled=not confirm,
            type="primary",
        ):
            delete_production_line(session, line_id)
            st.rerun()

    @st.dialog("Add Resource Node")
    def add_node_dialog(group_id: int) -> None:
        name = st.text_input("Name")
        item_name = st.selectbox("Item:", sorted_item_names)
        purity = st.selectbox("Purity:", [p.name for p in Purity])
        miner_tier = st.selectbox(
            "Miner tier (for auto-fill)",
            ["custom", *MINER_TIERS.keys()],
            index=2,
        )
        if miner_tier in MINER_TIERS:
            suggested = default_extraction_rate(miner_tier, purity)
            st.caption(f"Auto rate: {suggested:.1f}/min ({miner_tier} on {purity} node)")
        else:
            suggested = 60.0
        rate = st.number_input(
            "Extraction rate (items/min)", min_value=0.01, value=float(suggested), step=10.0
        )
        if st.button("Add", key="add_node_submit"):
            if not name.strip():
                st.error("Name is required.")
            else:
                add_resource_node(
                    session, group_id, name.strip(),
                    items_by_name[item_name], purity, rate,
                )
                st.rerun()

    @st.dialog("Edit Resource Node")
    def edit_node_dialog(node: dict) -> None:
        node_id = node['id']
        new_name = st.text_input("Name", value=node['name'])
        new_purity = st.selectbox(
            "Purity:", [p.name for p in Purity],
            index=[p.name for p in Purity].index(node['purity']),
        )
        new_rate = st.number_input(
            "Extraction rate (items/min)",
            min_value=0.01,
            value=float(node['extraction_rate']),
            step=10.0,
        )
        save, cancel = st.columns(2)
        with save:
            if st.button("Save", key=f"edit_node_save_{node_id}", use_container_width=True):
                if not new_name.strip():
                    st.error("Name is required.")
                else:
                    update_resource_node(
                        session, node_id,
                        name=new_name.strip(),
                        purity=new_purity,
                        extraction_rate=new_rate,
                    )
                    st.rerun()
        with cancel:
            if st.button("Cancel", key=f"edit_node_cancel_{node_id}", use_container_width=True):
                st.rerun()

        st.divider()
        confirm = st.checkbox("Confirm delete", key=f"delete_node_confirm_{node_id}")
        if st.button(
            "Delete node",
            key=f"delete_node_btn_{node_id}",
            disabled=not confirm,
            type="primary",
        ):
            delete_resource_node(session, node_id)
            st.rerun()

    # --- Sidebar: search + group picker + new group ---

    with st.sidebar:
        st.header("Groups")
        group_search = st.text_input("Search groups", key="group_search").strip().lower()
        filtered_groups = [
            g for g in groups if not group_search or group_search in g['name'].lower()
        ]

        selected_group_id = None
        if filtered_groups:
            group_names = [g['name'] for g in filtered_groups]
            selected_name = st.radio(
                "Select a group:",
                group_names,
                key="selected_group_name",
            )
            selected = next((g for g in filtered_groups if g['name'] == selected_name), None)
            selected_group_id = selected['id'] if selected else None

            if selected:
                if st.button(
                    "Edit selected group",
                    key="edit_group_btn",
                    use_container_width=True,
                ):
                    edit_group_dialog(
                        selected['id'], selected['name'], selected['description'] or ""
                    )
        elif group_search:
            st.write("No matches.")
        else:
            st.write("No groups yet.")

        if st.button("+ New Group", use_container_width=True):
            create_group_dialog()

        if not groups:
            if st.button("Load demo data", use_container_width=True):
                created = create_starter_data(session)
                if created:
                    st.success(f"Seeded {created.name}.")
                    st.rerun()
                else:
                    st.warning("Could not seed starter data.")

        st.divider()
        st.markdown("**Import / Export**")
        export_bytes = json.dumps(
            export_factory_state(session), indent=2
        ).encode("utf-8")
        st.download_button(
            "Export factory (.json)",
            export_bytes,
            file_name="satisfactory_factory.json",
            mime="application/json",
            use_container_width=True,
        )
        uploaded = st.file_uploader("Import factory (.json)", type=["json"])
        if uploaded is not None:
            try:
                imported_data = json.loads(uploaded.getvalue().decode("utf-8"))
                result = import_factory_state(session, imported_data)
                st.success(
                    f"Imported: {result['groups']} groups, "
                    f"{result['lines']} lines, {result['nodes']} nodes."
                )
                if result['skipped_items']:
                    st.warning(
                        f"Skipped {len(result['skipped_items'])} item(s) "
                        "not present in the database."
                    )
                st.rerun()
            except (json.JSONDecodeError, KeyError) as exc:
                st.error(f"Could not parse file: {exc}")

    # --- Main: title + global overview ---

    st.title("Satisfactory Factory Dashboard")

    summary = get_global_summary(session)

    st.header("Global Overview")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Groups", len(summary['groups']))
    with m2:
        st.metric(
            "Production Lines",
            sum(len(g['production_lines']) for g in summary['groups']),
        )
    with m3:
        st.metric("Buildings (active)", summary['total_buildings'])
    with m4:
        st.metric("Power (active)", f"{summary['total_power_mw']:.1f} MW")
    with m5:
        st.metric("Raw Materials", len(summary['global_resource_totals']))

    totals_col, balance_col = st.columns(2)
    with totals_col:
        st.subheader("Global Resource Totals")
        if summary['global_resource_totals']:
            st.dataframe(
                [{"material": m, "rate": r}
                 for m, r in summary['global_resource_totals'].items()],
                use_container_width=True,
            )
        else:
            st.write("None.")
    with balance_col:
        st.subheader("Global Balance")
        if summary['global_balance']:
            st.dataframe(
                [{"status": _balance_emoji(b), "material": m, "balance": b}
                 for m, b in summary['global_balance'].items()],
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

        gm1, gm2, gm3 = st.columns(3)
        with gm1:
            st.metric("Buildings", group_summary['total_buildings'])
        with gm2:
            st.metric("Power", f"{group_summary['total_power_mw']:.1f} MW")
        with gm3:
            st.metric("Production Lines", len(group_summary['production_lines']))

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
                    [{"material": m, "rate": r}
                     for m, r in group_summary['resource_totals'].items()],
                    use_container_width=True,
                )
            else:
                st.write("No resource nodes.")
        with overall_col:
            st.markdown("**Overall Balance**")
            if group_summary['overall_balance']:
                st.dataframe(
                    [{"status": _balance_emoji(b), "material": m, "balance": b}
                     for m, b in group_summary['overall_balance'].items()],
                    use_container_width=True,
                )
            else:
                st.write("Nothing to balance yet.")

        st.markdown("**Production Lines**")
        if not group_summary['production_lines']:
            st.write("No production lines in this group.")
        for line in group_summary['production_lines']:
            details = line['details']
            bottleneck_txt = (
                f" - bottleneck: {line['bottleneck']}" if line.get('bottleneck') else ""
            )
            header = (
                f"{details['name']} - {details['target_item_name']} "
                f"@ {details['target_rate']}/min "
                f"({line['building_count']} bldgs, {line['power_mw']:.1f} MW)"
                + bottleneck_txt
                + ("" if details['is_active'] else " [INACTIVE]")
            )
            with st.expander(header):
                factories = get_factories_for_production_line(session, details['id'])
                if factories:
                    st.markdown("*Factories*")
                    # approximate per-building output rate using this line's target rate
                    st.dataframe(
                        [
                            {
                                "order": f['order'],
                                "recipe": f['recipe_name'],
                                "building": f['building_name'],
                                "count": f['building_count'],
                                "clock %": round(f['clock_speed'], 1),
                            }
                            for f in factories
                        ],
                        use_container_width=True,
                    )
                    belt_needed = minimum_belt_tier(details['target_rate'])
                    if belt_needed is None:
                        st.warning(
                            f"Line output {details['target_rate']:.1f}/min exceeds Mk6 belts - "
                            "you'll need to split the flow."
                        )
                    elif belt_needed in ("Mk4", "Mk5", "Mk6"):
                        st.caption(f"Belt tier needed at line output: {belt_needed}")

                st.markdown("*Raw material balance*")
                if line['balance']:
                    st.dataframe(
                        [
                            {
                                "status": _balance_emoji(entry['balance']),
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

                if st.button("Edit / delete", key=f"edit_line_open_{details['id']}"):
                    edit_line_dialog(details)

        st.markdown("**Resource Nodes**")
        nodes = get_resource_nodes_for_group(session, selected_group_id)
        if nodes:
            st.dataframe(
                [
                    {
                        "id": n['id'],
                        "name": n['name'],
                        "item": n['item_name'],
                        "purity": n['purity'],
                        "extraction_rate": n['extraction_rate'],
                    }
                    for n in nodes
                ],
                use_container_width=True,
            )

            node_labels = {f"{n['name']} ({n['item_name']})": n for n in nodes}
            col_pick, col_edit = st.columns([3, 1])
            with col_pick:
                picked_label = st.selectbox(
                    "Node to edit:",
                    list(node_labels.keys()),
                    key="node_edit_pick",
                )
            with col_edit:
                st.write("")  # align
                if st.button("Edit node", use_container_width=True):
                    edit_node_dialog(node_labels[picked_label])
        else:
            st.write("No resource nodes in this group.")

finally:
    session.close()
