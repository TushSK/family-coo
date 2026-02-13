import os
import json
import datetime
import base64
import re
import pytz # NEW IMPORT
from groq import Groq

def encode_image(image):
    import io
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_coo_response(api_key, user_request, memory, calendar_data, pending_events, current_location, image_context=None, chat_history=None):
    """
    The Timezone-Aware Brain.
    Fixes the 'Tomorrow' bug by forcing EST/New_York time.
    """
    client = Groq(api_key=api_key)
    
    # 1. TIMEZONE FIX (Critical)
    # Force 'Now' to be Tampa Time (EST/EDT), not Server Time (UTC)
    tz = pytz.timezone('America/New_York')
    now = datetime.datetime.now(tz)
    
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    # Generate Cheat Sheet relative to EST
    cheat_sheet = "REFERENCE DATES (Use these for 'Tomorrow' etc):\n"
    cheat_sheet += f"- TODAY ({now.strftime('%A')}): {now.strftime('%Y-%m-%d')}\n"
    for i in range(1, 8):
        d = now + datetime.timedelta(days=i)
        cheat_sheet += f"- {d.strftime('%A')} (+{i} days): {d.strftime('%Y-%m-%d')}\n"

    history_txt = ""
    if chat_history:
        history_txt = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-5:]])

    # 2. SYSTEM PROMPT
    system_prompt = f"""
    You are the Family COO. 
    CURRENT TIME (EST): {current_time_str}.
    
    {cheat_sheet}
    
    EXISTING CALENDAR (Busy Slots):
    {calendar_data}
    
    PENDING PLANS (Treat as Busy):
    {json.dumps(pending_events)}
    
    MEMORY BANK:
    {json.dumps(memory)}
    
    TASK: Analyze "{user_request}"
    
    CRITICAL RULES:
    1. **CHECK DATES:** Use the 'REFERENCE DATES' list. If user says "Tomorrow", use the date listed for +1 day. Do not guess.
    2. **CONFLICT DETECTION:** Compare requested time against 'EXISTING CALENDAR' and 'PENDING PLANS'.
       - If overlap: STOP. Return type "conflict".
       - Example: "⚠️ Conflict! You already have 'Judo' at 5:30 PM. Shall we try 6:30 PM?"
    3. **SMART SUGGESTIONS:** If a conflict exists, look for the nearest empty gap and suggest it.
    4. **OUTPUT JSON:** Return ONLY JSON.
    
    FORMAT EXAMPLES:
    {{ "type": "question", "text": "Which location?" }}
    
    {{ "type": "plan", "text": "Scheduled for tomorrow (Friday).", "pre_prep": "Pack bag.", "events": [ {{ "title": "Visit", "start_time": "2026-02-13T12:00:00", "location": "Tampa" }} ] }}
    
    {{ "type": "conflict", "text": "⚠️ Conflict! You are busy with 'Judo' then. \n\n💡 Suggestion: 2:00 PM is free. Should I book that?" }}
    """

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # 3. EXECUTE
    if image_context:
        model = "llama-3.2-90b-vision-preview"
        base64_image = encode_image(image_context)
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_request},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        })
    else:
        model = "llama-3.3-70b-versatile" 
        messages.append({"role": "user", "content": user_request})

    try:
        completion = client.chat.completions.create(
            model=model, messages=messages, temperature=0.6, max_tokens=1024, stream=False
        )
        text = completion.choices[0].message.content
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match: return match.group(1)
        return text

    except Exception as e:
        return f'{{"type": "error", "text": "Groq Error: {str(e)}"}}'