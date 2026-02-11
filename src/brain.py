import google.generativeai as genai
import os
import json
import datetime
import time
import re

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The 'Stubborn' Brain.
    It uses ONLY the models confirmed to exist (Gemini 2.0).
    If it hits a rate limit, it WAITS the full duration required.
    """
    genai.configure(api_key=api_key)
    
    # 1. SETUP CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    history_context = ""
    if chat_history:
        formatted_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-4:]])
        history_context = f"PREVIOUS CONVERSATION:\n{formatted_history}\n"

    system_prompt = f"""
    You are the Family COO.
    CURRENT TIME: {current_time_str}.
    USER LOCATION: {current_location}.
    
    {history_context}
    
    RULES:
    1. **CLARIFY:** If location is missing, ask where.
    2. **NEARBY:** If "nearby" is used, find a placeholder near {current_location}.
    3. **OUTPUT JSON:** Return a JSON object strictly delimited by |||JSON_START||| and |||JSON_END|||.
    
    SCENARIO A: Clarification needed.
    {{
        "type": "question",
        "text": "Where should I look for this?"
    }}
    
    SCENARIO B: Plan ready.
    {{
        "type": "plan",
        "text": "I've scheduled it.",
        "events": [
            {{
                "title": "Event Title",
                "start_time": "YYYY-MM-DDTHH:MM:00",
                "end_time": "YYYY-MM-DDTHH:MM:00",
                "location": "Address",
                "description": "Notes"
            }}
        ]
    }}
    """
    
    # 2. THE CONFIRMED MODEL LIST
    # We ONLY use the 2.0 models because 1.5 is throwing 404s.
    # We start with "Lite" because it's faster.
    model_name = "gemini-2.0-flash-lite-preview-02-05" 
    
    # Fallback if Lite fails
    backup_model_name = "gemini-2.0-flash"

    models_to_try = [model_name, backup_model_name]
    
    for model_target in models_to_try:
        model = genai.GenerativeModel(model_target)
        
        # Retry Loop: Try up to 3 times per model
        attempts = 0
        while attempts < 3:
            try:
                if image_context:
                    response = model.generate_content([system_prompt, image_context])
                else:
                    response = model.generate_content(system_prompt)
                return response.text
                
            except Exception as e:
                error_str = str(e)
                
                # CHECK FOR QUOTA ERROR (429)
                if "429" in error_str or "Quota" in error_str:
                    # Find the exact wait time in the error message
                    # Example: "retry in 39.23 seconds"
                    match = re.search(r"retry in (\d+)", error_str)
                    
                    if match:
                        wait_seconds = int(match.group(1)) + 2 # Add 2s buffer
                    else:
                        wait_seconds = 10 # Default wait if parsing fails
                    
                    # STUBBORN WAIT: actually sleep the full time
                    time.sleep(wait_seconds)
                    attempts += 1
                    continue # Loop back and try again!
                
                # If it's a 404 (Not Found), break loop and try next model
                elif "404" in error_str:
                    break
                
                else:
                    # Unknown error? Wait 2s and retry
                    time.sleep(2)
                    attempts += 1

    return "⚠️ SYSTEM BUSY: Google is strictly rate-limiting right now. Please wait 2 minutes and try again."