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

def get_coo_response(api_key, user_request, memory, calendar_data, current_location, image_context=None, chat_history=None):
    """
    The Polished Groq Brain.
    Now includes 'pre_prep' instructions for events.
    """
    client = Groq(api_key=api_key)
    
    # 1. SETUP CONTEXT
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    history_txt = ""
    if chat_history:
        history_txt = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-5:]])

    # 2. SYSTEM PROMPT
    system_prompt = f"""
    You are the Family COO. Current time: {current_time_str}. Location: {current_location}.
    
    MEMORY BANK:
    {json.dumps(memory)}
    
    CALENDAR CONSTRAINTS:
    {calendar_data}
    
    HISTORY:
    {history_txt}
    
    TASK:
    Analyze request: "{user_request}"
    
    RULES:
    1. **PRE-PREP:** For every plan, include a 'pre_prep' field with 1-2 short, actionable preparation steps (e.g., "Wash Judo Gi," "Print tickets," "Pack water bottle").
    2. **DUPLICATES:** If event exists, use type 'confirmation'.
    3. **OUTPUT JSON:** Return ONLY a JSON object.
    
    FORMAT EXAMPLES:
    {{ "type": "question", "text": "Which location?" }}
    
    {{ 
      "type": "plan", 
      "text": "I've scheduled the swimming class.", 
      "pre_prep": "💡 Prep: Pack swim cap, goggles, and a towel. Don't forget sunscreen.",
      "events": [ {{ "title": "Swim Class", "start_time": "2026-02-26T16:00:00", "location": "Loretta Pool" }} ] 
    }}
    
    {{ "type": "confirmation", "text": "You already have that scheduled." }}
    """

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # 3. CONTENT PAYLOAD
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
            model=model,
            messages=messages,
            temperature=0.6,
            max_tokens=1024,
            stream=False
        )
        
        text = completion.choices[0].message.content
        
        # 5. CLEANUP
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match: return match.group(1)
        return text

    except Exception as e:
        return f'{{"type": "error", "text": "Groq Error: {str(e)}"}}'