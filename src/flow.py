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
        "last_proactive_date": "",
        "last_proactive_kind": "",
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
    run_proactive_checks(trigger="app_load")

def run_proactive_checks(trigger: str = "app_load"):
    """
    Trigger-driven proactive help.
    - Runs only when app loads or calendar refreshes.
    - Runs at most once per day per user.
    - Never schedules events. Only adds an assistant message.
    """
    uid = (st.session_state.get("user_email") or "").strip().lower()
    if not uid:
        return

    # Only run when user is authenticated (prevents noise on login screen)
    if not st.session_state.get("authenticated"):
        return

    today = datetime.now().astimezone().date().isoformat()
    if st.session_state.get("last_proactive_date") == today:
        return  # already ran today

    # ---- Trigger 1: pending mission review ----
    pending = get_pending_review()
    if pending:
        title = pending.get("title") or "a task"
        add_msg("assistant", f"🔔 Action required: Did you complete “{title}”? Use **Yes/No** above.")
        st.session_state.last_proactive_date = today
        st.session_state.last_proactive_kind = "mission_checkin"
        return

    # ---- Trigger 2: daily suggestion (based on memory + day) ----
    # Lightweight read of user memory (safe if function exists; otherwise skip)
    pref_outing = ""
    try:
        from src.utils import load_user_memory
        mem = load_user_memory(uid, limit=30)
        for row in reversed(mem):
            if (row.get("kind") == "preference") and (row.get("key") == "outing_style"):
                pref_outing = str(row.get("value") or "")
                break
    except Exception:
        pass

    dow = datetime.now().astimezone().weekday()  # Mon=0 ... Sun=6
    # Only nudge Thu/Fri/Sat/Sun (keeps it “triggered”, not spammy)
    if dow in (3, 4, 5, 6):
        if pref_outing:
            add_msg(
                "assistant",
                f"💡 Quick suggestion: Want 3 {pref_outing} options for this weekend? "
                f"Type: **plan weekend** (or tell me Sat/Sun + time)."
            )
        else:
            add_msg(
                "assistant",
                "💡 Quick suggestion: Want 3 weekend outing ideas? Type: **plan weekend** "
                "(or tell me Sat/Sun + time)."
            )
        st.session_state.last_proactive_date = today
        st.session_state.last_proactive_kind = "daily_suggestion"
        return

def _extract_json(raw):
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        try:
            m = re.search(r"(\{.*\})", raw, re.DOTALL)
            if not m:
                return None
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

def _extract_options_json(pre_prep: str):
    import json, re
    if not pre_prep or not isinstance(pre_prep, str):
        return None
    m = re.search(r"OPTIONS_JSON\s*=\s*(\[[\s\S]*\])", pre_prep)
    if not m:
        return None
    try:
        arr = json.loads(m.group(1))
        return arr if isinstance(arr, list) else None
    except Exception:
        return None

def _extract_schedule_choice(text: str) -> str:
    import re
    t = (text or "").strip().lower()
    m = re.fullmatch(r"(schedule|plan|add)\s+([abc])", t)
    return m.group(2).upper() if m else ""

# -----------------------
# 2. LOGIC
# -----------------------
def execute_plan_logic(user_text: str, image_obj=None):
    import json
    import re
    import streamlit as st

    # ✅ Idea Inbox capture (must happen before Brain call)
    if handle_idea_inbox_capture(user_text):
        return

    memory = load_memory(limit=10)
    cal_events = st.session_state.get("calendar_events_all") or st.session_state.get("calendar_events")

    if cal_events:
        lines = [f"- {e.get('start_friendly','')}: {e.get('title','')}" for e in cal_events]
        human = "SCHEDULE (Next 7 Days):\n" + "\n".join(lines)
        structured = [{"title": e.get("title"), "start": e.get("start_raw"), "end": e.get("end_raw")} for e in cal_events]
        cal_str = human + "\nJSON:\n" + json.dumps(structured, ensure_ascii=False)
    else:
        cal_str = "Calendar Empty or Offline."

    # ------------------------------------------------------------
    # STRICT drafting gate: ONLY schedule/add/plan (whole words).
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

        return bool(re.search(r"\b(schedule|add|plan)\b", t))

    schedule_intent = _should_create_draft(user_text)

    try:
        api_key = st.secrets["general"]["groq_api_key"]
    except Exception:
        add_msg("assistant", "⛔ Error: Missing 'groq_api_key' in secrets.toml.")
        return

    # -----------------------------
    # Contextual Matching: inject relevant ideas (flow -> brain)
    # Standard keys:
    # - ideas_summary: list[dict] prompt-safe
    # - ideas_dump:    json string (debug/backward compatible)
    # -----------------------------
    ideas_summary = []
    ideas_dump = "[]"

    try:
        from src.utils import get_ideas_summary, select_relevant_ideas, safe_email_from_user

        uid = (st.session_state.get("user_email") or "").strip().lower()
        safe_email = safe_email_from_user(uid) if uid else ""

        if safe_email:
            ideas_all = get_ideas_summary(safe_email, n=30) or []
            ideas_sel = select_relevant_ideas(ideas_all, user_text, n=6) or []

            cleaned = []
            for it in ideas_sel:
                if isinstance(it, dict):
                    txt = (it.get("text") or "").strip()
                    if txt:
                        cleaned.append({**it, "text": txt})
                elif isinstance(it, str):
                    txt = it.strip()
                    if txt:
                        cleaned.append({"text": txt})

            ideas_summary = cleaned
            ideas_dump = json.dumps(ideas_summary, ensure_ascii=False)
    except Exception:
        ideas_summary = []
        ideas_dump = "[]"

    choice = _extract_schedule_choice(user_text)
    if choice and st.session_state.get("idea_options"):
        # carry selection into brain context so it can turn it into a schedulable plan/question
        st.session_state["selected_idea"] = choice
    else:
        st.session_state["selected_idea"] = ""

    # ---- call brain ----
    raw = get_coo_response(
        api_key=api_key,
        user_request=user_text,
        memory=memory,
        calendar_data=cal_str,
        chat_history=st.session_state.chat_history,
        image_obj=image_obj,
        current_location=st.session_state.user_location,
        ideas_summary=ideas_summary,
        ideas_dump=ideas_dump,
    )

    data = _extract_json(raw)
    # Persist weekend options deterministically (no UI change)
    opts = _extract_options_json(data.get("pre_prep", ""))
    if opts:
        st.session_state["idea_options"] = opts  # existing key used in debug :contentReference[oaicite:9]{index=9}

    if not data:
        add_msg("assistant", "⚠️ Error: I couldn't process that. Please try again.")
        return

    # add chat entries
    if user_text:
        add_msg("user", user_text)
    elif image_obj:
        add_msg("user", "📷 [Scanned Image]")

    add_msg("assistant", data.get("text", ""))

    # ---- optional debug (console only) ----
    if st.session_state.get("debug"):
        print("=== DEBUG FLOW ===")
        print("user_text:", repr(user_text))
        print("schedule_intent:", schedule_intent)
        print("pending_events:", len(st.session_state.get("pending_events") or []))
        print("ideas_summary_count:", len(ideas_summary))
        print("raw_from_brain_head:", (raw or "")[:250])

    # ---- memory writeback (unchanged) ----
    try:
        from src.utils import parse_memory_tags, append_user_memory_entry
        uid = (st.session_state.get("user_email") or "").strip().lower()
        tags = parse_memory_tags(data.get("pre_prep", ""))
        for t in tags:
            entry = {
                "kind": t.get("kind", "preference"),
                "key": t.get("key", ""),
                "value": t.get("value", ""),
                "confidence": float(t.get("confidence", 0.7) or 0.7),
                "notes": t.get("notes", ""),
                "source": "brain",
            }
            if entry["key"] and entry["value"] and uid:
                append_user_memory_entry(uid, entry)
    except Exception:
        pass

    # ✅ Only draft when strict scheduling intent is detected
    new_events = data.get("events", [])
    if schedule_intent and new_events:
        st.session_state.pending_events = new_events

def add_msg(role, content):
    st.session_state.chat_history.append({"role": role, "content": content})
    if len(st.session_state.chat_history) > 15:
        st.session_state.chat_history = st.session_state.chat_history[-15:]

def apply_deferred_ui_resets():
    """
    Applies deferred resets BEFORE widgets are instantiated.
    Must be called early in app.py (before render_command_center).
    """
    import streamlit as st

    if st.session_state.get("defer_train_brain_reset"):
        # These keys are used by widgets; safe ONLY before widgets are created.
        st.session_state["brain_correction"] = ""
        st.session_state["brain_bad_response"] = False

        # Clear the deferred flag
        st.session_state["defer_train_brain_reset"] = False

import re

def _extract_idea_text(user_text: str) -> str | None:
    if not user_text:
        return None

    # Accept: "idea: ...", "Idea: ...", "save idea: ...", "add idea: ..."
    m = re.match(r"^\s*(idea|save idea|add idea)\s*:\s*(.+)\s*$", user_text, flags=re.IGNORECASE)
    if not m:
        return None
    return (m.group(2) or "").strip() or None


def handle_idea_inbox_capture(user_text: str) -> bool:
    """
    Returns True if we captured/saved an idea and injected a confirmation message.
    Returns False if not an idea message (normal flow continues).
    """
    idea_text = _extract_idea_text(user_text)
    if not idea_text:
        return False

    # Must have safe_email in session (your app already has this for memory)
    safe_email = (st.session_state.get("safe_email") or "").strip()
    if not safe_email:
        # Fall back to user_email if that's what you store
        safe_email = (st.session_state.get("user_email") or "").strip()
        safe_email = safe_email.replace("@", "_").replace(".", "_")

    try:
        from src.utils import add_idea_to_inbox
        item = add_idea_to_inbox(safe_email, idea_text, tags=["inbox"])
        msg = f'✅ Saved to Ideas Inbox: "{item.get("text","")}"'
    except Exception as e:
        msg = f"⚠️ Could not save idea. ({e})"

    # Inject assistant message into chat history (no UI change)
    st.session_state["chat_history"] = st.session_state.get("chat_history") or []
    st.session_state["chat_history"].append({"role": "user", "content": user_text})
    st.session_state["chat_history"].append({"role": "assistant", "content": msg})

    return True

# -----------------------
#  Train the Brain 
# -----------------------
def process_train_brain_feedback():
    """
    Train-the-Brain writeback:
    - Triggered only when Save button is clicked (brain_save)
    - Writes a learning row to memory/feedback_log.json via save_manual_feedback
    - Uses deferred reset flag (no widget-key mutation after instantiation)
    """
    import streamlit as st
    from src.utils import save_manual_feedback

    # Save button click is a one-rerun trigger; don't reset the key manually.
    if not st.session_state.get("brain_save"):
        return

    correction = (st.session_state.get("brain_correction") or "").strip()
    bad = bool(st.session_state.get("brain_bad_response", False))
    uid = (st.session_state.get("user_email") or "").strip().lower()

    # If empty, just schedule a reset (optional) and exit
    if not correction:
        st.session_state["defer_train_brain_reset"] = True
        return

    try:
        topic = "TrainBrain: Bad Response" if bad else "TrainBrain: Improvement"
        rating = "👎" if bad else "👍"
        save_manual_feedback(topic, correction, rating, user_id=uid)

        # Mark KPI as dirty (optional, no UI changes required)
        st.session_state["kpi_dirty"] = True

    except Exception:
        # Never crash app due to training feedback
        pass
    finally:
        # Defer widget value resets to BEFORE UI instantiation on next run
        st.session_state["defer_train_brain_reset"] = True


# -----------------------
# 3. CALLBACKS
# -----------------------
def submit_plan():
    import streamlit as st
    from PIL import Image

    st.session_state.setdefault("plan_text", "")
    st.session_state.setdefault("show_camera", False)
    st.session_state.setdefault("clear_plan_text", False)

    text = (st.session_state.get("plan_text") or "").strip()
    cam_val = st.session_state.get("cam_input")

    img = None
    if st.session_state.get("show_camera") and cam_val:
        try:
            img = Image.open(cam_val)
        except Exception:
            img = None

    if not text and not img:
        return

    execute_plan_logic(text, image_obj=img)

    # ✅ Defer clear to UI BEFORE widget is created
    st.session_state["clear_plan_text"] = True

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
run_proactive_checks("calendar_refresh")

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
    uid = st.session_state.get("user_email")
    save_manual_feedback(title, reason, "👎",user_id=uid)
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
    uid = st.session_state.get("user_email")
    complete_mission_review(mission["id"], True, note,user_id=uid)

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
        uid = st.session_state.get("user_email")
        save_manual_feedback(mission.get("title","Item"), "Completed as planned", "👍",user_id=uid)
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
        uid = st.session_state.get("user_email")
        save_manual_feedback(mission.get("title","Item",user_id=uid), fb, "👎")
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

