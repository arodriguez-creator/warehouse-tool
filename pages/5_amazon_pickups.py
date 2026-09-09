import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import zoneinfo
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from styles import GLOBAL_CSS, page_header
from auth import require_auth, show_user, get_db

require_auth()
show_user()

st.set_page_config(layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
page_header("Amazon pickups", "Live from Supabase — SAKAR Amazon Pick ups")

pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
today = datetime.now(pacific).date()
tomorrow = today + timedelta(days=1)

def clean(val):
    return "" if not val or str(val) == "nan" or val is None else str(val).strip()

@st.cache_data(ttl=60)
def load_pending():
    db = get_db()
    result = db.table("amazon_pickups")\
        .select("*")\
        .eq("picked_up", False)\
        .order("pickup_date", desc=False)\
        .execute()
    df = pd.DataFrame(result.data)
    if not df.empty:
        df["pickup_date"] = pd.to_datetime(df["pickup_date"], errors="coerce").dt.tz_localize(None)
    return df

@st.cache_data(ttl=60)
def load_view(date_filter, carrier_filter):
    db = get_db()
    query = db.table("amazon_pickups").select("*")
    if date_filter == "today":
        query = query.eq("pickup_date", today.strftime("%Y-%m-%d"))
    elif date_filter == "tomorrow":
        query = query.eq("pickup_date", tomorrow.strftime("%Y-%m-%d"))
    elif date_filter == "pending":
        query = query.eq("picked_up", False)
    elif date_filter == "last30":
        cutoff = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        query = query.gte("pickup_date", cutoff)
    if carrier_filter and carrier_filter != "All":
        query = query.eq("carrier", carrier_filter)
    result = query.order("pickup_date", desc=True).execute()
    df = pd.DataFrame(result.data)
    if not df.empty:
        df["pickup_date"] = pd.to_datetime(df["pickup_date"], errors="coerce").dt.tz_localize(None)
    return df

pending_df = load_pending()
today_df = pending_df[pending_df["pickup_date"].dt.date == today] if not pending_df.empty else pd.DataFrame()
tomorrow_df = pending_df[pending_df["pickup_date"].dt.date == tomorrow] if not pending_df.empty else pd.DataFrame()

# --- sidebar for detail edits only ---
with st.sidebar:
    st.subheader("Edit order details")
    st.caption("For status changes use the checkboxes in the table")

    cutoff_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    db = get_db()
    edit_result = db.table("amazon_pickups")\
        .select("*")\
        .eq("picked_up", False)\
        .gte("pickup_date", cutoff_str)\
        .order("pickup_date", desc=False)\
        .execute()
    edit_df = pd.DataFrame(edit_result.data)

    if not edit_df.empty:
        so_options = [s for s in edit_df["sales_order"].dropna().tolist() if str(s).strip() != ""]
        if so_options:
            selected_so = st.selectbox("Select sales order", so_options)
            sel_row = edit_df[edit_df["sales_order"] == selected_so].iloc[0]
            row_id = sel_row["id"]
            k = selected_so.replace(" ", "_")

            new_carrier = st.text_input("Carrier", value=clean(sel_row.get("carrier", "")), key=f"carrier_{k}")
            new_pallets = st.number_input("Pallets", min_value=0, step=1,
                                           value=int(sel_row.get("pallets", 0) or 0), key=f"pallets_{k}")
            new_cartons = st.number_input("Cartons", min_value=0, step=1,
                                           value=int(sel_row.get("cartons", 0) or 0), key=f"cartons_{k}")
            new_notes = st.text_area("Notes", value=clean(sel_row.get("notes", "")), key=f"notes_{k}")

            if st.button("Save details", type="primary", use_container_width=True):
                get_db().table("amazon_pickups").update({
                    "carrier": new_carrier,
                    "pallets": new_pallets,
                    "cartons": new_cartons,
                    "notes": new_notes,
                }).eq("id", row_id).execute()
                st.cache_data.clear()
                st.success(f"{selected_so} updated")
                st.rerun()
    else:
        st.info("No pending pickups in the last 7 days")

# --- metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Pending pickups", len(pending_df))
col2.metric("Pickup today", len(today_df))
col3.metric("Pickup tomorrow", len(tomorrow_df))
col4.metric("Total pallets pending", int(pending_df["pallets"].sum()) if not pending_df.empty else 0)

if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

# --- view filters ---
st.subheader("Pickup log")
date_options = ["Pending", "Today", "Tomorrow", "Last 30 days", "All"]
selected_range = st.radio("Show", date_options, horizontal=True)
date_filter_map = {"Pending": "pending", "Today": "today", "Tomorrow": "tomorrow",
                   "Last 30 days": "last30", "All": "all"}
date_filter = date_filter_map[selected_range]

carrier_filter = st.selectbox("Carrier", ["All", "AMZX", "EXLA", "CTII", "TFIN", "AACT", "XJLW"])

view_df = load_view(date_filter, carrier_filter if carrier_filter != "All" else None)

if not view_df.empty:
    # format date for display
    view_df["pickup_date"] = view_df["pickup_date"].apply(
        lambda x: x.strftime("%m/%d/%Y") if pd.notna(x) else "")

    st.caption(f"{len(view_df)} orders · {int(view_df['pallets'].sum())} pallets · {int(view_df['cartons'].sum())} cartons")
    st.caption("✏️ Check or uncheck boxes directly in the table, then click **Save changes** to update all at once")

    # columns to show in editor
    display_cols = ["pickup_date", "sales_order", "arn", "carrier", "pallets",
                    "cartons", "picked", "ready", "bol_printed", "picked_up", "notes"]
    display_cols = [c for c in display_cols if c in view_df.columns]

    rename_map = {
        "pickup_date": "Pickup date", "sales_order": "Sales order",
        "arn": "ARN#", "carrier": "Carrier", "pallets": "Pallets",
        "cartons": "Cartons", "picked": "Picked", "ready": "Ready",
        "bol_printed": "BOL printed", "picked_up": "Picked up", "notes": "Notes"
    }

    display_df = view_df[display_cols + ["id"]].rename(columns=rename_map)

    edited_df = st.data_editor(
        display_df.drop(columns=["id"]),
        use_container_width=True,
        hide_index=True,
        disabled=["Pickup date", "Sales order", "ARN#", "Carrier", "Pallets", "Cartons", "Notes"],
        column_config={
            "Picked": st.column_config.CheckboxColumn("Picked"),
            "Ready": st.column_config.CheckboxColumn("Ready"),
            "BOL printed": st.column_config.CheckboxColumn("BOL printed"),
            "Picked up": st.column_config.CheckboxColumn("Picked up"),
        }
    )

    if st.button("Save changes", type="primary"):
        db = get_db()
        changed = 0
        original = display_df.drop(columns=["id"])

        for i, row in edited_df.iterrows():
            orig = original.iloc[i]
            row_id = display_df.iloc[i]["id"]
            updates = {}

            for col, db_col in [("Picked", "picked"), ("Ready", "ready"),
                                  ("BOL printed", "bol_printed"), ("Picked up", "picked_up")]:
                if col in row and bool(row[col]) != bool(orig[col]):
                    updates[db_col] = bool(row[col])

            if updates:
                db.table("amazon_pickups").update(updates).eq("id", row_id).execute()
                changed += 1

        if changed > 0:
            st.cache_data.clear()
            st.success(f"Saved changes to {changed} orders")
            st.rerun()
        else:
            st.info("No changes detected")
else:
    st.info("No pickups found for the selected filters")

st.caption("Check/uncheck status boxes directly in the table. Use the sidebar to edit carrier, pallets, cartons, and notes.")
