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
    initial_sidebar_state="expanded" # Ensures menu is accessible on mobile
)

# --- CSS (Dark/Light Mode Compatible) ---
st.markdown("""
    <style>
    /* 1. Mobile & Theme Fixes */
    .stAppDeployButton {display: none;}
    .stButton>button {width: 100%; border-radius: 12px; height: 3.5rem; font-weight: 600;}
    
    /* 2. Chat Bubble (Adapts to theme) */
    .ai-question {
        background-color: var(--secondary-background-color); 
        color: var(--text-color);
        padding: 15px; 
        border-radius: 12px; 
        margin-bottom: 15px;
        border-left: 5px solid #1a73e8;
        font-weight: 500;
    }
    
    /* 3. Event Card (Adapts to theme) */
    .event-card-compact {
        border-left: 4px solid #34A853; 
        padding: 10px 15px; 
        background-color: var(--secondary-background-color); 
        color: var(--text-color);
        margin-bottom: 10px; 
        border-radius: 8px;
    }
    
    /* 4. Feedback Area */
    .feedback-area {
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid var(--secondary-background-color);
    }
    
    /* 5. Check-in Card (Red Alert) */
    .feedback-card {
        padding: 15px; border-radius: 12px; 
        background-color: var(--secondary-background-color); 
        border-left: 6px solid #FF4B4B;
        margin-bottom: 20px;
    }
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

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Tushar Khandare")
    st.caption("Family Administrator")
    
    with st.expander("🌍 Location", expanded=True):
        st.session_state.user_location = st.text_input("City", value=st.session_state.user_location)
        
    with st.expander("🧠 Memory"):
        st.write(f"Learned Patterns: **{len(load_memory())}**")
        if st.button("Clear Memory"): pass 
            
    st.divider()
    if st.button("Log Out"): 
        st.session_state.authenticated = False
        st.rerun()

# --- CHECK-IN LOGIC ---
pending_mission = get_pending_review()
if pending_mission:
    with st.container():
        st.markdown(f"""
        <div class="feedback-card">
            <h3 style="margin:0;">📋 Follow Up</h3>
            <p style="margin:5px 0 10px 0;"><strong>{pending_mission['title']}</strong> ended recently.</p>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2,2,1])
        with c1: 
            if st.button("✅ Done"): complete_mission_review(pending_mission['id'], True, "Done"); st.rerun()
        with c2: 
            if st.button("❌ No"): st.session_state.show_reason = True
        with c3: 
            if st.button("💤"): snooze_mission(pending_mission['id'], 4); st.rerun()
        
        if st.session_state.get('show_reason'):
            reason = st.text_input("Reason?"); 
            if st.button("Save Reason"): complete_mission_review(pending_mission['id'], False, reason); st.rerun()
    st.divider()

# --- MAIN UI ---
st.title("Family COO")
tab_plan, tab_scan = st.tabs(["📝 Plan", "📸 Scan"])
img_context, user_input = None, ""

with tab_plan:
    # AI Question Bubble
    if st.session_state.last_ai_question:
        st.markdown(f"<div class='ai-question'>🤖 {st.session_state.last_ai_question}</div>", unsafe_allow_html=True)
    
    # Dynamic Placeholder
    ph = "Your Answer..." if st.session_state.last_ai_question else "Mission Brief (e.g. 'Plan Judo')"
    user_input = st.text_area("Input", placeholder=ph, height=100, label_visibility="collapsed")
    
    # Reset Context
    if st.button("🔄 Reset Context"): 
        st.session_state.chat_history = []
        st.session_state.last_ai_question = None
        st.session_state['result'] = None
        st.toast("🧠 Context Cleared")
        st.rerun()
        
    upl = st.file_uploader("Upload", type=['jpg','png'], label_visibility="collapsed")
    if upl: img_context = Image.open(upl)

with tab_scan:
    if st.toggle("Activate Camera"):
        cam = st.camera_input("Scan", label_visibility="collapsed")
        if cam: img_context = Image.open(cam)

# --- EXECUTION ---
# Dynamic Button Label
btn_label = "Reply" if st.session_state.last_ai_question else "🚀 EXECUTE"

if st.button(btn_label, type="primary"):
    with st.spinner("Processing..."):
        memory = load_memory(limit=5)
        cal_data = list_upcoming_events()
        
        raw = get_coo_response(
            API_KEY, 
            user_input, 
            memory, 
            cal_data, 
            st.session_state.user_location, 
            img_context, 
            st.session_state.chat_history
        )
        
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
            except: st.error("System Error: Parsing Failed")
        else:
            st.session_state['result'] = raw

# --- RESULTS ---
if st.session_state.get('result'):
    st.success(st.session_state['result'])
    
    events = st.session_state.get('event_list', [])
    if events:
        st.subheader(f"📅 Schedule ({len(events)})")
        for i, event in enumerate(events):
            st.markdown(f"""
            <div class='event-card-compact'>
                <b>{event.get('start_time','')[11:16]}</b> {event.get('title')}
                <br><span style='font-size:0.9em; opacity:0.8'>📍 {event.get('location', 'No Loc')}</span>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("Add", key=f"a_{i}"):
                    add_event_to_calendar(event)
                    log_mission_start(event)
                    st.toast("✅ Added")
            with c2:
                loc = event.get('location', st.session_state.user_location)
                st.link_button("🗺️ Map", f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc)}")

    # FEEDBACK SECTION
    st.markdown("<div class='feedback-area'></div>", unsafe_allow_html=True)
    with st.expander("📝 Feedback & Corrections"):
        c_a, c_b = st.columns([1,4])
        with c_a: 
            rate = st.radio("Quality", ["👍", "👎"], label_visibility="collapsed")
        with c_b: 
            fb = st.text_input("Correction?")
        if st.button("Save Feedback"):
            save_manual_feedback(st.session_state.get('last_input', 'Last Plan'), fb, rate)
            st.toast("🧠 Brain Updated!")