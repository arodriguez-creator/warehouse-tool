import gspread
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")
st.title("Inbound containers")
st.caption("Live from Brodiaea Operations — Inbound tab")

def get_creds():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

@st.cache_data(ttl=60)
def load_data():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Inbound")
    df = pd.DataFrame(sheet.get_all_values())
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df = df.loc[:, df.columns != '']
    df["_row_num"] = range(2, len(df) + 2)
    return df

@st.cache_data(ttl=60)
def load_dock_data():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Dock_Status")
    df = pd.DataFrame(sheet.get_all_values())
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df = df.loc[:, df.columns != '']
    df["_row_num"] = range(2, len(df) + 2)
    return df

def get_sheet():
    gc = gspread.authorize(get_creds())
    return gc.open("Brodiaea Operations").worksheet("Inbound")

def get_dock_sheet():
    gc = gspread.authorize(get_creds())
    return gc.open("Brodiaea Operations").worksheet("Dock_Status")

def parse_date(val):
    if not val or str(val).strip() == "":
        return pd.NaT
    for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%-m/%-d/%Y", "%-m/%-d/%y"]:
        try:
            return pd.to_datetime(val, format=fmt)
        except:
            pass
    return pd.to_datetime(val, errors="coerce")

all_headers = get_sheet().row_values(1)

def col_letter(col_name):
    idx = all_headers.index(col_name)
    return chr(ord('A') + idx)

received_col = col_letter("RECEIVED")
picked_up_col = col_letter("PICKED UP")
dock_door_col = col_letter("DOCK DOOR")
status_col = col_letter("CONTAINER STATUS")
trucking_col = col_letter("TRUCKING COMPANY")
account_col = col_letter("ACCOUNT")
sku_col = col_letter("SKU Count")
carton_col = col_letter("Carton Count")
warehouse_col = col_letter("WAREHOUSE")

def get_active_df():
    df = load_data()
    df["Arrival date"] = df["Arrival date"].apply(parse_date)
    df = df[df["PICKED UP"] != "TRUE"]
    df = df[df["EMPTY"] != "TRUE"]
    df = df[df["Arrival date"].notna()]
    df = df[df["CONTAINER"].str.strip() != ""]
    cutoff = datetime.today() - timedelta(days=14)
    df = df[df["Arrival date"] >= cutoff]
    df = df.sort_values("Arrival date", ascending=False)
    return df

# --- sidebar --- everything inside this block stays in the sidebar
with st.sidebar:
    st.subheader("Container actions")

    df_all = get_active_df()
    container_options = df_all["CONTAINER"].tolist()

    if container_options:
        selected_container = st.selectbox("Select container", container_options)
        sel_row = df_all[df_all["CONTAINER"] == selected_container].iloc[0]
        row_num = int(sel_row["_row_num"])

        received = sel_row["RECEIVED"] == "TRUE"
        picked = sel_row["PICKED UP"] == "TRUE"
        empty = sel_row["EMPTY"] == "TRUE"

        st.markdown("**Quick actions**")

        if empty:
            st.success("Container empty")
        else:
            if st.button("Mark empty", type="primary", use_container_width=True):
                sheet = get_sheet()
                today_str = datetime.today().strftime("%-m/%-d/%Y")
                sheet.update(f"G{row_num}", [["TRUE"]])
                sheet.update(f"H{row_num}", [[today_str]])
                st.cache_data.clear()
                st.success(f"{selected_container} marked empty")
                st.rerun()

    if received:
        st.success("Received")
    else:
        if st.button("Mark received", type="primary", use_container_width=True):
            sheet = get_sheet()
            sheet.update(f"{received_col}{row_num}", [["TRUE"]])
            st.cache_data.clear()
            st.success(f"{selected_container} marked received")
            st.rerun()

    if picked:
        st.success("Picked up")
    else:
        if st.button("Mark picked up", use_container_width=True):
            sheet = get_sheet()
            sheet.update(f"{picked_up_col}{row_num}", [["TRUE"]])
            st.cache_data.clear()
            st.success(f"{selected_container} marked picked up")
            st.rerun()

        st.divider()
        st.markdown("**Edit details**")

        current_status = str(sel_row.get("CONTAINER STATUS", "")).strip()
        current_dock = str(sel_row.get("DOCK DOOR", "")).strip()
        current_trucking = str(sel_row.get("TRUCKING COMPANY", "")).strip()
        current_account = str(sel_row.get("ACCOUNT", "")).strip()
        current_sku = str(sel_row.get("SKU Count", "")).strip()
        current_carton = str(sel_row.get("Carton Count", "")).strip()
        current_warehouse = str(sel_row.get("WAREHOUSE", "")).strip()

        status_options = ["", "In dock", "picked up", "scheduled"]
        status_index = status_options.index(current_status) if current_status in status_options else 0

        new_status = st.selectbox("Container status", status_options, index=status_index)
        new_dock = st.text_input("Dock door", value=current_dock if current_dock != "nan" else "")
        new_trucking = st.text_input("Trucking company", value=current_trucking if current_trucking != "nan" else "")
        new_account = st.text_input("Account", value=current_account if current_account != "nan" else "")
        new_sku = st.number_input("SKU count", min_value=0, step=1, value=int(current_sku) if current_sku.isdigit() else 0)
        new_carton = st.number_input("Carton count", min_value=0, step=1, value=int(current_carton) if current_carton.isdigit() else 0)
        new_warehouse = st.text_input("Warehouse", value=current_warehouse if current_warehouse != "nan" else "")

        if st.button("Save changes", type="primary"):
            dock_warning = False

            if new_dock and new_dock != current_dock:
                dock_df = load_dock_data()
                matching = dock_df[dock_df["Door"] == f"Door {new_dock}"] if "Door" in dock_df.columns else pd.DataFrame()
                if not matching.empty:
                    door_status = str(matching.iloc[0].get("Status", "")).strip().lower()
                    door_container = str(matching.iloc[0].get("Container #/Trailer", "")).strip()
                    if "occupied" in door_status and door_container and door_container != "nan":
                        st.warning(f"Door {new_dock} is already occupied by {door_container}. Save anyway?")
                        dock_warning = True

            if not dock_warning:
                sheet = get_sheet()
                updates = {
                    status_col: new_status,
                    dock_door_col: new_dock,
                    trucking_col: new_trucking,
                    account_col: new_account,
                    sku_col: str(new_sku),
                    carton_col: str(new_carton),
                    warehouse_col: new_warehouse,
                }
                for col, val in updates.items():
                    sheet.update(f"{col}{row_num}", [[val]])

                if new_dock:
                    dock_df = load_dock_data()
                    dock_headers = get_dock_sheet().row_values(1)
                    matching = dock_df[dock_df["Door"] == f"Door {new_dock}"] if "Door" in dock_df.columns else pd.DataFrame()
                    if not matching.empty:
                        dock_row_num = int(matching.iloc[0]["_row_num"])
                        dock_sheet = get_dock_sheet()
                        container_col_idx = dock_headers.index("Container #/Trailer") if "Container #/Trailer" in dock_headers else None
                        dock_status_col_idx = dock_headers.index("Status") if "Status" in dock_headers else None
                        if container_col_idx is not None:
                            dock_sheet.update(f"{chr(ord('A') + container_col_idx)}{dock_row_num}", [[selected_container]])
                        if dock_status_col_idx is not None:
                            dock_sheet.update(f"{chr(ord('A') + dock_status_col_idx)}{dock_row_num}", [["Occupied"]])

                st.success(f"{selected_container} updated")
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No active containers to edit")

# --- main page ---
df = get_active_df()

total = len(df)
in_dock = df[df["CONTAINER STATUS"] == "In dock"].shape[0]
not_received = df[df["RECEIVED"] != "TRUE"].shape[0]
not_billed = df[df["Billed?"] != "TRUE"].shape[0]

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
                sheet = get_sheet()
                new_row = [
                    new_arrival.strftime("%-m/%-d/%Y"),
                    new_container_num,
                    new_account,
                    new_trucking,
                    new_status,
                    new_dock_door,
                    "", "", "", "", "",
                    new_warehouse,
                    "",
                    str(int(new_sku_count)),
                    str(int(new_carton_count)),
                    ""
                ]
                sheet.append_row(new_row)
                st.success(f"Container {new_container_num} added successfully")
                st.cache_data.clear()
                st.rerun()

accounts = ["All"] + sorted(df["ACCOUNT"].dropna().unique().tolist())
selected_account = st.selectbox("Filter by account", accounts)
if selected_account != "All":
    df = df[df["ACCOUNT"] == selected_account]

display_cols = ["Arrival date", "CONTAINER", "ACCOUNT", "CONTAINER STATUS",
                "TRUCKING COMPANY", "DOCK DOOR", "SKU Count", "Carton Count",
                "RECEIVED", "WAREHOUSE"]

display_cols = [c for c in display_cols if c in df.columns]
df["Arrival date"] = df["Arrival date"].dt.strftime("%m/%d/%Y")

st.dataframe(
    df[display_cols],
    use_container_width=True,
    hide_index=True
)

st.caption("Select a container in the sidebar to mark received, picked up, or edit details. Changes write directly to Google Sheets.")
