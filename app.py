import streamlit as st
from PIL import Image
import json
import requests
from geopy.geocoders import Nominatim
import pandas as pd
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

# --- HELPER: AUTO-LOCATE ---
@st.cache_data(ttl=3600) # Cache for 1 hour so we don't spam requests
def get_auto_location():
    try:
        # Get City from IP Address (Free, no key needed)
        ip_data = requests.get('https://ipinfo.io/json').json()
        city = ip_data.get('city', 'Tampa')
        region = ip_data.get('region', 'FL')
        return f"{city}, {region}"
    except:
        return "Tampa, FL"

# --- HELPER: GET MAP COORDINATES ---
@st.cache_data
def get_lat_lon(location_name):
    try:
        geolocator = Nominatim(user_agent="family_coo_app")
        loc = geolocator.geocode(location_name)
        if loc:
            return pd.DataFrame({'lat': [loc.latitude], 'lon': [loc.longitude]})
    except:
        return None
    return None

# --- CUSTOM CSS (MOBILE OPTIMIZED) ---
st.markdown("""
    <style>
    /* Full Width Camera & Buttons */
    .stButton>button {width: 100%; border-radius: 12px; height: 3.5em; font-weight: 600;}
    div[data-testid="stCameraInput"] video {width: 100% !important; border-radius: 12px;}
    
    /* Sleek Sidebar */
    [data-testid="stSidebar"] {background-color: #f8f9fa;}
    .user-card {
        background-color: white; 
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        text-align: center;
    }
    .user-name {font-weight: bold; font-size: 1.1em; margin: 0;}
    .user-handle {color: #888; font-size: 0.9em; margin: 0;}
    </style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🏡 Family COO")
    st.caption("Secure Login")
    pin = st.text_input("Enter Access PIN", type="password")
    if st.button("Unlock"):
        if pin == st.secrets["general"]["app_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("⛔ Incorrect PIN")
    st.stop()

# --- MAIN APP ---
API_KEY = st.secrets["general"]["gemini_api_key"]

# --- SIDEBAR: THE "REAL APP" FEEL ---
with st.sidebar:
    # 1. Profile Card
    st.markdown("""
    <div class="user-card">
        <div style="font-size: 2em;">👤</div>
        <p class="user-name">Tushar Khandare</p>
        <p class="user-handle">Family Administrator</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. Personalization & Map
    with st.expander("🌍 Location Base", expanded=True):
        # Auto-detect default if session is empty
        default_loc = get_auto_location()
        current_loc = st.text_input("Current City", value=default_loc)
        
        # Live Map
        coords = get_lat_lon(current_loc)
        if coords is not None:
            st.map(coords, zoom=12, size=50, height=150)
        else:
            st.caption("Map unavailable for this location.")

    # 3. Settings
    with st.expander("⚙️ Settings"):
        mem_count = len(load_memory())
        st.write(f"**Brain Memory:** {mem_count} items")
        if st.button("🧹 Clear Memory"):
            st.toast("Memory Wiped")
        st.divider()
        st.caption("📅 Calendar: Connected")

    # 4. Help
    with st.expander("ℹ️ Help"):
        st.markdown("Use the **Camera** tab to snap flyers. Use **Type** for quick questions.")

    # 5. Logout (Pushed to bottom)
    st.write("") 
    st.write("")
    if st.button("🚪 Log Out", type="secondary"):
        st.session_state.authenticated = False
        st.rerun()

# --- MAIN INTERFACE ---
st.title("The Family COO")

tab_req, tab_cam = st.tabs(["📝 Type Request", "📸 Camera"])

img_context = None
user_input = ""

with tab_req:
    user_input = st.text_area("Mission Brief", placeholder="Ex: Find a Thai temple near me...", height=100)
    upl = st.file_uploader("Upload", type=['jpg','png'], label_visibility="collapsed")
    if upl: img_context = Image.open(upl)

with tab_cam:
    st.caption("Point at any flyer, schedule, or invite.")
    cam = st.camera_input("Snap Photo", label_visibility="collapsed") 
    if cam: 
        img_context = Image.open(cam)
        st.success("✅ Image Captured")

# --- EXECUTION ---
st.divider()

if st.button("🚀 EXECUTE PLAN", type="primary"):
    with st.spinner(f"🧠 Scanning {current_loc} & Checking Calendar..."):
        # 1. Context
        memory = load_memory(limit=5)
        cal_data = list_upcoming_events()
        
        # 2. AI
        raw_response = get_coo_response(API_KEY, user_input, memory, cal_data, current_loc, img_context)
        
        # 3. Parsing
        if "|||JSON_START|||" in raw_response:
            parts = raw_response.split("|||JSON_START|||")
            st.session_state['result'] = parts[0].strip()
            try:
                js = parts[1].split("|||JSON_END|||")[0].strip()
                st.session_state['event_data'] = json.loads(js)
            except:
                st.session_state['event_data'] = None
        else:
            st.session_state['result'] = raw_response
            st.session_state['event_data'] = None
            
        st.session_state['last_input'] = user_input

# --- RESULTS ---
if st.session_state.get('result'):
    st.markdown(st.session_state['result'])
    
    if st.session_state.get('event_data'):
        if st.button("📅 Add to Schedule"):
            res = add_event_to_calendar(st.session_state['event_data'])
            if "http" in res:
                st.success(f"✅ [Event Created]({res})")
            else:
                st.error("Sync Error")

    with st.expander("🧠 Teach AI"):
        col1, col2 = st.columns([1,4])
        with col1: r = st.radio("Rate", ["👍", "👎"], label_visibility="collapsed")
        with col2: fb = st.text_input("Correction")
        if st.button("Save Feedback"):
            save_feedback(st.session_state.get('last_input'), "Plan", fb, r)
            st.toast("Learned!")