import os
import urllib.parse
from datetime import datetime, timedelta
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Authenticates with Google Calendar API locally. Handles corrupt tokens."""
    creds = None
    token_file = 'token.json'
    
    # 1. Try to load existing token
    if os.path.exists(token_file):
        try:
            # Check if file is empty first
            if os.path.getsize(token_file) > 0:
                creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            else:
                print("⚠️ Token file is empty. Deleting it.")
                os.remove(token_file)
        except Exception as e:
            print(f"⚠️ Corrupt token file ({e}). Deleting it.")
            os.remove(token_file)

    # 2. If no valid credentials, log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️ Token refresh failed: {e}. Deleting token.")
                if os.path.exists(token_file): os.remove(token_file)
                creds = None
        
        # If still no creds, start fresh login flow
        if not creds:
            if os.path.exists('credentials.json'):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                    # Save the new token
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    print(f"❌ Auth Flow Error: {e}")
                    return None
            else:
                print("❌ Missing 'credentials.json'")
                return None
                
    return build('calendar', 'v3', credentials=creds)

def list_upcoming_events():
    """
    READS the next 10 events.
    """
    try:
        service = get_calendar_service()
        if not service: 
            return "Calendar Access: Not connected (Check terminal for Auth errors)."
        
        # Get start of today in UTC format
        now = datetime.utcnow().isoformat() + 'Z' 
        
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=10, singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events: return "No upcoming events found in Google Calendar."

        calendar_text = "CONFIRMED CALENDAR EVENTS:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'Busy')
            calendar_text += f"- {summary} at {start}\n"
        
        return calendar_text

    except Exception as e:
        print(f"❌ Read Error: {e}")
        return f"Calendar Read Error: {str(e)}"

# --- LINK HELPERS ---
def create_calendar_link(event):
    title = urllib.parse.quote(event.get('title', 'New Event'))
    location = urllib.parse.quote(event.get('location', ''))
    desc = event.get('description', '')
    if event.get('pre_prep'): desc += f"\n\n💡 PRE-PREP: {event.get('pre_prep')}"
    details = urllib.parse.quote(desc)
    
    start_str = event.get('start_time')
    if not start_str: return "https://calendar.google.com/"
    
    try:
        dt_start = datetime.fromisoformat(start_str)
        if event.get('end_time'): dt_end = datetime.fromisoformat(event.get('end_time'))
        else: dt_end = dt_start + timedelta(hours=1)
        fmt = "%Y%m%dT%H%M%S"
        dates = f"{dt_start.strftime(fmt)}/{dt_end.strftime(fmt)}"
    except: return "https://calendar.google.com/"
    
    base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    return f"{base}&text={title}&dates={dates}&details={details}&location={location}"

def add_event_to_calendar(event):
    try:
        service = get_calendar_service()
        if service:
            start_dt = datetime.fromisoformat(event.get('start_time'))
            end_dt = datetime.fromisoformat(event.get('end_time')) if event.get('end_time') else start_dt + timedelta(hours=1)
            
            body = {
                'summary': event.get('title'),
                'location': event.get('location', ''),
                'description': f"{event.get('description', '')}\n\n💡 {event.get('pre_prep', '')}",
                'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/New_York'},
                'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/New_York'},
            }
            service.events().insert(calendarId='primary', body=body).execute()
            return True, "✅ Added to Calendar!"
    except Exception as e:
        print(f"Add Error: {e}")
    
    # Fallback to link if API fails
    return False, create_calendar_link(event)