import google.generativeai as genai
import os
import json
import datetime
import time
import random

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The 'Patient' Brain.
    Handles '429 Quota' errors by switching models and waiting intelligently.
    """
    genai.configure(api_key=api_key)
    
    # 1. SETUP CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    history_context = ""
    if chat_history:
        # Keep last 4 turns to save tokens
        formatted_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-4:]])
        history_context = f"PREVIOUS CONVERSATION:\n{formatted_history}\n"

    # 2. SYSTEM PROMPT
    system_prompt = f"""
    You are the Family COO.
    CURRENT TIME: {current_time_str}.
    USER LOCATION: {current_location}.
    
    {history_context}
    
    RULES:
    1. **CLARIFY:** If the user asks for an activity without a location, ask where.
    2. **NEARBY:** If user says "nearby", find a placeholder near {current_location}.
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
    
    # 3. ROBUST MODEL LADDER
    # We prioritize the "Lite" model because it has a separate quota bucket.
    model_ladder = [
        "gemini-2.0-flash-lite-preview-02-05", # First choice: Fast & Free
        "gemini-2.0-flash",                  # Second choice: Standard
        "gemini-1.5-pro",                    # Third choice: Stable Backup
    ]
    
    last_error = ""
    
    for i, model_name in enumerate(model_ladder):
        try:
            model = genai.GenerativeModel(model_name)
            
            # If this is a RETRY (i > 0), wait a few seconds to let the API cool down
            if i > 0:
                time.sleep(4) 
                
            if image_context:
                response = model.generate_content([system_prompt, image_context])
            else:
                response = model.generate_content(system_prompt)
            return response.text
            
        except Exception as e:
            error_str = str(e)
            last_error = f"{model_name}: {error_str}"
            
            # If 429 (Busy), we MUST wait longer.
            if "429" in error_str or "Quota" in error_str:
                # Exponential backoff: Wait 5s, then 10s...
                wait_time = (i + 1) * 5
                time.sleep(wait_time)
                continue
            elif "404" in error_str:
                # Model missing? Skip instantly.
                continue
            else:
                continue

    return f"⚠️ ALL MODELS BUSY. Please wait 1 minute and try again. (Last error: {last_error})"