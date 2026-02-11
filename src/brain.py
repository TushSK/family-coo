import google.generativeai as genai
import os
import json
import datetime
import time

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The Precision Brain.
    Uses ONLY models confirmed to exist on your server (Gemini 2.0 series).
    """
    genai.configure(api_key=api_key)
    
    # 1. SETUP CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    history_context = ""
    if chat_history:
        formatted_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-6:]])
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
    
    # 3. THE CONFIRMED MODEL LADDER
    # These match your Diagnostic Report exactly.
    # We prioritize "Lite" to avoid Quota (429) errors.
    model_ladder = [
        "gemini-2.0-flash-lite-preview-02-05", # FASTEST, usually open quota
        "gemini-2.0-flash",                  # Standard, often busy
        "gemini-2.0-flash-001"               # Backup version
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
            error_str = str(e)
            last_error = f"{model_name}: {error_str}"
            
            # If 429 (Busy) or 404 (Not Found), try next model
            time.sleep(1) 
            continue

    return f"⚠️ ALL MODELS FAILED. Debug Info: {last_error}"