# src/brain.py
"""
Family COO Brain (Checkpoint 2.6)

STRICT RULES:
- Reasoning/planning only (NO Streamlit, NO tool execution).
- Returns ONLY a raw JSON string with schema:
  {
    "type": "plan" | "conflict" | "question" | "confirmation" | "chat" | "error",
    "text": "string",
    "pre_prep": "string",
    "events": [{"title","start_time","end_time","location","description"}]
  }
- No extra keys, no wrappers, no markdown in outputs.

This module:
- Builds LLM prompts (via src.prompts) and interprets the model response.
- Applies routing/continuity heuristics (A/B/C selection mirroring) to prevent loops.
- Applies lightweight safety gates to prevent weak/invalid outputs from reaching UI.
"""

from __future__ import annotations

import base64
import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from groq import Groq

from src.prompts import (
    build_json_repair_prompt,
    build_system_prompt,
    build_weekend_regen_prompt,
)


# -----------------------------
# Time helpers (no pytz)
# -----------------------------
def _get_tz_now() -> datetime.datetime:
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


# -----------------------------
# Intent + guardrails
# -----------------------------
_SCHEDULE_INTENT_RE = re.compile(r"\b(schedule|add|plan)\b", flags=re.IGNORECASE)


def _is_schedule_intent(user_text: str) -> bool:
    return bool(_SCHEDULE_INTENT_RE.search((user_text or "").strip()))


_GREET_RE = re.compile(
    r"^\s*(hi|hello|hey|good\s+morning|good\s+afternoon|good\s+evening|hiya)\b",
    flags=re.IGNORECASE,
)

def _is_greeting(user_text: str) -> bool:
    return bool(_GREET_RE.search((user_text or "").strip()))


def _looks_like_banned_scheduling_prompt(text: str) -> bool:
    """
    Guard: if user didn't ask to schedule, the assistant must NOT push scheduling.
    We avoid hardcoded user-facing content by re-generating via LLM when this triggers.
    """
    t = (text or "").strip().lower()
    if not t:
        return False

    # If the assistant is asking the user to "schedule" with A/B/C selection, that's a scheduling push.
    if "reply exactly" in t and "schedule" in t and re.search(r"\b[A-C]\b", t):
        return True

    # Generic scheduling prompts without explicit user scheduling intent
    scheduling_cues = [
        "would you like to schedule",
        "do you want to schedule",
        "shall i schedule",
        "which one would you like to schedule",
        "which outing would you like to schedule",
        "pick a time",
        "choose a time",
        "time options",
    ]
    return any(cue in t for cue in scheduling_cues)


def _strict_error_json(msg: str) -> str:
    return json.dumps({"type": "error", "text": msg, "pre_prep": "", "events": []}, ensure_ascii=False)


# -----------------------------
# JSON parsing / repair
# -----------------------------
def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = text.strip()

    # Fast path
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Try to extract first {...}
    extracted = _extract_first_json_object(text)
    if extracted:
        try:
            obj = json.loads(extracted)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None


def _extract_first_json_object(text: str) -> Optional[str]:
    """Extract the first top-level JSON object substring (best-effort)."""
    if not text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _repair_json_with_llm(client: Groq, model: str, bad_text: str) -> str:
    repair_prompt = build_json_repair_prompt(bad_text)
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": repair_prompt}],
        temperature=0.0,
        max_tokens=900,
        stream=False,
    )
    return (completion.choices[0].message.content or "").strip()


# -----------------------------
# Idea selection helpers (for continuity, NOT tool execution)
# -----------------------------
def _normalize_choice_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_option_titles_from_history(history: List[Dict[str, Any]]) -> List[str]:
    """
    Extract option titles from the last assistant message that looks like an option list:
    - numeric: 1) Title
    - letter: (A) Title or A) Title
    """
    if not history:
        return []

    last = None
    for msg in reversed(history):
        try:
            if (msg.get("role") or "").lower() != "assistant":
                continue
            txt = (msg.get("content") or "").strip()
            if not txt:
                continue

            has_numeric = re.search(r"(^|\n)\s*\d+\s*[\).]", txt)
            has_abc = re.search(r"(^|\n)\s*\(?\s*[A-C]\s*\)?\s*[\).:-]", txt, flags=re.IGNORECASE)
            if has_numeric or has_abc:
                last = txt
                break
        except Exception:
            continue

    if not last:
        return []

    options: List[str] = []

    # Numeric options: 1) Title
    for line in last.splitlines():
        m = re.match(r"\s*(\d+)\s*[\).]\s*(.+?)\s*$", line)
        if not m:
            continue
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


def _match_selected_idea_title(user_text: str, options: List[str]) -> Optional[str]:
    """Return the matched option title if the user repeats/chooses it."""
    ut = _normalize_choice_text(user_text)
    if not ut or not options:
        return None

    # Handle "1" / "option 1" style selections
    m = re.search(r"\b(option\s*)?(\d)\b", ut)
    if m:
        idx = int(m.group(2)) - 1
        if 0 <= idx < len(options):
            return options[idx]

    for opt in options:
        o = _normalize_choice_text(opt)
        if not o:
            continue

        if o in ut or ut in o:
            return opt

        # token overlap heuristic
        o_tokens = [t for t in o.split() if len(t) >= 3]
        if not o_tokens:
            continue
        hit = sum(1 for t in o_tokens if t in ut)
        if hit >= max(2, int(len(o_tokens) * 0.6)):
            return opt

    return None


# -----------------------------
# Dialog continuity helpers (A/B/C routing)
# -----------------------------
def _get_last_assistant_text(chat_history: List[Dict[str, Any]]) -> str:
    if not chat_history:
        return ""
    for msg in reversed(chat_history):
        try:
            if (msg.get("role") or "").lower() == "assistant":
                return (msg.get("content") or "").strip()
        except Exception:
            continue
    return ""


def _match_selected_option(user_text: str, last_assistant_text: str) -> Dict[str, str]:
    """
    Routes schedule A/B/C (or plain A/B/C) based on what the last assistant message contained.

    Returns a dict:
      {"kind": "weekend_choice"|"time_choice"|"confirm_choice"|"none", "choice":"A|B|C"}

    NOTE: This does NOT execute anything. It only helps route the next prompt to stop loops.
    """
    res = {"kind": "none", "choice": ""}
    ut = (user_text or "").strip()
    if not ut:
        return res

    # Accept "schedule A" or just "A"
    m = re.search(r"\b(schedule\s*)?([A-C])\b", ut, flags=re.IGNORECASE)
    if not m:
        return res

    choice = m.group(2).upper()
    last = (last_assistant_text or "")

    # Detect time choice question (assistant offered A/B/C time windows)
    if re.search(r"\bwhat time\b|\btime works\b|\bstart time\b", last, flags=re.IGNORECASE):
        return {"kind": "time_choice", "choice": choice}

    # Detect confirm choice (assistant asked schedule it / change time / cancel)
    if re.search(r"\bschedule it\b|\bchange the time\b|\bcancel\b", last, flags=re.IGNORECASE):
        return {"kind": "confirm_choice", "choice": choice}

    # Detect weekend choice (assistant offered weekend outing A/B/C)
    if re.search(r"\bweekend\b|\bSaturday\b|\bSunday\b|\boutings?\b", last, flags=re.IGNORECASE):
        return {"kind": "weekend_choice", "choice": choice}

    # Default: if last assistant had (A)(B)(C), treat as generic selection (time_choice is safer loop-buster)
    if ("(A)" in last and "(B)" in last and "(C)" in last) or re.search(
        r"(^|\n)\s*\(?\s*[A-C]\s*\)?\s*[\).:-]", last, flags=re.IGNORECASE
    ):
        return {"kind": "time_choice", "choice": choice}

    return res


def _extract_last_assistant_question(chat_history: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    Best-effort extraction of the last assistant question for continuity:
    Returns dict: {"question_text": "...", "question_kind": "time|date|location|generic"}.
    """
    last = _get_last_assistant_text(chat_history)
    if not last:
        return None

    # Heuristic: pick a question-like sentence / line
    q_text = ""
    for line in reversed(last.splitlines()):
        line = line.strip()
        if "?" in line:
            q_text = line
            break
    if not q_text and "?" in last:
        q_text = last.strip()

    if not q_text:
        # also treat A/B/C prompts as questions
        if ("(A)" in last and "(B)" in last and "(C)" in last):
            q_text = last.strip()
        else:
            return None

    kind = "generic"
    lq = q_text.lower()
    if "time" in lq or "start" in lq:
        kind = "time"
    elif "date" in lq or "day" in lq or "tomorrow" in lq or "saturday" in lq or "sunday" in lq:
        kind = "date"
    elif "where" in lq or "location" in lq:
        kind = "location"

    return {"question_text": q_text, "question_kind": kind}


def _looks_like_answer(user_text: str, q_kind: str) -> bool:
    ut = (user_text or "").strip()
    if not ut:
        return False
    q_kind = (q_kind or "generic").lower()

    # If user replied with A/B/C or a simple token, treat as answer for continuity
    if re.fullmatch(r"(?i)(schedule\s*)?[A-C]", ut) or re.fullmatch(r"(?i)[A-C]", ut):
        return True

    # Time-ish answers
    if q_kind == "time":
        return bool(re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)?\b", ut, flags=re.IGNORECASE)) or bool(
            re.search(r"\bmorning\b|\bafternoon\b|\bevening\b|\btonight\b", ut, flags=re.IGNORECASE)
        )

    # Date-ish answers
    if q_kind == "date":
        return bool(
            re.search(r"\b(today|tomorrow|sat|saturday|sun|sunday|mon|tue|wed|thu|fri)\b", ut, flags=re.IGNORECASE)
        ) or bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", ut))

    # Generic: short replies likely answers
    return len(ut.split()) <= 6


# -----------------------------
# Event schema enforcement
# -----------------------------
def _default_end_time(start_dt: datetime.datetime, minutes: int = 60) -> datetime.datetime:
    return start_dt + datetime.timedelta(minutes=minutes)


def _parse_tomorrow_time(user_text: str, now: datetime.datetime) -> Optional[datetime.datetime]:
    """
    Very light parser used only for schema safety. The model is primary.
    Returns a datetime if we can parse "tomorrow 3pm" like patterns.
    """
    if not user_text:
        return None
    ut = user_text.lower()

    if "tomorrow" not in ut:
        return None

    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", ut)
    if not m:
        return None

    hour = int(m.group(1))
    minute = int(m.group(2) or "0")
    ampm = m.group(3).lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    tomorrow = now + datetime.timedelta(days=1)
    return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _ensure_event_schema(parsed: Dict[str, Any], user_request: str, now: datetime.datetime) -> Dict[str, Any]:
    """
    Enforce the exact output contract keys and coerce events to schema.
    """
    t = (parsed.get("type") or "chat").lower()
    if t not in {"plan", "conflict", "question", "confirmation", "chat", "error"}:
        t = "chat"

    txt = parsed.get("text")
    if not isinstance(txt, str):
        txt = str(txt) if txt is not None else ""

    pre_prep = parsed.get("pre_prep")
    if not isinstance(pre_prep, str):
        pre_prep = str(pre_prep) if pre_prep is not None else ""

    events_in = parsed.get("events")
    if not isinstance(events_in, list):
        events_in = []

    events_out: List[Dict[str, str]] = []
    for ev in events_in:
        if not isinstance(ev, dict):
            continue
        title = str(ev.get("title") or "")
        start_time = str(ev.get("start_time") or "")
        end_time = str(ev.get("end_time") or "")
        location = str(ev.get("location") or "")
        description = str(ev.get("description") or "")

        # If model gave no times but it tried to create an event, keep schema valid (but do not guess).
        # We only fill if we can parse a clear "tomorrow <time>" from user text as a safety fallback.
        if not start_time or not end_time:
            dt = _parse_tomorrow_time(user_request, now)
            if dt:
                start_time = dt.strftime("%Y-%m-%dT%H:%M:%S")
                end_time = _default_end_time(dt, 60).strftime("%Y-%m-%dT%H:%M:%S")
            else:
                # Keep empty strings (schema-valid). Flow/UI should gate execution anyway.
                start_time = start_time or ""
                end_time = end_time or ""

        events_out.append(
            {
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "description": description,
            }
        )

    return {"type": t, "text": txt, "pre_prep": pre_prep, "events": events_out}


# -----------------------------
# Weekend detection + regen
# -----------------------------
_WEEKEND_HINT_RE = re.compile(
    r"\b(weekend|this weekend|sat|saturday|sun|sunday|family day|outing|go out)\b", flags=re.IGNORECASE
)


def _is_weekend_outing_request(user_text: str) -> bool:
    return bool(_WEEKEND_HINT_RE.search(user_text or ""))


def _dead_end_output(parsed: Dict[str, Any], user_request: str = "") -> bool:
    """
    Heuristic safety gate: detect lazy / mirroring / non-actionable outputs.
    Signature MUST be stable for all call sites.
    """
    t = (parsed.get("type") or "").lower()
    txt = (parsed.get("text") or "").strip()

    if t == "error":
        return True
    if not txt:
        return True

    # Detect pure mirroring
    ut = (user_request or "").strip().lower()
    if ut and txt.lower() == ut:
        return True

    # Too short + non-informative
    if len(txt) < 10 and t in {"chat", "question"}:
        return True

    # "I can't" style dead ends
    if re.search(r"\b(can't|cannot|unable to)\b", txt.lower()) and t != "conflict":
        return True

    return False


def _regen_dynamic_weekend_options(
    client: Groq,
    model: str,
    user_request: str,
    current_location: Optional[str],
    memory_dump: str,
    ideas_dump: str,
) -> Dict[str, Any]:
    prompt = build_weekend_regen_prompt({
        "user_request": user_request,
        "current_location": current_location or "",
        "memory_dump": memory_dump or "[]",
        "ideas_dump": ideas_dump or "[]",
    })
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}],
        temperature=0.6,
        max_tokens=900,
        stream=False,
    )
    txt = (completion.choices[0].message.content or "").strip()
    parsed = _try_parse_json(txt) or {}
    return _ensure_event_schema(parsed, user_request, _get_tz_now())


# -----------------------------
# Misc helpers
# -----------------------------
def encode_image(image) -> str:
    """Encode a PIL image or raw bytes to base64 JPEG string."""
    if image is None:
        return ""
    try:
        # PIL Image
        import io

        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        try:
            # raw bytes
            return base64.b64encode(image).decode("utf-8")
        except Exception:
            return ""


def _user_provided_time(user_text: str) -> bool:
    return bool(re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", user_text or "", flags=re.IGNORECASE))


def _user_requested_multiple(user_text: str) -> bool:
    return bool(re.search(r"\b(two|three|multiple|few)\b", user_text or "", flags=re.IGNORECASE))


def _safe_json_dumps(obj: Any, default: str = "[]") -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return default


def _regen_safe_chat_no_scheduling(
    client: Groq,
    model: str,
    ctx: Dict[str, Any],
    user_request: str,
) -> Dict[str, Any]:
    """
    If model tries to push scheduling when user did not request it,
    regenerate a 'chat' response via LLM (no hardcoded user-facing text).
    """
    instruction = (
        "You must return STRICT JSON ONLY with keys: type,text,pre_prep,events.\n"
        "The user did NOT ask to schedule/add/plan anything.\n"
        "Return type='chat' with helpful suggestions and ONE short follow-up question.\n"
        "Do NOT ask the user which option to schedule.\n"
        "events must be an empty list.\n"
    )
    system_prompt = build_system_prompt(ctx)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": instruction},
        {"role": "user", "content": user_request or ""},
    ]
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.6,
        max_tokens=700,
        stream=False,
    )
    txt = (completion.choices[0].message.content or "").strip()
    parsed = _try_parse_json(txt)
    if not isinstance(parsed, dict):
        # Attempt repair once
        try:
            fixed = _repair_json_with_llm(client, model, txt)
            parsed = _try_parse_json(fixed)
        except Exception:
            parsed = None
    if not isinstance(parsed, dict):
        return {"type": "chat", "text": "", "pre_prep": "", "events": []}
    parsed = _ensure_event_schema(parsed, user_request, _get_tz_now())
    parsed["type"] = "chat"
    parsed["events"] = []
    return parsed


def _regen_time_question(
    client: Groq,
    model: str,
    ctx: Dict[str, Any],
    user_request: str,
) -> Dict[str, Any]:
    """
    If model produced a 'plan' with events but user didn't provide time,
    regenerate a single tight A/B/C time question (no hardcoded times in code).
    """
    instruction = (
        "You must return STRICT JSON ONLY with keys: type,text,pre_prep,events.\n"
        "The user wants scheduling but did NOT provide a specific start time.\n"
        "Return type='question'. Provide exactly 3 options labeled (A),(B),(C) with reasonable time windows.\n"
        "End the question with: Reply exactly: schedule A / schedule B / schedule C\n"
        "events must be an empty list.\n"
    )
    system_prompt = build_system_prompt(ctx)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": instruction},
        {"role": "user", "content": user_request or ""},
    ]
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.6,
        max_tokens=700,
        stream=False,
    )
    txt = (completion.choices[0].message.content or "").strip()
    parsed = _try_parse_json(txt)
    if not isinstance(parsed, dict):
        try:
            fixed = _repair_json_with_llm(client, model, txt)
            parsed = _try_parse_json(fixed)
        except Exception:
            parsed = None
    if not isinstance(parsed, dict):
        return {"type": "question", "text": "", "pre_prep": "", "events": []}
    parsed = _ensure_event_schema(parsed, user_request, _get_tz_now())
    parsed["type"] = "question"
    parsed["events"] = []
    return parsed


# -----------------------------
# Main entrypoint
# -----------------------------
def get_coo_response(
    api_key: str,
    user_request: str,
    memory: Optional[List[Dict[str, Any]]] = None,
    calendar_data: Optional[List[Dict[str, Any]]] = None,
    pending_events: Optional[List[Dict[str, Any]]] = None,
    current_location: Optional[str] = None,
    image_context: Any = None,
    image_obj: Any = None,  # alias used by flow.py
    chat_history: Optional[List[Dict[str, Any]]] = None,
    ideas_dump: str = "[]",
    ideas_summary: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Main Brain call. Returns STRICT JSON string only.

    NOTE: This function performs ONLY LLM calls + heuristics, no tool execution.
    """
    # Backward compatibility: flow.py passes image_obj
    if image_context is None and image_obj is not None:
        image_context = image_obj

    # Normalize None -> empty structures (type-safe)
    memory = memory or []
    calendar_data = calendar_data or []
    pending_events = pending_events or []
    chat_history = chat_history or []

    client = Groq(api_key=api_key)

    now = _get_tz_now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    cheat_sheet = _next_7_days_cheatsheet(now)
    next_saturday = _next_saturday_date(now)

    # -----------------------------
    # Route: option continuity (ideas + A/B/C)
    # -----------------------------
    idea_options = _extract_option_titles_from_history(chat_history)
    selected_idea = _match_selected_idea_title(user_request, idea_options) or ""

    # Dialog continuation: treat short replies as answers to last assistant question (prevents restarting)
    last_q = _extract_last_assistant_question(chat_history)
    continuation_hint = ""
    if last_q and _looks_like_answer(user_request, last_q.get("question_kind", "generic")):
        continuation_hint = (
            "DIALOG CONTINUATION:\n"
            f"- The assistant previously asked: {last_q.get('question_text','')}\n"
            f"- The user message is the answer: {user_request}\n"
            "INSTRUCTION: Treat the user message as an answer and continue; do not restart.\n"
        )

    # A/B/C selection mapping from last assistant message
    last_assistant_text = _get_last_assistant_text(chat_history)
    sel = _match_selected_option(user_request, last_assistant_text)
    if not isinstance(sel, dict):
        sel = {"kind": "none", "choice": ""}
    sel.setdefault("kind", "none")
    sel.setdefault("choice", "")

    # Loop-stopper: if user selects time options, mirror the chosen assistant line (no hardcoded times)
    if sel["kind"] == "time_choice" and sel["choice"]:
        try:
            patt = rf"\({sel['choice'].lower()}\)\s*([^()]+)"
            mm = re.search(patt, last_assistant_text, flags=re.IGNORECASE)
            if mm:
                picked = mm.group(1).strip().strip(".")
                if picked:
                    user_request = f"schedule {picked}"
        except Exception:
            pass

    # Confirm choice mapping (A/B/C -> intent words) without user-facing text
    if sel["kind"] == "confirm_choice" and sel["choice"]:
        if sel["choice"] == "A":
            user_request = "schedule it"
        elif sel["choice"] == "B":
            user_request = "change the time"
        elif sel["choice"] == "C":
            user_request = "cancel"

    # -----------------------------
    # Context for prompts
    # -----------------------------
    # Keep recent history small (prompt efficiency)
    history_txt = ""
    if chat_history:
        try:
            history_txt = "\n".join(
                [f"{(m.get('role','') or '').upper()}: {m.get('content','') or ''}" for m in chat_history[-6:]]
            )
        except Exception:
            history_txt = ""

    memory_dump = _safe_json_dumps(memory, default="[]")
    pending_dump = _safe_json_dumps(pending_events, default="[]")

    # Normalize ideas safely
    if ideas_summary is None:
        try:
            ideas_summary = json.loads(ideas_dump or "[]")
            if not isinstance(ideas_summary, list):
                ideas_summary = []
        except Exception:
            ideas_summary = []
    ideas_dump = _safe_json_dumps(ideas_summary, default="[]")

    ctx: Dict[str, Any] = {
        "current_time_str": current_time_str,
        "cheat_sheet": cheat_sheet,
        "next_saturday": next_saturday,
        "current_location": current_location,
        "calendar_data": calendar_data,
        "pending_dump": pending_dump,
        "memory_dump": memory_dump,
        "history_txt": history_txt,
        "idea_options": idea_options,
        "selected_idea": selected_idea,
        "continuation_hint": continuation_hint,
        "user_request": user_request,
        "ideas_summary": ideas_summary,
        "ideas_dump": ideas_dump,
    }

    # Optional: memory summary (safe, no file I/O assumptions)
    try:
        from src.utils import get_memory_summary_from_memory

        ctx["memory_summary"] = get_memory_summary_from_memory(memory, n=12)
    except Exception:
        ctx["memory_summary"] = []

    system_prompt = build_system_prompt(ctx)
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    # Greetings must NEVER trigger weekend routing or scheduling.
    # If the user didn't express scheduling intent, force a chat response (content generated by LLM, not hardcoded here).
    if _is_greeting(user_request) and (not _is_schedule_intent(user_request)) and (not _is_weekend_outing_request(user_request)):
        messages.append(
            {
                "role": "system",
                "content": (
                    "GREETING MODE: The user greeted you. "
                    "Return type='chat' with a friendly response and one short follow-up question. "
                    "Do NOT offer to schedule/add/plan anything. events must be an empty list."
                ),
            }
        )

    if image_context is not None:
        model = "llama-3.2-90b-vision-preview"
        base64_image = encode_image(image_context)
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_request or ""},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }
        )
    else:
        model = "llama-3.3-70b-versatile"
        messages.append({"role": "user", "content": user_request or ""})

    # -----------------------------
    # LLM call
    # -----------------------------
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.6,
            max_tokens=1024,
            stream=False,
        )
        raw_text = (completion.choices[0].message.content or "").strip()
    except Exception as e:
        return _strict_error_json(str(e))

    # -----------------------------
    # Parse + repair
    # -----------------------------
    parsed = _try_parse_json(raw_text)
    if not isinstance(parsed, dict):
        try:
            fixed = _repair_json_with_llm(client, model, raw_text)
            parsed = _try_parse_json(fixed)
        except Exception:
            parsed = None

    if not isinstance(parsed, dict):
        return _strict_error_json("I couldn't process that. Please try again.")

    # Enforce schema
    parsed = _ensure_event_schema(parsed, user_request, now)

    # -----------------------------
    # -----------------------------
    # Safety gate: prevent scheduling prompts when user didn't ask to schedule
    # -----------------------------
    if (not _is_weekend_outing_request(user_request)) and (not _is_schedule_intent(user_request)):
        # If assistant tries to push scheduling or time selection, regenerate as chat.
        if _looks_like_banned_scheduling_prompt(parsed.get("text", "")) or (parsed.get("type") in {"plan", "question", "confirmation", "conflict"} and "schedule" in (parsed.get("text") or "").lower()):
            safe_chat = _regen_safe_chat_no_scheduling(client, model, ctx, user_request)
            return json.dumps(safe_chat, ensure_ascii=False)

    t = (parsed.get("type") or "").lower()
    txt = (parsed.get("text") or "")
    events = parsed.get("events") or []

    # -----------------------------
    # Weekend enforcement: must be a clean A/B/C question; regen if weak
    # -----------------------------
    if _is_weekend_outing_request(user_request):
        has_abc = ("(A)" in txt and "(B)" in txt and "(C)" in txt)
        if _dead_end_output(parsed, user_request=user_request) or (t != "question") or (not has_abc):
            regen = _regen_dynamic_weekend_options(
                client=client,
                model=model,
                user_request=user_request,
                current_location=current_location,
                memory_dump=memory_dump,
                ideas_dump=ideas_dump,
            )
            return json.dumps(regen, ensure_ascii=False)

    # -----------------------------
    # Prevent guessed-time scheduling (plan with events but user didn't specify time)
    # -----------------------------
    if t == "plan" and events:
        if not _user_provided_time(user_request) and not _user_requested_multiple(user_request):
            q = _regen_time_question(client, model, ctx, user_request)
            return json.dumps(q, ensure_ascii=False)

    # Final return (STRICT JSON only)
    return json.dumps(parsed, ensure_ascii=False)
