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
st.set_page_config(page_title="Family COO", page_icon="🏡", layout="wide", initial_sidebar_state="collapsed")

# --- CSS ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    .stButton>button {width: 100%; border-radius: 12px; height: 3.5rem; font-weight: 600;}
    .ai-question {background-color: #e8f0fe; color: #1a73e8; padding: 15px; border-radius: 12px; margin-bottom: 15px;}
    .event-card-compact {border-left: 4px solid #34A853; padding: 8px 12px; background: var(--secondary-background-color); margin-bottom: 8px; border-radius: 4px;}
    </style>
""", unsafe_allow_html=True)

# --- AUTH ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; margin-top:50px;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    pin = st.text_input("PIN", type="password", label_visibility="collapsed")
    if st.button("Unlock"):
        if pin == st.secrets["general"]["app_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else: st.error("⛔ Incorrect")
    st.stop()

# --- INIT ---
if 'user_location' not in st.session_state: st.session_state.user_location = "Tampa, FL"
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'last_ai_question' not in st.session_state: st.session_state.last_ai_question = None

API_KEY = st.secrets["general"]["gemini_api_key"]

# --- CACHED BRAIN FUNCTION ---
@st.cache_data(show_spinner=False, ttl=600)
def cached_brain_call(user_input, _img, location, _history_len):
    memory = load_memory(limit=5)
    cal_data = list_upcoming_events()
    return get_coo_response(API_KEY, user_input, memory, cal_data, location, _img, st.session_state.chat_history)

# --- CHECK-IN LOGIC ---
pending_mission = get_pending_review()
if pending_mission:
    st.info(f"📋 Follow Up: **{pending_mission['title']}**")
    c1, c2, c3 = st.columns([2,2,1])
    with c1: 
        if st.button("✅ Done"): complete_mission_review(pending_mission['id'], True, "Done"); st.rerun()
    with c2: 
        if st.button("❌ No"): st.session_state.show_reason = True
    with c3: 
        if st.button("💤"): snooze_mission(pending_mission['id'], 4); st.rerun()
    if st.session_state.get('show_reason'):
        reason = st.text_input("Reason?"); 
        if st.button("Save"): complete_mission_review(pending_mission['id'], False, reason); st.rerun()
    st.divider()

# --- MAIN UI ---
st.title("Family COO")
tab_plan, tab_scan = st.tabs(["📝 Plan", "📸 Scan"])
img_context, user_input = None, ""

with tab_plan:
    if st.session_state.last_ai_question:
        st.markdown(f"<div class='ai-question'>🤖 {st.session_state.last_ai_question}</div>", unsafe_allow_html=True)
    
    user_input = st.text_area("Input", placeholder="Mission Brief...", height=100)
    
    # CLEAR CACHE BUTTON (For debugging)
    if st.button("🧹 Reset Context"): 
        st.cache_data.clear()
        st.session_state.chat_history = []
        st.session_state.last_ai_question = None
        st.rerun()
        
    upl = st.file_uploader("Img", type=['jpg','png'], label_visibility="collapsed")
    if upl: img_context = Image.open(upl)

with tab_scan:
    if st.toggle("Camera"):
        cam = st.camera_input("Scan", label_visibility="collapsed")
        if cam: img_context = Image.open(cam)

# --- EXECUTION ---
if st.button("🚀 EXECUTE", type="primary"):
    # Clear cache for this run to force a retry if needed
    st.cache_data.clear()
    
    with st.spinner("⏳ Negotiating with Google AI (This might take 40s due to traffic)..."):
        raw = cached_brain_call(
            user_input, 
            img_context, 
            st.session_state.user_location, 
            len(st.session_state.chat_history)
        )
        
        # Parse
        if "|||JSON_START|||" in raw:
            parts = raw.split("|||JSON_START|||")
            json_str = parts[1].split("|||JSON_END|||")[0].strip()
            try:
                data = json.loads(json_str)
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                
                if data.get("type") == "question":
                    st.session_state.last_ai_question = data.get("text")
                    st.session_state.chat_history.append({"role": "assistant", "content": data.get("text")})
                    st.rerun()
                elif data.get("type") == "plan":
                    st.session_state.last_ai_question = None
                    st.session_state['result'] = data.get("text")
                    st.session_state['event_list'] = data.get("events", [])
                    st.session_state.chat_history.append({"role": "assistant", "content": data.get("text")})
            except: st.error("JSON Error")
        else:
            st.session_state['result'] = raw

# --- RESULTS ---
if st.session_state.get('result'):
    st.success(st.session_state['result'])
    events = st.session_state.get('event_list', [])
    if events:
        st.subheader(f"📅 Schedule ({len(events)})")
        for i, event in enumerate(events):
            st.markdown(f"<div class='event-card-compact'><b>{event.get('start_time','')[11:16]}</b> {event.get('title')}<br><small>📍 {event.get('location')}</small></div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Add", key=f"a_{i}"):
                    add_event_to_calendar(event); log_mission_start(event); st.toast("Added")
            with c2:
                st.link_button("Map", f"http://maps.google.com/?q={urllib.parse.quote(event.get('location',''))}")