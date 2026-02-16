# app.py
import streamlit as st

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
# AUTH: Supabase OTP login
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

# 2) If still not authenticated -> show login UI
if not st.session_state.get("authenticated"):
    st.markdown("<br><br><h2 style='text-align:center;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center; color:#64748b;'>Log in with your email (OTP) to access your household calendar ✨</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        email = st.text_input("Email", placeholder="you@email.com")
        st.session_state.login_email = email

        colA, colB = st.columns([1, 1], gap="small")
        with colA:
            if st.button("Send OTP", type="primary", use_container_width=True):
                ok, msg = supabase_send_otp(st, email)
                if ok:
                    st.session_state.otp_sent = True
                    st.success(msg)
                else:
                    st.error(msg)

        with colB:
            if st.button("Clear", use_container_width=True):
                st.session_state.otp_sent = False
                st.session_state.login_email = ""
                st.session_state.login_code = ""
                _clear_sid()
                st.rerun()

        if st.session_state.get("otp_sent"):
            code = st.text_input("OTP Code", placeholder="6-digit code", key="login_code")
            if st.button("Verify & Continue", use_container_width=True):
                ok, msg, sess = supabase_verify_otp(st, email, code)
                if not ok:
                    st.error(msg)
                else:
                    # Create persistent app session sid
                    sid = create_app_session(st, email)
                    if not sid:
                        st.error("Could not create app session. Check Supabase REST permissions.")
                        st.stop()

                    _set_sid(sid)
                    st.session_state.user_email = email.strip().lower()
                    st.session_state.authenticated = True
                    st.session_state.otp_sent = False
                    st.success("✅ Logged in")
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
kpis = compute_kpis()
checkin_item, checkin_mode = get_checkin_context()

render_metrics(
    kpis,
    checkin_item=checkin_item,
    checkin_mode=checkin_mode,
    on_checkin_yes=checkin_yes,
    on_checkin_no=checkin_no,
    on_checkin_snooze=checkin_snooze,
    on_checkin_reschedule=checkin_reschedule,
    on_checkin_delete=checkin_delete,
)

# -----------------------
# MAIN LAYOUT
# -----------------------
left, right = st.columns([2.2, 1.1], gap="large")

with left:
    render_command_center(
        history=st.session_state.get("chat_history") or [],
        submit_callback=submit_plan,
        toggle_camera_callback=toggle_camera,
    )

with right:
    render_right_column(
        drafts=st.session_state.get("pending_events") or [],
        calendar=st.session_state.get("calendar_events") or [],
        on_add=add_to_calendar,
        on_reject=reject_draft,
    )
