import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import zoneinfo
import sys, os
sys.path.append(os.path.dirname(__file__))
from styles import GLOBAL_CSS, page_header
from auth import require_auth, logout, get_db

require_auth()

pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
today = datetime.now(pacific).date()
tomorrow = today + timedelta(days=1)
today_str = today.strftime("%Y-%m-%d")
tomorrow_str = tomorrow.strftime("%Y-%m-%d")
cutoff_str = (today - timedelta(days=14)).strftime("%Y-%m-%d")

st.set_page_config(page_title="Brodiaea Operations", layout="wide", page_icon="📦")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

def compact_table(rows, columns, empty_msg="No data"):
    if not rows:
        st.markdown(f"""<div class="alert-green">
            <p class="alert-title">{empty_msg}</p>
        </div>""", unsafe_allow_html=True)
        return
    header_html = "".join(f'<th style="text-align:left;padding:6px 10px;font-size:11px;font-weight:500;color:#6b7280;border-bottom:1px solid #e5e7eb;">{c}</th>' for c in columns)
    rows_html = ""
    for row in rows:
        cells = "".join(f'<td style="padding:6px 10px;font-size:12px;color:#1a2332;border-bottom:1px solid #f3f4f6;">{cell}</td>' for cell in row)
        rows_html += f"<tr>{cells}</tr>"
    st.markdown(f"""
    <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:8px;">
        <table style="width:100%;border-collapse:collapse;">
            <thead><tr>{header_html}</tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def load_active_containers():
    db = get_db()
    result = db.table("containers")\
        .select("*")\
        .eq("picked_up", False)\
        .gte("arrival_date", cutoff_str)\
        .execute()
    df = pd.DataFrame(result.data)
    if df.empty:
        return df
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
    df["empty_timestamp"] = pd.to_datetime(df["empty_timestamp"], errors="coerce")
    return df

@st.cache_data(ttl=60)
def load_dock():
    db = get_db()
    result = db.table("dock_status").select("*").order("door").execute()
    return pd.DataFrame(result.data)

@st.cache_data(ttl=120)
def load_outbound_today():
    db = get_db()
    result = db.table("outbound").select("*").eq("date", today_str).execute()
    return pd.DataFrame(result.data)

@st.cache_data(ttl=120)
def load_outbound_tomorrow():
    db = get_db()
    result = db.table("outbound").select("*").eq("date", tomorrow_str).execute()
    return pd.DataFrame(result.data)

# --- load data ---
active = load_active_containers()
dock_df = load_dock()
out_today = load_outbound_today()
out_tomorrow = load_outbound_tomorrow()

# --- inbound calculations ---
if not active.empty:
    active["arrival_date_only"] = active["arrival_date"].dt.date
    active["days_since_arrival"] = (pd.Timestamp(today) - active["arrival_date"]).dt.days
    active["days_since_empty"] = active.apply(
    lambda r: (pd.Timestamp(today) - r["empty_timestamp"]).days
    if pd.notna(r["empty_timestamp"])
    else (pd.Timestamp(today) - r["arrival_date"]).days
    if r["empty"] == True else None, axis=1
)
    
    unload_breached = active[(active["empty"] != True) & (active["days_since_arrival"] >= 3)]
    unload_at_risk = active[(active["empty"] != True) & (active["days_since_arrival"] == 2)]
    receive_breached = active[(active["empty"] == True) & (active["received"] != True) & (active["days_since_empty"] >= 2)]
    receive_at_risk = active[(active["empty"] == True) & (active["received"] != True) & (active["days_since_empty"] == 1)]
    dwell_24_48 = active[(active["empty"] != True) & (active["days_since_arrival"] >= 1) & (active["days_since_arrival"] < 2)]
    dwell_48_72 = active[(active["empty"] != True) & (active["days_since_arrival"] >= 2) & (active["days_since_arrival"] < 3)]
    dwell_72_plus = active[(active["empty"] != True) & (active["days_since_arrival"] >= 3)]
    arriving_today = active[active["arrival_date_only"] == today]
    arriving_tomorrow = active[active["arrival_date_only"] == tomorrow]
else:
    unload_breached = unload_at_risk = receive_breached = receive_at_risk = pd.DataFrame()
    dwell_24_48 = dwell_48_72 = dwell_72_plus = pd.DataFrame()
    arriving_today = arriving_tomorrow = pd.DataFrame()

# --- outbound calculations ---
mad_today = out_today[out_today["business"] == "MAD"] if not out_today.empty else pd.DataFrame()
insta_today = out_today[out_today["business"] == "Instaship"] if not out_today.empty else pd.DataFrame()

# --- dock calculations ---
def door_type(row):
    status = str(row.get("status", "")).strip().lower()
    container = str(row.get("container_trailer", "")).strip()
    reserved = ["ramp", "trash", "cardboard", "pallets", "fedex fround", "ups"]
    if any(r in container.lower() for r in reserved):
        return "reserved"
    if "vacant" in status:
        return "vacant"
    return "occupied"

if not dock_df.empty:
    dock_df["_type"] = dock_df.apply(door_type, axis=1)
    total_doors = len(dock_df)
    occupied_doors = dock_df[dock_df["_type"] == "occupied"].shape[0]
    vacant_doors = dock_df[dock_df["_type"] == "vacant"].shape[0]
    utilization = round((occupied_doors / total_doors) * 100) if total_doors > 0 else 0
else:
    total_doors = occupied_doors = vacant_doors = utilization = 0

# --- header ---
page_header("Brodiaea Operations", f"Morning briefing — {today.strftime('%A, %B %d %Y')}")

with st.sidebar:
    st.caption(f"👤 {st.session_state['user'].email}")
    if st.button("Sign out", use_container_width=True):
        logout()

if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()

# --- 2x2 metric cards ---
card_style = "background:#ffffff;border-radius:10px;padding:1rem 1.25rem;border:1.5px solid #d1d5db;box-shadow:0 2px 6px rgba(0,0,0,0.08);min-height:90px;"
inbound_col, outbound_col = st.columns(2)

with inbound_col:
    st.markdown('<div class="group-header"><p>Inbound</p></div>', unsafe_allow_html=True)
    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)
    with r1c1:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Arriving today</p><p class="metric-value">{len(arriving_today)}</p></div>', unsafe_allow_html=True)
    with r1c2:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Arriving tomorrow</p><p class="metric-value">{len(arriving_tomorrow)}</p></div>', unsafe_allow_html=True)
    with r2c1:
        color = "#e53935" if len(unload_breached) > 0 else "#1a2332"
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Unload SLA breached</p><p class="metric-value" style="color:{color}">{len(unload_breached)}</p></div>', unsafe_allow_html=True)
    with r2c2:
        color = "#e53935" if len(receive_breached) > 0 else "#1a2332"
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Receive report overdue</p><p class="metric-value" style="color:{color}">{len(receive_breached)}</p></div>', unsafe_allow_html=True)

with outbound_col:
    st.markdown('<div class="group-header"><p>Outbound</p></div>', unsafe_allow_html=True)
    r1c3, r1c4 = st.columns(2)
    r2c3, r2c4 = st.columns(2)
    with r1c3:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">MAD shipments today</p><p class="metric-value">{len(mad_today)}</p><p class="metric-sub">{mad_today["ctn"].sum():,} cartons</p></div>', unsafe_allow_html=True)
    with r1c4:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Instaship shipments today</p><p class="metric-value">{len(insta_today)}</p><p class="metric-sub">{insta_today["ctn"].sum():,} cartons</p></div>', unsafe_allow_html=True)
    with r2c3:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Outbound tomorrow</p><p class="metric-value">{len(out_tomorrow)}</p></div>', unsafe_allow_html=True)
    with r2c4:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Total pallets out today</p><p class="metric-value">{out_today["pallet_total"].sum() if not out_today.empty else 0}</p></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- main content ---
left, right = st.columns(2)

with left:
    st.markdown('<p class="section-header">SLA alerts</p>', unsafe_allow_html=True)
    total_alerts = len(unload_breached) + len(unload_at_risk) + len(receive_breached) + len(receive_at_risk)
    if total_alerts == 0:
        st.markdown("""<div class="alert-green">
            <p class="alert-title">All containers within SLA</p>
            <p class="alert-sub">No action required right now</p>
        </div>""", unsafe_allow_html=True)
    else:
        for _, row in unload_breached.iterrows():
            st.markdown(f"""<div class="alert-red">
                <p class="alert-title">Unload SLA breached — {row['container']}</p>
                <p class="alert-sub">{row['account']} · Arrived {row['days_since_arrival']} days ago · Door {row.get('dock_door') or '—'}</p>
            </div>""", unsafe_allow_html=True)
        for _, row in unload_at_risk.iterrows():
            st.markdown(f"""<div class="alert-amber">
                <p class="alert-title">Unload SLA at risk — {row['container']}</p>
                <p class="alert-sub">{row['account']} · Arrived {row['days_since_arrival']} days ago · Must unload tomorrow</p>
            </div>""", unsafe_allow_html=True)
        for _, row in receive_breached.iterrows():
            st.markdown(f"""<div class="alert-red">
                <p class="alert-title">Receive report overdue — {row['container']}</p>
                <p class="alert-sub">{row['account']} · Empty {row['days_since_empty']} days ago · Report not sent</p>
            </div>""", unsafe_allow_html=True)
        for _, row in receive_at_risk.iterrows():
            st.markdown(f"""<div class="alert-amber">
                <p class="alert-title">Receive report due tomorrow — {row['container']}</p>
                <p class="alert-sub">{row['account']} · Empty yesterday · Send report today</p>
            </div>""", unsafe_allow_html=True)

    st.markdown('<p class="section-header">Container dwell</p>', unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown(f'<div class="dwell-card dwell-green"><p class="dwell-num">{len(dwell_24_48)}</p><p class="dwell-label">1–2 days</p></div>', unsafe_allow_html=True)
    with d2:
        st.markdown(f'<div class="dwell-card dwell-amber"><p class="dwell-num">{len(dwell_48_72)}</p><p class="dwell-label">2–3 days</p></div>', unsafe_allow_html=True)
    with d3:
        st.markdown(f'<div class="dwell-card dwell-red"><p class="dwell-num">{len(dwell_72_plus)}</p><p class="dwell-label">3+ days</p></div>', unsafe_allow_html=True)

    st.markdown('<p class="section-header">Arriving today</p>', unsafe_allow_html=True)
    compact_table(
        [[row['container'], row['account'], row.get('trucking_company') or '—',
          row.get('sku_count') or '—', row.get('carton_count') or '—']
         for _, row in arriving_today.iterrows()],
        ["Container", "Account", "Carrier", "SKUs", "Cartons"],
        "No containers arriving today"
    )

    st.markdown('<p class="section-header">Arriving tomorrow</p>', unsafe_allow_html=True)
    compact_table(
        [[row['container'], row['account'], row.get('trucking_company') or '—',
          row.get('sku_count') or '—', row.get('carton_count') or '—']
         for _, row in arriving_tomorrow.iterrows()],
        ["Container", "Account", "Carrier", "SKUs", "Cartons"],
        "No containers arriving tomorrow"
    )

with right:
    st.markdown('<p class="section-header">Shipments going out today</p>', unsafe_allow_html=True)
    compact_table(
        [[row.get('sales_order') or '—', row.get('business') or '—',
          row.get('carrier') or '—', row.get('consignee') or '—',
          f"{row.get('ctn', 0):,}", str(row.get('pallet_total', 0)),
          str(row.get('load_number') or '—')]
         for _, row in out_today.iterrows()],
        ["Sales order", "Biz", "Carrier", "Consignee", "Cartons", "Pallets", "Load #"],
        "No shipments scheduled today"
    )

    st.markdown('<p class="section-header">Outbound tomorrow</p>', unsafe_allow_html=True)
    compact_table(
        [[row.get('sales_order') or '—', row.get('business') or '—',
          row.get('carrier') or '—', row.get('consignee') or '—',
          f"{row.get('ctn', 0):,}", str(row.get('pallet_total', 0))]
         for _, row in out_tomorrow.iterrows()],
        ["Sales order", "Biz", "Carrier", "Consignee", "Cartons", "Pallets"],
        "No shipments scheduled tomorrow"
    )

    st.markdown('<p class="section-header">Dock snapshot</p>', unsafe_allow_html=True)
    st.markdown(f"""<div class="metric-card">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="font-size:13px;color:#1a2332;">Total doors</span>
            <span style="font-size:13px;font-weight:500;color:#1a2332;">{total_doors}</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="font-size:13px;color:#1a2332;">Occupied</span>
            <span style="font-size:13px;font-weight:500;color:#e53935;">{occupied_doors}</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:12px;">
            <span style="font-size:13px;color:#1a2332;">Vacant</span>
            <span style="font-size:13px;font-weight:500;color:#00c851;">{vacant_doors}</span>
        </div>
        <div style="background:#e0e0e0;border-radius:4px;height:6px;">
            <div style="background:#1a2332;border-radius:4px;height:6px;width:{utilization}%;"></div>
        </div>
        <p style="font-size:11px;color:#6b7280;margin:6px 0 0;text-align:right;">{utilization}% utilized</p>
    </div>""", unsafe_allow_html=True)

st.caption(f"Last updated: {datetime.now(pacific).strftime('%I:%M %p')} · Refreshes every 5 minutes")
