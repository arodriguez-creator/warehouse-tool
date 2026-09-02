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

# --- sidebar ---
with st.sidebar:
    st.subheader("Pickup actions")
    st.caption("Select one or more orders")

    source_carrier = st.selectbox("Filter by carrier", ["All", "AMZX", "EXLA", "CTII", "TFIN", "AACT", "XJLW"])
    cutoff_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    db = get_db()
    edit_query = db.table("amazon_pickups")\
        .select("*")\
        .eq("picked_up", False)\
        .gte("pickup_date", cutoff_str)\
        .order("pickup_date", desc=False)

    if source_carrier != "All":
        edit_query = edit_query.eq("carrier", source_carrier)

    edit_result = edit_query.execute()
    edit_df = pd.DataFrame(edit_result.data)

    if not edit_df.empty:
        so_options = [s for s in edit_df["sales_order"].dropna().tolist() if str(s).strip() != ""]

        if so_options:
            selected_orders = st.multiselect("Select sales orders", so_options,
                                              help="Select one to edit, multiple for bulk actions")

            if selected_orders:
                is_bulk = len(selected_orders) > 1
                sel_rows = edit_df[edit_df["sales_order"].isin(selected_orders)]

                if is_bulk:
                    st.caption(f"{len(selected_orders)} orders selected")
                    st.markdown("**Bulk actions**")
                    mark_picked = st.checkbox("Mark all Picked", key="bulk_picked")
                    mark_ready = st.checkbox("Mark all Ready", key="bulk_ready")
                    mark_bol = st.checkbox("Mark all BOL printed", key="bulk_bol")
                    mark_pu = st.checkbox("Mark all Picked up", key="bulk_pu")

                    if st.button("Apply to all selected", type="primary", use_container_width=True):
                        db = get_db()
                        updates = {}
                        if mark_picked:
                            updates["picked"] = True
                        if mark_ready:
                            updates["ready"] = True
                        if mark_bol:
                            updates["bol_printed"] = True
                        if mark_pu:
                            updates["picked_up"] = True
                        if updates:
                            for _, row in sel_rows.iterrows():
                                db.table("amazon_pickups").update(updates).eq("id", row["id"]).execute()
                        st.cache_data.clear()
                        st.success(f"Updated {len(selected_orders)} orders")
                        st.rerun()

                else:
                    selected_so = selected_orders[0]
                    sel_row = sel_rows.iloc[0]
                    row_id = sel_row["id"]
                    k = selected_so.replace(" ", "_")

                    st.markdown("**Quick actions**")

                    picked = sel_row.get("picked", False)
                    ready = sel_row.get("ready", False)
                    bol = sel_row.get("bol_printed", False)
                    pu = sel_row.get("picked_up", False)

                    if picked:
                        st.success("Picked ✓")
                    else:
                        if st.button("Mark picked", type="primary", use_container_width=True, key=f"picked_{k}"):
                            get_db().table("amazon_pickups").update({"picked": True}).eq("id", row_id).execute()
                            st.cache_data.clear()
                            st.rerun()

                    if ready:
                        st.success("Ready ✓")
                    else:
                        if st.button("Mark ready", use_container_width=True, key=f"ready_{k}"):
                            get_db().table("amazon_pickups").update({"ready": True}).eq("id", row_id).execute()
                            st.cache_data.clear()
                            st.rerun()

                    if bol:
                        st.success("BOL printed ✓")
                    else:
                        if st.button("Mark BOL printed", use_container_width=True, key=f"bol_{k}"):
                            get_db().table("amazon_pickups").update({"bol_printed": True}).eq("id", row_id).execute()
                            st.cache_data.clear()
                            st.rerun()

                    st.divider()
                    if pu:
                        st.success("Picked up ✓")
                    else:
                        if st.button("Mark picked up", use_container_width=True, key=f"pu_{k}"):
                            get_db().table("amazon_pickups").update({"picked_up": True}).eq("id", row_id).execute()
                            st.cache_data.clear()
                            st.rerun()

                    st.divider()
                    st.markdown("**Edit details**")

                    current_carrier = clean(sel_row.get("carrier", ""))
                    current_pallets = sel_row.get("pallets", 0) or 0
                    current_cartons = sel_row.get("cartons", 0) or 0
                    current_notes = clean(sel_row.get("notes", ""))
                    current_date = sel_row.get("pickup_date", "")

                    new_carrier = st.text_input("Carrier", value=current_carrier, key=f"carrier_{k}")
                    new_pallets = st.number_input("Pallets", min_value=0, step=1, value=int(current_pallets), key=f"pallets_{k}")
                    new_cartons = st.number_input("Cartons", min_value=0, step=1, value=int(current_cartons), key=f"cartons_{k}")
                    new_notes = st.text_area("Notes", value=current_notes, key=f"notes_{k}")

                    if st.button("Save changes", type="primary", use_container_width=True, key=f"save_{k}"):
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
                st.caption("Select one or more sales orders above")
        else:
            st.info("No pending pickups in the last 7 days")
    else:
        st.info("No pending pickups found")

# --- metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Pending pickups", len(pending_df))
col2.metric("Pickup today", len(today_df))
col3.metric("Pickup tomorrow", len(tomorrow_df))
col4.metric("Total pallets pending", int(pending_df["pallets"].sum()) if not pending_df.empty else 0)

if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

# --- view ---
st.subheader("Pickup log")
date_options = ["Pending", "Today", "Tomorrow", "Last 30 days", "All"]
selected_range = st.radio("Show", date_options, horizontal=True)
date_filter_map = {"Pending": "pending", "Today": "today", "Tomorrow": "tomorrow",
                   "Last 30 days": "last30", "All": "all"}
date_filter = date_filter_map[selected_range]

fc1, fc2 = st.columns(2)
carrier_filter = fc1.selectbox("Carrier", ["All", "AMZX", "EXLA", "CTII", "TFIN", "AACT", "XJLW"])

view_df = load_view(date_filter, carrier_filter if carrier_filter != "All" else None)
st.write(view_df[["sales_order", "pickup_date"]].head())


if not view_df.empty:
    view_df["pickup_date"] = view_df["pickup_date"].apply(lambda x: pd.to_datetime(x).strftime("%m/%d/%Y") if pd.notna(x) else "")

    st.caption(f"{len(view_df)} orders · {int(view_df['pallets'].sum())} pallets · {int(view_df['cartons'].sum())} cartons")

    display_cols = ["pickup_date", "sales_order", "arn", "carrier", "pallets",
                    "cartons", "picked", "ready", "bol_printed", "picked_up", "notes"]
    display_cols = [c for c in display_cols if c in view_df.columns]

    rename_map = {
        "pickup_date": "Pickup date", "sales_order": "Sales order",
        "arn": "ARN#", "carrier": "Carrier", "pallets": "Pallets",
        "cartons": "Cartons", "picked": "Picked", "ready": "Ready",
        "bol_printed": "BOL printed", "picked_up": "Picked up", "notes": "Notes"
    }
    st.dataframe(view_df[display_cols].rename(columns=rename_map),
                 use_container_width=True, hide_index=True)
else:
    st.info("No pickups found for the selected filters")

st.caption("Select orders in the sidebar to update status. Changes write directly to Supabase.")
