import streamlit as st
from PIL import Image
import json
import urllib.parse
from src.brain import get_coo_response
from src.gcal import add_event_to_calendar, list_upcoming_events
from src.utils import (
    load_memory, 
    save_manual_feedback, 
    log_mission_start, 
    get_pending_review, 
    complete_mission_review, 
    snooze_mission
)

# --- CONFIG ---
st.set_page_config(
    page_title="Family COO", 
    page_icon="🏡", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important; display: none !important;}
    header {visibility: hidden !important;}
    .stAppDeployButton {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    
    .reportview-container {background: var(--background-color); color: var(--text-color);}
    .stButton>button {width: 100%; border-radius: 12px; height: 3.5rem; font-weight: 600;}
    
    /* Event Card Style */
    .event-card {
        background-color: var(--secondary-background-color);
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 4px solid #4CAF50;
    }
    </style>
""", unsafe_allow_html=True)

# --- AUTH ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; margin-top:50px;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    pin = st.text_input("Access PIN", type="password", label_visibility="collapsed")
    if st.button("Unlock"):
        if pin == st.secrets["general"]["app_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else: st.error("⛔ Incorrect")
    st.stop()

# --- CHECK-IN LOGIC ---
pending_mission = get_pending_review()
if pending_mission:
    with st.container():
        st.info(f"📋 Follow Up: **{pending_mission['title']}**")
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            if st.button("✅ Done"):
                complete_mission_review(pending_mission['id'], True, "Done")
                st.rerun()
        with c2:
            if st.button("❌ No"):
                st.session_state.show_reason_input = True
        with c3:
            if st.button("💤"):
                snooze_mission(pending_mission['id'], 4)
                st.rerun()
        if st.session_state.get('show_reason_input'):
            reason = st.text_input("Reason?", placeholder="Ex: Too tired...")
            if st.button("Save"):
                complete_mission_review(pending_mission['id'], False, reason)
                st.rerun()
    st.divider()

# --- MAIN APP ---
if 'user_location' not in st.session_state: st.session_state.user_location = "Tampa, FL"
API_KEY = st.secrets["general"]["gemini_api_key"]

with st.sidebar:
    st.header("👤 Tushar Khandare")
    with st.expander("🌍 Location", expanded=True):
        st.session_state.user_location = st.text_input("City", value=st.session_state.user_location)
    with st.expander("🧠 Memory"):
        st.write(f"Learned Patterns: **{len(load_memory())}**")
        if st.button("Clear"): pass 
    st.divider()
    if st.button("Log Out"): st.session_state.authenticated = False; st.rerun()

st.title("Family COO")
tab_plan, tab_scan = st.tabs(["📝 Plan", "📸 Scan"])
img_context, user_input = None, ""

with tab_plan:
    user_input = st.text_area("Mission Brief", placeholder="Ex: Visit Quest, then Walmart, then cook Misal...", height=100)
    upl = st.file_uploader("Upload", type=['jpg','png'], label_visibility="collapsed")
    if upl: img_context = Image.open(upl)

with tab_scan:
    st.info("💡 Tap below to activate camera.")
    if st.toggle("Activate Camera"):
        cam = st.camera_input("Scan", label_visibility="collapsed")
        if cam: img_context = Image.open(cam)

# --- EXECUTION ---
if st.button("🚀 EXECUTE", type="primary"):
    with st.spinner("Analyzing Logistics..."):
        memory = load_memory(limit=10)
        cal_data = list_upcoming_events()
        raw = get_coo_response(API_KEY, user_input, memory, cal_data, st.session_state.user_location, img_context)
        
        # Reset previous data
        st.session_state['event_list'] = []
        
        # PARSING LOGIC (Handles Lists now)
        if "|||JSON_START|||" in raw:
            parts = raw.split("|||JSON_START|||")
            st.session_state['result'] = parts[0].strip()
            try:
                js = parts[1].split("|||JSON_END|||")[0].strip()
                data = json.loads(js)
                # Ensure it's a list
                if isinstance(data, dict):
                    st.session_state['event_list'] = [data]
                elif isinstance(data, list):
                    st.session_state['event_list'] = data
            except:
                st.session_state['event_list'] = []
        else:
            st.session_state['result'] = raw
            
        st.session_state['last_input'] = user_input

# --- RESULTS DISPLAY ---
if st.session_state.get('result'):
    st.markdown(st.session_state['result'])
    
    # MULTI-EVENT HANDLER
    events = st.session_state.get('event_list', [])
    
    if events:
        st.divider()
        st.subheader(f"📅 Proposed Schedule ({len(events)} Items)")
        
        for i, event in enumerate(events):
            # Unique key for every button using index
            with st.container():
                st.markdown(f"""
                <div class="event-card">
                    <b>{event.get('start_time', '')[11:16]} - {event.get('title')}</b><br>
                    <small>📍 {event.get('location', 'No Loc')}</small>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button(f"Add '{event['title']}'", key=f"btn_add_{i}"):
                        link = add_event_to_calendar(event)
                        log_mission_start(event)
                        if "http" in link: st.toast(f"✅ Added {event['title']}")
                        else: st.error("Sync Error")
                with c2:
                    loc = event.get('location', st.session_state.user_location)
                    map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc)}"
                    st.link_button("🗺️ Map", map_url)

    # FEEDBACK
    with st.expander("Feedback"):
        c_a, c_b = st.columns([1,4])
        with c_a: rate = st.radio("Rate", ["👍", "👎"], label_visibility="collapsed")
        with c_b: fb = st.text_input("Correction?")
        if st.button("Save"):
            save_manual_feedback(st.session_state.get('last_input'), fb, rate)
            st.toast("Saved!")