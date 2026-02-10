import google.generativeai as genai
import os
import json
import datetime
import time

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The 'Conversational' Brain.
    Can now return a PLAN (List of events) OR a QUESTION (Clarification).
    """
    genai.configure(api_key=api_key)
    
    # 1. TIME & CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # 2. HISTORY FORMATTING
    history_context = ""
    if chat_history:
        formatted_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-6:]])
        history_context = f"PREVIOUS CONVERSATION:\n{formatted_history}\n"

    # 3. SYSTEM INSTRUCTION (The Major Upgrade)
    system_prompt = f"""
    You are the Family COO.
    CURRENT TIME: {current_time_str}.
    USER LOCATION: {current_location}.
    
    {history_context}
    
    RULES:
    1. **CLARIFY IF NEEDED:** If the user asks for a specific activity (e.g., "Plan Judo") but does NOT specify a location, and you don't know it from Memory/History, DO NOT GUESS. Instead, ask a clarification question.
    2. **HANDLE 'NEARBY':** If the user says "Nearby" or "Close to me", use the USER LOCATION ({current_location}) to find a generic placeholder (e.g., "Judo Center near {current_location}").
    3. **SIMPLICITY:** Keep the text summary BRIEF and conversational. Avoid corporate jargon.
    
    OUTPUT FORMAT:
    You must return a JSON object strictly delimited by |||JSON_START||| and |||JSON_END|||.
    
    SCENARIO A: You need more info.
    {{
        "type": "question",
        "text": "I can help with that. Where is the Judo class located, or should I look for one nearby?"
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
    
    # 4. ROBUST MODEL LADDER
    model_ladder = [
        "gemini-2.0-flash-lite-preview-02-05", # Fast & conversational
        "gemini-2.0-flash",
        "gemini-1.5-flash"
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

    return f"⚠️ Brain Freeze: {last_error}"