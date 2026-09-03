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
page_header("Outbound shipments", "Live from Supabase — MAD & Instaship")

pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
today = datetime.now(pacific).date()
tomorrow = today + timedelta(days=1)

# --- fixed lists ---
CARRIERS = ["", "FEDEX FREIGHT", "E&E TRANS", "ROAD RUNNER", "FEDEX ECONOMY",
            "FEDEX PROPRITY", "JB HUNT", "UPS", "CTCC", "WALMART FLEET",
            "UPS GROUND", "CTCC/FEDEX FREIGHT", "CTCC/SEAVIEW", "CENTRAL TRANSPORT",
            "FEDEX GROUND", "ESTES", "ONTRAC", "Other"]

FREIGHT_TERMS = ["", "Prepaid CTCC", "Collect", "Prepaid UPS Ground", "PREPAID",
                 "UPS 2ND DAY AIR", "UPS NEXT DAY AIR", "FEDEX GROUND",
                 "FEDEX HOME DELIVERY", "FEDEX COLLECT", "3RD PARTY",
                 "CUSTOMER PROVIDED LABELS", "Other"]

CONSIGNEES = ["", "WALMART", "HINDA", "VA VETERANS", "TRANSFER", "SAMPLE",
              "STAPLES", "DOME PUBLISHING", "FRED MEYER", "A&A GLOBAL",
              "POWER SALES", "AMAZON", "BSD SUPERBUY", "TANNER COMPANY",
              "CERTIF-A-GIFT", "Other"]

ACCOUNTS = ["", "SAKAR", "AGA", "MNS BRANDS", "TECHNICAL PRO", "CASTLEWOOD",
            "OSMO", "M.HIDARY", "Other"]

ACCOUNT_COLORS = {
    "SAKAR": "#ffffff",
    "AGA": "#cce5ff",
    "MNS BRANDS": "#ffcccc",
    "TECHNICAL PRO": "#ccffcc",
    "CASTLEWOOD": "#ffe5cc",
    "OSMO": "#e5ccff",
    "M.HIDARY": "#fff0cc",
}

def clean(val):
    return "" if not val or str(val) == "nan" or val is None else str(val).strip()

def selectbox_with_other(label, options, current_val, key):
    if current_val and current_val not in options:
        options = options + [current_val]
    idx = options.index(current_val) if current_val in options else 0
    selected = st.selectbox(label, options, index=idx, key=f"sel_{key}")
    if selected == "Other":
        return st.text_input(f"Enter {label.lower()}", key=f"other_{key}")
    return selected

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
    if account_filter and account_filter.strip():
        query = query.ilike("account", f"%{account_filter}%")
    if carrier_filter and carrier_filter.strip():
        query = query.ilike("carrier", f"%{carrier_filter}%")
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

                        bulk_carrier = selectbox_with_other("Carrier (all)", CARRIERS, "", "bulk_carrier")
                        bulk_freight = selectbox_with_other("Freight terms (all)", FREIGHT_TERMS, "", "bulk_freight")
                        bulk_load = st.text_input("Set load # (all)", key="bulk_load")
                        bulk_appt = st.text_input("Set appt time (all)", key="bulk_appt")
                        bulk_pallets_str = st.text_input("Set pallets (all)", key="bulk_pallets")
                        st.divider()
                        mark_pu = st.checkbox("Mark all as picked up", key="bulk_pu")

                        if st.button("Apply to all selected", type="primary", use_container_width=True):
                            db = get_db()
                            updated = 0
                            for _, row in sel_rows.iterrows():
                                updates = {}
                                if bulk_carrier and bulk_carrier != "Other":
                                    updates["carrier"] = bulk_carrier
                                if bulk_freight and bulk_freight != "Other":
                                    updates["freight_terms"] = bulk_freight
                                if bulk_load.strip():
                                    updates["load_number"] = bulk_load.strip()
                                if bulk_appt.strip():
                                    updates["appt_time"] = bulk_appt.strip()
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
                        current_notes = clean(sel_row.get("notes", ""))
                        current_date = sel_row.get("date", "")
                        current_account = clean(sel_row.get("account", ""))
                        current_consignee = clean(sel_row.get("consignee", ""))
                        is_picked_up = sel_row.get("pu", False)

                        st.markdown("**Edit details**")

                        try:
                            date_val = datetime.strptime(current_date, "%Y-%m-%d").date() if current_date else today
                        except:
                            date_val = today

                        new_date = st.date_input("Date", value=date_val, key=f"date_{k}")
                        new_account = selectbox_with_other("Account", ACCOUNTS, current_account.upper(), f"acct_{k}")
                        new_carrier = selectbox_with_other("Carrier", CARRIERS, current_carrier.upper(), f"carrier_{k}")
                        new_freight = selectbox_with_other("Freight terms", FREIGHT_TERMS, current_freight, f"freight_{k}")
                        new_consignee = selectbox_with_other("Consignee", CONSIGNEES, current_consignee.upper(), f"consignee_{k}")
                        if is_mad:
                            new_appt = st.text_input("Appt time", value=current_appt, key=f"appt_{k}")
                        new_pallets = st.number_input("Pallet total", min_value=0, step=1,
                                                       value=int(current_pallets), key=f"pallets_{k}")
                        new_load = st.text_input("Load #", value=current_load, key=f"load_{k}")
                        new_notes = st.text_area("Notes", value=current_notes, key=f"notes_{k}")

                        if st.button("Save changes", type="primary", use_container_width=True, key=f"save_{k}"):
                            db = get_db()
                            updates = {
                                "date": new_date.strftime("%Y-%m-%d"),
                                "account": new_account,
                                "carrier": new_carrier,
                                "freight_terms": new_freight,
                                "consignee": new_consignee,
                                "pallet_total": new_pallets,
                                "load_number": new_load,
                                "notes": new_notes,
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
        st.markdown("**Assign load ID to multiple orders**")
        st.caption("Select orders that share a carrier pickup")
        load_source = st.selectbox("Business", ["MAD", "Instaship"])
        new_load_id = st.text_input("Load ID (from carrier)")
        new_appt_time = st.text_input("Appt time (optional)")
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
                        updates = {"load_number": new_load_id}
                        if new_appt_time.strip():
                            updates["appt_time"] = new_appt_time.strip()
                        db.table("outbound").update(updates).eq("id", match.iloc[0]["id"]).execute()
                st.cache_data.clear()
                st.success(f"Load ID {new_load_id} assigned to {len(selected_orders_load)} orders")
                st.rerun()

# --- add shipment ---
with st.expander("Add new shipment"):
    with st.form("new_shipment"):
        fa, fb = st.columns(2)
        new_business = fa.selectbox("Business", ["MAD", "Instaship"])
        new_account_sel = fb.selectbox("Account", ACCOUNTS)
        new_account_other = fb.text_input("Other account") if new_account_sel == "Other" else ""
        new_account = new_account_other if new_account_sel == "Other" else new_account_sel

        fc, fd = st.columns(2)
        new_date = fc.date_input("Date")
        new_carrier_sel = fd.selectbox("Carrier", CARRIERS)

        fe, ff = st.columns(2)
        new_freight_sel = fe.selectbox("Freight terms", FREIGHT_TERMS)
        new_consignee_sel = ff.selectbox("Consignee", CONSIGNEES)

        fg, fh = st.columns(2)
        new_so = fg.text_input("Sales order")
        new_po = fh.text_input("PO")

        fi, fj = st.columns(2)
        new_ctn = fi.number_input("Cartons", min_value=0, step=1)
        new_pallets = fj.number_input("Pallets", min_value=0, step=1)

        fk, fl = st.columns(2)
        new_load = fk.text_input("Load #")
        new_appt = fl.text_input("Appt time (MAD only)")

        new_notes = st.text_area("Notes")

        submitted = st.form_submit_button("Add shipment")

        if submitted:
            if not new_so:
                st.error("Sales order is required")
            else:
                db = get_db()
                carrier_val = new_carrier_sel if new_carrier_sel != "Other" else ""
                freight_val = new_freight_sel if new_freight_sel != "Other" else ""
                consignee_val = new_consignee_sel if new_consignee_sel != "Other" else ""
                db.table("outbound").insert({
                    "business": new_business,
                    "account": new_account,
                    "carrier": carrier_val,
                    "date": new_date.strftime("%Y-%m-%d"),
                    "freight_terms": freight_val,
                    "appt_time": new_appt if new_business == "MAD" else "",
                    "consignee": consignee_val,
                    "sales_order": new_so,
                    "po": new_po,
                    "ctn": int(new_ctn),
                    "pallet_total": int(new_pallets),
                    "load_number": new_load,
                    "notes": new_notes,
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
    view_df["date"] = view_df["date"].apply(
        lambda x: pd.to_datetime(x).strftime("%m/%d/%Y") if x else "")

    s1, s2, s3 = st.columns(3)
    s1.caption(f"{len(view_df)} shipments")
    s2.caption(f"{view_df['ctn'].sum():,} cartons")
    s3.caption(f"{view_df['pallet_total'].sum()} pallets")

    # apply account color coding
    display_cols = ["business", "date", "account", "carrier", "freight_terms",
                    "consignee", "sales_order", "po", "ctn", "pallet_total",
                    "load_number", "appt_time", "pu", "notes"]
    display_cols = [c for c in display_cols if c in view_df.columns]

    rename_map = {
        "business": "Business", "date": "Date", "account": "Account",
        "carrier": "Carrier", "freight_terms": "Freight terms",
        "consignee": "Consignee", "sales_order": "Sales order",
        "po": "PO", "ctn": "Cartons", "pallet_total": "Pallets",
        "load_number": "Load #", "appt_time": "Appt time",
        "pu": "PU", "notes": "Notes"
    }

    display_df = view_df[display_cols].rename(columns=rename_map)

    def color_account_row(row):
        account = str(row.get("Account", "")).upper().strip()
        color = ACCOUNT_COLORS.get(account, "#ffffff")
        if color == "#ffffff":
            return [""] * len(row)
        return [f"background-color: {color}"] * len(row)

    def get_row_color(account):
        return ACCOUNT_COLORS.get(str(account).upper().strip(), "")

    st.dataframe(
        display_df.style.apply(
            lambda x: [f"background-color: {get_row_color(x['Account'])}" 
                   if get_row_color(x['Account']) else "" 
                   for _ in x],
            axis=1
        ),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No shipments found for the selected filters")

st.caption("Click any column header to sort. Data refreshes every 2 minutes.")
