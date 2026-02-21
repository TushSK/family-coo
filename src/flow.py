import json
import re
from datetime import datetime, timedelta
import streamlit as st
from PIL import Image

from dateutil import parser as dtparser

from src.utils import (
    get_pending_review,
    snooze_mission,
    complete_mission_review,
)


# --- INTERNAL IMPORTS ---
from src.brain import get_coo_response
from src.gcal import (
    get_upcoming_events_list,
    get_events_range,
    add_event_to_calendar,
    delete_event,
    start_device_flow,
    poll_device_flow,
    save_token_from_device_flow
)
from src.utils import (
    load_memory,
    log_mission_start,
    upsert_calendar_missions,
    load_feedback_rows,
    get_missed_count,
    save_manual_feedback,
    # ✅ used by Check-in Required
    get_pending_review,
    snooze_mission,
    complete_mission_review,
    calculate_reliability_score
)

# -----------------------
# 1. SESSION STATE
# -----------------------

def _get_query_user() -> str:
    """Read persistent user from URL query params (survives Streamlit Cloud refresh)."""
    try:
        val = st.query_params.get("user", "")
        if isinstance(val, list):
            val = val[0] if val else ""
        return (val or "").strip().lower()
    except Exception:
        try:
            qp = st.experimental_get_query_params()
            val = (qp.get("user") or [""])[0]
            return (val or "").strip().lower()
        except Exception:
            return ""


def _set_query_user(email: str) -> None:
    """Persist user email in URL so backend can load tokens silently after refresh."""
    email = (email or "").strip().lower()
    if not email:
        return
    try:
        st.query_params["user"] = email
    except Exception:
        try:
            st.experimental_set_query_params(user=email)
        except Exception:
            pass


def _clear_query_user() -> None:
    """Remove persisted user from URL (optional)."""
    try:
        if "user" in st.query_params:
            del st.query_params["user"]
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


def init_state():
    defaults = {
        "user_location": "Tampa, FL",
        "user_email": "",
        "calendar_online": False,
        "calendar_events": None,
        "calendar_events_all": None,
        "pending_events": [],
        "chat_history": [],
        "last_result_type": None,
        "last_result_text": "",
        "device_flow": None,
        "plan_text": "",
        "authenticated": False,
        "checkin_feedback_open": False,
        "checkin_feedback_text": "",
        "show_camera": False
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

    # Restore user_email from URL on fresh sessions (Streamlit Cloud refresh)
    if not st.session_state.get("user_email"):
        q_user = _get_query_user()
        if q_user:
            st.session_state.user_email = q_user


# -----------------------
# 2. LOGIC
# -----------------------
def execute_plan_logic(user_text: str, image_obj=None):
    import json
    import re
    import streamlit as st

    memory = load_memory(limit=10)
    cal_events = st.session_state.get("calendar_events_all") or st.session_state.get("calendar_events")

    if cal_events:
        lines = [f"- {e.get('start_friendly','')}: {e.get('title','')}" for e in cal_events]
        human = "SCHEDULE (Next 7 Days):\n" + "\n".join(lines)
        structured = [{"title": e.get("title"), "start": e.get("start_raw"), "end": e.get("end_raw")} for e in cal_events]
        cal_str = human + "\nJSON:\n" + json.dumps(structured)
    else:
        cal_str = "Calendar Empty or Offline."

    # ------------------------------------------------------------
    # STRICT drafting gate:
    # Draft ONLY when user explicitly uses schedule/add/plan (whole words).
    # ------------------------------------------------------------
    def _should_create_draft(text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False

        # Never draft for questions
        if "?" in t:
            return False

        question_prefixes = (
            "what", "whats", "what's", "when", "show", "list", "tell me",
            "do i", "did i", "am i", "any", "my upcoming", "upcoming schedule",
            "next event", "next events",
        )
        if any(t.startswith(p) for p in question_prefixes):
            return False

        # Strict: only these explicit action words
        explicit_actions = ("schedule", "add", "plan")
        return any(re.search(rf"\\b{w}\\b", t) for w in explicit_actions)

    schedule_intent = _should_create_draft(user_text)

    try:
        api_key = st.secrets["general"]["groq_api_key"]
    except Exception:
        add_msg("assistant", "⛔ Error: Missing 'groq_api_key' in secrets.toml.")
        return

    raw = get_coo_response(
        api_key=api_key,
        user_request=user_text,
        memory=memory,
        calendar_data=cal_str,
        chat_history=st.session_state.chat_history,
        image_obj=image_obj,
        current_location=st.session_state.user_location
    )

    data = _extract_json(raw)
    if not data:
        add_msg("assistant", "⚠️ Error: I couldn't process that. Please try again.")
        return

    resp_text = data.get("text", "")

    if user_text:
        add_msg("user", user_text)
    elif image_obj:
        add_msg("user", "📷 [Scanned Image]")

    add_msg("assistant", resp_text)

    # ✅ Only draft when strict scheduling intent is detected
    new_events = data.get("events", [])
    if schedule_intent and new_events:
        st.session_state.pending_events = new_events
    # else: ignore events (prevents Drafting from popping up on questions)


def _extract_json(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except:
        m = re.search(r"(\{.*\})", raw, re.DOTALL)
        return json.loads(m.group(1)) if m else None

def add_msg(role, content):
    st.session_state.chat_history.append({"role": role, "content": content})
    if len(st.session_state.chat_history) > 15:
        st.session_state.chat_history = st.session_state.chat_history[-15:]

# -----------------------
# 3. CALLBACKS
# -----------------------
def submit_plan():
    text = st.session_state.get("plan_text", "").strip()
    cam_val = st.session_state.get("cam_input")

    img = None
    if st.session_state.get("show_camera") and cam_val:
        try:
            img = Image.open(cam_val)
        except:
            pass

    if not text and not img:
        return

    execute_plan_logic(text, image_obj=img)
    st.session_state.plan_text = ""

def toggle_camera():
    st.session_state.show_camera = not st.session_state.get("show_camera", False)

# -----------------------
# 4. ACTIONS
# -----------------------
def refresh_calendar(force_email=None):
    uid = (force_email or st.session_state.get("user_email") or "").strip().lower()
    if not uid:
        return

    upcoming = get_upcoming_events_list(user_id=uid, days=7)
    if upcoming is not None:
        st.session_state.calendar_events = upcoming
        st.session_state.calendar_online = True

        now = datetime.now().astimezone()
        try:
            full = get_events_range(uid, now, now + timedelta(days=7))
            st.session_state.calendar_events_all = full
            upsert_calendar_missions(full)
        except:
            st.session_state.calendar_events_all = upcoming
    else:
        st.session_state.calendar_online = False

def add_to_calendar(ev):
    uid = st.session_state.get("user_email", "").strip().lower()
    if not uid:
        add_msg("assistant", "⚠️ Connect your calendar first!")
        return

    ok, msg, eid = add_event_to_calendar(uid, ev)
    if ok:
        log_mission_start(ev)
        st.session_state.pending_events = [x for x in st.session_state.pending_events if x != ev]
        refresh_calendar()
        add_msg("assistant", f"✅ Added '{ev.get('title')}' to calendar.")
    else:
        add_msg("assistant", f"⛔ Failed: {msg}")

def reject_draft(ev):
    st.session_state.pending_events = [x for x in st.session_state.pending_events if x != ev]
    st.toast(f"Discarded '{ev.get('title')}'")

def mark_missed(title, reason):
    save_manual_feedback(title, reason, "👎")
    st.toast("Feedback saved.")

# -----------------------
# 5. AUTH
# -----------------------
def begin_reconnect(email):
    if email:
        st.session_state.user_email = email
        _set_query_user(email)   # ✅ persist across refresh
    st.session_state.device_flow = start_device_flow()


def clear_reconnect():
    st.session_state.device_flow = None
    st.session_state.calendar_online = False
    st.session_state.calendar_events = None
    st.session_state.calendar_events_all = None
    st.session_state.pending_events = []
    st.session_state.user_email = ""
    _clear_query_user()


def complete_reconnect():
    flow = st.session_state.get("device_flow")
    if not flow:
        return False, "No flow."
    token = poll_device_flow(flow["device_code"], int(flow.get("interval", 5)))
    if token.get("error"):
        return False, token["error"]

    uid = st.session_state.get("user_email", "").strip().lower()
    ok, msg = save_token_from_device_flow(uid, token)
    if ok:
        st.session_state.device_flow = None
        _set_query_user(uid)  # ✅ persist across refresh
        refresh_calendar(force_email=uid)
        return True, msg
    return False, msg

from datetime import datetime
import streamlit as st

from src.utils import load_feedback_rows, get_missed_count, calculate_reliability_score

def compute_kpis(user_name: str = "Tushar"):
    """
    Returns a dict consumed by render_metrics().
    """
    now = datetime.now()
    hour = now.hour
    greeting = "Good Morning" if hour < 12 else ("Good Afternoon" if hour < 18 else "Good Evening")

    # Calendar (weekly count) - keep it simple: if you already store upcoming 7 days in session, use that
    events_week = st.session_state.get("calendar_events_week")
    if events_week is None:
        # fallback to whatever list you already store
        events_week = st.session_state.get("calendar_events") or []

    try:
        rows = load_feedback_rows()
    except Exception:
        rows = []

    try:
        missed = int(get_missed_count())
    except Exception:
        missed = 0

    # NEW: Reliability KPI
    try:
        reliability = int(calculate_reliability_score())
    except Exception:
        reliability = 0

    return {
        "name": user_name,
        "greeting": greeting,
        "header_date": now.strftime("%b %d, %Y"),
        "date_label": now.strftime("%b %d"),
        "upcoming_week": len(events_week),
        "learnings": len(rows),
        "missed": missed,
        "reliability": reliability,
    }

# -----------------------
# 6. CHECK-IN REQUIRED (front page)
# -----------------------
def get_checkin_context():
    """
    Returns (mission, mode)
      mode = "ask"   -> show Yes/No/Snooze
      mode = "action"-> user said No; show Reschedule/Delete
    """
    pending_action = st.session_state.get("checkin_pending_action")
    if pending_action:
        return pending_action, "action"

    try:
        m = get_pending_review()
        return (m, "ask") if m else (None, "ask")
    except Exception:
        return None, "ask"


def checkin_yes():
    mission, mode = get_checkin_context()
    if not mission:
        return

    note = (st.session_state.get("checkin_reason") or "").strip() or "Completed"
    complete_mission_review(mission["id"], True, note)

    st.session_state.checkin_reason = ""
    st.session_state.checkin_reschedule_when = ""
    st.session_state.checkin_pending_action = None
    add_msg("assistant", f"✅ Noted: '{mission.get('title','Item')}' completed.")

def checkin_yes_learning():
    """
    YES => mark completed + add to learnings (memory file).
    """
    from src.utils import save_manual_feedback
    mission, _mode = get_checkin_context()
    if not mission:
        return

    note = "Completed"
    complete_mission_review(mission["id"], True, note)

    # ✅ add to learning
    try:
        save_manual_feedback(mission.get("title","Item"), "Completed as planned", "👍")
    except Exception:
        pass

    st.session_state.checkin_pending_action = None
    st.session_state.checkin_reason = ""
    st.session_state.checkin_reschedule_when = ""
    add_msg("assistant", f"✅ Noted: '{mission.get('title','Item')}' completed.")



def checkin_no():
    mission, mode = get_checkin_context()
    if not mission:
        return

    # Open feedback mini-panel (instead of action-mode reschedule/delete)
    st.session_state.checkin_pending_action = None
    st.session_state.checkin_feedback_open = True
    st.session_state.checkin_feedback_text = ""

    add_msg("assistant", "📝 Quick note — what got in the way?")

def checkin_no_with_feedback(feedback: str = ""):
    """
    NO => ask feedback in UI, then call this:
      - mark missed
      - add feedback to learnings (memory file)
    """
    from src.utils import save_manual_feedback
    mission, _mode = get_checkin_context()
    if not mission:
        return

    fb = (feedback or "").strip() or "Missed"
    complete_mission_review(mission["id"], False, fb)

    # ✅ add to learning
    try:
        save_manual_feedback(mission.get("title","Item"), fb, "👎")
    except Exception:
        pass

    st.session_state.checkin_pending_action = None
    st.session_state.checkin_reason = ""
    st.session_state.checkin_reschedule_when = ""
    add_msg("assistant", f"📝 Saved feedback for '{mission.get('title','Item')}'.")


def checkin_submit_feedback():
    mission, mode = get_checkin_context()
    if not mission:
        st.session_state.checkin_feedback_open = False
        st.session_state.checkin_feedback_text = ""
        return

    fb = (st.session_state.get("checkin_feedback_text") or "").strip()
    fb = fb if fb else "Skipped (no details provided)"

    # Save as learning (missed)
    complete_mission_review(mission["id"], False, fb)

    # Close feedback UI + cleanup
    st.session_state.checkin_feedback_open = False
    st.session_state.checkin_feedback_text = ""
    st.session_state.checkin_reason = ""
    st.session_state.checkin_reschedule_when = ""
    st.session_state.checkin_pending_action = None

    add_msg("assistant", f"✅ Noted. I’ll learn from this: '{mission.get('title','Item')}'.")

def checkin_submit_feedback():
    mission, mode = get_checkin_context()
    if not mission:
        st.session_state.checkin_feedback_open = False
        st.session_state.checkin_feedback_text = ""
        return

    fb = (st.session_state.get("checkin_feedback_text") or "").strip()
    fb = fb if fb else "Skipped (no details provided)"

    # Save learning entry (missed)
    complete_mission_review(mission["id"], False, fb)

    # Clear UI state
    st.session_state.checkin_feedback_open = False
    st.session_state.checkin_feedback_text = ""
    st.session_state.checkin_reason = ""
    st.session_state.checkin_reschedule_when = ""
    st.session_state.checkin_pending_action = None

    add_msg("assistant", f"✅ Noted. I’ll learn from this: '{mission.get('title','Item')}'.")


def checkin_snooze(hours: int = 4):
    mission, mode = get_checkin_context()
    if not mission:
        return

    snooze_mission(mission["id"], hours=hours)
    st.session_state.checkin_reason = ""
    st.session_state.checkin_reschedule_when = ""
    st.session_state.checkin_pending_action = None
    add_msg("assistant", f"⏰ Snoozed check-in for '{mission.get('title','Item')}'.")


def _parse_user_datetime(text: str):
    """
    Natural language datetime parsing (local timezone).
    Handles common relative words like: tomorrow, today
    Falls back safely, and if time resolves to the past -> pushes to next day.
    """
    if not text:
        return None

    try:
        now = datetime.now().astimezone()
        raw = text.strip()
        t = raw.lower()

        # Base date for relative words
        base = now
        if "tomorrow" in t:
            base = now + timedelta(days=1)
            t = t.replace("tomorrow", "").strip()

        if "today" in t:
            base = now
            t = t.replace("today", "").strip()

        # Default used by dateutil when date is missing
        default = base.replace(minute=0, second=0, microsecond=0)

        # Parse remaining text (usually time)
        dt = dtparser.parse(t or raw, fuzzy=True, default=default)

        # Make tz-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default.tzinfo)

        dt = dt.astimezone()

        # If user said "tomorrow", force date to base.date()
        if "tomorrow" in raw.lower():
            dt = dt.replace(year=base.year, month=base.month, day=base.day)

        # Safety: if result is still in the past, bump to next day
        if dt <= now:
            dt = dt + timedelta(days=1)

        return dt

    except Exception:
        return None



def checkin_reschedule():
    """
    Creates a NEW calendar event (safe) and marks the old mission as missed+rescheduled.
    We avoid editing old past events to reduce risk.
    """
    mission, mode = get_checkin_context()
    if not mission:
        return

    uid = (st.session_state.get("user_email") or "").strip().lower()
    if not uid:
        add_msg("assistant", "⚠️ Connect your calendar first to reschedule.")
        return

    when_text = (st.session_state.get("checkin_reschedule_when") or "").strip()
    new_start = _parse_user_datetime(when_text)
    if not new_start:
        add_msg("assistant", "⚠️ I couldn’t understand the new time. Try: 'tomorrow 6pm' or 'Sat 10am'.")
        return

    new_end = new_start + timedelta(hours=1)

    note = (st.session_state.get("checkin_reason") or "").strip() or "Missed"
    title = mission.get("title") or "Event"

    new_event = {
        "title": f"{title} (Rescheduled)",
        "start_time": new_start.isoformat(),
        "end_time": new_end.isoformat(),
        "location": "",
        "description": f"Rescheduled after missed check-in. Note: {note}",
    }

    ok, msg, eid = add_event_to_calendar(uid, new_event)
    if ok:
        # Mark old mission as missed
        complete_mission_review(mission["id"], False, f"Missed. Rescheduled. Note: {note}")

        # Track the new mission too
        log_mission_start({"title": new_event["title"], "end_time": new_event["end_time"], "source_id": eid})

        st.session_state.checkin_reason = ""
        st.session_state.checkin_reschedule_when = ""
        st.session_state.checkin_pending_action = None

        refresh_calendar(force_email=uid)
        add_msg("assistant", f"✅ Rescheduled: '{new_event['title']}' added to your calendar.")
    else:
        add_msg("assistant", f"⛔ Reschedule failed: {msg}")


def checkin_delete():
    """
    Deletes the old calendar event only if we have its Calendar ID (source_id).
    Then marks mission as missed+deleted.
    """
    mission, mode = get_checkin_context()
    if not mission:
        return

    uid = (st.session_state.get("user_email") or "").strip().lower()
    if not uid:
        add_msg("assistant", "⚠️ Connect your calendar first to delete.")
        return

    note = (st.session_state.get("checkin_reason") or "").strip() or "Missed"
    source_id = mission.get("source_id")

    if source_id:
        ok, msg = (
            delete_event(source_id, user_id=uid)
            if "user_id" in delete_event.__code__.co_varnames
            else delete_event(source_id, uid)
        )

        if ok:
            complete_mission_review(mission["id"], False, f"Missed. Deleted. Note: {note}")
            refresh_calendar(force_email=uid)
            add_msg("assistant", f"🗑️ Deleted '{mission.get('title','Item')}' from calendar.")
        else:
            complete_mission_review(mission["id"], False, f"Missed. Delete failed. Note: {note}")
            add_msg("assistant", f"⚠️ Could not delete from calendar, but I saved the feedback. ({msg})")
    else:
        complete_mission_review(mission["id"], False, f"Missed. No calendar ID to delete. Note: {note}")
        add_msg("assistant", "⚠️ Saved feedback, but this item wasn’t linked to a calendar event (can’t delete).")

    st.session_state.checkin_reason = ""
    st.session_state.checkin_reschedule_when = ""
    st.session_state.checkin_pending_action = None


# --- Backward compatibility alias (app.py may still import this) ---
def get_checkin_item():
    mission, _mode = get_checkin_context()
    return mission

