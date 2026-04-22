import os

import streamlit as st
from dotenv import load_dotenv

from src.database import get_engine, get_session
from src.production import get_global_summary


load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

try:
    summary = get_global_summary(session)

    st.title("Satisfactory Factory Dashboard")

    # Top third — global stats
    st.header("Global Overview")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Groups", len(summary['groups']))
    with col2:
        total_lines = sum(len(g['production_lines']) for g in summary['groups'])
        st.metric("Production Lines", total_lines)
    with col3:
        total_materials = len(summary['global_resource_totals'])
        st.metric("Raw Materials", total_materials)

    st.subheader("Global Resource Totals (items/min)")
    if summary['global_resource_totals']:
        st.dataframe(
            [
                {"material": mat, "extraction_rate": rate}
                for mat, rate in summary['global_resource_totals'].items()
            ],
            use_container_width=True,
        )
    else:
        st.write("No resource nodes have been added yet.")

    st.subheader("Global Balance (surplus / deficit per material)")
    if summary['global_balance']:
        st.dataframe(
            [
                {"material": mat, "balance": bal}
                for mat, bal in summary['global_balance'].items()
            ],
            use_container_width=True,
        )
    else:
        st.write("Nothing to balance yet.")

    # Bottom two thirds — group viewer
    st.header("Groups")

    if not summary['groups']:
        st.info("No groups yet. Create a group and add production lines to see them here.")
    else:
        tabs = st.tabs([g['name'] for g in summary['groups']])
        for tab, group in zip(tabs, summary['groups']):
            with tab:
                st.subheader(f"{group['name']} - Resource Totals")
                if group['resource_totals']:
                    st.dataframe(
                        [
                            {"material": mat, "extraction_rate": rate}
                            for mat, rate in group['resource_totals'].items()
                        ],
                        use_container_width=True,
                    )
                else:
                    st.write("No resource nodes in this group.")

                st.subheader("Production Lines")
                if not group['production_lines']:
                    st.write("No production lines in this group.")
                for line in group['production_lines']:
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

                st.subheader("Overall Balance")
                if group['overall_balance']:
                    st.dataframe(
                        [
                            {"material": mat, "balance": bal}
                            for mat, bal in group['overall_balance'].items()
                        ],
                        use_container_width=True,
                    )
                else:
                    st.write("No materials tracked in this group yet.")

finally:
    session.close()
