# src/prompts_v23.py
# Prompt builders for Family COO Brain (Checkpoint 2.3)
# - No Streamlit
# - No tool calls
# - No file I/O
# - Pure string construction only

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _to_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "[]"


def _schema_example() -> Dict[str, Any]:
    return {
        "type": "plan|conflict|question|confirmation|chat|error",
        "text": "string",
        "pre_prep": "string",
        "events": [
            {
                "title": "string",
                "start_time": "YYYY-MM-DDTHH:MM:SS",
                "end_time": "YYYY-MM-DDTHH:MM:SS",
                "location": "string",
                "description": "string",
            }
        ],
    }


def build_system_prompt(ctx: Dict[str, Any]) -> str:
    """
    Checkpoint 2.5 Fix #1:
    - Remove accidental duplicated prompt blocks inside build_system_prompt
    - Ensure rules are ALWAYS injected
    - Ensure Ideas Inbox is ALWAYS injected via ideas_summary (list[dict])
    - Keep Brain JSON contract strict: type/text/pre_prep/events only
    - No Streamlit, no tool calls, no file I/O
    """

    # ---------------------------
    # Safe helpers
    # ---------------------------
    def _safe_lines_from_kv(items: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for it in items or []:
            try:
                k = (it.get("key") or "").strip()
                v = (it.get("value") or "").strip()
                if k and v:
                    lines.append(f"- {k}: {v}")
            except Exception:
                continue
        return "\n".join(lines) if lines else "- (none)"

    def _safe_lines_from_ideas(items: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for it in items or []:
            try:
                txt = (it.get("text") or "").strip()
                if txt:
                    lines.append(f"- {txt}")
            except Exception:
                continue
        return "\n".join(lines) if lines else "- (none)"

    # ---------------------------
    # Blocks: memory + ideas
    # ---------------------------
    memory_summary = ctx.get("memory_summary") or []
    ideas_summary = ctx.get("ideas_summary") or []

    memory_block = _safe_lines_from_kv(memory_summary)
    ideas_block = _safe_lines_from_ideas(ideas_summary)

    # ---------------------------
    # Context fields
    # ---------------------------
    current_time_str = str(ctx.get("current_time_str", ""))
    cheat_sheet = str(ctx.get("cheat_sheet", ""))
    next_saturday = str(ctx.get("next_saturday", ""))
    current_location = str(ctx.get("current_location", ""))
    calendar_data = ctx.get("calendar_data", [])
    pending_dump = ctx.get("pending_dump", "[]")
    memory_dump = str(ctx.get("memory_dump", "[]"))
    history_txt = str(ctx.get("history_txt", ""))
    idea_options = ctx.get("idea_options", []) or []
    selected_idea = str(ctx.get("selected_idea") or "")
    continuation_hint = str(ctx.get("continuation_hint") or "")
    user_request = str(ctx.get("user_request", ""))

    schema = _schema_example()

    # ---------------------------
    # Hard rules (SMART Policy)
    # ---------------------------
    rules_block = f"""
YOU ARE: Family COO.

USER PREFERENCES (LATEST-WINS, USE WHEN RELEVANT):
{memory_block}

IDEAS INBOX (USER-ADDED ACTIVITIES — PRIORITIZE WHEN RELEVANT):
{ideas_block}

NON-NEGOTIABLE OUTPUT CONTRACT:
- Output MUST be STRICT JSON only (no markdown, no extra text).
- Top-level keys MUST be exactly: type, text, pre_prep, events
- No extra fields. No commentary.
- Always include all 4 keys even if empty.
- If type="question" => events MUST be []
- If type="plan" or type="conflict" => events MUST be non-empty and valid schema.

SCHEDULING TRIGGER (APP GATE):
- The app schedules ONLY if the USER message contains the whole word: schedule/add/plan.

SMART DECISION POLICY:
A) If you have enough info to schedule (date + time OR clear time window) AND user used schedule/add/plan => type="plan"
B) If missing critical info => type="question" ask EXACTLY ONE tight question (prefer A/B/C choices), events=[]
C) If conflict detected vs EXISTING CALENDAR or PENDING EVENTS => type="conflict"
   - text must include A/B/C alternatives
   - events must contain 2–3 alternative event options
D) If same event already exists (same title + start_time +/- 15 min) => type="confirmation"

WEEKEND OUTING BEHAVIOR (MANDATORY):
- If user asks weekend ideas / outings / family fun AND not enough info to schedule:
  Return type="question", events=[]
  text MUST include EXACTLY 3 options labeled (A),(B),(C)
  Each option must include: Title + Duration + Suggested time window
  Then ONE instruction line:
    "Reply exactly: schedule A / schedule B / schedule C"

ANTI-LAZY RULES:
- Do NOT ask generic mirror questions like:
  "Which activity would you like?" / "Which outing would you like to schedule?"
- If you ask a question, it must contain concrete A/B/C choices.
""".strip()

    # ---------------------------
    # Prompt assembly
    # ---------------------------
    lines: List[str] = []
    lines.append(rules_block)
    lines.append("")
    lines.append(f"CURRENT TIME (America/New_York): {current_time_str}".strip())
    if cheat_sheet:
        lines.append("")
        lines.append("CHEAT SHEET:")
        lines.append(cheat_sheet.strip())
    if next_saturday:
        lines.append("")
        lines.append(f"REFERENCE: \"Next Saturday\" date is: {next_saturday}".strip())

    lines.append("")
    lines.append(f"USER LOCATION: {current_location}".strip())

    lines.append("")
    lines.append("EXISTING CALENDAR (Busy Slots):")
    lines.append(calendar_data if isinstance(calendar_data, str) else _to_json(calendar_data))

    lines.append("")
    lines.append("PENDING EVENTS (Treat as Busy):")
    lines.append(pending_dump if isinstance(pending_dump, str) else _to_json(pending_dump))

    lines.append("")
    lines.append("MEMORY BANK (raw json):")
    lines.append(memory_dump)

    lines.append("")
    lines.append("CHAT HISTORY (recent):")
    lines.append(history_txt)

    lines.append("")
    lines.append("IDEA OPTIONS (if previously offered):")
    lines.append(_to_json(idea_options))

    lines.append("")
    lines.append("USER SELECTED IDEA (if detected):")
    lines.append(selected_idea)

    if continuation_hint:
        lines.append("")
        lines.append("CONTINUATION HINT:")
        lines.append(continuation_hint.strip())

    lines.append("")
    lines.append("TASK:")
    lines.append(f'Turn the user request into an actionable outcome: "{user_request}"')

    lines.append("")
    lines.append("OUTPUT JSON SCHEMA EXAMPLE (match keys + structure):")
    lines.append(_to_json(schema))

    return "\n".join(lines).strip()


def build_json_repair_prompt(bad_text: str) -> str:
    schema = _schema_example()
    lines: List[str] = []
    lines.append("You must output STRICT JSON ONLY. No markdown. No explanations.")
    lines.append("")
    lines.append("Fix the following into a valid JSON object that matches EXACTLY this schema and includes ALL fields:")
    lines.append(_to_json(schema))
    lines.append("")
    lines.append('If info is missing, use type="question", events=[], and ask exactly ONE question.')
    lines.append("")
    lines.append("BAD OUTPUT TO FIX:")
    lines.append(str(bad_text or ""))
    return "\n".join(lines).strip()


def build_weekend_regen_prompt(ctx: Dict[str, Any]) -> str:
    user_request = str(ctx.get("user_request", ""))
    current_location = str(ctx.get("current_location", ""))
    memory_dump = str(ctx.get("memory_dump", "[]"))
    ideas_dump = str(ctx.get("ideas_dump", "[]"))
    constraints = ctx.get("constraints", {}) or {}

    schema_question = {
        "type": "question",
        "text": "string",
        "pre_prep": "string",
        "events": [],
    }

    lines: List[str] = []
    lines.append("Return STRICT JSON ONLY. No markdown. No extra text.")
    lines.append("")
    lines.append("You MUST return a JSON object matching this schema exactly (include ALL fields):")
    lines.append(_to_json(schema_question))
    lines.append("")
    lines.append(f"User location: {current_location}")
    lines.append(f"Memory bank: {memory_dump}")
    lines.append(f"Ideas Inbox (use when relevant): {ideas_dump}")
    lines.append(f"Constraints (MUST honor): {json.dumps(constraints, ensure_ascii=False)}")
    lines.append("")
    lines.append(f'Task: Generate EXACTLY 3 dynamic family-friendly weekend outing options for: "{user_request}"')
    lines.append("")
    lines.append("MANDATORY RULES:")
    lines.append('- type MUST be "question"')
    lines.append("- events MUST be []")
    lines.append("- text MUST be plain text (NO markdown) and MUST follow EXACTLY the template below.")
    lines.append("- pre_prep MUST contain exactly 1 helpful tip sentence.")
    lines.append("- pre_prep MUST ALSO include one line starting with OPTIONS_JSON= followed by a JSON list of 3 objects.")
    lines.append("- OPTIONS_JSON objects MUST match the text options A/B/C and include keys: key,title,duration_hours,time_window,notes")
    lines.append("")

    lines.append("TEXT TEMPLATE (copy structure exactly):")
    lines.append("Weekend outing — pick one:")
    lines.append("")
    lines.append("(A) <Title>")
    lines.append("    Duration: <N> hours")
    lines.append("    Time window: <start time>–<end time>")
    lines.append("")
    lines.append("(B) <Title>")
    lines.append("    Duration: <N> hours")
    lines.append("    Time window: <start time>–<end time>")
    lines.append("")
    lines.append("(C) <Title>")
    lines.append("    Duration: <N> hours")
    lines.append("    Time window: <start time>–<end time>")
    lines.append("")
    lines.append("Reply exactly: schedule A / schedule B / schedule C")
    lines.append("(Optional: add Sat/Sun + adjust time window)")
    lines.append("")
    lines.append("pre_prep FORMAT (must include both):")
    lines.append("1) Tip: <one sentence>")
    lines.append('2) OPTIONS_JSON=[{"key":"A","title":"...","duration_hours":2,"time_window":"Sat 10:00 AM–12:00 PM","notes":"..."}, {...}, {...}]')
    lines.append("")
    lines.append("If user expressed a stable preference, append ONE memory tag at the end of pre_prep on a new line:")
    lines.append('[[MEMORY:{"kind":"preference","key":"...","value":"...","confidence":0.0-1.0,"notes":""}]]')
    lines.append("")

    return "\n".join(lines).strip()