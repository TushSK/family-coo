import google.generativeai as genai
import os
import json
import datetime
import time

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The 'Smart Switcher' Brain with CONVERSATIONAL MEMORY.
    """
    genai.configure(api_key=api_key)
    
    # 1. TIME & CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # 2. FORMAT HISTORY (The New Part)
    # We turn the list of past Q&A into a script for the AI to read.
    history_context = ""
    if chat_history:
        formatted_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-6:]]) # Keep last 6 turns
        history_context = f"PREVIOUS CONVERSATION (Use this for context):\n{formatted_history}\n"

    # 3. SYSTEM INSTRUCTION
    system_prompt = f"""
    You are the Family COO. 
    CURRENT TIME: {current_time_str}. 
    USER LOCATION: {current_location}.
    
    {history_context}
    
    RULES:
    - No time travel (do not schedule in the past).
    - Handle multiple tasks by breaking them into a list.
    - If the user request is a FOLLOW-UP (e.g., "Change that to 6pm"), update the previous plan accordingly.
    
    INPUT:
    - Current Request: "{user_request}"
    - Learned Memory: {json.dumps(memory)}
    - Calendar Constraints: {calendar_data}
    
    OUTPUT FORMAT:
    Provide a text summary, followed by a JSON block delimited by |||JSON_START||| and |||JSON_END|||.
    The JSON must be a LIST of objects. If the plan is cancelled/cleared, return an empty list [].
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
    
    # 4. ROBUST MODEL LADDER
    model_ladder = [
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite-preview-02-05", 
        "gemini-2.0-flash",
        "gemini-2.0-flash-001"
    ]
    
    last_error = ""
    
    for model_name in model_ladder:
        try:
            model = genai.GenerativeModel(model_name)
            
            if image_context:
                response = model.generate_content([system_prompt, image_context])
            else:
                response = model.generate_content(system_prompt)
                
            return response.text
            
        except Exception as e:
            last_error = f"Model {model_name} failed: {str(e)}"
            time.sleep(1)
            continue

    return f"⚠️ Brain Freeze: All backup models failed. Last error: {last_error}"