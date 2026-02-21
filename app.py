# app.py
import streamlit as st
import time

# UI only
from src.ui import (
    inject_css,
    render_sidebar,
    render_metrics,
    render_command_center,
    render_right_column,
)

# Flow only (state + actions)
from src.flow import (
    init_state,
    refresh_calendar,
    submit_plan,
    toggle_camera,
    add_to_calendar,
    reject_draft,
    begin_reconnect,
    clear_reconnect,
    complete_reconnect,
    compute_kpis,
    # check-in required
    get_checkin_context,
    checkin_yes,
    checkin_no,
    checkin_snooze,
    checkin_reschedule,
    checkin_delete,
    checkin_submit_feedback
)

from src.token_store import (
    supabase_send_otp,
    supabase_verify_otp,
    create_app_session,
    load_app_session,
)

# -----------------------
# APP CONFIG
# -----------------------
st.set_page_config(
    page_title="Family COO",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------
# BOOTSTRAP
# -----------------------
init_state()
inject_css()

# -----------------------
# QUERY PARAM HELPERS (sid)
# -----------------------
def _get_sid() -> str:
    try:
        v = st.query_params.get("sid", "")
        if isinstance(v, list):
            v = v[0] if v else ""
        return (v or "").strip()
    except Exception:
        try:
            qp = st.experimental_get_query_params()
            return ((qp.get("sid") or [""])[0]).strip()
        except Exception:
            return ""


def _set_sid(sid: str) -> None:
    sid = (sid or "").strip()
    if not sid:
        return
    try:
        st.query_params["sid"] = sid
    except Exception:
        try:
            st.experimental_set_query_params(sid=sid)
        except Exception:
            pass


def _clear_sid() -> None:
    try:
        if "sid" in st.query_params:
            del st.query_params["sid"]
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


# -----------------------
# AUTH: Simple Email + PIN (no OTP, no Google)
# -----------------------
# 1) Try restore from sid (refresh-safe)
if not st.session_state.get("authenticated"):
    sid = _get_sid()
    if sid:
        sdata = load_app_session(st, sid)
        email = (sdata.get("email") or "").strip().lower()
        if email:
            st.session_state.user_email = email
            st.session_state.authenticated = True

# 2) If still not authenticated -> show PIN login UI
if not st.session_state.get("authenticated"):
    # init (NO new keys without init)
    st.session_state.setdefault("login_email", "")
    st.session_state.setdefault("login_pin", "")
    st.session_state.setdefault("login_msg", "")
    st.session_state.setdefault("do_clear_login_widgets", False)

    # Safe clear (must happen before widgets render)
    if st.session_state.get("do_clear_login_widgets"):
        st.session_state["do_clear_login_widgets"] = False
        st.session_state["login_email"] = ""
        st.session_state["login_pin"] = ""
        st.session_state["login_msg"] = ""
        _clear_sid()

    st.markdown("<br><br><h2 style='text-align:center;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center; color:#64748b;'>Log in with your email and PIN to access Family COO ✨</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("pin_login_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="you@email.com", key="login_email")
            pin = st.text_input("PIN", placeholder="Enter PIN", key="login_pin", type="password")

            colA, colB = st.columns([1, 1], gap="small")
            with colA:
                login_submit = st.form_submit_button("Login", type="primary", use_container_width=True)
            with colB:
                clear_submit = st.form_submit_button("Clear", use_container_width=True)

        if clear_submit:
            st.session_state["do_clear_login_widgets"] = True
            st.rerun()

        # Message banner
        if st.session_state.get("login_msg"):
            msg = st.session_state["login_msg"]
            if "✅" in msg:
                st.success(msg)
            else:
                st.error(msg)

        if login_submit:
            email_norm = (email or "").strip().lower()
            pin_norm = (pin or "").strip()

            if not email_norm or "@" not in email_norm:
                st.session_state["login_msg"] = "Enter a valid email."
                st.rerun()

            if not pin_norm:
                st.session_state["login_msg"] = "Enter your PIN."
                st.rerun()

            # ✅ PIN config (simple + fool-proof)
            # Supported:
            # 1) st.secrets["auth"]["pin"] = "1234" (single PIN for all)
            # 2) st.secrets["auth"]["pins"][email] = "1234" (per-user PIN)
            auth = st.secrets.get("auth", {}) if hasattr(st, "secrets") else {}
            global_pin = str(auth.get("pin", "") or "").strip()
            pins_map = auth.get("pins", {}) or {}

            expected = ""
            if isinstance(pins_map, dict):
                expected = str(pins_map.get(email_norm, "") or "").strip()

            if (expected and pin_norm != expected) or (not expected and global_pin and pin_norm != global_pin) or (not expected and not global_pin):
                if not expected and not global_pin:
                    st.session_state["login_msg"] = "PIN auth is not configured. Add [auth] pin/pins in secrets.toml."
                else:
                    st.session_state["login_msg"] = "Invalid email or PIN."
                st.rerun()

            # ✅ Login success: create app session + persist sid
            sid = create_app_session(st, email_norm)
            if not sid:
                st.session_state["login_msg"] = "Could not create app session. Check Supabase REST permissions."
                st.rerun()

            _set_sid(sid)
            st.session_state.user_email = email_norm
            st.session_state.authenticated = True
            st.session_state["login_msg"] = "✅ Logged in"
            st.rerun()

    st.stop()

# -----------------------
# CALENDAR AUTO-REFRESH (light touch)
# -----------------------
if st.session_state.get("user_email") and st.session_state.get("calendar_events") is None:
    refresh_calendar()

# -----------------------
# SIDEBAR
# -----------------------
status = "🟢 Online" if st.session_state.get("calendar_online") else "🟡 Offline"
count = len(st.session_state.get("calendar_events") or [])

render_sidebar(
    status=status,
    count=count,
    on_start=begin_reconnect,
    on_clear=clear_reconnect,
    on_complete=complete_reconnect,
)

# -----------------------
# TOP METRICS + CHECK-IN REQUIRED
# -----------------------
kpis = compute_kpis(user_name=st.session_state.get("user_name", "Tushar"))
checkin_item, checkin_mode = get_checkin_context()

render_metrics(
    kpis 
)

# -----------------------
# MAIN LAYOUT
# -----------------------
left, right = st.columns([2.2, 1.1], gap="large")

# Use the correct callback that accepts the feedback string argument
from src.flow import checkin_yes_learning, checkin_no_with_feedback  # noqa: F401

with left:
    render_command_center(
        history=st.session_state.get("chat_history") or [],
        submit_callback=submit_plan,
        toggle_camera_callback=toggle_camera,
        checkin_item=checkin_item,
        on_checkin_yes=checkin_yes,
        on_checkin_no_with_feedback=checkin_no_with_feedback,  # ✅ FIX
    )

with right:
    render_right_column(
        drafts=st.session_state.get("pending_events") or [],
        calendar=st.session_state.get("calendar_events") or [],
        on_add=add_to_calendar,
        on_reject=reject_draft,
    )