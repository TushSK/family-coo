import streamlit as st
from PIL import Image
import json
import urllib.parse
import re
from datetime import datetime
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
    initial_sidebar_state="expanded"
)

# --- CSS ---
st.markdown("""
    <style>
    .stAppDeployButton {display: none;}
    .stButton>button {width: 100%; border-radius: 12px; height: 3.5rem; font-weight: 600;}
    
    /* Chat Bubble */
    .ai-question {
        background-color: var(--secondary-background-color); 
        color: var(--text-color);
        padding: 15px; border-radius: 12px; margin-bottom: 15px;
        border-left: 5px solid #f04e23;
        font-weight: 500;
    }
    
    /* Event Card */
    .event-card-compact {
        border-left: 4px solid #34A853; 
        padding: 12px 15px; 
        background-color: var(--secondary-background-color); 
        color: var(--text-color);
        margin-bottom: 10px; 
        border-radius: 8px;
    }
    
    /* Feedback Area */
    .feedback-area {
        margin-top: 20px; padding-top: 20px;
        border-top: 1px solid var(--secondary-background-color);
    }
    
    /* Check-in Card */
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
            st.session_state.authenticated = True; st.rerun()
        else: st.error("⛔ Incorrect")
    st.stop()

# --- INIT ---
if 'user_location' not in st.session_state: st.session_state.user_location = "Tampa, FL"
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'last_ai_question' not in st.session_state: st.session_state.last_ai_question = None

API_KEY = st.secrets["general"]["groq_api_key"]

# --- HELPER: FORMAT DATE ---
def format_event_dt(iso_str):
    """Converts 2026-02-16T17:30:00 to Mon, Feb 16 @ 5:30 PM"""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%a, %b %d @ %I:%M %p")
    except:
        return iso_str # Fallback

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Tushar Khandare")
    st.caption("Family Administrator")
    with st.expander("🌍 Location", expanded=True):
        st.session_state.user_location = st.text_input("City", value=st.session_state.user_location)
    with st.expander("🧠 Memory", expanded=True):
        st.write(f"Learned Patterns: **{len(load_memory())}**")
        if st.button("Clear Memory"): st.toast("Memory cleared (Placeholder)")
    st.divider()
    if st.button("Log Out"): st.session_state.authenticated = False; st.rerun()

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
            if st.button("✅ Done"): complete_mission_review(pending_mission['id'], True, "Done"); st.toast("Saved!"); st.rerun()
        with c2: 
            if st.button("❌ No"): st.session_state.show_reason = True
        with c3: 
            if st.button("💤"): snooze_mission(pending_mission['id'], 4); st.toast("Snoozed"); st.rerun()
        if st.session_state.get('show_reason'):
            reason = st.text_input("Reason?"); 
            if st.button("Save Reason"): complete_mission_review(pending_mission['id'], False, reason); st.rerun()
    st.divider()

# --- MAIN UI ---
st.title("Family COO")
tab_plan, tab_scan = st.tabs(["📝 Plan", "📸 Scan"])
img_context, user_input = None, ""

with tab_plan:
    if st.session_state.last_ai_question:
        st.markdown(f"<div class='ai-question'>🤖 {st.session_state.last_ai_question}</div>", unsafe_allow_html=True)
    
    ph = "Your Answer..." if st.session_state.last_ai_question else "Mission Brief (e.g. 'Plan Judo')"
    user_input = st.text_area("Input", placeholder=ph, height=100, label_visibility="collapsed")
    
    if st.button("🔄 Reset Context"): 
        st.session_state.chat_history = []
        st.session_state.last_ai_question = None
        st.session_state['result'] = None
        st.session_state['event_list'] = None
        st.session_state['pre_prep'] = None
        st.toast("🧠 Context Cleared"); st.rerun()
        
    upl = st.file_uploader("Upload", type=['jpg','png'], label_visibility="collapsed")
    if upl: img_context = Image.open(upl)

with tab_scan:
    if st.toggle("Activate Camera"):
        cam = st.camera_input("Scan", label_visibility="collapsed")
        if cam: img_context = Image.open(cam)

# --- EXECUTION ---
btn_label = "Reply" if st.session_state.last_ai_question else "🚀 EXECUTE"

if st.button(btn_label, type="primary"):
    with st.spinner("Processing..."):
        memory = load_memory(limit=10)
        cal_data = list_upcoming_events()
        
        raw_response = get_coo_response(
            API_KEY, user_input, memory, cal_data, 
            st.session_state.user_location, img_context, st.session_state.chat_history
        )
        
        json_match = re.search(r'(\{.*\})', raw_response, re.DOTALL)
        try:
            if json_match:
                data = json.loads(json_match.group(1))
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                st.session_state.chat_history.append({"role": "assistant", "content": data.get("text", "")})
                
                if data.get("type") == "question":
                    st.session_state.last_ai_question = data.get("text")
                    st.session_state['result'] = None; st.rerun()
                    
                elif data.get("type") in ["plan", "confirmation"]:
                    st.session_state.last_ai_question = None
                    st.session_state['result'] = data.get("text")
                    st.session_state['pre_prep'] = data.get("pre_prep")
                    st.session_state['event_list'] = data.get("events", [])
            else:
                st.session_state['result'] = raw_response
        except:
            st.error("⚠️ Parsing Error"); st.code(raw_response)

# --- RESULTS DISPLAY ---
if st.session_state.get('result'):
    st.success(st.session_state['result'])
    
    # 1. SHOW PRE-PREP (New Feature)
    if st.session_state.get('pre_prep'):
        st.info(st.session_state['pre_prep'])
    
    # 2. SHOW EVENTS
    events = st.session_state.get('event_list', [])
    if events:
        st.subheader(f"📅 Schedule ({len(events)})")
        for i, event in enumerate(events):
            # Format Date nicely
            pretty_time = format_event_dt(event.get('start_time',''))
            
            st.markdown(f"""
            <div class='event-card-compact'>
                <b>{pretty_time}</b><br>
                <span style='font-size:1.1em'>{event.get('title')}</span>
                <br><span style='font-size:0.9em; opacity:0.8'>📍 {event.get('location', 'No Loc')}</span>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([1, 1])
            with c1:
                calendar_link = add_event_to_calendar(event)
                st.link_button("📅 Add to Calendar", calendar_link)
                log_mission_start(event)
            with c2:
                # MAP LINK FIX
                loc = event.get('location', st.session_state.user_location)
                map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc)}"
                st.link_button("🗺️ Map", map_url)

    # 3. FEEDBACK
    st.markdown("<div class='feedback-area'></div>", unsafe_allow_html=True)
    with st.expander("📝 Feedback"):
        c1, c2 = st.columns([1,4])
        with c1: rate = st.radio("Rate", ["👍", "👎"], label_visibility="collapsed")
        with c2: fb = st.text_input("Correction?")
        if st.button("Save"):
            save_manual_feedback(st.session_state.get('last_input','Plan'), fb, rate)
            st.toast("Updated!")