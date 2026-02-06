import google.generativeai as genai
import os
import json
import datetime

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None):
    """
    Standard AI Logic using the latest library.
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
    
    # 3. GENERATE (Using the standard model)
    # The library update fixes the 404 error
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    try:
        if image_context:
            response = model.generate_content([system_prompt, image_context])
        else:
            response = model.generate_content(system_prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Brain Error: {str(e)}"