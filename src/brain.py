import os
import json
import datetime
import base64
import re
from groq import Groq

def encode_image(image):
    import io
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_coo_response(api_key, user_request, memory, calendar_data, pending_events, current_location, image_context=None, chat_history=None):
    """
    The Conflict-Aware Brain.
    Now checks 'pending_events' (plans from this session not yet saved) to prevent double-booking.
    """
    client = Groq(api_key=api_key)
    
    # 1. TIME CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y")
    
    # Cheat sheet for next 7 days
    cheat_sheet = "UPCOMING DATES:\n"
    for i in range(0, 8):
        d = now + datetime.timedelta(days=i)
        cheat_sheet += f"- {d.strftime('%A')}: {d.strftime('%Y-%m-%d')}\n"

    history_txt = ""
    if chat_history:
        history_txt = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-5:]])

    # 2. SYSTEM PROMPT
    system_prompt = f"""
    You are the Family COO. TODAY: {current_time_str}.
    
    {cheat_sheet}
    
    REAL CALENDAR (Confirmed):
    {calendar_data}
    
    PENDING PLANS (Just discussed, treat as busy):
    {json.dumps(pending_events)}
    
    MEMORY BANK:
    {json.dumps(memory)}
    
    TASK: Analyze "{user_request}"
    
    PROTOCOL:
    1. **CONFLICT CHECK:** You MUST compare the request against BOTH 'REAL CALENDAR' and 'PENDING PLANS'.
       - If overlap found: STOP. Use type "conflict". Suggest an alternative time.
    2. **SMART SCHEDULING:** If user says "This Weekend", check Saturday AND Sunday. Pick the empty slot.
    3. **OUTPUT JSON:** Return ONLY JSON.
    
    FORMAT EXAMPLES:
    {{ "type": "question", "text": "Which location?" }}
    
    {{ "type": "plan", "text": "Scheduled.", "pre_prep": "Pack water.", "events": [ {{ "title": "Judo", "start_time": "...", "location": "..." }} ] }}
    
    {{ "type": "conflict", "text": "⚠️ Conflict! You already have 'Beach Visit' planned for Saturday at 11 AM. \n\n💡 Suggestion: How about Sunday at 11 AM instead?" }}
    """

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # 3. PAYLOAD
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

    # 4. EXECUTE
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