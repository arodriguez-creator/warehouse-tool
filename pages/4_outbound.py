import gspread
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")
st.title("Outbound shipments")
st.caption("Live from Brodiaea Operations — MAD & Instaship")

st.markdown("""
<style>
  [data-testid="stMetric"] {
      background: #ffffff;
      border: 1.5px solid #d1d5db;
      border-radius: 10px;
      padding: 1rem 1.25rem;
      box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  }
</style>
""", unsafe_allow_html=True)

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

@st.cache_data(ttl=120)
def load_mad():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Outbound-MAD 2026")
    data = sheet.get_all_values()
    headers = [h.strip() for h in data[1]]
    rows = data[2:]
    df = pd.DataFrame(rows, columns=headers)
    df = df.loc[:, df.columns != '']
    df.columns = [c.strip() for c in df.columns]
    df["_source"] = "MAD"
    df["_row_num"] = range(3, len(df) + 3)
    df = df.rename(columns={"CARTONS": "CTN", "READY FOR PU": "READY PU",
                             "FREIGHT TERMS": "FREIGHT TERMS", "SALES ORDER": "SALES ORDER"})
    df["CTN"] = df["CTN"].apply(safe_int)
    df["PALLET TOTAL"] = df["PALLET TOTAL"].apply(safe_int)
    return df

@st.cache_data(ttl=120)
def load_instaship():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Outbound-Instaship 2026")
    data = sheet.get_all_values()
    headers = [h.strip() for h in data[1]]
    rows = data[2:]
    df = pd.DataFrame(rows, columns=headers)
    df = df.loc[:, df.columns != '']
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
    mad_cols = [c for c in shared if c in mad.columns]
    insta_cols = [c for c in shared if c in insta.columns]
    combined = pd.concat([mad[mad_cols], insta[insta_cols]], ignore_index=True)
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
    action = st.radio("Action", ["Edit shipment", "Assign load ID"], label_visibility="collapsed")

    if action == "Edit shipment":
        st.markdown("**Edit shipment**")
        source_filter = st.selectbox("Business", ["MAD", "Instaship"])

        if source_filter == "MAD":
            edit_df = load_mad()
            edit_df["DATE"] = edit_df["DATE"].apply(parse_date)
            edit_df = edit_df[edit_df["DATE"].notna()]
            edit_df = edit_df[edit_df["ACCOUNT"].str.strip() != ""]
            cutoff = pd.Timestamp(today - timedelta(days=7))
            edit_df = edit_df[edit_df["DATE"] >= cutoff]
            so_col = "SALES ORDER"
            carrier_col = "B"
            pallets_col = "J"
            load_col = "L"
            freight_col = "D"
            appt_col = "E"
            sheet_fn = get_mad_sheet
        else:
            edit_df = load_instaship()
            edit_df["DATE"] = edit_df["DATE"].apply(parse_date)
            edit_df = edit_df[edit_df["DATE"].notna()]
            edit_df = edit_df[edit_df["ACCOUNT"].str.strip() != ""]
            cutoff = pd.Timestamp(today - timedelta(days=7))
            edit_df = edit_df[edit_df["DATE"] >= cutoff]
            so_col = "SALES ORDER"
            carrier_col = "B"
            pallets_col = "I"
            load_col = "K"
            freight_col = "D"
            appt_col = None
            sheet_fn = get_insta_sheet

        edit_df = edit_df.sort_values("DATE", ascending=False)
        so_options = edit_df["SALES ORDER"].dropna().tolist()
        so_options = [s for s in so_options if str(s).strip() != ""]

        if so_options:
            selected_so = st.selectbox("Select sales order", so_options)
            sel_row = edit_df[edit_df["SALES ORDER"] == selected_so].iloc[0]
            row_num = int(sel_row["_row_num"])

            current_carrier = str(sel_row.get("CARRIER", "")).strip()
            current_pallets = sel_row.get("PALLET TOTAL", 0)
            current_load = str(sel_row.get("LOAD #", "")).strip()
            current_freight = str(sel_row.get("FREIGHT TERMS", "")).strip()
            current_appt = str(sel_row.get("APPT TIME", "")).strip()

            new_carrier = st.text_input("Carrier", value=current_carrier if current_carrier != "nan" else "")
            new_freight = st.text_input("Freight terms", value=current_freight if current_freight != "nan" else "")
            if appt_col:
                new_appt = st.text_input("Appt time", value=current_appt if current_appt != "nan" else "")
            new_pallets = st.number_input("Pallet total", min_value=0, step=1,
                                          value=int(current_pallets) if str(current_pallets).isdigit() else 0)
            new_load = st.text_input("Load #", value=current_load if current_load != "nan" else "")

            if st.button("Save changes", type="primary", use_container_width=True):
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

        so_list = load_df["SALES ORDER"].dropna().tolist()
        so_list = [s for s in so_list if str(s).strip() != ""]

        selected_orders = st.multiselect("Select sales orders", so_list)

        if st.button("Assign load ID", type="primary", use_container_width=True):
            if not new_load_id:
                st.error("Enter a load ID first")
            elif not selected_orders:
                st.error("Select at least one order")
            else:
                sheet = sheet_fn()
                for so in selected_orders:
                    match = load_df[load_df["SALES ORDER"] == so]
                    if not match.empty:
                        rn = int(match.iloc[0]["_row_num"])
                        sheet.update(f"{load_col}{rn}", [[new_load_id]])
                st.cache_data.clear()
                st.success(f"Load ID {new_load_id} assigned to {len(selected_orders)} orders")
                st.rerun()

# --- add new shipment expander ---
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
                    new_row = [
                        new_account, new_carrier, date_str,
                        new_freight, new_appt, new_consignee,
                        new_so, new_po, str(new_ctn), str(new_pallets),
                        "", new_load, "", "", ""
                    ]
                else:
                    sheet = get_insta_sheet()
                    new_row = [
                        new_account, new_carrier, date_str,
                        new_freight, new_consignee, new_so,
                        new_po, str(new_ctn), str(new_pallets),
                        "", new_load, "", "", ""
                    ]
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
                "CONSIGNEE", "SALES ORDER", "PO", "CTN",
                "PALLET TOTAL", "LOAD #", "APPT TIME"]
display_cols = [c for c in display_cols if c in view_df.columns]
view_df["DATE"] = view_df["DATE"].dt.strftime("%m/%d/%Y")
view_df = view_df.rename(columns={"_source": "Business"})
display_cols = ["Business"] + [c for c in display_cols if c not in ["_source", "Business"]]

st.dataframe(view_df[display_cols], use_container_width=True, hide_index=True)
st.caption("Click any column header to sort. Data refreshes every 2 minutes.")
