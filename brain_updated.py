import os, textwrap, json, datetime, re, pathlib

updated_path = "/mnt/data/brain_updated.py"

code = r'''import json
import datetime
import base64
import re
import os
import argparse
from typing import Any, Dict, List, Optional, Tuple

from groq import Groq


# -----------------------------
# Time helpers
# -----------------------------
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


def encode_image(image) -> str:
    import io
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# -----------------------------
# Core response builder
# -----------------------------
def get_coo_response(
    api_key: str,
    user_request: str,
    memory: Optional[List[Any]] = None,
    calendar_data: Optional[str] = None,
    pending_events: Optional[List[Dict[str, Any]]] = None,
    current_location: Optional[str] = None,
    image_context=None,
    image_obj=None,
    chat_history: Optional[List[Dict[str, str]]] = None,
    proactive_triggers: Optional[List[str]] = None,
):
    """
    Standalone-friendly "brain" with:
    - Context + memory (lightweight retrieval)
    - Hypothesis -> Validation -> Action -> Confirm loop
    - Actionability via structured outputs (plan/conflict + events)
    - Proactive help via explicit triggers (daily_brief, conflict_alert, etc.)

    Output JSON contract (kept compatible):
      { "type": "question|confirmation|plan|conflict|error",
        "text": "...",
        "events": [ {title,start_time,end_time,location,description} ],
        "pre_prep": "..." }
    """
    if image_context is None and image_obj is not None:
        image_context = image_obj

    memory = memory or []
    calendar_data = calendar_data or ""
    pending_events = pending_events or []
    chat_history = chat_history or []
    proactive_triggers = proactive_triggers or []

    client = Groq(api_key=api_key)
    now = _get_tz_now()

    # -----------------------------
    # Output helpers (keep contract)
    # -----------------------------
    def _safe_json(obj) -> str:
        return json.dumps(obj, ensure_ascii=False)

    def _mk_question(q: str) -> str:
        # EXACTLY one question
        q = (q or "").strip()
        if q.count("?") > 1:
            q = q.split("?")[0].strip() + "?"
        if not q.endswith("?"):
            q = q + "?"
        return _safe_json({"type": "question", "text": q, "events": [], "pre_prep": ""})

    def _mk_confirmation(msg: str, pre_prep: str = "") -> str:
        return _safe_json({"type": "confirmation", "text": (msg or "").strip(), "events": [], "pre_prep": pre_prep or ""})

    def _mk_error(msg: str) -> str:
        return _safe_json({"type": "error", "text": (msg or "").strip(), "events": [], "pre_prep": ""})

    # -----------------------------
    # Parse helpers
    # -----------------------------
    def _parse_first_json(text: str):
        if not text:
            return None
        t = text.strip()
        try:
            obj = json.loads(t)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass
        m = re.search(r"(\{.*\})", t, re.DOTALL)
        if not m:
            return None
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def _dt_parse(s: str):
        if not s or not isinstance(s, str):
            return None
        ss = s.strip().replace("Z", "+00:00")
        try:
            return datetime.datetime.fromisoformat(ss)
        except Exception:
            # accept YYYY-MM-DDTHH:MM
            if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$", ss):
                try:
                    return datetime.datetime.fromisoformat(ss + ":00")
                except Exception:
                    return None
            return None

    def _localize(dt: datetime.datetime) -> datetime.datetime:
        if dt is None:
            return None
        try:
            if dt.tzinfo is not None:
                return dt.astimezone(_get_tz_now().tzinfo)
        except Exception:
            pass
        return dt

    def _iso_no_tz(dt: datetime.datetime) -> str:
        if dt is None:
            return ""
        dt = _localize(dt)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    def _format_time(dt: datetime.datetime) -> str:
        dt = _localize(dt)
        try:
            return dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            return str(dt)

    # -----------------------------
    # Calendar ledger parsing (calendar_data string + pending drafts)
    # -----------------------------
    def _parse_busy_from_calendar_data(cal_str):
        busy = []
        if not cal_str:
            return busy
        if not isinstance(cal_str, str):
            cal_str = str(cal_str)

        m = re.search(r"JSON:\s*(\[[\s\S]*\])", cal_str)
        payload = m.group(1) if m else None
        if not payload:
            m2 = re.search(r"(\[[\s\S]*\])", cal_str)
            payload = m2.group(1) if m2 else None
        if not payload:
            return busy

        try:
            arr = json.loads(payload)
        except Exception:
            return busy
        if not isinstance(arr, list):
            return busy

        for e in arr:
            if not isinstance(e, dict):
                continue
            st = _dt_parse(str(e.get("start", "") or e.get("start_raw", "") or ""))
            en = _dt_parse(str(e.get("end", "") or e.get("end_raw", "") or ""))
            title = str(e.get("title", "") or "").strip()
            loc = str(e.get("location", "") or "").strip()
            if st and en:
                busy.append({"title": title, "start": _localize(st), "end": _localize(en), "location": loc})
        return busy

    def _parse_busy_from_pending(pending):
        busy = []
        if not pending or not isinstance(pending, list):
            return busy
        for e in pending:
            if not isinstance(e, dict):
                continue
            st = _dt_parse(str(e.get("start_time", "") or ""))
            en = _dt_parse(str(e.get("end_time", "") or ""))
            title = str(e.get("title", "") or "").strip()
            loc = str(e.get("location", "") or "").strip()
            if st and en:
                busy.append({"title": title, "start": _localize(st), "end": _localize(en), "location": loc})
        return busy

    def _ledger():
        return _parse_busy_from_calendar_data(calendar_data) + _parse_busy_from_pending(pending_events)

    # -----------------------------
    # Agents (lightweight, standalone)
    # -----------------------------
    def _memory_agent(text: str) -> Dict[str, Any]:
        """
        Simple but effective memory retrieval:
        - Keyword match against memory items
        - Pulls last 1-2 assistant decisions from chat_history
        """
        t = (text or "").lower()
        keywords = set(re.findall(r"[a-zA-Z]{4,}", t))

        def _as_text(m):
            if isinstance(m, str):
                return m
            if isinstance(m, dict):
                return " ".join([str(v) for v in m.values() if v is not None])
            return str(m)

        picked = []
        for m in memory:
            mt = _as_text(m).lower()
            if any(k in mt for k in list(keywords)[:20]):
                picked.append(_as_text(m))
            if len(picked) >= 5:
                break

        last_decisions = []
        for msg in reversed(chat_history[-20:]):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                last_decisions.append((msg.get("content") or "")[:200])
            if len(last_decisions) >= 2:
                break

        # Always include minimal stable context
        return {
            "timezone": "America/New_York",
            "location_hint": current_location or "",
            "relevant_memory": picked,
            "recent_assistant_notes": list(reversed(last_decisions)),
        }

    def _planner_agent(text: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produces:
        - intent
        - hypothesis (what user wants)
        - missing fields (if any)
        """
        intent = _route_intent(text)
        plan = {"intent": intent, "hypothesis": "", "missing": [], "requirements": None}

        if intent == "calendar_inquiry":
            plan["hypothesis"] = "User wants to see their schedule for a time range."
            return plan

        if intent == "planner_request":
            plan["hypothesis"] = "User wants ideas/options for planning."
            return plan

        if intent != "schedule_action":
            plan["hypothesis"] = "General question; offer next best action (calendar or planning)."
            return plan

        # schedule_action: missing-field gating (ask only what's missing)
        low = (text or "").lower()
        has_any_time = bool(
            re.search(r"\b\d{1,2}(:\d{2})?\s?(am|pm)\b", low)
            or re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", low)
            or re.search(r"\b(morning|afternoon|evening|night|tonight)\b", low)
        )
        has_any_day = bool(
            re.search(r"\b(today|tomorrow|tonight|this week|next week|this weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", low)
            or re.search(r"\b\d{4}-\d{2}-\d{2}\b", low)
        )

        plan["hypothesis"] = "User wants to schedule something on their calendar."

        if not has_any_day:
            plan["missing"].append("day")
        if not has_any_time:
            plan["missing"].append("time")

        if plan["missing"]:
            return plan

        # Extract requirements (LLM is used ONLY for extraction)
        req = _extract_requirements(text)
        plan["requirements"] = req
        return plan

    def _validator_agent(plan: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Checks sanity/conflicts and produces:
        - status: ok|needs_info|conflict|error
        - question (if needs_info)
        - draft events (if ok/conflict with alternatives)
        """
        intent = plan.get("intent")

        if intent != "schedule_action":
            return {"status": "ok"}

        missing = plan.get("missing") or []
        if missing:
            # one tight question
            if missing == ["day"]:
                return {"status": "needs_info", "question": "Which day — today, tomorrow, or next week"}
            if missing == ["time"]:
                return {"status": "needs_info", "question": "What time — morning, afternoon, or evening"}
            return {"status": "needs_info", "question": "What day and what time"}

        req = plan.get("requirements") or {}
        if not isinstance(req, dict):
            return {"status": "error", "error": "Could not extract scheduling details."}

        title = str(req.get("title") or "New Event").strip()
        loc = str(req.get("location") or "").strip()
        duration_min = int(req.get("duration_min") or 60)

        explicit_start = _dt_parse(str(req.get("explicit_start") or ""))
        explicit_end = _dt_parse(str(req.get("explicit_end") or ""))

        if explicit_start:
            explicit_start = _localize(explicit_start)
        if explicit_end:
            explicit_end = _localize(explicit_end)

        ledger = _ledger()

        # Hypothesis slot
        if explicit_start:
            cand_start = explicit_start
        else:
            cand_start = now + datetime.timedelta(minutes=30)

        if explicit_end and explicit_start:
            cand_end = explicit_end
            duration_min = max(15, int((cand_end - cand_start).total_seconds() / 60))
        else:
            cand_end = cand_start + datetime.timedelta(minutes=duration_min)

        conflict, conflict_item = _conflict_with_travel(cand_start, cand_end, loc, ledger)

        if not conflict:
            return {
                "status": "ok",
                "draft": {
                    "title": title,
                    "start_time": _iso_no_tz(cand_start),
                    "end_time": _iso_no_tz(cand_end),
                    "location": loc,
                    "description": "",
                },
            }

        slots = _find_next_valid_slots(cand_start + datetime.timedelta(minutes=30), duration_min, loc, ledger, limit=3)
        if not slots:
            return {"status": "needs_info", "question": "I’m seeing conflicts — prefer later today, tomorrow, or weekend"}

        alts = []
        for s, e in slots:
            alts.append(
                {
                    "title": title,
                    "start_time": _iso_no_tz(s),
                    "end_time": _iso_no_tz(e),
                    "location": loc,
                    "description": "",
                }
            )

        conflict_title = (conflict_item or {}).get("title") or "another event"
        return {"status": "conflict", "conflict_with": conflict_title, "alternatives": alts}

    def _executor_agent(text: str, plan: Dict[str, Any], validation: Dict[str, Any], ctx: Dict[str, Any]) -> str:
        """
        Performs safe actions in this module by returning structured outputs.
        (Real calendar writes happen in your app layer.)
        """
        intent = plan.get("intent")

        # Proactive help (explicit triggers only)
        if proactive_triggers:
            return _handle_proactive(proactive_triggers, ctx)

        if intent == "calendar_inquiry":
            return _handle_calendar_inquiry(text)

        if intent == "planner_request":
            return _mk_question("What kind of plan — (A) family outing (B) errand/appointment (C) fitness/class")

        if intent != "schedule_action":
            return _mk_confirmation("Want me to check your schedule, or help plan something?")

        status = validation.get("status")
        if status == "needs_info":
            return _mk_question(str(validation.get("question") or "What day and time"))

        if status == "error":
            return _mk_error(str(validation.get("error") or "Something went wrong."))

        if status == "ok":
            draft = validation.get("draft") or {}
            return _safe_json(
                {
                    "type": "plan",
                    "text": "Draft ready — reply 'confirm' to add it, or tell me what to change.",
                    "pre_prep": _next_best_step_hint(ctx, draft),
                    "events": [draft],
                }
            )

        if status == "conflict":
            alts = validation.get("alternatives") or []
            return _safe_json(
                {
                    "type": "conflict",
                    "text": f"That overlaps with {validation.get('conflict_with')}. Pick 1 / 2 / 3.",
                    "pre_prep": "If the location differs, a 30-minute travel buffer is enforced.",
                    "events": alts,
                }
            )

        return _mk_error("Unhandled state.")

    # -----------------------------
    # Intent Router (deterministic)
    # -----------------------------
    def _has_schedule_action(text: str) -> bool:
        return bool(re.search(r"\b(schedule|add|plan|book|set up)\b", (text or ""), flags=re.IGNORECASE))

    def _is_calendar_inquiry(text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False
        if re.search(r"\b(check|show)\b", t) and re.search(r"\b(calendar|schedule|agenda|plan)\b", t):
            return True
        patterns = [
            r"\bwhat('?s| is)\s+my\s+plan\b",
            r"\bmy\s+plan\s+for\s+(today|tomorrow|this week|next week)\b",
            r"\bwhat\s+do\s+i\s+have\b",
            r"\bagenda\b",
            r"\bmeetings?\s+(today|tomorrow|this week|next week)\b",
        ]
        return any(re.search(p, t) for p in patterns)

    def _is_planner_request(text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False
        if re.search(r"\b(help me|suggest|recommend|ideas?)\b", t) and re.search(r"\b(plan|planning)\b", t):
            return True
        if re.search(r"\bplan\b", t) and re.search(r"\b(something|interesting|fun|outing)\b", t) and not re.search(r"\b(schedule|add|book)\b", t):
            return True
        return False

    def _route_intent(text: str) -> str:
        if _is_calendar_inquiry(text):
            return "calendar_inquiry"
        if _is_planner_request(text):
            return "planner_request"
        if _has_schedule_action(text):
            return "schedule_action"
        return "general_qa"

    # -----------------------------
    # Calendar inquiry responder
    # -----------------------------
    def _start_of_day(dt):
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    def _end_of_day(dt):
        return dt.replace(hour=23, minute=59, second=59, microsecond=0)

    def _start_of_week(dt):
        d0 = _start_of_day(dt)
        return d0 - datetime.timedelta(days=d0.weekday())

    def _end_of_week(dt):
        return _start_of_week(dt) + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)

    def _agenda_for_range(rs, re_, label: str):
        items = []
        for b in _ledger():
            st = b["start"]
            en = b["end"]
            if (st <= re_) and (en >= rs):
                items.append(b)
        items.sort(key=lambda x: x["start"])

        if not items:
            return _mk_confirmation(f"You're clear {label}. Want to add something?")

        grouped = {}
        for b in items:
            d = _localize(b["start"]).date()
            grouped.setdefault(d, []).append(b)

        lines = [f"Your plan {label}:", ""]
        for d in sorted(grouped.keys()):
            day_label = datetime.datetime.combine(d, datetime.time()).strftime("%a %b %d")
            lines.append(day_label)
            for b in grouped[d]:
                st = _localize(b["start"])
                en = _localize(b["end"])
                title = b.get("title") or "Untitled"
                loc = b.get("location") or ""
                if loc:
                    lines.append(f"• {_format_time(st)}–{_format_time(en)}  {title} ({loc})")
                else:
                    lines.append(f"• {_format_time(st)}–{_format_time(en)}  {title}")
            lines.append("")
        return _mk_confirmation("\n".join(lines).strip())

    def _handle_calendar_inquiry(text: str):
        t = (text or "").lower()
        if "next week" in t:
            base = _start_of_week(now) + datetime.timedelta(days=7)
            return _agenda_for_range(base, _end_of_week(base), "for next week")
        if "this week" in t:
            return _agenda_for_range(_start_of_week(now), _end_of_week(now), "for this week")
        if "tomorrow" in t:
            d = now + datetime.timedelta(days=1)
            return _agenda_for_range(_start_of_day(d), _end_of_day(d), "for tomorrow")
        return _agenda_for_range(_start_of_day(now), _end_of_day(now), "for today")

    # -----------------------------
    # CSP / validation utilities
    # -----------------------------
    def _overlaps(a_start, a_end, b_start, b_end) -> bool:
        return (a_start < b_end) and (a_end > b_start)

    def _needs_travel_buffer(loc_a: str, loc_b: str) -> bool:
        la = (loc_a or "").strip().lower()
        lb = (loc_b or "").strip().lower()
        if not la or not lb:
            return False
        return la != lb

    def _conflict_with_travel(proposed_start, proposed_end, proposed_loc, ledger):
        travel = datetime.timedelta(minutes=30)

        for b in ledger:
            b_start = b["start"]
            b_end = b["end"]
            b_loc = b.get("location", "")

            # direct overlap
            if _overlaps(proposed_start, proposed_end, b_start, b_end):
                return True, b

            # travel buffer if different locations
            if _needs_travel_buffer(proposed_loc, b_loc):
                if b_end <= proposed_start and (proposed_start - b_end) < travel:
                    return True, b
                if proposed_end <= b_start and (b_start - proposed_end) < travel:
                    return True, b

        return False, None

    def _round_to_30(dt):
        dt = dt.replace(second=0, microsecond=0)
        addm = (30 - (dt.minute % 30)) % 30
        return dt + datetime.timedelta(minutes=addm)

    def _find_next_valid_slots(base_start, duration_min, loc, ledger, limit=3):
        dur = datetime.timedelta(minutes=max(15, int(duration_min)))
        slots = []
        cursor = _round_to_30(base_start)
        end_limit = base_start + datetime.timedelta(days=7)

        while cursor < end_limit and len(slots) < limit:
            cand_start = cursor
            cand_end = cand_start + dur

            if 6 <= cand_start.hour <= 21:
                conflict, _ = _conflict_with_travel(cand_start, cand_end, loc, ledger)
                if not conflict:
                    slots.append((cand_start, cand_end))
            cursor += datetime.timedelta(minutes=30)

        return slots

    # -----------------------------
    # LLM extraction ONLY
    # -----------------------------
    def _extract_requirements(text: str):
        current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
        cheat_sheet = _next_7_days_cheatsheet(now)
        next_saturday = _next_saturday_date(now)

        system_prompt = f"""
You are an extraction engine for a personal assistant.

CURRENT TIME (America/New_York): {current_time_str}
{cheat_sheet}
"Next Saturday" date is: {next_saturday}

TASK:
Extract requirements ONLY. Do NOT do any calendar math. Do NOT validate conflicts.

Return STRICT JSON ONLY:
{{
  "title": "string",
  "location": "string",
  "duration_min": 60,
  "preferred_window": "today|tomorrow|this week|next week|none",
  "explicit_start": "YYYY-MM-DDTHH:MM:SS",
  "explicit_end": "YYYY-MM-DDTHH:MM:SS"
}}

Rules:
- If duration is not stated, set duration_min=60.
- If user says dinner, you may set duration_min=90.
- If no explicit time is stated, set explicit_start="" and explicit_end="".
""".strip()

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}]

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.2,
            max_tokens=500,
            stream=False,
        )
        raw = (completion.choices[0].message.content or "").strip()
        obj = _parse_first_json(raw)
        if not obj or not isinstance(obj, dict):
            return None
        obj.setdefault("title", "New Event")
        obj.setdefault("location", "")
        obj.setdefault("duration_min", 60)
        obj.setdefault("preferred_window", "none")
        obj.setdefault("explicit_start", "")
        obj.setdefault("explicit_end", "")
        return obj

    # -----------------------------
    # Proactive help (triggered)
    # -----------------------------
    def _handle_proactive(triggers: List[str], ctx: Dict[str, Any]) -> str:
        if "daily_brief" in triggers:
            # Brief for today + one suggestion
            brief = json.loads(_handle_calendar_inquiry("today"))
            # brief is a dict-like, but _handle_calendar_inquiry returns JSON string; parse safely:
            try:
                brief_obj = json.loads(_handle_calendar_inquiry("today"))
                txt = brief_obj.get("text") or "Today's plan is clear."
            except Exception:
                txt = "Here's your day."
            return _mk_confirmation(f"{txt}\n\nNext: Want me to protect a 60‑minute focus block?", "")
        if "conflict_alert" in triggers:
            return _mk_confirmation("Heads up — I see a potential conflict in your schedule. Want me to suggest alternatives?", "")
        return _mk_confirmation("I’m here. What do you want to do next?", "")

    def _next_best_step_hint(ctx: Dict[str, Any], draft: Dict[str, Any]) -> str:
        # minimal, human, actionable
        mem = ctx.get("relevant_memory") or []
        if mem:
            return "Next: confirm, or tell me your preferred time window."
        return "Next: confirm, or tell me what to change."

    # -----------------------------
    # Supervisor orchestrates the loop
    # -----------------------------
    ctx = _memory_agent(user_request)
    plan = _planner_agent(user_request, ctx)
    validation = _validator_agent(plan, ctx)
    return _executor_agent(user_request, plan, validation, ctx)


# -----------------------------
# Standalone runner (VS Code friendly)
# -----------------------------
def _load_json_file(path: Optional[str], default):
    if not path:
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", default=os.getenv("GROQ_API_KEY", ""))
    parser.add_argument("--memory", help="Path to memory.json", default="")
    parser.add_argument("--calendar", help="Path to calendar.json (list of events)", default="")
    parser.add_argument("--interactive", action="store_true", help="Interactive chat loop")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: Set GROQ_API_KEY or pass --api_key")
        raise SystemExit(1)

    memory = _load_json_file(args.memory, [])
    cal = _load_json_file(args.calendar, [])

    # Provide calendar_data in the same style your app expects: string containing JSON list
    calendar_data = "JSON: " + json.dumps(cal, ensure_ascii=False)

    if args.interactive:
        print("Family COO brain (standalone). Type 'exit' to quit.\n")
        chat_history = []
        while True:
            user = input("You: ").strip()
            if user.lower() in {"exit", "quit"}:
                break
            out = get_coo_response(
                api_key=args.api_key,
                user_request=user,
                memory=memory,
                calendar_data=calendar_data,
                pending_events=[],
                chat_history=chat_history,
            )
            print("\nBrain JSON:\n", out, "\n")
            chat_history.append({"role": "user", "content": user})
            chat_history.append({"role": "assistant", "content": out})
    else:
        # single-shot example
        sample = "Book dentist tomorrow evening"
        out = get_coo_response(args.api_key, sample, memory=memory, calendar_data=calendar_data)
        print(out)


if __name__ == "__main__":
    main()
'''
