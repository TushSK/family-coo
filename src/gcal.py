import os
import urllib.parse
from datetime import datetime, timedelta
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# SCOPE: We request permission to Read AND Write events
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """
    Authenticates with Google.
    Auto-fixes corrupt tokens to ensure 'One-Click' adding works.
    """
    creds = None
    token_file = 'token.json'
    
    # 1. Try to load existing login
    if os.path.exists(token_file):
        try:
            if os.path.getsize(token_file) > 0:
                creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            else:
                print("⚠️ Token empty. Deleting.")
                os.remove(token_file)
        except:
            print("⚠️ Token corrupt. Deleting.")
            os.remove(token_file)

    # 2. Login if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                if os.path.exists(token_file): os.remove(token_file)
                creds = None
        
        if not creds:
            if os.path.exists('credentials.json'):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    print(f"❌ Login Failed: {e}")
                    return None
            else:
                return None
                
    return build('calendar', 'v3', credentials=creds)

def add_event_to_calendar(event):
    """
    The 'One-Click' Function.
    Tries to insert directly via API.
    """
    try:
        service = get_calendar_service()
        if service:
            # Parse Dates
            start_str = event.get('start_time')
            if not start_str: return False, "No start time"
            
            start_dt = datetime.fromisoformat(start_str)
            if event.get('end_time'):
                end_dt = datetime.fromisoformat(event.get('end_time'))
            else:
                end_dt = start_dt + timedelta(hours=1)
            
            # Construct Event
            body = {
                'summary': event.get('title', 'New Event'),
                'location': event.get('location', ''),
                'description': f"{event.get('description', '')}\n\n💡 {event.get('pre_prep', '')}",
                'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/New_York'},
                'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/New_York'},
            }
            
            # INSERT (The Magic Step)
            service.events().insert(calendarId='primary', body=body).execute()
            return True, "✅ Successfully added to Google Calendar!"
            
    except Exception as e:
        print(f"API Error: {e}")
        # If API fails, fall through to link generator
    
    # FALLBACK LINK (If API failed)
    return False, create_calendar_link(event)

def list_upcoming_events():
    """Reads calendar for conflict detection"""
    try:
        service = get_calendar_service()
        if not service: return "Calendar Not Connected"
        
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=10, singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        if not events: return "No upcoming events."
        
        text = "YOUR CALENDAR:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            text += f"- {event.get('summary', 'Busy')} at {start}\n"
        return text
    except Exception as e:
        return f"Read Error: {str(e)}"

def create_calendar_link(event):
    """Fallback generator"""
    title = urllib.parse.quote(event.get('title', 'Event'))
    location = urllib.parse.quote(event.get('location', ''))
    details = urllib.parse.quote(f"{event.get('description','')}\n\n💡 {event.get('pre_prep','')}")
    try:
        dt_start = datetime.fromisoformat(event.get('start_time'))
        dt_end = datetime.fromisoformat(event.get('end_time')) if event.get('end_time') else dt_start + timedelta(hours=1)
        dates = f"{dt_start.strftime('%Y%m%dT%H%M%S')}/{dt_end.strftime('%Y%m%dT%H%M%S')}"
    except: return "https://calendar.google.com/"
    
    return f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={dates}&details={details}&location={location}"