import streamlit as st
from PIL import Image
import json
import urllib.parse
from src.brain import get_coo_response
from src.gcal import add_event_to_calendar, list_upcoming_events
from src.utils import load_memory, save_feedback

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Family COO", 
    page_icon="🏡", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- THE "CLEAN APP" CSS SUITE ---
st.markdown("""
    <style>
    /* 1. HIDE STREAMLIT UI (The Crown, Rocket, Hamburger, Footer) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAppDeployButton {display: none;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stStatusWidget"] {visibility: hidden;}
    
    /* 2. SMART SIDEBAR (Native Theme Adaptation) */
    /* We DO NOT force colors here. We let Streamlit pick 
       White for Light Mode and Dark Gray for Dark Mode automatically. */
       
    /* 3. CAMERA & BUTTONS (Mobile Optimization) */
    div[data-testid="stCameraInput"] {width: 100%;}
    div[data-testid="stCameraInput"] video {
        width: 100% !important; 
        border-radius: 12px;
        object-fit: cover;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    pin = st.text_input("Enter PIN", type="password", label_visibility="collapsed", placeholder="Enter Access PIN")
    if st.button("Unlock"):
        if pin == st.secrets["general"]["app_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("⛔ Incorrect PIN")
    st.stop()

# --- MAIN APP LOGIC ---

# 1. Initialize Location
if 'user_location' not in st.session_state:
    st.session_state.user_location = "Tampa, FL"

API_KEY = st.secrets["general"]["gemini_api_key"]

# --- SIDEBAR (Native Elements = Perfect Dark Mode) ---
with st.sidebar:
    st.header("👤 Tushar Khandare")
    st.caption("Family Administrator")
    
    # Using Native Expanders ensures the text color adapts automatically
    with st.expander("🌍 Location Base", expanded=True):
        new_loc = st.text_input("City", value=st.session_state.user_location)
        if new_loc != st.session_state.user_location:
            st.session_state.user_location = new_loc

    with st.expander("🧠 Brain Memory"):
        st.write(f"Items Learned: **{len(load_memory())}**")
        if st.button("Clear Memory"):
            st.toast("Memory Wiped")

    st.divider()
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# --- HOME SCREEN ---
st.title("Family COO")
st.caption(f"📍 Active in: **{st.session_state.user_location}**")

# TABS
tab_text, tab_cam = st.tabs(["📝 Plan", "📸 Scan"])
img_context = None
user_input = ""

with tab_text:
    user_input = st.text_area("Mission Brief", placeholder="Ex: Find a Thai Temple with a market...", height=100)
    uploaded = st.file_uploader("Upload", type=['jpg','png'], label_visibility="collapsed")
    if uploaded: img_context = Image.open(uploaded)

with tab_cam:
    cam = st.camera_input("Scanner", label_visibility="collapsed")
    if cam: 
        img_context = Image.open(cam)
        st.success("Photo Captured")

# ACTION BUTTON
st.divider()
if st.button("🚀 EXECUTE PLAN", type="primary"):
    with st.spinner("🔄 Checking Schedule & Maps..."):
        # Load Data
        memory = load_memory(limit=5)
        cal_data = list_upcoming_events()
        
        # AI Processing
        raw = get_coo_response(API_KEY, user_input, memory, cal_data, st.session_state.user_location, img_context)
        
        # Parse Results
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

# --- RESULTS & MAPS ---
if st.session_state.get('result'):
    st.markdown(st.session_state['result'])
    
    # 🗺️ MAP INTEGRATION
    if st.session_state.get('event_data'):
        data = st.session_state['event_data']
        # Use location from AI, or fallback to current city
        loc_query = data.get('location', st.session_state.user_location)
        
        # Google Maps URL (Universal Link)
        map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc_query)}"
        
        # Action Buttons
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📅 Add to Calendar"):
                link = add_event_to_calendar(data)
                if "http" in link: st.success("Saved!")
                else: st.error("Error")
        with c2:
            st.link_button("🗺️ Open in Maps", map_url)

    # FEEDBACK
    with st.expander("Feedback"):
        c_a, c_b = st.columns([1,4])
        with c_a: rate = st.radio("Rate", ["👍", "👎"], label_visibility="collapsed")
        with c_b: fb = st.text_input("Correction?")
        if st.button("Save Feedback"):
            save_feedback(st.session_state.get('last_input'), "Plan", fb, rate)
            st.toast("Saved!")