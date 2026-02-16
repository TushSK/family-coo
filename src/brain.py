import json
import datetime
import base64
import re

from groq import Groq


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

    system_prompt = f"""
You are the Family COO.

CURRENT TIME (America/New_York): {current_time_str}

{cheat_sheet}
"Next Saturday" date is: {next_saturday}

USER LOCATION: {current_location}

EXISTING CALENDAR (Busy Slots):
{calendar_data}

PENDING EVENTS (User-approved plans; treat as Busy):
{pending_dump}

MEMORY BANK:
{memory_dump}

CHAT HISTORY (recent):
{history_txt}

TASK:
Turn the user's request into an actionable schedule and NEVER leave dead-ends.
User request: "{user_request}"

NON-NEGOTIABLE RULES
1) STRICT JSON ONLY. No markdown. No backticks. No extra text.
2) Use the REFERENCE DATES list. If user says "Tomorrow", use (+1 day). If user says "Next Saturday", use the given Next Saturday date.
3) ALWAYS finish with exactly one type: plan | conflict | question | confirmation | error

SMART DECISION POLICY
A) If you have enough info to schedule (date + time or clear time window): return type="plan".
B) If missing critical info: return type="question" and ask EXACTLY ONE question (prefer A/B/C options).
C) If conflict detected: return type="conflict" AND include 2–3 alternative event options inside events[].
   Alternatives priority:
   1) nearest free slot same day
   2) same day later
   3) next best day
D) If the same event already exists (same title + start time +/- 15 minutes): return type="confirmation".

CONFLICT DETECTION (MANDATORY)
- Compare the requested time window against BOTH EXISTING CALENDAR and PENDING EVENTS.
- Overlap definition: any time intersection.
- If end_time is missing, assume 60 minutes duration and still output end_time.

OUTPUT JSON SCHEMA (ALWAYS include ALL fields)
{{
  "type": "plan|conflict|question|confirmation|error",
  "text": "short human message",
  "events": [
    {{"title":"", "start_time":"YYYY-MM-DDTHH:MM:SS", "end_time":"YYYY-MM-DDTHH:MM:SS", "location":""}}
  ],
  "pre_prep": "1-2 actionable tips"
}}

RULES FOR EACH TYPE
- question: events must be [] and ask exactly ONE question.
- conflict: events MUST contain 2–3 alternative options the user can choose from.
- plan: include the event(s) to schedule.
""".strip()

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

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.6,
            max_tokens=1024,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()

        # Prefer direct JSON parse
        try:
            json.loads(text)
            return text
        except Exception:
            pass

        # Fallback: extract first JSON object
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            candidate = match.group(1)
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                pass

        return json.dumps(
            {"type": "error", "text": "Model returned non-JSON output.", "events": [], "pre_prep": ""},
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps(
            {"type": "error", "text": f"Groq Error: {str(e)}", "events": [], "pre_prep": ""},
            ensure_ascii=False,
        )
