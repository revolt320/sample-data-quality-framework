import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide")
st.title("Sample Data Quality Framework")

# =========================================================
# Sidebar Upload
# =========================================================

st.sidebar.header("Dataset Configuration")
uploaded_file = st.sidebar.file_uploader("Upload CSV Dataset", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.session_state["dataset"] = df
else:
    df = None

# =========================================================
# Tabs
# =========================================================

tab1, tab2 = st.tabs(["Dataset Preview", "Data Quality Checks"])

# =========================================================
# TAB 1 → DATASET PREVIEW
# =========================================================

with tab1:

    if df is None:
        st.info("Please upload a dataset from the sidebar.")
    else:
        st.subheader("Dataset Preview")
        st.dataframe(df.head())

        st.subheader("Column Data Types")

        dtype_df = pd.DataFrame({
            "Column Name": df.columns,
            "Detected Data Type": df.dtypes.astype(str)
        })

        st.dataframe(dtype_df)


# =========================================================
# TAB 2 → DATA QUALITY CHECKS
# =========================================================

with tab2:

    if df is None:
        st.warning("Please upload dataset first.")
        st.stop()

    # Initialize Rule Registry
    if "rule_registry" not in st.session_state:
        st.session_state.rule_registry = {
            col: {
                "type": "string",
                "allow_null": False,
                "allow_duplicates": True,
                "regex": "",
                "max_length": None,
                "custom_condition": ""
            }
            for col in df.columns
        }

    # =========================================================
    # Rule Editor Popup
    # =========================================================

    def open_rule_editor(column):

        rule_data = st.session_state.rule_registry[column]

        @st.dialog(f"Edit Rule for {column}")
        def rule_modal():

            rule_type = st.selectbox(
                "Type",
                ["string", "number", "datetime"],
                index=["string", "number", "datetime"].index(rule_data["type"])
            )

            allow_null = st.checkbox("Allow Null", value=rule_data["allow_null"])
            allow_duplicates = st.checkbox("Allow Duplicates", value=rule_data["allow_duplicates"])

            regex = st.text_input("Regex (Optional)", value=rule_data["regex"])

            max_length = st.number_input(
                "Max Length (0 = no limit)",
                min_value=0,
                value=0 if rule_data["max_length"] is None else rule_data["max_length"]
            )

            st.markdown("### Cross Column Rule (Optional)")
            custom_condition = st.text_input(
                "Pandas Query Condition",
                value=rule_data["custom_condition"],
                help="Example: ceded_loss <= gross_loss"
            )

            colA, colB = st.columns(2)

            with colA:
                if st.button("Save"):
                    st.session_state.rule_registry[column] = {
                        "type": rule_type,
                        "allow_null": allow_null,
                        "allow_duplicates": allow_duplicates,
                        "regex": regex,
                        "max_length": None if max_length == 0 else max_length,
                        "custom_condition": custom_condition
                    }
                    st.success("Rule Saved")
                    st.rerun()

            with colB:
                if st.button("Close"):
                    st.rerun()

        rule_modal()

    # =========================================================
    # Field Table
    # =========================================================

    st.subheader("Fields")

    for col in df.columns:

        col1, col2, col3, col4 = st.columns([3, 3, 2, 2])

        with col1:
            st.write(f"**{col}**")

        with col2:
            sample_value = (
                df[col].dropna().iloc[0]
                if not df[col].dropna().empty else "NULL"
            )
            st.write(sample_value)

        with col3:
            st.write(st.session_state.rule_registry[col]["type"])

        with col4:
            if st.button("Edit/View", key=f"edit_{col}"):
                open_rule_editor(col)

    # =========================================================
    # Run Validation
    # =========================================================

    st.divider()

    if st.button("Run Data Quality Checks"):

        issues = []
        total_rows = len(df)

        for col, rules in st.session_state.rule_registry.items():

            # Duplicate Check
            if not rules["allow_duplicates"]:
                duplicates = df[df.duplicated(col, keep=False)]
                for _ in duplicates.index:
                    issues.append({
                        "column": col,
                        "issue": "Duplicate value found"
                    })

            for _, value in df[col].items():

                # Null Check
                if not rules["allow_null"] and pd.isnull(value):
                    issues.append({
                        "column": col,
                        "issue": "Null value not allowed"
                    })
                    continue

                # Type Check
                if rules["type"] == "number":
                    try:
                        float(value)
                    except:
                        issues.append({
                            "column": col,
                            "issue": "Expected numeric value"
                        })

                if rules["type"] == "datetime":
                    try:
                        pd.to_datetime(value)
                    except:
                        issues.append({
                            "column": col,
                            "issue": "Invalid datetime format"
                        })

                # Regex
                if rules["regex"]:
                    if not re.match(rules["regex"], str(value)):
                        issues.append({
                            "column": col,
                            "issue": "Regex validation failed"
                        })

                # Max Length
                if rules["max_length"]:
                    if len(str(value)) > rules["max_length"]:
                        issues.append({
                            "column": col,
                            "issue": "Max length exceeded"
                        })

            # Cross Column Rule
            if rules["custom_condition"]:
                try:
                    failed = df.query(f"not ({rules['custom_condition']})")
                    for _ in failed.index:
                        issues.append({
                            "column": col,
                            "issue": f"Custom rule failed: {rules['custom_condition']}"
                        })
                except:
                    issues.append({
                        "column": col,
                        "issue": "Rule syntax error"
                    })

        # =========================================================
        # Aggregated Issue Summary
        # =========================================================

        st.subheader("Issue Summary")

        if not issues:
            st.success("No Issues Found")
        else:
            issues_df = pd.DataFrame(issues)

            summary = (
                issues_df
                .groupby(["column", "issue"])
                .size()
                .reset_index(name="failure_count")
            )

            summary["failure_percentage"] = round(
                (summary["failure_count"] / total_rows) * 100, 2
            )

            summary = summary.sort_values(
                "failure_percentage",
                ascending=False
            )

            st.error(f"{len(summary)} unique issue types detected")
            st.dataframe(summary)

            st.download_button(
                "Download Issue Summary",
                summary.to_csv(index=False),
                file_name="dq_issue_summary.csv",
                mime="text/csv"
            )
