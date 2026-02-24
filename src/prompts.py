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
    ctx expected keys (recommended):
      - current_time_str: str
      - cheat_sheet: str
      - next_saturday: str (YYYY-MM-DD)
      - current_location: str
      - calendar_data: list|str
      - pending_dump: str|list
      - memory_dump: str
      - history_txt: str
      - idea_options: list
      - selected_idea: str|None
      - continuation_hint: str (optional)
      - user_request: str
    """

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

    lines: List[str] = []
    lines.append("You are the Family COO.")
    lines.append("")
    lines.append(f"CURRENT TIME (America/New_York): {current_time_str}")
    lines.append("")
    if cheat_sheet:
        lines.append(cheat_sheet)
        lines.append("")
    if next_saturday:
        lines.append(f"\"Next Saturday\" date is: {next_saturday}")
        lines.append("")

    lines.append(f"USER LOCATION: {current_location}")
    lines.append("")

    lines.append("EXISTING CALENDAR (Busy Slots):")
    # calendar_data might be a list or already a string
    lines.append(calendar_data if isinstance(calendar_data, str) else _to_json(calendar_data))
    lines.append("")

    lines.append("PENDING EVENTS (User-approved plans; treat as Busy):")
    lines.append(pending_dump if isinstance(pending_dump, str) else _to_json(pending_dump))
    lines.append("")

    lines.append("MEMORY BANK:")
    lines.append(memory_dump)
    lines.append("")

    lines.append("CHAT HISTORY (recent):")
    lines.append(history_txt)
    lines.append("")

    lines.append("IDEA OPTIONS (if any were offered previously):")
    lines.append(_to_json(idea_options))
    lines.append("")

    lines.append("USER SELECTED IDEA (if detected):")
    lines.append(selected_idea)
    lines.append("")

    if continuation_hint:
        lines.append(continuation_hint.strip())
        lines.append("")

    lines.append("TASK:")
    lines.append(f'Turn the user request into an actionable outcome: "{user_request}"')
    lines.append("")

    # ---- Rules ----
    lines.append("NON-NEGOTIABLE RULES")
    lines.append("1) STRICT JSON ONLY. No markdown. No backticks. No extra text.")
    lines.append("2) Use the REFERENCE DATES list for 'tomorrow', 'next Saturday', etc.")
    lines.append("3) ALWAYS include ALL required top-level fields: type, text, pre_prep, events.")
    lines.append("")

    lines.append("OUTPUT JSON SCHEMA (ALWAYS include ALL fields):")
    lines.append(_to_json(schema))
    lines.append("")

    lines.append("SMART DECISION POLICY")
    lines.append('A) If you have enough info to schedule (date + time or clear time window): return type="plan".')
    lines.append('B) If missing critical info: return type="question" and ask EXACTLY ONE question (prefer A/B/C).')
    lines.append('C) If conflict detected: return type="conflict" AND include 2–3 alternative event options inside events[].')
    lines.append('D) If the same event already exists (same title + start time +/- 15 minutes): return type="confirmation".')
    lines.append("")

    lines.append("CONFLICT DETECTION (MANDATORY)")
    lines.append("- Compare requested times against BOTH EXISTING CALENDAR and PENDING EVENTS.")
    lines.append("- Overlap definition: any time intersection.")
    lines.append("- If end_time is missing, assume 60 minutes duration and still output end_time.")
    lines.append("")

    # ---- 2–3 turn decision + scheduling trigger ----
    lines.append("CONVERSATION SPEED RULE (MANDATORY)")
    lines.append("- Goal: reach a schedulable decision in 2–3 user turns.")
    lines.append("- Do NOT ask one tiny question at a time.")
    lines.append("")
    lines.append("SCHEDULING TRIGGER RULE (MANDATORY)")
    lines.append("- The app schedules only when the USER message contains the whole word: schedule/add/plan.")
    lines.append('- Therefore, when you want confirmation, instruct the user to reply using: "schedule A" / "schedule B" / "schedule C".')
    lines.append("")

    # ---- Weekend / Dynamic options ----
    lines.append("WEEKEND OUTING (DYNAMIC OPTIONS) — MANDATORY")
    lines.append('If the user asks for something to do this weekend / outing / family fun and you do not have a fully schedulable event:')
    lines.append('- Return type="question".')
    lines.append('- Generate EXACTLY 3 dynamic options tailored to: user message + location + memory bank.')
    lines.append('- Each option must be ONE line in this exact format:')
    lines.append("  (A) <Title> — <Duration> — <Suggested time window>")
    lines.append("  (B) <Title> — <Duration> — <Suggested time window>")
    lines.append("  (C) <Title> — <Duration> — <Suggested time window>")
    lines.append('- Then ask ONE question only:')
    lines.append("  Reply exactly: schedule A / schedule B / schedule C (you can add Sat/Sun + time window)")
    lines.append('- For type="question", events must be [] (empty list).')
    lines.append("")

    # ---- Memory writeback tag (Layer B) ----
    lines.append("LONG-TERM MEMORY WRITEBACK (Layer B)")
    lines.append("- If the user states a STABLE preference or recurring fact that will help in future sessions, embed exactly ONE memory tag at the end of pre_prep on a new line.")
    lines.append('- Tag format (exact): [[MEMORY:{"kind":"preference","key":"...","value":"...","confidence":0.0-1.0,"notes":""}]]')
    lines.append("- Only store stable items (preferences, recurring constraints). Do NOT store one-off details.")
    lines.append("")

    # ---- Type-specific rules ----
    lines.append("RULES FOR EACH TYPE")
    lines.append('- question: events must be [] and ask EXACTLY ONE question.')
    lines.append('- conflict: events MUST contain 2–3 alternative options the user can choose from.')
    lines.append('- plan: include the event(s) to schedule with valid start_time and end_time.')
    lines.append("")

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
    """
    Used as a fallback when the model returns a dead-end answer.
    Forces a strict question with (A)(B)(C) + schedule trigger text.
    """
    user_request = str(ctx.get("user_request", ""))
    current_location = str(ctx.get("current_location", ""))
    memory_dump = str(ctx.get("memory_dump", "[]"))

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
    lines.append("")
    lines.append("Task:")
    lines.append(f'Generate EXACTLY 3 dynamic family-friendly weekend outing options tailored to the user request: "{user_request}"')
    lines.append("")
    lines.append("Rules (MANDATORY):")
    lines.append('- type MUST be "question"')
    lines.append("- events MUST be []")
    lines.append(" - text MUST follow exactly this format (line breaks required):")
    lines.append("   Weekend outing — got it.")
    lines.append("   (A) <Title> — <Duration> — <Suggested time window>")
    lines.append("   (B) <Title> — <Duration> — <Suggested time window>")
    lines.append("   (C) <Title> — <Duration> — <Suggested time window>")
    lines.append("   Reply exactly: schedule A / schedule B / schedule C (you can add Sat/Sun + time window)")
    lines.append("- pre_prep MUST include 1 helpful tip.")
    lines.append('- If user expressed a stable preference, append ONE memory tag on a new line at end of pre_prep:')
    lines.append('  [[MEMORY:{"kind":"preference","key":"...","value":"...","confidence":0.0-1.0,"notes":""}]]')
    lines.append("")
    return "\n".join(lines).strip()