import os

import streamlit as st
from dotenv import load_dotenv

from src.database import get_engine, get_session, Item, RecipeIngredient
from src.queries import get_all_items, get_all_groups, get_recipes_for_item
from src.calculator import calculate_chain
from src.production import get_max_output


load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)


def collect_multi_recipe_items(node: dict, out: dict) -> None:
    """Walk the chain; for any non-raw item with >1 recipe candidate, remember options."""
    if node.get('is_raw_material'):
        return
    item_id = node['item_id']
    if item_id not in out:
        candidates = get_recipes_for_item(session, item_id)
        if len(candidates) > 1:
            out[item_id] = {
                "item_name": node['item_name'],
                "candidates": [(r.id, f"{r.name} ({r.building.name})") for r in candidates],
                "current_id": node['recipe']['recipe_id'],
            }
    for dep in node.get('dependencies', {}).values():
        collect_multi_recipe_items(dep, out)


def render_chain(node: dict, depth: int = 0) -> None:
    if node.get('is_raw_material'):
        st.write(f"Raw: **{node['item_name']}** @ {node['required_rate']:.2f}/min")
        return

    req = node['recipe']
    label = (
        f"{req['output']['item_name']} @ {req['output']['rate']:.2f}/min "
        f"- {req['num_buildings_rounded']}x {req['building_name']} "
        f"@ {req['clock_speed']:.1f}% clock ({req['recipe_name']})"
        f" - {req['total_power_mw']:.2f} MW"
    )
    with st.expander(label, expanded=depth == 0):
        if req['inputs']:
            st.caption("Inputs")
            st.dataframe(
                [{"item": i['item_name'], "rate": i['rate']} for i in req['inputs']],
                use_container_width=True,
            )
        if req['byproducts']:
            st.caption("Byproducts")
            st.dataframe(
                [{"item": b['item_name'], "rate": b['rate']} for b in req['byproducts']],
                use_container_width=True,
            )
        for dep in node.get('dependencies', {}).values():
            render_chain(dep, depth + 1)


try:
    st.title("Production Calculator")

    all_items = get_all_items(session)
    items_by_name = {item['name']: item['id'] for item in all_items}
    items_by_id = {item['id']: item['name'] for item in all_items}
    sorted_item_names = sorted(items_by_name.keys())

    tab_forward, tab_reverse, tab_max = st.tabs(
        ["Forward Calculator", "Reverse Calculator", "Max Output"]
    )

    # --- Forward ---
    with tab_forward:
        st.header("Output -> Required Inputs")
        item_name = st.selectbox(
            "Target item:", sorted_item_names, key="fwd_item_name"
        )
        target_rate = st.number_input(
            "Target rate (items/min):", min_value=0.01,
            value=st.session_state.get("fwd_target_rate", 60.0),
            step=10.0, key="fwd_target_rate",
        )

        # Persist per-item recipe overrides across reruns.
        st.session_state.setdefault("fwd_preferred_recipes", {})
        preferred = st.session_state["fwd_preferred_recipes"]

        if st.button("Calculate", key="fwd_calc"):
            st.session_state["fwd_ran"] = True

        if st.session_state.get("fwd_ran"):
            target_id = items_by_name[item_name]
            chain = calculate_chain(session, target_id, target_rate, preferred_recipes=preferred)

            if chain.get('is_raw_material'):
                st.warning(f"{item_name} is a raw material - no recipe to expand.")
            else:
                c1, c2, c3 = st.columns(3)
                total_bldg = sum(v for v in chain['building_summary'].values())
                with c1:
                    st.metric("Buildings (ideal)", f"{total_bldg:.2f}")
                with c2:
                    st.metric("Power", f"{chain['power_mw_total']:.2f} MW")
                with c3:
                    st.metric("Raw types", len(chain['raw_materials']))

                # Alt recipe picker
                multi: dict = {}
                collect_multi_recipe_items(chain, multi)
                if multi:
                    with st.expander(
                        f"Alternate recipes available for {len(multi)} item(s)",
                        expanded=False,
                    ):
                        changed = False
                        for item_id, info in multi.items():
                            labels = [lbl for _, lbl in info['candidates']]
                            ids = [rid for rid, _ in info['candidates']]
                            default_idx = ids.index(info['current_id']) if info['current_id'] in ids else 0
                            sel = st.selectbox(
                                info['item_name'],
                                labels,
                                index=default_idx,
                                key=f"alt_pick_{item_id}",
                            )
                            new_id = ids[labels.index(sel)]
                            if preferred.get(item_id) != new_id:
                                # Only store if not default to keep state minimal
                                if new_id == info['candidates'][0][0] and item_id in preferred:
                                    del preferred[item_id]
                                else:
                                    preferred[item_id] = new_id
                                changed = True
                        if changed:
                            st.rerun()

                st.subheader("Building Summary")
                st.dataframe(
                    [{"building": b, "count (ideal)": round(c, 2)}
                     for b, c in chain['building_summary'].items()],
                    use_container_width=True,
                )

                st.subheader("Raw Materials")
                st.dataframe(
                    [{"material": m, "rate": r}
                     for m, r in chain['raw_materials'].items()],
                    use_container_width=True,
                )

                if chain['byproducts_totals']:
                    st.subheader("Byproducts")
                    st.dataframe(
                        [{"material": m, "rate": r}
                         for m, r in chain['byproducts_totals'].items()],
                        use_container_width=True,
                    )

                st.subheader("Production Chain")
                render_chain(chain)

    # --- Reverse ---
    with tab_reverse:
        st.header("Given these inputs -> max output")
        target_name = st.selectbox(
            "Target item:", sorted_item_names, key="rev_target_name"
        )

        st.caption("Available resources (items/min)")
        st.session_state.setdefault("rev_available", {"Iron Ore": 240.0})

        available = st.session_state["rev_available"]

        # Rendering: show current list with delete buttons, plus an add row
        to_delete = None
        for mat, rate in list(available.items()):
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                st.write(mat)
            with c2:
                new_rate = st.number_input(
                    f"rate_{mat}", min_value=0.0, value=float(rate),
                    step=10.0, key=f"rev_rate_{mat}", label_visibility="collapsed",
                )
                available[mat] = new_rate
            with c3:
                if st.button("Remove", key=f"rev_del_{mat}"):
                    to_delete = mat
        if to_delete:
            del available[to_delete]
            st.rerun()

        add_col1, add_col2, add_col3 = st.columns([3, 2, 1])
        with add_col1:
            new_mat = st.selectbox(
                "Add material",
                [n for n in sorted_item_names if n not in available],
                key="rev_add_pick",
                label_visibility="collapsed",
            )
        with add_col2:
            new_mat_rate = st.number_input(
                "Add rate",
                min_value=0.0, value=60.0, step=10.0,
                key="rev_add_rate",
                label_visibility="collapsed",
            )
        with add_col3:
            if st.button("Add", key="rev_add_btn"):
                if new_mat:
                    available[new_mat] = new_mat_rate
                    st.rerun()

        if st.button("Calculate", key="rev_calc") and available:
            target_id = items_by_name[target_name]
            chain = calculate_chain(session, target_id, 1.0)
            raw = chain['raw_materials']

            if chain.get('is_raw_material'):
                st.warning(f"{target_name} is a raw material.")
            elif not raw:
                st.info("This recipe has no raw-material dependencies; output is unconstrained.")
            else:
                missing = [r for r in raw if r not in available]
                if missing:
                    st.error(
                        f"Your inputs don't include: {', '.join(missing)}. "
                        "Add these to compute an output."
                    )
                else:
                    ratios = {r: available[r] / raw[r] for r in raw}
                    bottleneck = min(ratios, key=ratios.get)
                    max_rate = ratios[bottleneck]
                    st.success(
                        f"You can produce **{max_rate:.2f} {target_name}/min** "
                        f"(limited by {bottleneck})."
                    )

                    leftovers = {mat: avail - max_rate * raw.get(mat, 0)
                                 for mat, avail in available.items()}
                    st.subheader("Leftovers")
                    st.dataframe(
                        [{"material": m, "leftover": v} for m, v in leftovers.items()],
                        use_container_width=True,
                    )

                    st.subheader("What would unlock more")
                    deficits = {
                        r: (max_rate * raw[r]) - available[r]
                        for r in raw if r != bottleneck
                    }
                    unlock = {r: max(0, -d) for r, d in deficits.items() if d < 0}
                    if unlock:
                        st.dataframe(
                            [{"material": m, "additional /min": v} for m, v in unlock.items()],
                            use_container_width=True,
                        )
                    else:
                        st.write("Increase the bottleneck material to scale linearly.")

    # --- Max output ---
    with tab_max:
        st.header("Max Output Given a Group's Resources")
        groups = get_all_groups(session)
        if not groups:
            st.info("No groups available. Create a group and add resource nodes first.")
        else:
            groups_by_name = {g['name']: g['id'] for g in groups}
            group_name = st.selectbox("Group:", list(groups_by_name.keys()), key="max_group")
            max_item_name = st.selectbox(
                "Target item:", sorted_item_names, key="max_item"
            )

            if st.button("Calculate", key="max_calc"):
                result = get_max_output(
                    session, groups_by_name[group_name], items_by_name[max_item_name]
                )
                if result['max_rate'] == 0.0:
                    st.warning(
                        f"Missing raw materials in {group_name}: "
                        f"{', '.join(result['missing'])}."
                    )
                elif result['max_rate'] == float('inf'):
                    st.info(
                        f"{max_item_name} has no raw-material requirements; "
                        "output is unconstrained."
                    )
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.metric("Max output (items/min)", f"{result['max_rate']:.2f}")
                    with c2:
                        st.metric("Bottleneck", result['bottleneck'])

finally:
    session.close()
