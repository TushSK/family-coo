# backend/main.py
"""
Family COO — FastAPI Backend
=============================
Wraps the existing brain.py / gcal.py logic into clean REST endpoints.
brain.py, flow.py, prompts.py, llm_router.py are NEVER modified.

Endpoints:
  POST  /api/chat          — AI conversation (brain.py)
  GET   /api/calendar      — upcoming Google Calendar events
  POST  /api/calendar/add  — add event to Google Calendar
  GET   /api/missions      — pending/reviewed missions (Supabase)
  POST  /api/missions/{id}/complete  — mark mission reviewed
  POST  /api/missions/{id}/snooze    — snooze mission
  GET   /api/memory        — user memory blob (Supabase)
  GET   /api/insights      — KPIs + pattern insights (zero LLM)
  POST  /api/feedback      — save feedback entry (Supabase)
  GET   /api/health        — liveness check

Run locally:
  uvicorn backend.main:app --reload --port 8000
  -> Swagger UI: http://localhost:8000/docs
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone as _tz_utc, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import base64, hashlib, hmac, smtplib, urllib.parse, urllib.request as _urlreq
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ── Timezone helper ────────────────────────────────────────────────────────────
# Tampa, FL is in America/New_York (ET).
# Standard offset: EST = UTC-5, EDT = UTC-4 (DST Mar–Nov).
# The LLM generates naive ISO strings like "2025-03-17T17:30:00".
# PostgreSQL (Supabase) timestamps WITHOUT offset are treated as UTC — so a naive
# 5:30 PM string lands in the DB as 5:30 PM UTC = 1:30 PM ET → shown OVERDUE too early.
# This function converts any naive or tz-aware ISO string → UTC ISO with Z suffix
# so every end_time stored in mission_log is unambiguous UTC.
def _to_utc_iso(time_str: str) -> str:
    """
    Normalise an event time string to UTC ISO-8601 (with Z suffix).

    Rules:
    - If the string already carries a UTC offset (±HH:MM or Z) → convert to UTC.
    - If the string is naive (no offset) → assume America/New_York (ET) and convert.
    - EDT (Mar 2nd Sun – Nov 1st Sun) = UTC-4; EST = UTC-5. We auto-detect DST.
    - Falls back to returning the original string unchanged on any parse error.
    """
    if not time_str:
        return time_str
    try:
        # Try dateutil for robust parsing (handles many formats)
        try:
            from dateutil import parser as _dtparser
            dt = _dtparser.parse(time_str)
        except Exception:
            # stdlib fallback for bare ISO format
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return time_str  # cannot parse at all

        if dt.tzinfo is None:
            # Naive → assume America/New_York (ET)
            try:
                from zoneinfo import ZoneInfo
                et_tz = ZoneInfo("America/New_York")
                dt = dt.replace(tzinfo=et_tz)
            except Exception:
                # zoneinfo not available (Python < 3.9) → manual DST offset
                # DST: 2nd Sunday March 02:00 → 1st Sunday November 02:00
                year = dt.year
                # 2nd Sunday in March
                mar1 = datetime(year, 3, 1)
                dst_start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)
                # 1st Sunday in November
                nov1 = datetime(year, 11, 1)
                dst_end = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)
                is_dst = dst_start <= dt.replace(tzinfo=None) < dst_end
                offset = timedelta(hours=-4 if is_dst else -5)
                dt = dt.replace(tzinfo=_tz_utc.utc) - offset  # convert to UTC manually
                # dt is now in UTC — return directly
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Convert to UTC
        dt_utc = dt.astimezone(_tz_utc.utc)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return time_str  # safe fallback — return unchanged

# -- locate project root & load secrets ---------------------------------------
PROJECT_ROOT  = Path(__file__).resolve().parent.parent
SECRETS_PATH  = PROJECT_ROOT / ".streamlit" / "secrets.toml"
sys.path.insert(0, str(PROJECT_ROOT))


def _load_secrets() -> dict:
    """Local dev only — on Render, env vars take priority."""
    try:
        if SECRETS_PATH.exists():
            with SECRETS_PATH.open("rb") as f:
                return tomllib.load(f)
    except Exception:
        pass
    return {}


_SECRETS = _load_secrets()
_SB      = _SECRETS.get("supabase", {})
_KEYS    = _SECRETS.get("keys", {})
_GENERAL = _SECRETS.get("general", {})
_GOAUTH  = _SECRETS.get("google_oauth", {})


def _secret(env_key: str, *toml_keys: str, section: dict = {}) -> str:
    """Env var first, secrets.toml fallback for local dev."""
    val = os.getenv(env_key, "")
    if val:
        return val
    for k in toml_keys:
        val = section.get(k, "")
        if val:
            return val
    return ""


SUPABASE_URL         = _secret("SUPABASE_URL",         "url",               section=_SB).rstrip("/")
SUPABASE_SERVICE_KEY = _secret("SUPABASE_SERVICE_KEY", "service_role_key",  section=_SB)
ANTHROPIC_KEY        = _secret("ANTHROPIC_API_KEY",    "ANTHROPIC_API_KEY", section=_KEYS)
GROQ_KEY             = _secret("GROQ_API_KEY",         "GROQ_API_KEY",      section=_KEYS) or _GENERAL.get("groq_api_key", "")
GCAL_CLIENT_ID       = _secret("GOOGLE_CLIENT_ID",     "client_id",         section=_GOAUTH)
GCAL_CLIENT_SECRET   = _secret("GOOGLE_CLIENT_SECRET", "client_secret",     section=_GOAUTH)

# Separate credentials for waitlist OAuth (Web application type client)
# Falls back to GCAL credentials if not set — allows gradual migration
WAITLIST_CLIENT_ID     = os.environ.get("WAITLIST_GOOGLE_CLIENT_ID")     or GCAL_CLIENT_ID
WAITLIST_CLIENT_SECRET = os.environ.get("WAITLIST_GOOGLE_CLIENT_SECRET") or GCAL_CLIENT_SECRET

# -- Supabase client (singleton) ----------------------------------------------
from supabase import create_client, Client as SupabaseClient

_sb_client: Optional[SupabaseClient] = None


def get_db() -> SupabaseClient:
    global _sb_client
    if _sb_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise HTTPException(500, "Supabase not configured")
        _sb_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _sb_client


# -- Google Calendar helper ---------------------------------------------------
def _get_gcal_service(user_id: str):
    """
    Returns a Google Calendar service or None.

    Token resolution order (most-to-least preferred):
      1. Supabase user_tokens table  (primary — works on any device/deploy)
      2. gcal_token.json             (local dev fallback — never used on Render)
      3. None → caller gets empty calendar, never raises

    On every successful load, if the access token is expired the function
    auto-refreshes it via the refresh_token and writes the new token back to
    whichever store it came from, so the next call is instant.
    """
    import urllib.parse, urllib.request as urlreq
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GRequest
    from googleapiclient.discovery import build

    google_cfg    = _SECRETS.get("google_oauth", {})
    client_id     = os.environ.get("GOOGLE_CLIENT_ID")     or google_cfg.get("client_id",     "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or google_cfg.get("client_secret", "")

    token_data: Optional[dict] = None
    token_source: str = "none"

    # ── 1. Try Supabase ───────────────────────────────────────────────────────
    try:
        q_user     = urllib.parse.quote(user_id)
        q_provider = urllib.parse.quote("google_calendar")
        url = (
            f"{SUPABASE_URL}/rest/v1/user_tokens"
            f"?user_id=eq.{q_user}&provider=eq.{q_provider}&select=token_json"
        )
        req = urlreq.Request(url, headers={
            "apikey":        SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        })
        with urlreq.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read().decode())
        if rows:
            td = rows[0].get("token_json") or {}
            if isinstance(td, str):
                td = json.loads(td)
            if td.get("refresh_token"):          # only use if it has a refresh_token
                token_data   = td
                token_source = "supabase"
    except Exception:
        pass  # Supabase unreachable → fall through to local

    # ── 2. Local fallback (gcal_token.json) ───────────────────────────────────
    if not token_data:
        for path in ["gcal_token.json", "token.json"]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as _f:
                        td = json.load(_f)
                    if td.get("refresh_token"):
                        token_data   = td
                        token_source = f"local:{path}"
                        break
                except Exception:
                    pass

    if not token_data:
        return None  # no token anywhere

    try:
        creds = Credentials(
            token         = token_data.get("token"),
            refresh_token = token_data.get("refresh_token"),
            token_uri     = "https://oauth2.googleapis.com/token",
            client_id     = client_id     or token_data.get("client_id",     ""),
            client_secret = client_secret or token_data.get("client_secret", ""),
        )

        # Refresh if expired (access tokens last ~1 hour; refresh_token is long-lived)
        if not creds.valid and creds.refresh_token:
            try:
                creds.refresh(GRequest())
                refreshed = json.loads(creds.to_json())

                # Write refreshed token back to whichever store we used
                if token_source == "supabase":
                    try:
                        q_user     = urllib.parse.quote(user_id)
                        q_provider = urllib.parse.quote("google_calendar")
                        patch_url  = (f"{SUPABASE_URL}/rest/v1/user_tokens"
                                      f"?user_id=eq.{q_user}&provider=eq.{q_provider}")
                        patch_req  = urlreq.Request(patch_url,
                            data    = json.dumps({"token_json": refreshed}).encode(),
                            headers = {
                                "apikey":        SUPABASE_SERVICE_KEY,
                                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                                "Content-Type":  "application/json",
                                "Prefer":        "return=minimal",
                            }, method="PATCH")
                        urlreq.urlopen(patch_req, timeout=5)
                    except Exception:
                        pass
                else:
                    # Local file — overwrite with fresh token
                    local_path = token_source.split(":", 1)[-1] if ":" in token_source else "gcal_token.json"
                    try:
                        with open(local_path, "w", encoding="utf-8") as _f:
                            json.dump(refreshed, _f)
                    except Exception:
                        pass
                    # Also try to seed Supabase so it works next deploy
                    try:
                        seed_url = f"{SUPABASE_URL}/rest/v1/user_tokens"
                        seed_req = urlreq.Request(seed_url,
                            data    = json.dumps({"user_id": user_id, "provider": "google_calendar", "token_json": refreshed}).encode(),
                            headers = {
                                "apikey":        SUPABASE_SERVICE_KEY,
                                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                                "Content-Type":  "application/json",
                                "Prefer":        "resolution=merge-duplicates,return=minimal",
                            }, method="POST")
                        urlreq.urlopen(seed_req, timeout=5)
                    except Exception:
                        pass
            except Exception:
                pass  # refresh failed — try with possibly-expired token anyway

        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None


# -- Pydantic models ----------------------------------------------------------

class ChatRequest(BaseModel):
    user_id:          str
    message:          str
    chat_history:     List[Dict[str, Any]] = []
    idea_options:     List[Dict[str, Any]] = []
    current_location: Optional[str]        = None


class ChatResponse(BaseModel):
    type:     str
    text:     str
    pre_prep: str        = ""
    events:   List[Dict] = []
    raw_json: str        = ""


class AddEventRequest(BaseModel):
    user_id:     str
    title:       str
    start_time:  str
    end_time:    str
    location:    Optional[str] = None
    description: Optional[str] = None


class FeedbackRequest(BaseModel):
    user_id:       str
    mission:       str           # mission title OR AI response summary
    feedback:      str = ""
    rating:        str = "thumbs_up"
    # Extended fields for chat bubble feedback
    reason:        str = ""      # pivot chip label ("Too late", "Indoor instead", etc.)
    note:          str = ""      # free text if any
    feedback_type: str = ""      # "chat_thumbs_up" | "chat_thumbs_down" | "skipped" | "completed"
    # Store the full good response so the AI learns from it
    good_response_text:    str = ""   # AI message text when thumbs_up
    good_response_options: str = ""   # JSON list of option titles when thumbs_up


class SnoozeRequest(BaseModel):
    snoozed_until: str


# ── Admin models ──────────────────────────────────────────────────────────────

class AdminBumpRequest(BaseModel):
    email:     str
    admin_pin: str

class AdminPauseRequest(BaseModel):
    email:     str
    paused:    bool
    admin_pin: str


# -- app factory --------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_db()
        print("Supabase connected")
    except Exception as e:
        print(f"Supabase connection failed: {e}")
    yield


app = FastAPI(
    title="Family COO API",
    version="2.0.0",
    description="Backend for the Family COO AI assistant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- helpers ------------------------------------------------------------------

def _get_user_uuid(db: SupabaseClient, email: str) -> Optional[str]:
    try:
        res = db.table("users").select("id").eq("email", email).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        return None


def _get_user_memory(db: SupabaseClient, user_id: str) -> list:
    """
    Returns memory as a list of {kind, key, value, confidence, ts_utc} items.

    The Supabase user_memory.memory column can be either:
      A) A dict blob  {"cuisine": ["Indian"], "interests": [...], ...}  (onboarding format)
      B) A list of    {"kind":..., "key":..., "value":..., ...}         (brain-written format)

    get_memory_summary_from_memory() in utils.py expects format B.
    We normalise A → B here so the AI always sees a rich, de-duplicated
    preference list regardless of how the data was originally written.
    """
    try:
        res = db.table("user_memory").select("memory").eq("email", user_id).execute()
        if not res.data:
            return []
        mem = res.data[0].get("memory") or {}

        # Already in list format (brain-written, has 'key' field)
        if isinstance(mem, list):
            return mem

        if not isinstance(mem, dict):
            return []

        # ── Flatten dict blob → [{kind, key, value, confidence}] ──────────────
        # Maps every meaningful field from the onboarding/profile dict into the
        # key/value format that get_memory_summary_from_memory() iterates.
        out: list = []
        ts = "2026-01-01T00:00:00Z"  # stable fallback timestamp

        def _add(kind: str, key: str, value, conf: float = 0.8):
            v = value
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v) if v else ""
            if v:
                out.append({"kind": kind, "key": key, "value": str(v),
                            "confidence": conf, "ts_utc": ts})

        # Core preferences
        _add("preference", "cuisine",          mem.get("cuisine")          or mem.get("food_preferences"))
        _add("preference", "interests",        mem.get("interests")        or mem.get("lifestyle_interests"))
        _add("preference", "hobbies",          mem.get("hobbies")          or mem.get("hobby_list"))
        _add("preference", "food_preference",  mem.get("food_preference"))
        _add("preference", "diet",             mem.get("diet"))
        _add("preference", "tone",             mem.get("tone")             or mem.get("tone_response_style"))
        _add("preference", "scheduling_style", mem.get("scheduling_style"))
        _add("preference", "outing_preferences", mem.get("outing_preferences"))
        _add("preference", "weekend_style",    mem.get("weekend_style")    or mem.get("weekend_outing_style"))

        # Family / logistics
        fam = mem.get("family_members") or mem.get("family") or []
        if isinstance(fam, list) and fam:
            _add("profile", "family_members", ", ".join(str(f) for f in fam))
        elif isinstance(fam, str) and fam:
            _add("profile", "family_members", fam)
        _add("profile",  "location",      mem.get("location") or mem.get("home_city"))
        _add("profile",  "fitness",       mem.get("fitness")  or mem.get("gym"))
        _add("profile",  "vehicles",      mem.get("vehicles"))
        _add("profile",  "routines",      mem.get("routines"))

        # Activity preferences
        _add("preference", "outdoor_activities",  mem.get("outdoor_activities"))
        _add("preference", "activity_preferences",mem.get("activity_preferences"))
        _add("pattern",    "weekly_activity",     mem.get("weekly_activity"))
        _add("preference", "proactive_frequency", mem.get("proactive_frequency"))
        _add("preference", "avoid",               mem.get("avoid"))

        # Any extra keys not explicitly mapped above
        known = {"cuisine","food_preferences","interests","lifestyle_interests","hobbies",
                 "hobby_list","food_preference","diet","tone","tone_response_style",
                 "scheduling_style","outing_preferences","weekend_style","weekend_outing_style",
                 "family_members","family","location","home_city","fitness","gym","vehicles",
                 "routines","outdoor_activities","activity_preferences","weekly_activity",
                 "proactive_frequency","avoid"}
        for k, v in mem.items():
            if k not in known and v:
                _add("preference", k, v, conf=0.7)

        return out
    except Exception:
        return []


def _get_recent_missions(db: SupabaseClient, user_id: str) -> str:
    try:
        res = (
            db.table("mission_log")
            .select("title,status,end_time")
            .eq("user_id", _get_user_uuid(db, user_id))
            .order("end_time", desc=True)
            .limit(20)
            .execute()
        )
        return json.dumps(res.data or [])
    except Exception:
        return "[]"



def _track_usage(
    db: SupabaseClient,
    email: str,
    intent: str,
    tokens_used: int = 0,
    error_type: Optional[str] = None,
    error_msg: Optional[str] = None,
) -> None:
    """
    Atomically increments tester_usage counters and optionally logs a silent error.
    Fire-and-forget — never blocks or raises so the user response is never delayed.

    Tokens are estimated from word count (×1.3 multiplier) because the Anthropic SDK
    response object isn't threaded through to this layer. Accurate enough for the
    dashboard — real token counts can be swapped in later via usage metadata.
    """
    try:
        existing = (
            db.table("tester_usage")
            .select("id,request_count,token_count")
            .eq("email", email)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            db.table("tester_usage").update({
                "request_count": (row.get("request_count") or 0) + 1,
                "token_count":   (row.get("token_count")   or 0) + tokens_used,
                "last_intent":   intent[:80] if intent else "",
                "last_pulse":    datetime.utcnow().isoformat() + "Z",
            }).eq("email", email).execute()
        else:
            # Auto-register unknown callers with default limit
            db.table("tester_usage").insert({
                "email":         email,
                "display_name":  email.split("@")[0],
                "request_count": 1,
                "token_count":   tokens_used,
                "request_limit": 50,
                "last_intent":   intent[:80] if intent else "",
                "last_pulse":    datetime.utcnow().isoformat() + "Z",
            }).execute()
    except Exception:
        pass  # never block the user response

    if error_type:
        try:
            db.table("tester_errors").insert({
                "email":       email,
                "error_type":  error_type,
                "error_msg":   str(error_msg or "")[:500],
                "intent":      intent[:80] if intent else "",
                "tokens_used": tokens_used,
            }).execute()
        except Exception:
            pass


def _get_feedback_dump(db: SupabaseClient, user_id: str) -> str:
    """
    Returns the last 30 feedback entries as JSON.
    Includes mission title, feedback text, rating, reason, and timestamp.
    Used by the AI to learn what the user liked/disliked and avoid repeating mistakes.
    NOTE: orders by 'timestamp' (not created_at — that column doesn't exist).
    """
    try:
        res = (
            db.table("feedback_log")
            .select("mission,feedback,rating,reason,note,timestamp,feedback_type")
            .eq("email", user_id)
            .order("timestamp", desc=True)
            .limit(30)
            .execute()
        )
        return json.dumps(res.data or [])
    except Exception:
        # Fallback: try without ordering if timestamp column also fails
        try:
            res = (
                db.table("feedback_log")
                .select("mission,feedback,rating,reason,note,timestamp,feedback_type")
                .eq("email", user_id)
                .limit(30)
                .execute()
            )
            return json.dumps(res.data or [])
        except Exception:
            return "[]"


def _save_chat_turn(db: SupabaseClient, user_id: str, role: str, content: str, meta: dict = {}):
    try:
        uid = _get_user_uuid(db, user_id)
        if uid:
            db.table("chat_history").insert({
                "user_id": uid,
                "role":    role,
                "content": content,
                "meta":    meta,
            }).execute()
    except Exception:
        pass


def _gcal_upcoming(service) -> list:
    try:
        from datetime import timezone, timedelta
        now = datetime.now(timezone.utc)

        # Start from Sunday midnight of the CURRENT WEEK (ET) so the full
        # 7-day grid (Sun–Sat) is always populated — including past days like
        # Sunday, Monday, Tuesday when today is mid-week.
        # The frontend buildWeekGrid() shows Sun–Sat, so the API window must match.
        try:
            from zoneinfo import ZoneInfo
            et = ZoneInfo("America/New_York")
            now_et = datetime.now(et)
            # Go back to Sunday (weekday 6 in isoweekday, but 0 in .weekday() Mon-based)
            # .weekday(): Mon=0 … Sun=6  →  days_since_sunday = (weekday + 1) % 7
            days_since_sunday = (now_et.weekday() + 1) % 7
            week_sunday = now_et.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=days_since_sunday)
            time_min = week_sunday.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            # Fallback: 7 days ago from now
            time_min = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Fetch through end of next week so weekend planner always has data
        time_max = (now + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")

        result = service.events().list(
            calendarId  = "primary",
            timeMin     = time_min,
            timeMax     = time_max,
            maxResults  = 100,
            singleEvents= True,
            orderBy     = "startTime",
        ).execute()
        return result.get("items", [])
    except Exception:
        return []


# -- routes -------------------------------------------------------------------

@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok", "service": "Family COO API v2"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: SupabaseClient = Depends(get_db)):
    if not ANTHROPIC_KEY:
        raise HTTPException(500, "ANTHROPIC_API_KEY not configured")

    # ── Admin pause guard — checked on every call, fails fast ─────────────────
    try:
        pause_row = (
            db.table("tester_usage")
            .select("is_paused,request_count,request_limit")
            .eq("email", req.user_id)
            .execute()
        )
        if pause_row.data:
            row = pause_row.data[0]
            if row.get("is_paused"):
                raise HTTPException(403, "Access temporarily paused by admin.")
            if (row.get("request_count") or 0) >= (row.get("request_limit") or 50):
                _track_usage(db, req.user_id, intent=req.message[:80],
                             error_type="Limit Reached",
                             error_msg=f"Used {row.get('request_count')} of {row.get('request_limit')}")
                raise HTTPException(429, "Request limit reached. Contact admin to extend.")
    except HTTPException:
        raise
    except Exception:
        pass  # tester_usage table might not exist yet — don't block

    memory        = _get_user_memory(db, req.user_id)
    missions_dump = _get_recent_missions(db, req.user_id)
    feedback_dump = _get_feedback_dump(db, req.user_id)

    ideas_dump    = "[]"
    ideas_summary = []
    try:
        res = db.table("user_memory").select("ideas").eq("email", req.user_id).execute()
        if res.data:
            raw = res.data[0].get("ideas") or []
            # ideas can be stored as [{id,text,converted,...}] — filter to pending only
            if isinstance(raw, list):
                ideas_summary = [
                    {"text": i.get("text",""), "id": i.get("id","")}
                    for i in raw
                    if isinstance(i, dict) and i.get("text") and not i.get("converted")
                ]
            ideas_dump = json.dumps(ideas_summary)
    except Exception:
        pass

    # ── Merge frontend chat_history with DB history for richer context ─────────
    # Frontend state is cleared when the user taps "Clear". Loading recent DB
    # turns gives the AI continuity across sessions without bloating the prompt.
    merged_history = list(req.chat_history or [])
    if len(merged_history) < 6:
        try:
            uid = _get_user_uuid(db, req.user_id)
            if uid:
                db_hist = (
                    db.table("chat_history")
                    .select("role,content")
                    .eq("user_id", uid)
                    .order("created_at", desc=True)
                    .limit(10)
                    .execute()
                )
                # Reverse so oldest-first, then prepend to frontend history
                db_turns = list(reversed(db_hist.data or []))
                # Deduplicate: drop DB turns whose content already appears in frontend
                frontend_contents = {m.get("content","") for m in merged_history}
                db_turns = [t for t in db_turns if t.get("content","") not in frontend_contents]
                merged_history = db_turns + merged_history
        except Exception:
            pass

    calendar_data = []
    try:
        svc = _get_gcal_service(req.user_id)
        if svc:
            calendar_data = _gcal_upcoming(svc) or []
    except Exception:
        pass

    _save_chat_turn(db, req.user_id, "user", req.message)

    from src.brain import get_coo_response
    raw_json = get_coo_response(
        api_key          = ANTHROPIC_KEY,
        groq_key         = GROQ_KEY,
        user_request     = req.message,
        memory           = memory,
        calendar_data    = calendar_data,
        chat_history     = merged_history,   # ← merged DB + frontend history
        idea_options     = req.idea_options,
        ideas_summary    = ideas_summary,
        ideas_dump       = ideas_dump,
        missions_dump    = missions_dump,
        feedback_dump    = feedback_dump,
        current_location = req.current_location,
    )

    try:
        parsed = json.loads(raw_json)
    except Exception as _parse_err:
        parsed = {"type": "error", "text": raw_json, "pre_prep": "", "events": []}
        _track_usage(db, req.user_id, intent=req.message[:80],
                     error_type="Parse Error", error_msg=str(_parse_err))

    _save_chat_turn(db, req.user_id, "assistant", parsed.get("text", ""), meta=parsed)

    # ── Track usage silently — estimate tokens from message + response length ──
    _tokens = int(
        (len(req.message.split()) + len(parsed.get("text","").split())) * 1.3
    )
    _track_usage(db, req.user_id, intent=req.message[:80], tokens_used=_tokens)

    return ChatResponse(
        type     = parsed.get("type", "chat"),
        text     = parsed.get("text", ""),
        pre_prep = parsed.get("pre_prep", ""),
        events   = parsed.get("events") or [],
        raw_json = raw_json,
    )


@app.get("/api/calendar")
def get_calendar(user_id: str, db: SupabaseClient = Depends(get_db)):
    svc = _get_gcal_service(user_id)
    if not svc:
        raise HTTPException(403, "Google Calendar not connected. Please authenticate first.")
    events = _gcal_upcoming(svc)
    return {"events": events}


@app.post("/api/calendar/add")
def add_calendar_event(req: AddEventRequest, db: SupabaseClient = Depends(get_db)):
    svc = _get_gcal_service(req.user_id)
    if not svc:
        raise HTTPException(403, "Google Calendar not connected.")

    body: Dict[str, Any] = {
        "summary": req.title,
        "start":   {"dateTime": req.start_time, "timeZone": "America/New_York"},
        "end":     {"dateTime": req.end_time,   "timeZone": "America/New_York"},
    }
    if req.location:
        body["location"] = req.location
    if req.description:
        body["description"] = req.description

    try:
        event = svc.events().insert(calendarId="primary", body=body).execute()
        uid = _get_user_uuid(db, req.user_id)
        if uid:
            # ── FIX: Normalize to UTC before storing so isPast() is always correct.
            # The LLM emits naive ISO strings (no TZ offset); Supabase would treat
            # them as UTC, making a 5:30 PM ET event appear as 5:30 PM UTC (=1:30 PM ET)
            # and mark it OVERDUE 4 hours too early.
            end_utc = _to_utc_iso(req.end_time)
            db.table("mission_log").insert({
                "user_id":   uid,
                "source_id": event.get("id"),
                "title":     req.title,
                "end_time":  end_utc,
                "status":    "pending",
            }).execute()
        return {"success": True, "event_id": event.get("id"), "event": event}
    except Exception as e:
        raise HTTPException(500, f"Failed to add event: {e}")


@app.get("/api/missions")
def get_missions(user_id: str, status: str = "pending", db: SupabaseClient = Depends(get_db)):
    uid = _get_user_uuid(db, user_id)
    if not uid:
        return {"missions": []}
    try:
        q = db.table("mission_log").select("*").eq("user_id", uid)
        if status != "all":
            q = q.eq("status", status)
        res = q.order("end_time", desc=True).limit(50).execute()
        return {"missions": res.data or []}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/missions/{mission_id}/complete")
def complete_mission(mission_id: str, db: SupabaseClient = Depends(get_db)):
    try:
        db.table("mission_log").update({"status": "reviewed"}).eq("id", mission_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/missions/{mission_id}/snooze")
def snooze_mission(mission_id: str, req: SnoozeRequest, db: SupabaseClient = Depends(get_db)):
    try:
        db.table("mission_log").update({
            "snoozed_until": req.snoozed_until
        }).eq("id", mission_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/memory")
def get_memory(user_id: str, db: SupabaseClient = Depends(get_db)):
    try:
        res = db.table("user_memory").select("memory,ideas,updated_at").eq("email", user_id).execute()
        if not res.data:
            return {"memory": {}, "ideas": []}
        row = res.data[0]
        return {"memory": row.get("memory") or {}, "ideas": row.get("ideas") or []}
    except Exception as e:
        raise HTTPException(500, str(e))


class IdeasSyncRequest(BaseModel):
    user_id: str
    ideas:   List[Dict]


@app.get("/api/memory/ideas")
def get_ideas(user_id: str, db: SupabaseClient = Depends(get_db)):
    """Return the ideas array stored in user_memory for this user."""
    try:
        res = db.table("user_memory").select("ideas").eq("email", user_id).execute()
        if not res.data:
            return {"ideas": []}
        return {"ideas": res.data[0].get("ideas") or []}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/memory/ideas")
def save_ideas(req: IdeasSyncRequest, db: SupabaseClient = Depends(get_db)):
    """
    Upsert the full ideas list into user_memory.ideas.
    This is the Supabase source-of-truth for ideas — AsyncStorage is just
    a local cache. On every add/remove/convert, the client POSTs the full
    array here so it survives cache clears, reinstalls, and device switches.
    """
    try:
        # Check if the user row already exists
        existing = db.table("user_memory").select("email").eq("email", req.user_id).execute()
        if existing.data:
            db.table("user_memory").update({"ideas": req.ideas}).eq("email", req.user_id).execute()
        else:
            db.table("user_memory").insert({"email": req.user_id, "ideas": req.ideas}).execute()
        return {"success": True, "count": len(req.ideas)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/feedback")
def save_feedback(req: FeedbackRequest, db: SupabaseClient = Depends(get_db)):
    """
    Stores feedback from both mission snooze/complete and chat bubble thumbs.

    For chat thumbs_up: good_response_text + good_response_options are stored
    so the AI can reference what worked well in future sessions.

    For chat thumbs_down: reason (pivot chip label) is stored so the AI avoids
    repeating the same type of suggestion.
    """
    uid = _get_user_uuid(db, req.user_id)
    try:
        row: dict = {
            "user_id":      uid,
            "email":        req.user_id,
            "mission":      req.mission,
            "feedback":     req.feedback,
            "rating":       req.rating,
            "reason":       req.reason,
            "note":         req.note,
            "timestamp":    "now",
            "entry_type":   "feedback",
            "feedback_type": req.feedback_type or ("chat_thumbs_up" if req.rating == "thumbs_up" else "feedback"),
        }
        # Persist good response content so prompts.py feedback_block can surface it
        if req.rating == "thumbs_up" and req.good_response_text:
            row["feedback"] = f"[GOOD RESPONSE] {req.good_response_text[:300]}"
        if req.good_response_options:
            row["note"] = req.good_response_options[:400]

        db.table("feedback_log").insert(row).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/chat/history")
def chat_history(user_id: str, limit: int = 50, db: SupabaseClient = Depends(get_db)):
    uid = _get_user_uuid(db, user_id)
    if not uid:
        return {"history": []}
    try:
        res = (
            db.table("chat_history")
            .select("role,content,meta,created_at")
            .eq("user_id", uid)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return {"history": res.data or []}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/insights")
def get_insights(user_id: str, db: SupabaseClient = Depends(get_db)):
    """Dashboard KPIs + pattern insights. Zero LLM tokens."""
    uid = _get_user_uuid(db, user_id)

    feedback_rows: list = []
    mission_rows:  list = []

    try:
        fb = (
            db.table("feedback_log")
            .select("mission,rating,timestamp")
            .eq("email", user_id)
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        feedback_rows = fb.data or []
    except Exception:
        pass

    try:
        ms = (
            db.table("mission_log")
            .select("title,status,end_time")
            .eq("user_id", uid)
            .order("end_time", desc=True)
            .limit(100)
            .execute()
        )
        mission_rows = ms.data or []
    except Exception:
        pass

    _noise = {
        "last plan", "plan", "trainbrain: bad response", "",
        "test missed task", "test missed task (rescheduled)",
    }
    real_fb   = [m for m in feedback_rows if (m.get("mission") or "").lower().strip() not in _noise]
    completed = [m for m in real_fb if "thumbs_up"   in str(m.get("rating", "")) or chr(128077) in str(m.get("rating", ""))]
    skipped   = [m for m in real_fb if "thumbs_down" in str(m.get("rating", "")) or chr(128078) in str(m.get("rating", ""))]
    total     = len(completed) + len(skipped)
    pct       = int(100 * len(completed) / total) if total else 0

    now = datetime.now().astimezone()
    pending_count = sum(1 for m in mission_rows if m.get("status") == "pending")
    overdue_count = 0
    for m in mission_rows:
        if m.get("status") == "pending" and m.get("end_time"):
            try:
                end = datetime.fromisoformat(m["end_time"].replace("Z", "+00:00"))
                if end.tzinfo is None:
                    end = end.replace(tzinfo=now.tzinfo)
                if end < now:
                    overdue_count += 1
            except Exception:
                pass

    insights = []

    if total == 0:
        insights.append({
            "emoji": "💡", "type": "tip",
            "headline": "No history yet",
            "detail": "Complete a few missions and your patterns will show up here.",
        })
    else:
        if pct >= 80:
            insights.append({
                "emoji": "🟢", "type": "win",
                "headline": f"You're nailing it — {pct}% completion rate",
                "detail": f"You followed through on {len(completed)} of {total} tracked events. Strong track record.",
            })
        elif pct >= 60:
            insights.append({
                "emoji": "🟡", "type": "stat",
                "headline": f"Decent follow-through — {pct}% completed",
                "detail": f"{len(completed)} of {total} events done. A few easy wins could push this above 80%.",
            })
        else:
            insights.append({
                "emoji": "🔴", "type": "watch",
                "headline": f"{pct}% completion — plans aren't sticking",
                "detail": f"Only {len(completed)} of {total} events completed. Try scheduling fewer, higher-priority commitments.",
            })

        skip_counts: Counter = Counter()
        for m in skipped:
            title = (m.get("mission") or "").lower()
            for kw, label in [
                ("outing", "family outings"), ("judo", "judo classes"),
                ("gym", "gym sessions"),      ("doctor", "doctor visits"),
                ("grocery", "grocery runs"),  ("aquarium", "aquarium trips"),
            ]:
                if kw in title:
                    skip_counts[label] += 1
        if skip_counts:
            top_skip, skip_n = skip_counts.most_common(1)[0]
            insights.append({
                "emoji": "⚠️", "type": "watch",
                "headline": f"{top_skip.capitalize()} keep getting skipped ({skip_n}x)",
                "detail": "These show up planned but don't happen. The timing might be off or the commitment too heavy.",
            })

        done_counts: Counter = Counter()
        for m in completed:
            title = (m.get("mission") or "").lower()
            for kw, label in [
                ("judo", "Judo classes"),    ("gym", "Gym sessions"),
                ("doctor", "Doctor visits"), ("outing", "Family outings"),
                ("grocery", "Grocery runs"),
            ]:
                if kw in title:
                    done_counts[label] += 1
        if done_counts:
            top_done, done_n = done_counts.most_common(1)[0]
            insights.append({
                "emoji": "✅", "type": "win",
                "headline": f"{top_done} — your most reliable habit ({done_n}x done)",
                "detail": "This is clearly working for your family. Protect this time slot.",
            })

        day_counts: Counter = Counter()
        for m in completed:
            ts = m.get("timestamp", "")
            try:
                d = datetime.fromisoformat(ts).strftime("%A")
                day_counts[d] += 1
            except Exception:
                pass
        if day_counts and day_counts.most_common(1)[0][1] >= 2:
            best_day, best_n = day_counts.most_common(1)[0]
            insights.append({
                "emoji": "📅", "type": "stat",
                "headline": f"{best_day}s are your most productive day",
                "detail": f"You've completed {best_n} events on {best_day}s. Schedule important things here.",
            })

        if pct < 65:
            insights.append({
                "emoji": "💡", "type": "tip",
                "headline": "Schedule fewer things, finish more",
                "detail": "With completion under 65%, the issue is usually too many plans. Pick 2 family commitments per week and protect those.",
            })

    return {
        "kpis": {
            "completion_pct":   pct,
            "total_feedback":   total,
            "completed_count":  len(completed),
            "skipped_count":    len(skipped),
            "pending_missions": pending_count,
            "overdue_missions": overdue_count,
        },
        "insights": insights[:5],
    }


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS  —  protected by ADMIN_PIN env var
# ═════════════════════════════════════════════════════════════════════════════

ADMIN_PIN    = os.environ.get("ADMIN_PIN", "4240")
ADMIN_EMAILS: list = ["tushar.khandare@gmail.com"]

# ── Waitlist / email config ────────────────────────────────────────────────────
VERCEL_URL    = os.environ.get("VERCEL_URL",    "https://family-coo-landing.vercel.app")
RENDER_URL    = os.environ.get("RENDER_URL",    "https://family-coo.onrender.com")
EMAIL_FROM    = os.environ.get("EMAIL_FROM",    "")   # your gmail address
EMAIL_PASS    = os.environ.get("EMAIL_PASS",    "")   # Gmail app password
ADMIN_EMAIL   = os.environ.get("ADMIN_EMAIL",   "tushar.khandare@gmail.com")
GOOGLE_OAUTH_REDIRECT = f"{os.environ.get('RENDER_URL', 'https://family-coo.onrender.com')}/api/waitlist/callback"

def _verify_admin(pin: str) -> None:
    """Raise 403 if PIN is wrong. One-liner guard used by all admin routes."""
    if pin != ADMIN_PIN:
        raise HTTPException(403, "Invalid admin PIN")


@app.get("/api/admin/stats")
def admin_stats(admin_pin: str, db: SupabaseClient = Depends(get_db)):
    """
    Returns the full tester roster with usage + recent errors merged per tester.
    Called by the admin dashboard on load and every 30-second poll.

    Response shape:
      {
        testers: [{email, display_name, request_count, token_count, request_limit,
                   is_paused, last_intent, last_pulse, joined_at,
                   recent_errors: [{error_type, error_msg, intent, created_at}]}],
        totals:  {total_requests, total_tokens, active_today, alert_count}
      }
    """
    _verify_admin(admin_pin)
    try:
        testers_res = db.table("tester_usage").select("*").order("last_pulse", desc=True).execute()
        testers = testers_res.data or []
    except Exception as e:
        raise HTTPException(500, f"Could not fetch tester_usage: {e}")

    # Fetch errors from the last 24 hours
    try:
        from datetime import timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        errors_res = (
            db.table("tester_errors")
            .select("email,error_type,error_msg,intent,created_at")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        errors_raw = errors_res.data or []
    except Exception:
        errors_raw = []

    # Group errors by email
    errors_by_email: dict = {}
    for e in errors_raw:
        em = e.get("email", "")
        errors_by_email.setdefault(em, []).append(e)

    # Merge errors onto tester rows + compute alert flag
    from datetime import timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    active_today = 0
    alert_count  = 0

    for t in testers:
        em = t.get("email", "")
        t["recent_errors"] = errors_by_email.get(em, [])[:5]

        # Active today = last_pulse within 24h
        pulse_str = t.get("last_pulse") or ""
        try:
            pulse_dt = datetime.fromisoformat(pulse_str.replace("Z", "+00:00"))
            if (now_utc - pulse_dt).total_seconds() < 86400:
                active_today += 1
        except Exception:
            pass

        # Alert = has errors OR at/above 84% of limit
        limit = t.get("request_limit") or 50
        used  = t.get("request_count") or 0
        has_alert = bool(t["recent_errors"]) or (used / max(limit, 1) >= 0.84)
        t["has_alert"] = has_alert
        if has_alert:
            alert_count += 1

    # Compute global totals
    total_requests = sum(t.get("request_count", 0) for t in testers)
    total_tokens   = sum(t.get("token_count",   0) for t in testers)

    return {
        "testers": testers,
        "totals": {
            "total_requests": total_requests,
            "total_tokens":   total_tokens,
            "active_today":   active_today,
            "alert_count":    alert_count,
        },
    }


@app.post("/api/admin/bump")
def admin_bump(req: AdminBumpRequest, db: SupabaseClient = Depends(get_db)):
    """
    Increments a tester's request_limit by 25.
    Called when admin taps "Bump Limit +25" on the dashboard.
    """
    _verify_admin(req.admin_pin)
    try:
        existing = db.table("tester_usage").select("request_limit").eq("email", req.email).execute()
        if not existing.data:
            raise HTTPException(404, f"Tester {req.email} not found")
        current_limit = existing.data[0].get("request_limit") or 50
        new_limit = current_limit + 25
        db.table("tester_usage").update({
            "request_limit": new_limit,
        }).eq("email", req.email).execute()
        return {"success": True, "email": req.email, "new_limit": new_limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/admin/pause")
def admin_pause(req: AdminPauseRequest, db: SupabaseClient = Depends(get_db)):
    """
    Toggles is_paused on a tester row.
    When paused=True, the /api/chat guard rejects their calls immediately.
    Takes effect on the next request — no restart needed.
    """
    _verify_admin(req.admin_pin)
    try:
        existing = db.table("tester_usage").select("id").eq("email", req.email).execute()
        if not existing.data:
            raise HTTPException(404, f"Tester {req.email} not found")
        db.table("tester_usage").update({
            "is_paused": req.paused,
        }).eq("email", req.email).execute()
        action = "paused" if req.paused else "unpaused"
        return {"success": True, "email": req.email, "status": action}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# WAITLIST ENDPOINTS  —  Full OAuth → waitlist → approve → deep link flow
# ═════════════════════════════════════════════════════════════════════════════

# ── Email helper ──────────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, html_body: str) -> bool:
    """Send HTML email via Gmail SMTP. Returns True on success."""
    if not EMAIL_FROM or not EMAIL_PASS:
        print(f"[email] skipped — EMAIL_FROM/EMAIL_PASS not set. Would send to: {to}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_FROM
        msg["To"]      = to
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as s:
            s.login(EMAIL_FROM, EMAIL_PASS)
            s.sendmail(EMAIL_FROM, to, msg.as_string())
        print(f"[email] sent to {to}")
        return True
    except Exception as e:
        print(f"[email] failed: {e}")
        return False


def _google_token_exchange(code: str) -> dict:
    """
    Exchange Google auth code for id_token.
    Decodes the JWT payload (no signature verify — we trust Google's redirect).
    Returns dict with at least: email, name.
    """
    data = urllib.parse.urlencode({
        "code":          code,
        "client_id":     WAITLIST_CLIENT_ID,
        "client_secret": WAITLIST_CLIENT_SECRET,
        "redirect_uri":  GOOGLE_OAUTH_REDIRECT,
        "grant_type":    "authorization_code",
    }).encode()
    req = _urlreq.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with _urlreq.urlopen(req, timeout=15) as r:
        tokens = json.loads(r.read())

    id_token = tokens.get("id_token", "")
    if not id_token:
        raise ValueError("No id_token in Google response")

    # Decode JWT payload (middle segment) — base64url, no sig verify needed
    parts = id_token.split(".")
    payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
    info = json.loads(base64.urlsafe_b64decode(payload_b64))
    return {
        "email": info.get("email", ""),
        "name":  info.get("name", info.get("email", "").split("@")[0]),
        "sub":   info.get("sub", ""),
    }


# ── 1. OAuth callback — Google redirects here after sign-in ──────────────────

@app.get("/api/waitlist/callback")
def waitlist_callback(code: str, db: SupabaseClient = Depends(get_db)):
    """
    Google redirects here with ?code=…
    Flow:
      1. Exchange code for email via Google token endpoint
      2. Upsert into waitlist table (pending)
      3. Email admin (you) — new application alert
      4. Redirect browser → Vercel /waiting.html?email=…&pos=…
    """
    # Exchange code for user info
    try:
        user = _google_token_exchange(code)
    except Exception as e:
        raise HTTPException(400, f"Google auth failed: {e}")

    email = user["email"]
    name  = user["name"]

    if not email:
        raise HTTPException(400, "Could not retrieve email from Google")

    # Upsert into waitlist — ignore if already exists
    try:
        existing = db.table("waitlist").select("id,position,status").eq("email", email).execute()
        if existing.data:
            row      = existing.data[0]
            position = row.get("position") or 1
            status   = row.get("status")   or "pending"
        else:
            # Insert new applicant
            res = db.table("waitlist").insert({
                "email":  email,
                "name":   name,
                "status": "pending",
            }).execute()
            row      = res.data[0] if res.data else {}
            position = row.get("position") or 1
            status   = "pending"
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")

    # Email admin — new application alert
    admin_approve_url = (
        f"{RENDER_URL}/api/waitlist/approve"
        f"?email={urllib.parse.quote(email)}&admin_pin={ADMIN_PIN}"
    )
    _send_email(
        to      = ADMIN_EMAIL,
        subject = f"🏠 New Family COO Beta Application — {name}",
        html_body = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
  <h2 style="color:#1C1917;margin-bottom:8px">New Beta Application</h2>
  <p style="color:#44403C;margin-bottom:20px">Someone just applied for Family COO beta access.</p>
  <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
    <tr><td style="padding:8px 0;color:#78716C;font-size:13px">Name</td>
        <td style="padding:8px 0;font-weight:500;color:#1C1917">{name}</td></tr>
    <tr><td style="padding:8px 0;color:#78716C;font-size:13px">Email</td>
        <td style="padding:8px 0;font-weight:500;color:#1C1917">{email}</td></tr>
    <tr><td style="padding:8px 0;color:#78716C;font-size:13px">Queue position</td>
        <td style="padding:8px 0;font-weight:500;color:#C2690A">#{position}</td></tr>
  </table>
  <a href="{admin_approve_url}"
     style="display:inline-block;background:#C2690A;color:#fff;padding:14px 28px;
            border-radius:100px;text-decoration:none;font-weight:600;font-size:14px">
    ✓ Approve {name}
  </a>
  <p style="color:#A8A29E;font-size:12px;margin-top:16px">
    Or go to your admin dashboard to manage all applicants.
  </p>
</div>"""
    )

    # Redirect browser to Vercel waiting page
    redirect_url = (
        f"{VERCEL_URL}/waiting.html"
        f"?email={urllib.parse.quote(email)}"
        f"&pos={position}"
        f"&name={urllib.parse.quote(name)}"
    )
    return RedirectResponse(url=redirect_url, status_code=302)


# ── 2. Status check — polled by waiting.html every 60s ───────────────────────

@app.get("/api/waitlist/status")
def waitlist_status(email: str, db: SupabaseClient = Depends(get_db)):
    """Called by waiting.html to check if status changed to approved."""
    try:
        res = (
            db.table("waitlist")
            .select("status,position,access_token")
            .eq("email", email)
            .execute()
        )
        if not res.data:
            raise HTTPException(404, "Not found")
        row = res.data[0]
        return {
            "status":       row.get("status", "pending"),
            "position":     row.get("position", 1),
            "access_token": row.get("access_token") if row.get("status") == "approved" else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── 3. Approve — called from admin dashboard or one-click email link ──────────

@app.get("/api/waitlist/approve")
@app.post("/api/waitlist/approve")
def waitlist_approve(
    email:     str,
    admin_pin: str,
    db: SupabaseClient = Depends(get_db),
):
    """
    Approves a waitlist applicant.
    - Sets status=approved in waitlist
    - Seeds tester_usage so admin dashboard tracks them
    - Sends approval email with deep link token
    Supports both GET (one-click from email) and POST (from admin dashboard).
    """
    _verify_admin(admin_pin)
    try:
        res = db.table("waitlist").select("*").eq("email", email).execute()
        if not res.data:
            raise HTTPException(404, f"{email} not on waitlist")
        row = res.data[0]

        if row.get("status") == "approved":
            return {"success": True, "message": "Already approved", "email": email}

        # Mark approved and stamp timestamp
        db.table("waitlist").update({
            "status":      "approved",
            "approved_at": datetime.utcnow().isoformat() + "Z",
        }).eq("email", email).execute()

        # Seed tester_usage so admin dashboard sees them
        existing_usage = db.table("tester_usage").select("id").eq("email", email).execute()
        if not existing_usage.data:
            db.table("tester_usage").insert({
                "email":         email,
                "display_name":  row.get("name", email.split("@")[0]),
                "request_count": 0,
                "token_count":   0,
                "request_limit": 50,
                "is_paused":     False,
                "last_pulse":    datetime.utcnow().isoformat() + "Z",
            }).execute()

        # Fetch the access_token (auto-generated uuid on insert)
        updated = db.table("waitlist").select("access_token,name").eq("email", email).execute()
        access_token = updated.data[0].get("access_token") if updated.data else ""
        name         = updated.data[0].get("name", "there") if updated.data else "there"

        # Build approval email
        approve_link = f"{VERCEL_URL}/approved.html?token={access_token}"
        _send_email(
            to      = email,
            subject = "You're approved — welcome to Family COO 🏠",
            html_body = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px">
  <h1 style="font-family:Georgia,serif;font-size:36px;font-weight:300;color:#1C1917;margin-bottom:12px">
    Welcome, {name}!
  </h1>
  <p style="font-size:16px;color:#44403C;line-height:1.65;margin-bottom:28px">
    Your Family COO beta application has been approved.
    Tap the button below to access the app and complete your household profile.
    It takes about 3 minutes.
  </p>
  <a href="{approve_link}"
     style="display:inline-block;background:#C2690A;color:#fff;
            padding:16px 36px;border-radius:100px;text-decoration:none;
            font-weight:600;font-size:16px;letter-spacing:-.01em">
    Access Family COO →
  </a>
  <p style="font-size:13px;color:#A8A29E;margin-top:24px;line-height:1.6">
    This link is personal to you. It opens the app directly and takes you
    straight to onboarding — no waiting room.
    <br><br>
    If the button doesn't work, copy this link into your browser:<br>
    <span style="color:#C2690A;font-size:12px">{approve_link}</span>
  </p>
</div>"""
        )

        # If called via GET (one-click from email) redirect to a confirmation page
        return {
            "success":  True,
            "email":    email,
            "message":  f"Approved and email sent to {email}",
            "token":    access_token,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── 4. Validate — called by approved.html and the Expo app on launch ─────────

@app.get("/api/waitlist/validate")
def waitlist_validate(token: str, db: SupabaseClient = Depends(get_db)):
    """
    Validates an access token from the approval deep link.
    Called by:
      - approved.html  (shows "you're in" UI)
      - Expo app       (on launch, to skip waiting room and go to onboarding)
    Returns email and approved=True, or 403 if token is invalid/not approved.
    """
    try:
        res = (
            db.table("waitlist")
            .select("email,name,status,access_token")
            .eq("access_token", token)
            .execute()
        )
        if not res.data:
            raise HTTPException(403, "Invalid access token")
        row = res.data[0]
        if row.get("status") != "approved":
            raise HTTPException(403, "Token exists but access not yet approved")
        return {
            "approved": True,
            "email":    row.get("email"),
            "name":     row.get("name"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))