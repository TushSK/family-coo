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
    import time  # do not assume
    import re    # do not assume

    # init (NO new keys without init)
    st.session_state.setdefault("otp_sent", False)
    st.session_state.setdefault("otp_last_sent_ts", 0.0)
    st.session_state.setdefault("otp_request_inflight", False)

    # cooldown + block window
    st.session_state.setdefault("otp_blocked_until_ts", 0.0)
    # ✅ Normal (non-429) cooldown is 30 seconds
    st.session_state.setdefault("otp_cooldown_sec", 30)

    # safe clear flag
    st.session_state.setdefault("do_clear_login_widgets", False)

    # If user clicked Clear last run, reset widget keys BEFORE creating widgets
    if st.session_state.get("do_clear_login_widgets"):
        st.session_state["do_clear_login_widgets"] = False
        st.session_state["login_email"] = ""
        st.session_state["login_code"] = ""
        st.session_state["otp_sent"] = False
        st.session_state["otp_request_inflight"] = False
        st.session_state["otp_last_sent_ts"] = 0.0
        st.session_state["otp_blocked_until_ts"] = 0.0
        st.session_state["otp_cooldown_sec"] = 30
        _clear_sid()

    st.markdown("<br><br><h2 style='text-align:center;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center; color:#64748b;'>Log in with your email (OTP) to access your household calendar ✨</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("otp_login_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="you@email.com", key="login_email")

            now = time.time()

            blocked_until = float(st.session_state.get("otp_blocked_until_ts") or 0.0)
            block_left = max(0, int(blocked_until - now))

            cooldown = int(st.session_state.get("otp_cooldown_sec") or 30)
            elapsed = now - float(st.session_state.get("otp_last_sent_ts") or 0.0)
            cooldown_left = max(0, int(cooldown - elapsed))

            # effective timer (max of both protections)
            seconds_left = max(block_left, cooldown_left)
            can_send_otp = (seconds_left <= 0) and (not st.session_state.get("otp_request_inflight"))

            colA, colB = st.columns([1, 1], gap="small")
            with colA:
                send_submit = st.form_submit_button(
                    "Send OTP",
                    type="primary",
                    use_container_width=True,
                    disabled=not can_send_otp,
                )
            with colB:
                clear_submit = st.form_submit_button("Clear", use_container_width=True)

        # Clear (safe): set flag + rerun (do NOT modify widget keys here)
        if clear_submit:
            st.session_state["do_clear_login_widgets"] = True
            st.rerun()

        # Live timer UI + smart auto-refresh tick (only when blocked/cooling)
        if seconds_left > 0:
            st.warning(f"OTP rate-limited or cooling down. Retry in **{seconds_left}s**.")
            time.sleep(1)
            st.rerun()

        # Send OTP
        if send_submit:
            if not email or "@" not in email:
                st.error("Enter a valid email.")
            elif st.session_state.get("otp_request_inflight"):
                st.warning("OTP request already in progress. Please wait…")
            else:
                st.session_state.otp_request_inflight = True
                ok, msg = supabase_send_otp(st, email)
                st.session_state.otp_request_inflight = False

                now2 = time.time()

                if ok:
                    st.session_state.otp_sent = True
                    st.session_state.otp_last_sent_ts = now2
                    st.session_state.otp_blocked_until_ts = 0.0
                    # ✅ normal cooldown back to 30s
                    st.session_state.otp_cooldown_sec = 30
                    st.success(msg)
                else:
                    m = str(msg or "")
                    m_low = m.lower()

                    # Default: keep normal 30s cooldown on any failure
                    st.session_state.otp_last_sent_ts = now2
                    st.session_state.otp_cooldown_sec = 30

                    # ✅ If 429/rate limit: extract WAIT seconds correctly (ignore 429)
                    if ("429" in m) or ("rate" in m_low) or ("limit" in m_low):
                        nums = [int(n) for n in re.findall(r"\d+", m)]

                        # If message contains 429 plus wait seconds, ignore 429 and pick a reasonable wait.
                        # Prefer any value between 5 and 300; otherwise fallback to 180.
                        candidates = [n for n in nums if n != 429 and 5 <= n <= 400]

                        wait_s = 30
                        if candidates:
                            # pick the largest candidate (usually the real wait)
                            wait_s = max(candidates)

                        st.session_state.otp_blocked_until_ts = now2 + max(1, int(wait_s))
                        # keep cooldown aligned with wait window so the max() timer is correct
                        st.session_state.otp_cooldown_sec = max(30, int(wait_s))

                    st.error(msg)

        # Verify OTP
        if st.session_state.get("otp_sent"):
            code = st.text_input("OTP Code", placeholder="6-digit code", key="login_code")
            if st.button("Verify & Continue", use_container_width=True):
                ok, msg, sess = supabase_verify_otp(st, email, code)
                if not ok:
                    st.error(msg)
                else:
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