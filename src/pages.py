# src/pages.py
"""
Tab page renderers for Family COO.
Each function renders one full page — zero LLM tokens, pure local logic.

render_page(active_page, **ctx) is the single entry point called from app.py.

Pages:
  dashboard   — Daily Briefing, Flight Plan, Quick Actions, Pattern Insights
  calendar    — Full calendar list view (placeholder → future)
  memory      — Memory Bank viewer (placeholder → future)
  settings    — Settings (placeholder → future)
"""

from __future__ import annotations
import re
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────
def render_page(active_page: str, **ctx):
    """
    Route active_page to the correct renderer.
    ctx keys accepted by all renderers:
      calendar_events  : list[dict]
      pending_missions : int
      location         : str
      user_name        : str
      memory_rows      : list[dict]   (from MEMORY_FILE)
      mission_rows     : list[dict]   (from MISSION_FILE)
    """
    if active_page == "dashboard":
        _render_dashboard(**ctx)
    elif active_page == "calendar":
        _render_calendar(**ctx)
    elif active_page == "memory":
        _render_memory(**ctx)
    elif active_page == "settings":
        _render_settings(**ctx)


# ─────────────────────────────────────────────────────────────
# HELPERS — shared, zero-token logic
# ─────────────────────────────────────────────────────────────
def _today_events(calendar_events: List[dict]) -> List[dict]:
    today = date.today().isoformat()
    evs = [
        e for e in (calendar_events or [])
        if str(e.get("start_raw") or e.get("start_time") or e.get("start") or "")
           .startswith(today)
    ]
    evs.sort(key=lambda e: str(e.get("start_raw") or e.get("start_time") or ""))
    return evs


def _parse_event_dt(ev: dict) -> Optional[datetime]:
    raw = str(ev.get("start_raw") or ev.get("start_time") or ev.get("start") or "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def _fmt_time(ev: dict) -> str:
    dt = _parse_event_dt(ev)
    if dt:
        return dt.strftime("%I:%M %p").lstrip("0")
    raw = str(ev.get("start_raw") or ev.get("start_time") or "")
    return raw[11:16] if len(raw) > 15 else "—"


def _current_event_idx(today_evs: List[dict]) -> int:
    """Returns index of the currently-active event, or -1."""
    now = datetime.now().astimezone()
    for i, ev in enumerate(today_evs):
        dt = _parse_event_dt(ev)
        if not dt:
            continue
        # estimate end as start + 1h if no end_raw
        end_raw = str(ev.get("end_raw") or ev.get("end_time") or "")
        try:
            end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone()
        except Exception:
            end_dt = dt + timedelta(hours=1)
        if dt <= now <= end_dt:
            return i
    return -1


def _daily_brief_text(today_evs: List[dict], location: str) -> str:
    """
    Build a 1-2 sentence contextual summary — zero LLM, pure template logic.
    """
    now = datetime.now()
    hour = now.hour
    greeting_part = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"

    if not today_evs:
        return f"You have a clear {greeting_part}. A good time to plan ahead or catch up on ideas."

    remaining = [e for e in today_evs if (_parse_event_dt(e) or datetime.min.astimezone()) > now.astimezone()]
    current_idx = _current_event_idx(today_evs)
    current = today_evs[current_idx] if current_idx >= 0 else None

    parts = []
    if current:
        parts.append(f"You're currently in **{current.get('title','')}**.")

    if remaining:
        titles = [e.get("title","") for e in remaining[:3]]
        if len(titles) == 1:
            parts.append(f"Up next: **{titles[0]}**.")
        else:
            parts.append(f"Still ahead today: {', '.join(f'**{t}**' for t in titles[:2])}"
                         + (f" and {len(remaining)-2} more." if len(remaining) > 2 else "."))
    else:
        last = today_evs[-1]
        last_time = _fmt_time(last)
        parts.append(f"Your last event ends at **{last_time}** — the rest of the {greeting_part} is yours.")

    return " ".join(parts)


# ── Contextual Quick Actions — keyword rules, zero LLM ──
_ACTION_RULES = [
    # (title_keywords, location_keywords, action_emoji, action_label)
    (["gym", "workout", "fitness", "eos", "eos fitness"],  [],              "🚗", "Traffic to {loc}"),
    (["grocery", "store", "market", "shopping"],           [],              "🛒", "Update {title} list"),
    (["commute", "drive", "car", "kia", "seltos"],         [],              "⛽", "Check fuel level"),
    (["meeting", "call", "sync", "standup", "zoom", "google meet"], [],     "📋", "Prep notes for {title}"),
    (["dentist", "doctor", "clinic", "appointment"],       [],              "📋", "Pack insurance card"),
    (["school", "pickup", "drop"],                         [],              "🚗", "Check school traffic"),
    (["dinner", "lunch", "breakfast", "meal", "cook"],     [],              "🍳", "Check ingredients"),
    (["flight", "airport", "travel"],                      [],              "🧳", "Check-in online"),
    (["judo", "practice", "lesson", "class"],              [],              "👟", "Pack gear bag"),
    (["yousician", "guitar", "music"],                     [],              "🎸", "Launch Yousician"),
    (["bank", "sip", "invest", "hdfc", "finance"],         [],              "📊", "Check account status"),
]

def _quick_actions(today_evs: List[dict]) -> List[dict]:
    """Return up to 5 contextual quick actions based on today's events."""
    actions = []
    seen_labels = set()
    for ev in today_evs:
        title = (ev.get("title") or "").lower()
        loc   = (ev.get("location") or "").lower()
        for kws, loc_kws, emoji, label_tmpl in _ACTION_RULES:
            if any(k in title or k in loc for k in kws):
                label = (label_tmpl
                         .replace("{title}", ev.get("title","Event"))
                         .replace("{loc}",   ev.get("location","") or ev.get("title","")))
                if label not in seen_labels:
                    actions.append({"emoji": emoji, "label": label, "event": ev.get("title","")})
                    seen_labels.add(label)
        if len(actions) >= 5:
            break
    return actions


# ── Pattern Insights — human-friendly, plain English, improvement plans ──
def _pattern_insights(mission_rows: List[dict], memory_rows: List[dict]) -> List[dict]:
    """
    Returns list of insight dicts:
      {emoji, headline, detail, type: "stat"|"win"|"watch"|"tip"}
    Written like a family COO coach, not a data analyst.
    Includes 1-2 improvement suggestions when patterns warrant it.
    """
    from collections import Counter

    # ── Filter real feedback (ignore test/manual entries) ──
    _noise = {"last plan","plan","trainbrain: bad response","","test missed task",
              "test missed task (rescheduled)","test missed task (rescheduled) (rescheduled)"}
    real_fb = [
        m for m in memory_rows
        if (m.get("mission") or m.get("key") or "").lower().strip() not in _noise
        and m.get("timestamp","") not in {"Just now","Manual"}
    ]
    completed = [m for m in real_fb if "👍" in str(m.get("rating",""))]
    skipped   = [m for m in real_fb if "👎" in str(m.get("rating",""))]
    total     = len(completed) + len(skipped)

    insights = []

    if total == 0:
        return [{"emoji":"💡","type":"tip",
                 "headline":"No history yet",
                 "detail":"Complete a few events and your patterns will start showing up here."}]

    # ── 1. Completion score — plain language ──
    pct = int(100 * len(completed) / total)
    if pct >= 80:
        emoji, type_ = "🟢", "win"
        headline = f"You're nailing it — {pct}% of events completed"
        detail   = (f"Out of {total} tracked events, you followed through on {len(completed)}. "
                    f"That's a strong track record for your family.")
    elif pct >= 60:
        emoji, type_ = "🟡", "stat"
        headline = f"Decent follow-through — {pct}% completed"
        detail   = (f"You completed {len(completed)} out of {total} tracked events. "
                    f"A few easy wins below could push this above 80%.")
    else:
        emoji, type_ = "🔴", "watch"
        headline = f"Almost half your plans aren't happening ({pct}% done)"
        detail   = (f"Only {len(completed)} of {total} events were completed. "
                    f"This usually means events are over-scheduled or poorly timed. "
                    f"See the improvement tip below.")
    insights.append({"emoji":emoji,"type":type_,"headline":headline,"detail":detail})

    # ── 2. What's being skipped — name the actual activity ──
    skip_activity_counts: Counter = Counter()
    for m in skipped:
        title = (m.get("mission") or "").lower()
        for kw, label in [
            ("outing","family outings"), ("aquarium","aquarium trips"),
            ("judo","judo classes"), ("gym","gym sessions"),
            ("doctor","doctor visits"), ("grocery","grocery runs"),
            ("temple","temple visits"), ("market","market visits"),
            ("chess","chess classes"), ("volleyball","volleyball"),
        ]:
            if kw in title:
                skip_activity_counts[label] += 1
    if skip_activity_counts:
        top_skip, skip_count = skip_activity_counts.most_common(1)[0]
        insights.append({"emoji":"⚠️","type":"watch",
            "headline": f"{top_skip.capitalize()} keep getting dropped ({skip_count}× missed)",
            "detail":   (f"These show up planned but don't happen. "
                         f"Either the timing is off, or it needs a shorter commitment to start.")})

    # ── 3. What's consistently working — name it ──
    done_activity_counts: Counter = Counter()
    for m in completed:
        title = (m.get("mission") or "").lower()
        for kw, label in [
            ("judo","judo classes"), ("gym","gym"), ("doctor","doctor visits"),
            ("blood work","blood work"), ("outing","outings"),
            ("grocery","grocery runs"), ("chess","chess"),
        ]:
            if kw in title:
                done_activity_counts[label] += 1
    if done_activity_counts:
        top_done, done_count = done_activity_counts.most_common(1)[0]
        insights.append({"emoji":"✅","type":"win",
            "headline": f"{top_done.capitalize()} — your most reliable commitment ({done_count}× done)",
            "detail":   (f"This is a habit that's clearly working for your family. "
                         f"Protect this time slot — don't let other things crowd it out.")})

    # ── 4. Best completion day (only real dates) ──
    day_counts: Counter = Counter()
    for m in completed:
        ts = m.get("timestamp","")
        try:
            d = datetime.fromisoformat(ts).strftime("%A")
            day_counts[d] += 1
        except Exception:
            pass
    if day_counts and day_counts.most_common(1)[0][1] >= 2:
        best_day, best_n = day_counts.most_common(1)[0]
        insights.append({"emoji":"📅","type":"stat",
            "headline": f"{best_day}s are your most productive day",
            "detail":   (f"You've completed {best_n} events on {best_day}s. "
                         f"A good day to schedule important family tasks.")})

    # ── Improvement Plans (only shown when there's a clear problem) ──
    improvements = []

    # Plan A: low completion rate + skipped outings
    if pct < 65 and "outing" in str(skip_activity_counts):
        improvements.append({"emoji":"💡","type":"tip",
            "headline": "Plan outings closer to home first",
            "detail":   ("Family outings often get cancelled because they feel like a big production. "
                         "Try a 1-hour local option — a park, a market, a short drive. "
                         "Small wins build the habit.")})

    # Plan B: reliable judo/gym + any skipped items
    if done_activity_counts.get("judo classes",0) >= 3 and len(skipped) >= 2:
        improvements.append({"emoji":"💡","type":"tip",
            "headline": "Use your judo routine as an anchor",
            "detail":   ("You show up consistently for judo. "
                         "Try scheduling one other commitment right after — like a quick grocery run "
                         "or a family dinner plan. Piggyback on a habit that already works.")})

    # Plan C: general low follow-through
    if pct < 60 and not improvements:
        improvements.append({"emoji":"💡","type":"tip",
            "headline": "Schedule fewer things, finish more",
            "detail":   ("With a completion rate under 60%, the issue is usually too many plans. "
                         "Pick 2 family commitments per week max and protect those. "
                         "Quality over quantity.")})

    return (insights + improvements[:2])[:5]


# ─────────────────────────────────────────────────────────────
# DASHBOARD PAGE
# ─────────────────────────────────────────────────────────────

# ── COO Action Plan builder — zero LLM, pattern + schedule aware ──
def _build_action_plan(
    today_evs: list, mission_rows: list, memory_rows: list, now
) -> list:
    """
    Returns ranked list of proactive action dicts:
      {emoji, action, reason, priority: "high"|"medium"|"low"}
    Sources: today's events + pattern data from memory/mission logs.
    Zero LLM tokens.
    """
    from collections import Counter
    items = []

    # ── 1. Pre-event prep actions (within 90 min of event start) ──
    for ev in today_evs:
        dt = _parse_event_dt(ev)
        if not dt:
            continue
        mins_away = (dt - now.astimezone()).total_seconds() / 60
        if 0 < mins_away <= 90:
            title = ev.get("title","Event")
            loc   = ev.get("location","")
            tl    = title.lower()
            ll    = loc.lower()
            priority = "high" if mins_away <= 30 else "medium"
            t_fmt = dt.strftime("%I:%M %p").lstrip("0")

            if any(k in tl or k in ll for k in ["gym","fitness","workout","eos"]):
                items.append({"emoji":"🚗","priority":priority,
                    "action": f"Check traffic to {loc or title}",
                    "reason": f"Starts at {t_fmt} — {int(mins_away)} min away."})
            elif any(k in tl for k in ["meeting","call","sync","standup","zoom","google meet"]):
                items.append({"emoji":"📋","priority":priority,
                    "action": f"Review agenda for {title}",
                    "reason": f"Starts at {t_fmt} — prep now to hit the ground running."})
            elif any(k in tl or k in ll for k in ["grocery","store","market","shopping"]):
                items.append({"emoji":"🛒","priority":priority,
                    "action": f"Finalize {loc or 'shopping'} list",
                    "reason": f"Starts at {t_fmt} — check pantry before heading out."})
            elif any(k in tl for k in ["judo","practice","class","lesson"]):
                items.append({"emoji":"👟","priority":priority,
                    "action": f"Pack gear for {title}",
                    "reason": f"Starts at {t_fmt} — don't forget your bag."})
            elif any(k in tl for k in ["dentist","doctor","clinic","appointment"]):
                items.append({"emoji":"📁","priority":priority,
                    "action": "Grab insurance card & ID",
                    "reason": f"{title} at {t_fmt}."})
            elif any(k in tl for k in ["commute","drive","kia","seltos","car"]):
                items.append({"emoji":"⛽","priority":priority,
                    "action": "Check fuel / pre-cool car",
                    "reason": f"Drive event at {t_fmt}."})
            else:
                items.append({"emoji":"⏰","priority":priority,
                    "action": f"Wrap up — {title} in {int(mins_away)} min",
                    "reason": f"Scheduled at {t_fmt}."})

    # ── 2. Pattern-based proactive nudges (from history) ──
    completed = [m for m in memory_rows if "👍" in str(m.get("rating",""))]
    skipped   = [m for m in memory_rows if "👎" in str(m.get("rating",""))]
    total_fb  = len(completed) + len(skipped)

    if total_fb >= 5:
        pct = int(100 * len(completed) / total_fb)
        if pct < 60:
            # Find most-skipped activity
            skip_words = []
            for m in skipped:
                skip_words += re.findall(r'\b[a-z]{4,}\b', m.get("mission","").lower())
            common = [w for w, _ in Counter(skip_words).most_common(5)
                      if w not in {"this","that","with","from","have","will","the","and","for","your"}]
            if common:
                items.append({"emoji":"🔁","priority":"medium",
                    "action": f"Reschedule or drop '{common[0]}' events",
                    "reason": f"You've skipped {len(skipped)} of {total_fb} tracked events ({100-pct}% skip rate). "
                              f"Consider blocking this type or removing it."})
        elif pct >= 80 and len(completed) >= 10:
            items.append({"emoji":"🏆","priority":"low",
                "action": "You're on a strong run — protect tomorrow's schedule",
                "reason": f"{pct}% completion over {total_fb} events. "
                          f"Block distractions to keep the streak."})

    # ── 3. Day-of-week pattern nudge ──
    day_today = now.strftime("%A")
    day_done = Counter()
    day_skip = Counter()
    for m in memory_rows:
        ts = m.get("timestamp","")
        try:
            d = datetime.fromisoformat(ts).strftime("%A")
            if "👍" in str(m.get("rating","")): day_done[d] += 1
            else: day_skip[d] += 1
        except Exception:
            pass
    if day_skip.get(day_today, 0) >= 3 and day_skip[day_today] > day_done.get(day_today, 0):
        items.append({"emoji":"⚠️","priority":"medium",
            "action": f"Heads up: {day_today}s are historically tough",
            "reason": f"You've skipped {day_skip[day_today]} events on {day_today}s vs "
                      f"{day_done.get(day_today,0)} completed. Plan lighter today."})

    # ── 4. Busiest-hour buffer nudge ──
    hour_counts: dict = {}
    for m in mission_rows:
        try:
            h = datetime.fromisoformat(
                m.get("end_time","").replace("Z","+00:00")).astimezone().hour
            hour_counts[h] = hour_counts.get(h,0) + 1
        except Exception:
            pass
    if hour_counts:
        busiest = max(hour_counts, key=hour_counts.get)
        if busiest == now.hour or busiest == now.hour + 1:
            ampm = f"{busiest % 12 or 12} {'AM' if busiest < 12 else 'PM'}"
            items.append({"emoji":"⏱️","priority":"low",
                "action": f"Buffer time around {ampm} — your busiest hour",
                "reason": "History shows this slot gets crowded. "
                          "Avoid scheduling anything new here."})

    # Cap at 5, sort by priority
    _rank = {"high":0,"medium":1,"low":2}
    items.sort(key=lambda x: _rank.get(x.get("priority","low"),2))
    return items[:5]



# ═══════════════════════════════════════════════════════════════
# generate_smart_actions()
# Reads 4 real data sources; zero LLM tokens.
# Returns top-3 ranked action dicts: {emoji, action, reason, priority, score}
# ═══════════════════════════════════════════════════════════════
def generate_smart_actions(
    calendar_events: list,
    user_email: str,
    weather_temp: str,
    weather_desc: str,
    now,
) -> list:
    """
    Three triggers — scored and ranked, top 3 returned.

    TRIGGER 1 — FREE TIME  : calendar empty for next 3h → suggest from Ideas Inbox
    TRIGGER 2 — PREP       : event coming up today → suggest prep task
    TRIGGER 3 — ROUTINE    : preferences + habits + time-of-day → suggest a habit/routine
    """
    import json, os

    suggestions = []   # each: {emoji, action, reason, priority, score (int, higher=more urgent)}

    # ── Load all 4 data sources ──────────────────────────────
    # 1. Ideas (memory/users/{safe_email}_ideas.json)
    try:
        from src.utils import safe_email_from_user, _ideas_path_for_user, load_user_ideas
        safe_email = safe_email_from_user(user_email) if user_email else ""
        ideas = load_user_ideas(safe_email) if safe_email else []
    except Exception:
        ideas = []
    active_ideas = [i for i in ideas if i.get("status") == "active"]

    # 2. Upcoming missions from mission_log.json
    try:
        from src.utils import _read_json, MISSION_FILE
        all_missions = _read_json(MISSION_FILE)
    except Exception:
        all_missions = []
    pending_missions = [m for m in all_missions if m.get("status") == "pending"]

    # 3. Preferences from memory/users/{safe_email}.json
    try:
        from src.utils import load_user_memory
        prefs_raw = load_user_memory(user_email, limit=100) if user_email else []
    except Exception:
        prefs_raw = []
    # Build preference dict: key → latest value
    prefs: dict = {}
    for p in prefs_raw:
        k = (p.get("key") or "").lower().strip()
        v = (p.get("value") or "").lower().strip()
        if k and v:
            prefs[k] = v  # last-write wins (sorted by ts_utc naturally)

    # 4. Habits/History from feedback_log.json (memory/feedback_log.json)
    try:
        from src.utils import load_feedback_rows
        feedback = load_feedback_rows()
    except Exception:
        feedback = []
    # Compute per-activity completion rate
    from collections import Counter
    fb_done  = Counter()
    fb_skip  = Counter()
    for fb in feedback:
        title = (fb.get("mission") or "").lower()
        if not title or title in {"last plan", "plan", "trainbrain: bad response"}:
            continue
        if "👍" in str(fb.get("rating", "")):
            for kw in ["judo", "gym", "workout", "outing", "doctor", "blood work",
                       "grocery", "volleyball", "market", "aquarium"]:
                if kw in title:
                    fb_done[kw] += 1
        elif "👎" in str(fb.get("rating", "")):
            for kw in ["judo", "gym", "workout", "outing", "doctor", "blood work",
                       "grocery", "volleyball", "market", "aquarium"]:
                if kw in title:
                    fb_skip[kw] += 1

    # ── Shared dedup set: tracks idea texts already used across triggers ──
    _used_idea_texts: set = set()

    # ────────────────────────────────────────────────────────
    # TRIGGER 1 — FREE TIME
    # If calendar has no event in the next 3 hours, suggest from Ideas Inbox.
    # Uses date-seeded rotation so a different idea surfaces each day.
    # ────────────────────────────────────────────────────────
    import datetime as _dt_mod
    now_aware = now.astimezone()
    window_end = now_aware + _dt_mod.timedelta(hours=3)

    def _ev_in_window(e):
        dt = _parse_event_dt(e)
        return dt is not None and now_aware <= dt <= window_end
    busy_next_3h = any(_ev_in_window(e) for e in (calendar_events or []))

    if not busy_next_3h and active_ideas:
        is_weekend   = now.weekday() >= 5
        is_morning   = 6 <= now.hour < 12
        outdoor_pref = any("outdoor" in k or "hiking" in v for k, v in prefs.items())
        family_pref  = "family" in prefs.get("outing_style", "")
        weather_nice = weather_desc != "—" and not any(
            w in weather_desc.lower() for w in ["rain","storm","thunder","fog"])

        # Score every active idea
        scored = []
        for idea in active_ideas:
            tl    = idea.get("text","").lower()
            score = int((idea.get("confidence", 0.5) - 0.5) * 50)
            if is_weekend and any(k in tl for k in ["park","hike","market","beach","kayak","outing"]):
                score += 30
            if outdoor_pref and any(k in tl for k in ["hike","park","river","nature","trail","kayak"]):
                score += 25
            if weather_nice and any(k in tl for k in ["park","hike","beach","outdoor","market","kayak"]):
                score += 20
            if family_pref and any(k in tl for k in ["family","kids","park","market"]):
                score += 15
            if is_morning and any(k in tl for k in ["breakfast","market","morning"]):
                score += 10
            scored.append((score, idea))

        # Group by score tier; within each tier rotate by day-of-year
        # so the same idea doesn't dominate every session
        scored.sort(key=lambda x: -x[0])
        if scored:
            top_score = scored[0][0]
            # Collect all ideas within 15 pts of top score (same tier)
            tier = [idea for s, idea in scored if s >= top_score - 15]
            # Deterministic daily rotation: offset by day ordinal
            day_offset = _dt_mod.date.today().toordinal() % len(tier)
            best_idea  = tier[day_offset]

            text = best_idea.get("text","")
            tl   = text.lower()
            is_outdoor = any(k in tl for k in ["park","hike","river","beach","kayak","trail","market"])
            if is_outdoor and weather_nice:
                reason = (f"Schedule clear for 3h and weather is {weather_desc.lower()}. "
                          f"Perfect window for this.")
            elif is_outdoor:
                reason = "Schedule clear — good window to act on this."
            else:
                reason = "Free time now — this idea has been waiting in your inbox."
            _used_idea_texts.add(text.lower())
            suggestions.append({
                "emoji": "💡", "action": text, "reason": reason,
                "priority": "medium", "score": 60 + top_score, "source": "ideas",
            })

    # ────────────────────────────────────────────────────────
    # TRIGGER 2 — PREP
    # Next event happening today → generate a specific prep suggestion
    # ────────────────────────────────────────────────────────
    today_evs_sorted = _today_events(calendar_events or [])
    next_ev = None
    for ev in today_evs_sorted:
        dt = _parse_event_dt(ev)
        if dt and dt > now_aware:
            next_ev = ev
            break

    if next_ev:
        title   = next_ev.get("title", "")
        tl      = title.lower()
        loc     = next_ev.get("location", "")
        dt      = _parse_event_dt(next_ev)
        mins_away = int((dt - now_aware).total_seconds() / 60) if dt else 999
        t_fmt   = dt.strftime("%I:%M %p").lstrip("0") if dt else ""
        priority = "high" if mins_away <= 45 else "medium"
        score    = 90 if mins_away <= 45 else 70

        # Look up this activity in feedback to calibrate tone
        activity_kw = next((k for k in ["judo","gym","workout","doctor","grocery","volleyball"]
                            if k in tl), None)
        completion_note = ""
        if activity_kw:
            done = fb_done.get(activity_kw, 0)
            skip = fb_skip.get(activity_kw, 0)
            if done + skip >= 3 and done > skip:
                completion_note = f" You consistently complete {activity_kw} events — you've got this."
            elif done + skip >= 3 and skip > done:
                completion_note = f" Note: you've skipped this type before — commit now."

        if any(k in tl or k in loc.lower() for k in ["gym","fitness","workout","eos"]):
            suggestions.append({"emoji":"🚗","priority":priority,"score":score,"source":"prep",
                "action": f"Check traffic to {loc or 'gym'}",
                "reason": f"Gym at {t_fmt} — leave early to warm up, not rush.{completion_note}"})
        elif any(k in tl for k in ["judo","chess","class","practice","lesson"]):
            bag_items = "gi, belt, water bottle" if "judo" in tl else "notebook, gear"
            suggestions.append({"emoji":"🎒","priority":priority,"score":score,"source":"prep",
                "action": f"Pack bag for {title}",
                "reason": f"Starts at {t_fmt} ({mins_away} min away). Pack: {bag_items}.{completion_note}"})
        elif any(k in tl for k in ["meeting","call","sync","standup","zoom","google meet"]):
            suggestions.append({"emoji":"📋","priority":priority,"score":score,"source":"prep",
                "action": f"5-min prep for {title}",
                "reason": f"At {t_fmt}. Review notes, mute notifications, join link ready.{completion_note}"})
        elif any(k in tl or k in loc.lower() for k in ["grocery","store","market","patel"]):
            suggestions.append({"emoji":"🛒","priority":priority,"score":score,"source":"prep",
                "action": f"Finalise shopping list before {loc or 'store'}",
                "reason": f"Heading out at {t_fmt}. Check pantry now to avoid a second trip."})
        elif any(k in tl for k in ["doctor","dentist","clinic","appointment","pediatrician"]):
            suggestions.append({"emoji":"📁","priority":priority,"score":score,"source":"prep",
                "action": "Pack: insurance card, ID, any test reports",
                "reason": f"{title} at {t_fmt}.{completion_note}"})
        elif any(k in tl for k in ["flight","airport","travel"]):
            suggestions.append({"emoji":"🧳","priority":"high","score":95,"source":"prep",
                "action": "Check-in online + bag ready",
                "reason": f"Travel event at {t_fmt}. Do not leave this to last minute."})
        else:
            if mins_away <= 60:
                suggestions.append({"emoji":"⏰","priority":priority,"score":score,"source":"prep",
                    "action": f"Wrap up — {title} in {mins_away} min",
                    "reason": f"Scheduled at {t_fmt}. Block distractions now."})

    # ────────────────────────────────────────────────────────
    # TRIGGER 3 — ROUTINE / HABIT
    # Preferences + feedback history + time-of-day → proactive habit nudge
    # ────────────────────────────────────────────────────────
    is_weekend = now.weekday() >= 5
    hour = now.hour

    # 3a. Volleyball (pattern: evenings 3-4 days/week)
    volleyball_pref = "volleyball" in prefs.get("weekly_activity", "")
    if volleyball_pref and 16 <= hour <= 20 and not busy_next_3h:
        done  = fb_done.get("volleyball", 0)
        score = 50 + done * 3
        suggestions.append({"emoji":"🏐","priority":"medium","score":score,"source":"routine",
            "action": "Time for volleyball?",
            "reason": f"Your pattern: volleyball evenings 3-4×/week. "
                      f"You've completed it {done} times in your history. "
                      f"Check your usual court availability."})

    # 3b. Outdoor activity (preference: outdoor/hiking, nice weather)
    # Skips any idea already surfaced by Trigger 1 to avoid duplicates.
    outdoor_pref = any("outdoor" in k or "hiking" in v for k, v in prefs.items())
    weather_nice = weather_desc != "—" and not any(
        w in weather_desc.lower() for w in ["rain","storm","thunder","fog"])
    if outdoor_pref and weather_nice and not busy_next_3h:
        outdoor_ideas = [
            i for i in active_ideas
            if any(k in i.get("text","").lower()
                   for k in ["hike","park","river","trail","kayak","beach"])
            and i.get("text","").lower() not in _used_idea_texts   # skip already-shown
        ]
        if outdoor_ideas:
            # Rotate by week number so it changes weekly even if ideas list is small
            week_offset = _dt_mod.date.today().isocalendar()[1] % len(outdoor_ideas)
            chosen = outdoor_ideas[week_offset]
            best_outdoor = chosen.get("text","")
            _used_idea_texts.add(best_outdoor.lower())
            score = 55 if is_weekend else 35
            suggestions.append({"emoji":"🥾","priority":"medium","score":score,"source":"routine",
                "action": f"Weather is {weather_desc.lower()} — go for: {best_outdoor}",
                "reason": f"You prefer outdoor activities and this idea is in your inbox. "
                          f"Good time slot: next 3 hours are free."})

    # 3c. Weekend morning breakfast outing
    food_pref = prefs.get("food_preference", "")
    weekend_window = prefs.get("weekend_time_window", "")
    if is_weekend and 7 <= hour <= 11 and not busy_next_3h:
        food_note = "South Indian breakfast" if "south indian" in food_pref else "breakfast"
        suggestions.append({"emoji":"🍽️","priority":"low","score":40,"source":"routine",
            "action": f"Weekend morning — find a {food_note} spot",
            "reason": f"Your preference: '{food_pref[:60]}'. "
                      f"Weekend mornings are your preferred breakfast window."})

    # 3d. Decision-friction nudge (user tendency to overthink)
    friction_pref = prefs.get("decision_friction","")
    if "overthink" in friction_pref and len(suggestions) >= 2:
        # Don't add more, but flag it
        pass

    # ── Dedup by action text, sort by score, top 3 ──────────
    seen_actions: set = set()
    deduped = []
    for s in suggestions:
        key = s.get("action","").lower().strip()
        if key not in seen_actions:
            seen_actions.add(key)
            deduped.append(s)
    deduped.sort(key=lambda x: -x.get("score", 0))
    top3 = deduped[:3]

    # Attach debug metadata to first item (or standalone) so caller can show expander
    _dbg = {
        "busy_next_3h":    busy_next_3h,
        "active_ideas":    len(active_ideas),
        "pending_missions":len(pending_missions),
        "prefs_loaded":    len(prefs),
        "feedback_entries":len(feedback),
        "all_suggestions": len(suggestions),
        "triggers_fired":  list({s["source"] for s in suggestions}),
        "user_email_used": user_email,
    }
    return top3, _dbg


def _render_dashboard(
    calendar_events=None,
    pending_missions=0,
    location="Tampa, FL",
    user_name="",
    user_email="",
    memory_rows=None,
    mission_rows=None,
    **_,
):
    import streamlit as st
    import requests

    # Recover user_email from session state if caller didn't pass it
    if not user_email:
        user_email = (st.session_state.get("user_email")
                      or st.session_state.get("user_id")
                      or "")

    now = datetime.now()
    today_evs = _today_events(calendar_events or [])

    # ── Header ──
    hour = now.hour
    greeting = "Good Morning" if hour < 12 else "Good Afternoon" if hour < 17 else "Good Evening"
    st.markdown(
        f"<h2 style='margin:0 0 10px 0;font-weight:900;letter-spacing:-0.5px;'>{greeting}"
        f"{', ' + user_name if user_name else ''} 👋</h2>",
        unsafe_allow_html=True,
    )

    # ── Daily Brief banner ──
    brief = _daily_brief_text(today_evs, location)
    st.markdown(
        f"<div style='background:#eef2ff;border-left:4px solid #4f46e5;"
        f"border-radius:8px;padding:10px 14px;margin-bottom:16px;"
        f"font-size:0.88rem;color:#1e293b;line-height:1.55;'>"
        f"<span style='font-weight:800;'>🔄 Daily Brief:</span> {brief}</div>",
        unsafe_allow_html=True,
    )

    # ── KPI row ──
    # ── Weather: try session cache first, then wttr.in, then open-meteo fallback ──
    weather_temp, weather_desc, weather_icon = "—", "—", "🌤️"
    _cached = st.session_state.get("_weather_cache")
    _cache_ts = st.session_state.get("_weather_cache_ts", 0)
    import time as _time
    _cache_age = _time.time() - _cache_ts

    if _cached and _cache_age < 1800:  # reuse for 30 min
        weather_temp, weather_desc, weather_icon = _cached
    else:
        try:
            city = location.split(",")[0].strip().replace(" ", "+")
            resp = requests.get(f"https://wttr.in/{city}?format=j1", timeout=4)
            if resp.status_code == 200:
                cur = resp.json()["current_condition"][0]
                weather_temp = f"{cur['temp_F']}°F"
                weather_desc = cur["weatherDesc"][0]["value"]
        except Exception:
            pass

        # Fallback: open-meteo (lat/lon for Tampa hardcoded; user_location overrides)
        if weather_temp == "—":
            try:
                _coords = {"Tampa": (27.9506, -82.4572), "Tampa, FL": (27.9506, -82.4572)}
                lat, lon = _coords.get(location, (27.9506, -82.4572))
                om = requests.get(
                    f"https://api.open-meteo.com/v1/forecast"
                    f"?latitude={lat}&longitude={lon}"
                    f"&current_weather=true&temperature_unit=fahrenheit",
                    timeout=4,
                )
                if om.status_code == 200:
                    cw = om.json().get("current_weather", {})
                    temp_c = cw.get("temperature")
                    wmo   = int(cw.get("weathercode", 0))
                    if temp_c is not None:
                        weather_temp = f"{temp_c}°F"
                        # WMO weather codes → description + icon
                        _wmo_map = {
                            0: ("Clear sky", "☀️"), 1: ("Mainly clear", "🌤️"),
                            2: ("Partly cloudy", "⛅"), 3: ("Overcast", "☁️"),
                            45: ("Foggy", "🌫️"), 48: ("Icy fog", "🌫️"),
                            51: ("Light drizzle", "🌦️"), 61: ("Light rain", "🌧️"),
                            63: ("Moderate rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
                            80: ("Showers", "🌦️"), 95: ("Thunderstorm", "⛈️"),
                        }
                        weather_desc, weather_icon = _wmo_map.get(wmo, ("Partly cloudy", "⛅"))
            except Exception:
                pass

        # Derive icon from desc if wttr.in succeeded
        if weather_temp != "—" and weather_desc != "—" and weather_icon == "🌤️":
            dl = weather_desc.lower()
            weather_icon = ("☀️" if "sun" in dl or "clear" in dl
                           else "🌧️" if "rain" in dl or "shower" in dl
                           else "⛈️" if "thunder" in dl or "storm" in dl
                           else "☁️" if "cloud" in dl or "overcast" in dl
                           else "🌫️" if "fog" in dl or "mist" in dl
                           else "💨" if "wind" in dl else "🌤️")

        # Cache result
        st.session_state["_weather_cache"]    = (weather_temp, weather_desc, weather_icon)
        st.session_state["_weather_cache_ts"] = _time.time()

    remaining_today = [
        e for e in today_evs
        if (_parse_event_dt(e) or datetime.min.astimezone()) > now.astimezone()
    ]

    _s = ("background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;")
    _l = ("font-size:0.7rem;font-weight:800;color:#94a3b8;text-transform:uppercase;"
          "letter-spacing:.07em;margin-bottom:6px;")
    _v = "font-size:1.85rem;font-weight:900;color:#0f172a;line-height:1;"
    _u = "font-size:0.73rem;font-weight:700;margin-top:6px;"

    k1, k2, k3 = st.columns(3, gap="small")
    with k1:
        color = "#ef4444" if pending_missions > 0 else "#10b981"
        sub   = "🔔 Review required" if pending_missions > 0 else "↑ All caught up!"
        st.markdown(f"""<div style="{_s}"><div style="{_l}">Pending Actions</div>
            <div style="{_v}">{pending_missions}</div>
            <div style="{_u} color:{color};">{sub}</div></div>""",
            unsafe_allow_html=True)
    with k2:
        sub2 = f"↑ Today" if remaining_today else "✅ All done"
        st.markdown(f"""<div style="{_s}"><div style="{_l}">Remaining Events</div>
            <div style="{_v}">{len(remaining_today)}</div>
            <div style="{_u} color:#10b981;">{sub2}</div></div>""",
            unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div style="{_s}"><div style="{_l}">{location.split(",")[0]} Weather</div>
            <div style="{_v}">{weather_temp}</div>
            <div style="{_u} color:#10b981;">{weather_icon} {weather_desc}</div></div>""",
            unsafe_allow_html=True)

    st.markdown("<div style='margin:14px 0 0 0;'></div>", unsafe_allow_html=True)

    # ── Two-column lower section ──
    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_left:
        # ── Flight Plan timeline ──
        st.markdown(
            "<div style='display:flex;align-items:center;gap:7px;margin-bottom:10px;'>"
            "<span style='font-size:1.2rem;'>✈️</span>"
            "<span style='font-size:1rem;font-weight:900;color:#0f172a;'>Today's Flight Plan</span>"
            "</div>", unsafe_allow_html=True)

        if not today_evs:
            st.markdown(
                "<div style='padding:12px 14px;background:#f8fafc;border-radius:8px;"
                "border:1px solid #e2e8f0;color:#64748b;font-size:0.85rem;'>"
                "No events today — ask the brain to plan your day!</div>",
                unsafe_allow_html=True)
        else:
            current_idx = _current_event_idx(today_evs)
            for i, ev in enumerate(today_evs):
                title    = (ev.get("title") or "Event").strip()
                time_str = _fmt_time(ev)
                loc_str  = ev.get("location") or ""
                is_cur   = (i == current_idx)
                is_past  = (i < current_idx) or (
                    current_idx == -1 and
                    (_parse_event_dt(ev) or datetime.now().astimezone()) < now.astimezone()
                )

                dot_color   = "#4f46e5" if is_cur else "#94a3b8" if is_past else "#10b981"
                card_bg     = "#f8f7ff" if is_cur else "#f8fafc"
                border_left = f"4px solid {dot_color}"
                time_label  = f"{time_str} (Current)" if is_cur else time_str
                time_color  = "#4f46e5" if is_cur else "#64748b"
                title_weight= "800" if is_cur else "600"

                st.markdown(
                    f"<div style='display:flex;gap:8px;align-items:flex-start;margin-bottom:6px;'>"
                    f"<div style='display:flex;flex-direction:column;align-items:center;"
                    f"padding-top:5px;min-width:8px;'>"
                    f"<div style='width:8px;height:8px;border-radius:50%;"
                    f"background:{dot_color};flex-shrink:0;'></div>"
                    f"<div style='width:2px;flex:1;background:#e2e8f0;min-height:24px;'></div>"
                    f"</div>"
                    f"<div style='background:{card_bg};border-left:{border_left};"
                    f"border-radius:8px;padding:8px 12px;flex:1;margin-bottom:2px;'>"
                    f"<div style='font-size:0.75rem;font-weight:800;color:{time_color};"
                    f"margin-bottom:2px;'>{time_label}</div>"
                    f"<div style='font-weight:{title_weight};color:#0f172a;font-size:0.88rem;'>"
                    f"{title}</div>"
                    + (f"<div style='font-size:0.73rem;color:#64748b;margin-top:1px;'>📍 {loc_str}</div>" if loc_str else "")
                    + f"</div></div>",
                    unsafe_allow_html=True,
                )

    with col_right:
        # ── COO Action Plan (proactive, pattern-driven) ──
        # Smart actions from real data sources (ideas, missions, prefs, feedback)
        plan_items, _sa_debug = generate_smart_actions(
            calendar_events=calendar_events or [],
            user_email=user_email,
            weather_temp=weather_temp,
            weather_desc=weather_desc,
            now=now,
        )
        insights   = _pattern_insights(mission_rows or [], memory_rows or [])

        st.markdown(
            "<div style='display:flex;align-items:center;gap:7px;margin-bottom:4px;'>"
            "<span style='font-size:1.2rem;'>⚡</span>"
            "<span style='font-size:1rem;font-weight:900;color:#0f172a;'>Your COO Action Plan</span>"
            "</div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:0.73rem;color:#94a3b8;margin-bottom:8px;'>"
            "Ideas · schedule · preferences · history — zero tokens.</div>",
            unsafe_allow_html=True)

        if plan_items:
            _SRC_BADGE = {
                "ideas":   ("#4f46e5", "💡 Idea"),
                "prep":    ("#f59e0b", "📅 Prep"),
                "routine": ("#10b981", "🔄 Routine"),
                "mission": ("#ef4444", "🔔 Mission"),
            }
            for item in plan_items:
                p_color = {"high":"#ef4444","medium":"#f59e0b","low":"#10b981"}.get(
                    item.get("priority","low"), "#10b981")
                p_label = {"high":"Urgent","medium":"Soon","low":"Later"}.get(
                    item.get("priority","low"), "")
                src_col, src_txt = _SRC_BADGE.get(item.get("source",""), ("#64748b","⚡ Action"))
                st.markdown(
                    f"<div style='display:flex;align-items:flex-start;gap:9px;"
                    f"padding:9px 11px;margin-bottom:6px;"
                    f"background:#fff;border:1px solid #e2e8f0;border-radius:10px;"
                    f"border-left:3px solid {p_color};'>"
                    f"<div style='font-size:1.1rem;padding-top:1px;line-height:1;'>{item['emoji']}</div>"
                    f"<div style='flex:1;min-width:0;'>"
                    f"<div style='display:flex;justify-content:space-between;"
                    f"align-items:flex-start;gap:4px;margin-bottom:2px;'>"
                    f"<span style='font-weight:800;font-size:0.83rem;color:#0f172a;line-height:1.3;'>"
                    f"{item['action']}</span>"
                    f"<div style='display:flex;gap:3px;flex-shrink:0;margin-top:1px;'>"
                    f"<span style='font-size:0.62rem;font-weight:700;color:{src_col};"
                    f"background:{src_col}18;padding:1px 5px;border-radius:20px;white-space:nowrap;'>"
                    f"{src_txt}</span>"
                    f"<span style='font-size:0.62rem;font-weight:700;color:{p_color};"
                    f"background:{p_color}18;padding:1px 5px;border-radius:20px;white-space:nowrap;'>"
                    f"{p_label}</span>"
                    f"</div></div>"
                    f"<div style='font-size:0.74rem;color:#64748b;line-height:1.4;'>"
                    f"{item['reason']}</div>"
                    f"</div></div>",
                    unsafe_allow_html=True)
        else:
            st.markdown(
                "<div style='color:#64748b;font-size:0.85rem;padding:10px;"
                "background:#f8fafc;border-radius:8px;'>No urgent actions right now. "
                "Your schedule looks clear — tell the brain to plan something!</div>",
                unsafe_allow_html=True)

        # ── Pattern Insights + Improvement Plans ──
        st.markdown(
            "<div style='display:flex;align-items:center;gap:7px;margin:14px 0 4px 0;'>"
            "<span style='font-size:1.2rem;'>🧠</span>"
            "<span style='font-size:1rem;font-weight:900;color:#0f172a;'>Pattern Insights</span>"
            "</div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:0.73rem;color:#94a3b8;margin-bottom:8px;'>"
            "Learnt from your history — zero tokens used.</div>",
            unsafe_allow_html=True)

        for ins in insights:
            is_tip = ins.get("type") == "tip"
            if is_tip:
                # Improvement plan — distinct card style
                st.markdown(
                    f"<div style='padding:9px 12px;margin-bottom:5px;"
                    f"background:#fffbeb;border-radius:8px;"
                    f"border:1px solid #fde68a;border-left:3px solid #f59e0b;'>"
                    f"<div style='font-size:0.78rem;font-weight:800;color:#92400e;"
                    f"margin-bottom:2px;'>{ins['emoji']} {ins['headline']}</div>"
                    f"<div style='font-size:0.74rem;color:#78350f;line-height:1.45;'>"
                    f"{ins['detail']}</div></div>",
                    unsafe_allow_html=True)
            else:
                # Regular insight
                border = {"win":"#10b981","watch":"#ef4444","stat":"#e2e8f0"}.get(
                    ins.get("type","stat"),"#e2e8f0")
                bg    = {"win":"#f0fdf4","watch":"#fff5f5","stat":"#f8fafc"}.get(
                    ins.get("type","stat"),"#f8fafc")
                st.markdown(
                    f"<div style='padding:8px 11px;margin-bottom:5px;"
                    f"background:{bg};border-radius:8px;"
                    f"border:1px solid {border};'>"
                    f"<div style='font-size:0.78rem;font-weight:800;color:#0f172a;"
                    f"margin-bottom:2px;'>{ins['emoji']} {ins['headline']}</div>"
                    f"<div style='font-size:0.74rem;color:#475569;line-height:1.45;'>"
                    f"{ins['detail']}</div></div>",
                    unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# CALENDAR VIEW PAGE  (placeholder — future)
# ─────────────────────────────────────────────────────────────
def _render_calendar(calendar_events=None, pending_missions=0, location="", user_email="", **_):
    import streamlit as st
    from datetime import date, datetime, timedelta
    from src.flow import add_to_calendar, reject_draft

    events = calendar_events or []
    today  = date.today()

    # ── helpers ────────────────────────────────────────────────
    def _dt(ev):
        raw = str(ev.get("start_raw") or ev.get("start_time") or "")
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
        except Exception:
            return None

    def _end_dt(ev):
        raw = str(ev.get("end_raw") or ev.get("end_time") or "")
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
        except Exception:
            start = _dt(ev)
            return start + timedelta(hours=1) if start else None

    def _fmt_hour(dt) -> str:
        """Cross-platform time format. Strips leading zero."""
        if not dt:
            return ""
        return dt.strftime("%I:%M %p").lstrip("0") or "12:00 AM"

    def _hm(ev):
        return _fmt_hour(_dt(ev)) or "—"

    def _hm_end(ev):
        return _fmt_hour(_end_dt(ev))

    def _ev_date(ev) -> date:
        dt = _dt(ev)
        return dt.date() if dt else today

    def _is_allday(ev):
        raw = str(ev.get("start_raw") or ev.get("start_time") or "")
        return "T" not in raw

    # ── compute bandwidth metrics ───────────────────────────────
    week_start = today - timedelta(days=today.weekday())        # Monday
    week_days  = [week_start + timedelta(days=i) for i in range(7)]

    week_evs = [e for e in events if _ev_date(e) in week_days]

    # busiest day
    day_counts: dict = {}
    for e in week_evs:
        d = _ev_date(e)
        day_counts[d] = day_counts.get(d, 0) + 1
    busiest_day = max(day_counts, key=lambda d: day_counts[d]) if day_counts else None
    busiest_label = busiest_day.strftime("%A") if busiest_day else "—"
    busiest_sub   = f"{day_counts[busiest_day]} events" if busiest_day else ""

    # free evenings (no events 5 PM-9 PM)
    free_evenings = []
    for d in week_days:
        eve_evs = [
            e for e in week_evs
            if _ev_date(e) == d and not _is_allday(e) and (
                (dt := _dt(e)) and dt.hour >= 17 and dt.hour < 21
            )
        ]
        if not eve_evs:
            free_evenings.append(d)
    free_ev_labels = [d.strftime("%a") for d in free_evenings[:3]]

    # pending drafts
    drafts = st.session_state.get("pending_events") or []
    ndrafts = len(drafts)

    # conflict detection
    def _conflicts(evs):
        """Return list of (ev_a, ev_b) pairs that overlap."""
        pairs = []
        timed = [(e, _dt(e), _end_dt(e)) for e in evs if _dt(e)]
        timed.sort(key=lambda x: x[1])
        for i in range(len(timed)):
            for j in range(i + 1, len(timed)):
                a_start, a_end = timed[i][1], timed[i][2]
                b_start, b_end = timed[j][1], timed[j][2]
                if a_end and b_start and a_end > b_start:
                    pairs.append((timed[i][0], timed[j][0]))
        return pairs

    all_conflicts = _conflicts(week_evs)

    # ── CSS ───────────────────────────────────────────────────
    st.markdown("""
    <style>
    /* Calendar page tokens */
    .cal-page { font-family: Inter, system-ui, sans-serif; }

    /* Bandwidth KPI row */
    .cal-kpi-grid {
        display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:14px 0 20px;
    }
    @media(max-width:700px){ .cal-kpi-grid{ grid-template-columns:repeat(2,1fr); } }
    .cal-kpi {
        background:var(--card-bg); border:1px solid var(--border-subtle);
        border-radius:14px; padding:16px 18px;
        box-shadow:var(--sh-sm);
    }
    .cal-kpi-label {
        font-size:.68rem; font-weight:800; color:var(--muted);
        text-transform:uppercase; letter-spacing:.07em; margin-bottom:6px;
    }
    .cal-kpi-value {
        font-size:1.9rem; font-weight:900; color:var(--text);
        letter-spacing:-.03em; line-height:1;
    }
    .cal-kpi-sub {
        margin-top:6px; font-size:.75rem; font-weight:700;
        display:inline-flex; align-items:center; gap:4px;
        padding:2px 7px; border-radius:6px;
    }
    .cal-kpi-sub.green  { background:#dcfce7; color:#15803d; }
    .cal-kpi-sub.amber  { background:#fef9c3; color:#92400e; }
    .cal-kpi-sub.red    { background:#fee2e2; color:#991b1b; }
    .cal-kpi-sub.blue   { background:#dbeafe; color:#1e40af; }
    [data-theme="dark"] .cal-kpi-sub.green  { background:#14532d; color:#86efac; }
    [data-theme="dark"] .cal-kpi-sub.amber  { background:#451a03; color:#fcd34d; }
    [data-theme="dark"] .cal-kpi-sub.red    { background:#450a0a; color:#fca5a5; }
    [data-theme="dark"] .cal-kpi-sub.blue   { background:#1e3a5f; color:#93c5fd; }

    /* Week grid */
    .cal-week-grid {
        display:grid; grid-template-columns:repeat(7,1fr); gap:8px; margin:14px 0 22px;
    }
    @media(max-width:700px){ .cal-week-grid{ grid-template-columns:repeat(4,1fr); } }
    @media(max-width:480px){ .cal-week-grid{ grid-template-columns:repeat(2,1fr); } }
    .cal-day-col { display:flex; flex-direction:column; gap:5px; }
    .cal-day-hdr {
        text-align:center; font-size:.68rem; font-weight:800;
        color:var(--muted); text-transform:uppercase; letter-spacing:.06em;
        padding-bottom:4px;
    }
    .cal-day-hdr.today { color:#4f46e5; }
    .cal-chip {
        border-radius:7px; padding:5px 7px; font-size:.72rem; font-weight:700;
        line-height:1.3; border-left:3px solid transparent; cursor:default;
        word-break:break-word;
    }
    .cal-chip.blue   { background:#dbeafe; color:#1e40af; border-color:#3b82f6; }
    .cal-chip.green  { background:#dcfce7; color:#166534; border-color:#22c55e; }
    .cal-chip.purple { background:#ede9fe; color:#5b21b6; border-color:#8b5cf6; }
    .cal-chip.amber  { background:#fef9c3; color:#92400e; border-color:#f59e0b; }
    .cal-chip.rose   { background:#ffe4e6; color:#9f1239; border-color:#f43f5e; }
    .cal-chip.slate  { background:var(--chip-bg); color:var(--muted); border-color:var(--border); }
    .cal-chip.free   {
        background:transparent; color:var(--muted); border:1px dashed var(--border);
        border-left:3px dashed var(--border); font-style:italic; font-weight:600;
    }
    [data-theme="dark"] .cal-chip.blue   { background:#1e3a5f; color:#93c5fd; }
    [data-theme="dark"] .cal-chip.green  { background:#14532d; color:#86efac; }
    [data-theme="dark"] .cal-chip.purple { background:#2e1065; color:#c4b5fd; }
    [data-theme="dark"] .cal-chip.amber  { background:#451a03; color:#fcd34d; }
    [data-theme="dark"] .cal-chip.rose   { background:#4c0519; color:#fda4af; }

    /* Section headers */
    .cal-section-hdr {
        display:flex; align-items:center; gap:9px;
        font-size:1.1rem; font-weight:900; color:var(--text);
        letter-spacing:-.02em; margin:6px 0 4px;
    }
    .cal-section-sub {
        font-size:.83rem; color:var(--muted); margin:0 0 14px; font-weight:500;
    }
    .cal-divider { height:1px; background:var(--border-subtle); margin:24px 0 18px; }

    /* Proactive planning card */
    .cal-obs-card {
        background:var(--card-bg); border:1px solid var(--border-subtle);
        border-radius:14px; padding:16px 18px; box-shadow:var(--sh-sm);
        margin-bottom:12px;
    }
    .cal-obs-label {
        font-size:.7rem; font-weight:800; color:#4f46e5;
        text-transform:uppercase; letter-spacing:.07em; margin-bottom:5px;
    }
    .cal-obs-text { font-size:.88rem; color:var(--text); font-weight:500; line-height:1.5; }

    /* Draft / conflict card */
    .cal-draft-card {
        background:var(--card-bg); border:1px solid var(--border-subtle);
        border-radius:14px; padding:16px 18px; box-shadow:var(--sh-sm);
        margin-bottom:12px;
    }
    .cal-draft-title { font-size:.92rem; font-weight:800; color:var(--text); margin-bottom:3px; }
    .cal-draft-meta  { font-size:.78rem; color:var(--muted); font-weight:500; }
    .cal-conflict-box {
        background:#fff1f2; border:1px solid #fecdd3;
        border-radius:8px; padding:9px 12px; margin:10px 0 12px;
        font-size:.78rem; color:#9f1239; font-weight:600; line-height:1.4;
    }
    [data-theme="dark"] .cal-conflict-box {
        background:#4c0519; border-color:#9f1239; color:#fda4af;
    }

    /* Pro tips */
    .cal-tips-grid {
        display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:14px;
    }
    @media(max-width:700px){ .cal-tips-grid{ grid-template-columns:1fr; } }
    .cal-tip {
        background:var(--card-bg); border:1px solid var(--border-subtle);
        border-radius:12px; padding:14px 16px; box-shadow:var(--sh-xs);
    }
    .cal-tip-icon { font-size:1.3rem; margin-bottom:7px; }
    .cal-tip-title { font-size:.8rem; font-weight:800; color:var(--text); margin-bottom:4px; }
    .cal-tip-body  { font-size:.76rem; color:var(--muted); line-height:1.5; font-weight:500; }
    </style>
    """, unsafe_allow_html=True)

    # ── PAGE HEADER ────────────────────────────────────────────
    st.markdown("""
    <div class="cal-section-hdr">🗂️ Logistics & Planning Hub</div>
    <p class="cal-section-sub">Analyze bandwidth, manage conflicts, and proactively plan your week.</p>
    """, unsafe_allow_html=True)

    if not events:
        st.info("📅 No events loaded. Connect your Google Calendar in **Settings** to get started.")
        _render_pro_tips()
        return

    # ── 1. WEEKLY BANDWIDTH KPIs ───────────────────────────────
    st.markdown('<div class="cal-section-hdr">📊 Weekly Bandwidth</div>', unsafe_allow_html=True)

    free_ev_str   = ", ".join(free_ev_labels) if free_ev_labels else "None"
    free_ev_color = "green" if len(free_evenings) >= 2 else "amber" if len(free_evenings) == 1 else "red"
    draft_color   = "amber" if ndrafts > 0 else "green"
    draft_sub_txt = "Requires Approval" if ndrafts > 0 else "All clear"

    st.markdown(f"""
    <div class="cal-kpi-grid">
      <div class="cal-kpi">
        <div class="cal-kpi-label">Events (Next 7 Days)</div>
        <div class="cal-kpi-value">{len(week_evs)}</div>
        <div class="cal-kpi-sub blue">📅 {len(week_evs)} scheduled</div>
      </div>
      <div class="cal-kpi">
        <div class="cal-kpi-label">Busiest Day</div>
        <div class="cal-kpi-value">{busiest_label}</div>
        <div class="cal-kpi-sub amber">⬆ {busiest_sub}</div>
      </div>
      <div class="cal-kpi">
        <div class="cal-kpi-label">Free Evenings</div>
        <div class="cal-kpi-value">{len(free_evenings)} Days</div>
        <div class="cal-kpi-sub {free_ev_color}">⬆ {free_ev_str}</div>
      </div>
      <div class="cal-kpi">
        <div class="cal-kpi-label">Pending Drafts</div>
        <div class="cal-kpi-value">{ndrafts}</div>
        <div class="cal-kpi-sub {draft_color}">⬆ {draft_sub_txt}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="cal-divider"></div>', unsafe_allow_html=True)

    # ── 2. WEEK AT A GLANCE ────────────────────────────────────
    st.markdown('<div class="cal-section-hdr">🗓️ Week at a Glance</div>', unsafe_allow_html=True)

    COLORS = ["blue", "green", "purple", "amber", "rose", "slate", "blue"]
    # Assign a stable color per unique event title
    color_map: dict = {}
    color_idx = 0
    for ev in week_evs:
        t = ev.get("title", "")
        if t not in color_map:
            color_map[t] = COLORS[color_idx % len(COLORS)]
            color_idx += 1

    # Build 7 columns
    cols = st.columns(7)
    for col_i, (col, d) in enumerate(zip(cols, week_days)):
        is_today = (d == today)
        hdr_cls  = "cal-day-hdr today" if is_today else "cal-day-hdr"
        day_evs  = sorted(
            [e for e in week_evs if _ev_date(e) == d],
            key=lambda e: str(e.get("start_raw") or "")
        )
        with col:
            st.markdown(
                f'<div class="{hdr_cls}">{d.strftime("%a")}<br>'
                f'<span style="font-size:.8rem;font-weight:700;">{d.day}</span></div>',
                unsafe_allow_html=True,
            )
            if day_evs:
                chips = ""
                for ev in day_evs[:4]:   # cap at 4 chips per column to avoid overflow
                    clr  = color_map.get(ev.get("title",""), "slate")
                    time = "" if _is_allday(ev) else f'<span style="font-size:.65rem;opacity:.7;">{_hm(ev)}</span><br>'
                    chips += f'<div class="cal-chip {clr}">{time}{ev.get("title","")}</div>'
                if len(day_evs) > 4:
                    chips += f'<div class="cal-chip slate">+{len(day_evs)-4} more</div>'
                st.markdown(chips, unsafe_allow_html=True)
            else:
                st.markdown('<div class="cal-chip free">Free Day</div>', unsafe_allow_html=True)

    st.markdown('<div class="cal-divider"></div>', unsafe_allow_html=True)

    # ── 3. PROACTIVE PLANNING + DRAFTS & CONFLICTS ─────────────
    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        st.markdown('<div class="cal-section-hdr">🎯 Proactive Planning</div>', unsafe_allow_html=True)

        # Build a contextual observation from free slots
        now_dt = datetime.now().astimezone()
        free_today = today not in day_counts
        tomorrow   = today + timedelta(days=1)
        free_tmrw  = tomorrow not in day_counts

        if free_today:
            obs = "You have a clear day today — great time to tackle something from your Ideas Inbox or plan ahead."
        elif free_tmrw:
            obs = f"Tomorrow looks open. Consider scheduling something meaningful or blocking focus time."
        elif free_evenings:
            day_name = free_evenings[0].strftime("%A")
            obs = f"You have a free evening this **{day_name}**. A good opportunity to recharge or explore an idea."
        elif len(week_evs) >= 8:
            obs = f"Heavy week ahead with **{len(week_evs)} events**. Consider blocking buffer time to avoid burnout."
        else:
            obs = "Your week looks balanced. Keep an eye on the busiest day and protect recovery time."

        st.markdown(f"""
        <div class="cal-obs-card">
            <div class="cal-obs-label">💡 AI Observation</div>
            <div class="cal-obs-text">{obs}</div>
        </div>
        """, unsafe_allow_html=True)

        # Conflict summary
        if all_conflicts:
            st.markdown(f"""
            <div class="cal-obs-card" style="border-left:3px solid #f43f5e;">
                <div class="cal-obs-label" style="color:#e11d48;">⚠️ Conflicts Detected</div>
                <div class="cal-obs-text">
                    {len(all_conflicts)} scheduling conflict{"s" if len(all_conflicts)>1 else ""} found this week.
                    Review them in <b>Drafts & Conflicts</b> →
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Quick action buttons
        st.markdown("**Quick Actions**")
        qa1, qa2 = st.columns(2)
        with qa1:
            if st.button("📋 View Today", key="cal_view_today", use_container_width=True):
                st.session_state["cal_filter"] = "today"
                st.rerun()
        with qa2:
            if st.button("🔍 Find Free Slot", key="cal_find_free", use_container_width=True):
                st.session_state["cal_filter"] = "free"
                st.rerun()

        # Today's timeline
        filter_mode = st.session_state.get("cal_filter")
        if filter_mode == "today":
            today_evs = sorted(
                [e for e in events if _ev_date(e) == today],
                key=lambda e: str(e.get("start_raw") or "")
            )
            st.markdown(f"**Today's Schedule — {today.strftime('%A, %b %d')}**")
            if today_evs:
                for ev in today_evs:
                    t = _hm(ev)
                    te = _hm_end(ev)
                    title = ev.get("title", "Event")
                    loc   = ev.get("location", "")
                    clr = color_map.get(title, "blue")
                    chip_html = (
                        f'<div class="cal-chip {clr}" style="margin-bottom:5px;">'
                        f'<span style="font-size:.7rem;opacity:.8;">{t} – {te}</span><br>'
                        f'<b>{title}</b>'
                        f'{(" · 📍 " + loc) if loc else ""}'
                        f'</div>'
                    )
                    st.markdown(chip_html, unsafe_allow_html=True)
            else:
                st.markdown('<div class="cal-chip free" style="margin-bottom:5px;">Nothing scheduled — enjoy the freedom!</div>', unsafe_allow_html=True)
            if st.button("✖ Close", key="cal_close_today", use_container_width=True):
                st.session_state["cal_filter"] = None
                st.rerun()

        elif filter_mode == "free":
            st.markdown("**Free Slots This Week**")
            if free_evenings:
                for d in free_evenings:
                    st.markdown(
                        f'<div class="cal-chip free" style="margin-bottom:5px;">'
                        f'{d.strftime("%A, %b %d")} — Free Evening</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("No fully free evenings this week.")
            free_days_week = [d for d in week_days if d not in day_counts]
            for d in free_days_week:
                st.markdown(
                    f'<div class="cal-chip green" style="margin-bottom:5px;">'
                    f'{d.strftime("%A, %b %d")} — Completely Free</div>',
                    unsafe_allow_html=True,
                )
            if st.button("✖ Close", key="cal_close_free", use_container_width=True):
                st.session_state["cal_filter"] = None
                st.rerun()

    with right_col:
        st.markdown('<div class="cal-section-hdr">📌 Drafts & Conflicts</div>', unsafe_allow_html=True)

        if not drafts and not all_conflicts:
            st.markdown(
                '<div class="cal-obs-card" style="text-align:center;color:var(--muted);">'
                '<div style="font-size:1.5rem;margin-bottom:6px;">✅</div>'
                '<div style="font-weight:700;">All clear</div>'
                '<div style="font-size:.8rem;margin-top:3px;">No pending drafts or conflicts.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            # Pending drafts
            for i, draft in enumerate(drafts):
                title    = draft.get("title", "Untitled")
                start    = draft.get("start_time", "")
                end_time = draft.get("end_time", "")
                loc      = draft.get("location", "")
                desc     = draft.get("description", "")

                # Format times
                try:
                    s_dt = datetime.fromisoformat(start)
                    e_dt = datetime.fromisoformat(end_time) if end_time else None
                    time_str = s_dt.strftime("%a %b %d  %I:%M %p")
                    if e_dt:
                        time_str += " - " + e_dt.strftime("%I:%M %p")
                except Exception:
                    time_str = start[:16].replace("T", " ")

                # Conflict check against existing week events
                draft_conflicts = []
                try:
                    d_start = datetime.fromisoformat(start).astimezone()
                    d_end   = datetime.fromisoformat(end_time).astimezone() if end_time else d_start + timedelta(hours=1)
                    for ev in week_evs:
                        e_start = _dt(ev)
                        e_end   = _end_dt(ev)
                        if e_start and e_end and e_end > d_start and e_start < d_end:
                            draft_conflicts.append(ev)
                except Exception:
                    pass

                conflict_html = ""
                if draft_conflicts:
                    for dc in draft_conflicts[:2]:
                        ct = _hm(dc)
                        ce = _hm_end(dc)
                        conflict_html += (
                            f'<div class="cal-conflict-box">'
                            f'⚠️ <b>Conflict:</b> Overlaps with {dc.get("title","")} '
                            f'({ct} – {ce}).</div>'
                        )

                st.markdown(f"""
                <div class="cal-draft-card">
                    <div style="font-size:.68rem;font-weight:800;color:#f59e0b;
                                text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px;">
                        🟡 Pending Approval ({i+1})
                    </div>
                    <div class="cal-draft-title">{title}</div>
                    <div class="cal-draft-meta">{time_str}{(" · 📍 " + loc) if loc else ""}</div>
                    {conflict_html}
                </div>
                """, unsafe_allow_html=True)

                btn_a, btn_b, btn_c = st.columns([1.2, 1.2, 1])
                with btn_a:
                    if st.button("➕ Add to Calendar", key=f"cal_add_{i}", type="primary", use_container_width=True):
                        with st.spinner("Adding…"):
                            add_to_calendar(draft)
                        st.rerun()
                with btn_b:
                    if draft_conflicts and st.button("📅 Auto-Reschedule", key=f"cal_reschedule_{i}", use_container_width=True):
                        st.toast("Auto-reschedule: use the Home tab to ask the AI for a new time.")
                with btn_c:
                    if st.button("🗑️", key=f"cal_reject_{i}", use_container_width=True, help="Discard draft"):
                        reject_draft(draft)
                        st.rerun()

            # Calendar conflicts (non-draft)
            if all_conflicts:
                st.markdown("**⚠️ Calendar Conflicts This Week**")
                for ev_a, ev_b in all_conflicts[:3]:
                    ta, tb = _hm(ev_a), _hm(ev_b)
                    st.markdown(f"""
                    <div class="cal-conflict-box">
                        ⚠️ <b>{ev_a.get("title","")}</b> ({ta}) overlaps with
                        <b>{ev_b.get("title","")}</b> ({tb})
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown('<div class="cal-divider"></div>', unsafe_allow_html=True)

    # ── 4. PRO TIPS ────────────────────────────────────────────
    _render_pro_tips()


def _render_pro_tips():
    import streamlit as st
    st.markdown('<div class="cal-section-hdr">💡 Pro Tips</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="cal-tips-grid">
      <div class="cal-tip">
        <div class="cal-tip-icon">🛡️</div>
        <div class="cal-tip-title">Protect buffer time</div>
        <div class="cal-tip-body">Add 15-min buffers between back-to-back meetings.
        Back-to-back drains focus — even a short break resets your cognitive state.</div>
      </div>
      <div class="cal-tip">
        <div class="cal-tip-icon">🌅</div>
        <div class="cal-tip-title">Own your mornings</div>
        <div class="cal-tip-body">Block 8-10 AM for deep work 3 days a week.
        Morning hours have the highest cognitive bandwidth — guard them from meetings.</div>
      </div>
      <div class="cal-tip">
        <div class="cal-tip-icon">🔁</div>
        <div class="cal-tip-title">Weekly review ritual</div>
        <div class="cal-tip-body">Every Sunday, spend 10 minutes planning the week ahead.
        Reviewing conflicts and free slots proactively saves hours of reactive scrambling.</div>
      </div>
      <div class="cal-tip">
        <div class="cal-tip-icon">📦</div>
        <div class="cal-tip-title">Batch similar tasks</div>
        <div class="cal-tip-body">Group errands, calls, and admin into single blocks.
        Context switching costs 20+ minutes each time — batching compounds efficiency.</div>
      </div>
      <div class="cal-tip">
        <div class="cal-tip-icon">🚫</div>
        <div class="cal-tip-title">Learn to decline</div>
        <div class="cal-tip-body">Every "yes" is a "no" to something else.
        A meeting with no clear agenda or outcome is a draft worth discarding.</div>
      </div>
      <div class="cal-tip">
        <div class="cal-tip-icon">🌙</div>
        <div class="cal-tip-title">Guard family evenings</div>
        <div class="cal-tip-body">Free evenings are your most valuable resource.
        Treat them like appointments — block them in the calendar before work fills them.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)



def _render_memory(memory_rows=None, user_email="", **_):
    """
    Context Engine page — surfaces what the AI knows about the household.
    Sections:
      0. KPI bar
      1. Household Identity Clusters  (left col)
      2. How AI Uses This Data        (left col, below clusters)
      3. Recently Learned — confirm / forget  (right col)
      4. Quick Idea Inbox             (right col, below deductions)
      5. Pro Tips
    Zero LLM tokens — pure local logic + file I/O.
    """
    import streamlit as st
    import os

    email = user_email or st.session_state.get("user_email", "")
    rows  = list(memory_rows or [])

    prefs: list = []
    ideas: list = []
    try:
        from src.utils import (
            _safe_user_key, _user_memory_path, _read_json,
            load_user_ideas, add_idea_to_inbox,
        )
        if email:
            safe       = _safe_user_key(email)
            pref_path  = _user_memory_path(email)
            prefs      = _read_json(pref_path) if os.path.exists(pref_path) else []
            ideas      = load_user_ideas(safe)
    except Exception:
        pass

    active_ideas = [i for i in ideas if (i.get("status") or "active") == "active"]

    # ── CSS ──────────────────────────────────────────────────────
    st.markdown("""
<style>
.mem-title{font-size:1.35rem;font-weight:900;letter-spacing:-.025em;
    display:flex;align-items:center;gap:9px;color:var(--text);margin:0 0 4px;}
.mem-sub{font-size:.88rem;color:var(--muted);margin:0 0 18px;}
.mem-divider{height:1px;background:var(--border-subtle);margin:22px 0;}
.mem-kpi-row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:4px;}
.mem-kpi{background:var(--card-bg);border:1px solid var(--border-subtle);
    border-radius:12px;padding:14px 18px;flex:1 1 110px;min-width:100px;
    box-shadow:var(--sh-xs);}
.mem-kpi-label{font-size:.68rem;font-weight:800;text-transform:uppercase;
    letter-spacing:.06em;color:var(--muted);margin-bottom:5px;}
.mem-kpi-val{font-size:1.75rem;font-weight:900;color:var(--text);line-height:1;}
.mem-sec-hdr{font-size:1.05rem;font-weight:900;color:var(--text);
    display:flex;align-items:center;gap:8px;margin:0 0 6px;}
.mem-sec-sub{font-size:.82rem;color:var(--muted);margin:0 0 14px;}
.mem-cluster-card{background:var(--card-bg);border:1px solid var(--border-subtle);
    border-radius:14px;padding:18px 20px;box-shadow:var(--sh-sm);}
.mem-cluster-group{margin-bottom:14px;}
.mem-cluster-group-label{font-size:.82rem;font-weight:800;color:var(--text);
    margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border-subtle);}
.mem-chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:6px;}
.mem-chip{display:inline-flex;align-items:center;gap:5px;padding:5px 12px;
    border-radius:20px;font-size:.78rem;font-weight:700;border:1.5px solid;}
.chip-pref{background:#ecfdf5;color:#065f46;border-color:#6ee7b7;}
.chip-pattern{background:#ede9fe;color:#4c1d95;border-color:#c4b5fd;}
.chip-idea{background:#fef3c7;color:#92400e;border-color:#fcd34d;}
[data-theme="dark"] .chip-pref{background:#052e16;color:#86efac;border-color:#065f46;}
[data-theme="dark"] .chip-pattern{background:#1e1040;color:#c4b5fd;border-color:#4c1d95;}
[data-theme="dark"] .chip-idea{background:#2d1a00;color:#fcd34d;border-color:#92400e;}
.mem-ai-box{background:var(--chip-bg);border-radius:12px;padding:14px 16px;
    border:1px solid var(--border-subtle);font-size:.85rem;line-height:1.6;}
.mem-ai-fact{color:#6366f1;font-size:.82rem;}
[data-theme="dark"] .mem-ai-fact{color:#818cf8;}
.mem-deduction-card{background:var(--card-bg);border:1px solid var(--border-subtle);
    border-radius:14px;padding:16px 18px;margin-bottom:12px;box-shadow:var(--sh-sm);}
.mem-deduction-text{font-size:.9rem;color:var(--text);line-height:1.5;margin-bottom:8px;}
.mem-deduction-meta{font-size:.72rem;color:var(--muted);margin-bottom:10px;}
.mem-idea-item{background:var(--chip-bg);border:1px solid var(--border-subtle);
    border-radius:10px;padding:10px 14px;margin-bottom:7px;
    display:flex;justify-content:space-between;align-items:center;gap:8px;}
.mem-idea-text{font-size:.85rem;color:var(--text);flex:1;}
.mem-idea-ts{font-size:.7rem;color:var(--muted);white-space:nowrap;}
.mem-tip-card{background:var(--card-bg);border:1px solid var(--border-subtle);
    border-radius:12px;padding:16px 18px;box-shadow:var(--sh-xs);
    border-left:4px solid #6366f1;margin-bottom:12px;}
[data-theme="dark"] .mem-tip-card{border-left-color:#818cf8;}
</style>
""", unsafe_allow_html=True)

    # ── HEADER ────────────────────────────────────────────────────
    st.markdown('<p class="mem-title">&#x1F9E0; Context Engine</p>', unsafe_allow_html=True)
    st.markdown('<p class="mem-sub">How the Family COO understands your household.</p>',
                unsafe_allow_html=True)

    _, rbtn_col = st.columns([9, 1])
    with rbtn_col:
        if st.button("\U0001f504", key="mem_refresh", help="Refresh memory data"):
            st.rerun()

    # ── KPI BAR ───────────────────────────────────────────────────
    num_prefs    = len([p for p in prefs if p.get("kind") == "preference"])
    num_patterns = len([p for p in prefs if p.get("kind") == "pattern"])
    num_ideas    = len(active_ideas)
    num_learned  = len(rows)

    chip_ideas  = "chip-amber" if num_ideas > 0  else "chip-green"
    chip_learn  = "chip-green" if num_learned > 0 else "chip-blue"

    st.markdown(
        f'<div class="mem-kpi-row">'
        f'<div class="mem-kpi"><div class="mem-kpi-label">Preferences</div>'
        f'<div class="mem-kpi-val">{num_prefs}</div></div>'
        f'<div class="mem-kpi"><div class="mem-kpi-label">Patterns</div>'
        f'<div class="mem-kpi-val">{num_patterns}</div></div>'
        f'<div class="mem-kpi"><div class="mem-kpi-label">Ideas Inbox</div>'
        f'<div class="mem-kpi-val">{num_ideas}</div></div>'
        f'<div class="mem-kpi"><div class="mem-kpi-label">Learned</div>'
        f'<div class="mem-kpi-val">{num_learned}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="mem-divider"></div>', unsafe_allow_html=True)

    # ── TWO-COLUMN LAYOUT ─────────────────────────────────────────
    left_col, right_col = st.columns([1.1, 1], gap="large")

    # ════════════════════════════════════
    # LEFT — Identity Clusters + AI box
    # ════════════════════════════════════
    with left_col:
        st.markdown('<p class="mem-sec-hdr">&#x1F9EC; Household Identity Clusters</p>',
                    unsafe_allow_html=True)

        CLUSTER_MAP = {
            "Diet & Dining":       ["food", "diet", "meal", "cuisine", "eat", "cook",
                                    "breakfast", "snack", "protein"],
            "Media & Interests":   ["media", "show", "series", "movie", "watch", "read",
                                    "book", "podcast", "python", "ai", "tech", "code",
                                    "music", "game", "cricket"],
            "Logistics & Routine": ["schedule", "routing", "drive", "car", "fitness",
                                    "gym", "exercise", "volleyball", "sport", "class",
                                    "weekly", "activity", "routine", "proactive",
                                    "scheduling", "frequency"],
            "Family & Outings":    ["family", "kid", "daughter", "son", "outing", "beach",
                                    "temple", "adventure", "weekend", "holiday"],
            "Style & Preferences": ["tone", "style", "response", "decision", "prefer",
                                    "approach", "framing"],
        }

        EMOJI_MAP = {
            "food": "&#x1F37D;", "diet": "&#x1F37D;", "cuisine": "&#x1F37D;",
            "fitness": "&#x1F4AA;", "gym": "&#x1F4AA;", "sport": "&#x1F4AA;",
            "volleyball": "&#x1F3D0;", "cricket": "&#x1F3CF;",
            "python": "&#x1F4BB;", "ai": "&#x1F4BB;", "tech": "&#x1F4BB;",
            "music": "&#x1F3B5;", "series": "&#x1F3AC;", "movie": "&#x1F3AC;",
            "car": "&#x1F697;", "drive": "&#x1F697;",
            "family": "&#x1F46A;", "daughter": "&#x1F467;",
            "schedule": "&#x1F4C5;", "outing": "&#x1F334;", "beach": "&#x1F334;",
        }

        def _cluster(entry):
            txt = (str(entry.get("key","")) + " " + str(entry.get("value",""))).lower()
            for c, kws in CLUSTER_MAP.items():
                if any(k in txt for k in kws):
                    return c
            return "Other"

        def _chip_emoji(entry):
            txt = str(entry.get("key","")).lower()
            for kw, em in EMOJI_MAP.items():
                if kw in txt:
                    return em
            return "&#x2726;" if entry.get("kind") == "preference" else "&#x1F501;"

        def _conf(entry):
            c = entry.get("confidence")
            return f" ({int(float(c)*100)}%)" if c else ""

        def _chip_cls(entry):
            if entry.get("kind") == "idea":
                return "chip-idea"
            return "chip-pref" if entry.get("kind") == "preference" else "chip-pattern"

        clusters: dict = {}
        for entry in prefs:
            clusters.setdefault(_cluster(entry), []).append(entry)
        if active_ideas:
            clusters["Quick Ideas"] = [
                {"kind": "idea",
                 "key": i.get("text","")[:38],
                 "value": "",
                 "confidence": i.get("confidence", 0.75)}
                for i in active_ideas[:5]
            ]

        st.markdown('<div class="mem-cluster-card">', unsafe_allow_html=True)
        if not clusters:
            st.markdown(
                '<div style="text-align:center;padding:32px;color:var(--muted);">'
                '&#x1F331; No identity data yet.<br>'
                '<span style="font-size:.82rem;">The brain learns as you interact.</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            for cname, entries in clusters.items():
                if not entries:
                    continue
                chips = ""
                for e in entries[:3]:
                    label = (e.get("key") or "").replace("_", " ").title()
                    em    = "&#x1F4A1;" if e.get("kind") == "idea" else _chip_emoji(e)
                    cls   = _chip_cls(e)
                    chips += (
                        f'<span class="mem-chip {cls}">'
                        f'{em} {label}{_conf(e)}</span>'
                    )
                st.markdown(
                    f'<div class="mem-cluster-group">'
                    f'<div class="mem-cluster-group-label">{cname}</div>'
                    f'<div class="mem-chips">{chips}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Summary + Quick Suggestions ─────────────────────────
        st.markdown('<div class="mem-divider" style="margin:16px 0;"></div>',
                    unsafe_allow_html=True)

        # --- Build summary sentence from top clusters ---
        top_pref = [p for p in prefs if p.get("kind") == "preference"]
        top_pat  = [p for p in prefs if p.get("kind") == "pattern"]

        # Derive 2-3 highlight phrases from real data
        highlights = []
        for p in (top_pref + top_pat)[:6]:
            v = (p.get("value") or p.get("key") or "").strip()
            if v:
                highlights.append(v[:60])

        if highlights:
            joined = " · ".join(highlights[:3])
            summary_html = (
                f'<div style="background:var(--chip-bg);border-radius:10px;'
                f'padding:12px 14px;margin-bottom:16px;border:1px solid var(--border-subtle);'
                f'font-size:.85rem;color:var(--text);line-height:1.6;">'
                f'<b>&#x1F4CB; Your Profile Summary</b><br>'
                f'<span style="color:var(--muted);">{joined}</span>'
                f'</div>'
            )
            st.markdown(summary_html, unsafe_allow_html=True)

        # --- Build 3 actionable suggestions + 1 improvement idea ---
        # Derived purely from the user's prefs / patterns — zero LLM
        SUGGESTION_RULES = [
            # (trigger_keywords_in_prefs, suggestion_text)
            (["food", "cuisine", "takeout", "indian"],
             "&#x1F37D; Try cooking one new Indian recipe this week using ingredients "
             "you already have at home. It cuts takeout costs and fits your food preference perfectly."),
            (["python", "ai", "tech", "code"],
             "&#x1F4BB; Block 45 min on a weekday morning for a focused AI or Python "
             "micro-project. Short daily sessions compound faster than weekend marathons."),
            (["fitness", "gym", "e6s", "volleyball", "sport"],
             "&#x1F3CB; Sync your fitness schedule to your Google Calendar so the COO "
             "can protect those slots from being overbooked automatically."),
            (["series", "movie", "hollywood", "hindi", "watch"],
             "&#x1F3AC; Queue up one new title that matches your taste this weekend "
             "and schedule a 2-hour watch window as a real calendar event."),
            (["music", "yousician", "guitar", "casio", "piano"],
             "&#x1F3B5; Pair your commute time with Yousician audio lessons — "
             "it turns dead drive time into practice time with zero extra scheduling."),
            (["beach", "outing", "temple", "outdoor", "weekend"],
             "&#x1F334; Plan your next family outing for a free Saturday morning "
             "using the Calendar tab — the COO will flag any conflicts automatically."),
            (["daughter", "kid", "judo", "chess", "class"],
             "&#x1F467; Review your daughter's class schedule this week and add "
             "prep-time buffers before each pickup in Google Calendar."),
            (["car", "kia", "sunpass", "drive"],
             "&#x1F697; Check that your SunPass is topped up if you have toll routes "
             "planned this week — quick 2-minute task that saves frustration."),
            (["schedule", "proactive", "planning"],
             "&#x1F4C5; Use the Home tab to ask the COO to plan your full week in one "
             "shot — say 'Plan my week' and it will suggest a structured schedule."),
        ]

        IMPROVEMENT_RULES = [
            (["food", "takeout", "diet"],
             "&#x1F331; Add your meal preferences in more detail — e.g., "
             "specific cuisines per day of week. The AI can then proactively "
             "suggest meal plans that prevent decision fatigue on busy evenings."),
            (["fitness", "gym", "sport", "volleyball"],
             "&#x1F331; Log your energy level after each workout session using "
             "'Train the Brain'. Over 2 weeks the AI will learn your peak-performance "
             "windows and schedule demanding tasks around them."),
            (["music", "yousician", "guitar"],
             "&#x1F331; Set a weekly practice goal in the Idea Inbox "
             "(e.g., '20 min Yousician daily'). The COO can then surface "
             "it as a recurring mission and track your streak."),
            (["python", "ai", "tech"],
             "&#x1F331; Share your current project or learning goal with the COO "
             "via the Home tab. It will break it into weekly milestones and schedule "
             "focus blocks automatically."),
            (["schedule", "planning", "proactive"],
             "&#x1F331; Enable a weekly Sunday review habit: ask the COO every Sunday "
             "evening to brief you on the upcoming week. Consistency trains the AI "
             "faster than sporadic use."),
        ]

        def _pref_text_blob():
            return " ".join(
                (p.get("key","") + " " + p.get("value","")).lower()
                for p in (top_pref + top_pat)
            )

        blob = _pref_text_blob()

        # Pick best-matching 3 suggestions
        matched_sugg = []
        for kws, sugg in SUGGESTION_RULES:
            if any(kw in blob for kw in kws):
                matched_sugg.append(sugg)
            if len(matched_sugg) >= 3:
                break
        # Pad with generic if needed
        while len(matched_sugg) < 3:
            matched_sugg.append(
                "&#x1F4DD; Ask the COO 'What should I focus on this week?' "
                "to get a personalised action plan based on your profile."
            )

        # Pick best-matching improvement
        matched_improve = ""
        for kws, imp in IMPROVEMENT_RULES:
            if any(kw in blob for kw in kws):
                matched_improve = imp
                break
        if not matched_improve:
            matched_improve = (
                "&#x1F331; The more you interact with the COO, the sharper its "
                "suggestions become. Try completing 3 missions this week and rating "
                "each one to accelerate the learning curve."
            )

        st.markdown(
            '<p class="mem-sec-hdr">&#x26A1; Quick Suggestions</p>',
            unsafe_allow_html=True,
        )

        for sugg in matched_sugg:
            st.markdown(
                f'<div style="margin-bottom:12px;padding:12px 14px;'
                f'background:var(--card-bg);border:1px solid var(--border-subtle);'
                f'border-radius:10px;border-left:3px solid #6366f1;'
                f'font-size:.85rem;color:var(--text);line-height:1.55;">'
                f'<span style="color:#6366f1;font-style:italic;font-weight:700;">'
                f'AI Suggestion:</span> {sugg}'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div style="margin-top:4px;padding:12px 14px;'
            f'background:var(--chip-bg);border:1px solid var(--border-subtle);'
            f'border-radius:10px;border-left:3px solid #10b981;'
            f'font-size:.85rem;color:var(--text);line-height:1.55;">'
            f'<span style="color:#10b981;font-style:italic;font-weight:700;">'
            f'&#x1F4A1; Improvement Idea:</span> {matched_improve}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════
    # RIGHT — Recently Learned + Idea Inbox
    # ════════════════════════════════════
    with right_col:

        # Recently Learned
        st.markdown('<p class="mem-sec-hdr">&#x1F50D; Recently Learned</p>',
                    unsafe_allow_html=True)
        st.markdown(
            '<p class="mem-sec-sub">Review the AI deductions to improve accuracy.</p>',
            unsafe_allow_html=True,
        )

        recent = list(reversed(rows[-20:]))

        if not recent:
            st.markdown(
                '<div class="mem-deduction-card" style="text-align:center;'
                'color:var(--muted);padding:28px;">'
                '&#x2728; No learnings yet.<br>'
                '<span style="font-size:.82rem;">Complete a mission to start '
                'building memory.</span></div>',
                unsafe_allow_html=True,
            )
        else:
            for idx, row in enumerate(recent[:5]):
                mission  = (row.get("mission") or row.get("key") or "Unknown").strip()
                feedback = (row.get("feedback") or "").strip()
                ts       = str(row.get("timestamp",""))[:16]
                rating   = row.get("rating","")
                r_icon   = "&#x1F44D;" if "👍" in str(rating) else (
                           "&#x1F44E;" if "👎" in str(rating) else "&#x2734;")

                deduction = mission[:120] + ("…" if len(mission) > 120 else "")
                fb_line   = (
                    f'<div class="mem-deduction-meta">{feedback[:80]}</div>'
                    if feedback else ""
                )
                ts_line   = (
                    f'<div class="mem-deduction-meta">&#x1F4C5; {ts} &nbsp;{r_icon}</div>'
                    if ts else ""
                )

                st.markdown(
                    f'<div class="mem-deduction-card">'
                    f'<div class="mem-deduction-text">'
                    f'&#x1F9E0; <b>Deduction:</b> {deduction}</div>'
                    f'{fb_line}{ts_line}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                cf_col, fg_col = st.columns(2)
                with cf_col:
                    if st.button(
                        "&#x2705; Confirm", key=f"mem_confirm_{idx}",
                        use_container_width=True
                    ):
                        st.toast("Confirmed — kept in memory.")
                with fg_col:
                    if st.button(
                        "&#x2716; Forget", key=f"mem_forget_{idx}",
                        use_container_width=True
                    ):
                        try:
                            from src.utils import _read_json, _write_json, MEMORY_FILE
                            all_r = _read_json(MEMORY_FILE)
                            all_r = [
                                r for r in all_r
                                if r.get("mission","") != row.get("mission","")
                            ]
                            _write_json(MEMORY_FILE, all_r)
                        except Exception:
                            pass
                        st.toast("Forgotten.")
                        st.rerun()

            if len(recent) > 5:
                with st.expander(f"See {len(recent)-5} more learnings"):
                    for row in recent[5:]:
                        m  = (row.get("mission") or "Unknown").strip()
                        ts = str(row.get("timestamp",""))[:16]
                        ri = "&#x1F44D;" if "👍" in str(row.get("rating","")) else "&#x1F44E;"
                        st.markdown(
                            f'<div class="mem-idea-item">'
                            f'<span class="mem-idea-text">{ri} {m[:72]}</span>'
                            f'<span class="mem-idea-ts">{ts}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

        # Quick Idea Inbox
        st.markdown('<div class="mem-divider" style="margin:16px 0;"></div>',
                    unsafe_allow_html=True)
        st.markdown('<p class="mem-sec-hdr">&#x1F4E5; Quick Idea Inbox</p>',
                    unsafe_allow_html=True)
        st.markdown(
            '<p class="mem-sec-sub">Drop an idea here…</p>',
            unsafe_allow_html=True,
        )

        new_idea = st.text_input(
            label="idea",
            placeholder="e.g. DIY wall decor ideas",
            key="mem_new_idea_input",
            label_visibility="collapsed",
        )
        if st.button(
            "&#x1F4BE; Save to Inbox", key="mem_save_idea",
            use_container_width=True, type="primary"
        ):
            text = (new_idea or "").strip()
            if not text:
                st.warning("Please type an idea first.")
            elif not email:
                st.warning("Sign in to save ideas.")
            else:
                try:
                    from src.utils import _safe_user_key, add_idea_to_inbox
                    add_idea_to_inbox(_safe_user_key(email), text)
                    st.toast(f"Saved: {text[:40]}")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Could not save: {ex}")

        if active_ideas:
            st.markdown(
                f'<div style="font-size:.8rem;font-weight:800;color:var(--muted);'
                f'margin:10px 0 8px;text-transform:uppercase;letter-spacing:.05em;">'
                f'{len(active_ideas)} ideas in inbox</div>',
                unsafe_allow_html=True,
            )
            for idea in active_ideas[:8]:
                ts_raw = idea.get("ts_utc","")[:10]
                text   = (idea.get("text") or "").strip()
                short  = text[:60] + ("…" if len(text) > 60 else "")
                st.markdown(
                    f'<div class="mem-idea-item">'
                    f'<span class="mem-idea-text">&#x1F4A1; {short}</span>'
                    f'<span class="mem-idea-ts">{ts_raw}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if len(active_ideas) > 8:
                st.caption(f"+{len(active_ideas)-8} more. Ask the COO to show all.")

    # ── PRO TIPS ──────────────────────────────────────────────────
    st.markdown('<div class="mem-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="mem-sec-hdr" style="font-size:1.08rem;">'
        '&#x1F4A1; Pro Tips — Getting the Most from Memory</p>',
        unsafe_allow_html=True,
    )

    TIPS = [
        ("&#x1F331; Feed the Brain",
         "The more missions you complete and rate, the sharper the AI gets. "
         "After any plan, tap Confirm or give feedback to log a result."),
        ("&#x2716; Forget Errors Fast",
         "If the AI learned something wrong, hit Forget immediately. "
         "Early corrections prevent bad patterns from compounding over time."),
        ("&#x1F4A1; Idea Inbox = Brain Dump",
         "Don't overthink it — drop any passing thought here. "
         "The AI will surface relevant ideas when the right moment arrives."),
        ("&#x1F501; Patterns Beat One-Offs",
         "Tell the AI about recurring routines (volleyball Mondays, "
         "Indian food Fridays). It uses patterns far more than single events."),
        ("&#x1F3AF; Name Things Precisely",
         "Saying 'Judo on Tue/Thu at 5:30' is 10x more useful than "
         "'daughter class'. Specifics produce far better suggestions."),
        ("&#x1F9EC; Review Clusters Weekly",
         "Scan Identity Clusters every Sunday. Remove anything stale or wrong. "
         "Fresh data keeps the AI contextually accurate."),
    ]

    tip_cols = st.columns(3)
    for idx, (title, body) in enumerate(TIPS):
        with tip_cols[idx % 3]:
            st.markdown(
                f'<div class="mem-tip-card">'
                f'<div style="font-weight:800;font-size:.88rem;color:var(--text);'
                f'margin-bottom:6px;">{title}</div>'
                f'<div style="font-size:.82rem;color:var(--muted);line-height:1.5;">'
                f'{body}</div></div>',
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────
# SETTINGS PAGE  (placeholder — future)
# ─────────────────────────────────────────────────────────────
def _render_settings(user_email="", user_name="", **_):
    import streamlit as st
    from src.flow import begin_reconnect, complete_reconnect, clear_reconnect
    from src.gcal import get_calendar_service, start_device_flow

    st.markdown("### ⚙️ Settings")

    # ── 1. ACCOUNT ──────────────────────────────────────────────
    with st.expander("👤 Account", expanded=True):
        email = user_email or st.session_state.get("user_email", "")
        st.markdown(f"**Signed in as:** `{email}`")
        loc = st.text_input(
            "📍 Default Location",
            value=st.session_state.get("user_location", "Tampa, FL"),
            key="settings_location",
            placeholder="e.g. Tampa, FL",
        )
        if st.button("Save Location", key="settings_save_location"):
            st.session_state["user_location"] = loc.strip()
            st.success("✅ Location saved.")

    # ── 2. GOOGLE CALENDAR ──────────────────────────────────────
    with st.expander("🗓️ Google Calendar", expanded=True):
        email = st.session_state.get("user_email", "")
        svc = None
        try:
            svc = get_calendar_service(user_id=email)
        except Exception:
            pass

        if svc:
            st.success("✅ Google Calendar is **connected**.")
            events_ok = st.session_state.get("calendar_online", False)
            count = len(st.session_state.get("calendar_events") or [])
            st.caption(f"{count} events loaded  •  Status: {'🟢 Online' if events_ok else '🟡 Checking…'}")
            if st.button("🔌 Disconnect Calendar", key="settings_disconnect"):
                # Wipe token
                try:
                    import re, os, json
                    safe = re.sub(r"[^a-zA-Z0-9_]", "_", email.lower())
                    p = os.path.join("memory", "users", safe, "gcal_token.json")
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
                try:
                    from src.token_store import supabase_upsert_token
                    supabase_upsert_token(st, user_id=email, token_json=None, provider="google_calendar")
                except Exception:
                    pass
                st.session_state["calendar_online"] = False
                st.session_state["calendar_events"] = None
                st.rerun()
        else:
            st.info("Connect your Google Calendar to see events and schedule tasks.")

            flow = st.session_state.get("device_flow")

            if not flow:
                if st.button("🔗 Connect Google Calendar", key="settings_cal_connect", type="primary"):
                    with st.spinner("Starting Google auth…"):
                        result = start_device_flow()
                    if result.get("error"):
                        st.error(f"Could not start auth: {result['error']}")
                    else:
                        st.session_state["device_flow"] = result
                        st.rerun()
            else:
                vc  = flow.get("user_code", "")
                url = flow.get("verification_url") or flow.get("verification_uri", "https://google.com/device")
                exp = flow.get("expires_in", 1800)

                st.markdown(
                    f"""
                    **Step 1 —** Open **[{url}]({url})** on any device  
                    **Step 2 —** Sign in with your Google account  
                    **Step 3 —** Enter this code:
                    """,
                    unsafe_allow_html=False,
                )
                st.code(vc, language=None)
                st.caption(f"Code expires in {exp // 60} minutes. Press **Done** after entering it.")

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("&#x2705; Done &#x2014; I entered the code", key="settings_cal_done", type="primary", use_container_width=True):
                        # Auto-retry up to 6 times (~30 s) so user doesn't have to click repeatedly
                        _spinner_slot = st.empty()
                        _status_slot  = st.empty()
                        _connected    = False
                        _last_msg     = ""
                        import time as _time
                        for _attempt in range(6):
                            _spinner_slot.info(f"&#x1F504; Checking with Google… (attempt {_attempt + 1}/6)")
                            _ok, _msg = complete_reconnect()
                            _last_msg = _msg
                            if _ok:
                                _connected = True
                                break
                            if "authorization_pending" in _msg or "slow_down" in _msg:
                                _time.sleep(4)   # wait before next poll
                                continue
                            # Any other error (expired, access_denied, etc.) — stop immediately
                            break
                        _spinner_slot.empty()
                        if _connected:
                            st.session_state["device_flow"] = None
                            _status_slot.success("&#x2705; Calendar connected! Loading events…")
                            _time.sleep(1)
                            st.rerun()
                        elif "authorization_pending" in _last_msg or "slow_down" in _last_msg:
                            _status_slot.warning(
                                "Google hasn't confirmed the code yet. "
                                "Make sure you entered the code at the link above, then click Done again."
                            )
                        elif "access_denied" in _last_msg:
                            _status_slot.error(
                                "&#x274C; Access was denied. "
                                "Please click **Connect Google Calendar** again and approve all permissions."
                            )
                            st.session_state["device_flow"] = None
                        else:
                            _status_slot.error(f"&#x274C; Auth failed: {_last_msg}")
                with col2:
                    if st.button("&#x2716; Cancel", key="settings_cal_cancel", use_container_width=True):
                        st.session_state["device_flow"] = None
                        st.rerun()

    # ── 3. TIMEZONE ─────────────────────────────────────────────
    with st.expander("🕐 Timezone", expanded=False):
        detected = st.session_state.get("user_tz", "")
        if detected:
            st.success(f"✅ Auto-detected: **{detected}**")
        else:
            st.info("Timezone is auto-detected from your browser on first load.")
        manual = st.text_input(
            "Override timezone (optional)",
            value=detected,
            key="settings_tz",
            placeholder="e.g. America/New_York",
        )
        if st.button("Apply Timezone", key="settings_save_tz"):
            if manual.strip():
                st.session_state["user_tz"] = manual.strip()
                try:
                    from src.gcal import set_display_tz
                    set_display_tz(manual.strip())
                except Exception:
                    pass
                st.success(f"✅ Timezone set to {manual.strip()}")
                st.session_state["calendar_events"] = None  # force refresh

    # ── 4. ABOUT ────────────────────────────────────────────────
    with st.expander("ℹ️ About", expanded=False):
        st.markdown("""
        **Family COO** — AI Operations Center  
        Powered by Claude (Anthropic) + Google Calendar  
        """)
