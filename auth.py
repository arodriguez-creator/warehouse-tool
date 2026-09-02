from supabase import create_client
import streamlit as st

def get_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def login():
    st.markdown("""
    <div style="max-width:400px;margin:4rem auto;padding:2rem;
                background:#ffffff;border-radius:12px;
                border:1.5px solid #d1d5db;
                box-shadow:0 2px 6px rgba(0,0,0,0.08);">
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#1a2332;padding:1rem 1.5rem;border-radius:8px;
                margin-bottom:1.5rem;text-align:center;">
      <p style="margin:0;font-size:20px;font-weight:500;color:#ffffff;">Brodiaea Operations</p>
      <p style="margin:0;font-size:12px;color:#9ca3af;">Sign in to continue</p>
    </div>
    """, unsafe_allow_html=True)

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary", use_container_width=True):
        if not email or not password:
            st.error("Please enter your email and password")
        else:
            try:
                supabase = get_supabase()
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state["user"] = response.user
                st.session_state["access_token"] = response.session.access_token
                st.rerun()
            except Exception:
                st.error("Invalid email or password")

    st.markdown("</div>", unsafe_allow_html=True)

def logout():
    st.session_state.pop("user", None)
    st.session_state.pop("access_token", None)
    st.rerun()

def require_auth():
    if "user" not in st.session_state:
        login()
        st.stop()

def get_supabase_client():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    client = create_client(url, key)
    if "access_token" in st.session_state:
        client.auth.set_session(
            st.session_state["access_token"],
            st.session_state.get("refresh_token", "")
        )
    return client

def show_user():
    with st.sidebar:
        st.caption(f"👤 {st.session_state['user'].email}")
        if st.button("Sign out", use_container_width=True):
            logout()