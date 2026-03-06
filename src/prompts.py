# prompts.py
# Prompt builders for Family COO Brain
# Checkpoint 2.7 – Brain Optimization Phase (Prompt Refinement)
# NOTE: Prompt-only changes. No tool calls. No Streamlit imports.

from __future__ import annotations

import json
from typing import Any, Dict, List


# ---------------------------
# Helpers
# ---------------------------
def _to_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "[]"


def _schema_example() -> Dict[str, Any]:
    # NOTE: Keep schema fields stable. App relies on these keys.
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


def _schema_question_example() -> Dict[str, Any]:
    return {"type": "question", "text": "string", "pre_prep": "string", "events": []}


_FINAL_REPLY_LINE = "Reply exactly: schedule A / schedule B / schedule C"


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
# Main system prompt
# ---------------------------
def build_system_prompt(ctx: Dict[str, Any]) -> str:
    """
    Checkpoint 2.7 – Prompt updates only.
    Goals:
      - Better readability (structured A/B/C + plan text)
      - Fewer loops (one-attempt batch collection)
      - Lower token waste (no back-and-forth)
      - Keep 2.6 behavior stable (routing/guards remain in code)
    """

    current_time_str = str(ctx.get("current_time_str", "") or "")
    cheat_sheet = str(ctx.get("cheat_sheet", "") or "")
    next_saturday = str(ctx.get("next_saturday", "") or "")
    current_location = str(ctx.get("current_location", "") or "")
    calendar_data = ctx.get("calendar_data", [])
    pending_dump = ctx.get("pending_dump", "[]")
    memory_dump = str(ctx.get("memory_dump", "[]") or "[]")
    history_txt = str(ctx.get("history_txt", "") or "")
    idea_options = ctx.get("idea_options", []) or []
    selected_idea = str(ctx.get("selected_idea") or "")
    continuation_hint = str(ctx.get("continuation_hint") or "")
    user_request = str(ctx.get("user_request", "") or "")

    memory_summary = ctx.get("memory_summary") or []
    ideas_summary = ctx.get("ideas_summary") or []
    memory_block = _safe_lines_from_kv(memory_summary)
    ideas_block = _safe_lines_from_ideas(ideas_summary)

    schema = _schema_example()

    rules_block = f"""
YOU ARE: Family COO (home chief-of-staff).

USER PREFERENCES (LATEST-WINS, USE WHEN RELEVANT):
{memory_block}

IDEAS INBOX (USER-ADDED ACTIVITIES — USE WHEN RELEVANT):
{ideas_block}

========================
ABSOLUTE OUTPUT CONTRACT
========================
- Output MUST be STRICT JSON only (no markdown, no stray text).
- Top-level keys MUST be EXACTLY: type, text, pre_prep, events
- Always include all 4 keys even if empty.
- events MUST always exist (empty list allowed).
- type="question" => events MUST be []
- type="plan"/"conflict" => events MUST be non-empty and MUST include events[0].start_time

========================
STABILITY / ROUTING RULES
========================
- The app only creates draft events when the USER message contains the whole word: schedule/add/plan.
- If user did NOT use schedule/add/plan: DO NOT push scheduling or A/B/C scheduling prompts.
- Greeting must never trigger scheduling logic.

# Replace the A/B/C template section in rules_block with:

A/B/C OUTPUT FORMAT (PLAIN TEXT, STRICT)
========================================
CRITICAL: Use plain text only (NO markdown). Use blank lines between options.

A/B/C TEMPLATE (COPY THIS SHAPE EXACTLY):

Weekend outing — pick one:

(A) <Title>
    When: <Day/Date> • <Start Time> – <End Time>
    Where: <Place>
    Notes: <1 short detail>

(B) <Title>
    When: <Day/Date> • <Start Time> – <End Time>
    Where: <Place>
    Notes: <1 short detail>

(C) Custom
    Tell me: <day/date> + <start time> + <place>

Reply exactly: schedule A / schedule B / schedule C

HARD RULES:
- MUST include blank lines between A, B, and C blocks.
- MUST NOT put (A)(B)(C) on the same line.
- Include the final reply line EXACTLY once.

=====================
SMART DECISION POLICY
=====================
A) If user used schedule/add/plan AND you have enough info to draft => type="plan"
   - Plan text MUST be structured like this (copy the shape):

     Draft ready

     <Event Title>
     <Day> • <Start Time> – <End Time>
     Location: <Location>

     Review in Drafting and click Add.

B) If user used schedule/add/plan BUT missing any critical info => type="question" using the A/B/C template above, events=[]
C) If conflict vs EXISTING CALENDAR or PENDING EVENTS => type="conflict"
   - text MUST use the A/B/C template above
   - events MUST contain 2–3 alternative event options (valid schema)
D) If same event already exists (same title + start_time +/- 15 min) => type="confirmation"
   - Ask one short confirmation question (no A/B/C unless needed).

==========================================
ONE-ATTEMPT MULTI-FIELD COLLECTION (BATCH)
==========================================
If the user used schedule/add/plan and ANY of these are missing/unclear:
- date/day
- start time (or clear time window)
- location/place
THEN:
- Ask for ALL missing pieces in ONE question using the A/B/C template.
- (A) and (B) must be fully specified proposals (date + time + place).
- Use ONLY: reference dates, next_saturday, user location, and explicit Memory/Ideas/History hints.
- If you cannot fill a field confidently, do NOT guess. Put the unknown(s) into option (C).

==========================================
NO-HALLUCINATION LOCATION / BUSINESS RULE
========================================
- Never invent real business names or addresses (stores, clubs, venues).
- Only use a specific venue if it exists explicitly in Memory / Ideas / History.
- Otherwise use generic phrasing like:
  "a park near you" / "a nearby store" / "at home".

=========================
WEEKEND OUTING BEHAVIOR
=========================
- If user asks for weekend ideas / outings / family fun AND did NOT use schedule/add/plan:
  Return type="question", events=[]
  Use the A/B/C template; titles should be activities + generic locations.
  End with the exact final reply line.
  Optionally add ONE extra line after the reply line:
  "(Optional: add Sat/Sun + adjust time window)"

=====================
GENERAL STYLE
=====================
- Keep answers concise and readable.
- If you ask a question, ask exactly ONE question (use A/B/C template when collecting fields).
""".strip()

    lines: List[str] = [rules_block]

    if current_time_str:
        lines += ["", f"CURRENT TIME (America/New_York): {current_time_str}".strip()]
    if cheat_sheet:
        lines += ["", "REFERENCE DATES:", cheat_sheet.strip()]
    if next_saturday:
        lines += ["", f'REFERENCE: "Next Saturday" date is: {next_saturday}'.strip()]

    lines += ["", f"USER LOCATION: {current_location}".strip()]
    lines += ["", "EXISTING CALENDAR (Busy Slots):", calendar_data if isinstance(calendar_data, str) else _to_json(calendar_data)]
    lines += ["", "PENDING EVENTS (Treat as Busy):", pending_dump if isinstance(pending_dump, str) else _to_json(pending_dump)]
    lines += ["", "MEMORY BANK (raw json):", memory_dump]
    lines += ["", "CHAT HISTORY (recent):", history_txt]
    lines += ["", "IDEA OPTIONS (if previously offered):", _to_json(idea_options)]
    lines += ["", "USER SELECTED IDEA (if detected):", selected_idea]

    if continuation_hint:
        lines += ["", "CONTINUATION HINT:", continuation_hint.strip()]

    lines += ["", "TASK:", f'Turn the user request into an actionable outcome: "{user_request}"']
    lines += ["", "OUTPUT JSON SCHEMA EXAMPLE (match keys + structure):", _to_json(schema)]

    return "\n".join(lines).strip()


# ---------------------------
# JSON repair prompt
# ---------------------------
def build_json_repair_prompt(bad_text: str) -> str:
    schema = _schema_example()
    lines: List[str] = []
    lines.append("You must output STRICT JSON ONLY. No markdown. No explanations.")
    lines.append("Top-level keys MUST be exactly: type, text, pre_prep, events (no extras).")
    lines.append("")
    lines.append("Fix the following into a valid JSON object that matches EXACTLY this schema and includes ALL fields:")
    lines.append(_to_json(schema))
    lines.append("")
    lines.append('If info is missing, use type="question", events=[], and use the A/B/C TEMPLATE (multi-line) to ask for day/date + start time + place together.')
    lines.append("")
    lines.append("BAD OUTPUT TO FIX:")
    lines.append(str(bad_text or ""))
    return "\n".join(lines).strip()


# ---------------------------
# Weekend forced regeneration prompt (kept stable)
# ---------------------------
def build_weekend_regen_prompt(ctx: Dict[str, Any]) -> str:
    user_request = str(ctx.get("user_request", "") or "")
    current_location = str(ctx.get("current_location", "") or "")
    memory_dump = str(ctx.get("memory_dump", "[]") or "[]")
    ideas_dump = str(ctx.get("ideas_dump", "[]") or "[]")
    constraints = ctx.get("constraints", {}) or {}
    # Variety: titles of ideas already shown (to avoid repetition)
    avoid_ideas = ctx.get("avoid_ideas") or []

    schema_question = _schema_question_example()

    lines: List[str] = []
    lines.append("Return STRICT JSON ONLY. No markdown. No extra text.")
    lines.append("Top-level keys MUST be exactly: type, text, pre_prep, events (no extras).")
    lines.append("")
    lines.append("You MUST return a JSON object matching this schema exactly (include ALL fields):")
    lines.append(_to_json(schema_question))
    lines.append("")
    lines.append(f"User location: {current_location}")
    lines.append(f"Memory bank: {memory_dump}")
    lines.append(f"Ideas Inbox (use when relevant): {ideas_dump}")
    lines.append(f"Constraints (MUST honor): {json.dumps(constraints, ensure_ascii=False)}")
    if avoid_ideas:
        avoid_str = ", ".join(f'"{t}"' for t in avoid_ideas[:6])
        lines.append(f"AVOID REPEATING (already shown to user): {avoid_str}")
        lines.append("You MUST generate DIFFERENT activity titles and locations from the ones above.")
    lines.append("")
    lines.append(f'Task: Generate EXACTLY 3 FRESH family-friendly weekend outing options for: "{user_request}"')
    lines.append("IMPORTANT: Rotate activity types (indoor/outdoor, active/relaxed, day/evening). Do NOT repeat previous suggestions.")
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
    lines.append("    When: <Day/Date> • <Start Time> – <End Time>")
    lines.append("    Where: <Place>")
    lines.append("    Notes: <1 short detail>")
    lines.append("")
    lines.append("(B) <Title>")
    lines.append("    When: <Day/Date> • <Start Time> – <End Time>")
    lines.append("    Where: <Place>")
    lines.append("    Notes: <1 short detail>")
    lines.append("")
    lines.append("(C) <Title>")
    lines.append("    When: <Day/Date> • <Start Time> – <End Time>")
    lines.append("    Where: <Place>")
    lines.append("    Notes: <1 short detail>")
    lines.append("")
    lines.append(_FINAL_REPLY_LINE)
    lines.append("(Optional: add Sat/Sun + adjust time window)")
    lines.append("")
    lines.append("pre_prep FORMAT (must include both):")
    lines.append("1) Tip: <one sentence>")
    lines.append('2) OPTIONS_JSON=[{"key":"A","title":"...","duration_hours":2,"time_window":"Sat 10:00 AM–12:00 PM","notes":"..."}, {"key":"B","title":"...","duration_hours":3,"time_window":"Sun 1:00 PM–4:00 PM","notes":"..."}, {"key":"C","title":"...","duration_hours":2,"time_window":"Sat 4:00 PM–6:00 PM","notes":"..."}]')
    lines.append("")
    lines.append("If user expressed a stable preference, append ONE memory tag at the end of pre_prep on a new line:")
    lines.append('[[MEMORY:{"kind":"preference","key":"...","value":"...","confidence":0.0-1.0,"notes":""}]]')

    return "\n".join(lines).strip()
