import google.generativeai as genai
import os
import json
import datetime

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None):
    """
    Diagnostic Brain: If it crashes, it tells us exactly what models are available.
    """
    genai.configure(api_key=api_key)
    
    # 1. TIME & CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    system_prompt = f"""
    You are the Family COO.
    CURRENT TIME: {current_time_str}.
    LOCATION: {current_location}.
    
    TASK:
    Plan the following request: "{user_request}"
    Context: {json.dumps(memory)}
    Calendar: {calendar_data}
    
    OUTPUT:
    Text summary followed by a JSON list of events strictly delimited by |||JSON_START||| and |||JSON_END|||.
    Example JSON:
    [
        {{ "title": "Task", "start_time": "2024-01-01T12:00:00", "location": "Home" }}
    ]
    """
    
    # 2. ATTEMPT GENERATION (With Fallbacks)
    # We try the standard name first.
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        if image_context:
            response = model.generate_content([system_prompt, image_context])
        else:
            response = model.generate_content(system_prompt)
        return response.text
        
    except Exception as e_main:
        # 3. DIAGNOSTIC MODE (If the above fails)
        error_msg = str(e_main)
        
        # Let's ask the server: "Okay, what models DO you have?"
        try:
            available_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            
            debug_report = f"\n\n🕵️ DIAGNOSTIC REPORT:\nThe server cannot find 'gemini-1.5-flash', but it CAN see these models:\n{available_models}"
            
        except Exception as e_list:
            debug_report = f"\n\n🕵️ DIAGNOSTIC REPORT:\nCould not even list models. API Key might be invalid. Error: {e_list}"
            
        return f"⚠️ BRAIN ERROR: {error_msg} {debug_report}"