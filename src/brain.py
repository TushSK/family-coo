import google.generativeai as genai
import os
import json
import datetime
import time

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None):
    """
    The 'Smart Switcher' Brain. 
    It loops through a list of available models. 
    If one gives a 429 (Quota/Busy) error, it instantly tries the next one.
    """
    genai.configure(api_key=api_key)
    
    # 1. TIME AWARENESS
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # 2. SYSTEM INSTRUCTION
    system_prompt = f"""
    You are the Family COO. 
    CURRENT TIME: {current_time_str}. 
    USER LOCATION: {current_location}.
    
    RULES:
    - No time travel (do not schedule in the past).
    - Handle multiple tasks by breaking them into a list.
    
    INPUT:
    - Request: "{user_request}"
    - Memory: {json.dumps(memory)}
    - Calendar: {calendar_data}
    
    OUTPUT FORMAT:
    Provide a text summary, followed by a JSON block delimited by |||JSON_START||| and |||JSON_END|||.
    The JSON must be a LIST of objects:
    [
        {{
            "title": "Event Name",
            "start_time": "YYYY-MM-DDTHH:MM:00",
            "end_time": "YYYY-MM-DDTHH:MM:00",
            "location": "Address",
            "description": "Notes"
        }}
    ]
    """
    
    # 3. THE MODEL LADDER (Based on your server's available list)
    # We try them in this specific order to dodge 429 errors.
    model_ladder = [
        "gemini-2.5-flash",                  # 1. Try the newest (Usually has fresh quota)
        "gemini-2.0-flash-lite-preview-02-05", # 2. Try the "Lite" version (Very fast, less traffic)
        "gemini-2.0-flash",                  # 3. Standard 2.0 (Busy, but worth a shot)
        "gemini-2.0-flash-001"               # 4. Alternative version
    ]
    
    last_error = ""
    
    for model_name in model_ladder:
        try:
            # print(f"Trying model: {model_name}...") # Debug log (invisible to user)
            model = genai.GenerativeModel(model_name)
            
            if image_context:
                response = model.generate_content([system_prompt, image_context])
            else:
                response = model.generate_content(system_prompt)
                
            # If we reach here, it worked! Return immediately.
            return response.text
            
        except Exception as e:
            # Capture error and loop to the next model
            last_error = f"Model {model_name} failed: {str(e)}"
            time.sleep(1) # Tiny pause before retrying
            continue

    # If ALL models in the ladder fail
    return f"⚠️ Brain Freeze: All backup models failed. Last error: {last_error}"