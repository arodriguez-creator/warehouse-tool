GLOBAL_CSS = """
<style>
  [data-testid="stSidebar"] { background-color: #1a2332 !important; }
  [data-testid="stSidebar"] * { color: #ffffff !important; }
  [data-testid="stSidebar"] .stSelectbox label { color: #ffffff !important; }
  [data-testid="stSidebar"] .stRadio label { color: #ffffff !important; }
  [data-testid="stSidebar"] input { color: #1a2332 !important; }
  [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] { background: #ffffff !important; }
  [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * { color: #1a2332 !important; }
  [data-testid="stSidebar"] .stNumberInput input { color: #1a2332 !important; background: #ffffff !important; }
  [data-testid="stSidebar"] textarea { color: #1a2332 !important; background: #ffffff !important; }
  [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] { border-radius: 8px !important; }
  [data-testid="stSidebar"] input { border-radius: 8px !important; }
  [data-testid="stSidebar"] .stButton button {
      background-color: #00c851;
      color: #ffffff !important;
      border: none;
  }
  [data-testid="stMetric"] {
      background: #ffffff;
      border: 1.5px solid #d1d5db;
      border-radius: 10px;
      padding: 1rem 1.25rem;
      box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  }
  .metric-card {
    background: #ffffff;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    border: 1.5px solid #d1d5db;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    min-height: 100px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .metric-label { font-size: 12px; color: #6b7280; margin: 0 0 4px; }
  .metric-value { font-size: 26px; font-weight: 500; margin: 0; color: #1a2332; }
  .metric-sub { font-size: 11px; color: #9ca3af; margin: 4px 0 0; }
  .alert-red {
    background: #fdecea; border-left: 4px solid #e53935;
    border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;
  }
  .alert-amber {
    background: #fff8e1; border-left: 4px solid #f59e0b;
    border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;
  }
  .alert-green {
    background: #e8f5e9; border-left: 4px solid #00c851;
    border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;
  }
  .alert-title { font-size: 13px; font-weight: 500; color: #1a2332; margin: 0 0 2px; }
  .alert-sub { font-size: 12px; color: #6b7280; margin: 0; }
  .section-header {
    font-size: 11px; font-weight: 500; color: #6b7280;
    text-transform: uppercase; letter-spacing: 0.06em; margin: 1.5rem 0 0.75rem;
  }
  .dwell-card { border-radius: 10px; padding: 1rem 1.25rem; text-align: center; }
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
    background: #ffffff; border: 0.5px solid #e0e0e0;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 6px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .outbound-card {
    background: #ffffff; border: 0.5px solid #e0e0e0;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 6px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .badge-mad { background: #e6f1fb; color: #185fa5; font-size: 10px; font-weight: 500; padding: 2px 8px; border-radius: 10px; }
  .badge-insta { background: #f3e8ff; color: #6b21a8; font-size: 10px; font-weight: 500; padding: 2px 8px; border-radius: 10px; }
  .group-header {
    background: #1a2332; border-radius: 8px; padding: 10px 16px;
    margin-bottom: 12px; text-align: center;
  }
  .group-header p { margin: 0; font-size: 14px; font-weight: 500; color: #ffffff; }
  
</style>
"""

def page_header(title, subtitle=None):
    import streamlit as st
    from datetime import datetime
    sub_html = f'<p style="margin:0;font-size:13px;color:#9ca3af;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="background:#1a2332;padding:1.25rem 1.5rem;border-radius:10px;
                margin-bottom:1.5rem;text-align:center;">
      <p style="margin:0;font-size:26px;font-weight:500;color:#ffffff;">{title}</p>
      {sub_html}
    </div>
    """, unsafe_allow_html=True)
