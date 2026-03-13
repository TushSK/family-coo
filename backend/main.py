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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    try:
        import urllib.parse, urllib.request as urlreq
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GRequest
        from googleapiclient.discovery import build

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
        if not rows:
            return None

        token_data = rows[0].get("token_json") or {}
        if isinstance(token_data, str):
            token_data = json.loads(token_data)

        google_cfg = _SECRETS.get("google_oauth", {})
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=google_cfg.get("client_id", ""),
            client_secret=google_cfg.get("client_secret", ""),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GRequest())

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
    user_id:  str
    mission:  str
    feedback: str = ""
    rating:   str = "thumbs_up"


class SnoozeRequest(BaseModel):
    snoozed_until: str


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
    try:
        res = db.table("user_memory").select("memory").eq("email", user_id).execute()
        if res.data:
            mem = res.data[0].get("memory") or {}
            if isinstance(mem, dict):
                return [mem]
            if isinstance(mem, list):
                return mem
        return []
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


def _get_feedback_dump(db: SupabaseClient, user_id: str) -> str:
    try:
        res = (
            db.table("feedback_log")
            .select("mission,feedback,rating,timestamp")
            .eq("email", user_id)
            .order("created_at", desc=True)
            .limit(20)
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
        from datetime import timezone
        now    = datetime.now(timezone.utc).isoformat()
        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=60,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except Exception:
        return []


# -- routes -------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Family COO API v2"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: SupabaseClient = Depends(get_db)):
    if not ANTHROPIC_KEY:
        raise HTTPException(500, "ANTHROPIC_API_KEY not configured")

    memory        = _get_user_memory(db, req.user_id)
    missions_dump = _get_recent_missions(db, req.user_id)
    feedback_dump = _get_feedback_dump(db, req.user_id)

    ideas_dump    = "[]"
    ideas_summary = []
    try:
        res = db.table("user_memory").select("ideas").eq("email", req.user_id).execute()
        if res.data:
            raw = res.data[0].get("ideas") or []
            ideas_summary = raw if isinstance(raw, list) else []
            ideas_dump    = json.dumps(ideas_summary)
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
        chat_history     = req.chat_history,
        idea_options     = req.idea_options,
        ideas_summary    = ideas_summary,
        ideas_dump       = ideas_dump,
        missions_dump    = missions_dump,
        feedback_dump    = feedback_dump,
        current_location = req.current_location,
    )

    try:
        parsed = json.loads(raw_json)
    except Exception:
        parsed = {"type": "error", "text": raw_json, "pre_prep": "", "events": []}

    _save_chat_turn(db, req.user_id, "assistant", parsed.get("text", ""), meta=parsed)

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
            db.table("mission_log").insert({
                "user_id":   uid,
                "source_id": event.get("id"),
                "title":     req.title,
                "end_time":  req.end_time,
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


@app.post("/api/feedback")
def save_feedback(req: FeedbackRequest, db: SupabaseClient = Depends(get_db)):
    uid = _get_user_uuid(db, req.user_id)
    try:
        db.table("feedback_log").insert({
            "user_id":    uid,
            "email":      req.user_id,
            "mission":    req.mission,
            "feedback":   req.feedback,
            "rating":     req.rating,
            "timestamp":  "now",
            "entry_type": "feedback",
        }).execute()
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
