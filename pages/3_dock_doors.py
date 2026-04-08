import gspread
import pandas as pd
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from styles import GLOBAL_CSS, page_header
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
page_header("Dock door board", "Live from Brodiaea Operations — Dock_Status tab")

def get_creds():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

@st.cache_data(ttl=60)
def load_data():
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
    return gc.open("Brodiaea Operations").worksheet("Dock_Status")

def clean(val):
    return "" if not val or str(val).strip() == "nan" else str(val).strip()

def get_door_type(status, unloading, container):
    status = str(status).strip().lower()
    unloading = str(unloading).strip().lower()
    container = str(container).strip()
    reserved = ["ramp", "trash", "cardboard", "pallets", "fedex fround", "ups"]
    if any(r in container.lower() for r in reserved):
        return "reserved"
    if "vacant" in status:
        return "vacant"
    if "full" in unloading:
        return "full"
    if "unload" in unloading or "loading" in unloading:
        return "unloading"
    return "occupied"

color_map = {
    "vacant":    {"bg": "#EAF3DE", "border": "#3B6D11", "text": "#27500A", "label": "Vacant"},
    "occupied":  {"bg": "#FCEBEB", "border": "#A32D2D", "text": "#791F1F", "label": "Occupied"},
    "unloading": {"bg": "#E6F1FB", "border": "#185FA5", "text": "#0C447C", "label": "Unloading"},
    "reserved":  {"bg": "#F1EFE8", "border": "#5F5E5A", "text": "#444441", "label": "Reserved"},
    "full":      {"bg": "#FAEEDA", "border": "#854F0B", "text": "#633806", "label": "Full"},
}

df = load_data()
headers = get_sheet().row_values(1)

with st.sidebar:
    st.subheader("Update a door")
    door_options = df["Door"].tolist() if "Door" in df.columns else [f"Door {i}" for i in range(1, 36)]
    selected_door = st.selectbox("Select door", door_options, key="door_select")

    door_row = df[df["Door"] == selected_door].iloc[0] if "Door" in df.columns and not df[df["Door"] == selected_door].empty else None

    if door_row is not None:
        row_num = int(door_row["_row_num"])
        k = selected_door.replace(" ", "_")

        current_container = clean(door_row.get("Container #/Trailer", ""))
        current_status = clean(door_row.get("Status", ""))
        current_unloading = clean(door_row.get("Unloading/Empty", ""))
        current_customer = clean(door_row.get("CUSTOMER", ""))
        current_carrier = clean(door_row.get("Carrier", ""))

        unloading_options = ["", "Unloading", "Full", "Loading"]
        unloading_index = unloading_options.index(current_unloading) if current_unloading in unloading_options else 0

        new_container = st.text_input("Container / trailer", value=current_container, key=f"container_{k}")
        new_status = st.selectbox("Status", ["Vacant", "Occupied"],
                                   index=0 if "vacant" in current_status.lower() else 1,
                                   key=f"status_{k}")
        new_unloading = st.selectbox("Unloading / empty", unloading_options,
                                      index=unloading_index, key=f"unload_{k}")
        new_customer = st.text_input("Customer", value=current_customer, key=f"customer_{k}")
        new_carrier = st.text_input("Carrier", value=current_carrier, key=f"carrier_{k}")

        if st.button("Save changes", type="primary", use_container_width=True, key=f"save_{k}"):
            sheet = get_sheet()
            updates = {}
            if "Container #/Trailer" in headers:
                updates[chr(ord('A') + headers.index("Container #/Trailer"))] = new_container
            if "Status" in headers:
                updates[chr(ord('A') + headers.index("Status"))] = new_status
            if "Unloading/Empty" in headers:
                updates[chr(ord('A') + headers.index("Unloading/Empty"))] = new_unloading
            if "CUSTOMER" in headers:
                updates[chr(ord('A') + headers.index("CUSTOMER"))] = new_customer
            if "Carrier" in headers:
                updates[chr(ord('A') + headers.index("Carrier"))] = new_carrier
            for col_letter, value in updates.items():
                sheet.update(f"{col_letter}{row_num}", [[value]])
            st.success(f"{selected_door} updated")
            st.cache_data.clear()
            st.rerun()

        if st.button("Clear door", use_container_width=True, key=f"clear_{k}"):
            sheet = get_sheet()
            for col_name in ["Container #/Trailer", "Unloading/Empty", "CUSTOMER", "Carrier"]:
                if col_name in headers:
                    col = chr(ord('A') + headers.index(col_name))
                    sheet.update(f"{col}{row_num}", [[""]])
            if "Status" in headers:
                status_col = chr(ord('A') + headers.index("Status"))
                sheet.update(f"{status_col}{row_num}", [["Vacant"]])
            st.success(f"{selected_door} cleared")
            st.cache_data.clear()
            st.rerun()

# --- metrics ---
total = len(df)
def door_type_series(row):
    return get_door_type(row.get("Status", ""), row.get("Unloading/Empty", ""), row.get("Container #/Trailer", ""))

types = df.apply(door_type_series, axis=1)
occupied_count = types.isin(["occupied", "full", "unloading"]).sum()
vacant_count = types.eq("vacant").sum()
utilization = round((occupied_count / total) * 100) if total > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total doors", total)
col2.metric("Occupied", occupied_count)
col3.metric("Vacant", vacant_count)
col4.metric("Utilization", f"{utilization}%")

if st.button("Refresh board"):
    st.cache_data.clear()
    st.rerun()

st.markdown("""
<div style="display:flex;gap:16px;flex-wrap:wrap;margin:1rem 0;">
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--color-text-secondary)"><span style="width:10px;height:10px;border-radius:2px;background:#639922;display:inline-block"></span>Vacant</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--color-text-secondary)"><span style="width:10px;height:10px;border-radius:2px;background:#E24B4A;display:inline-block"></span>Occupied</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--color-text-secondary)"><span style="width:10px;height:10px;border-radius:2px;background:#378ADD;display:inline-block"></span>Unloading</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--color-text-secondary)"><span style="width:10px;height:10px;border-radius:2px;background:#888780;display:inline-block"></span>Reserved</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--color-text-secondary)"><span style="width:10px;height:10px;border-radius:2px;background:#EF9F27;display:inline-block"></span>Full</span>
</div>
""", unsafe_allow_html=True)

cols = st.columns(7)
for i, row in df.iterrows():
    door_label = str(row.get("Door", f"Door {i+1}")).strip()
    container = str(row.get("Container #/Trailer", "")).strip()
    status_raw = str(row.get("Status", "")).strip()
    unloading = str(row.get("Unloading/Empty", "")).strip()
    door_type = get_door_type(status_raw, unloading, container)
    c = color_map[door_type]
    col = cols[i % 7]
    display_name = container if container and container != "nan" else ""
    display_sub = unloading if unloading and unloading != "nan" and door_type != "reserved" else c["label"]
    with col:
        st.markdown(f"""
        <div style="background:{c['bg']};border:0.5px solid {c['border']};border-radius:8px;
                    padding:10px 8px;min-height:80px;margin-bottom:8px;
                    display:flex;flex-direction:column;justify-content:space-between;">
          <span style="font-size:10px;font-weight:500;color:{c['text']}">{door_label}</span>
          <span style="font-size:10px;font-weight:500;color:{c['text']};word-break:break-all;margin-top:4px">{display_name}</span>
          <span style="font-size:9px;color:{c['text']};margin-top:2px">{display_sub}</span>
        </div>
        """, unsafe_allow_html=True)

st.caption("Select a door in the left panel to update its status. Changes save directly to Google Sheets.")
