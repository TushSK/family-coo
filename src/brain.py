import google.generativeai as genai
import os
import json
import datetime

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None):
    """
    The Core AI Logic.
    Now features ROBUST MODEL FALLBACK to prevent 404/403 errors.
    """
    genai.configure(api_key=api_key)
    
    # 1. TIME AWARENESS
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # 2. SYSTEM INSTRUCTION
    system_prompt = f"""
    You are the Family COO (Chief Operating Officer). Your goal is to execute family logistics efficiently.
    
    CRITICAL OPERATIONAL RULES:
    1. CURRENT TIME: It is currently {current_time_str}.
    2. NO TIME TRAVEL: DO NOT suggest schedule times that are in the past relative to {current_time_str}.
    3. MULTI-TASKING: The user often has multiple goals. Break them into separate calendar events.
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
        }}
    ]
    """
    
    # 3. ROBUST MODEL SELECTION (The Fix)
    # We try models in order. If one fails (404/403), we automatically switch to the next.
    model_options = [
        "gemini-2.0-flash",        # Newest & Fastest
        "gemini-1.5-flash",        # Standard
        "gemini-1.5-flash-latest", # Alternate Alias
        "gemini-pro"               # Old Reliable (Fallback)
    ]
    
    last_error = ""
    
    for model_name in model_options:
        try:
            model = genai.GenerativeModel(model_name)
            if image_context:
                response = model.generate_content([system_prompt, image_context])
            else:
                response = model.generate_content(system_prompt)
            
            # If we get here, it worked! Return immediately.
            return response.text
            
        except Exception as e:
            # If it failed, log error and loop to the next model
            last_error = f"{model_name}: {str(e)}"
            continue 

    # If ALL models fail, return the error log
    return f"⚠️ Brain Freeze: All models failed. Debug Log: {last_error}"