import google.generativeai as genai
import os
import json
import datetime
import time

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The 'Context-First' Brain.
    Prioritizes History/Memory for locations. 
    Asks MINIMAL questions only when necessary.
    """
    genai.configure(api_key=api_key)
    
    # 1. SETUP CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    history_context = ""
    if chat_history:
        # We provide the last 6 turns so it remembers "Judo is at 123 Main St" from 2 minutes ago
        formatted_history = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-6:]])
        history_context = f"PREVIOUS CONVERSATION:\n{formatted_history}\n"

    system_prompt = f"""
    You are the Family COO.
    CURRENT TIME: {current_time_str}.
    USER LOCATION: {current_location}.
    
    {history_context}
    
    CRITICAL RULES FOR LOCATION:
    1. **CHECK CONTEXT FIRST:** Before asking for a location, check the Chat History, Memory, and Image content. If the address is there, USE IT.
    2. **INTELLIGENT INFERENCE:** If user says "Home Depot" and you see a Home Depot address in the history/memory, schedule it there.
    3. **MINIMAL QUESTIONS:** If you MUST ask, keep it under 10 words. (e.g., "Which Home Depot location?" is better than "Could you please provide the address...").
    4. **HANDLE 'NEARBY':** If user says "nearby", select a generic place near {current_location}.
    
    OUTPUT FORMAT:
    Return a JSON object strictly delimited by |||JSON_START||| and |||JSON_END|||.
    
    SCENARIO A: Clarification needed (Location unknown).
    {{
        "type": "question",
        "text": "Which location?"
    }}
    
    SCENARIO B: Plan ready (Location found in context).
    {{
        "type": "plan",
        "text": "Scheduled at [Address Found].",
        "events": [
            {{
                "title": "Event Title",
                "start_time": "YYYY-MM-DDTHH:MM:00",
                "end_time": "YYYY-MM-DDTHH:MM:00",
                "location": "Address Found",
                "description": "Notes"
            }}
        ]
    }}
    """
    
    # 2. MODEL LADDER (Stable & Fast)
    model_ladder = [
        "gemini-1.5-flash-latest",      # Best balance of speed/context
        "gemini-flash-latest",
        "gemini-1.5-pro-latest"
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
            last_error = f"{model_name}: {str(e)}"
            continue

    return f"⚠️ System Error. Last debug: {last_error}"