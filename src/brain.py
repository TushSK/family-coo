import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
import json
import datetime

def get_coo_response(api_key, user_text, memory_context, calendar_agenda, current_location, image=None):
    genai.configure(api_key=api_key)
    
    # 1. STRICT MODEL LIST (Only models you definitely have)
    model_candidates = [
        'gemini-2.0-flash',      # Smartest available to you
        'gemini-1.5-flash',      # Most stable backup
        'gemini-flash-latest'    # Generic fallback
    ]
    
    today = datetime.datetime.now().strftime("%A, %B %d, %Y")
    
    # 2. CONSTRUCT KNOWLEDGE BASE
    memory_text = "No prior learning."
    if memory_context:
        # Convert list of dicts to string
        memory_text = "\n".join([f"- {m['feedback']}" for m in memory_context])

    system_instruction = f"""
    ### ROLE: FAMILY COO (INTELLIGENT MODE) ###
    Current Date: {today}
    Location Context: {current_location}
    
    ### DATA FEED:
    1. **USER CALENDAR:**
    {calendar_agenda}
    
    2. **USER MEMORY:**
    {memory_text}
    
    ### INTELLIGENCE RULES:
    1. **GENERAL SEARCH:** If the user asks for a type of place (e.g. "Buddha Temple"), identify the highest-rated specific option in {current_location}.
    2. **CALENDAR CHECK:** Scan the calendar data. If the user asks for a "good time", find a gap (White Space) in the schedule and suggest it.
       - Example: If Saturday 9-12 is free, suggest "Saturday Morning".
    3. **OUTPUT:** Be decisive. Don't ask questions, give a plan.
    
    ### OUTPUT FORMAT:
    
    📍 **LOCATION:** [Specific Name & Address]
    
    🕰️ **SUGGESTED TIME:** [Date @ Time]
    *(Reason: Your calendar is clear, and this is open)*
    
    💡 **STRATEGY:** [1 sentence reasoning]
    
    🛡️ **PREP:**
    * [Action item]
    
    📝 **SCHEDULE:**
    1. **[Time]**: [Activity]
    2. **[Time]**: [Activity]
    
    PART 2: JSON DATA BLOCK
    |||JSON_START|||
    {{
      "title": "[Activity Name]",
      "start_time": "YYYY-MM-DDTHH:MM:SS",
      "end_time": "YYYY-MM-DDTHH:MM:SS",
      "location": "[Address]",
      "description": "Strategy: [Strategy]",
      "alert_minutes": 60 
    }}
    |||JSON_END|||
    """

    prompt_parts = [system_instruction, "\nUSER REQUEST: " + user_text]
    if image: prompt_parts.append(image)

    # 3. EXECUTION LOOP (With Detailed Error Log)
    error_log = []
    
    for model_name in model_candidates:
        try:
            # Clean name just in case
            clean_name = model_name.replace("models/", "")
            model = genai.GenerativeModel(clean_name)
            response = model.generate_content(prompt_parts)
            return response.text
        except Exception as e:
            error_log.append(f"❌ {clean_name}: {str(e)}")
            continue
            
    # If we get here, show the user EXACTLY why every model failed
    return f"⚠️ **Brain Freeze:** All models failed.\n\nDebug Log:\n" + "\n".join(error_log)