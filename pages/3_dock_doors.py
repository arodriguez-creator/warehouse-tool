import pandas as pd
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from styles import GLOBAL_CSS, page_header
from auth import require_auth, show_user, get_db

require_auth()
show_user()

st.set_page_config(layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
page_header("Dock door board", "Live from Supabase — Dock Status")

def clean(val):
    return "" if not val or str(val) == "nan" or val is None else str(val).strip()

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

@st.cache_data(ttl=60)
def load_data():
    db = get_db()
    result = db.table("dock_status").select("*").order("door").execute()
    return pd.DataFrame(result.data)

df = load_data()

# --- sidebar ---
with st.sidebar:
    st.subheader("Update a door")

    door_options = df["door"].tolist() if not df.empty else [f"Door {i}" for i in range(1, 36)]
    selected_door = st.selectbox("Select door", door_options, key="door_select")

    door_row = df[df["door"] == selected_door].iloc[0] if not df.empty and selected_door in df["door"].values else None

    if door_row is not None:
        door_id = door_row["id"]
        k = selected_door.replace(" ", "_")

        current_container = clean(door_row.get("container_trailer", ""))
        current_status = clean(door_row.get("status", "Vacant"))
        current_unloading = clean(door_row.get("unloading_empty", ""))
        current_customer = clean(door_row.get("customer", ""))
        current_carrier = clean(door_row.get("carrier", ""))

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
            db = get_db()
            db.table("dock_status").update({
                "container_trailer": new_container,
                "status": new_status,
                "unloading_empty": new_unloading,
                "customer": new_customer,
                "carrier": new_carrier,
            }).eq("id", door_id).execute()
            st.success(f"{selected_door} updated")
            st.cache_data.clear()
            st.rerun()

        if st.button("Clear door", use_container_width=True, key=f"clear_{k}"):
            db = get_db()
            db.table("dock_status").update({
                "container_trailer": "",
                "status": "Vacant",
                "unloading_empty": "",
                "customer": "",
                "carrier": "",
            }).eq("id", door_id).execute()
            st.success(f"{selected_door} cleared")
            st.cache_data.clear()
            st.rerun()

# --- metrics ---
if not df.empty:
    types = df.apply(lambda row: get_door_type(
        row.get("status", ""),
        row.get("unloading_empty", ""),
        row.get("container_trailer", "")
    ), axis=1)
    total = len(df)
    occupied_count = types.isin(["occupied", "full", "unloading"]).sum()
    vacant_count = types.eq("vacant").sum()
    utilization = round((occupied_count / total) * 100) if total > 0 else 0
else:
    total = occupied_count = vacant_count = utilization = 0

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

# --- door tiles ---
if not df.empty:
    cols = st.columns(7)
    for i, row in df.iterrows():
        door_label = clean(row.get("door", f"Door {i+1}"))
        container = clean(row.get("container_trailer", ""))
        status_raw = clean(row.get("status", ""))
        unloading = clean(row.get("unloading_empty", ""))
        door_type = get_door_type(status_raw, unloading, container)
        c = color_map[door_type]
        col = cols[i % 7]
        display_name = container if container else ""
        display_sub = unloading if unloading and door_type != "reserved" else c["label"]
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

st.caption("Select a door in the left panel to update its status. Changes save directly to Supabase.")
