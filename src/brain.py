import google.generativeai as genai
import os
import json
import datetime
import time

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The Indestructible Brain.
    Features: Conversational Memory + Robust Error Handling + Automatic Retries.
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
    1. **CLARIFY IF NEEDED:** If the user asks for a specific activity (e.g., "Plan Judo") but does NOT specify a location, and you don't know it from Memory/History, ask a clarification question.
    2. **HANDLE 'NEARBY':** If the user says "Nearby", use the USER LOCATION ({current_location}) to find a generic placeholder.
    3. **OUTPUT JSON:** You must return a JSON object strictly delimited by |||JSON_START||| and |||JSON_END|||.
    
    SCENARIO A: You need more info.
    {{
        "type": "question",
        "text": "I can help with that. Where is the Judo class located?"
    }}
    
    SCENARIO B: You have enough info to plan.
    {{
        "type": "plan",
        "text": "I've scheduled Judo for 5:30 PM.",
        "events": [
            {{
                "title": "Judo Class",
                "start_time": "YYYY-MM-DDTHH:MM:00",
                "end_time": "YYYY-MM-DDTHH:MM:00",
                "location": "Address",
                "description": "Notes"
            }}
        ]
    }}
    """
    
    # 3. THE MODEL LADDER (Safety Net)
    # We mix new models (best quality) with old models (best availability)
    model_ladder = [
        "gemini-1.5-flash",          # Standard
        "gemini-2.0-flash",          # Newest
        "gemini-1.5-pro",            # High Intelligence
        "gemini-pro"                 # Old Reliable (Fallback)
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
            
            # If it's a Quota error (429), wait a bit and try the next one
            if "429" in error_str or "Quota" in error_str:
                time.sleep(2)
                continue
            # If it's a 404 (Not Found), just skip immediately
            elif "404" in error_str:
                continue
            else:
                # Unknown error? Try next anyway.
                continue

    return f"⚠️ ALL MODELS FAILED. Last error: {last_error}"