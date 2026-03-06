import streamlit as st
from datetime import datetime

# 1. Page Configuration
st.set_page_config(
    page_title="Family COO",
    page_icon="📱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom minimal CSS for a cleaner look
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 2rem;}
    
    /* Metrics Cards */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa; border: 1px solid #e9ecef; padding: 5% 10%; border-radius: 10px;
    }
    
    /* Heatmap (Calendar Tab) */
    .heatmap-day { text-align: center; font-weight: 800; color: #64748b; margin-bottom: 10px; }
    .heatmap-empty { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 10px; text-align: center; color: #94a3b8; font-size: 0.8rem; }
    .heatmap-chip { border-radius: 6px; padding: 6px; margin-bottom: 6px; font-size: 0.75rem; font-weight: 700; color: #0f172a; line-height: 1.2; }
    
    /* Timeline (Dashboard) */
    .timeline-container { border-left: 3px solid #e2e8f0; margin-left: 15px; padding-left: 20px; position: relative; margin-bottom: 20px;}
    .timeline-item { position: relative; margin-bottom: 20px; }
    .timeline-dot { position: absolute; left: -27px; top: 4px; width: 11px; height: 11px; border-radius: 50%; background-color: #cbd5e1; border: 2px solid #fff; }
    .timeline-dot.active { background-color: #4f46e5; box-shadow: 0 0 0 3px #e0e7ff; }
    .timeline-dot.past { background-color: #10b981; }
    .timeline-time { font-size: 0.85rem; font-weight: 800; color: #64748b; margin-bottom: 4px;}
    .timeline-content { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    .timeline-title { font-weight: 800; color: #0f172a; margin-bottom: 4px; font-size: 0.95rem; }
    
    /* Memory Pills */
    .memory-pill { display: inline-block; background: #eff6ff; color: #1e3a8a; border: 1px solid #bfdbfe; border-radius: 20px; padding: 5px 12px; font-size: 0.8rem; font-weight: 700; margin: 4px 4px 4px 0; }
    .memory-pill.high { background: #ecfdf5; color: #065f46; border-color: #a7f3d0; }
    .memory-pill.med { background: #fef3c7; color: #92400e; border-color: #fde68a; }
    
    /* Inference Engine Box */
    .inference-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; font-size: 0.9rem; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# App Title
st.title("Family COO")
st.caption(f"Current System Time: {datetime.now().strftime('%A, %B %d, %Y')}")

# Main Navigation using Streamlit Tabs
tab_dash, tab_cal, tab_mem, tab_set = st.tabs([
    "📊 Dashboard", 
    "🗓️ Calendar", 
    "🧠 Context Engine", 
    "⚙️ Settings"
])

# ==========================================
# TAB 1: DASHBOARD (THE EXECUTIVE BRIEFING)
# ==========================================
with tab_dash:
    # 1. The AI Briefing
    st.markdown("### Good Afternoon, Tushar 👋")
    st.info("🤖 **Daily Brief:** You have a busy afternoon with AI engineering tasks. Since you finish at 6:30 PM, I've queued up a Paneer Butter Masala recipe for dinner and verified the Kia Seltos has enough fuel for tomorrow's commute.")
    
    # Top-level metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Pending Actions", "0", "All caught up!", delta_color="normal")
    col2.metric("Remaining Events", "2", "Today")
    col3.metric("Tampa Weather", "78°F", "Sunny")
    
    st.divider()
    
    colA, colB = st.columns([1.5, 1], gap="large")
    
    with colA:
        # 2. Visual Flight Plan (Timeline)
        st.markdown("#### ✈️ Today's Flight Plan")
        st.markdown("""
        <div class="timeline-container">
            <div class="timeline-item">
                <div class="timeline-dot past"></div>
                <div class="timeline-time">10:00 AM</div>
                <div class="timeline-content">
                    <div class="timeline-title">Grocery Run</div>
                    <div style="color: #64748b; font-size: 0.85rem;">📍 Patel Brothers</div>
                </div>
            </div>
            <div class="timeline-item">
                <div class="timeline-dot active"></div>
                <div class="timeline-time">2:00 PM (Current)</div>
                <div class="timeline-content" style="border-left: 4px solid #4f46e5;">
                    <div class="timeline-title">AI Engineering Sync Call</div>
                    <div style="color: #64748b; font-size: 0.85rem;">💻 Google Meet</div>
                </div>
            </div>
            <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-time">5:30 PM</div>
                <div class="timeline-content">
                    <div class="timeline-title">Workout</div>
                    <div style="color: #64748b; font-size: 0.85rem;">📍 EōS Fitness</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with colB:
        # 3. Contextual Quick Actions (Replaces Action Required)
        st.markdown("#### ⚡ Contextual Quick Actions")
        st.markdown("<p style='font-size: 0.85rem; color: #64748b;'>Anticipated needs for your afternoon schedule.</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.button("🚗 Pre-cool Kia Seltos", use_container_width=True, help="Tampa weather is currently 78°F")
            st.button("🏋️ Traffic to EōS Fitness", use_container_width=True, help="Check route before your 5:30 PM workout")
            st.button("🛒 Add to Patel Brothers List", use_container_width=True)
            st.button("🎸 Launch Yousician Lesson", use_container_width=True)
            st.button("📈 Check HDFC SIP Status", use_container_width=True)

# ==========================================
# TAB 2: CALENDAR VIEW (ANALYTICAL HUB)
# ==========================================
with tab_cal:
    st.markdown("### 🗓️ Logistics & Planning Hub")
    st.markdown("<p style='color: #64748b; margin-top: -10px;'>Analyze bandwidth, manage conflicts, and proactively plan your week.</p>", unsafe_allow_html=True)

    # Weekly Bandwidth
    st.markdown("#### 📊 Weekly Bandwidth")
    i1, i2, i3, i4 = st.columns(4)
    i1.metric(label="Events (Next 7 Days)", value="14", delta="↑ 2 vs last week")
    i2.metric(label="Busiest Day", value="Saturday", delta="4 events", delta_color="off")
    i3.metric(label="Free Evenings", value="3 Days", delta="Tue, Thu, Fri", delta_color="normal")
    i4.metric(label="Pending Drafts", value="1", delta="Requires Approval", delta_color="inverse")

    st.divider()

    # Week at a Glance (Heatmap)
    st.markdown("#### 📅 Week at a Glance")
    days = st.columns(7)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    schedule_density = {
        "Mon": [{"title": "Doctor Meeting", "color": "#eff6ff", "border": "#3b82f6"}],
        "Tue": [],
        "Wed": [{"title": "AI Sync Call", "color": "#eff6ff", "border": "#3b82f6"}, {"title": "EōS Fitness", "color": "#fef2f2", "border": "#ef4444"}],
        "Thu": [{"title": "Yousician Practice", "color": "#fef2f2", "border": "#ef4444"}],
        "Fri": [],
        "Sat": [{"title": "Lab Work - Drishti", "color": "#fef2f2", "border": "#ef4444"}, {"title": "Grocery (Patel Bros)", "color": "#ecfdf5", "border": "#10b981"}, {"title": "Swim Class", "color": "#ecfdf5", "border": "#10b981"}],
        "Sun": [{"title": "Ybor City Market", "color": "#fffbeb", "border": "#f59e0b"}]
    }

    for i, day in enumerate(day_names):
        with days[i]:
            st.markdown(f"<div class='heatmap-day'>{day}</div>", unsafe_allow_html=True)
            events = schedule_density[day]
            if not events:
                st.markdown("<div class='heatmap-empty'>Free Day</div>", unsafe_allow_html=True)
            else:
                for ev in events:
                    st.markdown(f"<div class='heatmap-chip' style='background: {ev['color']}; border-left: 4px solid {ev['border']};'>{ev['title']}</div>", unsafe_allow_html=True)

    st.divider()

    # Proactive Planning & Drafts
    colC, colD = st.columns([1, 1], gap="large")
    with colC:
        st.markdown("#### 🪄 Proactive Planning")
        with st.container(border=True):
            st.markdown("💡 **AI Observation:** You have an open evening this Friday. Want to catch a Sci-Fi movie or get Indian takeout?")
            p1, p2 = st.columns(2)
            p1.button("🎬 Suggest Movies", type="primary", use_container_width=True)
            p2.button("🍽️ Suggest Dining", use_container_width=True)

    with colD:
        st.markdown("#### 📥 Drafts & Conflicts")
        with st.container(border=True):
            st.markdown("🟡 **Pending Approval (1)**\n**Hillsborough River State Park Hike**\nSat 10:00 AM - 12:00 PM • Tampa, FL")
            st.error("⚠️ **Conflict:** Overlaps with Drishti's Lab Work (8:00 AM - 10:30 AM).")
            d1, d2 = st.columns(2)
            d1.button("🔁 Auto-Reschedule", use_container_width=True)
            d2.button("Discard Draft", use_container_width=True)

# ==========================================
# TAB 3: CONTEXT ENGINE (MEMORY BANK)
# ==========================================
with tab_mem:
    st.markdown("### 🧠 Context Engine")
    st.markdown("<p style='color: #64748b; margin-top: -10px;'>How the Family COO understands your household.</p>", unsafe_allow_html=True)
    
    col_x, col_y = st.columns([1.5, 1], gap="large")
    
    with col_x:
        # 1. Identity Clusters (Visual Tags)
        st.markdown("#### 🧬 Household Identity Clusters")
        with st.container(border=True):
            st.markdown("**Diet & Dining**")
            st.markdown("<span class='memory-pill high'>🍲 Indian Cuisine (98%)</span> <span class='memory-pill high'>👨‍🍳 Home Cooking (92%)</span> <span class='memory-pill med'>🥡 Takeout Weekend (75%)</span>", unsafe_allow_html=True)
            
            st.markdown("**Media & Interests**")
            st.markdown("<span class='memory-pill high'>💻 Python / AI (99%)</span> <span class='memory-pill high'>🎬 Hollywood Sci-Fi (95%)</span> <span class='memory-pill med'>📺 Hindi Web Series (80%)</span>", unsafe_allow_html=True)
            
            st.markdown("**Logistics & Routine**")
            st.markdown("<span class='memory-pill high'>🚗 Kia Seltos (Active)</span> <span class='memory-pill high'>🏋️ EōS Fitness (M/W/F)</span> <span class='memory-pill'>🎸 Yousician (Learning)</span>", unsafe_allow_html=True)

        # 2. Inference Transparency
        st.markdown("#### ⚙️ How AI Uses This Data")
        st.markdown("""
        <div class="inference-box">
            <strong>Observation:</strong> Open Sunday afternoon block.<br>
            <span style="color: #64748b;">+ <strong>Fact 1:</strong> Family enjoys outdoor activities.</span><br>
            <span style="color: #64748b;">+ <strong>Fact 2:</strong> SunPass is active on the Kia Seltos.</span><br>
            <hr style="margin: 8px 0; border-top: 1px dashed #cbd5e1;">
            🚀 <strong>Inference:</strong> Suggesting a day trip to beaches across the toll bridge.
        </div>
        """, unsafe_allow_html=True)

    with col_y:
        # 3. Active Learning Queue (Gamification)
        st.markdown("#### 🔍 Recently Learned")
        st.markdown("<p style='font-size: 0.85rem; color: #64748b;'>Review the AI's recent deductions to improve accuracy.</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("🧠 **Deduction:** You prefer morning workouts on weekends instead of evenings.")
            l1, l2 = st.columns(2)
            l1.button("✅ Confirm", key="learn_1", use_container_width=True)
            l2.button("❌ Forget", key="learn_2", use_container_width=True)
            
        with st.container(border=True):
            st.markdown("🧠 **Deduction:** You are researching new Lenovo laptops for work.")
            l3, l4 = st.columns(2)
            l3.button("✅ Confirm", key="learn_3", use_container_width=True)
            l4.button("❌ Forget", key="learn_4", use_container_width=True)
            
        st.markdown("#### 📥 Quick Idea Inbox")
        st.text_input("Drop an idea here...", placeholder="e.g., DIY wall decor ideas")
        st.button("Save to Inbox", use_container_width=True)

# ==========================================
# TAB 4: SETTINGS
# ==========================================
with tab_set:
    st.markdown("### ⚙️ Engine Room")
    st.markdown("#### Integrations")
    st.text_input("Groq API Key", value="gsk_************************", type="password")
    st.text_input("Google Calendar OAuth", value="Connected: Valid Token", disabled=True)
    st.divider()
    st.markdown("#### Assistant Behavior")
    st.slider("Proactivity Level (Nudges per day)", 1, 5, 2)
    st.toggle("Allow AI to auto-draft from Idea Inbox", value=True)