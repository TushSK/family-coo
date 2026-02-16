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
    # ✅ check-in required (new)
    get_checkin_item,
    get_checkin_context,
    checkin_yes,
    checkin_no,
    checkin_snooze,
    checkin_reschedule,
    checkin_delete,
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
# AUTH (kept in app.py - simple gate)
# -----------------------
if not st.session_state.get("authenticated"):
    st.markdown("<br><br><h2 style='text-align:center;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center; color:#64748b;'>A tiny chief-of-staff for your home life ✨</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        pin = st.text_input("Enter PIN", type="password")
        if st.button("Unlock", type="primary", use_container_width=True):
            try:
                if pin == st.secrets["general"]["app_password"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("⛔ Incorrect PIN")
            except Exception:
                st.error("⛔ Missing app_password in secrets.toml")
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
