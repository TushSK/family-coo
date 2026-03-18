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
from datetime import timedelta
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.llm_router import LLMRouter

# NOTE: Model constants and provider selection live in src/llm_router.py only.
# To upgrade/swap models: edit llm_router.py — never this file.

from src.prompts import (
    build_json_repair_prompt,
    build_system_prompt,
    build_weekend_regen_prompt,
)

_FINAL_REPLY_LINE = ""
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

def _format_abc_text_for_ui(text: str) -> str:
    """
    Simplified UI formatter.
    Relies on the prompt template being correct instead of regex guessing.
    """
    if not text:
        return text

    t = text.strip()

    # Force A/B/C headers to start as separate paragraphs
    t = re.sub(r"\s*\(A\)\s*", "\n\n(A) ", t)
    t = re.sub(r"\s*\(B\)\s*", "\n\n(B) ", t)
    t = re.sub(r"\s*\(C\)\s*", "\n\n(C) ", t)

    # Strip "Reply exactly" line — options are tappable cards, not typed replies
    t = re.sub(r"\n*Reply exactly:\s*schedule\s*[A-C][^\n]*", "", t, flags=re.IGNORECASE)

    # Remove "(Optional: ...)" lines
    t = re.sub(r"\n*\(Optional:[^\n]*\)", "", t, flags=re.IGNORECASE)

    # Clean excess blank lines
    t = re.sub(r"\n{3,}", "\n\n", t)

    return t.strip()

def _format_plan_text_from_event(parsed: dict) -> str:
    """
    Deterministic Draft-ready text built ONLY from events[0]
    using Streamlit-friendly Markdown.
    """
    evs = parsed.get("events") or []
    if not evs or not isinstance(evs[0], dict):
        return (parsed.get("text") or "").strip() or "Draft ready. Review in Drafting and click Add."

    ev = evs[0]
    title = (ev.get("title") or "Draft event").strip()
    start_time = (ev.get("start_time") or "").replace("T", " ")[:16] # clean ISO string
    end_time = (ev.get("end_time") or "").replace("T", " ")[11:16]
    location = (ev.get("location") or "").strip()

    text = f"✅ **Draft ready**\n\n**{title}**\n\n"
    if start_time:
        text += f"📅 {start_time} – {end_time}\n\n"
    if location:
        text += f"📍 Location: {location}\n\n"
    text += "*Review in Drafting and click Add.*"

    return text

def _finalize_for_ui(parsed: dict) -> dict:
    """
    Single deterministic final pass for ALL outputs:
    - Never allow empty visible text
    - Apply correct formatting by type
    - Ensure reply-line exists when A/B/C exists
    - CRITICAL: do NOT wipe plan events just because text is empty
    """
    if not isinstance(parsed, dict):
        return {
            "type": "chat",
            "text": "Tell me what you’d like to do (e.g., ‘plan a park visit Saturday after 11am’).",
            "pre_prep": "",
            "events": [],
        }

    # Required keys (schema guard)
    parsed.setdefault("type", "chat")
    parsed.setdefault("text", "")
    parsed.setdefault("pre_prep", "")
    parsed.setdefault("events", [])

    t = (parsed.get("type") or "").lower()
    events = parsed.get("events") or []

    # If this is a plan with events, ALWAYS generate deterministic draft text
    # even if model text is empty.
    if t == "plan" and isinstance(events, list) and len(events) > 0:
        parsed["text"] = _format_plan_text_from_event(parsed)  # uses events[0]
        # Do not modify events

    # For non-plan: never allow empty visible text
    if not (parsed.get("text") or "").strip():
        # Keep it safe: no scheduling push here
        parsed["type"] = "chat"
        parsed["text"] = "Tell me what you’d like to do (e.g., ‘plan a park visit Saturday after 11am’)."
        parsed["pre_prep"] = parsed.get("pre_prep") or ""
        parsed["events"] = []

    t = (parsed.get("type") or "").lower()

    # Apply A/B/C formatting ONLY to question/conflict
    if t in ("question", "conflict"):
        parsed["text"] = _format_abc_text_for_ui(parsed.get("text", ""))

    # Strip "Reply exactly: schedule A / B / C" from displayed text —
    # options are now tappable cards so this instruction is UI noise.
    txt = parsed.get("text") or ""
    txt = re.sub(r"\n*Reply exactly:\s*schedule\s*[A-C][^\n]*", "", txt, flags=re.IGNORECASE).strip()
    txt = re.sub(r"\n*\(Optional:.*?\)", "", txt, flags=re.IGNORECASE | re.DOTALL).strip()
    if txt:
        parsed["text"] = txt

    return parsed


def _dump_final(parsed: dict) -> str:
    """Always return through finalizer (prevents bypass bugs)."""
    parsed = _finalize_for_ui(parsed)
    return json.dumps(parsed, ensure_ascii=False)


def _is_rate_limited(err: Exception) -> bool:
    """Delegates to LLMRouter so rate-limit detection lives in one place."""
    return LLMRouter.is_rate_limited_static(err)


# ---------------------------------------------------------------------------
# Single thin wrapper — every LLM call goes through here.
# Signature mirrors the old Groq pattern so call sites stay minimal.
# ---------------------------------------------------------------------------
def _llm_call(
    router: "LLMRouter",
    system: str,
    user: str,
    temperature: float = 0.6,
    max_tokens: int = 900,
    task: str = "regen",
) -> str:
    """
    Thin wrapper used by all regen helpers.
    `task` matches a key in llm_router.ROUTING_TABLE.
    Default task="regen" → routes to Claude.
    """
    return router.call(task, system=system, user=user, temperature=temperature, max_tokens=max_tokens)


def _option_to_event(option: Dict[str, Any], now_dt) -> Dict[str, str] | None:
    """
    Deterministic conversion from OPTIONS_JSON item -> event schema.
    Expects option keys: title, time_window, duration_hours (as in prompts.py).
    """
    try:
        title = (option.get("title") or "").strip()
        tw = (option.get("time_window") or "").strip()
        dur = float(option.get("duration_hours") or 0)

        if not title or not tw or dur <= 0:
            return None

        # tw example: "Sat 9:00 AM–12:00 PM"
        # Split day+times safely
        # Supports hyphen variants: – —
        tw_norm = tw.replace("—", "–").replace("-", "–")
        if "–" not in tw_norm:
            return None

        left, right = [x.strip() for x in tw_norm.split("–", 1)]

        # left includes day + start time: "Sat 9:00 AM"
        parts = left.split()
        if len(parts) < 2:
            return None

        day = parts[0]  # Sat/Sun
        start_time_txt = " ".join(parts[1:])
        end_time_txt = right

        # Anchor date: next Sat/Sun from now
        # Uses existing helper _next_saturday_date(now) already in brain
        next_sat = _next_saturday_date(now_dt)
        # next_sat is a string in your code; convert to date via dateutil parser if available
        try:
            from dateutil import parser as dtparser
            sat_date = dtparser.parse(next_sat).date()
        except Exception:
            sat_date = now_dt.date()

        if day.lower().startswith("sun"):
            base_date = sat_date + timedelta(days=1)
        else:
            base_date = sat_date

        # Parse times
        try:
            from dateutil import parser as dtparser
            st = dtparser.parse(start_time_txt)
            et = dtparser.parse(end_time_txt)
        except Exception:
            return None

        start_dt = datetime.datetime(
            base_date.year, base_date.month, base_date.day,
            st.hour, st.minute, 0,
            tzinfo=now_dt.tzinfo,
        )
        end_dt = datetime.datetime(
            base_date.year, base_date.month, base_date.day,
            et.hour, et.minute, 0,
            tzinfo=now_dt.tzinfo,
        )

        # Safety: if end <= start, add duration hours
        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(hours=dur)

        return {
            "title": title,
            "start_time": start_dt.replace(microsecond=0).isoformat(),
            "end_time": end_dt.replace(microsecond=0).isoformat(),
            "location": "",
            "description": (option.get("notes") or "").strip(),
        }
    except Exception:
        return None

def _extract_schedule_choice(user_text: str) -> str:
    """Mirroring the updated flow.py logic for continuity."""
    t = (user_text or "").strip().lower()
    m = re.search(r"\b(?:option\s+|schedule\s+|plan\s+|choose\s+|let\'s do\s+)?([a-c])\b", t)
    return m.group(1).upper() if m else ""

# Broaden intent to include choosing an option
_SCHEDULE_INTENT_RE = re.compile(r"\b(schedule|add|plan|book|create|visit|option|choose)\b", flags=re.IGNORECASE)

_FINAL_SCHEDULE_RE = re.compile(r"(?i)^\s*(?:schedule|plan|add|option|choose)?\s*([A-C])\s*$")

def _is_schedule_choice(user_text: str) -> bool:
    return bool(_FINAL_SCHEDULE_RE.match((user_text or "").strip()))

def _assistant_has_time_choice_prompt(text: str) -> bool:
    t = text or ""
    has_reply_exactly = "reply exactly" in t.lower() and "schedule a" in t.lower() and "schedule b" in t.lower()
    # time range like "10:00 AM - 2:00 PM"
    has_time_range = bool(re.search(r"\b\d{1,2}:\d{2}\s*(AM|PM)\s*-\s*\d{1,2}:\d{2}\s*(AM|PM)\b", t, flags=re.IGNORECASE))
    return has_reply_exactly and has_time_range


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


def _repair_json_with_llm(router: "LLMRouter", model: str, bad_text: str) -> str:
    """Uses Groq (fast/cheap) to repair malformed JSON — see llm_router.ROUTING_TABLE."""
    repair_prompt = build_json_repair_prompt(bad_text)
    try:
        return router.call("repair", system=repair_prompt, user="Fix the JSON.", temperature=0.0, max_tokens=900)
    except Exception as e:
        if _is_rate_limited(e):
            return bad_text  # deterministic: no extra LLM calls under 429
        raise



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


def _match_selected_idea_title(user_text: str, options) -> Optional[str]:
    """Return the matched option title if the user repeats/chooses it.
    options may be List[str] OR List[dict] (with 'title' key) — handles both.
    """
    ut = _normalize_choice_text(user_text)
    if not ut or not options:
        return None

    # Handle "1" / "option 1" style selections
    m = re.search(r"\b(option\s*)?(\d)\b", ut)
    if m:
        idx = int(m.group(2)) - 1
        if 0 <= idx < len(options):
            raw = options[idx]
            return raw.get("title", "") if isinstance(raw, dict) else raw

    for opt in options:
        # Extract display title regardless of whether opt is str or dict
        title_str = opt.get("title", "") if isinstance(opt, dict) else (opt or "")
        o = _normalize_choice_text(title_str)
        if not o:
            continue

        if o in ut or ut in o:
            return title_str

        # token overlap heuristic
        o_tokens = [t for t in o.split() if len(t) >= 3]
        if not o_tokens:
            continue
        hit = sum(1 for t in o_tokens if t in ut)
        if hit >= max(2, int(len(o_tokens) * 0.6)):
            return title_str

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

    # --- Priority 1: weekend outing (check BEFORE generic A/B/C fallback) ---
    # Claude's weekend response always contains Saturday/Sunday/weekend — match that first
    if re.search(r"\bweekend\b|\bSaturday\b|\bSunday\b|\bouting\b|pick one\b", last, flags=re.IGNORECASE):
        return {"kind": "weekend_choice", "choice": choice}

    # --- Priority 2: confirm choice (schedule it / change time / cancel) ---
    if re.search(r"\bschedule it\b|\bchange the time\b|\bcancel\b", last, flags=re.IGNORECASE):
        return {"kind": "confirm_choice", "choice": choice}

    # --- Priority 3: time window question ---
    if re.search(r"\bwhat time\b|\btime works\b|\bstart time\b|\btime window\b", last, flags=re.IGNORECASE):
        return {"kind": "time_choice", "choice": choice}

    # --- Fallback: generic A/B/C list → time_choice (safe loop-buster) ---
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


def _extract_shown_idea_titles(chat_history: List[Dict[str, Any]]) -> List[str]:
    """Return all A/B/C option titles shown in chat history (to avoid repeating)."""
    titles: List[str] = []
    for msg in (chat_history or []):
        try:
            if (msg.get("role") or "").lower() != "assistant":
                continue
            for m in re.finditer(r"\([A-C]\)\s+([^\n]+)", msg.get("content") or ""):
                t = m.group(1).strip()
                if t and t.lower() != "custom" and len(t) > 3 and t not in titles:
                    titles.append(t)
        except Exception:
            continue
    return titles


def _regen_dynamic_weekend_options(
    router: "LLMRouter",
    model: str,
    user_request: str,
    current_location: Optional[str],
    memory_dump: str,
    ideas_dump: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    missions_dump: str = "[]",
    feedback_dump: str = "[]",
) -> Dict[str, Any]:
    avoid_ideas = _extract_shown_idea_titles(chat_history or [])
    prompt = build_weekend_regen_prompt({
        "user_request": user_request,
        "current_location": current_location or "",
        "memory_dump": memory_dump or "[]",
        "ideas_dump": ideas_dump or "[]",
        "avoid_ideas": avoid_ideas,
        "missions_dump": missions_dump,
        "feedback_dump": feedback_dump,
    })

    try:
        txt = _llm_call(router, system=prompt, user=user_request or "Weekend outing ideas", temperature=0.6, max_tokens=900)
        parsed = _try_parse_json(txt) or {}
        parsed = _ensure_event_schema(parsed, user_request, _get_tz_now())
        parsed["type"] = "question"
        parsed["events"] = []
        return parsed

    except Exception as e:
        # Deterministic fallback under 429 or any upstream fail
        if _is_rate_limited(e):
            fallback_text = (
                "Weekend outing — pick one:\n\n"
                "(A) Park walk + snacks\n"
                "    Duration: 2 hours\n"
                "    Time window: Sat 11:00 AM–1:00 PM\n\n"
                "(B) Family board games at home\n"
                "    Duration: 2 hours\n"
                "    Time window: Sat 4:00 PM–6:00 PM\n\n"
                "(C) Local library + treat after\n"
                "    Duration: 2 hours\n"
                "    Time window: Sun 12:00 PM–2:00 PM\n\n"
                ""
        )
            return {"type": "question", "text": fallback_text, "pre_prep": "", "events": []}
        raise


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
    router: "LLMRouter",
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
    combined_system = system_prompt + "\n\n" + instruction
    txt = _llm_call(router, system=combined_system, user=user_request or " ", temperature=0.7, max_tokens=700)
    parsed = _try_parse_json(txt)
    if not isinstance(parsed, dict):
        # Attempt repair once
        try:
            fixed = _repair_json_with_llm(router, model, txt)
            parsed = _try_parse_json(fixed)
        except Exception:
            parsed = None
    if not isinstance(parsed, dict):
        return {"type": "chat", 
                "text": "I’m here. Tell me what you want to do (e.g., ‘plan a park visit Saturday after 11am’ or ‘suggest weekend ideas’).", 
                "pre_prep": "", 
                "events": []}
    parsed = _ensure_event_schema(parsed, user_request, _get_tz_now())
    parsed["type"] = "chat"
    parsed["events"] = []
    return parsed


def _regen_time_question(
    router: "LLMRouter",
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
                "events must be an empty list.\n"
    )
    system_prompt = build_system_prompt(ctx)
    combined_system = system_prompt + "\n\n" + instruction
    txt = _llm_call(router, system=combined_system, user=user_request or " ", temperature=0.6, max_tokens=700)
    parsed = _try_parse_json(txt)
    if not isinstance(parsed, dict):
        try:
            fixed = _repair_json_with_llm(router, model, txt)
            parsed = _try_parse_json(fixed)
        except Exception:
            parsed = None
    
    if not isinstance(parsed, dict):
        fallback_text = (
            "Pick a time window:\n\n"
            "(A) Morning — 10:00 AM - 12:00 PM\n"
            "(B) Afternoon — 2:00 PM - 4:00 PM\n"
            "(C) Evening — 6:00 PM - 8:00 PM\n\n"
            ""
        )
        return {"type": "question", "text": fallback_text, "pre_prep": "", "events": []}
    
    
    parsed = _ensure_event_schema(parsed, user_request, _get_tz_now())
    parsed["type"] = "question"
    parsed["events"] = []
    return parsed




def _regen_force_plan_direct(
    router: "LLMRouter",
    model: str,
    ctx: Dict[str, Any],
    user_request: str,
) -> Dict[str, Any]:
    """
    BUG-09: When user provides title + day + time, skip all follow-up questions
    and create the draft directly. Location defaults to empty if not specified.
    """
    instruction = (
        "You must return STRICT JSON ONLY with keys: type,text,pre_prep,events.\n"
        "The user has provided all required information (title, day, and time).\n"
        "Return type='plan' with exactly ONE event in events[].\n"
        "Use an empty string for location if none was specified — do NOT ask for it.\n"
        "The event MUST include non-empty start_time and end_time in format YYYY-MM-DDTHH:MM:SS.\n"
        "Do NOT ask any follow-up questions. Create the draft immediately.\n"
    )
    system_prompt = build_system_prompt(ctx)
    combined_system = system_prompt + "\n\n" + instruction
    txt = _llm_call(router, system=combined_system, user=user_request or " ", temperature=0.3, max_tokens=700)
    parsed = _try_parse_json(txt)
    if not isinstance(parsed, dict):
        try:
            fixed = _repair_json_with_llm(router, model, txt)
            parsed = _try_parse_json(fixed)
        except Exception:
            parsed = None
    if not isinstance(parsed, dict):
        return {"type": "chat", "text": "I couldn't create that event. Please try again.", "pre_prep": "", "events": []}
    parsed = _ensure_event_schema(parsed, user_request, _get_tz_now())
    parsed["type"] = "plan"
    return parsed


def _regen_force_plan_from_selection(
    router: "LLMRouter",
    model: str,
    ctx: Dict[str, Any],
    user_request: str,
    selection_summary: str,
) -> Dict[str, Any]:
    instruction = (
        "You must return STRICT JSON ONLY with keys: type,text,pre_prep,events.\n"
        "The user has CONFIRMED a specific selection and expects the event to be drafted now.\n"
        "Return type='plan' with exactly ONE event in events[].\n"
        "The event MUST include non-empty start_time and end_time in format YYYY-MM-DDTHH:MM:SS.\n"
        "Do NOT ask follow-up questions.\n"
        f"Selection: {selection_summary}\n"
    )

    system_prompt = build_system_prompt(ctx)
    combined_system = system_prompt + "\n\n" + instruction

    try:
        txt = _llm_call(router, system=combined_system, user=user_request or " ", temperature=0.3, max_tokens=700)
        parsed = _try_parse_json(txt)

        if not isinstance(parsed, dict):
            try:
                fixed = _repair_json_with_llm(router, model, txt)
                parsed = _try_parse_json(fixed)
            except Exception:
                parsed = None

        if not isinstance(parsed, dict):
            # Fallback MUST be a question (not empty error), so UI stays usable and no blank bubbles
            fallback_text = (
                "Pick a time window:\n\n"
                "(A) Morning — 10:00 AM - 12:00 PM\n"
                "(B) Afternoon — 2:00 PM - 4:00 PM\n"
                "(C) Evening — 6:00 PM - 8:00 PM\n\n"
                ""
            )
            return {"type": "question", "text": fallback_text, "pre_prep": "", "events": []}

        parsed = _ensure_event_schema(parsed, user_request, _get_tz_now())
        parsed["type"] = "plan"

        # If model failed to provide times, do ONE deterministic retry (already in your file)
        # ... keep your existing retry block, but ensure any failure returns the same fallback question above.

        return parsed

    except Exception as e:
        if _is_rate_limited(e):
            # Deterministic fallback on 429 (no extra calls, no empty text)
            fallback_text = (
                "Pick a time window:\n\n"
                "(A) Morning — 10:00 AM - 12:00 PM\n"
                "(B) Afternoon — 2:00 PM - 4:00 PM\n"
                "(C) Evening — 6:00 PM - 8:00 PM\n\n"
                ""
            )
            return {"type": "question", "text": fallback_text, "pre_prep": "", "events": []}
        raise
# -----------------------------
# Main entrypoint
# -----------------------------

def _parse_abc_options_from_text(text: str, now_dt: datetime.datetime) -> List[Dict[str, Any]]:
    """
    Fallback parser: extract A/B/C options from formatted assistant text.
    Returns list of option dicts compatible with _option_to_event.
    Used when OPTIONS_JSON is missing from pre_prep.
    """
    options = []
    if not text:
        return options
    # Pattern: (A) Title\n    When: Day/Date • HH:MM AM – HH:MM PM\n    Where: ...
    blocks = re.split(r"(?=\n?\s*\([A-C]\))", text)
    for block in blocks:
        m_key = re.search(r"\(([A-C])\)\s*(.+?)(?:\n|$)", block, re.IGNORECASE)
        if not m_key:
            continue
        key = m_key.group(1).upper()
        title = m_key.group(2).strip()
        # Extract time window: supports "When:", "Time window:", and "Time:" prefixes
        # Covers: Claude live output ("When:"), rate-limit fallback ("Time window:")
        m_when = re.search(
            r"(?:When|Time\s+window|Time):\s*(.+?)(?:\n|$)",
            block, re.IGNORECASE
        )
        if not m_when:
            continue
        when_str = m_when.group(1).strip()
        # Extract Where
        m_where = re.search(r"Where:\s*(.+?)(?:\n|$)", block, re.IGNORECASE)
        location = m_where.group(1).strip() if m_where else ""
        # Extract Notes
        m_notes = re.search(r"Notes:\s*(.+?)(?:\n|$)", block, re.IGNORECASE)
        notes = m_notes.group(1).strip() if m_notes else ""
        # Fallback: use Duration: as a hint when time can't be parsed from when_str
        m_dur_hint = re.search(r"Duration:\s*(\d+(?:\.\d+)?)\s*hour", block, re.IGNORECASE)
        dur_hint = float(m_dur_hint.group(1)) if m_dur_hint else 0

        # Convert when_str to _option_to_event-compatible time_window
        # Handles 3 formats:
        #   "Saturday, March 7 • 9:00 AM – 12:00 PM"  (Claude live)
        #   "Sat 9:00 AM–12:00 PM"                     (compact)
        #   "Sat 11:00 AM–1:00 PM"                     (rate-limit fallback)
        m_bullet = (
            re.search(
                r"(Sat|Sun|Saturday|Sunday)[^•]*•\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\s*[–\-]\s*(\d{1,2}:\d{2}\s*(?:AM|PM))",
                when_str, re.IGNORECASE
            ) or
            re.search(
                r"(Sat|Sun)[a-z]*\s+(\d{1,2}:\d{2}\s*(?:AM|PM))\s*[–\-]\s*(\d{1,2}:\d{2}\s*(?:AM|PM))",
                when_str, re.IGNORECASE
            )
        )

        if not m_bullet:
            continue

        day_str = m_bullet.group(1)[:3].capitalize()  # "Sat" or "Sun"
        start_t = m_bullet.group(2).strip()
        end_t   = m_bullet.group(3).strip()
        time_window = f"{day_str} {start_t}–{end_t}"

        # Estimate duration
        try:
            from dateutil import parser as _dtp
            st_dt = _dtp.parse(start_t)
            et_dt = _dtp.parse(end_t)
            calc_dur = (et_dt - st_dt).seconds / 3600
            if calc_dur <= 0 and dur_hint > 0:
                dur = dur_hint
            else:
                dur = max(1, round(calc_dur, 1))
        except Exception:
            dur = dur_hint if dur_hint > 0 else 2

        options.append({
            "key": key,
            "title": title,
            "time_window": time_window,
            "duration_hours": dur,
            "notes": notes,
            "location": location,
        })

    return options

def get_coo_response(
    api_key: str,
    user_request: str,
    groq_key: str = "",     # Groq key for JSON repair + fallback
    memory: Optional[List[Dict[str, Any]]] = None,
    calendar_data: Optional[List[Dict[str, Any]]] = None,
    pending_events: Optional[List[Dict[str, Any]]] = None,
    current_location: Optional[str] = None,
    image_context: Any = None,
    image_obj: Any = None,  # alias used by flow.py
    chat_history: Optional[List[Dict[str, Any]]] = None,
    ideas_dump: str = "[]",
    ideas_summary: Optional[List[Dict[str, Any]]] = None,
    idea_options: Optional[List[Dict[str, Any]]] = None,
    selected_idea: str = "",
    missions_dump: str = "[]",
    feedback_dump: str = "[]",
) -> str:
    """
    Main Brain call. Returns STRICT JSON string only.

    NOTE: This function performs ONLY LLM calls + heuristics, no tool execution.
    """
    # Backward compatibility: flow.py passes image_obj
    if image_context is None and image_obj is not None:
        image_context = image_obj

    # Keep the exact original user input for intent checks (do not mutate)
    original_user_request = (user_request or '').strip()

    # Normalize None -> empty structures (type-safe)
    memory = memory or []
    calendar_data = calendar_data or []
    pending_events = pending_events or []
    chat_history = chat_history or []

    router = LLMRouter(anthropic_key=api_key, groq_key=groq_key or "")

    now = _get_tz_now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    cheat_sheet = _next_7_days_cheatsheet(now)
    next_saturday = _next_saturday_date(now)

    # -----------------------------
    # Route: option continuity (ideas + A/B/C)
    # Prefer flow-provided persisted options for determinism.
    # -----------------------------
    # Resolve last assistant message early — used by both idea_options fallback and sel detection
    last_assistant_text = _get_last_assistant_text(chat_history)

    idea_options = idea_options or []
    if not isinstance(idea_options, list) or not idea_options:
        # fallback to history parsing only if flow didn't provide options
        idea_options = _extract_option_titles_from_history(chat_history)

    # Secondary fallback: if idea_options still empty but last assistant message had
    # A/B/C blocks with When/Where, parse them directly so schedule A works reliably
    if not idea_options and last_assistant_text:
        parsed_opts = _parse_abc_options_from_text(last_assistant_text, now)
        if parsed_opts:
            idea_options = parsed_opts

    # Normalise: ensure every item in idea_options is a dict (not a bare string).
    # _extract_option_titles_from_history returns List[str]; all other paths return List[dict].
    _LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    idea_options = [
        opt if isinstance(opt, dict)
        else {"key": _LETTERS[i] if i < len(_LETTERS) else str(i+1),
              "title": str(opt), "time_window": "", "duration_hours": 0,
              "notes": "", "location": ""}
        for i, opt in enumerate(idea_options)
    ]

    selected_idea = (selected_idea or "").strip()
    if not selected_idea:
        # fallback heuristic match
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

    # A/B/C selection mapping from last assistant message (last_assistant_text already set above)
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
                    picked_clean = picked
                    # Remove trailing instruction text that can confuse the planner
                    for cut in ['Reply exactly', 'Reply']:
                        if cut in picked_clean:
                            picked_clean = picked_clean.split(cut, 1)[0].strip()
                    picked_clean = picked_clean.rstrip(' .?')
                    user_request = f"schedule {picked_clean}"
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

    # Weekend choice: user picked A/B/C from a weekend outing list.
    # If idea_options are available, convert directly to a plan — no LLM call needed.
    if sel["kind"] == "weekend_choice" and sel["choice"] and idea_options:
        for opt in idea_options:
            if not isinstance(opt, dict):
                continue
            if (opt.get("key") or "").strip().upper() == sel["choice"].upper():
                ev = _option_to_event(opt, now)
                if ev and ev.get("start_time"):
                    plan = {
                        "type": "plan",
                        "text": "",        # _finalize_for_ui fills this from event
                        "pre_prep": "",
                        "events": [ev],
                    }
                    return _dump_final(plan)
                break
        # If _option_to_event failed (bad time_window), ask brain to force a plan
        # NOTE: do NOT include words like "outing/weekend" — that re-triggers the weekend flow
        user_request = f"Please create a calendar event for option {sel['choice']} that I just selected."

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

    # Count question turns already shown (for 3-turn max enforcement)
    _turn_count = sum(
        1 for m in (chat_history or [])
        if (m.get("role") == "assistant") and ("(A)" in (m.get("content") or ""))
    )
    # Titles already shown to avoid repeating in new suggestions
    _avoid_shown = _extract_shown_idea_titles(chat_history or [])

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
        "missions_dump": missions_dump,
        "feedback_dump": feedback_dump,
        "avoid_ideas": _avoid_shown,
        "turn_count": _turn_count,
    }

    # Memory summary — expanded to n=20 so all profile fields reach the AI.
    # With the flattened dict format from _get_user_memory(), each preference
    # (cuisine, interests, family, fitness, etc.) now occupies one slot.
    try:
        from src.utils import get_memory_summary_from_memory
        ctx["memory_summary"] = get_memory_summary_from_memory(memory, n=20)
    except Exception:
        ctx["memory_summary"] = []

    system_prompt = build_system_prompt(ctx)

    # Greetings must NEVER trigger weekend routing or scheduling.
    if _is_greeting(user_request) and (not _is_schedule_intent(user_request)) and (not _is_weekend_outing_request(user_request)):
        system_prompt += (
            "\n\nGREETING MODE: The user greeted you. "
            "Return type='chat' with a friendly response and one short follow-up question. "
            "Do NOT offer to schedule/add/plan anything. events must be an empty list."
        )

    # model is passed to helpers for signature compat (router handles actual model selection)
    model = "router"

    # user_content: str for text turns; list for vision (router handles encoding)
    user_content = user_request or " "

    # -----------------------------
    # LLM call
    # -----------------------------
    try:
        image_b64 = encode_image(image_context) if image_context is not None else None
        raw_text = router.call(
            "brain",
            system=system_prompt,
            user=user_content if isinstance(user_content, str) else (user_request or " "),
            temperature=0.6,
            max_tokens=1024,
            image_b64=image_b64,
        )
        if not raw_text:
            raise ValueError("Empty response from router")
    except Exception as e:
        if _is_rate_limited(e):
            return json.dumps(
                {
                    "type": "chat",
                    "text": "I'm getting rate-limited right now. Please resend your last message in ~30 seconds.",
                    "pre_prep": "",
                    "events": [],
                },
                ensure_ascii=False,
            )
        return _strict_error_json(str(e))


    # -----------------------------
    # Parse + repair
    # -----------------------------
    parsed = _try_parse_json(raw_text)
    if not isinstance(parsed, dict):
        try:
            fixed = _repair_json_with_llm(router, model, raw_text)
            parsed = _try_parse_json(fixed)
        except Exception:
            parsed = None

    if not isinstance(parsed, dict):
        return _strict_error_json("I couldn't process that. Please try again.")

    # Enforce schema
    parsed = _ensure_event_schema(parsed, user_request, now)

    # Deterministic drafting: if user selected a time option and model didn't emit a plan/events, force a plan regen.
    try:
        # Deterministic draft enforcement: if user selects a time option (schedule A/B/C)
        # but the model returns chat/confirmation or empty events, force a one-shot regen to a plan+events.
        # This also covers cases where sel.kind fails to detect time_choice but the last assistant message
        # clearly contains a time window A/B/C list.
        _m_choice = re.search(r"\b(schedule\s*)?([A-C])\b", original_user_request, flags=re.IGNORECASE)
        _choice_letter = (_m_choice.group(2).upper() if _m_choice else (sel.get('choice') or '')).upper()
        _looks_like_time_list = bool(
            re.search(r"\b(time window|time slot|start time|what time|time works)\b", last_assistant_text, flags=re.IGNORECASE)
            and re.search(r"\(A\).*\(B\).*\(C\)", last_assistant_text, flags=re.IGNORECASE | re.DOTALL)
        )
        _is_time_choice = bool(
            (_choice_letter and sel.get('kind') == 'time_choice') or (_choice_letter and _looks_like_time_list)
        )
        if _is_time_choice and _choice_letter and _is_schedule_intent(original_user_request):
            if (parsed.get('type') != 'plan') or (not parsed.get('events')):
                selection_summary = f"User chose time option {_choice_letter} from the last assistant time window list. Last assistant time list: {last_assistant_text}"
                forced = _regen_force_plan_from_selection(router, model, ctx, original_user_request, selection_summary)
                return _dump_final(forced)
    except Exception:
        pass

    # If user explicitly chose schedule A/B/C and we have idea_options,
    # enforce a real plan event even if the LLM forgot events[].
    choice = _extract_schedule_choice(original_user_request)
    if choice and isinstance(idea_options, list) and idea_options:
        if (parsed.get("type") != "plan") or (not (parsed.get("events") or [])):
            picked = None
            for opt in idea_options:
                if not isinstance(opt, dict):
                    continue
                if (opt.get("key") or "").strip().upper() == choice.upper():
                    picked = opt
                    break

            if picked:
                ev = _option_to_event(picked, now)
                if ev and ev.get("start_time"):
                    parsed["type"] = "plan"
                    parsed["events"] = [ev]
    

    # -----------------------------
    # -----------------------------
    # Safety gate: prevent scheduling prompts when user didn't ask to schedule
    # -----------------------------
    if (not _is_weekend_outing_request(user_request)) and (not _is_schedule_intent(user_request)):
        # If assistant tries to push scheduling or time selection, regenerate as chat.
        if _looks_like_banned_scheduling_prompt(parsed.get("text", "")) or (parsed.get("type") in {"plan", "question", "confirmation", "conflict"} and "schedule" in (parsed.get("text") or "").lower()):
            safe_chat = _regen_safe_chat_no_scheduling(router, model, ctx, user_request)
            return _dump_final(safe_chat)

    t = (parsed.get("type") or "").lower()
    txt = (parsed.get("text") or "")
    events = parsed.get("events") or []

    # -----------------------------
    # Weekend enforcement: must be a clean A/B/C question; regen if weak
    # BUG-13: Exempt direct schedule requests that mention Saturday/Sunday
    # (e.g. "plan lab work on Saturday at 8am") — those have full intent+time,
    # they are NOT outing picker requests.
    # -----------------------------
    _is_direct_schedule = _is_schedule_intent(user_request) and _user_provided_time(user_request)
    if _is_weekend_outing_request(user_request) and not _is_direct_schedule:
        has_abc = ("(A)" in txt and "(B)" in txt and "(C)" in txt)
        if _dead_end_output(parsed, user_request=user_request) or (t != "question") or (not has_abc):
            regen = _regen_dynamic_weekend_options(
                router=router,
                model=model,
                user_request=user_request,
                current_location=current_location,
                memory_dump=memory_dump,
                ideas_dump=ideas_dump,
                chat_history=chat_history,
                missions_dump=ctx.get("missions_dump", "[]"),
                feedback_dump=ctx.get("feedback_dump", "[]"),
            )
            return _dump_final(regen)

    # -----------------------------
    # BUG-09: If user already gave us title + day + time, skip ALL follow-up questions.
    # Force a direct plan regen — never ask location or anything else.
    # Exempt: weekend outing requests (those need the A/B/C picker — returned earlier).
    # -----------------------------
    if (
        _is_schedule_intent(user_request)
        and _user_provided_time(user_request)
        and parsed.get("type") == "question"
        and not _is_direct_schedule
    ):
        regen = _regen_force_plan_direct(router, model, ctx, user_request)
        return _dump_final(regen)

    # -----------------------------
    # A/B/C enforcement for scheduling questions (non-weekend)
    # If the model returns a question without the required A/B/C + final reply line,
    # regenerate a tight A/B/C question to prevent UI "empty options" experiences.
    # -----------------------------
    if _is_schedule_intent(user_request) and parsed.get("type") == "question":
        qtxt = (parsed.get("text") or "")
        has_abc = ("(A)" in qtxt and "(B)" in qtxt and "(C)" in qtxt)
        # has_reply check removed — "Reply exactly" line is stripped from display
        # and no longer injected. has_abc is sufficient to confirm options were given.
        if not has_abc:
            regen = _regen_time_question(router, model, ctx, user_request=user_request)
            return _dump_final(regen)


    # -----------------------------
    # Prevent guessed-time scheduling (plan with events but user didn't specify time)
    # Exempt: option selections (schedule A/B/C) — those carry an implicit time commitment
    # -----------------------------
    _is_option_selection = bool(re.search(r"\b(schedule\s*)?[A-C]\b", original_user_request, re.IGNORECASE)) \
                           and sel.get("kind") in ("weekend_choice", "time_choice")
    if t == "plan" and events and not _is_option_selection:
        if not _user_provided_time(user_request) and not _user_requested_multiple(user_request):
            q = _regen_time_question(router, model, ctx, user_request)
            return _dump_final(q)
        

    # Final return (STRICT JSON only)
    return _dump_final(parsed)