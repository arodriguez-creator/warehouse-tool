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
page_header("Dock door board", "Click any door to edit — Live from Supabase")
st.markdown("""
<style>
  [data-testid="stDialogOverlay"] {
      background: rgba(0, 0, 0, 0.75) !important;
  }
  div[role="dialog"] {
      background: #ffffff !important;
  }
  div[role="dialog"] * {
      color: #1a2332 !important;
  }
  div[role="dialog"] input,
  div[role="dialog"] textarea,
  div[role="dialog"] .stSelectbox {
      background: #ffffff !important;
      color: #1a2332 !important;
  }
</style>
""", unsafe_allow_html=True)

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
    if "empty" in unloading:
        return "empty"
    return "occupied"

color_map = {
    "vacant":    {"bg": "#EAF3DE", "border": "#3B6D11", "text": "#27500A", "label": "Vacant"},
    "occupied":  {"bg": "#FCEBEB", "border": "#A32D2D", "text": "#791F1F", "label": "Occupied"},
    "unloading": {"bg": "#E6F1FB", "border": "#185FA5", "text": "#0C447C", "label": "Unloading"},
    "reserved":  {"bg": "#F1EFE8", "border": "#5F5E5A", "text": "#444441", "label": "Reserved"},
    "full":      {"bg": "#FAEEDA", "border": "#854F0B", "text": "#633806", "label": "Full"},
    "empty":     {"bg": "#F3E8FF", "border": "#6B21A8", "text": "#4A1772", "label": "Empty"},
}

@st.cache_data(ttl=60)
def load_data():
    db = get_db()
    result = db.table("dock_status").select("*").execute()
    df = pd.DataFrame(result.data)
    if not df.empty:
        df["_door_num"] = df["door"].str.extract(r"(\d+)").astype(int)
        df = df.sort_values("_door_num").reset_index(drop=True).drop(columns=["_door_num"])
    return df

@st.cache_data(ttl=60)
def load_active_containers():
    db = get_db()
    result = db.table("containers")\
        .select("container, account")\
        .eq("picked_up", False)\
        .eq("empty", False)\
        .order("arrival_date", desc=True)\
        .execute()
    return [r["container"] for r in result.data if r["container"]]

df = load_data()

# init session state
if "edit_door_id" not in st.session_state:
    st.session_state["edit_door_id"] = None
if "show_door_modal" not in st.session_state:
    st.session_state["show_door_modal"] = False

# reset modal when navigating to this page from another page
current_page = "dock_doors"
last = st.session_state.get("last_page", "")
if last != current_page:
    st.session_state["show_door_modal"] = False
    st.session_state["edit_door_id"] = None
    st.session_state["last_page"] = current_page


# --- dialog modal ---
@st.dialog("Edit dock door", width="large")
def door_edit_modal(door_row):
    door_id = door_row["id"]
    door_label = clean(door_row.get("door", ""))
    current_container = clean(door_row.get("container_trailer", ""))
    current_status = clean(door_row.get("status", "Vacant"))
    current_unloading = clean(door_row.get("unloading_empty", ""))
    current_customer = clean(door_row.get("customer", ""))
    current_carrier = clean(door_row.get("carrier", ""))
    current_notes = clean(door_row.get("notes", ""))

    unloading_options = ["", "Unloading", "Full", "Loading", "Empty"]
    unloading_index = unloading_options.index(current_unloading) if current_unloading in unloading_options else 0

    st.markdown(f"**{door_label}**")

    mc1, mc2 = st.columns(2)
    active_containers = load_active_containers()
    container_options = [""] + active_containers + ["Other / manual entry"]
    current_idx = container_options.index(current_container) if current_container in container_options else len(container_options) - 1

    selected_container_opt = mc1.selectbox("Container / trailer", container_options,
                                        index=current_idx, key=f"d_container_sel")
    if selected_container_opt == "Other / manual entry":
        new_container = mc1.text_input("Enter container number", value=current_container, key=f"d_container_manual")
    else:
        new_container = selected_container_opt
    new_status = mc2.selectbox("Status", ["Vacant", "Occupied"],
        index=0 if "vacant" in current_status.lower() else 1,
        key=f"d_status")

    mc3, mc4 = st.columns(2)
    new_unloading = mc3.selectbox("Unloading / empty", unloading_options,
                                   index=unloading_index, key=f"d_unload")
    new_customer = mc4.text_input("Customer", value=current_customer, key=f"d_customer")

    mc5, mc6 = st.columns(2)
    new_carrier = mc5.text_input("Carrier", value=current_carrier, key=f"d_carrier")
    new_notes = mc6.text_input("Notes", value=current_notes, key=f"d_notes")

    st.markdown("<br>", unsafe_allow_html=True)
    btn1, btn2 = st.columns(2)

    if btn1.button("Save changes", type="primary", use_container_width=True):
        db = get_db()
        db.table("dock_status").update({
            "container_trailer": new_container,
            "status": new_status,
            "unloading_empty": new_unloading,
            "customer": new_customer,
            "carrier": new_carrier,
            "notes": new_notes,
        }).eq("id", door_id).execute()
        st.cache_data.clear()
        st.session_state["edit_door_id"] = None
        st.session_state["show_door_modal"] = False
        st.rerun()

    if btn2.button("Clear door", use_container_width=True):
        db = get_db()
        db.table("dock_status").update({
            "container_trailer": "",
            "status": "Vacant",
            "unloading_empty": "",
            "customer": "",
            "carrier": "",
            "notes": "",
        }).eq("id", door_id).execute()
        st.cache_data.clear()
        st.session_state["edit_door_id"] = None
        st.session_state["show_door_modal"] = False
        st.rerun()

# trigger modal if a door is selected
if st.session_state["show_door_modal"] and st.session_state["edit_door_id"] and not df.empty:
    door_row = df[df["id"] == st.session_state["edit_door_id"]]
    if not door_row.empty:
        door_edit_modal(door_row.iloc[0])

# --- metrics ---
if not df.empty:
    types = df.apply(lambda row: get_door_type(
        row.get("status", ""),
        row.get("unloading_empty", ""),
        row.get("container_trailer", "")
    ), axis=1)
    total = len(df)
    occupied_count = types.isin(["occupied", "full", "unloading", "empty"]).sum()
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

# --- legend ---
st.markdown("""
<div style="display:flex;gap:16px;flex-wrap:wrap;margin:0.5rem 0 1rem;">
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280"><span style="width:10px;height:10px;border-radius:2px;background:#639922;display:inline-block"></span>Vacant</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280"><span style="width:10px;height:10px;border-radius:2px;background:#E24B4A;display:inline-block"></span>Occupied</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280"><span style="width:10px;height:10px;border-radius:2px;background:#378ADD;display:inline-block"></span>Unloading</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280"><span style="width:10px;height:10px;border-radius:2px;background:#888780;display:inline-block"></span>Reserved</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280"><span style="width:10px;height:10px;border-radius:2px;background:#EF9F27;display:inline-block"></span>Full</span>
  <span style="display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280"><span style="width:10px;height:10px;border-radius:2px;background:#9333ea;display:inline-block"></span>Empty</span>
</div>
""", unsafe_allow_html=True)

st.caption("Click a door tile to open the edit form")

# --- door tiles ---
if not df.empty:
    cols = st.columns(7)
    for i, row in df.iterrows():
        door_label = clean(row.get("door", f"Door {i+1}"))
        container = clean(row.get("container_trailer", ""))
        status_raw = clean(row.get("status", ""))
        unloading = clean(row.get("unloading_empty", ""))
        notes = clean(row.get("notes", ""))
        door_type = get_door_type(status_raw, unloading, container)
        c = color_map[door_type]
        col = cols[i % 7]
        display_name = container if container else ""
        display_sub = unloading if unloading and door_type not in ["reserved", "vacant"] else c["label"]

        with col:
            st.markdown(f"""
            <div style="background:{c['bg']};border:0.5px solid {c['border']};border-radius:8px;
                        padding:10px 8px;min-height:80px;margin-bottom:4px;
                        display:flex;flex-direction:column;justify-content:space-between;">
              <span style="font-size:10px;font-weight:500;color:{c['text']}">{door_label}</span>
              <span style="font-size:10px;font-weight:500;color:{c['text']};word-break:break-all;margin-top:4px">{display_name}</span>
              <span style="font-size:9px;color:{c['text']};margin-top:2px">{display_sub}</span>
              {f'<span style="font-size:8px;color:{c["text"]};margin-top:2px;">📝</span>' if notes and len(notes) > 2 else ''}
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"✎ {door_label}", key=f"tile_{row['id']}", use_container_width=True):
                st.session_state["edit_door_id"] = row["id"]
                st.session_state["show_door_modal"] = True
                st.rerun()

st.caption("Changes save directly to Supabase.")
