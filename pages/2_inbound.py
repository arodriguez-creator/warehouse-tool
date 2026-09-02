import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from styles import GLOBAL_CSS, page_header
from auth import require_auth, show_user, get_db
require_auth()
show_user()
import zoneinfo

st.set_page_config(layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
page_header("Inbound containers", "Live from Supabase — Inbound")

def clean(val):
    return "" if not val or str(val) == "nan" or val is None else str(val).strip()

@st.cache_data(ttl=60)
def load_data():
    db = get_db()
    result = db.table("containers").select("*").execute()
    df = pd.DataFrame(result.data)
    if df.empty:
        return df
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
    return df

@st.cache_data(ttl=60)
def load_dock_data():
    db = get_db()
    result = db.table("dock_status").select("*").execute()
    return pd.DataFrame(result.data)

def get_active_df():
    db = get_db()
    import zoneinfo
    pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
    cutoff = (datetime.now(pacific) - timedelta(days=14)).strftime("%Y-%m-%d")
    result = db.table("containers")\
        .select("*")\
        .eq("picked_up", False)\
        .gte("arrival_date", cutoff)\
        .order("arrival_date", desc=True)\
        .execute()
    df = pd.DataFrame(result.data)
    if df.empty:
        return df
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
    df = df[df["container"].str.strip() != ""]
    return df

# --- sidebar ---
with st.sidebar:
    st.subheader("Container actions")
    df_all = get_active_df()

    if not df_all.empty:
        container_options = df_all["container"].tolist()
        selected_container = st.selectbox("Select container", container_options, key="container_select")
        sel_row = df_all[df_all["container"] == selected_container].iloc[0]
        row_id = sel_row["id"]
        received = sel_row.get("received", False)
        picked = sel_row.get("picked_up", False)
        empty = sel_row.get("empty", False)
        k = selected_container.replace(" ", "_")

        st.markdown("**Quick actions**")

        if empty:
            st.success("Container empty ✓")
            if st.button("Unmark empty", use_container_width=True, key=f"unempty_{k}"):
                db = get_db()
                db.table("containers").update({
                    "empty": False,
                    "empty_timestamp": None
                }).eq("id", row_id).execute()
                st.cache_data.clear()
                st.success(f"{selected_container} unmarked")
                st.rerun()
        else:
            if st.button("Mark empty", type="primary", use_container_width=True, key=f"empty_{k}"):
                db = get_db()
                pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
                db.table("containers").update({
                    "empty": True,
                    "empty_timestamp": datetime.now(pacific).strftime("%Y-%m-%d")
                }).eq("id", row_id).execute()
                st.cache_data.clear()
                st.success(f"{selected_container} marked empty")
                st.rerun()

        if received:
            st.success("Received ✓")
        else:
            if st.button("Mark received", type="primary", use_container_width=True, key=f"recv_{k}"):
                db = get_db()
                db.table("containers").update({"received": True}).eq("id", row_id).execute()
                st.cache_data.clear()
                st.success(f"{selected_container} marked received")
                st.rerun()

        if picked:
            st.success("Picked up ✓")
        else:
            if st.button("Mark picked up", use_container_width=True, key=f"pick_{k}"):
                db = get_db()
                db.table("containers").update({"picked_up": True}).eq("id", row_id).execute()
                st.cache_data.clear()
                st.success(f"{selected_container} marked picked up")
                st.rerun()

        st.divider()
        st.markdown("**Edit details**")

        current_status = clean(sel_row.get("container_status", ""))
        current_dock = clean(sel_row.get("dock_door", ""))
        current_trucking = clean(sel_row.get("trucking_company", ""))
        current_account = clean(sel_row.get("account", ""))
        current_sku = sel_row.get("sku_count", 0) or 0
        current_carton = sel_row.get("carton_count", 0) or 0
        current_warehouse = clean(sel_row.get("warehouse", ""))

        status_options = ["", "In dock", "picked up", "scheduled"]
        status_index = status_options.index(current_status) if current_status in status_options else 0

        new_status = st.selectbox("Container status", status_options, index=status_index, key=f"status_{k}")
        new_dock = st.text_input("Dock door", value=current_dock, key=f"dock_{k}")
        new_trucking = st.text_input("Trucking company", value=current_trucking, key=f"truck_{k}")
        new_account = st.text_input("Account", value=current_account, key=f"acct_{k}")
        new_sku = st.number_input("SKU count", min_value=0, step=1, value=int(current_sku), key=f"sku_{k}")
        new_carton = st.number_input("Carton count", min_value=0, step=1, value=int(current_carton), key=f"carton_{k}")
        new_warehouse = st.text_input("Warehouse", value=current_warehouse, key=f"wh_{k}")

        if st.button("Save changes", type="primary", use_container_width=True, key=f"save_{k}"):
            db = get_db()
            dock_warning = False

            if new_dock and new_dock != current_dock:
                dock_df = load_dock_data()
                matching = dock_df[dock_df["door"] == f"Door {new_dock}"] if "door" in dock_df.columns else pd.DataFrame()
                if not matching.empty:
                    door_status = str(matching.iloc[0].get("status", "")).strip().lower()
                    door_container = str(matching.iloc[0].get("container_trailer", "")).strip()
                    if "occupied" in door_status and door_container and door_container != "None":
                        st.warning(f"Door {new_dock} is already occupied by {door_container}. Save anyway?")
                        dock_warning = True

            if not dock_warning:
                db.table("containers").update({
                    "container_status": new_status,
                    "dock_door": new_dock,
                    "trucking_company": new_trucking,
                    "account": new_account,
                    "sku_count": new_sku,
                    "carton_count": new_carton,
                    "warehouse": new_warehouse,
                }).eq("id", row_id).execute()

                if new_dock:
                    dock_df = load_dock_data()
                    matching = dock_df[dock_df["door"] == f"Door {new_dock}"] if "door" in dock_df.columns else pd.DataFrame()
                    if not matching.empty:
                        dock_id = matching.iloc[0]["id"]
                        db.table("dock_status").update({
                            "container_trailer": selected_container,
                            "status": "Occupied"
                        }).eq("id", dock_id).execute()

                st.success(f"{selected_container} updated")
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("No active containers to edit")

# --- main page ---
df = get_active_df()
total = len(df)
in_dock = df[df["container_status"] == "In dock"].shape[0] if not df.empty else 0
not_received = df[df["received"] != True].shape[0] if not df.empty else 0
not_billed = df[df["billed"] != True].shape[0] if not df.empty else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Active containers", total)
col2.metric("In dock", in_dock)
col3.metric("Not yet received", not_received)
col4.metric("Not yet billed", not_billed)

if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

st.subheader("Active container log")
st.caption("Click any column header to sort")
with st.expander("🟡 Empty containers in yard", expanded=True):
    db = get_db()
    empty_result = db.table("containers")\
        .select("container, account, trucking_company, dock_door, empty_timestamp")\
        .eq("empty", True)\
        .eq("picked_up", False)\
        .order("empty_timestamp")\
        .execute()
    empty_df = pd.DataFrame(empty_result.data)

    if empty_df.empty:
        st.success("No empty containers in yard")
    else:
        st.caption(f"{len(empty_df)} empty containers waiting for pickup")
        rename_map = {
            "container": "Container",
            "account": "Account",
            "trucking_company": "Trucking company",
            "dock_door": "Dock door",
            "empty_timestamp": "Empty date"
        }
        st.dataframe(
            empty_df.rename(columns=rename_map),
            use_container_width=True,
            hide_index=True
        )

with st.expander("Add new inbound container"):
    with st.form("new_container"):
        fc1, fc2 = st.columns(2)
        new_arrival = fc1.date_input("Arrival date")
        new_container_num = fc2.text_input("Container number")
        fc3, fc4 = st.columns(2)
        new_account = fc3.text_input("Account")
        new_trucking = fc4.text_input("Trucking company")
        fc5, fc6 = st.columns(2)
        new_status = fc5.selectbox("Container status", ["", "In dock", "picked up", "scheduled"])
        new_dock_door = fc6.text_input("Dock door")
        fc7, fc8 = st.columns(2)
        new_sku_count = fc7.number_input("SKU count", min_value=0, step=1)
        new_carton_count = fc8.number_input("Carton count", min_value=0, step=1)
        new_warehouse = st.text_input("Warehouse")
        submitted = st.form_submit_button("Add container")

        if submitted:
            if not new_container_num:
                st.error("Container number is required")
            else:
                db = get_db()
                db.table("containers").insert({
                    "arrival_date": new_arrival.strftime("%Y-%m-%d"),
                    "container": new_container_num,
                    "account": new_account,
                    "trucking_company": new_trucking,
                    "container_status": new_status,
                    "dock_door": new_dock_door,
                    "sku_count": int(new_sku_count),
                    "carton_count": int(new_carton_count),
                    "warehouse": new_warehouse,
                    "empty": False,
                    "received": False,
                    "picked_up": False,
                    "billed": False,
                }).execute()
                st.success(f"Container {new_container_num} added successfully")
                st.cache_data.clear()
                st.rerun()

if not df.empty:
    accounts = ["All"] + sorted(df["account"].dropna().unique().tolist())
    selected_account = st.selectbox("Filter by account", accounts)
    if selected_account != "All":
        df = df[df["account"] == selected_account]

    display_cols = ["arrival_date", "container", "account", "container_status",
                "trucking_company", "dock_door", "sku_count", "carton_count",
                "empty", "received", "warehouse"]
    display_cols = [c for c in display_cols if c in df.columns]
    df["arrival_date"] = df["arrival_date"].dt.strftime("%m/%d/%Y")

    rename_map = {
        "arrival_date": "Arrival date",
        "container": "Container",
        "account": "Account",
        "container_status": "Status",
        "trucking_company": "Trucking company",
        "dock_door": "Dock door",
        "sku_count": "SKU count",
        "carton_count": "Carton count",
        "received": "Received",
        "warehouse": "Warehouse"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True, hide_index=True)
else:
    st.info("No active containers in the last 14 days")

st.caption("Select a container in the sidebar to mark received, picked up, or edit details. Changes write directly to Supabase.")
