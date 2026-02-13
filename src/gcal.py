import os
import urllib.parse
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def get_calendar_service():
    """Authenticates with Google Calendar and auto-heals token issues."""
    creds = None
    token_file = "token.json"

    if os.path.exists(token_file):
        try:
            if os.path.getsize(token_file) > 0:
                creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            else:
                _safe_remove(token_file)
        except Exception:
            _safe_remove(token_file)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                _safe_remove(token_file)
                creds = None

        if not creds:
            if not os.path.exists("credentials.json"):
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_file, "w", encoding="utf-8") as token:
                    token.write(creds.to_json())
            except Exception:
                return None

    try:
        return build("calendar", "v3", credentials=creds)
    except Exception:
        return None


def format_friendly_date(iso_str: str) -> str:
    """Converts ISO string to 'Fri, Feb 13 @ 5:00 PM' or 'Fri, Feb 13 (All Day)'."""
    try:
        if not iso_str:
            return ""
        if "T" in iso_str:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.strftime("%a, %b %d @ %I:%M %p")
        dt = datetime.strptime(iso_str, "%Y-%m-%d")
        return dt.strftime("%a, %b %d (All Day)")
    except Exception:
        return iso_str


def get_upcoming_events_list(days: int = 7):
    """
    Returns list of upcoming events (next N days).
    Returns None if calendar not connected.
    """
    try:
        service = get_calendar_service()
        if not service:
            return None

        now_dt = datetime.utcnow()
        max_dt = now_dt + timedelta(days=days)

        time_min = now_dt.isoformat() + "Z"
        time_max = max_dt.isoformat() + "Z"

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


def add_event_to_calendar(event: dict):
    """
    One-click add with link fallback.

    Returns:
      (True, "✅ Added to Calendar!", event_id)
      (False, link_url, None)
    """
    # API-first
    try:
        service = get_calendar_service()
        if service:
            start_str = event.get("start_time")
            if not start_str:
                return False, "No start_time", None

            start_dt = datetime.fromisoformat(start_str)
            end_dt = (
                datetime.fromisoformat(event.get("end_time"))
                if event.get("end_time")
                else start_dt + timedelta(hours=1)
            )

            body = {
                "summary": event.get("title", "New Event"),
                "location": event.get("location", ""),
                "description": f"{event.get('description', '')}\n\n💡 {event.get('pre_prep', '')}".strip(),
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/New_York"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/New_York"},
            }

            created = service.events().insert(calendarId="primary", body=body).execute()
            return True, "✅ Added to Calendar!", created.get("id")
    except Exception:
        pass

    # Fallback link mode
    title = urllib.parse.quote(event.get("title", "Event"))
    details = urllib.parse.quote(f"{event.get('description','')}\n\n💡 {event.get('pre_prep','')}".strip())
    location = urllib.parse.quote(event.get("location", ""))

    try:
        dt_start = datetime.fromisoformat(event.get("start_time"))
        dt_end = (
            datetime.fromisoformat(event.get("end_time"))
            if event.get("end_time")
            else dt_start + timedelta(hours=1)
        )
        dates = f"{dt_start.strftime('%Y%m%dT%H%M%S')}/{dt_end.strftime('%Y%m%dT%H%M%S')}"
    except Exception:
        return False, "https://calendar.google.com/", None

    link = (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={title}&dates={dates}&details={details}&location={location}"
    )
    return False, link, None


def delete_event(event_id: str):
    """
    Deletes an event from Google Calendar.
    Returns (True, message) or (False, message)
    """
    try:
        service = get_calendar_service()
        if not service:
            return False, "Calendar not connected (Link Mode)."

        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return True, "🗑️ Deleted from Calendar."
    except Exception as e:
        return False, f"Delete failed: {str(e)}"
