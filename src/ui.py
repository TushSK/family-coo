import streamlit as st
import urllib.parse
from datetime import datetime


# ------------------------------------------------------------
# CSS
# ------------------------------------------------------------
def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root{
            --primary:#3b82f6;
            --primary-dark:#2563eb;
            --bg-body:#f8fafc;
            --bg-card:#ffffff;
            --text-main:#0f172a;
            --text-muted:#64748b;
            --border:#e2e8f0;
            --success:#10b981;
            --warning:#f59e0b;
            --danger:#ef4444;
            --shadow-sm:0 1px 2px 0 rgba(0,0,0,.05);
            --shadow-md:0 4px 6px -1px rgba(0,0,0,.10), 0 2px 4px -1px rgba(0,0,0,.06);
        }

        * { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
        .stApp { background: var(--bg-body); }
        #MainMenu, footer, header { visibility: hidden; }
        .block-container { max-width: 1400px; padding-top: 1.2rem; padding-bottom: 3rem; }

        /* Sidebar skin */
        section[data-testid="stSidebar"]{
            background: var(--bg-card);
            border-right: 1px solid var(--border);
        }
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div{
            color: var(--text-main);
        }

        .coo-brand{
            display:flex; align-items:center; gap:12px;
            margin: 6px 0 18px 0;
        }
        .coo-brand-icon{ font-size: 28px; }
        .coo-brand-title{ font-size: 1.25rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1; }
        .coo-brand-sub{ font-size: 0.82rem; color: var(--text-muted); font-weight: 600; margin-top: 3px; }

        .coo-user-card{
            display:flex; align-items:center; gap:12px;
            padding:12px; background:#f1f5f9; border-radius:12px;
            border: 1px solid rgba(226,232,240,.5);
            margin-bottom: 16px;
        }
        .coo-avatar{
            width:40px; height:40px; border-radius:50%;
            background:#cbd5e1; display:flex; align-items:center; justify-content:center;
            font-weight:800; color:#475569;
        }
        .coo-user-name{ font-weight: 700; font-size: 0.95rem; }
        .coo-user-meta{ font-size: 0.80rem; color: var(--text-muted); font-weight: 600; }

        .coo-sidebar-label{
            text-transform: uppercase;
            font-size: 0.70rem;
            font-weight: 800;
            color: var(--text-muted);
            letter-spacing: .06em;
            margin: 10px 0 10px 0;
        }
        .coo-status-row{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
        .coo-status-badge{
            display:inline-flex; align-items:center; gap:6px;
            padding:4px 10px; border-radius: 20px;
            font-size: .75rem; font-weight: 800;
            background:#dcfce7; color:#166534;
            border: 1px solid rgba(22,101,52,.12);
        }
        .coo-status-dot{ width:8px; height:8px; border-radius:50%; background:#16a34a; }
        .coo-status-badge.offline{ background:#fef9c3; color:#854d0e; border-color: rgba(133,77,14,.14); }
        .coo-status-badge.offline .coo-status-dot{ background:#f59e0b; }

        /* Header row */
        .coo-header-row{
            display:flex; justify-content:space-between; align-items:flex-end;
            margin: 0 0 12px 0;
        }
        .coo-greeting h2{
            font-size: 1.8rem; font-weight: 800; letter-spacing: -0.02em;
            margin: 0;
        }
        .coo-greeting p{
            color: var(--text-muted);
            margin: 6px 0 0 0;
            font-weight: 600;
        }
        .coo-header-date{
            font-weight: 700;
            color: var(--text-muted);
        }

        /* Metrics grid (3 cards) */
        .coo-metrics{
            display:grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 16px;
        }
        .coo-metric-card{
            background: var(--bg-card);
            padding: 20px;
            border-radius: 16px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            display:flex; justify-content:space-between; align-items:center;
        }
        .coo-metric-label{
            display:block;
            font-size: .80rem;
            font-weight: 800;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: .04em;
            margin-bottom: 5px;
        }
        .coo-metric-value{
            font-size: 1.8rem;
            font-weight: 900;
            color: var(--text-main);
            line-height: 1;
        }
        .coo-metric-icon{
            width:48px; height:48px;
            border-radius: 12px;
            display:flex; align-items:center; justify-content:center;
            background:#f0f9ff;
            color: var(--primary);
            font-size: 1.2rem;
            font-weight: 700;
        }

        /* Follow-up alert (visual-only for now) */
        .coo-followup{
            background:#eff6ff;
            border-left:5px solid var(--primary);
            padding: 16px 20px;
            border-radius: 12px;
            display:flex;
            justify-content:space-between;
            align-items:center;
            box-shadow: var(--shadow-sm);
            margin: 6px 0 18px 0;
        }
        .coo-followup-left{ display:flex; align-items:center; gap: 12px; }
        .coo-followup-icon{ font-size: 1.4rem; }
        .coo-followup-title{ color:#1e3a8a; font-size: 1.05rem; font-weight: 900; display:block; }
        .coo-followup-sub{ color:#1e40af; font-size: .92rem; font-weight: 700; }

        /* Command card */
        .coo-card{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 24px;
            box-shadow: var(--shadow-md);
        }
        .coo-card-title{
            display:flex; justify-content:space-between; align-items:center;
            margin-bottom: 14px;
        }
        .coo-card-title h3{ margin:0; font-size: 1.05rem; font-weight: 900; }
        .coo-pill{
            font-size: .78rem; color: var(--text-muted);
            background:#f1f5f9;
            padding: 4px 10px;
            border-radius: 8px;
            font-weight: 800;
            border: 1px solid rgba(226,232,240,.8);
        }
        .coo-ai-bubble{
            background:#f0f9ff;
            border-left:4px solid var(--primary);
            padding: 16px;
            border-radius: 10px;
            color:#1e3a8a;
            font-weight: 650;
            line-height: 1.5;
            margin-bottom: 14px;
        }

        /* Feedback box */
        .coo-feedback{
            margin-top: 18px;
            padding: 18px;
            border-top: 1px solid var(--border);
            background: #f8fafc;
            border-radius: 12px;
        }
        .coo-feedback-head{
            display:flex; align-items:center; gap: 10px;
            font-weight: 900;
            color: var(--text-main);
            margin-bottom: 10px;
        }
        .coo-feedback-sub{
            margin-left:auto;
            font-size: .80rem;
            font-weight: 700;
            color: var(--text-muted);
        }

        /* Event cards */
        .coo-event-card{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            border-left: 4px solid var(--success);
            box-shadow: var(--shadow-sm);
            margin-bottom: 12px;
        }
        .coo-event-card.draft{
            border-left-color: var(--primary);
            border-style: dashed;
        }
        .coo-evt-time{ font-size: .80rem; font-weight: 900; color: var(--warning); margin-bottom: 4px; }
        .coo-evt-title{ font-weight: 900; color: var(--text-main); margin-bottom: 4px; }
        .coo-evt-loc{ font-size: .85rem; font-weight: 700; color: var(--text-muted); }

        /* Make Streamlit buttons look closer to HTML */
        .stButton > button{
            border-radius: 10px;
            font-weight: 850;
            height: 44px;
        }

        .coo-followup-actions{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:16px;
        }
        .coo-followup-right{
            display:flex;
            align-items:center;
            gap:10px;
        }
        .coo-pill{
            display:inline-flex;
            align-items:center;
            padding:6px 10px;
            border-radius:999px;
            font-size:12px;
            font-weight:600;
            background:#eef2ff;
            color:#3730a3;
            border:1px solid #e0e7ff;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------
def _initials_from_email_or_name(email: str, fallback_name: str = "Tushar"):
    email = (email or "").strip()
    if email and "@" in email:
        part = email.split("@", 1)[0]
        bits = [b for b in part.replace(".", " ").replace("_", " ").split() if b]
        if len(bits) >= 2:
            return (bits[0][0] + bits[1][0]).upper()
        return (bits[0][:2]).upper() if bits else "CO"
    # fallback name
    bits = [b for b in fallback_name.split() if b]
    if len(bits) >= 2:
        return (bits[0][0] + bits[1][0]).upper()
    return (fallback_name[:2]).upper()


def render_sidebar(status, count, on_start, on_clear, on_complete):
    is_online = "Online" in (status or "")
    email = st.session_state.get("user_email", "")
    loc = st.session_state.get("user_location", "Tampa, FL")
    initials = _initials_from_email_or_name(email, "Tushar Khandare")

    with st.sidebar:
        st.markdown(
            """
            <div class="coo-brand">
              <div class="coo-brand-icon">🏡</div>
              <div>
                <div class="coo-brand-title">Family COO</div>
                <div class="coo-brand-sub">AI Operations Center</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="coo-user-card">
              <div class="coo-avatar">{initials}</div>
              <div>
                <div class="coo-user-name">Tushar Khandare</div>
                <div class="coo-user-meta">Admin • {loc}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="coo-sidebar-label">System Status</div>', unsafe_allow_html=True)
        badge_class = "" if is_online else "offline"
        badge_text = "ONLINE" if is_online else "OFFLINE"
        st.markdown(
            f"""
            <div class="coo-status-row">
              <span style="font-size:0.9rem; font-weight:700; color:#475569;">Calendar</span>
              <span class="coo-status-badge {badge_class}">
                <span class="coo-status-dot"></span> {badge_text}
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("⚙️ Connection Settings"):
            email_in = st.text_input("Email", key="user_email")
            c1, c2 = st.columns(2)
            if c1.button("Connect", use_container_width=True):
                on_start(email_in)
                st.rerun()
            if c2.button("Clear", use_container_width=True):
                on_clear()
                st.rerun()

            if st.session_state.get("device_flow"):
                flow = st.session_state.device_flow
                st.info(f"Code: {flow.get('user_code')}")
                st.link_button("Verify Login", flow.get("verification_url"))
                if st.button("Complete", use_container_width=True):
                    ok, msg = on_complete()
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

        st.markdown("---")
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()


# ------------------------------------------------------------
# HEADER + METRICS + FOLLOWUP (front page top)
# ------------------------------------------------------------
def _day_greeting():
    h = datetime.now().hour
    if h < 12:
        return "Good Morning"
    if h < 17:
        return "Good Afternoon"
    return "Good Evening"


def render_metrics(
    kpis,
    checkin_item=None,
    checkin_mode="ask",
    on_checkin_yes=None,
    on_checkin_no=None,
    on_checkin_snooze=None,
    on_checkin_reschedule=None,
    on_checkin_delete=None,
):
    # --- Header + KPI cards (ALWAYS render) ---
    greeting = _day_greeting()
    name = "Tushar"
    upcoming = int(kpis.get("upcoming", 0) or 0)
    learnings = int(kpis.get("learnings", 0) or 0)
    missed = int(kpis.get("missed", 0) or 0)

    date_full = datetime.now().strftime("%b %d, %Y")
    date_short = datetime.now().strftime("%b %d")

    st.markdown(
        f"""
        <div class="coo-header-row">
          <div class="coo-greeting">
            <h2>{greeting}, {name} 👋</h2>
            <p>You have {upcoming} upcoming events this week.</p>
          </div>
          <div class="coo-header-date">{date_full}</div>
        </div>

        <div class="coo-metrics">
          <div class="coo-metric-card">
            <div>
              <span class="coo-metric-label">Upcoming</span>
              <div class="coo-metric-value">{upcoming}</div>
            </div>
            <div class="coo-metric-icon">📅</div>
          </div>

          <div class="coo-metric-card">
            <div>
              <span class="coo-metric-label">Learned Patterns</span>
              <div class="coo-metric-value">{learnings}</div>
            </div>
            <div class="coo-metric-icon" style="color:#10b981; background:#ecfdf5;">🧠</div>
          </div>

          <div class="coo-metric-card">
            <div>
              <span class="coo-metric-label">Date</span>
              <div class="coo-metric-value">{date_short}</div>
            </div>
            <div class="coo-metric-icon" style="color:#f59e0b; background:#fffbeb;">📆</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Check-in Required block ---
    if missed > 0:
        if checkin_item:
            title = (checkin_item.get("title") or "this item").strip()

        # ✅ Row layout: bar on left, actions on right (same line)
        left, right = st.columns([4.8, 3.2], gap="small", vertical_alignment="center")

        with left:
            st.markdown(
                f"""
                <div class="coo-followup" style="margin-bottom:0;">
                  <div class="coo-followup-left">
                    <div class="coo-followup-icon">🔔</div>
                    <div>
                      <span class="coo-followup-title">Check-in Required</span>
                      <span class="coo-followup-sub">Did you complete <b>{title}</b>?</span>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with right:
            if checkin_mode == "ask":
                b1, b2, b3 = st.columns([1, 1, 1], gap="small")
                with b1:
                    st.button("✅ Yes", use_container_width=True, on_click=on_checkin_yes)
                with b2:
                    st.button("❌ No", use_container_width=True, on_click=on_checkin_no)
                with b3:
                    st.button("⏰ Snooze", use_container_width=True, on_click=on_checkin_snooze, args=(4,))
            else:
                b1, b2 = st.columns([1, 1], gap="small")
                with b1:
                    st.button("🔁 Reschedule", use_container_width=True, on_click=on_checkin_reschedule)
                with b2:
                    st.button("🗑️ Delete", use_container_width=True, on_click=on_checkin_delete)

        # ✅ Ask mode: STOP here (no textbox shown)
        if checkin_mode == "ask":
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            return

        # ✅ Action mode (after NO):
        # Show ONLY ONE textbox (reason). Reschedule time goes in expander.
        st.text_input(
            "Why was it missed? (optional)",
            key="checkin_reason",
            placeholder="traffic, tired, got busy, kid's homework...",
            label_visibility="collapsed",
        )

        with st.expander("Set a new time (only if rescheduling)", expanded=False):
            st.text_input(
                "Reschedule to (e.g. tomorrow 6pm / Sat 10am)",
                key="checkin_reschedule_when",
                placeholder="tomorrow 6pm",
                label_visibility="collapsed",
            )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        return

    # fallback count-only
    st.markdown(
        f"""
        <div class="coo-followup">
          <div class="coo-followup-left">
            <div class="coo-followup-icon">🔔</div>
            <div>
              <span class="coo-followup-title">Check-in Required</span>
              <span class="coo-followup-sub">You have {missed} missed / no-response item(s).</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------
# COMMAND CENTER (left column)
# ------------------------------------------------------------
def render_command_center(history, submit_callback, toggle_camera_callback):
    # pick last assistant message for the blue "Brain" bubble
    last_ai = None
    if history:
        for msg in reversed(history):
            if msg.get("role") in ("assistant", "ai"):
                last_ai = msg.get("content")
                break

    if not last_ai:
        last_ai = "I noticed your routine patterns. Want me to schedule something for this weekend?"

    st.markdown('<div class="coo-card">', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="coo-card-title">
          <h3>📝 Command Center</h3>
          <span class="coo-pill">Ready</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="coo-ai-bubble">
          <strong>🤖 Brain:</strong> {last_ai}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Camera (optional)
    if st.session_state.get("show_camera"):
        st.camera_input("Take Photo", key="cam_input")

    st.text_area(
        "Message",
        key="plan_text",
        height=120,
        placeholder="Type your response or a new plan here.",
        label_visibility="collapsed",
    )

    # action row (Reset / Scan / Execute)
    c1, c2, c3 = st.columns([1, 1, 2.2], gap="small")
    with c1:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
    with c2:
        cam_label = "❌ Close" if st.session_state.get("show_camera") else "📷 Scan"
        st.button(cam_label, on_click=toggle_camera_callback, use_container_width=True)
    with c3:
        st.button("🚀 Execute Plan", type="primary", use_container_width=True, on_click=submit_callback)

    # Feedback box (UI only; safe storage in session state for now)
    st.markdown(
        """
        <div class="coo-feedback">
          <div class="coo-feedback-head">
            <span>💡 Train the Brain</span>
            <span class="coo-feedback-sub">Is the AI making mistakes?</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    f1, f2, f3 = st.columns([1.2, 3.0, 1.0], gap="small")
    with f1:
        st.checkbox("Bad Response?", key="feedback_bad")
    with f2:
        st.text_input("Correction", key="feedback_text", placeholder="Correction (e.g. 'Gym is closed Sundays')", label_visibility="collapsed")
    with f3:
        if st.button("Save", use_container_width=True, key="feedback_save"):
            # keep it simple: store timestamped feedback locally for now
            bucket = st.session_state.setdefault("feedback_bucket", [])
            bucket.append(
                {
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "bad": bool(st.session_state.get("feedback_bad")),
                    "text": (st.session_state.get("feedback_text") or "").strip(),
                }
            )
            st.toast("Saved. (Wiring to DB can be next step.)")

    st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# RIGHT COLUMN (drafts + schedule)
# ------------------------------------------------------------
def render_right_column(drafts, calendar, on_add, on_reject):
    # Drafts section
    if drafts:
        st.markdown(
            '<div style="font-weight:900; color: var(--primary); text-transform:uppercase; letter-spacing:.05em; font-size:.85rem; margin-bottom:10px;">✨ Proposed Draft</div>',
            unsafe_allow_html=True,
        )
        for ev in drafts:
            start = (ev.get("start_time") or "").replace("T", " ")
            title = ev.get("title") or "Untitled"
            loc = ev.get("location") or "TBD"

            st.markdown(
                f"""
                <div class="coo-event-card draft">
                  <div class="coo-evt-time">{start or "Draft time"}</div>
                  <div class="coo-evt-title">{title}</div>
                  <div class="coo-evt-loc">📍 {loc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            b1, b2 = st.columns(2, gap="small")
            if b1.button("Confirm", key=f"ok_{urllib.parse.quote_plus(title)}", use_container_width=True):
                on_add(ev)
                st.rerun()
            if b2.button("Reject", key=f"no_{urllib.parse.quote_plus(title)}", use_container_width=True):
                on_reject(ev)
                st.rerun()

    # Calendar section
    st.markdown(
        '<div style="font-weight:900; color: var(--text-muted); text-transform:uppercase; letter-spacing:.05em; font-size:.85rem; margin: 10px 0 10px 0;">📅 Live Calendar (7 Days)</div>',
        unsafe_allow_html=True,
    )

    if not calendar:
        st.info("No upcoming events.")
        return

    for e in (calendar[:8] if calendar else []):
        title = e.get("title", "Event")
        start = e.get("start_friendly", e.get("start_time", "")).replace("T", " ")
        loc = e.get("location", "")

        st.markdown(
            f"""
            <div class="coo-event-card">
              <div class="coo-evt-time">{start}</div>
              <div class="coo-evt-title">{title}</div>
              <div class="coo-evt-loc">📍 {loc if loc else "—"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
