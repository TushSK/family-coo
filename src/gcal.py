import os
import urllib.parse
from datetime import datetime, timedelta
import json
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Authenticates with Google (Cloud Priority + Local Fallback)."""
    creds = None
    
    # 1. CHECK CLOUD SECRETS
    if "token" in st.secrets and "google_token_json" in st.secrets["token"]:
        try:
            token_info = json.loads(st.secrets["token"]["google_token_json"])
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
        except Exception: pass

    # 2. CHECK LOCAL FILE
    if not creds:
        token_file = 'token.json'
        if os.path.exists(token_file):
            try:
                if os.path.getsize(token_file) > 0:
                    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
                else: os.remove(token_file)
            except: os.remove(token_file)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try: creds.refresh(Request())
                except: creds = None
            
            if not creds and os.path.exists('credentials.json'):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=8080)
                    with open(token_file, 'w') as token: token.write(creds.to_json())
                except Exception: return None

    if not creds: return None
    return build('calendar', 'v3', credentials=creds)

def list_upcoming_events():
    """Reads calendar with IDs."""
    try:
        service = get_calendar_service()
        if not service: return "Calendar Not Connected"
        
        now = datetime.utcnow()
        past_start = (now - timedelta(days=10)).isoformat() + 'Z'
        future_end = (now + timedelta(days=10)).isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary', timeMin=past_start, timeMax=future_end,
            singleEvents=True, orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        if not events: return "No events found."
        
        text = "CALENDAR DATA (With IDs):\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'Busy')
            ev_id = event.get('id')
            
            try:
                event_dt = datetime.fromisoformat(start)
                status = "[PAST]" if event_dt < datetime.now().astimezone() else "[UPCOMING]"
            except: status = "[EVENT]"
                
            text += f"- {status} ID:{ev_id} | {summary} at {start}\n"
            
        return text
    except Exception as e: return f"Read Error: {str(e)}"

def delete_event(event_id):
    """Deletes event. Treats '410 Gone' as Success."""
    try:
        service = get_calendar_service()
        if service:
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True, "✅ Deleted"
    except Exception as e:
        # If Google says "Deleted" or "Not Found", that is a SUCCESS for us.
        err_str = str(e).lower()
        if "deleted" in err_str or "not found" in err_str or "410" in err_str or "404" in err_str:
            return True, "✅ Already Deleted (Syncing...)"
        return False, f"Delete Failed: {str(e)}"

def add_event_to_calendar(event):
    """One-Click Add"""
    try:
        service = get_calendar_service()
        if service:
            start_dt = datetime.fromisoformat(event.get('start_time'))
            end_dt = datetime.fromisoformat(event.get('end_time')) if event.get('end_time') else start_dt + timedelta(hours=1)
            body = {
                'summary': event.get('title', 'New Event'),
                'location': event.get('location', ''),
                'description': f"{event.get('description', '')}\n\n💡 {event.get('pre_prep', '')}",
                'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/New_York'},
                'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/New_York'},
            }
            service.events().insert(calendarId='primary', body=body).execute()
            return True, "✅ Added to Calendar!"
    except: pass
    return False, create_calendar_link(event)

def create_calendar_link(event):
    title = urllib.parse.quote(event.get('title', 'Event'))
    location = urllib.parse.quote(event.get('location', ''))
    details = urllib.parse.quote(f"{event.get('description','')}\n\n💡 {event.get('pre_prep','')}")
    try:
        dt_start = datetime.fromisoformat(event.get('start_time'))
        dt_end = datetime.fromisoformat(event.get('end_time')) if event.get('end_time') else dt_start + timedelta(hours=1)
        dates = f"{dt_start.strftime('%Y%m%dT%H%M%S')}/{dt_end.strftime('%Y%m%dT%H%M%S')}"
    except: return "https://calendar.google.com/"
    return f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={dates}&details={details}&location={location}"