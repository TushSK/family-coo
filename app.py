import streamlit as st
from PIL import Image
import json
from src.brain import get_coo_response
from src.gcal import add_event_to_calendar, list_upcoming_events
from src.utils import load_memory, save_feedback

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Family COO", 
    page_icon="🏡", 
    layout="wide", # Uses more screen space on mobile
    initial_sidebar_state="collapsed" # Starts clean
)

# --- CUSTOM CSS (THE MAGIC SAUCE) ---
# This forces the camera to be big and styles the sidebar
st.markdown("""
    <style>
    /* 1. Make Camera & Buttons Full Width */
    .stButton>button {width: 100%; border-radius: 12px; height: 3em; font-weight: 600;}
    div[data-testid="stCameraInput"] video {width: 100% !important; border-radius: 12px;}
    
    /* 2. Clean up Sidebar */
    [data-testid="stSidebar"] {background-color: #f8f9fa;}
    .sidebar-user {padding: 10px; border-bottom: 1px solid #ddd; margin-bottom: 20px;}
    
    /* 3. Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION CHECK ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🏡 Family COO")
    st.caption("Secure Login")
    
    # Simple PIN Check (Matches your Secrets)
    pin = st.text_input("Enter Access PIN", type="password")
    if st.button("Unlock"):
        if pin == st.secrets["general"]["app_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("⛔ Incorrect PIN")
    st.stop()

# --- MAIN APP ---

# 1. Get Keys
API_KEY = st.secrets["general"]["gemini_api_key"]

# --- SIDEBAR: THE "PRO" MENU ---
with st.sidebar:
    # PROFILE HEADER
    st.markdown("""
    <div class="sidebar-user">
        <h3>👤 Tushar Khandare</h3>
        <p style="color:gray; font-size:0.9em;">tushar.khandare@gmail.com</p>
    </div>
    """, unsafe_allow_html=True)
    
    # MENU SECTIONS
    with st.expander("🎨 Personalization", expanded=True):
        current_loc = st.text_input("📍 Current Base", value="Tampa, FL")
        mem_count = len(load_memory())
        st.caption(f"🧠 Brain Memory: {mem_count} items")
        if st.button("Clear Memory", help="Wipes AI learning"):
            # Logic to clear memory file could go here
            st.toast("Memory Wiped")

    with st.expander("⚙️ Settings"):
        st.info("📅 Calendar: Connected")
        st.checkbox("Debug Mode", value=False, key="debug_mode")

    with st.expander("ℹ️ Help"):
        st.markdown("""
        **Quick Tips:**
        - **Plan:** "Plan a trip to [Place]"
        - **Check:** "Am I free Saturday?"
        - **Upload:** Photos of flyers works best.
        """)

    st.divider()
    if st.button("🚪 Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# --- MAIN INTERFACE (MOBILE OPTIMIZED) ---
st.title("The Family COO")

# TABS: Use icons for cleaner mobile look
tab_req, tab_cam = st.tabs(["📝 Type Request", "📸 Camera"])

img_context = None
user_input = ""

with tab_req:
    user_input = st.text_area("Mission Brief", placeholder="Ex: Is Saturday free for the Beach?", height=120)
    upl = st.file_uploader("Upload Image", type=['jpg','png'], label_visibility="collapsed")
    if upl: img_context = Image.open(upl)

with tab_cam:
    st.info("💡 Tip: Hold phone steady. Photo auto-uploads.")
    # The 'key' ensures it doesn't reload weirdly
    cam = st.camera_input("Snap Photo", label_visibility="collapsed") 
    if cam: 
        img_context = Image.open(cam)
        st.success("✅ Photo Captured")

# --- ACTION AREA ---
st.divider()

if st.button("🚀 EXECUTE PLAN", type="primary"):
    with st.spinner("🧠 Thinking..."):
        # 1. Gather Context
        memory = load_memory(limit=5)
        cal_data = list_upcoming_events()
        
        # 2. AI Processing
        raw_response = get_coo_response(API_KEY, user_input, memory, cal_data, current_loc, img_context)
        
        # 3. Parse JSON vs Text
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

# --- RESULTS DISPLAY ---
if st.session_state.get('result'):
    st.markdown(st.session_state['result'])
    
    # Calendar Button (Green)
    if st.session_state.get('event_data'):
        if st.button("📅 Add to Schedule"):
            res = add_event_to_calendar(st.session_state['event_data'])
            if "http" in res:
                st.balloons()
                st.success(f"✅ **Saved!** [Open Calendar]({res})")
            else:
                st.error("Sync Error. Check Secrets.")

    # Feedback Loop (Hidden unless needed)
    with st.expander("🧠 Teach the AI (Feedback)"):
        col_f1, col_f2 = st.columns([1,4])
        with col_f1: 
            rating = st.radio("Rate", ["👍", "👎"], label_visibility="collapsed")
        with col_f2: 
            fb_text = st.text_input("Correction?")
        
        if st.button("Save Feedback"):
            save_feedback(st.session_state.get('last_input'), "Plan", fb_text, rating)
            st.toast("Learning Saved!")