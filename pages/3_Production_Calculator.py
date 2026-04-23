import os

import streamlit as st
from dotenv import load_dotenv

from src.database import get_engine, get_session
from src.queries import get_all_items, get_all_groups
from src.calculator import ProductionCalculator
from src.production import get_max_output


load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)


def render_chain(node: dict, depth: int = 0) -> None:
    """Recursively render a production chain node as nested expanders."""
    if node.get('is_raw_material'):
        st.write(f"Raw material: **{node['item_name']}** @ {node['required_rate']:.2f}/min")
        return

    req = node['requirements']
    label = (
        f"{req['output']['item_name']} @ {req['output']['rate']:.2f}/min "
        f"- {req['num_buildings']:.2f}x {req['building_name']} ({req['recipe_name']})"
    )
    with st.expander(label, expanded=depth == 0):
        if req['inputs']:
            st.caption("Inputs")
            st.dataframe(
                [
                    {"item": inp['item_name'], "rate": inp['rate']}
                    for inp in req['inputs']
                ],
                use_container_width=True,
            )
        if req['byproducts']:
            st.caption("Byproducts")
            st.dataframe(
                [
                    {"item": bp['item_name'], "rate": bp['rate']}
                    for bp in req['byproducts']
                ],
                use_container_width=True,
            )
        for dep in node.get('dependencies', {}).values():
            render_chain(dep, depth + 1)


try:
    st.title("Production Calculator")

    all_items = get_all_items(session)
    items_by_name = {item['name']: item['id'] for item in all_items}

    tab_forward, tab_max = st.tabs(["Forward Calculator", "Max Output"])

    with tab_forward:
        st.header("Output -> Required Inputs")
        item_name = st.selectbox("Target item:", sorted(items_by_name.keys()), key="fwd_item")
        target_rate = st.number_input("Target rate (items/min):", min_value=0.01, value=60.0, step=10.0, key="fwd_rate")

        if st.button("Calculate", key="fwd_calc"):
            calculator = ProductionCalculator(session)
            chain = calculator.calculate(items_by_name[item_name], target_rate)

            if chain.get('is_raw_material'):
                st.warning(f"{item_name} is a raw material - it has no recipe to calculate.")
            else:
                st.subheader("Building Summary")
                st.dataframe(
                    [
                        {"building": b, "count": c}
                        for b, c in chain['building_summary'].items()
                    ],
                    use_container_width=True,
                )

                st.subheader("Raw Materials")
                st.dataframe(
                    [
                        {"material": m, "rate": r}
                        for m, r in chain['raw_materials'].items()
                    ],
                    use_container_width=True,
                )

                st.subheader("Production Chain")
                render_chain(chain)

    with tab_max:
        st.header("Max Output Given a Group's Resources")
        groups = get_all_groups(session)
        if not groups:
            st.info("No groups available. Create a group and add resource nodes first.")
        else:
            groups_by_name = {g['name']: g['id'] for g in groups}
            group_name = st.selectbox("Group:", list(groups_by_name.keys()), key="max_group")
            max_item_name = st.selectbox("Target item:", sorted(items_by_name.keys()), key="max_item")

            if st.button("Calculate", key="max_calc"):
                max_rate = get_max_output(
                    session, groups_by_name[group_name], items_by_name[max_item_name]
                )
                if max_rate == 0.0:
                    st.warning(
                        f"{group_name} is missing one or more raw materials required to produce {max_item_name}."
                    )
                else:
                    st.metric("Max output (items/min)", f"{max_rate:.2f}")

finally:
    session.close()
