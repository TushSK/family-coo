import streamlit as st
from PIL import Image
import json
import urllib.parse
import re
from datetime import datetime
from src.brain import get_coo_response
# FIX: Explicitly importing list_upcoming_events to prevent crash
from src.gcal import add_event_to_calendar, list_upcoming_events
from src.utils import (
    load_memory, 
    log_mission_start, 
    get_pending_review, 
    complete_mission_review, 
    snooze_mission, 
    save_manual_feedback
)

# --- CONFIG ---
st.set_page_config(
    page_title="Family COO", 
    page_icon="🏡", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- CSS STYLING ---
st.markdown("""
    <style>
    /* Hide Streamlit Branding */
    .stAppDeployButton {display: none;}
    
    /* Bigger, Bold Buttons */
    .stButton>button {
        width: 100%; 
        border-radius: 12px; 
        height: 3.5rem; 
        font-weight: 600;
    }
    
    /* AI Chat Bubble Style */
    .ai-question {
        background-color: var(--secondary-background-color); 
        color: var(--text-color);
        padding: 15px; 
        border-radius: 12px; 
        margin-bottom: 15px;
        border-left: 5px solid #f04e23; /* Groq Orange */
        font-weight: 500;
    }
    
    /* Event Card Style */
    .event-card-compact {
        border-left: 4px solid #34A853; /* Google Green */
        padding: 12px 15px; 
        background-color: var(--secondary-background-color); 
        color: var(--text-color);
        margin-bottom: 10px; 
        border-radius: 8px;
    }
    
    /* Feedback & Follow-up Card Style */
    .feedback-card {
        padding: 15px; 
        border-radius: 12px; 
        background-color: var(--secondary-background-color); 
        border-left: 6px solid #FF4B4B; /* Red Alert */
        margin-bottom: 20px;
    }
    
    .feedback-area {
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid var(--secondary-background-color);
    }
    </style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION ---
if 'authenticated' not in st.session_state: 
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><h2 style='text-align: center;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    
    # Centered Login Form
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        pin = st.text_input("Enter PIN", type="password")
        if st.button("Unlock", type="primary"):
            # Check PIN against secrets.toml
            if pin == st.secrets["general"]["app_password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("⛔ Incorrect PIN")
    st.stop()

# --- INIT SESSION STATE ---
if 'user_location' not in st.session_state: st.session_state.user_location = "Tampa, FL"
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'last_ai_question' not in st.session_state: st.session_state.last_ai_question = None
if 'event_list' not in st.session_state: st.session_state.event_list = []

API_KEY = st.secrets["general"]["groq_api_key"]

# --- HELPER FUNCTIONS ---
def format_event_dt(iso_str):
    """Converts ISO date string to readable format (Mon, Feb 16 @ 5:30 PM)"""
    try: 
        return datetime.fromisoformat(iso_str).strftime("%a, %b %d @ %I:%M %p")
    except: 
        return iso_str

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Tushar Khandare")
    st.caption("Family Administrator")
    
    with st.expander("🌍 Location", expanded=True):
        st.session_state.user_location = st.text_input("City", value=st.session_state.user_location)
        
    with st.expander("🧠 Memory", expanded=True):
        st.write(f"Learned Patterns: **{len(load_memory())}**")
        if st.button("Clear Memory"): 
            st.toast("Memory cleared (Placeholder)")
    
    # Calendar Status Indicator
    st.divider()
    calendar_status = list_upcoming_events()
    if "Calendar Access: Not connected" in calendar_status:
         st.caption("📅 Status: 🟡 Offline (Using Link Fallback)")
    else:
         st.caption("📅 Status: 🟢 Online (Reading Live Events)")

    if st.button("Log Out"): 
        st.session_state.authenticated = False
        st.rerun()

# --- CHECK-IN LOGIC (SMART FOLLOW-UP) ---
pending_mission = get_pending_review()

if pending_mission:
    with st.container():
        st.markdown(f"""
        <div class="feedback-card">
            <h3 style="margin:0;">📋 Follow Up</h3>
            <p style="margin:5px 0 10px 0;"><strong>{pending_mission['title']}</strong> ended recently.</p>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1: 
            if st.button("✅ Done"): 
                complete_mission_review(pending_mission['id'], True, "Done")
                st.toast("Saved to Memory!")
                st.rerun()
        with c2: 
            if st.button("❌ No"): 
                st.session_state.show_reason = True
        with c3: 
            if st.button("💤"): 
                snooze_mission(pending_mission['id'], 4)
                st.toast("Snoozed for 4 hours")
                st.rerun()
                
        if st.session_state.get('show_reason'):
            reason = st.text_input("Reason for incomplete?")
            if st.button("Save Reason"): 
                complete_mission_review(pending_mission['id'], False, reason)
                st.rerun()
    st.divider()

# --- MAIN UI TABS ---
st.title("Family COO")
tab_plan, tab_scan = st.tabs(["📝 Plan", "📸 Scan"])
img_context = None
user_input = ""

with tab_plan:
    # Display AI Question if exists
    if st.session_state.last_ai_question:
        st.markdown(f"<div class='ai-question'>🤖 {st.session_state.last_ai_question}</div>", unsafe_allow_html=True)
    
    # Input Area
    ph = "Your Answer..." if st.session_state.last_ai_question else "Mission Brief (e.g. 'Plan Judo Classes')"
    user_input = st.text_area("Input", placeholder=ph, height=100, label_visibility="collapsed")
    
    # Reset Button
    if st.button("🔄 Reset Context"): 
        st.session_state.chat_history = []
        st.session_state.last_ai_question = None
        st.session_state['result'] = None
        st.session_state['event_list'] = []
        st.session_state['pre_prep'] = None
        st.toast("🧠 Context Cleared")
        st.rerun()
        
    # File Upload
    upl = st.file_uploader("Upload Image", type=['jpg','png'], label_visibility="collapsed")
    if upl: 
        img_context = Image.open(upl)

with tab_scan:
    if st.toggle("Activate Camera"):
        cam = st.camera_input("Scan Document", label_visibility="collapsed")
        if cam: 
            img_context = Image.open(cam)

# --- EXECUTION LOGIC ---
btn_label = "Reply" if st.session_state.last_ai_question else "🚀 EXECUTE"

if st.button(btn_label, type="primary"):
    with st.spinner("Analyzing Schedule & Memory..."):
        # Load Context
        memory = load_memory(limit=10)
        
        # 1. READ REAL CALENDAR (For Conflict Detection)
        cal_data = list_upcoming_events()
        
        # 2. GET PENDING EVENTS (From this session)
        pending_events = st.session_state.get('event_list', [])

        # 3. ASK THE BRAIN
        raw_response = get_coo_response(
            API_KEY, 
            user_input, 
            memory, 
            cal_data,
            pending_events,
            st.session_state.user_location, 
            img_context, 
            st.session_state.chat_history
        )
        
        # 4. PARSE RESPONSE
        # Regex to find JSON object inside response text
        json_match = re.search(r'(\{.*\})', raw_response, re.DOTALL)
        
        try:
            if json_match:
                data = json.loads(json_match.group(1))
                
                # Update Chat History
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                st.session_state.chat_history.append({"role": "assistant", "content": data.get("text", "")})
                
                # Handle Response Types
                if data.get("type") == "question":
                    st.session_state.last_ai_question = data.get("text")
                    st.session_state['result'] = None
                    st.rerun()
                    
                elif data.get("type") == "conflict":
                    # Conflict Warning
                    st.session_state.last_ai_question = None
                    st.session_state['result'] = f"⚠️ {data.get('text')}"
                    st.session_state['pre_prep'] = None
                    st.session_state['event_list'] = [] # Clear events on conflict
                    
                elif data.get("type") in ["plan", "confirmation", "suggestion"]:
                    # Success / Plan
                    st.session_state.last_ai_question = None
                    st.session_state['result'] = data.get("text")
                    st.session_state['pre_prep'] = data.get("pre_prep")
                    st.session_state['event_list'] = data.get("events", [])
            else:
                # Fallback for plain text response
                st.session_state['result'] = raw_response
                
        except json.JSONDecodeError:
            st.error("⚠️ System Error: Could not parse AI response.")
            with st.expander("Debug Raw Output"):
                st.code(raw_response)

# --- RESULTS DISPLAY ---
if st.session_state.get('result'):
    # Warning for Conflicts, Success for Plans
    if "⚠️" in str(st.session_state['result']):
        st.warning(st.session_state['result'])
    else:
        st.success(st.session_state['result'])
    
    # Show Pre-Prep Info
    if st.session_state.get('pre_prep'):
        st.info(st.session_state['pre_prep'])
    
    # Show Scheduled Events
    events = st.session_state.get('event_list', [])
    if events:
        st.subheader(f"📅 Schedule ({len(events)})")
        
        for i, event in enumerate(events):
            pretty_time = format_event_dt(event.get('start_time',''))
            
            # Event Card
            st.markdown(f"""
            <div class='event-card-compact'>
                <b>{pretty_time}</b><br>
                <span style='font-size:1.1em'>{event.get('title')}</span>
                <br><span style='font-size:0.9em; opacity:0.8'>📍 {event.get('location', 'No Loc')}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Action Buttons
            c1, c2 = st.columns([1, 1])
            with c1:
                # Add to Calendar (API or Link Fallback)
                if st.button("📅 Add to Calendar", key=f"add_{i}"):
                    success, response = add_event_to_calendar(event)
                    if success:
                        st.toast(response) # API Success
                        st.success(response)
                    else:
                        # Link Fallback
                        st.error("Authentication incomplete. Use link:")
                        st.markdown(f"[🔗 Click to Open Calendar]({response})")
                    
                    # Log mission start when adding
                    log_mission_start(event)
                
            with c2:
                # Map Link
                loc = event.get('location', st.session_state.user_location)
                map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc)}"
                st.link_button("🗺️ Map", map_url)

    # Feedback Section
    st.markdown("<div class='feedback-area'></div>", unsafe_allow_html=True)
    with st.expander("📝 Feedback & Corrections"):
        c1, c2 = st.columns([1, 4])
        with c1: 
            rate = st.radio("Rate", ["👍", "👎"], label_visibility="collapsed")
        with c2: 
            fb = st.text_input("Correction?")
            
        if st.button("Save Feedback"):
            save_manual_feedback(st.session_state.get('last_input', 'Plan'), fb, rate)
            st.toast("Feedback Saved!")