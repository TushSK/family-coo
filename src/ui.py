import streamlit as st
import urllib.parse
from datetime import datetime


# ------------------------------------------------------------
# CSS
# ------------------------------------------------------------
def inject_css():
    import streamlit as st

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root{
            --primary:#4f46e5;          /* Indigo-600 */
            --primary-light:#e0e7ff;
            --bg-body:#f8fafc;          /* Slate-50 */
            --surface:#ffffff;
            --text-main:#0f172a;
            --text-muted:#64748b;
            --border:#e2e8f0;
            --success:#10b981;
            --warning:#f59e0b;
            --danger:#ef4444;
            --shadow-soft:0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
            --shadow-card:0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.02);
            --radius:16px;
        }

        * { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
        .stApp { background: var(--bg-body); }
        #MainMenu, footer, header { visibility: hidden; }

        /* Streamlit main container alignment */
        section.main > div { padding-top: 28px; }

        .block-container{
            max-width: 1400px;
            padding-top: 20px;
            padding-bottom: 48px;
            padding-left: 48px;
            padding-right: 48px;
        }

        @media (max-width: 1200px){
            .block-container{ padding-left: 32px; padding-right: 32px; }
        }
        @media (max-width: 900px){
            .block-container{ padding-left: 18px; padding-right: 18px; }
        }
        @media (max-width: 640px){
            .block-container{ padding-left: 12px; padding-right: 12px; padding-top: 12px; }
        }

        /* --------------------
           Sidebar
           -------------------- */
        section[data-testid="stSidebar"]{
            background: var(--surface);
            border-right: 1px solid var(--border);
        }
        section[data-testid="stSidebar"] > div{
            width: 260px;
            padding: 32px 24px;
        }

        @media (max-width: 900px){
            section[data-testid="stSidebar"] > div{
                width: 240px;
                padding: 26px 18px;
            }
        }

        .coo-brand{
            display:flex; align-items:center; gap:12px;
            margin-bottom: 28px;
        }
        .coo-brand-icon{
            width:40px; height:40px;
            border-radius: 12px;
            display:flex; align-items:center; justify-content:center;
            background: linear-gradient(135deg, #4f46e5 0%, #818cf8 100%);
            color: #fff;
            font-size: 18px;
            font-weight: 900;
            box-shadow: 0 4px 10px rgba(79,70,229,0.30);
        }
        .coo-brand-title{
            font-size: 1.1rem;
            font-weight: 900;
            letter-spacing: -0.02em;
            color: var(--text-main);
            line-height: 1.1;
        }
        .coo-brand-sub{
            font-size: .85rem;
            font-weight: 700;
            color: var(--text-muted);
            margin-top: 3px;
        }

        .coo-user-card{
            display:flex; align-items:center; gap:12px;
            padding: 12px;
            background: #f8fafc;
            border: 1px solid #eef2f7;
            border-radius: 14px;
            margin-bottom: 18px;
        }
        .coo-avatar{
            width: 42px; height: 42px;
            border-radius: 999px;
            display:flex; align-items:center; justify-content:center;
            background: var(--primary-light);
            color: #3730a3;
            font-weight: 900;
            flex: 0 0 auto;
        }
        .coo-user-name{ font-size: 14px; font-weight: 900; color: var(--text-main); }
        .coo-user-meta{ font-size: 12px; font-weight: 700; color: var(--text-muted); margin-top: 2px; }

        .coo-sidebar-label{
            font-size: 0.7rem;
            font-weight: 800;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin: 20px 0 10px;
        }

        .coo-status-row{
            display:flex;
            align-items:center;
            justify-content: space-between;
            gap: 10px;
            padding: 12px;
            border: 1px solid var(--border);
            border-radius: 14px;
            background: #ffffff;
            margin-bottom: 10px;
        }
        .coo-status-badge{
            display:inline-flex; align-items:center; gap:6px;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 900;
            border: 1px solid #d1fae5;
            background: #ecfdf5;
            color: #065f46;
        }
        .coo-status-badge.offline{
            border-color: #fee2e2;
            background: #fef2f2;
            color: #991b1b;
        }
        .coo-status-dot{
            width:8px; height:8px;
            border-radius: 999px;
            background: var(--success);
        }
        .coo-status-badge.offline .coo-status-dot{ background: var(--danger); }

        /* --------------------
           Header + Date
           -------------------- */
        .coo-header-row{
            display:flex;
            justify-content:space-between;
            align-items:flex-end;
            margin-bottom: 10px;
        }
        .coo-greeting h2{
            font-size: 1.75rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin: 0;
        }
        @media (max-width: 640px){
            .coo-greeting h2{ font-size: 1.35rem; }
        }
        .coo-greeting p{
            color: var(--text-muted);
            margin: 6px 0 0 0;
            font-weight: 600;
        }
        .coo-header-date{
            background: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 700;
            color: var(--text-muted);
            box-shadow: var(--shadow-soft);
            border: 1px solid #f1f5f9;
            display:inline-block;
        }

        /* --------------------
           KPI Grid
           -------------------- */
        .coo-metrics{
            display:grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 12px 0 14px 0;
        }
        @media (max-width: 1100px){ .coo-metrics{ grid-template-columns: repeat(2, 1fr);} }
        @media (max-width: 640px){ .coo-metrics{ grid-template-columns: 1fr; } }

        .coo-metric-card{
            background: var(--surface);
            padding: 20px;
            border-radius: var(--radius);
            box-shadow: var(--shadow-soft);
            border: 1px solid #f1f5f9;
            display:flex;
            justify-content:space-between;
            align-items:center;
        }
        .coo-metric-label{
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 6px;
            display:block;
        }
        .coo-metric-value{
            font-size: 2rem;
            font-weight: 900;
            color: var(--text-main);
            line-height: 1;
        }
        .coo-metric-icon{
            width:46px; height:46px;
            border-radius: 14px;
            display:flex;
            align-items:center;
            justify-content:center;
            background: var(--primary-light);
            color: var(--primary);
            font-size: 1.1rem;
            font-weight: 900;
        }

        .coo-reliability{ margin-top: 6px; }
        .coo-badge{
            display:inline-flex;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 900;
            font-size: 12px;
            background: #ecfdf5;
            color: #059669;
        }
        .coo-badge.med{ background:#fffbeb; color:#b45309; }
        .coo-badge.low{ background:#fef2f2; color:#b91c1c; }

        /* --------------------
           Hero Card — Layout 2.2 Parent container
           -------------------- */
        div[data-testid="stVerticalBlock"]:has(.coo-hero-marker){
            background: var(--surface);
            border: 1px solid #eef2f7;
            border-radius: 22px;
            box-shadow: var(--shadow-card);
            padding: 22px;
            margin-top: 12px;
        }
        @media (max-width: 640px){
            div[data-testid="stVerticalBlock"]:has(.coo-hero-marker){
                padding: 16px;
                border-radius: 18px;
            }
        }
        .coo-hero-title{
            font-size: 1.35rem;
            font-weight: 900;
            color: var(--text-main);
            margin: 6px 0 10px 0;
        }
        .coo-hero-divider{
            height: 1px;
            background: #eef2f7;
            margin: 18px 0 14px 0;
        }
        .coo-footer-label{
            font-weight: 900;
            color: var(--text-muted);
            margin-top: 8px;
        }

        /* --------------------
           Action Required (Smart Strip) — Layout 2.2 (RESPONSIVE)
           Buttons MUST appear inside the strip and never overlap.
           Uses :has() for robust targeting (no fragile sibling selectors).
           -------------------- */
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left){
            background:#eff6ff;
            border-left: 6px solid var(--primary);
            border-radius: 16px;
            padding: 16px 18px;
            box-shadow: var(--shadow-soft);
            margin: 14px 0 12px 0;

            /* ✅ make the strip itself a responsive flex row */
            display: flex !important;
            flex-wrap: wrap !important;
            align-items: center !important;
            justify-content: space-between !important;
            gap: 12px !important;
        }

        /* ✅ Streamlit columns inside the strip: keep safe min widths */
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]:nth-child(1){
            flex: 1 1 360px !important;
            min-width: 260px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]:nth-child(2),
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]:nth-child(3){
            flex: 0 0 120px !important;
            min-width: 110px !important;
        }

        .coo-smartstrip-left{
            display:flex;
            align-items:center;
            gap:12px;
            min-width: 0; /* ✅ allow text wrap */
        }
        .coo-smartstrip-icon{ font-size: 22px; line-height: 1; flex: 0 0 auto; }

        .coo-smartstrip-text{ min-width: 0; }
        .coo-smartstrip-text strong{
            display:block;
            font-weight: 900;
            color:#1e3a8a;
            font-size: 1.05rem;
            line-height: 1.2;
            word-break: break-word;
        }
        .coo-smartstrip-text span{
            display:block;
            color:#3b82f6;
            font-weight: 800;
            font-size: 1.0rem;
            margin-top: 3px;
            word-break: break-word;
        }
        .coo-smartstrip-text em{ font-style: italic; font-weight: 900; }

        /* YES button green (scoped only inside Action Required row) */
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) button[data-testid="baseButton-primary"]{
            background: #22c55e !important;
            border: 1px solid #16a34a !important;
            color: #ffffff !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) button[data-testid="baseButton-primary"]:hover{
            filter: brightness(0.95);
        }

        /* Button sizing only inside strip */
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) .stButton > button{
            height: 40px !important;
            border-radius: 12px !important;
            font-weight: 900 !important;

            /* ✅ prevent overflow into neighbor column */
            width: 100% !important;
            min-width: 96px !important;
            white-space: nowrap !important;
            box-sizing: border-box !important;
        }

        /* ✅ Mobile: stack (text then buttons full-width) */
        @media (max-width: 640px){
            div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]{
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }
            div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) .stButton > button{
                height: 42px !important;
                min-width: 100% !important;
            }
        }

        /* Feedback mini-panel (appears under strip, stays within hero) */
        .coo-checkin-feedback{
            margin-top: 10px;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 12px 12px 10px;
            box-shadow: var(--shadow-soft);
        }
        .coo-checkin-feedback-title{
            font-weight: 900;
            color: var(--text-main);
            margin-bottom: 6px;
        }

        /* Global buttons (keep consistent, do not override strip logic above) */
        .stButton > button{
            border-radius: 12px !important;
            font-weight: 800 !important;
            height: 44px !important;
        }

        /* --------------------
           Calendar (Right column) – Layout 2.2
           -------------------- */
        .coo-section-title{
            display:flex;
            align-items:center;
            gap:10px;
            font-weight: 900;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-size: 0.82rem;
            margin: 10px 0 12px 0;
        }

        /* Right Column event cards polish */
        .coo-event-card{
            border-radius: 16px;
            border: 1px solid #eef2f7;
            box-shadow: 0 8px 16px rgba(15,23,42,0.06);
            padding: 14px 14px;
            margin-bottom: 12px;
            background: #ffffff;
        }
        .coo-evt-time{ font-weight: 900; color: #0f172a; }
        .coo-evt-title{ font-weight: 900; line-height: 1.2; color: #0f172a; }
        .coo-evt-loc{ font-weight: 700; color: #64748b; }

        /* Draft look */
        .coo-event-card.coo-draft{
            background: #f9fafb;
            border: 2px dashed #334155;
            border-left: 6px solid var(--primary);
        }

        /* Upcoming look */
        .coo-event-card.coo-upcoming{
            border-left: 6px solid #22c55e;
        }

        /* Draft action buttons only */
        button[data-testid="baseButton-secondary"],
        button[data-testid="baseButton-primary"]{
            border-radius: 12px;
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
    import streamlit as st

    # Identity
    email = (st.session_state.get("user_email") or "").strip()
    display_name = (st.session_state.get("user_name") or "Tushar Khandare").strip()
    role_line = st.session_state.get("user_role_line") or "Admin • Tampa, FL"

    initials = _initials_from_email_or_name(email=email, fallback_name=display_name)
    is_online = "online" in (status or "").lower()

    # ensure current page state
    if "active_page" not in st.session_state:
        st.session_state.active_page = "dashboard"  # dashboard | calendar | memory | settings

    with st.sidebar:
        # Brand
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

        # User card
        st.markdown(
            f"""
            <div class="coo-user-card">
                <div class="coo-avatar">{initials}</div>
                <div>
                    <div class="coo-user-name">{display_name}</div>
                    <div class="coo-user-meta">{role_line}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # System status label + card
        st.markdown('<div class="coo-sidebar-label">SYSTEM STATUS</div>', unsafe_allow_html=True)

        badge_cls = "coo-status-badge" + ("" if is_online else " offline")
        badge_text = "Calendar ONLINE" if is_online else "Calendar OFFLINE"

        st.markdown(
            f"""
            <div class="coo-status-row">
                <div style="font-weight:900; color:#0f172a;">Calendar</div>
                <div class="{badge_cls}">
                    <span class="coo-status-dot"></span>
                    {badge_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption(f"Events loaded: {count}")

        # ----------------------------
        # Layout_2.2 Navigation (NEW)
        # ----------------------------
        st.markdown('<div class="coo-sidebar-label">MAIN MENU</div>', unsafe_allow_html=True)

        def nav_button(label, icon, key, page_name):
            active = st.session_state.active_page == page_name
            cls = "coo-nav-item active" if active else "coo-nav-item"
            clicked = st.button(
                f"{icon}  {label}",
                key=key,
                use_container_width=True,
            )
            # attach class via wrapper
            st.markdown(
                f"<script>const btn=document.querySelector('button[kind=\"secondary\"][data-testid=\"stBaseButton-secondary\"][id=\"{key}\"]');</script>",
                unsafe_allow_html=True,
            )
            if clicked:
                st.session_state.active_page = page_name
                st.rerun()

        # Streamlit doesn’t let us assign class directly to button,
        # so we style ALL sidebar buttons in CSS using container grouping.
        # The “active” highlighting is handled in ui.py render blocks.

        # Buttons
        if st.button("📊  Dashboard", use_container_width=True):
            st.session_state.active_page = "dashboard"
            st.rerun()

        if st.button("🗓️  Calendar View", use_container_width=True):
            st.session_state.active_page = "calendar"
            st.rerun()

        if st.button("🧠  Memory Bank", use_container_width=True):
            st.session_state.active_page = "memory"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="coo-sidebar-label">SYSTEM</div>', unsafe_allow_html=True)

        if st.button("⚙️  Settings", use_container_width=True):
            st.session_state.active_page = "settings"
            st.rerun()

        st.markdown("---")

        # Logout
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_email = ""
            st.session_state.otp_sent = False
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


import streamlit as st

def render_metrics(
    kpis: dict,
    checkin_item=None,
    checkin_mode: str = "ask",
    on_checkin_yes=None,
    on_checkin_no=None,
    on_checkin_snooze=None,
    on_checkin_reschedule=None,
    on_checkin_delete=None,
):
    """
    Renders ONLY:
      - Header row
      - KPI cards (Upcoming, Learned Patterns, Reliability, Date)

    NOTE:
      Action Required (Smart Strip) is rendered inside the main hero card
      in render_command_center() to match Layout_2.2 parent-child design.
    """
    import streamlit as st

    # --- Header ---
    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            f"""
            <div class="coo-header-row">
              <div class="coo-greeting">
                <h2>{kpis.get("greeting","Good Day")}, {kpis.get("name","") } 👋</h2>
                <p>You have <b>{kpis.get("upcoming_week",0)}</b> upcoming events this week.</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f"<div class='coo-header-date'>{kpis.get('header_date','')}</div>",
            unsafe_allow_html=True,
        )

    # --- KPI Cards ---
    upcoming = int(kpis.get("upcoming_week", 0))
    learnings = int(kpis.get("learnings", 0))
    reliability = int(kpis.get("reliability", 0))
    date_label = kpis.get("date_label", "")

    if reliability >= 90:
        badge_class, badge_text = "coo-badge", "High"
    elif reliability >= 75:
        badge_class, badge_text = "coo-badge med", "Medium"
    else:
        badge_class, badge_text = "coo-badge low", "Low"

    st.markdown(
        f"""
        <div class="coo-metrics">
          <div class="coo-metric-card">
            <div>
              <span class="coo-metric-label">Upcoming</span>
              <div class="coo-metric-value">{upcoming}</div>
            </div>
            <div class="coo-metric-icon">🗓️</div>
          </div>

          <div class="coo-metric-card">
            <div>
              <span class="coo-metric-label">Learned Patterns</span>
              <div class="coo-metric-value">{learnings}</div>
            </div>
            <div class="coo-metric-icon">🧠</div>
          </div>

          <div class="coo-metric-card">
            <div>
              <span class="coo-metric-label">Reliability</span>
              <div class="coo-metric-value">{reliability}%</div>
              <div class="coo-reliability">
                <span class="{badge_class}">{badge_text}</span>
              </div>
            </div>
            <div class="coo-metric-icon">✅</div>
          </div>

          <div class="coo-metric-card">
            <div>
              <span class="coo-metric-label">Date</span>
              <div class="coo-metric-value">{date_label}</div>
            </div>
            <div class="coo-metric-icon">📅</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_checkin_smart_strip():
    """
    Renders the Check-in Required strip + inline buttons (Yes/No/Snooze),
    and the action-mode buttons (Reschedule/Delete) when user clicked No.

    Uses only native Streamlit widgets, so backend callbacks work.
    Safe: if flow functions are missing, it won't crash the whole UI.
    """
    # ---- imports (best-effort, do not crash UI) ----
    try:
        from src.flow import (
            get_checkin_context,
            checkin_yes,
            checkin_no,
            checkin_snooze,
            checkin_reschedule,
            checkin_delete,
        )
    except Exception:
        # If your project uses flat imports
        try:
            from flow import (
                get_checkin_context,
                checkin_yes,
                checkin_no,
                checkin_snooze,
                checkin_reschedule,
                checkin_delete,
            )
        except Exception:
            return  # can't render check-in without flow layer

    # ---- get current mission + mode ----
    mission, mode = (None, "ask")
    try:
        mission, mode = get_checkin_context()
    except Exception:
        mission, mode = (None, "ask")

    if not mission:
        return  # nothing to check-in, render nothing (matches Layout behavior)

    title = (mission.get("title") or "this item").strip()

    # ---- strip + inline buttons row ----
    left, right = st.columns([7, 3], gap="large")

    with left:
        st.markdown(
            f"""
            <div class="coo-followup coo-checkin-strip">
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
        # Buttons aligned with strip: keep them compact and inline
        st.markdown('<div class="coo-checkin-actions">', unsafe_allow_html=True)

        if mode == "ask":
            b1, b2, b3 = st.columns(3, gap="small")
            with b1:
                st.button("✅ Yes", use_container_width=True, on_click=checkin_yes, key="chk_yes")
            with b2:
                st.button("❌ No", use_container_width=True, on_click=checkin_no, key="chk_no")
            with b3:
                # default snooze 4h; adjust if you want 2h/6h etc.
                st.button("⏰ Snooze", use_container_width=True, on_click=checkin_snooze, kwargs={"hours": 4}, key="chk_snooze")

        else:
            # action mode (user clicked No)
            b1, b2 = st.columns(2, gap="small")
            with b1:
                st.button("🔁 Reschedule", use_container_width=True, on_click=checkin_reschedule, key="chk_reschedule")
            with b2:
                st.button("🗑️ Delete", use_container_width=True, on_click=checkin_delete, key="chk_delete")

        st.markdown("</div>", unsafe_allow_html=True)

    # ---- Optional: inputs shown ONLY when needed ----
    # Keep layout clean: show reason always in action mode; show reason optional in ask mode
    if mode == "action":
        st.text_input(
            "Why was it missed?",
            key="checkin_reason",
            placeholder="traffic, tired, got busy, kid's homework...",
            label_visibility="collapsed",
        )

        with st.expander("Set a new time (only if rescheduling)", expanded=False):
            st.text_input(
                "New time",
                key="checkin_reschedule_when",
                placeholder="tomorrow at 7:30am",
                label_visibility="collapsed",
            )


# ------------------------------------------------------------
# COMMAND CENTER (left column)
# ------------------------------------------------------------
def render_command_center(
    history,
    submit_callback,
    toggle_camera_callback,
    checkin_item=None,
    on_checkin_yes=None,
    on_checkin_no_with_feedback=None,
):
    import streamlit as st

    # --- Safe init ---
    st.session_state.setdefault("checkin_feedback_open", False)
    st.session_state.setdefault("checkin_feedback_text", "")

    # ✅ Deferred clear flags
    st.session_state.setdefault("clear_plan_text", False)
    st.session_state.setdefault("clear_conversation", False)

    # Keys used by flow.py init_state()
    st.session_state.setdefault("plan_text", "")
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("last_result_type", None)
    st.session_state.setdefault("last_result_text", "")

    # ✅ Clear BEFORE widget instantiation (mandatory rule)
    if st.session_state.get("clear_plan_text"):
        st.session_state["plan_text"] = ""
        st.session_state["clear_plan_text"] = False

    # ✅ Clear conversation BEFORE rendering chat UI
    if st.session_state.get("clear_conversation"):
        st.session_state["chat_history"] = []
        st.session_state["last_result_type"] = None
        st.session_state["last_result_text"] = ""
        st.session_state["clear_conversation"] = False

    with st.container():
        st.markdown('<div class="coo-hero-marker"></div>', unsafe_allow_html=True)

        # ===== Action Required strip =====
        if checkin_item:
            title = (checkin_item.get("title") or "this item").strip()
            prompt = f'Did you complete "{title}"?'

            left, yes_col, no_col = st.columns([7, 1.3, 1.3], gap="small")

            with left:
                st.markdown(
                    f"""
                    <div class="coo-smartstrip-left">
                      <div class="coo-smartstrip-icon">🔔</div>
                      <div class="coo-smartstrip-text">
                        <strong>Action Required:</strong>
                        <span>{prompt}</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with yes_col:
                if st.button("Yes", key="coo_checkin_yes", type="primary", use_container_width=True):
                    if callable(on_checkin_yes):
                        on_checkin_yes()
                    st.session_state["checkin_feedback_open"] = False
                    st.session_state["checkin_feedback_text"] = ""
                    st.rerun()

            with no_col:
                if st.button("No", key="coo_checkin_no", use_container_width=True):
                    st.session_state["checkin_feedback_open"] = True
                    st.rerun()

            if st.session_state.get("checkin_feedback_open"):
                st.markdown('<div class="coo-checkin-feedback">', unsafe_allow_html=True)
                st.markdown(
                    '<div class="coo-checkin-feedback-title">Quick feedback (1 line)</div>',
                    unsafe_allow_html=True,
                )
                st.text_input(
                    label="",
                    key="checkin_feedback_text",
                    placeholder="e.g., got busy",
                    label_visibility="collapsed",
                )
                f1, f2 = st.columns([1, 1], gap="small")
                with f1:
                    if st.button("Save", key="coo_checkin_save", use_container_width=True):
                        txt = (st.session_state.get("checkin_feedback_text") or "").strip()
                        if callable(on_checkin_no_with_feedback):
                            on_checkin_no_with_feedback(txt)
                        st.session_state["checkin_feedback_open"] = False
                        st.session_state["checkin_feedback_text"] = ""
                        st.rerun()
                with f2:
                    if st.button("Cancel", key="coo_checkin_cancel", use_container_width=True):
                        st.session_state["checkin_feedback_open"] = False
                        st.session_state["checkin_feedback_text"] = ""
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        # ===== Input =====
        st.markdown("<div class='coo-hero-title'>📝 Plan your day</div>", unsafe_allow_html=True)

        st.text_area(
            "Command",
            key="plan_text",
            placeholder="e.g. 'Plan a movie night this Saturday at 7 PM...'",
            height=140,
            label_visibility="collapsed",
        )

        t1, t2, t3 = st.columns([1, 1, 1.4], gap="small")

        with t1:
            if st.button("📷 Scan", use_container_width=True):
                if callable(toggle_camera_callback):
                    toggle_camera_callback()
                st.rerun()

        with t2:
            if st.button("🔄 Reset", use_container_width=True):
                # ✅ Deferred clear (no direct mutation of widget key here)
                st.session_state["clear_plan_text"] = True
                st.session_state["clear_conversation"] = True
                st.rerun()

        with t3:
            if st.button("🚀 Execute", type="primary", use_container_width=True):
                if callable(submit_callback):
                    submit_callback()
                st.rerun()

        # ===== Conversation =====
        st.markdown("<div class='coo-hero-divider'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-weight:900; font-size:14px; margin:6px 0 10px 0;'>💬 Conversation</div>",
            unsafe_allow_html=True,
        )

        history = history or []
        if not history:
            st.info("No messages yet. Type something and click Execute.")
        else:
            for msg in history[-12:]:
                role = (msg.get("role") or "assistant").strip().lower()
                content = msg.get("content") or ""
                if role not in ("user", "assistant"):
                    role = "assistant"
                with st.chat_message(role):
                    st.write(content)

        # ===== Train the Brain =====
        st.markdown("<div class='coo-hero-divider'></div>", unsafe_allow_html=True)

        fL, fM, fR = st.columns([1.2, 3.6, 1.0], gap="small")
        with fL:
            st.markdown("<div class='coo-footer-label'>💡 Train the Brain:</div>", unsafe_allow_html=True)
            st.checkbox("Bad Response?", key="brain_bad_response")
        with fM:
            st.text_input(
                "Input",
                key="brain_correction",
                placeholder="Correction (e.g. 'Gym is closed Sundays')",
                label_visibility="collapsed",
            )
        with fR:
            if st.button("Save", use_container_width=True, key="brain_save"):
                st.toast("Saved.")
# ------------------------------------------------------------
# RIGHT COLUMN (drafts + schedule)
# ------------------------------------------------------------
def render_right_column(drafts, calendar, on_add, on_reject):
    import streamlit as st
    import re
    from datetime import datetime

    def _format_start_any(val) -> str:
        # If already datetime
        if isinstance(val, datetime):
            return val.strftime("%a, %b %d @ %I:%M %p")

        s = str(val or "").strip()
        if not s:
            return "—"

        # Normalize common variants:
        # "YYYY-MM-DD HH:MM:SS-0500" -> "...-05:00"
        s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
        # "19:00:00 -05:00" -> "19:00:00-05:00"
        s = re.sub(r"\s+([+-]\d{2}:\d{2})$", r"\1", s)
        # ensure T separator if needed
        if "T" not in s and len(s) >= 19 and s[10] == " ":
            s = s[:10] + "T" + s[11:]
        s = s.replace("Z", "+00:00")

        try:
            dt = datetime.fromisoformat(s)
            return dt.strftime("%a, %b %d @ %I:%M %p")
        except Exception:
            return str(val)

    # -----------------------
    # DRAFTING
    # -----------------------
    st.markdown(
        '<div class="coo-sidebar-label" style="margin-top:0;">DRAFTING</div>',
        unsafe_allow_html=True
    )

    if not drafts:
        st.caption("No drafts yet. Type a plan and click Execute Plan.")
    elif not drafts:
        st.caption("No drafts yet. Type a plan and click Execute Plan.")

    else:
        for i, d in enumerate(drafts):
            title = (d.get("title") or "Event").strip()
            raw_start = d.get("start_friendly") or d.get("start_time") or ""
            start = _format_start_any(raw_start)
            loc = (d.get("location") or "").strip()

            st.markdown(
                f"""
                <div class="coo-event-card coo-draft">
                    <div class="coo-evt-time">{start}</div>
                    <div class="coo-evt-title">{title}</div>
                    <div class="coo-evt-loc">📍 {loc if loc else "—"}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            c1, c2 = st.columns([1, 1], gap="small")
            with c1:
                if st.button("✅ Confirm", key=f"draft_confirm_{i}", use_container_width=True):
                    on_add(d)
                    st.rerun()
            with c2:
                if st.button("❌ Reject", key=f"draft_reject_{i}", use_container_width=True):
                    on_reject(d)
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------
    # UPCOMING
    # -----------------------
    st.markdown('<div class="coo-sidebar-label">UPCOMING</div>', unsafe_allow_html=True)

    if not calendar:
        st.info("No upcoming events.")
        return

    # Show first event as "Upcoming" (or first few if you prefer)
    for e in calendar[:1]:
        title = (e.get("title") or "Event").strip()
        raw_start = e.get("start_friendly") or e.get("start_time") or ""
        start = _format_start_any(raw_start)
        loc = (e.get("location") or "").strip()

        st.markdown(
            f"""
            <div class="coo-event-card coo-upcoming">
                <div class="coo-evt-time">{start}</div>
                <div class="coo-evt-title">{title}</div>
                <div class="coo-evt-loc">📍 {loc if loc else "—"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------
    # LIVE CALENDAR (7 DAYS)
    # -----------------------
    st.markdown(
        '<div class="coo-section-title">📅 LIVE CALENDAR (7 DAYS)</div>',
        unsafe_allow_html=True,
    )

    # Show a few upcoming items (adjust slice if you want)
    for e in calendar[:8]:
        title = (e.get("title") or "Event").strip()
        raw_start = e.get("start_friendly") or e.get("start_time") or ""
        start = _format_start_any(raw_start)
        loc = (e.get("location") or "").strip()

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

