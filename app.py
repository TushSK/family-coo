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

# --- MOBILE OPTIMIZED CSS ---
st.markdown("""
    <style>
    /* 1. AGGRESSIVE HIDING (Logos, Footer, Hamburger) */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important; display: none !important;}
    header {visibility: hidden !important;}
    .stAppDeployButton {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    
    /* 2. THEME ADAPTATION */
    .reportview-container {
        background: var(--background-color);
        color: var(--text-color);
    }
    
    /* 3. MOBILE TOUCH TARGETS */
    .stButton>button {
        width: 100%; 
        border-radius: 12px; 
        height: 3.5rem; 
        font-weight: 600;
    }
    
    /* 4. FEEDBACK CARD STYLE */
    .feedback-card {
        padding: 15px; 
        border-radius: 12px; 
        background-color: var(--secondary-background-color); 
        border-left: 6px solid #FF4B4B;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- AUTH ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; margin-top:50px;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    pin = st.text_input("Access PIN", type="password", label_visibility="collapsed")
    
    if st.button("Unlock"):
        if pin == st.secrets["general"]["app_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("⛔ Incorrect")
    st.stop()

# --- INTELLIGENT CHECK-IN (With Snooze) ---
pending_mission = get_pending_review()

if pending_mission:
    with st.container():
        st.markdown(f"""
        <div class="feedback-card">
            <h3 style="margin:0;">📋 Follow Up</h3>
            <p style="margin:5px 0 10px 0;"><strong>{pending_mission['title']}</strong> ended recently.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("Did it happen?")
        c1, c2, c3 = st.columns([2, 2, 1])
        
        with c1:
            if st.button("✅ Yes"):
                complete_mission_review(pending_mission['id'], True, "Done")
                st.toast("Logged!")
                st.rerun()
        with c2:
            if st.button("❌ No"):
                st.session_state.show_reason_input = True
        with c3:
            # SNOOZE BUTTON (Clock Icon)
            if st.button("💤", help="Ask me later"):
                snooze_mission(pending_mission['id'], hours=4)
                st.toast("Snoozed for 4 hours")
                st.rerun()

        if st.session_state.get('show_reason_input'):
            reason = st.text_input("Reason?", placeholder="Ex: Too tired, Rain...")
            if st.button("Save"):
                complete_mission_review(pending_mission['id'], False, reason)
                st.rerun()
    st.divider()

# --- MAIN APP ---
if 'user_location' not in st.session_state:
    st.session_state.user_location = "Tampa, FL"

API_KEY = st.secrets["general"]["gemini_api_key"]

# SIDEBAR
with st.sidebar:
    st.header("👤 Tushar Khandare")
    
    with st.expander("🌍 Location", expanded=True):
        st.session_state.user_location = st.text_input("City", value=st.session_state.user_location)
        
    with st.expander("🧠 Memory"):
        st.write(f"Learned Patterns: **{len(load_memory())}**")
        if st.button("Clear"):
            pass 
            
    st.divider()
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# MAIN INTERFACE
st.title("Family COO")
tab_plan, tab_scan = st.tabs(["📝 Plan", "📸 Scan"])
img_context = None
user_input = ""

with tab_plan:
    user_input = st.text_area("Mission Brief", placeholder="What do we need to do?", height=100)
    upl = st.file_uploader("Upload", type=['jpg','png'], label_visibility="collapsed")
    if upl:
        img_context = Image.open(upl)

with tab_scan:
    # CAMERA PERMISSION FIX: Only render camera if requested
    st.info("💡 Tap below to activate camera.")
    
    if st.toggle("Activate Camera"):
        cam = st.camera_input("Scan", label_visibility="collapsed")
        if cam: 
            img_context = Image.open(cam)
            st.success("Image Captured")

# EXECUTION
if st.button("🚀 EXECUTE", type="primary"):
    with st.spinner("Thinking..."):
        memory = load_memory(limit=10)
        cal_data = list_upcoming_events()
        raw = get_coo_response(API_KEY, user_input, memory, cal_data, st.session_state.user_location, img_context)
        
        if "|||JSON_START|||" in raw:
            parts = raw.split("|||JSON_START|||")
            st.session_state['result'] = parts[0].strip()
            try:
                js = parts[1].split("|||JSON_END|||")[0].strip()
                st.session_state['event_data'] = json.loads(js)
            except:
                st.session_state['event_data'] = None
        else:
            st.session_state['result'] = raw
            st.session_state['event_data'] = None
            
        st.session_state['last_input'] = user_input

# RESULTS
if st.session_state.get('result'):
    st.markdown(st.session_state['result'])
    
    if st.session_state.get('event_data'):
        data = st.session_state['event_data']
        c1, c2 = st.columns(2)
        
        with c1:
            if st.button("📅 Add to Calendar"):
                link = add_event_to_calendar(data)
                log_mission_start(data) # Start tracking
                if "http" in link:
                    st.success("Scheduled!")
                else:
                    st.error("Error")
                    
        with c2:
            loc = data.get('location', st.session_state.user_location)
            map_link = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc)}"
            st.link_button("🗺️ Map", map_link)

    with st.expander("Feedback"):
        c_a, c_b = st.columns([1,4])
        with c_a:
            rate = st.radio("Rate", ["👍", "👎"], label_visibility="collapsed")
        with c_b:
            fb = st.text_input("Correction?")
            
        if st.button("Save"):
            save_manual_feedback(st.session_state.get('last_input'), fb, rate)
            st.toast("Saved!")