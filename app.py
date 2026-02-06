import streamlit as st
from PIL import Image
import json
import urllib.parse
from src.brain import get_coo_response
from src.gcal import add_event_to_calendar, list_upcoming_events
from src.utils import load_memory, save_manual_feedback, log_mission_start, get_pending_review, complete_mission_review

# --- CONFIG ---
st.set_page_config(page_title="Family COO", page_icon="🏡", layout="wide", initial_sidebar_state="collapsed")

# --- CLEAN UI CSS ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .stAppDeployButton {display: none;}
    
    /* Card Style for Feedback */
    .feedback-card {
        padding: 15px; border-radius: 10px; 
        background-color: #f0f2f6; border-left: 5px solid #ff4b4b;
        margin-bottom: 20px;
    }
    /* Mobile Touch Targets */
    .stButton>button {width: 100%; border-radius: 12px; height: 3rem; font-weight: 600;}
    div[data-testid="stCameraInput"] {width: 100%;}
    </style>
""", unsafe_allow_html=True)

# --- AUTH ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    pin = st.text_input("PIN", type="password", label_visibility="collapsed", placeholder="Enter PIN")
    if st.button("Unlock"):
        if pin == st.secrets["general"]["app_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else: st.error("⛔ Incorrect")
    st.stop()

# --- 🧠 INTELLIGENT CHECK-IN (NEW FEATURE) ---
# Check if there is a past mission that needs a report
pending_mission = get_pending_review()

if pending_mission:
    with st.container():
        st.markdown(f"""
        <div class="feedback-card">
            <h3>📋 Follow Up</h3>
            <p><strong>{pending_mission['title']}</strong> ended recently.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("Did this happen?")
        col_y, col_n = st.columns(2)
        
        with col_y:
            if st.button("✅ Yes, Done!"):
                complete_mission_review(pending_mission['id'], True, "Completed successfully.")
                st.toast("Great job! Logged.")
                st.rerun()
                
        with col_n:
            if st.button("❌ No / Skipped"):
                st.session_state.show_reason_input = True

        if st.session_state.get('show_reason_input'):
            reason = st.text_input("Why? (Short reason helps me learn)", placeholder="Ex: Too tired, Traffic, Rain...")
            if st.button("Save Reason"):
                complete_mission_review(pending_mission['id'], False, reason)
                st.toast("Understood. Brain updated.")
                st.session_state.show_reason_input = False
                st.rerun()
    
    st.divider() # Separate feedback from main app

# --- MAIN APP ---
if 'user_location' not in st.session_state: st.session_state.user_location = "Tampa, FL"
API_KEY = st.secrets["general"]["gemini_api_key"]

# Sidebar
with st.sidebar:
    st.header("👤 Tushar Khandare")
    with st.expander("🌍 Location", expanded=True):
        st.session_state.user_location = st.text_input("City", value=st.session_state.user_location)
    with st.expander("🧠 Memory"):
        st.write(f"Learned Patterns: **{len(load_memory())}**")
        if st.button("Clear"): pass 
    st.divider()
    if st.button("Log Out"): st.session_state.authenticated = False; st.rerun()

# Main Interface
st.title("Family COO")
tab_plan, tab_scan = st.tabs(["📝 Plan", "📸 Scan"])
img_context, user_input = None, ""

with tab_plan:
    user_input = st.text_area("Mission Brief", placeholder="What do we need to do?", height=100)
    upl = st.file_uploader("Upload", type=['jpg','png'], label_visibility="collapsed")
    if upl: img_context = Image.open(upl)

with tab_scan:
    cam = st.camera_input("Scan", label_visibility="collapsed")
    if cam: img_context = Image.open(cam)

# Execution
if st.button("🚀 EXECUTE", type="primary"):
    with st.spinner("Thinking..."):
        memory = load_memory(limit=10) # More memory context
        cal_data = list_upcoming_events()
        raw = get_coo_response(API_KEY, user_input, memory, cal_data, st.session_state.user_location, img_context)
        
        # Parse
        if "|||JSON_START|||" in raw:
            parts = raw.split("|||JSON_START|||")
            st.session_state['result'] = parts[0].strip()
            try:
                js = parts[1].split("|||JSON_END|||")[0].strip()
                st.session_state['event_data'] = json.loads(js)
            except: st.session_state['event_data'] = None
        else:
            st.session_state['result'] = raw
            st.session_state['event_data'] = None
            
        st.session_state['last_input'] = user_input

# Results
if st.session_state.get('result'):
    st.markdown(st.session_state['result'])
    
    if st.session_state.get('event_data'):
        data = st.session_state['event_data']
        # 1. Calendar Link
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📅 Add to Calendar"):
                link = add_event_to_calendar(data)
                # CRITICAL: Start tracking this mission for feedback later
                log_mission_start(data) 
                
                if "http" in link: st.success("Scheduled & Tracking!")
                else: st.error("Error")
        # 2. Map Link
        with c2:
            loc = data.get('location', st.session_state.user_location)
            st.link_button("🗺️ Map", f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc)}")

    # Manual Feedback
    with st.expander("Feedback"):
        c_a, c_b = st.columns([1,4])
        with c_a: rate = st.radio("Rate", ["👍", "👎"], label_visibility="collapsed")
        with c_b: fb = st.text_input("Correction?")
        if st.button("Save"):
            save_manual_feedback(st.session_state.get('last_input'), fb, rate)
            st.toast("Saved!")