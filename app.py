import gspread
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import sys, os
sys.path.append(os.path.dirname(__file__))
from styles import GLOBAL_CSS, page_header

st.set_page_config(page_title="Brodiaea Operations", layout="wide", page_icon="📦")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

def get_creds():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

def safe_int(val):
    try:
        return int(str(val).replace(",", "").strip())
    except:
        return 0

def parse_date(val):
    if not val or str(val).strip() == "":
        return pd.NaT
    for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%-m/%-d/%Y",
                "%-m/%-d/%y", "%m/%d/%Y %H:%M:%S", "%m/%d/%y %H:%M:%S"]:
        try:
            return pd.to_datetime(val, format=fmt)
        except:
            pass
    return pd.to_datetime(val, errors="coerce")

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
def load_inbound():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Inbound")
    df = pd.DataFrame(sheet.get_all_values())
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df = df.loc[:, df.columns != '']
    return df

@st.cache_data(ttl=60)
def load_dock():
    gc = gspread.authorize(get_creds())
    sheet = gc.open("Brodiaea Operations").worksheet("Dock_Status")
    df = pd.DataFrame(sheet.get_all_values())
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df = df.loc[:, df.columns != '']
    return df

@st.cache_data(ttl=120)
def load_outbound():
    gc = gspread.authorize(get_creds())
    mad = gc.open("Brodiaea Operations").worksheet("Outbound-MAD 2026")
    mad_data = mad.get_all_values()
    mad_headers = [h.strip() for h in mad_data[1]]
    mad_df = pd.DataFrame(mad_data[2:], columns=mad_headers)
    mad_df.columns = [c.strip() for c in mad_df.columns]
    mad_df["_source"] = "MAD"
    mad_df = mad_df.rename(columns={"CARTONS": "CTN", "READY FOR PU": "READY PU"})
    mad_df["CTN"] = mad_df["CTN"].apply(safe_int)
    mad_df["PALLET TOTAL"] = mad_df["PALLET TOTAL"].apply(safe_int)

    insta = gc.open("Brodiaea Operations").worksheet("Outbound-Instaship 2026")
    insta_data = insta.get_all_values()
    insta_headers = [h.strip() for h in insta_data[1]]
    insta_df = pd.DataFrame(insta_data[2:], columns=insta_headers)
    insta_df.columns = [c.strip() for c in insta_df.columns]
    insta_df["_source"] = "Instaship"
    insta_df["CTN"] = insta_df["CTN"].apply(safe_int)
    insta_df["PALLET TOTAL"] = insta_df["PALLET TOTAL"].apply(safe_int)

    shared = ["ACCOUNT", "CARRIER", "DATE", "CONSIGNEE",
              "SALES ORDER", "PO", "CTN", "PALLET TOTAL", "LOAD #", "_source"]
    combined = pd.concat(
        [mad_df[[c for c in shared if c in mad_df.columns]],
         insta_df[[c for c in shared if c in insta_df.columns]]],
        ignore_index=True
    )
    combined = combined[combined["ACCOUNT"].str.strip() != ""]
    return combined

# --- load data ---
df = load_inbound()
dock_df = load_dock()
out_df = load_outbound()
today = datetime.today().date()
tomorrow = today + timedelta(days=1)

df["Arrival date"] = df["Arrival date"].apply(parse_date)
df["Empty TImeStamp"] = df["Empty TImeStamp"].apply(parse_date)

active = df[
    (df["PICKED UP"] != "TRUE") &
    (df["CONTAINER"].str.strip() != "") &
    (df["Arrival date"].notna())
].copy()

active["arrival_date_only"] = active["Arrival date"].dt.date
active["days_since_arrival"] = (pd.Timestamp(today) - active["Arrival date"]).dt.days
active["days_since_empty"] = active.apply(
    lambda r: (pd.Timestamp(today) - r["Empty TImeStamp"]).days
    if pd.notna(r["Empty TImeStamp"]) else None, axis=1
)

unload_breached = active[(active["EMPTY"] != "TRUE") & (active["days_since_arrival"] >= 3)]
unload_at_risk = active[(active["EMPTY"] != "TRUE") & (active["days_since_arrival"] == 2)]
receive_breached = active[(active["EMPTY"] == "TRUE") & (active["RECEIVED"] != "TRUE") & (active["days_since_empty"] >= 2)]
receive_at_risk = active[(active["EMPTY"] == "TRUE") & (active["RECEIVED"] != "TRUE") & (active["days_since_empty"] == 1)]
dwell_24_48 = active[(active["EMPTY"] != "TRUE") & (active["days_since_arrival"] >= 1) & (active["days_since_arrival"] < 2)]
dwell_48_72 = active[(active["EMPTY"] != "TRUE") & (active["days_since_arrival"] >= 2) & (active["days_since_arrival"] < 3)]
dwell_72_plus = active[(active["EMPTY"] != "TRUE") & (active["days_since_arrival"] >= 3)]
arriving_today = active[active["arrival_date_only"] == today]
arriving_tomorrow = active[active["arrival_date_only"] == tomorrow]

out_df["DATE"] = out_df["DATE"].apply(parse_date)
out_df = out_df[out_df["DATE"].notna()]
out_today = out_df[out_df["DATE"].dt.date == today]
out_tomorrow = out_df[out_df["DATE"].dt.date == tomorrow]
mad_today = out_today[out_today["_source"] == "MAD"]
insta_today = out_today[out_today["_source"] == "Instaship"]

def door_type(row):
    status = str(row.get("Status", "")).strip().lower()
    container = str(row.get("Container #/Trailer", "")).strip()
    reserved = ["ramp", "trash", "cardboard", "pallets", "fedex fround", "ups"]
    if any(r in container.lower() for r in reserved):
        return "reserved"
    if "vacant" in status:
        return "vacant"
    return "occupied"

dock_df["_type"] = dock_df.apply(door_type, axis=1)
total_doors = len(dock_df)
occupied_doors = dock_df[dock_df["_type"] == "occupied"].shape[0]
vacant_doors = dock_df[dock_df["_type"] == "vacant"].shape[0]
utilization = round((occupied_doors / total_doors) * 100) if total_doors > 0 else 0

# --- header ---
page_header("Brodiaea Operations", f"Morning briefing — {today.strftime('%A, %B %d %Y')}")

if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()

# --- 2x2 metric cards side by side ---
inbound_col, outbound_col = st.columns(2)

card_style = "background:#ffffff;border-radius:10px;padding:1rem 1.25rem;border:1.5px solid #d1d5db;box-shadow:0 2px 6px rgba(0,0,0,0.08);min-height:90px;"

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
        st.markdown(f'<div style="{card_style}"><p class="metric-label">MAD shipments today</p><p class="metric-value">{len(mad_today)}</p><p class="metric-sub">{mad_today["CTN"].sum():,} cartons</p></div>', unsafe_allow_html=True)
    with r1c4:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Instaship shipments today</p><p class="metric-value">{len(insta_today)}</p><p class="metric-sub">{insta_today["CTN"].sum():,} cartons</p></div>', unsafe_allow_html=True)
    with r2c3:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Outbound tomorrow</p><p class="metric-value">{len(out_tomorrow)}</p></div>', unsafe_allow_html=True)
    with r2c4:
        st.markdown(f'<div style="{card_style}"><p class="metric-label">Total pallets out today</p><p class="metric-value">{out_today["PALLET TOTAL"].sum()}</p></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- main content: strict 50/50 split ---
left, right = st.columns(2)

with left:
    # SLA alerts
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
                <p class="alert-title">Unload SLA breached — {row['CONTAINER']}</p>
                <p class="alert-sub">{row['ACCOUNT']} · Arrived {row['days_since_arrival']} days ago · Door {row.get('DOCK DOOR','—')}</p>
            </div>""", unsafe_allow_html=True)
        for _, row in unload_at_risk.iterrows():
            st.markdown(f"""<div class="alert-amber">
                <p class="alert-title">Unload SLA at risk — {row['CONTAINER']}</p>
                <p class="alert-sub">{row['ACCOUNT']} · Arrived {row['days_since_arrival']} days ago · Must unload tomorrow</p>
            </div>""", unsafe_allow_html=True)
        for _, row in receive_breached.iterrows():
            st.markdown(f"""<div class="alert-red">
                <p class="alert-title">Receive report overdue — {row['CONTAINER']}</p>
                <p class="alert-sub">{row['ACCOUNT']} · Empty {row['days_since_empty']} days ago · Report not sent</p>
            </div>""", unsafe_allow_html=True)
        for _, row in receive_at_risk.iterrows():
            st.markdown(f"""<div class="alert-amber">
                <p class="alert-title">Receive report due tomorrow — {row['CONTAINER']}</p>
                <p class="alert-sub">{row['ACCOUNT']} · Empty yesterday · Send report today</p>
            </div>""", unsafe_allow_html=True)

    # container dwell
    st.markdown('<p class="section-header">Container dwell</p>', unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown(f'<div class="dwell-card dwell-green"><p class="dwell-num">{len(dwell_24_48)}</p><p class="dwell-label">1–2 days</p></div>', unsafe_allow_html=True)
    with d2:
        st.markdown(f'<div class="dwell-card dwell-amber"><p class="dwell-num">{len(dwell_48_72)}</p><p class="dwell-label">2–3 days</p></div>', unsafe_allow_html=True)
    with d3:
        st.markdown(f'<div class="dwell-card dwell-red"><p class="dwell-num">{len(dwell_72_plus)}</p><p class="dwell-label">3+ days</p></div>', unsafe_allow_html=True)

    # arriving today compact table
    st.markdown('<p class="section-header">Arriving today</p>', unsafe_allow_html=True)
    compact_table(
        [[row['CONTAINER'], row['ACCOUNT'], row.get('TRUCKING COMPANY','—'),
          row.get('SKU Count','—'), row.get('Carton Count','—')]
         for _, row in arriving_today.iterrows()],
        ["Container", "Account", "Carrier", "SKUs", "Cartons"],
        "No containers arriving today"
    )

    # arriving tomorrow compact table
    st.markdown('<p class="section-header">Arriving tomorrow</p>', unsafe_allow_html=True)
    compact_table(
        [[row['CONTAINER'], row['ACCOUNT'], row.get('TRUCKING COMPANY','—'),
          row.get('SKU Count','—'), row.get('Carton Count','—')]
         for _, row in arriving_tomorrow.iterrows()],
        ["Container", "Account", "Carrier", "SKUs", "Cartons"],
        "No containers arriving tomorrow"
    )

with right:
    # shipments going out today compact table
    st.markdown('<p class="section-header">Shipments going out today</p>', unsafe_allow_html=True)
    compact_table(
        [[row.get('SALES ORDER','—'), row['_source'], row.get('CARRIER','—'),
          row.get('CONSIGNEE','—'), f"{row['CTN']:,}", str(row['PALLET TOTAL']),
          str(row.get('LOAD #','—'))]
         for _, row in out_today.iterrows()],
        ["Sales order", "Biz", "Carrier", "Consignee", "Cartons", "Pallets", "Load #"],
        "No shipments scheduled today"
    )

    # outbound tomorrow compact table
    st.markdown('<p class="section-header">Outbound tomorrow</p>', unsafe_allow_html=True)
    compact_table(
        [[row.get('SALES ORDER','—'), row['_source'], row.get('CARRIER','—'),
          row.get('CONSIGNEE','—'), f"{row['CTN']:,}", str(row['PALLET TOTAL'])]
         for _, row in out_tomorrow.iterrows()],
        ["Sales order", "Biz", "Carrier", "Consignee", "Cartons", "Pallets"],
        "No shipments scheduled tomorrow"
    )

    # dock snapshot
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

st.caption(f"Last updated: {datetime.now().strftime('%I:%M %p')} · Refreshes every 5 minutes")
