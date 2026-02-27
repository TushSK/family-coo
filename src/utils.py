# src/utils.py
import json
import os
import uuid
import datetime as dt
import re
from typing import Any, Dict, List, Optional
from dateutil import parser as dtparser

MEMORY_FILE = "memory/feedback_log.json"
MISSION_FILE = "memory/mission_log.json"


# --- NEW: per-user memory folder (Layer B) ---
USER_MEMORY_DIR = "memory/users"

def _safe_user_key(user_id: str) -> str:
    """
    Convert user_id (email) into a safe filename.
    Example: 'a.b+c@gmail.com' -> 'a_b_c_gmail_com'
    """
    s = (user_id or "").strip().lower()
    if not s:
        return "unknown_user"
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "unknown_user"

def safe_email_from_user(user_id: str) -> str:
    """
    Public helper: convert email/user_id into a safe filename key.
    This is a stable wrapper around _safe_user_key.
    """
    return _safe_user_key(user_id)

def _user_memory_path(user_id: str) -> str:
    init_files()
    if not os.path.exists(USER_MEMORY_DIR):
        os.makedirs(USER_MEMORY_DIR, exist_ok=True)
    fname = _safe_user_key(user_id) + ".json"
    return os.path.join(USER_MEMORY_DIR, fname)

def load_user_memory(user_id: str, limit: int = 20) -> List[dict]:
    """
    Long-term memory (Layer B) per user.
    Returns newest `limit` items.
    """
    path = _user_memory_path(user_id)
    rows = _read_json(path)
    return rows[-limit:] if limit and limit > 0 else rows

def append_user_memory_entry(user_id: str, entry: Dict[str, Any], max_items: int = 2000) -> bool:
    """
    Append entry with simple dedupe.
    Dedupe key: (kind, key, value) if present.
    """
    try:
        if not user_id:
            return False

        path = _user_memory_path(user_id)
        rows = _read_json(path)

        if not isinstance(entry, dict):
            return False

        kind = str(entry.get("kind") or "").strip().lower()
        key = str(entry.get("key") or "").strip().lower()
        value = str(entry.get("value") or "").strip()

        # Dedupe only if structured fields exist
        if kind and key and value:
            for r in reversed(rows[-200:]):  # small window is enough
                if not isinstance(r, dict):
                    continue
                if (
                    str(r.get("kind") or "").strip().lower() == kind
                    and str(r.get("key") or "").strip().lower() == key
                    and str(r.get("value") or "").strip() == value
                ):
                    return False  # already stored

        # Stamp
        entry.setdefault("ts_utc", _now_utc().isoformat())
        entry.setdefault("source", "brain")

        rows.append(entry)

        # Cap file size
        if max_items and len(rows) > max_items:
            rows = rows[-max_items:]

        _write_json(path, rows)
        return True
    except Exception:
        return False

def parse_memory_tags(pre_prep: str) -> List[dict]:
    """
    Extract [[MEMORY:{...json...}]] blocks from pre_prep.
    Returns list of dict payloads.
    """
    out = []
    s = str(pre_prep or "")
    if not s:
        return out

    # non-greedy json capture
    matches = re.findall(r"\[\[MEMORY:(\{.*?\})\]\]", s, flags=re.DOTALL)
    for m in matches[:3]:  # hard cap
        try:
            payload = json.loads(m)
            if isinstance(payload, dict):
                out.append(payload)
        except Exception:
            continue
    return out

def get_memory_summary_from_memory(memory_list, n=12):
    """
    Latest-wins dedupe by key.
    Returns list of {kind,key,value,confidence,ts_utc} (small + prompt-friendly).
    No file I/O.
    """
    memory_list = memory_list or []
    # sort newest first if ts_utc exists
    def _ts(m): 
        return m.get("ts_utc") or ""
    items = sorted(memory_list, key=_ts, reverse=True)

    seen = set()
    out = []
    for m in items:
        key = (m.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({
            "kind": m.get("kind",""),
            "key": key,
            "value": m.get("value",""),
            "confidence": m.get("confidence", 0.0),
            "ts_utc": m.get("ts_utc","")
        })
        if len(out) >= n:
            break
    return out

# -----------------------
# FILE BOOTSTRAP
# -----------------------
def init_files():
    """Ensures memory files exist."""
    if not os.path.exists("memory"):
        os.makedirs("memory", exist_ok=True)
    for fpath in [MEMORY_FILE, MISSION_FILE]:
        if not os.path.exists(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump([], f)


def _read_json(path: str) -> list:
    init_files()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_json(path: str, data: list) -> None:
    init_files()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


# -----------------------
# DATETIME HELPERS
# -----------------------
def _now_utc() -> dt.datetime:
    """Timezone-aware current UTC time."""
    return dt.datetime.now(dt.timezone.utc)


def _parse_dt(value: Optional[str]) -> Optional[dt.datetime]:
    """
    Parse common Google Calendar formats into timezone-aware datetime (UTC).
    Supports:
      - "2026-02-15T12:30:00-05:00"
      - "2026-02-15T17:30:00Z"
      - "2026-02-15" (all-day)
    """
    if not value:
        return None
    try:
        s = str(value).strip()

        # ISO datetime
        if "T" in s:
            v = s.replace("Z", "+00:00")
            dtx = dt.datetime.fromisoformat(v)
            if dtx.tzinfo is None:
                dtx = dtx.replace(tzinfo=dt.timezone.utc)
            return dtx.astimezone(dt.timezone.utc)

        # All-day date: treat as end-of-day UTC
        d = dt.datetime.strptime(s, "%Y-%m-%d").date()
        return dt.datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=dt.timezone.utc)
    except Exception:
        # Best-effort fallback with dateutil
        try:
            now_local = dt.datetime.now().astimezone()
            dtx = dtparser.parse(str(value), fuzzy=True, default=now_local.replace(minute=0, second=0, microsecond=0))
            if dtx.tzinfo is None:
                dtx = dtx.replace(tzinfo=now_local.tzinfo)
            return dtx.astimezone(dt.timezone.utc)
        except Exception:
            return None


# -----------------------
# MEMORY (BRAIN LEARNINGS)
# -----------------------
def load_memory(limit=10):
    """Loads actionable learnings for the Brain."""
    data = _read_json(MEMORY_FILE)
    return data[-limit:]


def load_feedback_rows() -> List[dict]:
    """
    Expected by flow.py.
    Returns all feedback rows (oldest -> newest).
    """
    return _read_json(MEMORY_FILE)


def save_manual_feedback(topic, feedback, rating, user_id=None):
    entry = {
        "timestamp": "Manual",
        "mission": topic,
        "feedback": feedback,
        "rating": rating,
    }
    if user_id:
        entry["user_id"] = str(user_id).strip().lower()

    d = _read_json(MEMORY_FILE)
    d.append(entry)
    _write_json(MEMORY_FILE, d)

# -----------------------
# MISSIONS (FOLLOW-UP / MISSED EVENTS)
# -----------------------
def log_mission_start(event_data):
    """Logs a mission so we can check on it later."""
    init_files()

    source_id = event_data.get("source_id") or event_data.get("id")
    title = event_data.get("title") or event_data.get("summary") or "Event"

    # Prefer end_time; fall back to end_raw (gcal events)
    end_time_raw = event_data.get("end_time") or event_data.get("end_raw")

    # Normalize end_time to timezone-aware ISO (UTC)
    end_dt = _parse_dt(end_time_raw) if end_time_raw else None
    end_time = end_dt.isoformat() if end_dt else end_time_raw

    new_mission = {
        "id": str(uuid.uuid4())[:8],
        "source_id": source_id,
        "title": title,
        "end_time": end_time,
        "status": "pending",
        "snoozed_until": None,
    }

    missions = _read_json(MISSION_FILE)
    missions.append(new_mission)
    _write_json(MISSION_FILE, missions)

    return new_mission


def upsert_calendar_missions(events: List[Dict[str, Any]]) -> None:
    """
    Expected by flow.py.
    Ensures calendar events are tracked as 'missions' for later feedback/missed checks.

    events format (from gcal.py / flow.py):
      - id
      - title / summary
      - end_raw (preferred) or end_time
    """
    if not events:
        return

    missions = _read_json(MISSION_FILE)
    existing_source_ids = {m.get("source_id") for m in missions if m.get("source_id")}

    changed = False
    for ev in events:
        source_id = ev.get("id") or ev.get("source_id")
        if not source_id or source_id in existing_source_ids:
            continue

        end_raw = ev.get("end_raw") or ev.get("end_time")
        end_dt = _parse_dt(end_raw)
        if not end_dt:
            continue

        missions.append(
            {
                "id": str(uuid.uuid4())[:8],
                "source_id": source_id,
                "title": ev.get("title") or ev.get("summary") or "Event",
                "end_time": end_dt.isoformat(),
                "status": "pending",
                "snoozed_until": None,
            }
        )
        existing_source_ids.add(source_id)
        changed = True

    if changed:
        _write_json(MISSION_FILE, missions)


def get_pending_review():
    """
    Picks ONE missed (pending + past end_time + not snoozed) mission to ask about.
    Returns mission dict or None.
    """
    missions = _read_json(MISSION_FILE)
    now = _now_utc()

    candidates = []
    for m in missions:
        if m.get("status") != "pending":
            continue

        end_dt = _parse_dt(m.get("end_time"))
        if not end_dt or end_dt >= now:
            continue

        snooze_dt = _parse_dt(m.get("snoozed_until"))
        if snooze_dt and snooze_dt >= now:
            continue

        candidates.append((end_dt, m))

    if not candidates:
        return None

    # Most recent missed first
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def get_missed_count() -> int:
    """
    Expected by flow.py.
    Counts how many missions are pending AND their end_time is in the past AND not snoozed.
    """
    missions = _read_json(MISSION_FILE)
    now = _now_utc()
    missed = 0

    for m in missions:
        if m.get("status") != "pending":
            continue

        end_dt = _parse_dt(m.get("end_time"))
        if not end_dt or end_dt >= now:
            continue

        snooze_dt = _parse_dt(m.get("snoozed_until"))
        if snooze_dt and snooze_dt >= now:
            continue

        missed += 1

    return missed


def snooze_mission(mission_id, hours=4):
    """Snoozes a mission so it doesn't annoy the user."""
    missions = _read_json(MISSION_FILE)

    # Always store snooze_until as UTC ISO (timezone-aware)
    wake_time = (_now_utc() + dt.timedelta(hours=hours)).isoformat()

    for m in missions:
        if m.get("id") == mission_id:
            m["snoozed_until"] = wake_time
            break

    _write_json(MISSION_FILE, missions)


def complete_mission_review(mission_id, was_completed, reason, user_id=None):
    """Saves the feedback and closes the mission."""
    missions = _read_json(MISSION_FILE)
    mission_title = "Unknown Mission"

    for m in missions:
        if m.get("id") == mission_id:
            m["status"] = "reviewed"
            mission_title = m.get("title", mission_title)
            break

    _write_json(MISSION_FILE, missions)

    learning_entry = {
        "timestamp": _now_utc().astimezone().strftime("%Y-%m-%d"),
        "mission": mission_title,
        "feedback": f"User {'completed' if was_completed else 'skipped'} this. Reason: {reason}",
        "rating": "👍" if was_completed else "👎",
    }
    if user_id:
        learning_entry["user_id"]=str(user_id).strip().lower()

    memories = _read_json(MEMORY_FILE)
    memories.append(learning_entry)
    _write_json(MEMORY_FILE, memories)


# ------------------------------------------------------------
# Reliability KPI
# ------------------------------------------------------------
def calculate_reliability_score(memory_path=None) -> int:
    """
    Reliability score (0-100), simple + explainable:
    - Read memory/log rows
    - Count mission/check-in feedback items
    - Reliability = % of non-failed items

    If there is no history yet, return 100.
    """
    try:
        mem = load_memory(memory_path) if memory_path else load_memory()
    except Exception:
        return 100

    rows = []
    if isinstance(mem, dict):
        for k in ("memory", "rows", "items", "events", "log"):
            v = mem.get(k)
            if isinstance(v, list):
                rows = v
                break
    elif isinstance(mem, list):
        rows = mem

    if not rows:
        return 100

    total = 0
    failed = 0

    for r in rows:
        if not isinstance(r, dict):
            continue

        # Only consider explicit feedback-like rows to avoid noise
        is_feedback = any(k in r for k in (
            "mission_id", "mission", "checkin", "review", "completed", "result", "status", "rating"
        ))
        if not is_feedback:
            continue

        total += 1

        if r.get("completed") is False:
            failed += 1
            continue

        status = str(r.get("status") or r.get("result") or r.get("answer") or "").strip().lower()
        if status in {"failed", "missed", "no", "not_done", "not done"}:
            failed += 1
            continue

        rating = str(r.get("rating") or "").strip().lower()
        if rating in {"👎", "no", "failed", "missed"}:
            failed += 1
            continue

    if total <= 0:
        return 100

    score = round(((total - failed) / total) * 100)
    return int(max(0, min(100, score)))

# -----------------------------#
    # Idea planner
# -----------------------------#

import os, json, hashlib
from datetime import datetime, timezone

def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _ideas_path_for_user(safe_email: str) -> str:
    return os.path.join("memory", "users", f"{safe_email}_ideas.json")

def load_user_ideas(safe_email: str) -> list:
    path = _ideas_path_for_user(safe_email)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_user_ideas(safe_email: str, ideas: list) -> None:
    path = _ideas_path_for_user(safe_email)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ideas, f, ensure_ascii=False, indent=2)


# ###############################################
# Add ideas to the inbox
# ###############################################
def add_idea_to_inbox(
    safe_email: str,
    text: str,
    tags: list | None = None,
    source: str = "manual_inbox",
    confidence: float = 0.75,
) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Idea text is empty")

    norm = " ".join(text.lower().split())
    idea_id = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]

    ideas = load_user_ideas(safe_email)

    # Dedup: if same id exists, just refresh timestamp + keep active
    for it in ideas:
        if it.get("id") == idea_id:
            it["ts_utc"] = _utc_now_iso()
            it["status"] = it.get("status") or "active"
            return it

    item = {
        "id": idea_id,
        "text": text,
        "tags": tags or [],
        "status": "active",
        "confidence": float(confidence),
        "source": source,
        "ts_utc": _utc_now_iso(),
    }
    ideas.insert(0, item)  # newest first
    save_user_ideas(safe_email, ideas)
    return item

def get_ideas_summary(safe_email: str, n: int = 10) -> list:
    ideas = load_user_ideas(safe_email)
    # newest first, active only
    active = [i for i in ideas if (i.get("status") or "active") == "active"]
    return active[:max(1, int(n))]

# ###############################################
# Improvement 1: Contextual Matching (Very Powerful)
# ###############################################
import re

def select_relevant_ideas(ideas: list, user_request: str, n: int = 6) -> list:
    """
    Lightweight lexical matcher (safe + deterministic).
    Returns top-n ideas sorted by score (desc).
    Does not mutate stored ideas.
    """
    t = " ".join((user_request or "").lower().split())

    # Extract simple intent signals
    wants_short = bool(re.search(r"\b(short|quick|brief|1-2 hours|couple hours)\b", t))
    wants_outdoor = bool(re.search(r"\b(outdoor|outside|park|trail|beach|river|lake|kayak|kayaking|walk)\b", t))
    wants_indoor = bool(re.search(r"\b(indoor|inside|museum|mall|movie|bowling|aquarium)\b", t))
    mentions_sun = bool(re.search(r"\b(sunday|sun)\b", t))
    mentions_sat = bool(re.search(r"\b(saturday|sat)\b", t))
    mentions_afternoon = bool(re.search(r"\b(afternoon|2pm|3pm|4pm)\b", t))
    mentions_morning = bool(re.search(r"\b(morning|8am|9am|10am|breakfast)\b", t))

    # Keywords from request for overlap scoring
    req_tokens = set([w for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 3])

    def score_item(it: dict) -> float:
        text = " ".join(((it.get("text") or "") + " " + " ".join(it.get("tags") or [])).lower().split())
        tokens = set([w for w in re.findall(r"[a-z0-9]+", text) if len(w) >= 3])

        overlap = len(req_tokens.intersection(tokens))
        s = overlap * 2.0

        # Light boosts
        if wants_outdoor and any(k in text for k in ["park", "trail", "beach", "river", "lake", "kayak", "kayaking", "outdoor"]):
            s += 2.0
        if wants_indoor and any(k in text for k in ["museum", "aquarium", "mall", "movie", "indoor"]):
            s += 2.0
        if wants_short and any(k in text for k in ["quick", "short", "nearby", "close"]):
            s += 1.0

        # Time-of-day hints (very light; we don’t store durations yet)
        if mentions_morning and "breakfast" in text:
            s += 1.0
        if mentions_afternoon and any(k in text for k in ["stroll", "walk", "visit", "outing"]):
            s += 0.5

        # If user explicitly says indoor, penalize strongly-outdoor activities
        if wants_indoor and any(k in text for k in ["kayak", "kayaking", "beach", "trail"]):
            s -= 2.0

        # Small bump for “active” and confidence (if present)
        conf = float(it.get("confidence") or 0.0)
        s += min(conf, 1.0) * 0.25

        return s

    scored = []
    for it in ideas or []:
        try:
            if (it.get("status") or "active") != "active":
                continue
            scored.append((score_item(it), it))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [it for s, it in scored if s > 0][:max(1, int(n))]

    # Fallback: if nothing scored, just return newest active
    if not top:
        active = [i for i in ideas or [] if (i.get("status") or "active") == "active"]
        return active[:max(1, int(n))]

    return top