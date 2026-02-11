import google.generativeai as genai
import os
import json
import datetime
import time
import re

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The 'Unstoppable' Brain.
    Prioritizes LITE models and parses error messages to wait exactly as long as needed.
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
    
    # 2. THE STRATEGIC MODEL LADDER
    # We use specific versions proven to exist in your logs.
    model_ladder = [
        "gemini-2.0-flash-lite-001",    # 1. Lite = Less Traffic (Best chance)
        "gemini-2.0-flash",             # 2. Standard (Often busy)
        "gemini-1.5-pro-latest",        # 3. Pro (Different quota bucket)
        "gemini-1.5-flash-latest"       # 4. Old Flash (Backup)
    ]
    
    last_error = ""
    
    for model_name in model_ladder:
        try:
            # print(f"Attempting {model_name}...") 
            model = genai.GenerativeModel(model_name)
            
            if image_context:
                response = model.generate_content([system_prompt, image_context])
            else:
                response = model.generate_content(system_prompt)
            return response.text
            
        except Exception as e:
            error_str = str(e)
            last_error = f"{model_name}: {error_str}"
            
            # 3. SMART WAIT LOGIC
            if "429" in error_str or "Quota" in error_str:
                # Try to find "retry in X seconds" in the error message
                match = re.search(r"retry in (\d+)", error_str)
                wait_time = float(match.group(1)) + 2 if match else 5
                
                # If wait is too long (> 20s), skip to next model instead of waiting
                if wait_time > 20:
                    time.sleep(1)
                    continue 
                else:
                    time.sleep(wait_time)
                    # Retry the SAME model one more time
                    try:
                        if image_context: response = model.generate_content([system_prompt, image_context])
                        else: response = model.generate_content(system_prompt)
                        return response.text
                    except:
                        continue # If it fails twice, move on

    return f"⚠️ SYSTEM OVERLOAD. All models are currently busy. Please wait 1 minute. (Debug: {last_error})"