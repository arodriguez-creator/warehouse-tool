import gspread
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Brodiaea Operations",
    layout="wide",
    page_icon="📦"
)

st.markdown("""
<style>
  [data-testid="stSidebar"] { background-color: #1a2332; }
  [data-testid="stSidebar"] * { color: #ffffff !important; }
  [data-testid="stSidebar"] .stSelectbox label { color: #ffffff !important; }
  .metric-card {
    background: #ffffff;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    border: 1.5px solid #d1d5db;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  }
  .metric-label { font-size: 12px; color: #6b7280; margin: 0 0 4px; }
  .metric-value { font-size: 26px; font-weight: 500; margin: 0; color: #1a2332; }
  .metric-sub { font-size: 11px; color: #9ca3af; margin: 4px 0 0; }
  .alert-red {
    background: #fdecea;
    border-left: 4px solid #e53935;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
  }
  .alert-amber {
    background: #fff8e1;
    border-left: 4px solid #f59e0b;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
  }
  .alert-green {
    background: #e8f5e9;
    border-left: 4px solid #00c851;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
  }
  .alert-title { font-size: 13px; font-weight: 500; color: #1a2332; margin: 0 0 2px; }
  .alert-sub { font-size: 12px; color: #6b7280; margin: 0; }
  .section-header {
    font-size: 11px;
    font-weight: 500;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 1.5rem 0 0.75rem;
  }
  .dwell-card {
    border-radius: 10px;
    padding: 1rem 1.25rem;
    text-align: center;
  }
  .dwell-green { background: #e8f5e9; }
  .dwell-amber { background: #fff8e1; }
  .dwell-red { background: #fdecea; }
  .dwell-num { font-size: 32px; font-weight: 500; margin: 0; }
  .dwell-green .dwell-num { color: #1b5e20; }
  .dwell-amber .dwell-num { color: #92400e; }
  .dwell-red .dwell-num { color: #b71c1c; }
  .dwell-label { font-size: 12px; margin: 4px 0 0; }
  .dwell-green .dwell-label { color: #2e7d32; }
  .dwell-amber .dwell-label { color: #92400e; }
  .dwell-red .dwell-label { color: #b71c1c; }
  .arriving-card {
    background: #ffffff;
    border: 0.5px solid #e0e0e0;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .outbound-card {
    background: #ffffff;
    border: 0.5px solid #e0e0e0;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .badge-mad { background: #e6f1fb; color: #185fa5; font-size: 10px; font-weight: 500; padding: 2px 8px; border-radius: 10px; }
  .badge-insta { background: #f3e8ff; color: #6b21a8; font-size: 10px; font-weight: 500; padding: 2px 8px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

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

    mad_sheet = gc.open("Brodiaea Operations").worksheet("Outbound-MAD 2026")
    mad_data = mad_sheet.get_all_values()
    mad_headers = [h.strip() for h in mad_data[1]]
    mad_df = pd.DataFrame(mad_data[2:], columns=mad_headers)
    mad_df.columns = [c.strip() for c in mad_df.columns]
    mad_df["_source"] = "MAD"
    mad_df = mad_df.rename(columns={"CARTONS": "CTN", "READY FOR PU": "READY PU"})
    mad_df["CTN"] = mad_df["CTN"].apply(safe_int)
    mad_df["PALLET TOTAL"] = mad_df["PALLET TOTAL"].apply(safe_int)

    insta_sheet = gc.open("Brodiaea Operations").worksheet("Outbound-Instaship 2026")
    insta_data = insta_sheet.get_all_values()
    insta_headers = [h.strip() for h in insta_data[1]]
    insta_df = pd.DataFrame(insta_data[2:], columns=insta_headers)
    insta_df.columns = [c.strip() for c in insta_df.columns]
    insta_df["_source"] = "Instaship"
    insta_df["CTN"] = insta_df["CTN"].apply(safe_int)
    insta_df["PALLET TOTAL"] = insta_df["PALLET TOTAL"].apply(safe_int)

    shared = ["ACCOUNT", "CARRIER", "DATE", "CONSIGNEE",
              "SALES ORDER", "PO", "CTN", "PALLET TOTAL", "LOAD #", "_source"]
    mad_cols = [c for c in shared if c in mad_df.columns]
    insta_cols = [c for c in shared if c in insta_df.columns]
    combined = pd.concat([mad_df[mad_cols], insta_df[insta_cols]], ignore_index=True)
    combined = combined[combined["ACCOUNT"].str.strip() != ""]
    return combined

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

# --- load data ---
df = load_inbound()
dock_df = load_dock()
out_df = load_outbound()
today = datetime.today().date()
tomorrow = today + timedelta(days=1)

# --- inbound prep ---
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

# --- outbound prep ---
out_df["DATE"] = out_df["DATE"].apply(parse_date)
out_df = out_df[out_df["DATE"].notna()]
out_today = out_df[out_df["DATE"].dt.date == today]
out_tomorrow = out_df[out_df["DATE"].dt.date == tomorrow]
mad_today = out_today[out_today["_source"] == "MAD"]
insta_today = out_today[out_today["_source"] == "Instaship"]

# --- dock ---
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
st.markdown(f"""
<div style="background:#1a2332;padding:1rem 1.5rem;border-radius:10px;margin-bottom:1.5rem;
            display:flex;justify-content:space-between;align-items:center;">
  <div>
    <p style="margin:0;font-size:20px;font-weight:500;color:#ffffff;">Brodiaea Operations</p>
    <p style="margin:0;font-size:13px;color:#9ca3af;">Morning briefing — {today.strftime("%A, %B %d %Y")}</p>
  </div>
  <div style="text-align:right;">
    <p style="margin:0;font-size:13px;color:#00c851;font-weight:500;">● Live</p>
  </div>
</div>
""", unsafe_allow_html=True)

if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()

# --- inbound metrics row ---
st.markdown('<p class="section-header">Inbound</p>', unsafe_allow_html=True)
m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Active containers</p>
        <p class="metric-value">{len(active)}</p>
    </div>""", unsafe_allow_html=True)
with m2:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Arriving today</p>
        <p class="metric-value">{len(arriving_today)}</p>
    </div>""", unsafe_allow_html=True)
with m3:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Unload SLA breached</p>
        <p class="metric-value" style="color:#e53935">{len(unload_breached)}</p>
    </div>""", unsafe_allow_html=True)
with m4:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Receive report overdue</p>
        <p class="metric-value" style="color:#e53935">{len(receive_breached)}</p>
    </div>""", unsafe_allow_html=True)
with m5:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Dock utilization</p>
        <p class="metric-value">{utilization}%</p>
    </div>""", unsafe_allow_html=True)

# --- outbound metrics row ---
st.markdown('<p class="section-header">Outbound — today</p>', unsafe_allow_html=True)
o1, o2, o3, o4, o5 = st.columns(5)

with o1:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Total shipments</p>
        <p class="metric-value">{len(out_today)}</p>
        <p class="metric-sub">Tomorrow: {len(out_tomorrow)}</p>
    </div>""", unsafe_allow_html=True)
with o2:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">MAD shipments</p>
        <p class="metric-value">{len(mad_today)}</p>
        <p class="metric-sub">{mad_today['CTN'].sum():,} cartons</p>
    </div>""", unsafe_allow_html=True)
with o3:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Instaship shipments</p>
        <p class="metric-value">{len(insta_today)}</p>
        <p class="metric-sub">{insta_today['CTN'].sum():,} cartons</p>
    </div>""", unsafe_allow_html=True)
with o4:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Total cartons out</p>
        <p class="metric-value">{out_today['CTN'].sum():,}</p>
    </div>""", unsafe_allow_html=True)
with o5:
    st.markdown(f"""<div class="metric-card">
        <p class="metric-label">Total pallets out</p>
        <p class="metric-value">{out_today['PALLET TOTAL'].sum()}</p>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- main content ---
left, right = st.columns([1.5, 1])

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

    st.markdown('<p class="section-header">Container dwell</p>', unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown(f"""<div class="dwell-card dwell-green">
            <p class="dwell-num">{len(dwell_24_48)}</p>
            <p class="dwell-label">1–2 days</p>
        </div>""", unsafe_allow_html=True)
    with d2:
        st.markdown(f"""<div class="dwell-card dwell-amber">
            <p class="dwell-num">{len(dwell_48_72)}</p>
            <p class="dwell-label">2–3 days</p>
        </div>""", unsafe_allow_html=True)
    with d3:
        st.markdown(f"""<div class="dwell-card dwell-red">
            <p class="dwell-num">{len(dwell_72_plus)}</p>
            <p class="dwell-label">3+ days</p>
        </div>""", unsafe_allow_html=True)

    if not dwell_72_plus.empty:
        st.markdown('<p class="section-header">Containers dwelling 3+ days</p>', unsafe_allow_html=True)
        for _, row in dwell_72_plus.iterrows():
            st.markdown(f"""<div class="arriving-card">
                <div>
                    <p style="margin:0;font-size:13px;font-weight:500;color:#1a2332">{row['CONTAINER']}</p>
                    <p style="margin:0;font-size:12px;color:#6b7280">{row['ACCOUNT']} · Arrived {row['days_since_arrival']} days ago</p>
                </div>
                <span style="background:#fdecea;color:#b71c1c;font-size:11px;font-weight:500;
                             padding:3px 10px;border-radius:12px;">{row['days_since_arrival']}d</span>
            </div>""", unsafe_allow_html=True)

    # outbound today list
    st.markdown('<p class="section-header">Shipments going out today</p>', unsafe_allow_html=True)
    if out_today.empty:
        st.markdown("""<div class="alert-green">
            <p class="alert-title">No shipments scheduled today</p>
        </div>""", unsafe_allow_html=True)
    else:
        for _, row in out_today.iterrows():
            badge = "badge-mad" if row["_source"] == "MAD" else "badge-insta"
            load = str(row.get("LOAD #", "")).strip()
            load_text = f"Load {load}" if load and load != "nan" else "No load ID"
            st.markdown(f"""<div class="outbound-card">
                <div>
                    <p style="margin:0;font-size:13px;font-weight:500;color:#1a2332">
                        {row.get('SALES ORDER','—')}
                        <span class="{badge}" style="margin-left:6px;">{row['_source']}</span>
                    </p>
                    <p style="margin:0;font-size:12px;color:#6b7280">
                        {row.get('CARRIER','—')} · {row.get('CONSIGNEE','—')}
                    </p>
                    <p style="margin:0;font-size:11px;color:#9ca3af">
                        {row['CTN']:,} cartons · {row['PALLET TOTAL']} pallets · {load_text}
                    </p>
                </div>
            </div>""", unsafe_allow_html=True)

with right:
    st.markdown('<p class="section-header">Arriving today</p>', unsafe_allow_html=True)
    if arriving_today.empty:
        st.markdown("""<div class="alert-green">
            <p class="alert-title">No containers arriving today</p>
        </div>""", unsafe_allow_html=True)
    else:
        for _, row in arriving_today.iterrows():
            sku = row.get("SKU Count", "")
            cartons = row.get("Carton Count", "")
            detail = f"{sku} SKUs · {cartons} cartons" if sku and cartons else ""
            st.markdown(f"""<div class="arriving-card">
                <div>
                    <p style="margin:0;font-size:13px;font-weight:500;color:#1a2332">{row['CONTAINER']}</p>
                    <p style="margin:0;font-size:12px;color:#6b7280">{row['ACCOUNT']} · {row.get('TRUCKING COMPANY','')}</p>
                    <p style="margin:0;font-size:11px;color:#9ca3af">{detail}</p>
                </div>
                <span style="background:#e8f5e9;color:#1b5e20;font-size:11px;font-weight:500;
                             padding:3px 10px;border-radius:12px;">Today</span>
            </div>""", unsafe_allow_html=True)

    st.markdown('<p class="section-header">Arriving tomorrow</p>', unsafe_allow_html=True)
    if arriving_tomorrow.empty:
        st.markdown("""<div class="alert-green">
            <p class="alert-title">No containers arriving tomorrow</p>
        </div>""", unsafe_allow_html=True)
    else:
        for _, row in arriving_tomorrow.iterrows():
            sku = row.get("SKU Count", "")
            cartons = row.get("Carton Count", "")
            detail = f"{sku} SKUs · {cartons} cartons" if sku and cartons else ""
            st.markdown(f"""<div class="arriving-card">
                <div>
                    <p style="margin:0;font-size:13px;font-weight:500;color:#1a2332">{row['CONTAINER']}</p>
                    <p style="margin:0;font-size:12px;color:#6b7280">{row['ACCOUNT']} · {row.get('TRUCKING COMPANY','')}</p>
                    <p style="margin:0;font-size:11px;color:#9ca3af">{detail}</p>
                </div>
                <span style="background:#e8f5e9;color:#1b5e20;font-size:11px;font-weight:500;
                             padding:3px 10px;border-radius:12px;">Tomorrow</span>
            </div>""", unsafe_allow_html=True)

    st.markdown('<p class="section-header">Outbound tomorrow</p>', unsafe_allow_html=True)
    if out_tomorrow.empty:
        st.markdown("""<div class="alert-green">
            <p class="alert-title">No shipments scheduled tomorrow</p>
        </div>""", unsafe_allow_html=True)
    else:
        for _, row in out_tomorrow.iterrows():
            badge = "badge-mad" if row["_source"] == "MAD" else "badge-insta"
            st.markdown(f"""<div class="outbound-card">
                <div>
                    <p style="margin:0;font-size:13px;font-weight:500;color:#1a2332">
                        {row.get('SALES ORDER','—')}
                        <span class="{badge}" style="margin-left:6px;">{row['_source']}</span>
                    </p>
                    <p style="margin:0;font-size:12px;color:#6b7280">
                        {row.get('CARRIER','—')} · {row.get('CONSIGNEE','—')}
                    </p>
                    <p style="margin:0;font-size:11px;color:#9ca3af">
                        {row['CTN']:,} cartons · {row['PALLET TOTAL']} pallets
                    </p>
                </div>
            </div>""", unsafe_allow_html=True)

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
