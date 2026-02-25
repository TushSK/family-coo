# brain_v23.py
import json
import datetime
import base64
import re

from groq import Groq
from src.prompts import build_system_prompt, build_json_repair_prompt, build_weekend_regen_prompt


def _get_tz_now():
    """Return timezone-aware 'now' for America/New_York without requiring pytz."""
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
        tz = ZoneInfo("America/New_York")
        return datetime.datetime.now(tz)
    except Exception:
        # Fallback (keeps app running)
        return datetime.datetime.now()


def _next_7_days_cheatsheet(now: datetime.datetime) -> str:
    lines = ["REFERENCE DATES (Use these for 'Tomorrow', 'Next Saturday', etc):"]
    lines.append(f"- TODAY ({now.strftime('%A')}): {now.strftime('%Y-%m-%d')}")
    for i in range(1, 8):
        d = now + datetime.timedelta(days=i)
        lines.append(f"- {d.strftime('%A')} (+{i} days): {d.strftime('%Y-%m-%d')}")
    return "\n".join(lines)


def _next_saturday_date(now: datetime.datetime) -> str:
    # weekday: Monday=0 ... Sunday=6, Saturday=5
    days_ahead = (5 - now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # "Next Saturday" must be future Saturday
    ns = now + datetime.timedelta(days=days_ahead)
    return ns.strftime("%Y-%m-%d")


def _try_parse_json(text: str):
    if not text:
        return None

    t = text.strip()

    # Strip common markdown fences if present
    t = re.sub(r"^```(json)?\s*", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s*```$", "", t).strip()

    # 1) direct parse
    try:
        return json.loads(t)
    except Exception:
        pass

    # 2) extract first { ... } block
    m = re.search(r"(\{.*\})", t, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        # remove trailing commas before } or ]
        candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None

def _repair_json_with_llm(client, model: str, bad_text: str) -> str:
    repair_prompt = build_json_repair_prompt(bad_text)

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": repair_prompt}],
        temperature=0.0,
        max_tokens=800,
        stream=False,
    )
    return (completion.choices[0].message.content or "").strip()


def encode_image(image) -> str:
    import io
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# -----------------------------
# Checkpoint 2.3 - Option B:
# Follow-up answer handling only
# -----------------------------

_WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
]
_WEEKDAY_RE = re.compile(r"\b(" + "|".join(_WEEKDAYS) + r")\b", flags=re.IGNORECASE)

_TIME_HINT_RE = re.compile(
    r"\b("
    r"\d{1,2}(:\d{2})?\s*(am|pm)|"          # 4pm, 4:30 pm
    r"morning|afternoon|evening|night|"    # time-of-day
    r"after\s+\d{1,2}|"                    # after 4
    r"post\s+\d{1,2}|"                     # post 4
    r"around\s+\d{1,2}|"                   # around 6
    r"tomorrow|today|tonight|"             # relative
    r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r")\b",
    flags=re.IGNORECASE,
)

_ANSWER_YES_RE = re.compile(r"\b(yes|yeah|yep|sure|ok|okay|do it|go ahead)\b", flags=re.IGNORECASE)
_ANSWER_NO_RE = re.compile(r"\b(no|nope|cancel|stop|don't)\b", flags=re.IGNORECASE)


def _extract_last_assistant_question(chat_history):
    """
    Find the last assistant message that looks like a direct question.
    Returns dict: {question_text, question_kind, choices}
    question_kind is a lightweight heuristic: 'day_choice' | 'time' | 'confirm' | 'generic'
    """
    if not chat_history:
        return None

    last_q = None
    for msg in reversed(chat_history):
        try:
            if (msg.get("role") or "").lower() != "assistant":
                continue
            txt = (msg.get("content") or "").strip()
            if not txt:
                continue

            # Looks like a question if ends with ? or has "Reply:" A/B/C etc.
            is_questiony = txt.endswith("?") or re.search(r"\bReply\b.*\b[A-C]\b", txt, flags=re.IGNORECASE)
            if not is_questiony:
                continue

            last_q = txt
            break
        except Exception:
            continue

    if not last_q:
        return None

    q_low = last_q.lower()

    # Heuristics for kind/choices
    choices = []
    if re.search(r"\bsaturday\b.*\bsunday\b|\bsunday\b.*\bsaturday\b", q_low):
        # extract explicit weekday choices if present
        if "saturday" in q_low:
            choices.append("Saturday")
        if "sunday" in q_low:
            choices.append("Sunday")
        kind = "day_choice"
    elif re.search(r"\bwhat time\b|\bwhich time\b|\bwhen\b|\btime\b", q_low):
        kind = "time"
    elif re.search(r"\bdo you want me to\b|\bshould i\b|\bconfirm\b", q_low):
        kind = "confirm"
    else:
        kind = "generic"

    # A/B/C style choices (keep it simple)
    m = re.findall(r"\(\s*([A-C])\s*\)\s*([^(\n]+)", last_q)
    if m:
        for _, label in m[:5]:
            label = label.strip().strip(".")
            if label:
                choices.append(label)

    return {
        "question_text": last_q,
        "question_kind": kind,
        "choices": choices[:5],
    }


def _looks_like_answer(user_text: str, q_kind: str) -> bool:
    """
    Decide if the user text is likely answering the previous assistant question.
    Keep conservative (Option B only).
    """
    t = (user_text or "").strip()
    if not t:
        return False

    # Basic yes/no answers for confirmation questions
    if q_kind == "confirm":
        if _ANSWER_YES_RE.search(t) or _ANSWER_NO_RE.search(t):
            return True

    # Day choice / time questions: look for weekday/time hints
    if q_kind in ("day_choice", "time"):
        if _WEEKDAY_RE.search(t) or _TIME_HINT_RE.search(t):
            return True

    # Generic question: short replies often are answers, but avoid over-triggering.
    # We'll only treat as answer if it contains weekday/time or yes/no.
    if _WEEKDAY_RE.search(t) or _TIME_HINT_RE.search(t) or _ANSWER_YES_RE.search(t) or _ANSWER_NO_RE.search(t):
        return True

    return False

def _default_end_time(start_dt: datetime.datetime, minutes: int = 60) -> datetime.datetime:
    return start_dt + datetime.timedelta(minutes=minutes)

def _parse_tomorrow_time(user_text: str, now: datetime.datetime):
    """
    Minimal parser for patterns like:
    - "tomorrow at 5:30 pm"
    - "tomorrow 5pm"
    Returns timezone-aware datetime or None.
    """
    if not user_text:
        return None

    t = user_text.lower()

    # Must contain "tomorrow"
    if "tomorrow" not in t:
        return None

    # Find time like 5:30 pm / 5 pm / 17:30
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    if not m:
        return None

    hh = int(m.group(1))
    mm = int(m.group(2) or "0")
    ampm = (m.group(3) or "").lower()

    # Convert to 24h if am/pm present
    if ampm == "pm" and hh != 12:
        hh += 12
    if ampm == "am" and hh == 12:
        hh = 0

    tomorrow = now + datetime.timedelta(days=1)
    try:
        dt = tomorrow.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return dt
    except Exception:
        return None

def _ensure_event_schema(parsed: dict, user_request: str, now: datetime.datetime) -> dict:
    """
    Ensures events comply with the Brain Output Contract.
    If missing start_time/end_time and we can infer from 'tomorrow at X', fill it.
    If still missing, convert to type='question' with exactly one question.
    """
    if not isinstance(parsed, dict):
        return {
            "type": "error",
            "text": "Invalid brain output (not a JSON object).",
            "pre_prep": "",
            "events": []
        }

    # Always ensure required top-level fields exist
    parsed.setdefault("type", "error")
    parsed.setdefault("text", "")
    parsed.setdefault("pre_prep", "")
    parsed.setdefault("events", [])

    t = (parsed.get("type") or "").lower()
    events = parsed.get("events") or []

        # ✅ If user used scheduling trigger but model didn't provide an event, force a proper question
    # (We do not execute tools here; we just ensure we can create a draft event.)
    if re.search(r"\b(schedule|add|plan)\b", user_request or "", flags=re.IGNORECASE):
        if t not in ("plan", "conflict", "confirmation"):
            parsed["type"] = "plan"
            t = "plan"

        if not isinstance(events, list) or len(events) == 0:
            # Minimal safe fallback: ask ONE question if we cannot infer a start time
            # (Keeps contract stable and avoids fake events with no time.)
            inferred = _parse_tomorrow_time(user_request, now)
            if inferred is None:
                return {
                    "type": "question",
                    "text": "What time should I schedule this? (A) 9:00 AM (B) 9:30 AM (C) Other",
                    "pre_prep": "Reply with A/B/C (or a time like '10:15 AM').",
                    "events": []
                }

            # If we inferred a time (tomorrow pattern), create a minimal draft event
            title = (parsed.get("text") or "").strip() or "Scheduled item"
            return {
                "type": "plan",
                "text": "Got it — I can schedule that.",
                "pre_prep": "Tip: add a location anytime if you want travel buffer suggestions.",
                "events": [{
                    "title": title[:80],
                    "start_time": inferred.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end_time": _default_end_time(inferred, 60).strftime("%Y-%m-%dT%H:%M:%S"),
                    "location": "",
                    "description": ""
                }]
            }


    # Only enforce schema strictly when events are expected to be executable
    if t in ("plan", "conflict", "confirmation") and isinstance(events, list) and len(events) > 0:
        fixed_events = []
        inferred_start = _parse_tomorrow_time(user_request, now)

        for ev in events:
            if not isinstance(ev, dict):
                ev = {}

            # Normalize keys if model used alternatives
            if "start" in ev and "start_time" not in ev:
                ev["start_time"] = ev.get("start")
            if "end" in ev and "end_time" not in ev:
                ev["end_time"] = ev.get("end")

            title = (ev.get("title") or "").strip()
            start_time = (ev.get("start_time") or "").strip()
            end_time = (ev.get("end_time") or "").strip()

            # Fill missing title from user_request minimally
            if not title:
                title = "Scheduled item"

            # Auto-fill start/end if missing and we inferred tomorrow time
            if (not start_time) and inferred_start is not None:
                ev["start_time"] = inferred_start.strftime("%Y-%m-%dT%H:%M:%S")
                ev["end_time"] = _default_end_time(inferred_start, 60).strftime("%Y-%m-%dT%H:%M:%S")

            # If still missing start_time -> downgrade to question (ONE question)
            start_time = (ev.get("start_time") or "").strip()
            end_time = (ev.get("end_time") or "").strip()
            if not start_time or not end_time:
                return {
                    "type": "question",
                    "text": "What start time should I use? (A) 5:30 PM (B) 6:00 PM (C) Other",
                    "pre_prep": "Reply with A/B/C (or a time like '7:15 PM').",
                    "events": []
                }

            # Ensure optional fields exist
            ev["title"] = title
            ev.setdefault("location", "")
            ev.setdefault("description", "")

            fixed_events.append(ev)

        parsed["events"] = fixed_events

    return parsed

def _is_weekend_outing_request(user_text: str) -> bool:
    t = (user_text or "").lower()

    weekend_signals = ["weekend", "saturday", "sunday", "sat", "sun"]

    # stronger intent coverage for your trick queries
    activity_signals = [
        "outing",
        "suggest",
        "ideas",
        "plan",
        "plans",
        "fun",
        "interesting",
        "family",
        "kids",
        "visit",
        "things to do",
        "go out",
        "what should we do",
        "what do we do",
    ]

    return any(w in t for w in weekend_signals) and any(a in t for a in activity_signals)

def _dead_end_output(parsed: dict) -> bool:
    if not isinstance(parsed, dict):
        return True

    t = (parsed.get("type") or "").lower()
    txt = (parsed.get("text") or "").strip()
    low = txt.lower()

        # ✅ Enforce structured weekend response
    # If this is a weekend outing request,
    # we REQUIRE type="question" (A/B/C structured).
    try:
        if _is_weekend_outing_request(user_request) and t != "question":
            return True
    except Exception:
        pass


    # 1) Any "chat" that is basically a question is a dead-end for weekend flows
    if t == "chat" and ("?" in txt) and len(txt) < 140:
        return True

    # 2) Generic "mirror questions" are dead-ends
    generic = [
        "which schedule do you prefer",
        "which activity would you like",
        "what are your plans for the weekend",
        "what would you like to do this weekend",
    ]
    if any(g in low for g in generic):
        return True

    # 3) If it's a weekend flow, we require A/B/C in a question
    if t == "question":
        if "(A)" not in txt or "(B)" not in txt or "(C)" not in txt:
            return True

    # 4) Very short non-actionable outputs are dead-ends
    if len(txt) < 40 and t in ("chat", "confirmation", "question"):
        return True

    return False

def _regen_dynamic_weekend_options(client, model: str, user_request: str, current_location: str, memory_dump: str) -> dict:
    """
    Weekend regen must be robust:
    - Never crash on non-JSON
    - Must return valid schema: {type,text,pre_prep,events}
    - Must keep type="question" and events=[]
    """
    ctx = {
        "user_request": user_request,
        "current_location": current_location,
        "memory_dump": memory_dump,
        
    }

    # ✅ Inject Ideas Inbox into regen context
    try:
        from src.utils import get_ideas_summary
        import streamlit as st

        safe_email = (st.session_state.get("safe_email") or "").strip()
        if not safe_email:
            safe_email = (st.session_state.get("user_email") or "").strip()
            safe_email = safe_email.replace("@", "_").replace(".", "_")

        ideas = get_ideas_summary(safe_email, n=10) if safe_email else []
        ctx["ideas_dump"] = json.dumps(ideas, ensure_ascii=False)

    except Exception:
        ctx["ideas_dump"] = "[]"

    prompt = build_weekend_regen_prompt(ctx)

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}],
        temperature=0.4,
        max_tokens=700,
        stream=False,
    )

    txt = (completion.choices[0].message.content or "").strip()

    # Prefer your existing parser/repair utilities if present
    try:
        parsed = _try_parse_json(txt)
        if parsed is None:
            # One repair attempt using your existing repair path (if available)
            try:
                repaired = _repair_json_with_llm(client, model, txt)
                parsed = _try_parse_json(repaired)
            except Exception:
                parsed = None

        if not isinstance(parsed, dict):
            raise ValueError("regen returned non-dict")

        # Hard-enforce schema constraints for regen
        parsed["type"] = "question"
        parsed["events"] = []

        # Ensure required fields exist
        if "text" not in parsed or not isinstance(parsed.get("text"), str):
            parsed["text"] = "Weekend outing — pick one:\n\n(A) Option A\n    Duration: 2 hours\n    Time window: 10:00 AM–12:00 PM\n\n(B) Option B\n    Duration: 2 hours\n    Time window: 12:00 PM–2:00 PM\n\n(C) Option C\n    Duration: 2 hours\n    Time window: 2:00 PM–4:00 PM\n\nReply exactly: schedule A / schedule B / schedule C\n(Optional: add Sat/Sun + adjust time window)"

        if "pre_prep" not in parsed or not isinstance(parsed.get("pre_prep"), str):
            parsed["pre_prep"] = "Tip: reply with schedule A/B/C and add Sat/Sun + time window if you want."

        return parsed

    except Exception:
        # Absolute last-resort safe fallback (never break the app)
        return {
            "type": "question",
            "text": (
                "Weekend outing — pick one:\n\n"
                "(A) Local park outing\n"
                "    Duration: 2 hours\n"
                "    Time window: 10:00 AM–12:00 PM\n\n"
                "(B) Museum visit\n"
                "    Duration: 2 hours\n"
                "    Time window: 12:00 PM–2:00 PM\n\n"
                "(C) Riverwalk stroll\n"
                "    Duration: 2 hours\n"
                "    Time window: 2:00 PM–4:00 PM\n\n"
                "Reply exactly: schedule A / schedule B / schedule C\n"
                "(Optional: add Sat/Sun + adjust time window)"
            ),
            "pre_prep": "Tip: include a preferred neighborhood or max drive time for better suggestions.",
            "events": [],
        }

def get_coo_response(
    api_key,
    user_request,
    memory=None,
    calendar_data=None,
    pending_events=None,
    current_location=None,
    image_context=None,
    image_obj=None,          # ✅ alias used by flow.py
    chat_history=None,
):
    # ✅ flow.py passes image_obj; keep backward compatibility
    if image_context is None and image_obj is not None:
        image_context = image_obj

    # ✅ normalize None -> empty structures to avoid downstream crashes
    memory = memory or []
    calendar_data = calendar_data or []
    pending_events = pending_events or []
    chat_history = chat_history or []

    """
    Smart, timezone-aware brain.

    Returns STRICT JSON only (string). Types:
      - plan | conflict | question | confirmation | error
    """
    client = Groq(api_key=api_key)

    now = _get_tz_now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    cheat_sheet = _next_7_days_cheatsheet(now)
    next_saturday = _next_saturday_date(now)

    # -----------------------------
    # Idea option selection support (dialog continuity) - preserved from 2.1
    # -----------------------------
    def _extract_idea_options(history):
        """Extract option titles from the last assistant message that looks like an option list (1/2/3 or A/B/C)."""
        if not history:
            return []
        last = None
        for msg in reversed(history):
            try:
                if (msg.get("role") or "").lower() == "assistant":
                    txt = (msg.get("content") or "").strip()
                    if not txt:
                        continue

                    # detect either numeric list or A/B/C list
                    has_numeric = re.search(r"(^|\n)\s*\d+\s*[\).]", txt)
                    has_abc = re.search(r"(^|\n)\s*\(?\s*[A-C]\s*\)?\s*[\).:-]", txt, flags=re.IGNORECASE)
                    if has_numeric or has_abc:
                        last = txt
                        break
            except Exception:
                continue

        if not last:
            return []

        options = []

        # Numeric options: 1) Title
        for line in last.splitlines():
            m = re.match(r"\s*(\d+)\s*[\).]\s*(.+?)\s*$", line)
            if m:
                title = m.group(2).strip()
                title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
                if title:
                    options.append(title)

        # A/B/C options: (A) Title  OR  A) Title
        if not options:
            for line in last.splitlines():
                m = re.match(r"\s*\(?\s*([A-C])\s*\)?\s*[\).:-]\s*(.+?)\s*$", line, flags=re.IGNORECASE)
                if not m:
                    continue
                title = m.group(2).strip()
                title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
                if title:
                    options.append(title)

        return options[:5]

    def _normalize_text(s: str) -> str:
        s = (s or "").lower()
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _match_selected_option(user_text: str, options):
        """Return the matched option title if the user repeats/chooses it."""
        ut = _normalize_text(user_text)
        if not ut or not options:
            return None

        # Handle "1" / "option 1" style selections
        m = re.search(r"\b(option\s*)?(\d)\b", ut)
        if m:
            idx = int(m.group(2)) - 1
            if 0 <= idx < len(options):
                return options[idx]

        for opt in options:
            o = _normalize_text(opt)
            if not o:
                continue
            if o in ut or ut in o:
                return opt

            o_tokens = [t for t in o.split() if len(t) >= 3]
            if not o_tokens:
                continue
            hit = sum(1 for t in o_tokens if t in ut)
            if hit >= max(2, int(len(o_tokens) * 0.6)):
                return opt

        return None

    idea_options = _extract_idea_options(chat_history)
    selected_idea = _match_selected_option(user_request, idea_options)

    # If the user selected an idea but didn't use the scheduling keyword,
    # keep Checkpoint 2.1 drafting gate intact by asking for ONE explicit confirmation.
    if selected_idea and not re.search(r"\b(schedule|add|plan)\b", user_request or "", flags=re.IGNORECASE):
        return json.dumps(
            {
                "type": "question",
                "text": f"Got it — do you want me to schedule \"{selected_idea}\"? Reply: (A) schedule it (B) change the time (C) cancel",
                "events": [],
                "pre_prep": "Tip: you can include day/time in the same reply, e.g., 'schedule it Saturday 7 PM'.",
            },
            ensure_ascii=False,
        )

    # -----------------------------
    # NEW: Follow-up answer handling (Option B)
    # -----------------------------
    dialog_state = _extract_last_assistant_question(chat_history)
    interpreted_as_answer = False

    if dialog_state and _looks_like_answer(user_request, dialog_state.get("question_kind", "generic")):
        # We DO NOT execute tools here; we just enrich the prompt so the model
        # treats user text as an answer to the previous question.
        interpreted_as_answer = True

    # Keep recent context small
    history_txt = ""
    if chat_history:
        try:
            history_txt = "\n".join(
                [f"{msg.get('role','').upper()}: {msg.get('content','')}" for msg in chat_history[-6:]]
            )
        except Exception:
            history_txt = ""

    # Safe JSON dumps
    try:
        memory_dump = json.dumps(memory or [], ensure_ascii=False)
    except Exception:
        memory_dump = "[]"

    try:
        pending_dump = json.dumps(pending_events or [], ensure_ascii=False)
    except Exception:
        pending_dump = "[]"

    # Build a continuation hint only when we are confident this is an answer
    continuation_hint = ""
    if interpreted_as_answer:
        continuation_hint = (
            "DIALOG CONTINUATION:\n"
            f"- The assistant previously asked this question: {dialog_state.get('question_text')}\n"
            f"- The user message is the answer: {user_request}\n"
            "INSTRUCTION: Treat the user message as an answer to the previous question and continue.\n"
        )

    ctx = {
        "current_time_str": current_time_str,
        "cheat_sheet": cheat_sheet,
        "next_saturday": next_saturday,
        "current_location": current_location,
        "calendar_data": calendar_data,
        "pending_dump": pending_dump,
        "memory_dump": memory_dump,
        "history_txt": history_txt,
        "idea_options": idea_options or [],
        "selected_idea": selected_idea or "",
        "continuation_hint": continuation_hint,
        "user_request": user_request,
    }
    # ✅ ADD THIS BLOCK RIGHT HERE
    try:
        from src.utils import get_memory_summary_for_user
        from src.utils import get_memory_summary_from_memory
        from src.utils import get_ideas_summary
        safe_email = (ctx.get("safe_email") or "").strip()  # if you have it
        if safe_email:
            safe_email = (ctx.get("user_email") or "").strip()
            safe_email = safe_email.replace("@", "_").replace(".", "_")

            ctx["ideas_summary"] = get_ideas_summary(safe_email, n=10) if safe_email else []
        else:
            ctx["ideas_summary"] = []
           
        # If you have email available in brain, use it:
        # ctx["memory_summary"] = get_memory_summary_for_user(user_email, n=12)
        # If you DON'T have email here (likely), use a summary-from-memory-list function instead (recommended):
        ctx["memory_summary"] = get_memory_summary_from_memory(memory, n=12)
    except Exception:
        ctx["memory_summary"] = []

    system_prompt = build_system_prompt(ctx)

    messages = [{"role": "system", "content": system_prompt}]

    if image_context is not None:
        model = "llama-3.2-90b-vision-preview"
        base64_image = encode_image(image_context)
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_request},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }
        )
    else:
        model = "llama-3.3-70b-versatile"
        messages.append({"role": "user", "content": user_request})

    
######################
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.6,
        max_tokens=1024,
        stream=False,
    )   
    text = (completion.choices[0].message.content or "").strip()

    parsed = _try_parse_json(text)

    # ✅ Only proceed if parsed is a dict
    if isinstance(parsed, dict):
        parsed = _ensure_event_schema(parsed, user_request, now)

        # (optional) weekend normalization logic here — safe now
        if _is_weekend_outing_request(user_request):
            t = (parsed.get("type") or "").lower()
            txt = (parsed.get("text") or "")

            has_abc = ("(A)" in txt and "(B)" in txt and "(C)" in txt)
            has_template = ("Weekend outing — pick one:" in txt and "Duration:" in txt and "Time window:" in txt)

            if t != "question" or (not has_abc) or (not has_template):
                regen = _regen_dynamic_weekend_options(client, model, user_request, current_location, memory_dump)
                return json.dumps(regen, ensure_ascii=False)

        return json.dumps(parsed, ensure_ascii=False)

    # ✅ If parsed is None or not dict, fall through to repair path (existing logic)

    # One repair attempt
    try:
        repaired = _repair_json_with_llm(client, model, text)
        parsed2 = _try_parse_json(repaired)
        if parsed2 is not None:
            parsed2 = _ensure_event_schema(parsed2, user_request, now)
            return json.dumps(parsed2, ensure_ascii=False)
    except Exception:
        pass

    return json.dumps(
    {"type": "error", "text": "Model returned non-JSON output.", "events": [], "pre_prep": ""},
    ensure_ascii=False,
)