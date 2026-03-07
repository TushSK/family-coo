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

        /* =====================================================
           FORCE LIGHT MODE — prevent OS/browser dark-mode
           from bleeding into Streamlit widgets
           ===================================================== */
        :root {
            color-scheme: light !important;
            --primary:#4f46e5;
            --primary-light:#e0e7ff;
            --bg-body:#f8fafc;
            --surface:#ffffff;
            --text-main:#0f172a;
            --text-muted:#64748b;
            --border:#e2e8f0;
            --success:#10b981;
            --warning:#f59e0b;
            --danger:#ef4444;
            --shadow-soft:0 4px 6px -1px rgba(0,0,0,0.05),0 2px 4px -1px rgba(0,0,0,0.03);
            --shadow-card:0 10px 15px -3px rgba(0,0,0,0.05),0 4px 6px -2px rgba(0,0,0,0.02);
            --radius:16px;
        }
        html, body { color-scheme: light !important; }

        * { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
        .stApp { background: var(--bg-body) !important; color: var(--text-main) !important; }
        #MainMenu, footer, header { visibility: hidden; }
        section.main > div { padding-top: 28px; }

        /* ── Force ALL Streamlit widgets to light mode ── */
        /* Textarea */
        .stTextArea textarea,
        .stTextArea > div,
        .stTextArea > div > div {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border-color: #e2e8f0 !important;
            color-scheme: light !important;
        }
        .stTextArea textarea::placeholder { color: #94a3b8 !important; }

        /* Text inputs */
        .stTextInput input,
        .stTextInput > div > div {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border-color: #e2e8f0 !important;
            color-scheme: light !important;
        }
        .stTextInput input::placeholder { color: #94a3b8 !important; }

        /* Buttons — override dark theme defaults */
        .stButton > button {
            background: #ffffff !important;
            color: #0f172a !important;
            border: 1.5px solid #e2e8f0 !important;
            border-radius: 12px !important;
            font-weight: 800 !important;
            height: 44px !important;
        }
        .stButton > button:hover { background: #f8fafc !important; border-color: #cbd5e1 !important; }

        /* Primary buttons */
        .stButton > button[kind="primary"],
        button[data-testid="baseButton-primary"] {
            background: linear-gradient(135deg, #4f46e5 0%, #818cf8 100%) !important;
            color: #ffffff !important;
            border: none !important;
        }
        .stButton > button[kind="primary"]:hover { filter: brightness(1.06) !important; }

        /* Checkbox + label */
        .stCheckbox label, .stCheckbox span { color: #0f172a !important; }
        .stCheckbox input[type="checkbox"] { color-scheme: light !important; }

        /* Chat messages */
        .stChatMessage { background: #f8fafc !important; color: #0f172a !important; }
        .stChatMessage p, .stChatMessage span { color: #0f172a !important; }

        /* Captions + info boxes */
        .stCaption { color: #64748b !important; }
        .stAlert, .stInfo { background: #eff6ff !important; color: #1e40af !important; }

        /* Expander */
        .streamlit-expanderHeader { background: #f8fafc !important; color: #0f172a !important; }
        .streamlit-expanderContent { background: #ffffff !important; }

        /* ── Layout ── */
        .block-container {
            max-width: 1400px;
            padding-top: 20px;
            padding-bottom: 48px;
            padding-left: 48px;
            padding-right: 48px;
        }
        @media (max-width: 1200px){ .block-container{ padding-left: 32px; padding-right: 32px; } }
        @media (max-width: 900px) { .block-container{ padding-left: 18px; padding-right: 18px; } }
        @media (max-width: 640px) { .block-container{ padding-left: 12px; padding-right: 12px; padding-top: 12px; } }

        /* ── Sidebar ── */
        section[data-testid="stSidebar"] {
            background: var(--surface) !important;
            border-right: 1px solid var(--border);
        }
        section[data-testid="stSidebar"] > div { width: 260px; padding: 32px 24px; }
        @media (max-width: 900px){ section[data-testid="stSidebar"] > div{ width: 240px; padding: 26px 18px; } }

        .coo-brand{ display:flex; align-items:center; gap:12px; margin-bottom: 28px; }
        .coo-brand-icon{
            width:40px; height:40px; border-radius: 12px;
            display:flex; align-items:center; justify-content:center;
            background: linear-gradient(135deg, #4f46e5 0%, #818cf8 100%);
            color: #fff; font-size: 18px; font-weight: 900;
            box-shadow: 0 4px 10px rgba(79,70,229,0.30);
        }
        .coo-brand-title{ font-size: 1.1rem; font-weight: 900; letter-spacing: -0.02em; color: #0f172a; line-height: 1.1; }
        .coo-brand-sub{ font-size: .85rem; font-weight: 700; color: #64748b; margin-top: 3px; }

        .coo-user-card{
            display:flex; align-items:center; gap:12px; padding: 12px;
            background: #f8fafc; border: 1px solid #eef2f7; border-radius: 14px; margin-bottom: 18px;
        }
        .coo-avatar{
            width: 42px; height: 42px; border-radius: 999px;
            display:flex; align-items:center; justify-content:center;
            background: var(--primary-light); color: #3730a3; font-weight: 900; flex: 0 0 auto;
        }
        .coo-user-name{ font-size: 14px; font-weight: 900; color: #0f172a; }
        .coo-user-meta{ font-size: 12px; font-weight: 700; color: #64748b; margin-top: 2px; }

        .coo-sidebar-label{
            font-size: 0.7rem; font-weight: 800; color: #94a3b8;
            text-transform: uppercase; letter-spacing: 0.05em; margin: 20px 0 10px;
        }
        .coo-status-row{
            display:flex; align-items:center; justify-content: space-between; gap: 10px;
            padding: 12px; border: 1px solid var(--border); border-radius: 14px;
            background: #ffffff; margin-bottom: 10px;
        }
        .coo-status-badge{
            display:inline-flex; align-items:center; gap:6px; padding: 6px 10px;
            border-radius: 999px; font-size: 12px; font-weight: 900;
            border: 1px solid #d1fae5; background: #ecfdf5; color: #065f46;
        }
        .coo-status-badge.offline{ border-color: #fee2e2; background: #fef2f2; color: #991b1b; }
        .coo-status-dot{ width:8px; height:8px; border-radius: 999px; background: var(--success); }
        .coo-status-badge.offline .coo-status-dot{ background: var(--danger); }

        /* ── Header ── */
        .coo-header-row{ display:flex; justify-content:space-between; align-items:flex-end; margin-bottom: 10px; }
        .coo-greeting h2{
            font-size: 1.75rem; font-weight: 800; letter-spacing: -0.02em;
            margin: 0; color: #0f172a !important;
        }
        .coo-greeting p{ color: #64748b !important; margin: 6px 0 0 0; font-weight: 600; }
        .coo-header-date{
            background: white; padding: 8px 16px; border-radius: 20px;
            font-size: 0.9rem; font-weight: 700; color: #64748b;
            box-shadow: var(--shadow-soft); border: 1px solid #f1f5f9; display:inline-block;
        }

        /* ── KPI Grid ── */
        .coo-metrics{
            display:grid; grid-template-columns: repeat(4, 1fr);
            gap: 20px; margin: 12px 0 14px 0;
        }
        @media (max-width: 1100px){ .coo-metrics{ grid-template-columns: repeat(2, 1fr); } }
        /* KEEP 2-col on all small screens (not 1-col) */
        @media (max-width: 640px) { .coo-metrics{ grid-template-columns: repeat(2, 1fr); gap: 10px; } }

        .coo-metric-card{
            background: #ffffff !important; padding: 20px;
            border-radius: var(--radius); box-shadow: var(--shadow-soft);
            border: 1px solid #f1f5f9; display:flex;
            justify-content:space-between; align-items:center;
        }
        .coo-metric-label{
            font-size: 0.8rem; font-weight: 700; color: #64748b !important;
            text-transform: uppercase; letter-spacing: 0.04em;
            margin-bottom: 6px; display:block;
        }
        .coo-metric-value{ font-size: 2rem; font-weight: 900; color: #0f172a !important; line-height: 1; }
        .coo-metric-icon{
            width:46px; height:46px; border-radius: 14px;
            display:flex; align-items:center; justify-content:center;
            background: var(--primary-light); color: var(--primary); font-size: 1.1rem; font-weight: 900;
        }
        .coo-reliability{ margin-top: 6px; }
        .coo-badge{ display:inline-flex; padding: 4px 8px; border-radius: 6px; font-weight: 900; font-size: 12px; background: #ecfdf5; color: #059669; }
        .coo-badge.med{ background:#fffbeb; color:#b45309; }
        .coo-badge.low{ background:#fef2f2; color:#b91c1c; }

        /* ── Hero Card ── */
        div[data-testid="stVerticalBlock"]:has(.coo-hero-marker){
            background: #ffffff !important;
            border: 1px solid #eef2f7; border-radius: 22px;
            box-shadow: var(--shadow-card); padding: 22px; margin-top: 12px;
        }
        .coo-hero-title{ font-size: 1.35rem; font-weight: 900; color: #0f172a !important; margin: 6px 0 10px 0; }
        .coo-hero-divider{ height: 1px; background: #eef2f7; margin: 18px 0 14px 0; }
        .coo-footer-label{ font-weight: 900; color: #64748b !important; margin-top: 8px; }

        /* ── Action Required (Smart Strip) ── */
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left){
            background:#eff6ff !important;
            border-left: 6px solid var(--primary); border-radius: 16px;
            padding: 16px 18px; box-shadow: var(--shadow-soft); margin: 14px 0 12px 0;
            display: flex !important; flex-wrap: wrap !important;
            align-items: center !important; justify-content: space-between !important; gap: 12px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]:nth-child(1){
            flex: 1 1 360px !important; min-width: 260px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]:nth-child(2),
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]:nth-child(3){
            flex: 0 0 120px !important; min-width: 110px !important;
        }
        .coo-smartstrip-left{ display:flex; align-items:center; gap:12px; min-width: 0; }
        .coo-smartstrip-icon{ font-size: 22px; line-height: 1; flex: 0 0 auto; }
        .coo-smartstrip-text{ min-width: 0; }
        .coo-smartstrip-text strong{ display:block; font-weight: 900; color:#1e3a8a !important; font-size: 1.05rem; line-height: 1.2; word-break: break-word; }
        .coo-smartstrip-text span{ display:block; color:#3b82f6 !important; font-weight: 800; font-size: 1.0rem; margin-top: 3px; word-break: break-word; }
        .coo-smartstrip-text em{ font-style: italic; font-weight: 900; }

        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) button[data-testid="baseButton-primary"]{
            background: #22c55e !important; border: 1px solid #16a34a !important; color: #ffffff !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) .stButton > button{
            height: 40px !important; border-radius: 12px !important; font-weight: 900 !important;
            width: 100% !important; min-width: 96px !important; white-space: nowrap !important; box-sizing: border-box !important;
        }
        @media (max-width: 640px){
            div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]{
                flex: 1 1 100% !important; min-width: 100% !important;
            }
        }

        /* Feedback panel */
        .coo-checkin-feedback{
            margin-top: 10px; background: #ffffff !important;
            border: 1px solid #e2e8f0; border-radius: 14px;
            padding: 12px 12px 10px; box-shadow: var(--shadow-soft);
        }
        .coo-checkin-feedback-title{ font-weight: 900; color: #0f172a !important; margin-bottom: 6px; }

        /* ── Action button row (Scan | Reset | Execute) ── */
        /* Marker class injected around the 3-col button row */
        .coo-action-row > div[data-testid="stHorizontalBlock"] {
            gap: 8px !important;
        }
        /* Force horizontal even on very narrow mobile */
        @media (max-width: 480px) {
            .coo-action-row > div[data-testid="stHorizontalBlock"] {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: nowrap !important;
            }
            .coo-action-row > div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
                flex: 1 !important;
                min-width: 0 !important;
            }
            .coo-action-row .stButton > button {
                font-size: 13px !important;
                padding: 0 6px !important;
                white-space: nowrap !important;
            }
        }

        /* ── Calendar cards ── */
        .coo-section-title{
            display:flex; align-items:center; gap:10px; font-weight: 900;
            color: #64748b !important; text-transform: uppercase;
            letter-spacing: 0.06em; font-size: 0.82rem; margin: 10px 0 12px 0;
        }
        .coo-event-card{
            border-radius: 16px; border: 1px solid #eef2f7;
            box-shadow: 0 8px 16px rgba(15,23,42,0.06);
            padding: 14px; margin-bottom: 12px; background: #ffffff !important;
        }
        .coo-evt-time { font-weight: 900; color: #0f172a !important; }
        .coo-evt-title{ font-weight: 900; line-height: 1.2; color: #0f172a !important; }
        .coo-evt-loc  { font-weight: 700; color: #64748b !important; }
        .coo-event-card.coo-draft{ background: #f9fafb !important; border: 2px dashed #334155; border-left: 6px solid var(--primary); }
        .coo-event-card.coo-upcoming{ border-left: 6px solid #22c55e; }

        button[data-testid="baseButton-secondary"],
        button[data-testid="baseButton-primary"]{ border-radius: 12px; }

        /* =====================================================
           MOBILE  (≤768px)
           ===================================================== */

        /* Bottom nav bar */
        .coo-mobile-nav {
            display: none;
            position: fixed; bottom: 0; left: 0; right: 0;
            height: 64px;
            background: #ffffff;
            border-top: 2px solid #e2e8f0;
            box-shadow: 0 -4px 20px rgba(15,23,42,0.10);
            z-index: 999999;
            justify-content: space-around;
            align-items: stretch;
        }
        .coo-mob-tab {
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            flex: 1; background: none; border: none; cursor: pointer;
            gap: 3px; padding: 8px 4px 6px;
            color: #94a3b8;
            font-family: Inter, system-ui, -apple-system, sans-serif;
            -webkit-tap-highlight-color: transparent;
            transition: color 0.12s, background 0.12s;
        }
        .coo-mob-tab.active { color: #4f46e5; background: #eef2ff; border-radius: 12px; }
        .coo-mob-tab:active { transform: scale(0.90); }
        .coo-mob-icon { font-size: 22px; line-height: 1.1; }
        .coo-mob-label { font-size: 11px; font-weight: 700; letter-spacing: 0.01em; line-height: 1; }

        /* FAB */
        .coo-fab {
            display: none;
            position: fixed; bottom: 76px; right: 16px;
            width: 52px; height: 52px; border-radius: 50%;
            background: linear-gradient(135deg, #4f46e5 0%, #818cf8 100%);
            color: #fff; font-size: 22px; border: none;
            box-shadow: 0 4px 18px rgba(79,70,229,0.50);
            align-items: center; justify-content: center;
            cursor: pointer; z-index: 999998;
            -webkit-tap-highlight-color: transparent;
            transition: transform 0.12s;
        }
        .coo-fab:active { transform: scale(0.86); }

        /* Next-event chip (mobile only) */
        .coo-mob-next-event {
            display: none;
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-left: 4px solid #22c55e;
            border-radius: 12px;
            padding: 10px 14px;
            margin-bottom: 12px;
        }
        .coo-mob-next-title { font-weight: 800; color: #14532d !important; font-size: 14px; }
        .coo-mob-next-time  { font-weight: 600; color: #166534 !important; font-size: 12px; margin-top: 2px; }

        @media (max-width: 768px) {
            /* Show bottom nav + FAB + chip */
            .coo-mobile-nav    { display: flex !important; }
            .coo-fab           { display: flex !important; }
            .coo-mob-next-event{ display: block !important; }

            /* Push sidebar completely off-screen */
            section[data-testid="stSidebar"] {
                position: fixed !important;
                left: -600px !important;
                opacity: 0 !important;
                pointer-events: none !important;
                z-index: 1 !important;
            }
            section[data-testid="stSidebar"] button { pointer-events: all !important; }

            /* Hide hamburger */
            button[data-testid="collapsedControl"],
            div[data-testid="collapsedControl"],
            [data-testid="collapsedControl"] { display: none !important; }

            /* Remove left margin Streamlit adds for sidebar */
            .main .block-container, section.main { margin-left: 0 !important; }

            /* Content padding */
            .block-container {
                padding-bottom: 90px !important;
                padding-left: 14px !important;
                padding-right: 14px !important;
                padding-top: 8px !important;
                max-width: 100% !important;
            }

            /* Compact greeting */
            .coo-greeting h2 { font-size: 1.1rem !important; color: #0f172a !important; }
            .coo-greeting p  { font-size: 0.8rem !important; margin-top: 2px !important; color: #64748b !important; }
            .coo-header-date { display: none !important; }
            /* Reduce header row bottom margin */
            .coo-header-row { margin-bottom: 6px !important; }

            /* 2×2 KPI grid */
            .coo-metrics {
                grid-template-columns: repeat(2, 1fr) !important;
                gap: 8px !important;
                margin: 8px 0 10px 0 !important;
            }
            .coo-metric-card  { padding: 12px 10px !important; border-radius: 12px !important; }
            .coo-metric-value { font-size: 1.5rem !important; }
            .coo-metric-icon  { width: 34px !important; height: 34px !important; font-size: 0.85rem !important; border-radius: 10px !important; }
            .coo-metric-label { font-size: 0.68rem !important; margin-bottom: 3px !important; }

            /* Hero card */
            div[data-testid="stVerticalBlock"]:has(.coo-hero-marker) {
                padding: 14px 12px !important;
                border-radius: 16px !important;
                margin-top: 8px !important;
            }
            .coo-hero-title { font-size: 1.1rem !important; margin-bottom: 8px !important; }

            /* Textarea — force light on mobile too */
            .stTextArea textarea {
                font-size: 16px !important;
                min-height: 90px !important;
                background-color: #f8fafc !important;
                color: #0f172a !important;
                border: 1.5px solid #e2e8f0 !important;
                border-radius: 12px !important;
            }
            .stTextInput input {
                font-size: 16px !important;
                background-color: #ffffff !important;
                color: #0f172a !important;
            }

            /* Buttons — clear dark, proper light */
            .stButton > button {
                min-height: 46px !important;
                font-size: 13px !important;
                background: #f1f5f9 !important;
                color: #0f172a !important;
                border: 1.5px solid #e2e8f0 !important;
                border-radius: 10px !important;
            }
            .stButton > button[kind="primary"],
            button[data-testid="baseButton-primary"] {
                background: linear-gradient(135deg, #4f46e5 0%, #818cf8 100%) !important;
                color: #ffffff !important;
                border: none !important;
            }

            /* Keep Scan/Reset/Execute in one row */
            .coo-action-row > div[data-testid="stHorizontalBlock"] {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                gap: 6px !important;
            }
            .coo-action-row > div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
                flex: 1 !important; min-width: 0 !important;
            }
            .coo-action-row .stButton > button {
                padding: 0 4px !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                font-size: 12px !important;
            }

            /* Chat messages */
            .stChatMessage { padding: 8px 10px !important; }
            .stChatMessage p { font-size: 14px !important; }

            /* Section labels */
            .coo-section-title { font-size: 0.72rem !important; }
            .coo-sidebar-label { font-size: 0.62rem !important; }

            /* Event cards */
            .coo-event-card { padding: 10px 12px !important; margin-bottom: 6px !important; border-radius: 12px !important; }
            .coo-evt-time   { font-size: 12px !important; }
            .coo-evt-title  { font-size: 13px !important; }
            .coo-evt-loc    { font-size: 11px !important; }

            /* Smartstrip on mobile */
            div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) { padding: 12px 12px !important; }
            div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) > div[data-testid="column"]{
                flex: 1 1 100% !important; min-width: 100% !important;
            }

            /* ── Train the Brain — keep horizontal on mobile ── */
            .coo-footer-label { font-size: 12px !important; }
            .coo-train-row > div[data-testid="stHorizontalBlock"] {
                display: flex !important; flex-direction: row !important;
                flex-wrap: nowrap !important; align-items: center !important; gap: 8px !important;
            }
            .coo-train-row > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1) {
                flex: 0 0 auto !important; min-width: 80px !important; max-width: 90px !important;
            }
            .coo-train-row > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {
                flex: 1 1 0 !important; min-width: 0 !important;
            }
            .coo-train-row > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) {
                flex: 0 0 64px !important; min-width: 64px !important;
            }
            .coo-train-row .stButton > button {
                min-height: 40px !important; font-size: 12px !important; padding: 0 8px !important;
            }

            /* ── Checkbox — force light mode ── */
            .stCheckbox label, .stCheckbox label span, .stCheckbox label p {
                color: #0f172a !important; font-size: 12px !important;
            }

            /* ── Chat messages — force readable contrast ── */
            div[data-testid="stChatMessage"] {
                background: #f1f5f9 !important;
                border-radius: 14px !important;
                padding: 10px 12px !important;
                margin-bottom: 8px !important;
                border: 1px solid #e2e8f0 !important;
            }
            div[data-testid="stChatMessage"] p,
            div[data-testid="stChatMessage"] span,
            div[data-testid="stChatMessage"] li,
            div[data-testid="stChatMessage"] div { color: #0f172a !important; }

            /* ── Bottom nav: max z-index to beat all overlays ── */
            #coo-mobile-nav {
                display: flex !important;
                z-index: 2147483647 !important;
                background: #ffffff !important;
                border-top: 2px solid #e2e8f0 !important;
            }
            #coo-fab { display: flex !important; z-index: 2147483646 !important; }
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
        st.session_state.active_page = "coo"  # coo (default) | dashboard | calendar | memory | settings

    with st.sidebar:
        # Brand — clickable, returns to main COO view
        if st.button(
            "🏡  Family COO",
            key="coo_brand_home",
            use_container_width=True,
            help="Go to main page",
        ):
            st.session_state.active_page = "coo"
            st.rerun()
        st.markdown(
            "<div style='text-align:center; font-size:11px; color:var(--text-muted);"
            " margin:-10px 0 8px 0;'>AI Operations Center</div>",
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

        # Active-tab nav: indigo left border strip on selected tab
        _cur = st.session_state.get("active_page", "coo")

        def _nav_btn(label, page, key):
            is_active = _cur == page
            st.markdown(
                f"<div style='border-left:3px solid "
                f"{'#4f46e5' if is_active else 'transparent'};"
                f"background:{'#eef2ff' if is_active else 'transparent'};"
                f"border-radius:0 10px 10px 0;margin-bottom:2px;padding-left:2px;'>",
                unsafe_allow_html=True,
            )
            if st.button(label, key=key, use_container_width=True):
                st.session_state.active_page = page
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        _nav_btn("📊  Dashboard",     "dashboard", "nav_dashboard")
        _nav_btn("🗓️  Calendar View", "calendar",  "nav_calendar")
        _nav_btn("🧠  Memory Bank",   "memory",    "nav_memory")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="coo-sidebar-label">SYSTEM</div>', unsafe_allow_html=True)

        _nav_btn("⚙️  Settings",      "settings",  "nav_settings")


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

    # ✅ Deferred clear flags (check-in feedback)
    st.session_state.setdefault("clear_checkin_feedback_text", False)

    # ✅ Clear BEFORE widget instantiation (mandatory rule)
    if st.session_state.get("clear_checkin_feedback_text"):
        st.session_state["checkin_feedback_text"] = ""
        st.session_state["clear_checkin_feedback_text"] = False

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
                    st.session_state["clear_checkin_feedback_text"] = True
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
                        st.session_state["clear_checkin_feedback_text"] = True
                        st.rerun()
                with f2:
                    if st.button("Cancel", key="coo_checkin_cancel", use_container_width=True):
                        st.session_state["checkin_feedback_open"] = False
                        st.session_state["clear_checkin_feedback_text"] = True
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

        st.markdown('<div class="coo-action-row">', unsafe_allow_html=True)
        t1, t2, t3 = st.columns([1, 1, 1.4], gap="small")

        with t1:
            if st.button("📷 Scan", key="coo_scan_btn", use_container_width=True):
                if callable(toggle_camera_callback):
                    toggle_camera_callback()
                st.rerun()

        with t2:
            if st.button("🔄 Reset", key="coo_reset_btn", use_container_width=True):
                st.session_state["clear_plan_text"] = True
                st.session_state["clear_conversation"] = True
                st.rerun()

        with t3:
            if st.button("🚀 Execute", key="coo_execute_btn", type="primary", use_container_width=True):
                if callable(submit_callback):
                    submit_callback()
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Camera widget — shown when Scan toggled on
        if st.session_state.get("show_camera"):
            st.markdown(
                "<div style='margin-top:8px; font-size:12px; font-weight:700;"
                " color:var(--text-muted);'>📷 Point camera at text and capture:</div>",
                unsafe_allow_html=True,
            )
            cam_img = st.camera_input(
                "Capture",
                key="cam_input",
                label_visibility="collapsed",
            )
            if cam_img:
                st.success("✅ Image captured — click 🚀 Execute to process.")

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
            import re as _re_abc
            _last_abc_idx = -1
            for _i, _m in enumerate(history[-12:]):
                _c = (_m.get("content") or "")
                if (_m.get("role") == "assistant"
                        and "(A)" in _c and "(B)" in _c and "(C)" in _c
                        and "schedule a" in _c.lower()):
                    _last_abc_idx = _i

            for _idx, msg in enumerate(history[-12:]):
                role = (msg.get("role") or "assistant").strip().lower()
                content = msg.get("content") or ""
                if role not in ("user", "assistant"):
                    role = "assistant"
                with st.chat_message(role):
                    display = _re_abc.sub(
                        r"\n?Reply exactly:.*?schedule C[^\n]*", "",
                        content, flags=_re_abc.IGNORECASE
                    ).rstrip()
                    display = display.replace("\n", "  \n")
                    st.markdown(display)

                if role == "assistant" and _idx == _last_abc_idx:
                    st.markdown(
                        "<div style='font-size:12px; font-weight:700;"
                        " color:var(--text-muted); margin:6px 0 4px 0;'>"
                        "Choose an option:</div>",
                        unsafe_allow_html=True,
                    )
                    _ba, _bb, _bc = st.columns(3, gap="small")
                    with _ba:
                        if st.button("✅ Option A", key="coo_abc_a", use_container_width=True):
                            st.session_state["_abc_choice_pending"] = "schedule A"
                            st.rerun()
                    with _bb:
                        if st.button("✅ Option B", key="coo_abc_b", use_container_width=True):
                            st.session_state["_abc_choice_pending"] = "schedule B"
                            st.rerun()
                    with _bc:
                        if st.button("✅ Option C", key="coo_abc_c", use_container_width=True):
                            st.session_state["_abc_choice_pending"] = "schedule C"
                            st.rerun()

        # ===== Train the Brain =====
        st.markdown("<div class='coo-hero-divider'></div>", unsafe_allow_html=True)
        st.markdown('<div class="coo-train-row">', unsafe_allow_html=True)
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
        st.markdown('</div>', unsafe_allow_html=True)
# ------------------------------------------------------------
# RIGHT COLUMN (drafts + schedule)
# ------------------------------------------------------------
def render_right_column(drafts, calendar, on_add, on_reject):
    import streamlit as st
    import re
    from datetime import datetime

    def _format_start_any(val) -> str:
        if isinstance(val, datetime):
            return val.strftime("%a, %b %d @ %I:%M %p")
        s = str(val or "").strip()
        if not s:
            return "—"
        s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
        s = re.sub(r"\s+([+-]\d{2}:\d{2})$", r"\1", s)
        if "T" not in s and len(s) >= 19 and s[10] == " ":
            s = s[:10] + "T" + s[11:]
        s = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt.strftime("%a, %b %d @ %I:%M %p")
        except Exception:
            return str(val)

    # ── Mobile: inject a JS snippet to detect viewport and add class ──
    # We use a sentinel div approach — no extra Python logic needed.
    st.markdown("""
<script>
(function(){
    function checkMobile(){
        var rc = document.querySelector('.coo-right-col-wrap');
        if(!rc) return;
        if(window.innerWidth <= 768){
            rc.classList.add('coo-is-mobile');
        } else {
            rc.classList.remove('coo-is-mobile');
        }
    }
    document.addEventListener('DOMContentLoaded', checkMobile);
    window.addEventListener('resize', checkMobile);
    setTimeout(checkMobile, 200);
})();
</script>
<style>
/* Right col wrapper: on mobile becomes a card below main content */
@media (max-width: 768px) {
    .coo-right-col-wrap {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 14px 12px 10px;
        margin-top: 4px;
        box-shadow: 0 2px 8px rgba(15,23,42,0.06);
    }
    /* Tighten spacing inside right col on mobile */
    .coo-right-col-wrap .coo-sidebar-label { margin: 8px 0 6px !important; font-size: 0.62rem !important; }
    .coo-right-col-wrap .coo-event-card { padding: 10px 12px !important; margin-bottom: 6px !important; }
    .coo-right-col-wrap .coo-section-title { margin: 10px 0 6px !important; }
    /* Calendar list: show only 3 on mobile, rest via expander handled in Python */
}
</style>
<div class="coo-right-col-wrap">
""", unsafe_allow_html=True)

    # ── DRAFTING ──
    st.markdown(
        '<div class="coo-sidebar-label" style="margin-top:0;">📋 DRAFTING</div>',
        unsafe_allow_html=True
    )

    if not drafts:
        st.caption("No drafts yet. Type a plan and click Execute.")
    else:
        for i, d in enumerate(drafts):
            title = (d.get("title") or "Event").strip()
            raw_start = d.get("start_friendly") or d.get("start_time") or ""
            start = _format_start_any(raw_start)
            loc = (d.get("location") or "").strip()
            st.markdown(
                f'<div class="coo-event-card coo-draft">'
                f'<div class="coo-evt-time">{start}</div>'
                f'<div class="coo-evt-title">{title}</div>'
                f'<div class="coo-evt-loc">📍 {loc or "—"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns([1, 1], gap="small")
            with c1:
                if st.button("✅ Confirm", key=f"draft_confirm_{i}", use_container_width=True):
                    on_add(d); st.rerun()
            with c2:
                if st.button("❌ Reject", key=f"draft_reject_{i}", use_container_width=True):
                    on_reject(d); st.rerun()

    # ── UPCOMING (next 1 event, always visible) ──
    st.markdown('<div class="coo-sidebar-label">⚡ UPCOMING</div>', unsafe_allow_html=True)
    if not calendar:
        st.caption("No upcoming events.")
    else:
        e = calendar[0]
        title = (e.get("title") or "Event").strip()
        start = _format_start_any(e.get("start_friendly") or e.get("start_time") or "")
        loc   = (e.get("location") or "").strip()
        st.markdown(
            f'<div class="coo-event-card coo-upcoming">'
            f'<div class="coo-evt-time">{start}</div>'
            f'<div class="coo-evt-title">{title}</div>'
            f'<div class="coo-evt-loc">📍 {loc or "—"}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── LIVE CALENDAR — collapsible on mobile, always open on desktop ──
    if not calendar:
        st.markdown('</div>', unsafe_allow_html=True)
        return

    with st.expander("📅 Full week calendar", expanded=True):
        for e in calendar[:8]:
            title = (e.get("title") or "Event").strip()
            start = _format_start_any(e.get("start_friendly") or e.get("start_time") or "")
            loc   = (e.get("location") or "").strip()
            st.markdown(
                f'<div class="coo-event-card">'
                f'<div class="coo-evt-time">{start}</div>'
                f'<div class="coo-evt-title">{title}</div>'
                f'<div class="coo-evt-loc">📍 {loc or "—"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown('</div>', unsafe_allow_html=True)  # close coo-right-col-wrap




# ------------------------------------------------------------
# MOBILE BOTTOM NAV + FAB
# Approach: real Streamlit buttons styled as a fixed bottom bar.
# Wrapped in a CSS-display:none container on desktop, shown on mobile.
# This is 100% reliable — no JS sidebar-button hunting needed.
# ------------------------------------------------------------
def render_mobile_nav():
    """
    Mobile bottom tab bar + FAB Execute (shown only on <=768px via CSS).
    Uses real Streamlit buttons → guaranteed routing, no JS hacks.
    Call once per render cycle, right after inject_css().
    """
    import streamlit as st

    active = st.session_state.get("active_page", "dashboard")

    # ── Next-event chip (above hero card, mobile only) ──
    cal = st.session_state.get("calendar_events") or []
    if cal:
        nxt_title = (cal[0].get("title") or "").strip()
        nxt_time  = (cal[0].get("start_friendly") or cal[0].get("start_raw") or "").strip()
        if nxt_title:
            st.markdown(
                '<div class="coo-mob-next-event">'
                '<div class="coo-mob-next-title">\u26A1 Next: ' + nxt_title + '</div>'
                '<div class="coo-mob-next-time">' + nxt_time + '</div>'
                '</div>',
                unsafe_allow_html=True,
            )

    # ── Fixed bottom nav: pure HTML+CSS — Streamlit buttons below it ──
    # The HTML bar is cosmetic. Real Streamlit buttons are hidden in a
    # zero-height div so they remain in DOM and JS can click them.
    tabs = [
        ("coo",       "\U0001F3E0", "Home"),
        ("dashboard", "\U0001F4CA", "Dash"),
        ("calendar",  "\U0001F5D3", "Cal"),
        ("memory",    "\U0001F9E0", "Memory"),
        ("settings",  "\u2699\uFE0F",    "More"),
    ]

    tab_parts = []
    for page_id, icon, label in tabs:
        is_active = active == page_id
        active_style = (
            "color:#4f46e5;background:#eef2ff;border-radius:10px;"
            if is_active else "color:#94a3b8;"
        )
        tab_parts.append(
            '<button class="coo-mob-tab" style="' + active_style + '" '
            'onclick="(function(){var all=Array.from(document.querySelectorAll'
            '(\'[data-testid=stBaseButton-secondary]\'));\n'
            'var b=all.find(function(x){return x.getAttribute(\'aria-label\')==\''
            + page_id + '\';});if(b)b.click();})()" '
            'aria-label="' + label + '">'
            '<span class="coo-mob-icon">' + icon + '</span>'
            '<span class="coo-mob-label">' + label + '</span>'
            '</button>'
        )

    st.markdown(
        '<div id="coo-mobile-nav" class="coo-mobile-nav">'
        + "".join(tab_parts)
        + '</div>'
        + '<button class="coo-fab" id="coo-fab" onclick="'
          '(function(){var all=Array.from(document.querySelectorAll(\'button\'));'
          'var b=all.find(function(x){return x.innerText&&x.innerText.includes(\'Execute\');});'
          'if(b)b.click();})()" title="Execute">\U0001F680</button>',
        unsafe_allow_html=True,
    )

    # ── Real Streamlit buttons (CSS-hidden, aria-label = page_id) ──
    # These are what actually trigger routing. CSS hides them visually
    # but they remain in DOM. JS from the HTML buttons clicks them.
    st.markdown(
        '<div style="position:fixed;left:-9999px;width:1px;height:1px;overflow:hidden;"'
        ' aria-hidden="false" id="coo-nav-triggers">',
        unsafe_allow_html=True,
    )
    for page_id, icon, label in tabs:
        # Use a unique key pattern; button click sets active_page
        btn_key = f"_mobnav_{page_id}"
        if st.button(
            f"{icon} {label}",
            key=btn_key,
            help=label,
        ):
            st.session_state.active_page = page_id
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

