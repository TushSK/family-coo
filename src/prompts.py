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
    Checkpoint 2.8 – Full context utilisation.
    All user data (memory, preferences, feedback, ideas, calendar, missions)
    is surfaced in distinct readable blocks the AI uses directly.
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
    ideas_summary  = ctx.get("ideas_summary")  or []
    feedback_raw   = str(ctx.get("feedback_dump", "[]") or "[]")

    # ── HOUSEHOLD PROFILE: human-readable preference lines ────────────────────
    memory_block = _safe_lines_from_kv(memory_summary) if memory_summary else "- (no preferences recorded yet)"

    # ── IDEAS INBOX: pending activities as a clean list ───────────────────────
    ideas_block = _safe_lines_from_ideas(ideas_summary) if ideas_summary else "- (no ideas yet)"

    # ── FEEDBACK: parse into plain completed / skipped summaries ─────────────
    def _build_feedback_block(raw: str) -> str:
        try:
            entries = json.loads(raw or "[]")
            if not isinstance(entries, list) or not entries:
                return "- No feedback recorded yet."
            completed, skipped = [], []
            for e in entries[:30]:
                m    = (e.get("mission") or "").strip()
                r    = (e.get("rating") or "").lower()
                t    = (e.get("feedback_type") or "").lower()
                note = (e.get("reason") or e.get("note") or e.get("feedback") or "").strip()
                if not m:
                    continue
                if t == "completed" or r == "thumbs_up":
                    completed.append(m)
                elif t in ("skipped", "skip") or r == "thumbs_down":
                    skipped.append(f"{m}" + (f" — {note}" if note else ""))
            lines = []
            if completed:
                lines.append("Completed: " + "; ".join(dict.fromkeys(completed))[:300])
            if skipped:
                lines.append("Skipped/avoided: " + "; ".join(dict.fromkeys(skipped))[:300])
            return "\n".join(lines) if lines else "- No feedback recorded yet."
        except Exception:
            return "- No feedback recorded yet."

    feedback_block = _build_feedback_block(feedback_raw)

    schema = _schema_example()

    rules_block = f"""
YOU ARE: Family COO — personal chief-of-staff for the Khandare household in Tampa, FL.
Make every response immediately actionable and deeply personalised to this family.

══════════════════════════════════════════
HOUSEHOLD PROFILE  (use in EVERY response)
══════════════════════════════════════════
{memory_block}

KEY FACTS (always apply):
- Location: Tampa, FL — day trips within 30 miles
- Family: Tushar (adult), Sonam (spouse), Drishti (child) — outings must be family-friendly
- Food: Indian cuisine is the DEFAULT preference — always lead with it for food suggestions
- Fitness: EōS Fitness routine active
- Style: minimal options, no clutter, concrete steps

══════════════════════════════════════════
IDEAS INBOX  (prioritise for outing/plan suggestions)
══════════════════════════════════════════
{ideas_block}

When suggesting weekend plans or outings ALWAYS check the Ideas Inbox first.
Prioritise items from the inbox before generating generic suggestions.

══════════════════════════════════════════
BEHAVIOUR LEARNED FROM FEEDBACK
══════════════════════════════════════════
{feedback_block}

RULES:
- Do NOT re-suggest items in the Skipped/avoided list without a clear new reason.
- Reinforce patterns from the Completed list — the user follows through on these.

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

HARD RULES:
- MUST include blank lines between A, B, and C blocks.
- MUST NOT put (A)(B)(C) on the same line.

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
==========================================
- Never invent real business names or addresses.
- Only use a specific venue if it exists in Memory, Ideas Inbox, or History.
- Otherwise: "a park near you" / "a nearby store" / "at home".

=========================
WEEKEND OUTING BEHAVIOR
=========================
- If user asks for weekend ideas / outings AND did NOT use schedule/add/plan:
  Return type="question", events=[]
  Pull from IDEAS INBOX first. Use A/B/C template with specific days and times.
  End with the exact final reply line.

=====================
GENERAL STYLE
=====================
- Keep answers concise. User prefers minimal options, no clutter.
- If you ask a question, ask exactly ONE question (use A/B/C template when collecting fields).

==============================================
QUICK ACTION MODE (tap-driven, zero follow-up)
==============================================
When the user message starts with [QUICK_ACTION: <tag>], this is a pre-built tap.
The user expects IMMEDIATE tappable options — no clarifying questions.
You MUST:

1. Output the A/B/C template IMMEDIATELY with 2 fully-specified options + (C) Custom.
2. Use HOUSEHOLD PROFILE + IDEAS INBOX + FEEDBACK + CALENDAR — all of it — RIGHT NOW.
3. Each option MUST have: title, When (specific day + time), Where, Notes.
4. DO NOT ask follow-up questions. Pick sensible defaults from the profile and commit.
5. type MUST be "question", events MUST be [].

QUICK ACTION tags:
- plan_weekend   → Check calendar free Sat/Sun slots. Suggest 2 outings from IDEAS INBOX.
- today_briefing → Summarise today. (A) prepare for next event, (B) top pending mission.
- family_outing  → Pick 2 specific outings from IDEAS INBOX. Drishti joining. Ready to schedule.
- dinner_tonight → (A) Indian home cook + dish + prep time, (B) Indian takeout/restaurant + ETA.
- mission_review → Top 2 active missions. (A) tackle NOW with specific steps, (B) 2nd priority.""".strip()


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
    missions_dump = str(ctx.get("missions_dump", "[]") or "[]")
    feedback_dump = str(ctx.get("feedback_dump", "[]") or "[]")
    avoid_ideas   = ctx.get("avoid_ideas") or []
    turn_count    = int(ctx.get("turn_count") or 0)

    lines += ["", "MEMORY BANK (raw json):", memory_dump]
    lines += ["", "PAST MISSIONS (completed/pending — use to personalise ideas):", missions_dump]
    lines += ["", "FEEDBACK & LEARNINGS (from user — use to avoid repeating mistakes):", feedback_dump]
    lines += ["", "CHAT HISTORY (recent):", history_txt]
    lines += ["", "IDEA OPTIONS (if previously offered):", _to_json(idea_options)]
    lines += ["", "USER SELECTED IDEA (if detected):", selected_idea]

    if avoid_ideas:
        avoid_str = ", ".join(f'"{t}"' for t in avoid_ideas[:8])
        lines += ["", f"ALREADY SHOWN TO USER — DO NOT REPEAT: {avoid_str}",
                  "You MUST suggest different activities, venues, and time slots."]

    if turn_count >= 2:
        lines += ["",
                  "⚠️ CONVERSATION LIMIT: This is turn 3+. You MUST resolve now.",
                  "If user is asking for ideas: provide concrete options WITH specific times.",
                  "Do NOT ask follow-up questions. Commit to a plan or A/B/C with full details.",
                  "If any info is still missing, pick the most sensible default and proceed."]

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
    missions_dump = str(ctx.get("missions_dump", "[]") or "[]")
    feedback_dump = str(ctx.get("feedback_dump", "[]") or "[]")
    avoid_ideas = ctx.get("avoid_ideas") or []
    constraints = ctx.get("constraints", {}) or {}

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
    lines.append(f"Past missions (use to personalise — what has this family done?): {missions_dump}")
    lines.append(f"Feedback & learnings (avoid repeating disliked things): {feedback_dump}")
    lines.append(f"Ideas Inbox (prioritise these when relevant): {ideas_dump}")
    lines.append(f"Constraints (MUST honor): {json.dumps(constraints, ensure_ascii=False)}")
    if avoid_ideas:
        avoid_str = ", ".join(f'"{t}"' for t in avoid_ideas[:8])
        lines.append(f"ALREADY SHOWN — DO NOT REPEAT: {avoid_str}")
        lines.append("You MUST suggest completely different activities, venues, and time slots.")
    lines.append("")
    lines.append(f'Task: Generate EXACTLY 3 FRESH, PERSONALISED family-friendly weekend outing options for: "{user_request}"')
    lines.append("Use missions + feedback + ideas to pick activities this specific family would enjoy.")
    lines.append("Rotate activity types: vary indoor/outdoor, active/relaxed, morning/afternoon/evening.")
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