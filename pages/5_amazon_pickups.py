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
st.session_state["last_page"] = "other"

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

@st.cache_data(ttl=60)
def get_existing_keys():
    db = get_db()
    existing_keys = set()
    offset = 0
    while True:
        batch = db.table("amazon_pickups").select("sales_order, arn")\
            .range(offset, offset + 999).execute()
        for r in batch.data:
            existing_keys.add((r["sales_order"], r["arn"]))
        if len(batch.data) < 1000:
            break
        offset += 1000
    return existing_keys

pending_df = load_pending()
today_df = pending_df[pending_df["pickup_date"].dt.date == today] if not pending_df.empty else pd.DataFrame()
tomorrow_df = pending_df[pending_df["pickup_date"].dt.date == tomorrow] if not pending_df.empty else pd.DataFrame()

# --- sidebar ---
with st.sidebar:
    st.subheader("Edit order details")
    st.caption("For status use checkboxes in table")

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

            current_date = sel_row.get("pickup_date", "")
            try:
                date_val = datetime.strptime(str(current_date)[:10], "%Y-%m-%d").date() if current_date else today
            except:
                date_val = today

            new_date = st.date_input("Pickup date", value=date_val, key=f"date_{k}")
            new_carrier = st.text_input("Carrier", value=clean(sel_row.get("carrier", "")), key=f"carrier_{k}")
            new_pallets = st.number_input("Pallets", min_value=0, step=1,
                                           value=int(sel_row.get("pallets", 0) or 0), key=f"pallets_{k}")
            new_cartons = st.number_input("Cartons", min_value=0, step=1,
                                           value=int(sel_row.get("cartons", 0) or 0), key=f"cartons_{k}")
            new_notes = st.text_area("Notes", value=clean(sel_row.get("notes", "")), key=f"notes_{k}")

            if st.button("Save details", type="primary", use_container_width=True):
                get_db().table("amazon_pickups").update({
                    "pickup_date": new_date.strftime("%Y-%m-%d"),
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

# --- bulk add ---
with st.expander("Bulk add orders"):
    st.caption("Paste the table from your pickup notification (columns: SHIPMENTID, ARN#, CARRIER)")
    
    bulk_date = st.date_input("Pickup date for all orders", value=today, key="bulk_date")
    pasted = st.text_area("Paste order data here", height=200, 
                           placeholder="SHIPMENTID\tARN#\tCARRIER\nDN26243232\t46179996121\tUPSN")
    
    if st.button("Preview orders", key="preview_bulk"):
        if pasted.strip():
            lines = [l.strip() for l in pasted.strip().split("\n") if l.strip()]
            # skip header row if present
            if lines and "SHIPMENT" in lines[0].upper():
                lines = lines[1:]
            parsed = []
            for line in lines:
                parts = line.split("\t") if "\t" in line else line.split()
                if len(parts) >= 2:
                    so = clean(parts[0])
                    arn = clean(parts[1])
                    carrier = clean(parts[2]) if len(parts) > 2 else ""
                    if so:
                        parsed.append({"Sales order": so, "ARN#": arn, "Carrier": carrier})
            if parsed:
                st.session_state["bulk_preview"] = parsed
                preview_df = pd.DataFrame(parsed)
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
                st.caption(f"{len(parsed)} orders ready to add")
            else:
                st.error("Could not parse the pasted data")
        else:
            st.error("Paste some data first")

    if "bulk_preview" in st.session_state and st.session_state["bulk_preview"]:
        if st.button("Add all orders", type="primary", key="confirm_bulk"):
            db = get_db()
            existing_keys = get_existing_keys()
            new_rows = []
            skipped = 0
            for item in st.session_state["bulk_preview"]:
                so = item["Sales order"]
                arn = item["ARN#"]
                if (so, arn) in existing_keys:
                    skipped += 1
                    continue
                new_rows.append({
                    "sales_order": so,
                    "arn": arn,
                    "carrier": item["Carrier"],
                    "pickup_date": bulk_date.strftime("%Y-%m-%d"),
                    "picked": False,
                    "ready": False,
                    "bol_printed": False,
                    "picked_up": False,
                    "pallets": 0,
                    "cartons": 0,
                    "notes": "",
                })
            if new_rows:
                db.table("amazon_pickups").insert(new_rows).execute()
                st.cache_data.clear()
                st.session_state.pop("bulk_preview", None)
                st.success(f"Added {len(new_rows)} orders" + (f" · {skipped} already existed" if skipped else ""))
                st.rerun()
            else:
                st.warning(f"All {skipped} orders already exist in the database")

# --- single add ---
with st.expander("Add single order"):
    with st.form("new_pickup"):
        fa, fb = st.columns(2)
        new_so = fa.text_input("Sales order")
        new_arn = fb.text_input("ARN#")
        fc, fd = st.columns(2)
        new_carrier = fc.text_input("Carrier")
        new_date = fd.date_input("Pickup date", value=today)
        fe, ff = st.columns(2)
        new_pallets = fe.number_input("Pallets", min_value=0, step=1)
        new_cartons = ff.number_input("Cartons", min_value=0, step=1)
        new_notes = st.text_input("Notes")
        submitted = st.form_submit_button("Add order")
        if submitted:
            if not new_so:
                st.error("Sales order is required")
            else:
                db = get_db()
                existing = db.table("amazon_pickups")\
                    .select("id")\
                    .eq("sales_order", new_so)\
                    .eq("arn", new_arn)\
                    .execute()
                if existing.data:
                    st.error(f"Order {new_so} with ARN {new_arn} already exists in the database")
                else:
                    db.table("amazon_pickups").insert({    
                    "sales_order": new_so,
                    "arn": new_arn,
                    "carrier": new_carrier,
                    "pickup_date": new_date.strftime("%Y-%m-%d"),
                    "pallets": int(new_pallets),
                    "cartons": int(new_cartons),
                    "notes": new_notes,
                    "picked": False,
                    "ready": False,
                    "bol_printed": False,
                    "picked_up": False,
                }).execute()
                st.cache_data.clear()
                st.success(f"Order {new_so} added")
                st.rerun()

# --- view ---
st.subheader("Pickup log")
date_options = ["Pending", "Today", "Tomorrow", "Last 30 days", "All"]
selected_range = st.radio("Show", date_options, horizontal=True)
date_filter_map = {"Pending": "pending", "Today": "today", "Tomorrow": "tomorrow",
                   "Last 30 days": "last30", "All": "all"}
date_filter = date_filter_map[selected_range]

carrier_filter = st.selectbox("Carrier", ["All", "AMZX", "EXLA", "CTII", "TFIN", "AACT", "XJLW", "UPSN"])

view_df = load_view(date_filter, carrier_filter if carrier_filter != "All" else None)

if not view_df.empty:
    view_df["pickup_date_display"] = view_df["pickup_date"].apply(
        lambda x: x.strftime("%m/%d/%Y") if pd.notna(x) else "")

    st.caption(f"{len(view_df)} orders · {int(view_df['pallets'].sum())} pallets · {int(view_df['cartons'].sum())} cartons")
    st.caption("✏️ Edit pickup date and notes directly. Check/uncheck status boxes. Click **Save changes** when done.")

    display_cols = ["pickup_date_display", "sales_order", "arn", "carrier", "pallets",
                    "cartons", "picked", "ready", "bol_printed", "picked_up", "notes"]
    display_cols = [c for c in display_cols if c in view_df.columns]

    rename_map = {
        "pickup_date_display": "Pickup date", "sales_order": "Sales order",
        "arn": "ARN#", "carrier": "Carrier", "pallets": "Pallets",
        "cartons": "Cartons", "picked": "Picked", "ready": "Ready",
        "bol_printed": "BOL printed", "picked_up": "Picked up", "notes": "Notes"
    }

    display_df = view_df[display_cols + ["id"]].rename(columns=rename_map)

    edited_df = st.data_editor(
        display_df.drop(columns=["id"]),
        use_container_width=True,
        hide_index=True,
        disabled=["Sales order", "ARN#", "Carrier", "Pallets", "Cartons"],
        column_config={
            "Pickup date": st.column_config.TextColumn("Pickup date"),
            "Picked": st.column_config.CheckboxColumn("Picked"),
            "Ready": st.column_config.CheckboxColumn("Ready"),
            "BOL printed": st.column_config.CheckboxColumn("BOL printed"),
            "Picked up": st.column_config.CheckboxColumn("Picked up"),
            "Notes": st.column_config.TextColumn("Notes"),
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

            # check status checkboxes
            for col, db_col in [("Picked", "picked"), ("Ready", "ready"),
                                  ("BOL printed", "bol_printed"), ("Picked up", "picked_up")]:
                if col in row and bool(row[col]) != bool(orig[col]):
                    updates[db_col] = bool(row[col])

            # check notes
            if str(row.get("Notes", "")) != str(orig.get("Notes", "")):
                updates["notes"] = str(row.get("Notes", ""))

            # check pickup date
            new_date_str = str(row.get("Pickup date", "")).strip()
            orig_date_str = str(orig.get("Pickup date", "")).strip()
            if new_date_str != orig_date_str and new_date_str:
                try:
                    parsed = pd.to_datetime(new_date_str).strftime("%Y-%m-%d")
                    updates["pickup_date"] = parsed
                except:
                    pass

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

st.caption("Check/uncheck status boxes directly. Edit pickup date and notes inline. Use sidebar to edit carrier, pallets, cartons.")
