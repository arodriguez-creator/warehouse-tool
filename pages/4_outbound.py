import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from styles import GLOBAL_CSS, page_header
from auth import require_auth, show_user, get_db

require_auth()
show_user()

st.set_page_config(layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
page_header("Outbound shipments", "Live from Supabase — MAD & Instaship")

def clean(val):
    return "" if not val or str(val) == "nan" or val is None else str(val).strip()

today = datetime.today().date()
tomorrow = today + timedelta(days=1)

@st.cache_data(ttl=120)
def load_today():
    db = get_db()
    result = db.table("outbound")\
        .select("*")\
        .eq("date", today.strftime("%Y-%m-%d"))\
        .order("business")\
        .execute()
    return pd.DataFrame(result.data)

@st.cache_data(ttl=120)
def load_for_edit(business, cutoff_str):
    db = get_db()
    result = db.table("outbound")\
        .select("*")\
        .eq("business", business)\
        .eq("pu", False)\
        .gte("date", cutoff_str)\
        .order("date", desc=True)\
        .execute()
    return pd.DataFrame(result.data)

@st.cache_data(ttl=120)
def load_view(date_filter, business_filter, account_filter, carrier_filter):
    db = get_db()
    query = db.table("outbound").select("*")

    if date_filter == "today":
        query = query.eq("date", today.strftime("%Y-%m-%d"))
    elif date_filter == "tomorrow":
        query = query.eq("date", tomorrow.strftime("%Y-%m-%d"))
    elif date_filter == "last7":
        cutoff = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        query = query.gte("date", cutoff)

    if business_filter and business_filter != "All":
        query = query.eq("business", business_filter)
    if account_filter and account_filter != "All":
        query = query.eq("account", account_filter)
    if carrier_filter and carrier_filter != "All":
        query = query.eq("carrier", carrier_filter)

    result = query.order("date", desc=True).execute()
    return pd.DataFrame(result.data)

df_today = load_today()
mad_today = df_today[df_today["business"] == "MAD"] if not df_today.empty else pd.DataFrame()
insta_today = df_today[df_today["business"] == "Instaship"] if not df_today.empty else pd.DataFrame()

# --- sidebar ---
with st.sidebar:
    st.subheader("Shipment actions")
    action = st.radio("Action", ["Edit / Bulk update", "Assign load ID"])

    if action == "Edit / Bulk update":
        source_filter = st.selectbox("Business", ["MAD", "Instaship"])
        cutoff_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        edit_df = load_for_edit(source_filter, cutoff_str)
        is_mad = source_filter == "MAD"

        if not edit_df.empty:
            so_options = [s for s in edit_df["sales_order"].dropna().tolist() if str(s).strip() != ""]

            if so_options:
                selected_orders = st.multiselect(
                    "Select sales orders", so_options,
                    help="Select one to edit, or multiple for bulk actions"
                )

                if selected_orders:
                    is_bulk = len(selected_orders) > 1
                    sel_rows = edit_df[edit_df["sales_order"].isin(selected_orders)]

                    if is_bulk:
                        st.caption(f"{len(selected_orders)} orders selected")
                        st.markdown("**Bulk update fields**")
                        st.caption("Leave blank to skip that field")

                        bulk_carrier = st.text_input("Set carrier (all)", key="bulk_carrier")
                        bulk_load = st.text_input("Set load # (all)", key="bulk_load")
                        bulk_pallets_str = st.text_input("Set pallets (all)", key="bulk_pallets")
                        st.divider()
                        mark_pu = st.checkbox("Mark all as picked up", key="bulk_pu")

                        if st.button("Apply to all selected", type="primary", use_container_width=True):
                            db = get_db()
                            updated = 0
                            for _, row in sel_rows.iterrows():
                                updates = {}
                                if bulk_carrier.strip():
                                    updates["carrier"] = bulk_carrier.strip()
                                if bulk_load.strip():
                                    updates["load_number"] = bulk_load.strip()
                                if bulk_pallets_str.strip().isdigit():
                                    updates["pallet_total"] = int(bulk_pallets_str.strip())
                                if mark_pu:
                                    updates["pu"] = True
                                if updates:
                                    db.table("outbound").update(updates).eq("id", row["id"]).execute()
                                updated += 1
                            st.cache_data.clear()
                            st.success(f"Updated {updated} shipments")
                            st.rerun()

                    else:
                        selected_so = selected_orders[0]
                        sel_row = sel_rows.iloc[0]
                        row_id = sel_row["id"]
                        k = selected_so.replace(" ", "_")

                        current_carrier = clean(sel_row.get("carrier", ""))
                        current_pallets = sel_row.get("pallet_total", 0) or 0
                        current_load = clean(sel_row.get("load_number", ""))
                        current_freight = clean(sel_row.get("freight_terms", ""))
                        current_appt = clean(sel_row.get("appt_time", ""))
                        is_picked_up = sel_row.get("pu", False)

                        st.markdown("**Edit details**")
                        new_carrier = st.text_input("Carrier", value=current_carrier, key=f"carrier_{k}")
                        new_freight = st.text_input("Freight terms", value=current_freight, key=f"freight_{k}")
                        if is_mad:
                            new_appt = st.text_input("Appt time", value=current_appt, key=f"appt_{k}")
                        new_pallets = st.number_input("Pallet total", min_value=0, step=1,
                                                       value=int(current_pallets), key=f"pallets_{k}")
                        new_load = st.text_input("Load #", value=current_load, key=f"load_{k}")

                        if st.button("Save changes", type="primary", use_container_width=True, key=f"save_{k}"):
                            db = get_db()
                            updates = {
                                "carrier": new_carrier,
                                "freight_terms": new_freight,
                                "pallet_total": new_pallets,
                                "load_number": new_load,
                            }
                            if is_mad:
                                updates["appt_time"] = new_appt
                            db.table("outbound").update(updates).eq("id", row_id).execute()
                            st.cache_data.clear()
                            st.success(f"{selected_so} updated")
                            st.rerun()

                        st.divider()
                        if is_picked_up:
                            st.success("Picked up ✓")
                        else:
                            if st.button("Mark picked up", use_container_width=True, key=f"pu_{k}"):
                                db = get_db()
                                db.table("outbound").update({"pu": True}).eq("id", row_id).execute()
                                st.cache_data.clear()
                                st.success(f"{selected_so} marked picked up")
                                st.rerun()
                else:
                    st.caption("Select one or more sales orders above")
            else:
                st.info("No unpicked shipments in the last 7 days")
        else:
            st.info("No shipments found in the last 7 days")

    else:
        st.markdown("**Assign load ID to multiple orders**")
        st.caption("Select orders that share a carrier pickup")
        load_source = st.selectbox("Business", ["MAD", "Instaship"])
        new_load_id = st.text_input("Load ID (from carrier)")
        cutoff_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        load_df = load_for_edit(load_source, cutoff_str)
        so_list = [s for s in load_df["sales_order"].dropna().tolist() if str(s).strip() != ""] if not load_df.empty else []
        selected_orders_load = st.multiselect("Select sales orders", so_list)

        if st.button("Assign load ID", type="primary", use_container_width=True):
            if not new_load_id:
                st.error("Enter a load ID first")
            elif not selected_orders_load:
                st.error("Select at least one order")
            else:
                db = get_db()
                for so in selected_orders_load:
                    match = load_df[load_df["sales_order"] == so]
                    if not match.empty:
                        db.table("outbound").update({"load_number": new_load_id}).eq("id", match.iloc[0]["id"]).execute()
                st.cache_data.clear()
                st.success(f"Load ID {new_load_id} assigned to {len(selected_orders_load)} orders")
                st.rerun()

# --- add shipment ---
with st.expander("Add new shipment"):
    with st.form("new_shipment"):
        fa, fb = st.columns(2)
        new_business = fa.selectbox("Business", ["MAD", "Instaship"])
        new_account = fb.text_input("Account")
        fc, fd = st.columns(2)
        new_date = fc.date_input("Date")
        new_carrier = fd.text_input("Carrier")
        fe, ff = st.columns(2)
        new_freight = fe.text_input("Freight terms")
        new_consignee = ff.text_input("Consignee")
        fg, fh = st.columns(2)
        new_so = fg.text_input("Sales order")
        new_po = fh.text_input("PO")
        fi, fj = st.columns(2)
        new_ctn = fi.number_input("Cartons", min_value=0, step=1)
        new_pallets = fj.number_input("Pallets", min_value=0, step=1)
        fk, fl = st.columns(2)
        new_load = fk.text_input("Load #")
        new_appt = fl.text_input("Appt time (MAD only)")
        submitted = st.form_submit_button("Add shipment")

        if submitted:
            if not new_so:
                st.error("Sales order is required")
            else:
                db = get_db()
                db.table("outbound").insert({
                    "business": new_business,
                    "account": new_account,
                    "carrier": new_carrier,
                    "date": new_date.strftime("%Y-%m-%d"),
                    "freight_terms": new_freight,
                    "appt_time": new_appt if new_business == "MAD" else "",
                    "consignee": new_consignee,
                    "sales_order": new_so,
                    "po": new_po,
                    "ctn": int(new_ctn),
                    "pallet_total": int(new_pallets),
                    "load_number": new_load,
                    "pu": False,
                    "billed": False,
                }).execute()
                st.cache_data.clear()
                st.success(f"Shipment {new_so} added to {new_business}")
                st.rerun()

# --- metrics ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Shipments today", len(df_today))
col2.metric("MAD today", len(mad_today))
col3.metric("Instaship today", len(insta_today))
col4.metric("Total cartons", f"{df_today['ctn'].sum():,}" if not df_today.empty else "0")
col5.metric("Total pallets", df_today["pallet_total"].sum() if not df_today.empty else 0)

# --- view filters ---
st.subheader("Shipment log")
date_options = ["Today", "Tomorrow", "Last 7 days", "All"]
selected_range = st.radio("Show", date_options, horizontal=True)

date_filter_map = {"Today": "today", "Tomorrow": "tomorrow", "Last 7 days": "last7", "All": "all"}
date_filter = date_filter_map[selected_range]

fc1, fc2, fc3 = st.columns(3)
selected_source = fc1.selectbox("Business", ["All", "MAD", "Instaship"])
selected_account = fc2.text_input("Filter account")
selected_carrier = fc3.text_input("Filter carrier")

view_df = load_view(
    date_filter,
    selected_source if selected_source != "All" else None,
    selected_account if selected_account else None,
    selected_carrier if selected_carrier else None
)

if not view_df.empty:
    view_df["date"] = view_df["date"].apply(lambda x: pd.to_datetime(x).strftime("%m/%d/%Y") if x else "")

    s1, s2, s3 = st.columns(3)
    s1.caption(f"{len(view_df)} shipments")
    s2.caption(f"{view_df['ctn'].sum():,} cartons")
    s3.caption(f"{view_df['pallet_total'].sum()} pallets")

    display_cols = ["business", "date", "account", "carrier", "freight_terms",
                    "consignee", "sales_order", "po", "ctn", "pallet_total",
                    "load_number", "pu", "appt_time"]
    display_cols = [c for c in display_cols if c in view_df.columns]

    rename_map = {
        "business": "Business", "date": "Date", "account": "Account",
        "carrier": "Carrier", "freight_terms": "Freight terms",
        "consignee": "Consignee", "sales_order": "Sales order",
        "po": "PO", "ctn": "Cartons", "pallet_total": "Pallets",
        "load_number": "Load #", "pu": "PU", "appt_time": "Appt time"
    }
    st.dataframe(view_df[display_cols].rename(columns=rename_map),
                 use_container_width=True, hide_index=True)
else:
    st.info("No shipments found for the selected filters")

st.caption("Click any column header to sort. Data refreshes every 2 minutes.")
