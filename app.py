import streamlit as st
from PIL import Image
import json
import re
import urllib.parse
import textwrap

from datetime import datetime, timedelta

from src.brain import get_coo_response
from src.gcal import add_event_to_calendar, get_upcoming_events_list, delete_event
from src.utils import (
    load_memory,
    log_mission_start,
    get_pending_review,
    complete_mission_review,
    snooze_mission,
    save_manual_feedback,
)

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="Family COO", page_icon="🏡", layout="wide", initial_sidebar_state="expanded")

# -----------------------------
# CSS
# -----------------------------
st.markdown(
    """
<style>
/* Hide Streamlit chrome */
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}
.stAppDeployButton {display:none;}

/* Page width */
.block-container {padding-top: 1.0rem; padding-bottom: 2rem; max-width: 1240px;}

/* Divider */
hr.soft{
  border:none;
  height:1px;
  background: rgba(125,125,125,0.18);
  margin: 14px 0;
}

/* Brand */
.brand-wrap{display:flex; flex-direction:column; gap:6px;}
.brand-title{
  font-size: 1.45rem;
  font-weight: 1100;
  margin:0;
  display:flex;
  gap:10px;
  align-items:center;
}
.brand-tag{
  font-size: 1.05rem;
  opacity: 0.70;
  margin: 0;
  line-height: 1.35rem;
}

/* KPI Cards */
.kpi-card{
  background: #fff;
  border-radius: 16px;
  padding: 12px 14px;
  border: 1px solid rgba(125,125,125,0.16);
  box-shadow: 0 4px 10px rgba(0,0,0,0.05);
  min-height: 84px;
  display:flex;
  flex-direction:column;
  justify-content:center;
}

.kpi-title{
  font-size: 0.78rem;
  font-weight: 1000;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  opacity: 0.62;
  margin:0;
}

.kpi-value{
  font-size: 1.55rem;
  font-weight: 1100;
  margin-top: 6px;
  line-height: 1.1;
}

/* Color accents */
.kpi-blue{ border-left: 7px solid #29B5E8; }
.kpi-green{ border-left: 7px solid #34A853; }
.kpi-yellow{ border-left: 7px solid #fbbc04; }
.kpi-orange{ border-left: 7px solid #f04e23; }

/* Centered Date card text like your screenshot */
.kpi-date{ text-align:center; }

/* Button polish (optional, keeps your UI consistent) */
.stButton>button{
  width: 100%;
  border-radius: 12px;
  height: 3.0rem;
  font-weight: 950;
}
a[role="button"]{
  border-radius: 12px !important;
  height: 3.0rem !important;
  display:flex !important;
  align-items:center !important;
  justify-content:center !important;
  font-weight: 950 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# AUTH
# -----------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><h2 style='text-align:center;'>🏡 Family COO</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; opacity:0.75;'>A tiny chief-of-staff for your home life ✨</p>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        pin = st.text_input("Enter PIN", type="password")
        if st.button("Unlock", type="primary"):
            if pin == st.secrets["general"]["app_password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("⛔ Incorrect PIN")
    st.stop()

API_KEY = st.secrets["general"]["groq_api_key"]

# -----------------------------
# STATE
# -----------------------------
st.session_state.setdefault("user_location", "Tampa, FL")
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("last_ai_question", None)
st.session_state.setdefault("proposed_events", [])
st.session_state.setdefault("pending_events", [])
st.session_state.setdefault("result", None)
st.session_state.setdefault("pre_prep", "")
st.session_state.setdefault("show_reason_for_key", None)
st.session_state.setdefault("camera_on", False)
st.session_state.setdefault("_show_preview", False)

# -----------------------------
# HELPERS
# -----------------------------
def safe_parse_json(raw: str):
    if not raw:
        return None
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    m = re.search(r"(\{.*\})", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def format_event_dt(iso_str: str) -> str:
    try:
        return datetime.fromisoformat(iso_str).strftime("%a, %b %d @ %I:%M %p")
    except Exception:
        return iso_str or ""


def to_dt(iso_str: str):
    try:
        return datetime.fromisoformat(iso_str)
    except Exception:
        return None


def within_minutes(a: datetime, b: datetime, mins: int = 15) -> bool:
    if not a or not b:
        return False
    return abs((a - b).total_seconds()) <= mins * 60


def is_same_event(proposed: dict, cal_ev: dict) -> bool:
    p_title = (proposed.get("title") or "").strip().lower()
    c_title = (cal_ev.get("title") or "").strip().lower()

    if not p_title or not c_title:
        return False

    title_ok = (p_title == c_title) or (p_title in c_title) or (c_title in p_title)

    p_start = to_dt(proposed.get("start_time", ""))
    c_start = None
    if cal_ev.get("start_raw") and "T" in cal_ev["start_raw"]:
        try:
            c_start = datetime.fromisoformat(cal_ev["start_raw"].replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            c_start = None

    if p_start and getattr(p_start, "tzinfo", None):
        p_start = p_start.replace(tzinfo=None)

    return title_ok and within_minutes(p_start, c_start, 15)


def load_feedback_rows():
    return load_memory(limit=500) or []


def load_mission_rows():
    try:
        with open("memory/mission_log.json", "r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception:
        return []


def count_missed_no_response(missions: list) -> int:
    now = datetime.now()
    missed = 0
    for m in missions:
        if m.get("status") != "pending":
            continue
        end_str = m.get("end_time")
        if not end_str:
            continue
        try:
            end_dt = datetime.fromisoformat(end_str)
        except Exception:
            continue
        if end_dt <= (now - timedelta(hours=4)):
            su = m.get("snoozed_until")
            if su:
                try:
                    if datetime.fromisoformat(su) > now:
                        continue
                except Exception:
                    pass
            missed += 1
    return missed


def calendar_context_string(real_calendar_events):
    if not real_calendar_events:
        return "Calendar not connected."

    human = "UPCOMING SCHEDULE (Next 7 Days):\n" + "\n".join(
        [f"- {e['start_friendly']} → {e.get('end_friendly','')}: {e['title']}" for e in real_calendar_events]
    )
    struct = "\n\nSTRUCTURED_EVENTS_JSON:\n" + json.dumps(
        [
            {
                "title": e.get("title"),
                "start": e.get("start_raw"),
                "end": e.get("end_raw"),
                "location": e.get("location", ""),
            }
            for e in real_calendar_events
        ],
        ensure_ascii=False,
    )
    return human + struct


def smart_prep_tips(user_text: str, events: list) -> str:
    """
    Adds a few helpful tips based on the task request (simple, reliable, no hallucinations).
    """
    base = (st.session_state.get("pre_prep") or "").strip()
    text = (user_text or "").lower()
    title = ((events[0].get("title") if events else "") or "").lower()
    blob = f"{text} {title}"

    tips = []

    # Universal scheduling tips
    tips.append("Confirm the exact time window.")
    tips.append("Add a 10–15 min buffer for travel or delays.")

    # Contextual tips
    if any(k in blob for k in ["doctor", "clinic", "diagnostic", "hospital", "appointment", "visa", "dropbox"]):
        tips.append("Carry ID + any required documents.")
        tips.append("Reach 10 minutes early for check-in.")
    elif any(k in blob for k in ["movie", "cinema", "theatre", "theater"]):
        tips.append("Book seats early to avoid last-minute rush.")
        tips.append("Carry water/snack if needed.")
    elif any(k in blob for k in ["beach", "park", "outdoor", "temple", "trip", "travel"]):
        tips.append("Pack water and a light snack.")
        tips.append("Check weather + parking availability.")
    elif any(k in blob for k in ["breakfast", "lunch", "dinner", "restaurant", "food"]):
        tips.append("Check peak hours and plan a reservation if needed.")
        tips.append("Carry a backup option nearby in case it’s crowded.")
    elif any(k in blob for k in ["gym", "workout", "volleyball", "exercise"]):
        tips.append("Keep a small towel and water bottle ready.")
        tips.append("Warm up 5 minutes to avoid strain.")

    # Keep it short (few tips)
    tips = tips[:4]

    combined = []
    if base:
        combined.append(base)
    combined.append(" • ".join(tips))
    return "\n".join([c for c in combined if c]).strip()


# -----------------------------
# CALENDAR + COUNTS
# -----------------------------
real_calendar_events = get_upcoming_events_list(days=7)
calendar_online = real_calendar_events is not None
calendar_status = "🟢 Online" if calendar_online else "🟡 Offline (Link Mode)"
upcoming_count = len(real_calendar_events) if real_calendar_events else 0

feedback_rows = load_feedback_rows()
completed_count = len([x for x in feedback_rows if x.get("rating") == "👍"])
missed_pending = count_missed_no_response(load_mission_rows())
missed_with_reason = len([x for x in feedback_rows if x.get("rating") == "👎"])
missed_total = missed_pending + missed_with_reason
learnings_count = len(feedback_rows)

# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    st.markdown("### 👤 Profile")
    st.caption("Family Administrator")
    st.session_state.user_location = st.text_input("📍 Location", value=st.session_state.user_location)

    st.markdown("<hr class='soft'>", unsafe_allow_html=True)
    st.markdown("### 📅 Calendar")
    st.caption(f"Status: {calendar_status}")
    st.caption(f"Upcoming (7 days): {upcoming_count}")

    st.markdown("<hr class='soft'>", unsafe_allow_html=True)
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# -----------------------------
# TOP BAR
# -----------------------------
# ===== HEADER RENDER (matches screenshot) =====
today_label = datetime.now().strftime("%b %d")
tagline = "Plan • Avoid conflicts • One-click calendar"

# Left brand + right cards row
h_left, h_right = st.columns([2.2, 5.8], vertical_alignment="top")

with h_left:
    st.markdown(
        f"""
        <div class="brand-wrap">
          <div class="brand-title">🏡 <span>Family COO</span></div>
          <div class="brand-tag">{tagline}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with h_right:
    c_date, c_up, c_comp, c_miss, c_learn = st.columns(5, gap="small")

    with c_date:
        st.markdown(
            f"""
            <div class="kpi-card kpi-blue kpi-date">
              <div class="kpi-title">Date</div>
              <div class="kpi-value">{today_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_up:
        st.markdown(
            f"""
            <div class="kpi-card kpi-blue">
              <div class="kpi-title">Upcoming</div>
              <div class="kpi-value">{upcoming_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_comp:
        st.markdown(
            f"""
            <div class="kpi-card kpi-green">
              <div class="kpi-title">Completed</div>
              <div class="kpi-value">{completed_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_miss:
        st.markdown(
            f"""
            <div class="kpi-card kpi-yellow">
              <div class="kpi-title">Missed / No Response</div>
              <div class="kpi-value">{missed_total}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_learn:
        st.markdown(
            f"""
            <div class="kpi-card kpi-orange">
              <div class="kpi-title">Learnings</div>
              <div class="kpi-value">{learnings_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<hr class='soft'>", unsafe_allow_html=True)
# -----------------------------
# FOLLOW-UP (keep this — it’s your smart loop)
# -----------------------------
pending_review = get_pending_review()
if pending_review:
    st.markdown(
        f"""
        <div class="card danger">
          <h3>📋 Follow-up</h3>
          <p>Did you finish <b>{pending_review.get('title','')}</b>?</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        if st.button("✅ Done", key="fu_done"):
            complete_mission_review(pending_review["id"], True, "Done")
            st.toast("Saved.")
            st.rerun()
    with c2:
        if st.button("❌ Not done", key="fu_notdone"):
            st.session_state.show_reason_for_key = f"fu:{pending_review['id']}"
    with c3:
        if st.button("💤 Snooze", key="fu_snooze"):
            snooze_mission(pending_review["id"], hours=4)
            st.toast("Snoozed.")
            st.rerun()

    if st.session_state.show_reason_for_key == f"fu:{pending_review['id']}":
        reason = st.text_input("Quick reason (1 line)", key="fu_reason")
        if st.button("Save reason", key="fu_reason_save"):
            complete_mission_review(pending_review["id"], False, reason or "No reason")
            st.session_state.show_reason_for_key = None
            st.rerun()

    st.markdown("<hr class='soft'>", unsafe_allow_html=True)

# -----------------------------
# INPUT / CAMERA / UPLOAD
# -----------------------------
if st.session_state.last_ai_question:
    st.markdown(
        f"""
        <div class="card orange">
          <h3>🤖 Quick question</h3>
          <p>{st.session_state.last_ai_question}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    "<div class='card info'><h3>📝 What do you want to plan?</h3><p class='small'>Try: “What does my schedule look like next week?” or “Plan movie this weekend at 11 AM”.</p></div>",
    unsafe_allow_html=True,
)

ph = "Your answer..." if st.session_state.last_ai_question else "Example: Plan movie this weekend at 11 AM"
user_input = st.text_area("Input", placeholder=ph, height=120, label_visibility="collapsed")

r1, r2, r3, r4 = st.columns([1.1, 1.1, 1.1, 3.7])
with r1:
    if st.button("🔄 Reset", key="reset_all"):
        st.session_state.chat_history = []
        st.session_state.last_ai_question = None
        st.session_state.result = None
        st.session_state.pre_prep = ""
        st.session_state.proposed_events = []
        st.session_state.camera_on = False
        st.session_state.show_reason_for_key = None
        st.session_state._show_preview = False
        st.rerun()

with r2:
    if st.button("📅 Preview", key="preview"):
        st.session_state._show_preview = not st.session_state.get("_show_preview", False)

with r3:
    if st.button("📷 Camera", key="camera_btn"):
        st.session_state.camera_on = not st.session_state.camera_on

with r4:
    upl = st.file_uploader("Upload image", type=["jpg", "png", "jpeg"], label_visibility="collapsed")
    upload_img = Image.open(upl) if upl else None

camera_img = None
if st.session_state.camera_on:
    cam = st.camera_input("Take a photo", label_visibility="collapsed")
    if cam:
        camera_img = Image.open(cam)

img_context = camera_img or upload_img

if st.session_state.get("_show_preview"):
    st.markdown("<div class='card'><h3>📅 Calendar Preview (Next 7 days)</h3></div>", unsafe_allow_html=True)
    if real_calendar_events:
        for e in real_calendar_events:
            st.markdown(f"- **{e['start_friendly']}** → {e.get('end_friendly','')}: {e['title']}")
    else:
        st.warning("Calendar offline or no upcoming events.")

# -----------------------------
# EXECUTE
# -----------------------------
btn = "Reply" if st.session_state.last_ai_question else "🚀 Execute"
if st.button(btn, type="primary", key="execute"):
    with st.spinner("Thinking…"):
        memory = load_memory(limit=10)
        cal_str = calendar_context_string(real_calendar_events)

        pending_events = st.session_state.get("pending_events", [])

        raw = get_coo_response(
            API_KEY,
            user_input,
            memory,
            cal_str,
            pending_events,
            st.session_state.user_location,
            img_context,
            st.session_state.chat_history,
        )

        data = safe_parse_json(raw)
        if not data:
            st.session_state.last_ai_question = None
            st.session_state.result = "⚠️ I couldn’t parse the response. Try with Day + Time + Location."
            st.session_state.pre_prep = ""
            st.session_state.proposed_events = []
        else:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            st.session_state.chat_history.append({"role": "assistant", "content": data.get("text", "")})

            rtype = (data.get("type") or "").lower()
            if rtype == "question":
                st.session_state.last_ai_question = data.get("text", "")
                st.session_state.result = None
                st.session_state.pre_prep = ""
                st.session_state.proposed_events = []
                st.rerun()
            else:
                st.session_state.last_ai_question = None
                st.session_state.result = data.get("text", "")
                st.session_state.pre_prep = data.get("pre_prep", "") or ""
                st.session_state.proposed_events = data.get("events", []) or []

# -----------------------------
# RESULT + PRE-PREP (single combined card)
# -----------------------------
if st.session_state.get("result"):
    txt = str(st.session_state.result or "")
    proposed = st.session_state.get("proposed_events", []) or []
    merged_prep = smart_prep_tips(user_input, proposed)

    style = "warn" if (txt.startswith("⚠️") or "conflict" in txt.lower()) else "ok"
    st.markdown(
        f"""
        <div class="card {style}">
          <h3>✅ Result</h3>
          <p>{txt}</p>
          <hr class="soft">
          <h3>🧰 Pre-prep</h3>
          <p style="white-space:pre-wrap;">{merged_prep if merged_prep else "—"}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------
    # SCHEDULE SPLIT: Suggested vs Already-in-Calendar
    # -----------------------------
    already = []
    suggested = []

    if real_calendar_events:
        for ev in proposed:
            matched = None
            for cal_ev in real_calendar_events:
                if is_same_event(ev, cal_ev):
                    matched = cal_ev
                    break
            if matched:
                ev2 = dict(ev)
                ev2["_calendar_id"] = matched.get("id")
                already.append(ev2)
            else:
                suggested.append(ev)
    else:
        suggested = proposed

    st.markdown("<hr class='soft'>", unsafe_allow_html=True)

    # If any already exists, show two sections (not tabs)
    if suggested:
        st.markdown(
            f"<div class='card'><h3>🗓️ Suggested Schedule ({len(suggested)})</h3><p class='small'>Clean actions only (no “Not completed” here since it’s not in calendar yet).</p></div>",
            unsafe_allow_html=True,
        )

        for i, ev in enumerate(suggested):
            pretty = format_event_dt(ev.get("start_time", ""))
            st.markdown(
                f"""
                <div class="event-card">
                  <div class="event-title">{ev.get('title','')}</div>
                  <div class="event-time">🕒 {pretty}</div>
                  <div class="event-loc">📍 {ev.get('location','No location')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Aligned buttons
            b1, b2, b3 = st.columns([1.3, 1.1, 1.4])
            with b1:
                if st.button("📅 Add to Calendar", key=f"add_{i}"):
                    ev["pre_prep"] = smart_prep_tips(user_input, [ev])
                    ok, msg, event_id = add_event_to_calendar(ev)
                    if ok:
                        st.success(msg)
                        st.session_state.pending_events.append(
                            {
                                "title": ev.get("title"),
                                "start_time": ev.get("start_time"),
                                "end_time": ev.get("end_time"),
                                "location": ev.get("location", ""),
                            }
                        )
                        ev["_calendar_id"] = event_id
                        log_mission_start(ev)
                    else:
                        st.warning("Link Mode:")
                        st.markdown(f"[🔗 Open Calendar Link]({msg})")
            with b2:
                if st.button("✅ Completed?", key=f"comp_{i}"):
                    # Records learning only (not deleting since not in calendar yet)
                    save_manual_feedback(ev.get("title", "Event"), "Completed", "👍")
                    st.toast("Marked as completed.")
            with b3:
                st.link_button(
                    "📍 Location",
                    f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(ev.get('location',''))}",
                )

    if already:
        st.markdown(
            f"<div class='card'><h3>📌 Already in Calendar ({len(already)})</h3><p class='small'>Here you can mark Completed (delete from calendar) or give a quick “Not completed” reason.</p></div>",
            unsafe_allow_html=True,
        )

        for j, ev in enumerate(already):
            pretty = format_event_dt(ev.get("start_time", ""))
            st.markdown(
                f"""
                <div class="event-card">
                  <div class="event-title">{ev.get('title','')}</div>
                  <div class="event-time">🕒 {pretty}</div>
                  <div class="event-loc">📍 {ev.get('location','No location')}</div>
                  <div class="small">✅ Already in Calendar</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Aligned buttons
            d1, d2, d3 = st.columns([1.3, 1.2, 1.4])
            with d1:
                if st.button("✅ Completed? (Delete)", key=f"done_del_{j}"):
                    cal_id = ev.get("_calendar_id")
                    if cal_id:
                        ok, msg = delete_event(cal_id)
                        if ok:
                            st.success("Completed ✅ and removed from calendar.")
                            save_manual_feedback(ev.get("title", "Event"), "Completed and deleted from calendar", "👍")
                        else:
                            st.error(msg)
                    else:
                        st.warning("No calendar id found to delete.")

            with d2:
                if st.button("❌ Not completed", key=f"acal_not_{j}"):
                    st.session_state.show_reason_for_key = f"acal_not:{j}"

            with d3:
                st.link_button(
                    "📍 Location",
                    f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(ev.get('location',''))}",
                )

            if st.session_state.show_reason_for_key == f"acal_not:{j}":
                reason = st.text_input("Why not completed? (short)", key=f"acal_reason_{j}")
                if st.button("Save reason", key=f"acal_reason_save_{j}"):
                    save_manual_feedback(ev.get("title", "Event"), reason or "No response", "👎")
                    st.toast("Recorded.")
                    st.session_state.show_reason_for_key = None
                    st.rerun()
