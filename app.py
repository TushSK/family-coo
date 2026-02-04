import streamlit as st
from PIL import Image
import json
from src.brain import get_coo_response
from src.gcal import add_event_to_calendar, list_upcoming_events
from src.utils import load_memory, save_feedback

# --- CONFIG ---
st.set_page_config(page_title="Family COO", page_icon="🏡", layout="centered")

# --- CUSTOM CSS (MOBILE OPTIMIZED) ---
st.markdown("""
    <style>
    .stButton>button {width: 100%; border-radius: 20px; font-weight: bold; padding: 0.5rem;}
    .reportview-container {margin-top: -2em;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION GATE ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state.password == st.secrets["general"]["app_password"]:
        st.session_state.authenticated = True
        del st.session_state.password
    else:
        st.error("⛔ Access Denied")

if not st.session_state.authenticated:
    st.title("🏡 Welcome Home")
    st.text_input("Enter Access PIN", type="password", key="password", on_change=check_password)
    st.stop() # HALT HERE if not logged in

# --- MAIN APP (ONLY RUNS IF LOGGED IN) ---

# Get API Key silently from secrets
API_KEY = st.secrets["general"]["gemini_api_key"]

# --- PROFILE HEADER ---
with st.expander("👤 **Profile & Settings**", expanded=False):
    st.caption("User: **Tushar Khandare**")
    loc = st.text_input("📍 Current Base", value="Tampa, FL")
    st.caption(f"🧠 Brain Memory: {len(load_memory())} items")

st.title("Family COO")

# --- INPUT TABS ---
tab_req, tab_cam = st.tabs(["📝 Type Request", "📸 Snap Photo"])
img_context = None
user_input = ""

with tab_req:
    user_input = st.text_area("What do we need to do?", placeholder="Ex: Plan a trip to Wat Thai Temple...", height=100)
    upl = st.file_uploader("Upload", type=['jpg','png'], label_visibility="collapsed")
    if upl: img_context = Image.open(upl)

with tab_cam:
    cam = st.camera_input("Take a picture")
    if cam: img_context = Image.open(cam)

# --- EXECUTE BUTTON ---
if st.button("🚀 GO", type="primary"):
    with st.spinner("Thinking..."):
        # 1. Fetch Context
        memory = load_memory(limit=5)
        cal_data = list_upcoming_events()
        
        # 2. Process
        raw = get_coo_response(API_KEY, user_input, memory, cal_data, loc, img_context)
        
        # 3. Parse JSON
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

# --- RESULTS ---
if st.session_state.get('result'):
    st.markdown(st.session_state['result'])
    
    # Calendar Action
    if st.session_state.get('event_data'):
        if st.button("📅 Add to Schedule"):
            res = add_event_to_calendar(st.session_state['event_data'])
            if "http" in res:
                st.success("✅ Saved to Google Calendar!")
            else:
                st.error("Sync Error. Check Secrets.")

    # Simple Feedback
    st.divider()
    with st.popover("👎 Correction?"):
        fb = st.text_input("What did I get wrong?")
        if st.button("Learn"):
            save_feedback(st.session_state.get('last_input'), "Plan", fb, "👎")
            st.toast("Updated Memory!")