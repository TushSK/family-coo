import streamlit as st
import datetime
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_calendar_service():
    """Authenticates using Streamlit Secrets (Cloud Compatible)."""
    creds = None
    
    # 1. Try loading from Cloud Secrets first
    if "google_token" in st.secrets:
        token_info = json.loads(st.secrets["google_token"])
        creds = Credentials.from_authorized_user_info(token_info)
        
    # 2. Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            return None # Auth failed

    if not creds or not creds.valid:
        return None

    return build('calendar', 'v3', credentials=creds)

def list_upcoming_events(days=3):
    service = get_calendar_service()
    if not service: return "Calendar Disconnected (Check Secrets)"

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=10, singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    if not events: return "Calendar is clear."
        
    agenda_text = ""
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'Busy')
        agenda_text += f"- {start}: {summary}\n"
    return agenda_text

def add_event_to_calendar(event_data):
    service = get_calendar_service()
    if not service: return "AUTH_ERROR"

    event = {
        'summary': event_data.get('title', 'Family Event'),
        'location': event_data.get('location', ''),
        'description': event_data.get('description', ''),
        'start': {'dateTime': event_data.get('start_time'), 'timeZone': 'America/New_York'},
        'end': {'dateTime': event_data.get('end_time'), 'timeZone': 'America/New_York'},
        'reminders': {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 60}]},
    }
    try:
        event = service.events().insert(calendarId='primary', body=event).execute()
        return event.get('htmlLink')
    except Exception as e:
        return str(e)