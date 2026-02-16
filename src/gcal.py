# src/gcal.py
"""
Google Calendar helpers for Family COO.

Design goals:
- Works with either local token.json (dev) OR Supabase token storage (multi-session).
- Supports OAuth Device Flow (recommended for Streamlit).
- Keeps all datetimes timezone-aware to avoid "naive vs aware" errors.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.token_store import supabase_get_token, supabase_upsert_token

SCOPES = ["https://www.googleapis.com/auth/calendar"]

GOOGLE_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


# -----------------------
# INTERNALS
# -----------------------
def _safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _load_token_from_supabase(user_id: str) -> Optional[dict]:
    try:
        token_json = supabase_get_token(st, user_id=user_id, provider="google_calendar")
        if not token_json:
            return None
        if isinstance(token_json, dict):
            return token_json
        if isinstance(token_json, str):
            return json.loads(token_json)
        return None
    except Exception:
        return None


def _save_token_to_supabase(user_id: str, token_dict: dict) -> bool:
    try:
        return bool(supabase_upsert_token(st, user_id=user_id, token_json=token_dict, provider="google_calendar"))
    except Exception:
        return False


def _load_token_from_local() -> Optional[dict]:
    token_file = "token.json"
    if not os.path.exists(token_file):
        return None
    try:
        if os.path.getsize(token_file) <= 0:
            _safe_remove(token_file)
            return None
        with open(token_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        _safe_remove(token_file)
        return None


def _save_token_to_local(token_dict: dict) -> None:
    try:
        with open("token.json", "w", encoding="utf-8") as f:
            json.dump(token_dict, f)
    except Exception:
        pass


def _coerce_aware(dt: datetime) -> datetime:
    """Ensure dt is timezone-aware (UTC default)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _oauth_cfg() -> Optional[dict]:
    """
    Expected secrets layout:
      [google_oauth]
      client_id = "..."
      client_secret = "..."   # recommended
    """
    try:
        g = st.secrets.get("google_oauth", {})
        cid = (g.get("client_id") or "").strip()
        csec = (g.get("client_secret") or "").strip()
        if not cid:
            return None
        return {"client_id": cid, "client_secret": csec}
    except Exception:
        return None


def _build_creds_from_token_dict(token_dict: dict) -> Optional[Credentials]:
    try:
        if not token_dict:
            return None
        return Credentials.from_authorized_user_info(token_dict, SCOPES)
    except Exception:
        return None


# -----------------------
# PUBLIC API: AUTH / SERVICE
# -----------------------
def get_calendar_service(user_id: Optional[str] = None):
    """
    Returns a googleapiclient Calendar service or None.
    If user_id is provided, tries Supabase token first, then local token.json.
    """
    token_dict = None

    if user_id:
        token_dict = _load_token_from_supabase(user_id)

    if not token_dict:
        token_dict = _load_token_from_local()

    creds = _build_creds_from_token_dict(token_dict) if token_dict else None

    # Refresh if needed
    if creds and (not creds.valid):
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = json.loads(creds.to_json())
                if user_id:
                    _save_token_to_supabase(user_id, refreshed)
                else:
                    _save_token_to_local(refreshed)
            except Exception:
                creds = None
        else:
            creds = None

    if not creds:
        return None

    try:
        return build("calendar", "v3", credentials=creds)
    except Exception:
        return None


def start_device_flow() -> Dict[str, Any]:
    """
    Starts Google OAuth Device Flow.
    Returns dict with device_code, user_code, verification_url, interval, expires_in
    or {"error": "..."}.
    """
    cfg = _oauth_cfg()
    if not cfg:
        return {"error": "Missing google_oauth.client_id in secrets."}

    payload = urllib.parse.urlencode(
        {"client_id": cfg["client_id"], "scope": " ".join(SCOPES)}
    ).encode("utf-8")

    req = urllib.request.Request(
        GOOGLE_DEVICE_CODE_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "verification_url" not in data and "verification_uri" in data:
            data["verification_url"] = data["verification_uri"]
        return data
    except Exception as e:
        return {"error": f"Device flow start failed: {str(e)}"}


def poll_device_flow(device_code: str, interval: int = 5) -> Dict[str, Any]:
    """
    Polls token endpoint once (Streamlit-friendly).
    Returns token dict or {"error": "..."}.
    Non-fatal errors: authorization_pending, slow_down
    """
    cfg = _oauth_cfg()
    if not cfg:
        return {"error": "Missing google_oauth.client_id in secrets."}

    payload_dict = {
        "client_id": cfg["client_id"],
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }
    if cfg.get("client_secret"):
        payload_dict["client_secret"] = cfg["client_secret"]

    payload = urllib.parse.urlencode(payload_dict).encode("utf-8")

    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            return json.loads(body)
        except Exception:
            return {"error": f"Token poll failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Token poll failed: {str(e)}"}
    finally:
        try:
            time.sleep(min(max(interval, 1), 5))
        except Exception:
            pass


def save_token_from_device_flow(user_id: str, token_response: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Persists device-flow token response to Supabase under user_id.
    Returns (ok, message)
    """
    if not user_id:
        return False, "Missing user email."

    if not token_response or token_response.get("error"):
        return False, token_response.get("error", "No token response.")

    cfg = _oauth_cfg()
    if not cfg:
        return False, "Missing google_oauth.client_id in secrets."

    token_dict = {
        "token": token_response.get("access_token"),
        "refresh_token": token_response.get("refresh_token"),
        "token_uri": GOOGLE_TOKEN_URL,
        "client_id": cfg["client_id"],
        "client_secret": cfg.get("client_secret", ""),
        "scopes": SCOPES,
    }

    ok = _save_token_to_supabase(user_id, token_dict)
    if ok:
        return True, "✅ Calendar connected!"
    return False, "Could not save token to Supabase."


# -----------------------
# PUBLIC API: EVENTS
# -----------------------
def format_friendly_date(iso_str: str) -> str:
    """Converts ISO string to 'Fri, Feb 13 @ 5:00 PM' or 'Fri, Feb 13 (All Day)'."""
    try:
        if not iso_str:
            return ""
        if "T" in iso_str:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.astimezone().strftime("%a, %b %d @ %I:%M %p")
        dt = datetime.strptime(iso_str, "%Y-%m-%d")
        return dt.strftime("%a, %b %d (All Day)")
    except Exception:
        return iso_str


def get_upcoming_events_list(user_id: Optional[str] = None, days: int = 7) -> Optional[List[dict]]:
    """Returns list of upcoming events (next N days). Returns None if not connected."""
    try:
        service = get_calendar_service(user_id=user_id)
        if not service:
            return None

        now_dt = datetime.now(timezone.utc)
        max_dt = now_dt + timedelta(days=days)

        time_min = now_dt.isoformat().replace("+00:00", "Z")
        time_max = max_dt.isoformat().replace("+00:00", "Z")

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        items = events_result.get("items", [])
        clean_events = []

        for ev in items:
            start_raw = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
            end_raw = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
            clean_events.append(
                {
                    "id": ev.get("id"),
                    "title": ev.get("summary", "Busy"),
                    "start_raw": start_raw,
                    "end_raw": end_raw,
                    "start_friendly": format_friendly_date(start_raw),
                    "end_friendly": format_friendly_date(end_raw),
                    "location": ev.get("location", ""),
                }
            )

        return clean_events
    except Exception:
        return None


def get_events_range(user_id: str, start_dt: datetime, end_dt: datetime) -> Optional[List[dict]]:
    """Fetch events between start_dt and end_dt (timezone-safe)."""
    try:
        service = get_calendar_service(user_id=user_id)
        if not service:
            return None

        s = _coerce_aware(start_dt)
        e = _coerce_aware(end_dt)

        time_min = s.isoformat().replace("+00:00", "Z")
        time_max = e.isoformat().replace("+00:00", "Z")

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=250,
            )
            .execute()
        )

        items = events_result.get("items", [])
        out: List[dict] = []
        for ev in items:
            start_raw = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
            end_raw = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
            out.append(
                {
                    "id": ev.get("id"),
                    "title": ev.get("summary", "Busy"),
                    "start_raw": start_raw,
                    "end_raw": end_raw,
                    "start_friendly": format_friendly_date(start_raw),
                    "end_friendly": format_friendly_date(end_raw),
                    "location": ev.get("location", ""),
                    "description": ev.get("description", ""),
                }
            )
        return out
    except Exception:
        return None


def add_event_to_calendar(*args, **kwargs) -> Tuple[bool, str, Optional[str]]:
    """
    Backward-compatible add to Google Calendar.

    Supports BOTH call styles:
      1) add_event_to_calendar(event_dict, user_id="email")
      2) add_event_to_calendar(user_id, event_dict)   <-- current flow.py does this

    Returns: (ok:bool, message:str, event_id:Optional[str])
    """
    user_id = kwargs.get("user_id")
    event = None

    # Handle positional args
    if len(args) == 1:
        # could be (event_dict) or (user_id)
        if isinstance(args[0], dict):
            event = args[0]
        else:
            user_id = args[0]
    elif len(args) >= 2:
        # could be (event_dict, user_id) or (user_id, event_dict)
        if isinstance(args[0], dict) and not isinstance(args[1], dict):
            event = args[0]
            user_id = args[1]
        elif not isinstance(args[0], dict) and isinstance(args[1], dict):
            user_id = args[0]
            event = args[1]
        elif isinstance(args[0], dict) and isinstance(args[1], dict):
            # ambiguous: pick first as event
            event = args[0]
        else:
            # both non-dict -> invalid
            return False, "Invalid arguments for add_event_to_calendar()", None

    if not isinstance(event, dict):
        return False, "Invalid event payload (expected dict).", None

    try:
        service = get_calendar_service(user_id=user_id)
        if service:
            start_str = event.get("start_time")
            if not start_str:
                return False, "No start_time", None

            start_dt = datetime.fromisoformat(start_str)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc).astimezone()

            end_dt = (
                datetime.fromisoformat(event.get("end_time"))
                if event.get("end_time")
                else start_dt + timedelta(hours=1)
            )
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=start_dt.tzinfo)

            body = {
                "summary": event.get("title", "New Event"),
                "location": event.get("location", ""),
                "description": f"{event.get('description', '')}\n\n💡 {event.get('pre_prep', '')}".strip(),
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/New_York"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/New_York"},
            }

            created = service.events().insert(calendarId="primary", body=body).execute()
            return True, "✅ Added to Calendar!", created.get("id")

    except Exception as e:
        # Don’t fail silently — return message so UI can show it
        return False, f"Calendar add failed: {str(e)}", None

    # Fallback link mode (if service is None)
    title = urllib.parse.quote(str(event.get("title", "Event")))
    details = urllib.parse.quote(f"{event.get('description','')}\n\n💡 {event.get('pre_prep','')}".strip())
    location = urllib.parse.quote(str(event.get("location", "")))

    try:
        dt_start = datetime.fromisoformat(event.get("start_time"))
        dt_end = datetime.fromisoformat(event.get("end_time")) if event.get("end_time") else dt_start + timedelta(hours=1)
        dates = f"{dt_start.strftime('%Y%m%dT%H%M%S')}/{dt_end.strftime('%Y%m%dT%H%M%S')}"
    except Exception:
        return False, "https://calendar.google.com/", None

    link = (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={title}&dates={dates}&details={details}&location={location}"
    )
    return False, link, None

def delete_event(event_id: str, user_id: Optional[str] = None) -> Tuple[bool, str]:
    """Deletes an event from Google Calendar."""
    try:
        service = get_calendar_service(user_id=user_id)
        if not service:
            return False, "Calendar not connected."

        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return True, "🗑️ Deleted from Calendar."
    except Exception as e:
        return False, f"Delete failed: {str(e)}"
