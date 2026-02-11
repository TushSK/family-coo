import google.generativeai as genai
import os
import json
import datetime
import time

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The 'Stable' Brain.
    Uses 'latest' aliases to find the high-speed, high-quota models.
    """
    genai.configure(api_key=api_key)
    
    # 1. SETUP CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    history_context = ""
    if chat_history:
        formatted_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-6:]])
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
    
    # 2. THE STABLE MODEL LADDER
    # We use 'latest' aliases which usually map to the most stable, high-quota endpoints.
    model_ladder = [
        "gemini-1.5-flash-latest",      # High Speed, High Quota
        "gemini-flash-latest",          # Backup Alias
        "gemini-1.5-pro-latest",        # High Intelligence
        "gemini-2.0-flash-lite-preview-02-05" # Fallback (New but low quota)
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
            # If a model fails, we just try the next one instantly.
            last_error = f"{model_name}: {str(e)}"
            continue

    return f"⚠️ SYSTEM ERROR: Could not connect to Google AI. Last error: {last_error}"