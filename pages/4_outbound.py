import gspread
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")
st.title("Outbound shipments")
st.caption("Live from Brodiaea Operations — MAD & Instaship")

def get_creds():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

@st.cache_data(ttl=120)
def load_mad():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Outbound-MAD 2026")
    data = sheet.get_all_values()
    headers = [h.strip() for h in data[1]]
    df = pd.DataFrame(data[2:], columns=headers)
    df = df.loc[:, df.columns != '']
    df["_source"] = "MAD"
    df = df.rename(columns={"CARTONS": "CTN", "READY FOR PU": "READY PU"})
    return df

@st.cache_data(ttl=120)
def load_instaship():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Outbound-Instaship 2026")
    data = sheet.get_all_values()
    headers = [h.strip() for h in data[1]]
    df = pd.DataFrame(data[2:], columns=headers)
    df = df.loc[:, df.columns != '']
    df["_source"] = "Instaship"
    df["APPT TIME"] = ""
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
              "READY PU", "LOAD #", "PU", "_source"]

    # normalize column names — strip spaces
    mad.columns = [c.strip() for c in mad.columns]
    insta.columns = [c.strip() for c in insta.columns]

    # keep only shared cols that exist
    mad_cols = [c for c in shared if c in mad.columns]
    insta_cols = [c for c in shared if c in insta.columns]

    combined = pd.concat([mad[mad_cols], insta[insta_cols]], ignore_index=True)
    combined["DATE"] = combined["DATE"].apply(parse_date)
    combined = combined[combined["DATE"].notna()]
    combined = combined[combined["ACCOUNT"].str.strip() != ""]
    combined["CTN"] = pd.to_numeric(combined["CTN"], errors="coerce").fillna(0).astype(int)
    combined["PALLET TOTAL"] = pd.to_numeric(combined["PALLET TOTAL"], errors="coerce").fillna(0).astype(int)
    return combined

df = load_combined()

today = datetime.today().date()
tomorrow = today + timedelta(days=1)

df_today = df[df["DATE"].dt.date == today]
df_tomorrow = df[df["DATE"].dt.date == tomorrow]

# --- metrics ---
total_today = len(df_today)
mad_today = len(df_today[df_today["_source"] == "MAD"])
insta_today = len(df_today[df_today["_source"] == "Instaship"])
total_cartons = df_today["CTN"].sum()
total_pallets = df_today["PALLET TOTAL"].sum()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Shipments today", total_today)
col2.metric("MAD", mad_today)
col3.metric("Instaship", insta_today)
col4.metric("Total cartons", f"{total_cartons:,}")
col5.metric("Total pallets", total_pallets)

if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

# --- date range selector ---
st.subheader("Shipment log")
date_options = ["Today", "Tomorrow", "Last 7 days", "All"]
selected_range = st.radio("Show", date_options, horizontal=True)

if selected_range == "Today":
    view_df = df_today.copy()
elif selected_range == "Tomorrow":
    view_df = df_tomorrow.copy()
elif selected_range == "Last 7 days":
    cutoff = pd.Timestamp(today - timedelta(days=7))
    view_df = df[df["DATE"] >= cutoff].copy()
else:
    view_df = df.copy()

# --- filters ---
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

# --- summary bar ---
if len(view_df) > 0:
    s1, s2, s3 = st.columns(3)
    s1.caption(f"{len(view_df)} shipments")
    s2.caption(f"{view_df['CTN'].sum():,} cartons")
    s3.caption(f"{view_df['PALLET TOTAL'].sum()} pallets")

# --- table ---
display_cols = ["_source", "DATE", "ACCOUNT", "CARRIER", "FREIGHT TERMS",
                "CONSIGNEE", "SALES ORDER", "PO", "CTN",
                "PALLET TOTAL", "LOAD #", "APPT TIME"]
display_cols = [c for c in display_cols if c in view_df.columns]

view_df["DATE"] = view_df["DATE"].dt.strftime("%m/%d/%Y")
view_df = view_df.rename(columns={"_source": "Business"})
display_cols = [c if c != "_source" else "Business" for c in display_cols]
display_cols = ["Business"] + [c for c in display_cols if c != "Business"]

st.dataframe(
    view_df[display_cols],
    use_container_width=True,
    hide_index=True
)

st.caption("Data refreshes every 2 minutes. Click any column header to sort.")
