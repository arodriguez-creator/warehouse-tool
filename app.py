import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")
st.title("Shift Summary")
st.caption("Warehouse pick rate analysis")

uploaded_file = st.file_uploader("Upload your Jasci report", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    median_uph = df["UPH"].median()
    mad = (df["UPH"] - median_uph).abs().median()
    df["Status"] = df["UPH"].apply(
        lambda x: "Outlier" if x > (median_uph + 3 * mad) else "Normal"
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Team members", len(df))
    col2.metric("Total units", f"{df['Total Units'].sum():,}")
    col3.metric("Total lines", f"{df['Total Lines'].sum():,}")
    col4.metric("Total errors", df["Total Errors"].sum())

    st.subheader("Pick rates")
    st.dataframe(
        df[["Team Member", "Hours", "UPH", "Total Units", "Total Lines", "Status"]],
        use_container_width=True
    )

    flagged = df[df["Status"] == "Outlier"]
    if not flagged.empty:
        for _, row in flagged.iterrows():
            st.error(
                f"Outlier detected — {row['Team Member']} | "
                f"UPH of {row['UPH']:,.0f} vs median of {median_uph:,.0f}"
            )
    else:
        st.success("No outliers detected this shift")