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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

        /* ════════════════════════════════════════════════════════
           DESIGN TOKENS
           ════════════════════════════════════════════════════════ */
        :root {
            color-scheme: light !important;
            --indigo-50:#eef2ff;  --indigo-100:#e0e7ff;
            --indigo-500:#6366f1; --indigo-600:#4f46e5; --indigo-700:#4338ca;
            --slate-50:#f8fafc;  --slate-100:#f1f5f9; --slate-200:#e2e8f0;
            --slate-400:#94a3b8; --slate-500:#64748b; --slate-700:#334155;
            --slate-800:#1e293b; --slate-900:#0f172a;
            --green:#10b981; --amber:#f59e0b; --red:#ef4444;
            --bg:#f4f6f9; --surface:#ffffff;
            --text:#0f172a; --muted:#64748b; --border:#e2e8f0;
            --sh-xs:0 1px 3px rgba(15,23,42,.07);
            --sh-sm:0 2px 8px rgba(15,23,42,.09),0 1px 3px rgba(15,23,42,.05);
            --sh-md:0 8px 24px rgba(15,23,42,.10),0 2px 8px rgba(15,23,42,.05);
            --sh-lg:0 16px 40px rgba(15,23,42,.12),0 4px 12px rgba(15,23,42,.06);
            --r-xs:6px; --r-sm:10px; --r-md:14px; --r-lg:20px; --r-xl:24px;
        }
        html,body { color-scheme:light !important; }
        * { font-family:Inter,system-ui,-apple-system,sans-serif; box-sizing:border-box; }

        /* ── App shell ── */
        .stApp { background:var(--bg) !important; color:var(--text) !important; }
        #MainMenu,footer,header { visibility:hidden; }
        section.main>div { padding-top:0 !important; }
        .block-container { max-width:1400px; padding:24px 40px 60px; }
        @media(max-width:1200px){ .block-container{ padding:20px 28px 60px; } }
        @media(max-width:900px) { .block-container{ padding:14px 18px 60px; } }
        /* Mobile: 90px bottom padding so content clears the fixed nav bar */
        @media(max-width:768px) { .block-container{ padding:10px 12px 90px !important; } }
        @media(max-width:640px) { .block-container{ padding:8px 10px 90px !important; } }

        /* ════════════════════════════════════════════════════════
           RESPONSIVE COLUMN STACKING
           Streamlit st.columns() has no native breakpoints.
           At ≤768px: every stHorizontalBlock becomes a vertical stack
           EXCEPT the ones we explicitly keep horizontal (action row,
           train row, ABC buttons — those have their own overrides below).
           ════════════════════════════════════════════════════════ */
        @media(max-width:768px){
            /* Stack the main left + right panel columns */
            section.main div[data-testid="stHorizontalBlock"]:not(.coo-action-row div[data-testid="stHorizontalBlock"]):not(.coo-train-row div[data-testid="stHorizontalBlock"]) {
                flex-direction:column !important;
            }
            section.main div[data-testid="stHorizontalBlock"]:not(.coo-action-row div[data-testid="stHorizontalBlock"]):not(.coo-train-row div[data-testid="stHorizontalBlock"])>div[data-testid="column"] {
                width:100% !important;
                flex:1 1 100% !important;
                min-width:0 !important;
            }
        }

        /* ════════════════════════════════════════════════════════
           LIGHT-MODE ENFORCEMENT (beats system dark-mode)
           ════════════════════════════════════════════════════════ */
        .stTextArea textarea {
            background:#ffffff !important; color:#0f172a !important;
            border:1.5px solid #e2e8f0 !important; border-radius:var(--r-md) !important;
            font-size:15px !important; line-height:1.6 !important;
            transition:border-color .15s,box-shadow .15s !important;
            color-scheme:light !important;
        }
        .stTextArea textarea:focus {
            border-color:#6366f1 !important;
            box-shadow:0 0 0 3px rgba(99,102,241,.14) !important; outline:none !important;
        }
        .stTextArea textarea::placeholder { color:#94a3b8 !important; }
        .stTextArea>div,.stTextArea>div>div { background:transparent !important; border:none !important; }

        .stTextInput input {
            background:#ffffff !important; color:#0f172a !important;
            border:1.5px solid #e2e8f0 !important; border-radius:var(--r-sm) !important;
            font-size:14px !important; transition:border-color .15s,box-shadow .15s !important;
            color-scheme:light !important;
        }
        .stTextInput input:focus {
            border-color:#6366f1 !important;
            box-shadow:0 0 0 3px rgba(99,102,241,.14) !important;
        }
        .stTextInput input::placeholder { color:#94a3b8 !important; }
        .stTextInput>div>div { background:transparent !important; }

        .stCheckbox label,.stCheckbox label span,.stCheckbox label p {
            color:#0f172a !important; font-size:13px !important;
        }
        div[data-testid="stChatMessage"] {
            background:#f8fafc !important; border:1px solid #f0f4f8 !important;
            border-radius:var(--r-md) !important; padding:12px 16px !important;
            margin-bottom:10px !important; color-scheme:light !important;
        }
        div[data-testid="stChatMessage"] p,
        div[data-testid="stChatMessage"] span,
        div[data-testid="stChatMessage"] li,
        div[data-testid="stChatMessage"] div { color:#0f172a !important; }
        div[data-testid="stChatMessage"] code { background:#f1f5f9 !important; color:#4f46e5 !important; }

        .stAlert { border-radius:var(--r-sm) !important; }
        /* Spinner — larger, centered, branded */
        div[data-testid="stSpinner"] {
            display:flex; align-items:center; justify-content:center;
            padding:18px 0 !important;
        }
        div[data-testid="stSpinner"] > div {
            border-top-color:#4f46e5 !important;
            width:32px !important; height:32px !important;
            border-width:3px !important;
        }
        div[data-testid="stSpinner"] p {
            color:#4f46e5 !important; font-weight:700 !important;
            font-size:15px !important; margin-left:12px !important;
        }
        /* Status widget */
        div[data-testid="stStatus"] {
            border-radius: var(--r-md) !important;
            border: 1px solid #c7d2fe !important;
            background: #eef2ff !important;
        }

        .streamlit-expanderHeader {
            background:#f8fafc !important; color:#0f172a !important;
            border-radius:var(--r-sm) !important; font-weight:700 !important;
        }
        .streamlit-expanderContent { background:#ffffff !important; }

        /* ════════════════════════════════════════════════════════
           GLOBAL BUTTONS
           ════════════════════════════════════════════════════════ */
        .stButton>button {
            background:#ffffff !important; color:#0f172a !important;
            border:1.5px solid #e2e8f0 !important; border-radius:var(--r-sm) !important;
            font-weight:700 !important; font-size:14px !important;
            height:42px !important; letter-spacing:-0.01em !important;
            transition:background .14s,border-color .14s,box-shadow .14s,transform .08s !important;
            box-shadow:var(--sh-xs) !important;
        }
        .stButton>button:hover {
            background:#f8fafc !important; border-color:#c7d2fe !important;
            color:#4338ca !important; box-shadow:var(--sh-sm) !important;
        }
        .stButton>button:active { transform:scale(.97) !important; }

        /* Primary */
        button[data-testid="baseButton-primary"],
        .stButton>button[kind="primary"] {
            background:linear-gradient(135deg,#4f46e5 0%,#6366f1 100%) !important;
            color:#ffffff !important; border:none !important;
            box-shadow:0 2px 10px rgba(79,70,229,.32) !important;
        }
        button[data-testid="baseButton-primary"]:hover,
        .stButton>button[kind="primary"]:hover {
            background:linear-gradient(135deg,#4338ca 0%,#4f46e5 100%) !important;
            box-shadow:0 4px 16px rgba(79,70,229,.42) !important;
        }

        /* ════════════════════════════════════════════════════════
           SIDEBAR
           ════════════════════════════════════════════════════════ */
        section[data-testid="stSidebar"] {
            background:#ffffff !important;
            border-right:1px solid #eef2f7 !important;
            box-shadow:3px 0 16px rgba(15,23,42,.06) !important;
        }
        section[data-testid="stSidebar"]>div {
            width:260px !important; padding:20px 14px 32px !important;
        }

        /* Brand block (static HTML) */
        .coo-brand-header {
            display:flex; align-items:center; gap:11px;
            padding:13px 14px; margin-bottom:14px;
            border-radius:var(--r-md);
            background:linear-gradient(135deg,#4f46e5 0%,#6366f1 100%);
            box-shadow:0 4px 16px rgba(79,70,229,.28); cursor:default;
        }
        .coo-brand-icon { font-size:22px; line-height:1; }
        .coo-brand-name {
            font-size:15px; font-weight:900; color:#fff;
            letter-spacing:-0.02em; line-height:1.2;
        }
        .coo-brand-sub {
            font-size:10px; font-weight:700;
            color:rgba(255,255,255,.72); text-transform:uppercase;
            letter-spacing:.06em; margin-top:1px;
        }

        /* All sidebar buttons: nav-item look */
        section[data-testid="stSidebar"] .stButton>button {
            text-align:left !important; justify-content:flex-start !important;
            padding:0 12px !important; height:42px !important;
            font-size:14px !important; font-weight:600 !important;
            border-radius:var(--r-sm) !important;
            border:1.5px solid transparent !important;
            background:transparent !important; color:#475569 !important;
            box-shadow:none !important; transition:all .14s !important;
        }
        section[data-testid="stSidebar"] .stButton>button:hover {
            background:#f8fafc !important; border-color:#e2e8f0 !important;
            color:#0f172a !important; box-shadow:var(--sh-xs) !important;
        }
        /* Active nav item via type=primary */
        section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
            background:#eef2ff !important;
            border:1.5px solid #c7d2fe !important;
            border-left:4px solid #4f46e5 !important;
            border-radius:0 var(--r-sm) var(--r-sm) 0 !important;
            color:#3730a3 !important; font-weight:800 !important;
            box-shadow:var(--sh-xs) !important;
        }
        section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:hover {
            background:#e0e7ff !important; border-color:#a5b4fc !important;
            box-shadow:var(--sh-sm) !important;
        }
        /* Logout (last button) */
        section[data-testid="stSidebar"] .stButton:last-of-type>button {
            color:#dc2626 !important; background:transparent !important;
            border-color:transparent !important; margin-top:4px;
        }
        section[data-testid="stSidebar"] .stButton:last-of-type>button:hover {
            background:#fef2f2 !important; border-color:#fecaca !important;
        }

        /* Sidebar elements */
        .coo-sidebar-label {
            font-size:.67rem; font-weight:800; color:#94a3b8;
            text-transform:uppercase; letter-spacing:.08em;
            margin:16px 2px 6px; display:block;
        }
        .coo-sidebar-divider { height:1px; background:#f1f5f9; margin:10px 2px; }
        .coo-user-card {
            display:flex; align-items:center; gap:10px;
            padding:11px 13px; border-radius:var(--r-md);
            background:var(--slate-50); border:1px solid var(--slate-200);
            margin-bottom:14px; box-shadow:var(--sh-xs);
        }
        .coo-avatar {
            width:38px; height:38px; border-radius:999px; flex:0 0 auto;
            display:flex; align-items:center; justify-content:center;
            background:var(--indigo-100); color:#3730a3;
            font-weight:900; font-size:13px;
        }
        .coo-user-name { font-size:13px; font-weight:800; color:#0f172a; }
        .coo-user-meta { font-size:11px; font-weight:600; color:#64748b; margin-top:1px; }
        .coo-status-row {
            display:flex; align-items:center; justify-content:space-between;
            padding:9px 12px; border-radius:var(--r-md);
            border:1px solid var(--border); background:#ffffff;
            margin-bottom:4px; box-shadow:var(--sh-xs);
        }
        .coo-status-badge {
            display:inline-flex; align-items:center; gap:5px;
            padding:3px 9px; border-radius:999px; font-size:11px; font-weight:800;
            background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0;
        }
        .coo-status-badge.offline { background:#fef2f2; color:#991b1b; border-color:#fecaca; }

        /* ════════════════════════════════════════════════════════
           HEADER + GREETING
           ════════════════════════════════════════════════════════ */
        .coo-header-row {
            display:flex; justify-content:space-between;
            align-items:flex-start; margin-bottom:8px; gap:16px;
        }
        .coo-greeting h2 {
            font-size:1.65rem; font-weight:900; letter-spacing:-.025em;
            margin:0; color:#0f172a !important; line-height:1.2;
        }
        .coo-greeting p { color:#64748b !important; margin:5px 0 0; font-size:15px; font-weight:500; }
        @media(max-width:640px){
            .coo-greeting h2 { font-size:1.2rem !important; }
            .coo-greeting p  { font-size:.82rem !important; margin-top:2px !important; }
        }
        .coo-header-date {
            background:#ffffff; padding:8px 18px; border-radius:999px;
            font-size:.85rem; font-weight:700; color:#475569;
            box-shadow:var(--sh-sm); border:1px solid var(--border);
            white-space:nowrap; flex-shrink:0;
        }

        /* ════════════════════════════════════════════════════════
           KPI GRID
           ════════════════════════════════════════════════════════ */
        .coo-metrics {
            display:grid; grid-template-columns:repeat(4,1fr);
            gap:16px; margin:16px 0;
        }
        @media(max-width:1100px){ .coo-metrics{ grid-template-columns:repeat(2,1fr); } }
        @media(max-width:640px) {
            .coo-metrics{ grid-template-columns:repeat(2,1fr); gap:8px; margin:8px 0 10px; }
        }
        .coo-metric-card {
            background:#ffffff; padding:18px 20px;
            border-radius:var(--r-lg); box-shadow:var(--sh-sm);
            border:1px solid #eef2f7;
            display:flex; justify-content:space-between; align-items:center;
            transition:box-shadow .18s,transform .12s;
        }
        .coo-metric-card:hover { box-shadow:var(--sh-md); transform:translateY(-2px); }
        .coo-metric-label {
            font-size:.72rem; font-weight:800; color:#94a3b8 !important;
            text-transform:uppercase; letter-spacing:.06em;
            margin-bottom:5px; display:block;
        }
        .coo-metric-value { font-size:2rem; font-weight:900; color:#0f172a !important; line-height:1; }
        .coo-metric-icon {
            width:44px; height:44px; border-radius:12px; flex:0 0 auto;
            display:flex; align-items:center; justify-content:center;
            background:var(--indigo-100); font-size:1.05rem;
        }
        .coo-reliability { margin-top:5px; }
        .coo-badge {
            display:inline-flex; padding:3px 8px; border-radius:6px;
            font-weight:800; font-size:11px;
            background:#dcfce7; color:#166534;
        }
        .coo-badge.med { background:#fef9c3; color:#854d0e; }
        .coo-badge.low { background:#fee2e2; color:#991b1b; }
        @media(max-width:640px){
            .coo-metric-card  { padding:12px 10px !important; border-radius:12px !important; }
            .coo-metric-value { font-size:1.5rem !important; }
            .coo-metric-icon  { width:34px !important; height:34px !important; font-size:.85rem !important; border-radius:9px !important; }
            .coo-metric-label { font-size:.66rem !important; }
        }

        /* ════════════════════════════════════════════════════════
           HERO CARD  (Plan your day)
           ════════════════════════════════════════════════════════ */
        div[data-testid="stVerticalBlock"]:has(.coo-hero-marker) {
            background:#ffffff !important;
            border:1px solid #e8edf4; border-radius:var(--r-xl);
            box-shadow:var(--sh-md); padding:24px; margin-top:12px;
        }
        @media(max-width:640px){
            div[data-testid="stVerticalBlock"]:has(.coo-hero-marker) {
                padding:14px 12px !important; border-radius:16px !important;
                margin-top:6px !important;
            }
        }
        .coo-hero-title {
            font-size:1.15rem; font-weight:900; color:#0f172a !important;
            margin:0 0 14px; display:flex; align-items:center; gap:8px;
        }
        .coo-hero-divider { height:1px; background:#eef2f7; margin:20px 0 16px; }

        /* ════════════════════════════════════════════════════════
           ACTION REQUIRED STRIP
           ════════════════════════════════════════════════════════ */
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) {
            background:linear-gradient(135deg,#eff6ff 0%,#f0f9ff 100%) !important;
            border-left:4px solid #3b82f6; border-radius:var(--r-md);
            padding:14px 16px; box-shadow:var(--sh-sm); margin:0 0 14px;
            display:flex !important; flex-wrap:wrap !important;
            align-items:center !important; justify-content:space-between !important;
            gap:10px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left)>div[data-testid="column"]:nth-child(1) {
            flex:1 1 280px !important; min-width:200px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left)>div[data-testid="column"]:nth-child(2),
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left)>div[data-testid="column"]:nth-child(3) {
            flex:0 0 96px !important; min-width:86px !important;
        }
        .coo-smartstrip-left { display:flex; align-items:center; gap:12px; min-width:0; }
        .coo-smartstrip-icon { font-size:20px; line-height:1; flex:0 0 auto; }
        .coo-smartstrip-text { min-width:0; }
        .coo-smartstrip-text strong {
            display:block; font-weight:900; color:#1e40af !important;
            font-size:.95rem; line-height:1.3; word-break:break-word;
        }
        .coo-smartstrip-text span {
            display:block; color:#3b82f6 !important;
            font-size:.9rem; font-weight:600; margin-top:2px;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) button[data-testid="baseButton-primary"] {
            background:linear-gradient(135deg,#10b981 0%,#059669 100%) !important;
            border:none !important; color:#fff !important;
            box-shadow:0 2px 8px rgba(16,185,129,.35) !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) .stButton>button {
            height:38px !important; width:100% !important;
            min-width:80px !important; border-radius:var(--r-sm) !important;
            font-weight:800 !important; white-space:nowrap !important;
        }
        @media(max-width:640px){
            div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left)>div[data-testid="column"] {
                flex:1 1 100% !important; min-width:100% !important;
            }
        }
        .coo-checkin-feedback {
            background:#f8fafc; border:1px solid #e2e8f0;
            border-radius:var(--r-md); padding:14px; margin-top:10px;
            box-shadow:var(--sh-xs);
        }
        .coo-checkin-feedback-title { font-weight:800; color:#0f172a !important; font-size:13px; margin-bottom:8px; }

        /* ════════════════════════════════════════════════════════
           ACTION ROW  (Scan | Reset | Execute)
           ════════════════════════════════════════════════════════ */
        .coo-action-row { margin-top:10px; }
        .coo-action-row>div[data-testid="stHorizontalBlock"] {
            display:flex !important; flex-direction:row !important;
            flex-wrap:nowrap !important; gap:8px !important;
        }
        .coo-action-row>div[data-testid="stHorizontalBlock"]>div[data-testid="column"] {
            flex:1 !important; min-width:0 !important;
        }
        .coo-action-row .stButton>button { white-space:nowrap !important; overflow:hidden !important; }
        @media(max-width:480px){
            .coo-action-row .stButton>button { font-size:12px !important; padding:0 4px !important; }
        }

        /* Train the Brain */
        .coo-footer-label { font-weight:800; color:#334155 !important; font-size:13px; }
        .coo-train-row>div[data-testid="stHorizontalBlock"] {
            display:flex !important; flex-direction:row !important;
            flex-wrap:nowrap !important; align-items:center !important; gap:8px !important;
        }
        .coo-train-row>div[data-testid="stHorizontalBlock"]>div[data-testid="column"]:nth-child(1) {
            flex:0 0 auto !important; min-width:80px !important; max-width:95px !important;
        }
        .coo-train-row>div[data-testid="stHorizontalBlock"]>div[data-testid="column"]:nth-child(2) {
            flex:1 1 0 !important; min-width:0 !important;
        }
        .coo-train-row>div[data-testid="stHorizontalBlock"]>div[data-testid="column"]:nth-child(3) {
            flex:0 0 60px !important; min-width:60px !important;
        }
        .coo-train-row .stButton>button { height:38px !important; font-size:13px !important; }
        @media(max-width:640px){
            .coo-footer-label { font-size:11px !important; }
            .coo-train-row .stButton>button { min-height:38px !important; font-size:12px !important; }
        }

        /* ════════════════════════════════════════════════════════
           RIGHT COLUMN — Calendar cards
           ════════════════════════════════════════════════════════ */
        .coo-section-title {
            display:flex; align-items:center; gap:8px; font-weight:800;
            color:#64748b !important; text-transform:uppercase;
            letter-spacing:.06em; font-size:.76rem; margin:14px 0 10px;
        }
        .coo-event-card {
            background:#ffffff !important; border-radius:var(--r-md);
            border:1px solid #eef2f7; box-shadow:var(--sh-sm);
            padding:13px 15px; margin-bottom:10px;
            transition:box-shadow .16s,transform .1s;
        }
        .coo-event-card:hover { box-shadow:var(--sh-md); transform:translateY(-2px); }
        .coo-event-card.coo-draft {
            background:#fafafa !important; border:2px dashed #c7d2fe;
            border-left:5px solid #4f46e5;
        }
        .coo-event-card.coo-upcoming { border-left:5px solid #10b981; }
        .coo-evt-time  { font-size:12px; font-weight:700; color:#64748b !important; margin-bottom:3px; }
        .coo-evt-title { font-size:14px; font-weight:900; color:#0f172a !important; line-height:1.3; }
        .coo-evt-loc   { font-size:12px; font-weight:500; color:#94a3b8 !important; margin-top:3px; }
        .coo-right-col-wrap { }
        @media(max-width:768px){
            .coo-right-col-wrap {
                background:#ffffff; border:1px solid #e2e8f0;
                border-radius:var(--r-lg); padding:14px 12px 10px;
                margin-top:6px; box-shadow:var(--sh-sm);
            }
            .coo-event-card { padding:10px 12px !important; margin-bottom:6px !important; }
            .coo-evt-time  { font-size:11px !important; }
            .coo-evt-title { font-size:13px !important; }
            .coo-evt-loc   { font-size:11px !important; }
            .coo-section-title { font-size:.7rem !important; margin:10px 0 6px !important; }
        }

        /* ════════════════════════════════════════════════════════
           MOBILE LAYOUT OVERRIDES  (≤768px)
           ════════════════════════════════════════════════════════ */
        @media(max-width:768px){
            /* === KEEP SIDEBAR ACCESSIBLE via hamburger === */
            /* Do NOT push sidebar off-screen.
               Streamlit natively collapses sidebar on narrow viewports.
               The collapsedControl hamburger stays visible so users can open it. */
            section.main { margin-left:0 !important; }

            /* Chat messages */
            div[data-testid="stChatMessage"] { padding:10px 12px !important; }
            div[data-testid="stChatMessage"] p { font-size:13px !important; color:#0f172a !important; }

            /* Textarea */
            .stTextArea textarea { font-size:16px !important; min-height:90px !important; background:#f8fafc !important; }
            .stTextInput input   { font-size:16px !important; }

            /* Buttons */
            .stButton>button { min-height:44px !important; font-size:13px !important; }

            /* Action row */
            .coo-action-row>div[data-testid="stHorizontalBlock"] { gap:6px !important; }
            .coo-action-row .stButton>button { font-size:12px !important; padding:0 4px !important; }

            /* Smartstrip */
            div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left) { padding:12px !important; }
            div[data-testid="stHorizontalBlock"]:has(.coo-smartstrip-left)>div[data-testid="column"] {
                flex:1 1 100% !important; min-width:100% !important;
            }
        }

        /* mobile nav CSS injected inline by render_mobile_nav() */

        /* ════════════════════════════════════════════════════════
           CAMERA WIDGET  — make it large, usable, and clear
           ════════════════════════════════════════════════════════ */
        /* Outer wrapper Streamlit adds */
        div[data-testid="stCameraInput"] {
            width: 100% !important;
        }
        /* The video/canvas frame itself */
        div[data-testid="stCameraInput"] video,
        div[data-testid="stCameraInput"] canvas,
        div[data-testid="stCameraInput"] img {
            width:  100% !important;
            max-width: 100% !important;
            height: auto !important;
            min-height: 280px !important;
            border-radius: var(--r-lg) !important;
            border: 2px solid #c7d2fe !important;
            background: #0f172a !important;
            display: block !important;
        }
        /* The inner container Streamlit wraps the video in */
        div[data-testid="stCameraInput"] > div:first-child {
            width: 100% !important;
            border-radius: var(--r-lg) !important;
            overflow: hidden !important;
        }
        /* Capture / Retake button row */
        div[data-testid="stCameraInputButton"] {
            width: 100% !important;
            margin-top: 10px !important;
        }
        div[data-testid="stCameraInputButton"] button {
            width: 100% !important;
            height: 48px !important;
            font-size: 15px !important;
            font-weight: 800 !important;
            border-radius: var(--r-md) !important;
            background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
            color: #ffffff !important;
            border: none !important;
            box-shadow: 0 4px 14px rgba(79,70,229,0.35) !important;
            cursor: pointer !important;
        }
        div[data-testid="stCameraInputButton"] button:hover {
            background: linear-gradient(135deg, #4338ca 0%, #4f46e5 100%) !important;
        }
        /* Mobile: camera takes full width */
        @media(max-width:768px) {
            div[data-testid="stCameraInput"] video,
            div[data-testid="stCameraInput"] canvas,
            div[data-testid="stCameraInput"] img {
                min-height: 220px !important;
            }
        }


        /* ════════════════════════════════════════════════════════
           FAB — Execute floating button (mobile only)
           ════════════════════════════════════════════════════════ */
        .coo-fab {
            display:none;
            position:fixed; bottom:72px; right:16px;
            width:52px; height:52px; border-radius:50%;
            background:linear-gradient(135deg,#4f46e5 0%,#6366f1 100%);
            color:#fff; font-size:20px; border:none;
            box-shadow:0 4px 18px rgba(79,70,229,.46);
            align-items:center; justify-content:center;
            cursor:pointer; z-index:2147483646;
            -webkit-tap-highlight-color:transparent;
            transition:transform .12s;
        }
        .coo-fab:active { transform:scale(.86); }
        @media(max-width:768px){ .coo-fab{ display:flex !important; } }
        </style>
        <script>
        /* One-shot TZ detection. Guard: only reload if ?tz= not in URL.
           After reload ?tz= IS in URL so no second reload. Loop-safe.
           NOTE: Does not use browser storage of any kind - avoids the bug
           where storage flags persist through Streamlit Cloud server
           restarts and block TZ detection for returning users. */
        (function() {
            try {
                var u = new URL(window.location.href);
                if (u.searchParams.get('tz')) return;
                var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
                if (!tz) return;
                u.searchParams.set('tz', tz);
                window.location.replace(u.toString());
            } catch(e) {}
        })();
        </script>""",
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

    email        = (st.session_state.get("user_email") or "").strip()
    display_name = (st.session_state.get("user_name") or "Tushar Khandare").strip()
    role_line    = st.session_state.get("user_role_line") or "Admin • Tampa, FL"
    initials     = _initials_from_email_or_name(email=email, fallback_name=display_name)
    is_online    = "online" in (status or "").lower()

    st.session_state.setdefault("active_page", "coo")
    _cur = st.session_state.active_page

    # Nav helper — type="primary" when active → CSS gives it indigo highlight
    def _nb(label: str, page: str, key: str):
        if st.button(
            label, key=key,
            type="primary" if _cur == page else "secondary",
            use_container_width=True,
        ):
            st.session_state.active_page = page
            st.rerun()

    with st.sidebar:
        # Brand (pure HTML — not a button so it can't be accidentally triggered)
        st.markdown(
            '<div class="coo-brand-header">'
            '<span class="coo-brand-icon">🏡</span>'
            '<div>'
            '<div class="coo-brand-name">Family COO</div>'
            '<div class="coo-brand-sub">AI Operations Center</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

        # User card
        st.markdown(
            f'<div class="coo-user-card">'
            f'<div class="coo-avatar">{initials}</div>'
            f'<div><div class="coo-user-name">{display_name}</div>'
            f'<div class="coo-user-meta">{role_line}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Status
        dot  = "#10b981" if is_online else "#ef4444"
        blbl = "Online"   if is_online else "Offline"
        bcls = "coo-status-badge" + ("" if is_online else " offline")
        st.markdown(
            f'<div class="coo-status-row">'
            f'<span style="font-weight:700;font-size:13px;color:#0f172a;">🗓️ Calendar</span>'
            f'<div class="{bcls}">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{dot};display:inline-block;margin-right:3px;"></span>'
            f'{blbl}</div></div>'
            f'<div style="font-size:11px;color:#94a3b8;padding:2px 2px 10px;">{count} events loaded</div>',
            unsafe_allow_html=True,
        )

        # Navigation
        st.markdown('<span class="coo-sidebar-label">NAVIGATE</span>', unsafe_allow_html=True)
        _nb("🏠  Home",        "coo",       "nav_coo")
        _nb("📊  Dashboard",   "dashboard", "nav_dashboard")
        _nb("🗓️  Calendar",    "calendar",  "nav_calendar")
        _nb("🧠  Memory Bank", "memory",    "nav_memory")

        st.markdown('<div class="coo-sidebar-divider"></div>', unsafe_allow_html=True)
        st.markdown('<span class="coo-sidebar-label">SYSTEM</span>', unsafe_allow_html=True)
        _nb("⚙️  Settings",    "settings",  "nav_settings")
        st.markdown('<div class="coo-sidebar-divider"></div>', unsafe_allow_html=True)

        if st.button("🚪  Log Out", key="nav_logout", use_container_width=True):
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
                    with st.spinner("✅ Marking complete…"):
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
            _exec_clicked = st.button("🚀 Execute", key="coo_execute_btn", type="primary", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Loading spinner — shown while AI processes ──
        if _exec_clicked:
            has_image = bool(st.session_state.get("cam_input"))
            has_text  = bool((st.session_state.get("plan_text") or "").strip())
            if has_image and has_text:
                _msg = "🔍 Reading image and processing your plan…"
            elif has_image:
                _msg = "🔍 Scanning image with AI…"
            elif has_text:
                _msg = "🤔 AI is thinking…"
            else:
                _msg = "⚙️ Processing…"
            with st.spinner(_msg):
                if callable(submit_callback):
                    submit_callback()
            st.rerun()

        # Camera widget — shown when Scan toggled on
        if st.session_state.get("show_camera"):
            st.markdown(
                """
                <div style='
                    background:#eff6ff;
                    border:1.5px solid #bfdbfe;
                    border-left:4px solid #3b82f6;
                    border-radius:12px;
                    padding:12px 14px;
                    margin:12px 0 8px;
                '>
                  <div style='font-weight:900;color:#1e40af;font-size:14px;margin-bottom:4px;'>
                    📷 Camera Scan
                  </div>
                  <div style='font-size:13px;color:#3b82f6;font-weight:600;line-height:1.5;'>
                    1 · Allow camera access if prompted<br>
                    2 · Point at the text you want to scan<br>
                    3 · Click <b>Take photo</b> below the viewfinder<br>
                    4 · Hit <b>🚀 Execute</b> to process the image
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            cam_img = st.camera_input(
                "📷 Point at text then click Take photo",
                key="cam_input",
            )

            if cam_img:
                st.success("✅ Photo captured! Click **🚀 Execute** to process it.")
                # Show thumbnail so user can confirm what was captured
                st.image(cam_img, caption="Captured — ready to process", use_container_width=True)

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


# ═══════════════════════════════════════════════════════════════════
# MOBILE NAV  —  pure <a> anchor tag approach (final)
#
# WHY PREVIOUS APPROACHES FAILED:
#   - st.components.v1.html iframe: window.parent.location.replace()
#     throws a silent SecurityError on Streamlit Cloud because the
#     iframe is served from a different subdomain (CORS block).
#   - iframe CSS title selector: Streamlit changes iframe title attrs
#     between versions (stHtml, components.v1.html, st_html) — selector
#     never matched, nav rendered inline at top of page.
#   - st.button/radio JS .click(): React synthetic events on
#     visually-hidden elements don't propagate to Streamlit's root
#     event container on mobile.
#   - history.replaceState: Streamlit reads query_params from the
#     WebSocket session URL, not the live browser URL bar.
#
# WHY <a> TAGS WORK:
#   Standard browser anchor navigation (<a href="?page=X" target="_self">)
#   has zero CORS restrictions, works on every browser/OS, and requires
#   no JavaScript whatsoever. It causes a full page load which Streamlit
#   reconnects normally. ?sid=, ?tz= are preserved in the URL.
#   app.py reads ?page= on reconnect and sets active_page.
# ═══════════════════════════════════════════════════════════════════


def render_nav_triggers():
    """No-op stub. Kept so app.py import doesn't break.
    Navigation uses pure <a> anchor tags in render_mobile_nav()."""
    pass


def render_mobile_nav():
    """
    Mobile bottom nav bar using pure HTML anchor tags.
    No JavaScript, no iframes, no CORS issues.
    Each tab is an <a href="?page=X&sid=Y&tz=Z" target="_self"> link.
    Visible only on mobile (<=768px) via CSS media query.
    """
    import streamlit as st
    import urllib.parse

    active = st.session_state.get("active_page", "coo")

    TABS = [
        ("coo",       "🏠", "Home"),
        ("dashboard", "📊", "Dash"),
        ("calendar",  "🗓️", "Cal"),
        ("memory",    "🧠", "Brain"),
        ("settings",  "⚙️",  "More"),
    ]

    # Carry all existing query params (sid, tz, etc.) forward so auth
    # and timezone survive the navigation reload.
    try:
        base_params = dict(st.query_params)
    except Exception:
        base_params = {}
    # Remove stale page param — we'll set it fresh per tab
    base_params.pop("page", None)

    tab_html = []
    for page_id, icon, label in TABS:
        active_cls = "active" if active == page_id else ""
        params = {**base_params, "page": page_id}
        href = "?" + urllib.parse.urlencode(params, doseq=True)
        tab_html.append(
            f'<a href="{href}" target="_self" class="coo-mob-tab {active_cls}">'
            f'<span class="coo-mob-icon">{icon}</span>'
            f'<span class="coo-mob-label">{label}</span>'
            f'</a>'
        )

    st.markdown(
        f"""
        <style>
        /* ── Mobile bottom nav container ── */
        .coo-mobile-nav-container {{
            display: none;                  /* hidden on desktop */
            position: fixed;
            bottom: 0; left: 0; right: 0;
            height: 62px;
            background: rgba(255,255,255,0.97);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-top: 1px solid #e2e8f0;
            box-shadow: 0 -4px 20px rgba(15,23,42,0.08);
            z-index: 2147483647;
            justify-content: space-around;
            align-items: stretch;
        }}
        @media (max-width: 768px) {{
            .coo-mobile-nav-container {{
                display: flex !important;
            }}
            .block-container {{
                padding-bottom: 90px !important;
            }}
        }}

        /* ── Tab link styles ── */
        a.coo-mob-tab {{
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            flex: 1; text-decoration: none;
            gap: 3px; padding: 8px 4px 6px;
            color: #94a3b8;
            font-family: Inter, system-ui, sans-serif;
            -webkit-tap-highlight-color: transparent;
            transition: background 0.15s, color 0.15s;
            border-radius: 10px; margin: 3px;
        }}
        a.coo-mob-tab.active {{
            color: #4f46e5;
            background: #eef2ff;
        }}
        a.coo-mob-tab:active {{ transform: scale(0.92); }}
        a.coo-mob-tab .coo-mob-icon  {{ font-size: 20px; line-height: 1; }}
        a.coo-mob-tab .coo-mob-label {{ font-size: 10px; font-weight: 700; letter-spacing: 0.01em; }}
        </style>

        <div class="coo-mobile-nav-container">
            {"".join(tab_html)}
        </div>
        """,
        unsafe_allow_html=True,
    )
