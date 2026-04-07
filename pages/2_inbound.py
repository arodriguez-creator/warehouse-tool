import gspread
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import json
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")
st.title("Inbound containers")
st.caption("Live from Brodiaea Operations — Inbound tab")

@st.cache_data(ttl=300)
def load_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(creds)
    sheet = gc.open("Brodiaea Operations").worksheet("Inbound")
    df = pd.DataFrame(sheet.get_all_values())
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df = df.loc[:, df.columns != '']
    df["_row_num"] = range(2, len(df) + 2)
    return df

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(creds)
    return gc.open("Brodiaea Operations").worksheet("Inbound")

def get_sheet_inbound():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(creds)
    return gc.open("Brodiaea Operations").worksheet("Inbound")

def mark_column(row_num, col_letter):
    sheet = get_sheet()
    sheet.update(f"{col_letter}{row_num}", [["TRUE"]])
    st.cache_data.clear()

df = load_data()

# figure out which column letter maps to RECEIVED and PICKED UP
all_headers = get_sheet().row_values(1)
def col_letter(col_name):
    idx = all_headers.index(col_name)
    return chr(ord('A') + idx)

received_col = col_letter("RECEIVED")
picked_up_col = col_letter("PICKED UP")

# filters
def parse_date(val):
    if not val or str(val).strip() == "":
        return pd.NaT
    for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%-m/%-d/%Y", "%-m/%-d/%y"]:
        try:
            return pd.to_datetime(val, format=fmt)
        except:
            pass
    return pd.to_datetime(val, errors="coerce")

df["Arrival date"] = df["Arrival date"].apply(parse_date)

df = df[df["PICKED UP"] != "TRUE"]
df = df[df["EMPTY"] != "TRUE"]
df = df[df["Arrival date"].notna()]
df = df[df["CONTAINER"].str.strip() != ""]
cutoff = datetime.today() - timedelta(days=14)
df = df[df["Arrival date"] >= cutoff]
df = df.sort_values("Arrival date", ascending=False)

# metrics
total = len(df)
in_dock = df[df["CONTAINER STATUS"] == "In dock"].shape[0]
not_received = df[df["RECEIVED"] != "TRUE"].shape[0]
not_billed = df[df["Billed?"] != "TRUE"].shape[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Active containers", total)
col2.metric("In dock", in_dock)
col3.metric("Not yet received", not_received)
col4.metric("Not yet billed", not_billed)

# account filter
if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()
st.subheader("Active container log")
with st.expander("Add new inbound container"):
    with st.form("new_container"):
        st.markdown("**New container entry**")

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
                sheet = get_sheet_inbound()
                new_row = [
                    new_arrival.strftime("%-m/%-d/%Y"),              # Arrival date
                    new_container_num,       # Container
                    new_account,             # Account
                    new_trucking,            # Trucking company
                    new_status,              # Container status
                    new_dock_door,           # Dock door
                    "",                      # Empty
                    "",                      # Empty timestamp
                    "",                      # Empty report sent
                    "",                      # Received
                    "",                      # Picked up
                    new_warehouse,           # Warehouse
                    "",                      # Sent documents
                    str(int(new_sku_count)), # SKU count
                    str(int(new_carton_count)), # Carton count
                    ""                       # Billed
]
                
                sheet.append_row(new_row)
                st.success(f"Container {new_container_num} added successfully")
                st.cache_data.clear()
                st.rerun()

accounts = ["All"] + sorted(df["ACCOUNT"].dropna().unique().tolist())
selected_account = st.selectbox("Filter by account", accounts)
if selected_account != "All":
    df = df[df["ACCOUNT"] == selected_account]

# table with action buttons
header = st.columns([1.5, 2, 1.5, 1.5, 1.5, 1, 1])
header[0].markdown("**Arrival date**")
header[1].markdown("**Container**")
header[2].markdown("**Account**")
header[3].markdown("**Status**")
header[4].markdown("**Carrier**")
header[5].markdown("**Received**")
header[6].markdown("**Picked up**")

st.divider()

for _, row in df.iterrows():
    c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 2, 1.5, 1.5, 1.5, 1, 1])
    c1.write(str(row["Arrival date"])[:10])
    c2.write(row["CONTAINER"])
    c3.write(row["ACCOUNT"])
    c4.write(row["CONTAINER STATUS"])
    c5.write(row.get("TRUCKING COMPANY", ""))

    received = row["RECEIVED"] == "TRUE"
    picked = row["PICKED UP"] == "TRUE"
    row_num = int(row["_row_num"])

    if received:
        c6.success("Done")
    else:
        if c6.button("Received", key=f"rec_{row_num}"):
            mark_column(row_num, received_col)
            st.rerun()

    if picked:
        c7.success("Done")
    else:
        if c7.button("Picked up", key=f"pick_{row_num}"):
            mark_column(row_num, picked_up_col)
            st.rerun()

st.caption("Changes write directly to Google Sheets. Refreshes every 5 minutes or on action.")