import gspread
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from styles import GLOBAL_CSS, page_header
from auth import require_auth
require_auth()
show_user()

st.set_page_config(layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
page_header("Outbound shipments", "Live from Brodiaea Operations — MAD & Instaship")

def get_creds():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

def get_mad_sheet():
    gc = gspread.authorize(get_creds())
    return gc.open("Brodiaea Operations").worksheet("Outbound-MAD 2026")

def get_insta_sheet():
    gc = gspread.authorize(get_creds())
    return gc.open("Brodiaea Operations").worksheet("Outbound-Instaship 2026")

def safe_int(val):
    try:
        return int(str(val).replace(",", "").strip())
    except:
        return 0

def clean(val):
    return "" if not val or str(val).strip() == "nan" else str(val).strip()

@st.cache_data(ttl=120)
def load_mad():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Outbound-MAD 2026")
    data = sheet.get_all_values()
    headers = [h.strip() for h in data[1]]
    df = pd.DataFrame(data[2:], columns=headers)
    df.columns = [c.strip() for c in df.columns]
    df["_source"] = "MAD"
    df["_row_num"] = range(3, len(df) + 3)
    df = df.rename(columns={"CARTONS": "CTN", "READY FOR PU": "READY PU"})
    df["CTN"] = df["CTN"].apply(safe_int)
    df["PALLET TOTAL"] = df["PALLET TOTAL"].apply(safe_int)
    return df

@st.cache_data(ttl=120)
def load_instaship():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Outbound-Instaship 2026")
    data = sheet.get_all_values()
    headers = [h.strip() for h in data[1]]
    df = pd.DataFrame(data[2:], columns=headers)
    df.columns = [c.strip() for c in df.columns]
    df["_source"] = "Instaship"
    df["_row_num"] = range(3, len(df) + 3)
    df["APPT TIME"] = ""
    df["CTN"] = df["CTN"].apply(safe_int)
    df["PALLET TOTAL"] = df["PALLET TOTAL"].apply(safe_int)
    return df

def parse_date(val):
    if not val or str(val).strip() == "":
        return pd.NaT
    for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%-m/%-d/%Y", "%-m/%-d/%y"]:
        try:
            return pd.to_datetime(val, format=fmt)
        except:
            pass
    return pd.to_datetime(val, errors="coerce")

def load_combined():
    mad = load_mad()
    insta = load_instaship()
    shared = ["ACCOUNT", "CARRIER", "DATE", "FREIGHT TERMS", "APPT TIME",
              "CONSIGNEE", "SALES ORDER", "PO", "CTN", "PALLET TOTAL",
              "READY PU", "LOAD #", "PU", "_source", "_row_num"]
    combined = pd.concat(
        [mad[[c for c in shared if c in mad.columns]],
         insta[[c for c in shared if c in insta.columns]]],
        ignore_index=True
    )
    combined["DATE"] = combined["DATE"].apply(parse_date)
    combined = combined[combined["DATE"].notna()]
    combined = combined[combined["ACCOUNT"].str.strip() != ""]
    return combined

df = load_combined()
today = datetime.today().date()
tomorrow = today + timedelta(days=1)
df_today = df[df["DATE"].dt.date == today]

# --- sidebar ---
with st.sidebar:
    st.subheader("Shipment actions")
    action = st.radio("Action", ["Edit / Bulk update", "Assign load ID"])

    if action == "Edit / Bulk update":
        source_filter = st.selectbox("Business", ["MAD", "Instaship"])

        if source_filter == "MAD":
            edit_df = load_mad()
            carrier_col = "B"
            freight_col = "D"
            appt_col = "E"
            pallets_col = "J"
            load_col = "L"
            pu_col = "M"
            sheet_fn = get_mad_sheet
        else:
            edit_df = load_instaship()
            carrier_col = "B"
            freight_col = "D"
            appt_col = None
            pallets_col = "I"
            load_col = "K"
            pu_col = "L"
            sheet_fn = get_insta_sheet

        edit_df["DATE"] = edit_df["DATE"].apply(parse_date)
        edit_df = edit_df[edit_df["DATE"].notna()]
        edit_df = edit_df[edit_df["ACCOUNT"].str.strip() != ""]
        cutoff = pd.Timestamp(today - timedelta(days=7))
        edit_df = edit_df[edit_df["DATE"] >= cutoff]
        edit_df = edit_df.sort_values("DATE", ascending=False)
        edit_df = edit_df[edit_df["PU"].astype(str).str.strip() != "TRUE"]
        so_options = [s for s in edit_df["SALES ORDER"].dropna().tolist() if str(s).strip() != ""]

        if so_options:
            selected_orders = st.multiselect(
                "Select sales orders",
                so_options,
                help="Select one to edit details, or multiple for bulk actions"
            )

            if selected_orders:
                is_bulk = len(selected_orders) > 1
                sel_rows = edit_df[edit_df["SALES ORDER"].isin(selected_orders)]

                if is_bulk:
                    # bulk mode — show count and shared fields only
                    st.caption(f"{len(selected_orders)} orders selected")
                    st.markdown("**Bulk update fields**")
                    st.caption("Leave blank to skip that field")

                    bulk_carrier = st.text_input("Set carrier (all)", key="bulk_carrier")
                    bulk_load = st.text_input("Set load # (all)", key="bulk_load")
                    bulk_pallets_str = st.text_input("Set pallets (all)", key="bulk_pallets")

                    st.divider()
                    mark_pu = st.checkbox("Mark all as picked up", key="bulk_pu")

                    if st.button("Apply to all selected", type="primary", use_container_width=True):
                        sheet = sheet_fn()
                        updated = 0
                        for _, row in sel_rows.iterrows():
                            rn = int(row["_row_num"])
                            if bulk_carrier.strip():
                                sheet.update(f"{carrier_col}{rn}", [[bulk_carrier.strip()]])
                            if bulk_load.strip():
                                sheet.update(f"{load_col}{rn}", [[bulk_load.strip()]])
                            if bulk_pallets_str.strip().isdigit():
                                sheet.update(f"{pallets_col}{rn}", [[bulk_pallets_str.strip()]])
                            if mark_pu:
                                sheet.update(f"{pu_col}{rn}", [["TRUE"]])
                            updated += 1
                        st.cache_data.clear()
                        st.success(f"Updated {updated} shipments")
                        st.rerun()

                else:
                    # single mode — full edit form with pre-filled values
                    selected_so = selected_orders[0]
                    sel_row = sel_rows.iloc[0]
                    row_num = int(sel_row["_row_num"])
                    k = selected_so.replace(" ", "_")

                    current_carrier = clean(sel_row.get("CARRIER", ""))
                    current_pallets = sel_row.get("PALLET TOTAL", 0)
                    current_load = clean(sel_row.get("LOAD #", ""))
                    current_freight = clean(sel_row.get("FREIGHT TERMS", ""))
                    current_appt = clean(sel_row.get("APPT TIME", ""))
                    is_picked_up = str(sel_row.get("PU", "")).strip() == "TRUE"

                    st.markdown("**Edit details**")
                    new_carrier = st.text_input("Carrier", value=current_carrier, key=f"carrier_{k}")
                    new_freight = st.text_input("Freight terms", value=current_freight, key=f"freight_{k}")
                    if appt_col:
                        new_appt = st.text_input("Appt time", value=current_appt, key=f"appt_{k}")
                    new_pallets = st.number_input("Pallet total", min_value=0, step=1,
                                                   value=int(current_pallets) if str(current_pallets).isdigit() else 0,
                                                   key=f"pallets_{k}")
                    new_load = st.text_input("Load #", value=current_load, key=f"load_{k}")

                    if st.button("Save changes", type="primary", use_container_width=True, key=f"save_{k}"):
                        sheet = sheet_fn()
                        sheet.update(f"{carrier_col}{row_num}", [[new_carrier]])
                        sheet.update(f"{freight_col}{row_num}", [[new_freight]])
                        sheet.update(f"{pallets_col}{row_num}", [[str(new_pallets)]])
                        sheet.update(f"{load_col}{row_num}", [[new_load]])
                        if appt_col:
                            sheet.update(f"{appt_col}{row_num}", [[new_appt]])
                        st.cache_data.clear()
                        st.success(f"{selected_so} updated")
                        st.rerun()

                    st.divider()
                    if is_picked_up:
                        st.success("Picked up ✓")
                    else:
                        if st.button("Mark picked up", use_container_width=True, key=f"pu_{k}"):
                            sheet = sheet_fn()
                            sheet.update(f"{pu_col}{row_num}", [["TRUE"]])
                            st.cache_data.clear()
                            st.success(f"{selected_so} marked picked up")
                            st.rerun()
            else:
                st.caption("Select one or more sales orders above")
        else:
            st.info("No shipments found in the last 7 days")

    else:
        st.markdown("**Assign load ID to multiple orders**")
        st.caption("Select orders that share a carrier pickup")
        load_source = st.selectbox("Business", ["MAD", "Instaship"])
        new_load_id = st.text_input("Load ID (from carrier)")

        if load_source == "MAD":
            load_df = load_mad()
            load_col = "L"
            sheet_fn = get_mad_sheet
        else:
            load_df = load_instaship()
            load_col = "K"
            sheet_fn = get_insta_sheet

        load_df["DATE"] = load_df["DATE"].apply(parse_date)
        load_df = load_df[load_df["DATE"].notna()]
        load_df = load_df[load_df["ACCOUNT"].str.strip() != ""]
        cutoff = pd.Timestamp(today - timedelta(days=7))
        load_df = load_df[load_df["DATE"] >= cutoff]
        load_df = load_df.sort_values("DATE", ascending=False)
        so_list = [s for s in load_df["SALES ORDER"].dropna().tolist() if str(s).strip() != ""]
        selected_orders_load = st.multiselect("Select sales orders", so_list)

        if st.button("Assign load ID", type="primary", use_container_width=True):
            if not new_load_id:
                st.error("Enter a load ID first")
            elif not selected_orders_load:
                st.error("Select at least one order")
            else:
                sheet = sheet_fn()
                for so in selected_orders_load:
                    match = load_df[load_df["SALES ORDER"] == so]
                    if not match.empty:
                        rn = int(match.iloc[0]["_row_num"])
                        sheet.update(f"{load_col}{rn}", [[new_load_id]])
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
                date_str = new_date.strftime("%-m/%-d/%Y")
                if new_business == "MAD":
                    sheet = get_mad_sheet()
                    new_row = [new_account, new_carrier, date_str, new_freight,
                               new_appt, new_consignee, new_so, new_po,
                               str(new_ctn), str(new_pallets), "", new_load, "", "", ""]
                else:
                    sheet = get_insta_sheet()
                    new_row = [new_account, new_carrier, date_str, new_freight,
                               new_consignee, new_so, new_po, str(new_ctn),
                               str(new_pallets), "", new_load, "", "", ""]
                sheet.append_row(new_row)
                st.cache_data.clear()
                st.success(f"Shipment {new_so} added to {new_business}")
                st.rerun()

# --- metrics ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Shipments today", len(df_today))
col2.metric("MAD today", len(df_today[df_today["_source"] == "MAD"]))
col3.metric("Instaship today", len(df_today[df_today["_source"] == "Instaship"]))
col4.metric("Total cartons", f"{df_today['CTN'].sum():,}")
col5.metric("Total pallets", df_today["PALLET TOTAL"].sum())

# --- filters ---
st.subheader("Shipment log")
date_options = ["Today", "Tomorrow", "Last 7 days", "All"]
selected_range = st.radio("Show", date_options, horizontal=True)

if selected_range == "Today":
    view_df = df_today.copy()
elif selected_range == "Tomorrow":
    view_df = df[df["DATE"].dt.date == tomorrow].copy()
elif selected_range == "Last 7 days":
    cutoff = pd.Timestamp(today - timedelta(days=7))
    view_df = df[df["DATE"] >= cutoff].copy()
else:
    view_df = df.copy()

fc1, fc2, fc3 = st.columns(3)
sources = ["All"] + sorted(view_df["_source"].unique().tolist())
selected_source = fc1.selectbox("Business", sources)
accounts = ["All"] + sorted(view_df["ACCOUNT"].dropna().unique().tolist())
selected_account = fc2.selectbox("Account", accounts)
carriers = ["All"] + sorted(view_df["CARRIER"].dropna().unique().tolist())
selected_carrier = fc3.selectbox("Carrier", carriers)

if selected_source != "All":
    view_df = view_df[view_df["_source"] == selected_source]
if selected_account != "All":
    view_df = view_df[view_df["ACCOUNT"] == selected_account]
if selected_carrier != "All":
    view_df = view_df[view_df["CARRIER"] == selected_carrier]

if len(view_df) > 0:
    s1, s2, s3 = st.columns(3)
    s1.caption(f"{len(view_df)} shipments")
    s2.caption(f"{view_df['CTN'].sum():,} cartons")
    s3.caption(f"{view_df['PALLET TOTAL'].sum()} pallets")

display_cols = ["_source", "DATE", "ACCOUNT", "CARRIER", "FREIGHT TERMS",
                "CONSIGNEE", "SALES ORDER", "PO", "CTN", "PALLET TOTAL",
                "LOAD #", "PU", "APPT TIME"]
display_cols = [c for c in display_cols if c in view_df.columns]
view_df["DATE"] = view_df["DATE"].dt.strftime("%m/%d/%Y")
view_df = view_df.rename(columns={"_source": "Business"})
display_cols = ["Business"] + [c for c in display_cols if c not in ["_source", "Business"]]

st.dataframe(view_df[display_cols], use_container_width=True, hide_index=True)
st.caption("Click any column header to sort. Data refreshes every 2 minutes.")