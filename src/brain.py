import google.generativeai as genai
import os
import json
import datetime

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None):
    """
    The Core AI Logic. Now Time-Aware and supports Multiple Events.
    """
    genai.configure(api_key=api_key)
    
    # 1. TIME AWARENESS (Crucial Fix)
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # 2. SYSTEM INSTRUCTION
    # We teach it to be a strict Scheduler that handles multiple tasks.
    system_prompt = f"""
    You are the Family COO (Chief Operating Officer). Your goal is to execute family logistics efficiently.
    
    CRITICAL OPERATIONAL RULES:
    1. CURRENT TIME: It is currently {current_time_str}.
    2. NO TIME TRAVEL: DO NOT suggest schedule times that are in the past relative to {current_time_str}. If the user asks for "today" but the day is mostly over, plan for "right now" or move non-urgent tasks to tomorrow.
    3. MULTI-TASKING: The user often has multiple goals (e.g., "Shop then Cook"). Break them into separate calendar events.
    4. LOCATION: User is currently in {current_location}.
    
    INPUT CONTEXT:
    - User Request: "{user_request}"
    - Learned Preferences (Memory): {json.dumps(memory)}
    - Existing Calendar Constraints: {calendar_data}
    
    OUTPUT FORMAT:
    You must provide TWO parts in your response:
    
    PART 1: The Strategic Plan (Text)
    - A clear, bulleted executive summary of the plan.
    - Explain logic (e.g., "I scheduled Quest first because they close at 5 PM").
    
    PART 2: The Data Payload (JSON)
    - Strictly strictly delimit this block with |||JSON_START||| and |||JSON_END|||.
    - It must be a JSON LIST of objects (even if just one event).
    - Format:
    [
        {{
            "title": "Event Title",
            "start_time": "YYYY-MM-DDTHH:MM:00",
            "end_time": "YYYY-MM-DDTHH:MM:00",
            "location": "Address or Name",
            "description": "Notes for the calendar",
            "reminders": {{ "useDefault": false, "overrides": [ {{ "method": "popup", "minutes": 30 }} ] }}
        }},
        ... (more events)
    ]
    """
    
    # 3. MODEL SETUP
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 4. GENERATE
    try:
        if image_context:
            response = model.generate_content([system_prompt, image_context])
        else:
            response = model.generate_content(system_prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Brain Freeze: {str(e)}"