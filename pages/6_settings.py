import pandas as pd
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from styles import GLOBAL_CSS, page_header
from auth import require_auth, show_user, get_db

require_auth()
show_user()
st.session_state["last_page"] = "other"

st.set_page_config(layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
page_header("Settings", "Manage lookup lists, carrier emails, and configuration")

def load_lookup(category):
    db = get_db()
    result = db.table("settings_lookup")\
        .select("*")\
        .eq("category", category)\
        .order("sort_order")\
        .execute()
    return result.data

def load_config():
    db = get_db()
    result = db.table("settings_config").select("*").execute()
    return {r["key"]: r for r in result.data}

def add_lookup(category, value, metadata=""):
    db = get_db()
    existing = db.table("settings_lookup")\
        .select("id")\
        .eq("category", category)\
        .eq("value", value)\
        .execute()
    if existing.data:
        return False
    db.table("settings_lookup").insert({
        "category": category,
        "value": value,
        "metadata": metadata,
        "sort_order": 999
    }).execute()
    return True

def delete_lookup(row_id):
    db = get_db()
    db.table("settings_lookup").delete().eq("id", row_id).execute()

def update_config(key, value):
    db = get_db()
    db.table("settings_config").update({"value": value}).eq("key", key).execute()

# --- tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Carriers", "Freight terms", "Consignees & Accounts", "Carrier emails", "Configuration"
])

# --- carriers ---
with tab1:
    st.subheader("Carriers")
    st.caption("These appear in the carrier dropdown on the outbound page")

    carriers = load_lookup("carrier")

    for item in carriers:
        c1, c2 = st.columns([6, 1])
        c1.write(item["value"])
        if c2.button("Remove", key=f"del_carrier_{item['id']}"):
            delete_lookup(item["id"])
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("**Add carrier**")
    nc1, nc2 = st.columns([4, 1])
    new_carrier = nc1.text_input("Carrier name", key="new_carrier_input", label_visibility="collapsed",
                                  placeholder="Enter carrier name")
    if nc2.button("Add", key="add_carrier", type="primary"):
        if new_carrier.strip():
            if add_lookup("carrier", new_carrier.strip().upper()):
                st.success(f"Added {new_carrier.strip().upper()}")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Carrier already exists")
        else:
            st.error("Enter a carrier name")

# --- freight terms ---
with tab2:
    st.subheader("Freight terms")
    st.caption("These appear in the freight terms dropdown on the outbound page")

    terms = load_lookup("freight_term")

    for item in terms:
        c1, c2 = st.columns([6, 1])
        c1.write(item["value"])
        if c2.button("Remove", key=f"del_term_{item['id']}"):
            delete_lookup(item["id"])
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("**Add freight term**")
    nc1, nc2 = st.columns([4, 1])
    new_term = nc1.text_input("Freight term", key="new_term_input", label_visibility="collapsed",
                               placeholder="Enter freight term")
    if nc2.button("Add", key="add_term", type="primary"):
        if new_term.strip():
            if add_lookup("freight_term", new_term.strip()):
                st.success(f"Added {new_term.strip()}")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Freight term already exists")
        else:
            st.error("Enter a freight term")

# --- consignees and accounts ---
with tab3:
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Consignees")
        st.caption("These appear in the consignee dropdown on the outbound page")

        consignees = load_lookup("consignee")
        for item in consignees:
            c1, c2 = st.columns([6, 1])
            c1.write(item["value"])
            if c2.button("Remove", key=f"del_consignee_{item['id']}"):
                delete_lookup(item["id"])
                st.cache_data.clear()
                st.rerun()

        st.divider()
        st.markdown("**Add consignee**")
        nc1, nc2 = st.columns([4, 1])
        new_consignee = nc1.text_input("Consignee", key="new_consignee_input",
                                        label_visibility="collapsed", placeholder="Enter consignee")
        if nc2.button("Add", key="add_consignee", type="primary"):
            if new_consignee.strip():
                if add_lookup("consignee", new_consignee.strip().upper()):
                    st.success(f"Added {new_consignee.strip().upper()}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Consignee already exists")
            else:
                st.error("Enter a consignee name")

    with col_right:
        st.subheader("Accounts & colors")
        st.caption("Account names and their row highlight colors in the outbound table")

        accounts = load_lookup("account")
        for item in accounts:
            c1, c2, c3 = st.columns([4, 2, 1])
            color = item.get("metadata", "#ffffff") or "#ffffff"
            c1.write(item["value"])
            c2.markdown(f'<div style="background:{color};border-radius:4px;padding:4px 8px;font-size:12px;">{color}</div>',
                       unsafe_allow_html=True)
            if c3.button("Remove", key=f"del_account_{item['id']}"):
                delete_lookup(item["id"])
                st.cache_data.clear()
                st.rerun()

        st.divider()
        st.markdown("**Add account**")
        na1, na2, na3 = st.columns([3, 2, 1])
        new_account = na1.text_input("Account name", key="new_account_input",
                                      label_visibility="collapsed", placeholder="Account name")
        new_color = na2.color_picker("Color", value="#ffffff", key="new_account_color",
                                      label_visibility="collapsed")
        if na3.button("Add", key="add_account", type="primary"):
            if new_account.strip():
                if add_lookup("account", new_account.strip().upper(), new_color):
                    st.success(f"Added {new_account.strip().upper()}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Account already exists")
            else:
                st.error("Enter an account name")

# --- carrier emails ---
with tab4:
    st.subheader("Carrier email addresses")
    st.caption("Email addresses for trucking companies — used for empty container notifications")

    carrier_emails = load_lookup("carrier_email")

    for item in carrier_emails:
        c1, c2, c3 = st.columns([3, 4, 1])
        c1.write(item["value"])
        email_val = item.get("metadata", "") or ""
        new_email = c2.text_input("Email", value=email_val, key=f"email_{item['id']}",
                                   label_visibility="collapsed", placeholder="carrier@example.com")
        if new_email != email_val:
            db = get_db()
            db.table("settings_lookup").update({"metadata": new_email}).eq("id", item["id"]).execute()
            st.success(f"Updated {item['value']}")
            st.cache_data.clear()
            st.rerun()
        if c3.button("Remove", key=f"del_email_{item['id']}"):
            delete_lookup(item["id"])
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("**Add carrier email**")
    ne1, ne2, ne3 = st.columns([3, 4, 1])
    new_email_carrier = ne1.text_input("Carrier name", key="new_email_carrier",
                                        label_visibility="collapsed", placeholder="Carrier name")
    new_email_addr = ne2.text_input("Email address", key="new_email_addr",
                                     label_visibility="collapsed", placeholder="carrier@example.com")
    if ne3.button("Add", key="add_email", type="primary"):
        if new_email_carrier.strip():
            if add_lookup("carrier_email", new_email_carrier.strip().upper(), new_email_addr.strip()):
                st.success(f"Added {new_email_carrier.strip().upper()}")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Carrier already exists")
        else:
            st.error("Enter a carrier name")

# --- configuration ---
with tab5:
    st.subheader("Configuration")
    config = load_config()

    st.markdown("**Email settings**")
    cc_email = config.get("cc_email", {}).get("value", "")
    new_cc = st.text_input("Internal CC email", value=cc_email,
                            help="This email is CC'd on all empty container notifications")
    if new_cc != cc_email:
        update_config("cc_email", new_cc)
        st.success("CC email updated")

    sender_email = config.get("sender_email", {}).get("value", "")
    new_sender = st.text_input("Sender email", value=sender_email,
                                help="Email address notifications are sent from")
    if new_sender != sender_email:
        update_config("sender_email", new_sender)
        st.success("Sender email updated")

    st.divider()
    st.markdown("**SLA settings**")

    unload_days = config.get("unload_sla_days", {}).get("value", "3")
    new_unload = st.number_input("Unload SLA (days)", min_value=1, max_value=30,
                                  value=int(unload_days),
                                  help="Days from arrival before unload SLA is breached")
    if str(new_unload) != unload_days:
        update_config("unload_sla_days", str(new_unload))
        st.success("Unload SLA updated")

    receive_days = config.get("receive_sla_days", {}).get("value", "2")
    new_receive = st.number_input("Receive report SLA (days)", min_value=1, max_value=30,
                                   value=int(receive_days),
                                   help="Days after empty before receive report SLA is breached")
    if str(new_receive) != receive_days:
        update_config("receive_sla_days", str(new_receive))
        st.success("Receive report SLA updated")

    st.divider()
    st.markdown("**Email API**")
    st.info("Email notifications require an API key. Once you have your SendGrid or Resend API key, enter it here.")
    api_key = config.get("email_api_key", {}).get("value", "")
    new_api_key = st.text_input("Email API key", value=api_key, type="password",
                                 help="API key for sending email notifications")
    if new_api_key != api_key:
        db = get_db()
        if api_key:
            db.table("settings_config").update({"value": new_api_key}).eq("key", "email_api_key").execute()
        else:
            db.table("settings_config").insert({
                "key": "email_api_key",
                "value": new_api_key,
                "description": "API key for email notifications"
            }).execute()
        st.success("API key saved")
