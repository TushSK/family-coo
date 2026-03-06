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
def _render_calendar(calendar_events=None, **_):
    import streamlit as st
    st.markdown("### 🗓️ Calendar View")
    st.info("Full calendar view coming soon. Your events are managed via Google Calendar.")
    events = calendar_events or []
    if events:
        for ev in events[:20]:
            start = str(ev.get("start_raw") or ev.get("start_time") or "")[:16].replace("T", " ")
            title = ev.get("title") or "Event"
            loc   = ev.get("location") or ""
            st.markdown(
                f"<div style='padding:8px 12px;margin-bottom:6px;background:#f8fafc;"
                f"border-radius:8px;border:1px solid #e2e8f0;'>"
                f"<b>{start}</b> — {title}"
                f"{'  📍 ' + loc if loc else ''}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown("No events loaded. Connect your Google Calendar in Settings.")


# ─────────────────────────────────────────────────────────────
# MEMORY BANK PAGE  (placeholder — future)
# ─────────────────────────────────────────────────────────────
def _render_memory(memory_rows=None, **_):
    import streamlit as st
    st.markdown("### 🧠 Memory Bank")
    rows = memory_rows or []
    if rows:
        st.markdown(f"**{len(rows)} learnings stored.**")
        for r in reversed(rows[-30:]):
            ts      = r.get("timestamp", "")[:10]
            mission = r.get("mission","") or r.get("key","") or r.get("topic","")
            fb      = r.get("feedback","") or r.get("value","")
            rating  = r.get("rating","")
            st.markdown(
                f"<div style='padding:8px 12px;margin-bottom:5px;background:#f8fafc;"
                f"border-radius:8px;border:1px solid #e2e8f0;font-size:0.83rem;'>"
                f"<b>{rating} {mission}</b><br>"
                f"<span style='color:#64748b;'>{fb}</span>"
                + (f"  <span style='color:#94a3b8;font-size:0.75rem;'>{ts}</span>" if ts else "")
                + "</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No memories yet. The brain learns as you use the COO.")


# ─────────────────────────────────────────────────────────────
# SETTINGS PAGE  (placeholder — future)
# ─────────────────────────────────────────────────────────────
def _render_settings(**_):
    import streamlit as st
    st.markdown("### ⚙️ Settings")
    st.info("Settings panel coming soon.")
    st.markdown("""
    **Planned settings:**
    - Default location & timezone
    - Notification preferences
    - Calendar sync options
    - PIN / account management
    - Brain training preferences
    """)
