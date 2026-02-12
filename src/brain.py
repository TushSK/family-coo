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
    The 'Manager' Brain.
    Supports ID tracking for deleting events and formatted Markdown outputs.
    """
    client = Groq(api_key=api_key)
    
    now = datetime.datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y")
    
    cheat_sheet = "UPCOMING DATES:\n"
    for i in range(0, 8):
        d = now + datetime.timedelta(days=i)
        cheat_sheet += f"- {d.strftime('%A')}: {d.strftime('%Y-%m-%d')}\n"

    history_txt = ""
    if chat_history:
        history_txt = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-10:]])

    system_prompt = f"""
    You are the Family COO. TODAY: {current_time_str}.
    
    {cheat_sheet}
    
    CALENDAR DATA (With IDs):
    {calendar_data}
    
    ACTIVE PROPOSALS:
    {json.dumps(pending_events)}
    
    HISTORY:
    {history_txt}
    
    TASK: Analyze "{user_request}"
    
    RULES:
    1. **FORMATTING:** Use Markdown for the 'text' field. Use bullet points for lists. Make it clean and readable.
    2. **REVIEWING EVENTS:** If the user asks to review/check pending or past events:
       - List them in the 'events' JSON array.
       - **CRITICAL:** Include the 'id' field from the CALENDAR DATA so the App can provide a "Mark as Done" button.
       
    3. **CREATING EVENTS:** If creating new plans, do NOT include an 'id' field.
    
    4. **CONFLICTS:** Check for overlaps.
    
    OUTPUT JSON EXAMPLES:
    
    (Reviewing Past):
    {{
      "type": "review",
      "text": "### 📋 Pending Activities\\nI found these events from the last few days:\\n* **Judo** (Yesterday)\\n* **Beach** (Saturday)\\n\\nMark them as done below if completed.",
      "events": [
        {{ "title": "Judo", "start_time": "...", "location": "...", "id": "12345_from_calendar_data" }},
        {{ "title": "Beach", "start_time": "...", "location": "...", "id": "67890_from_calendar_data" }}
      ]
    }}
    
    (Creating New):
    {{
      "type": "plan",
      "text": "### ✅ Plan Ready\\nI have scheduled the movie.",
      "pre_prep": "Buy tickets online.",
      "events": [ {{ "title": "Movie", "start_time": "2026-02-14T11:00:00", "location": "Cinema" }} ]
    }}
    """

    messages = [{"role": "system", "content": system_prompt}]

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
        return completion.choices[0].message.content
    except Exception as e:
        return f'{{"type": "error", "text": "Groq Error: {str(e)}"}}'