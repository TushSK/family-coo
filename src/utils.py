import json
import os

MEMORY_FILE = "memory/feedback_log.json"

def init_memory():
    """Ensures the memory directory and file exist."""
    if not os.path.exists("memory"):
        os.makedirs("memory")
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w") as f:
            json.dump([], f)

def load_memory(limit=5):
    """Loads the last N feedback items to give the AI context."""
    init_memory()
    try:
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
            # Return the last 'limit' items (most recent)
            return data[-limit:]
    except:
        return []

def save_feedback(mission, plan_summary, user_feedback, rating):
    """Saves new learnings to the long-term memory."""
    init_memory()
    
    new_entry = {
        "mission": mission,
        "feedback": user_feedback,
        "rating": rating, # "👍" or "👎"
        "timestamp": "Just now"
    }
    
    # Load existing, append new, save back
    try:
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
    except:
        data = []
        
    data.append(new_entry)
    
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)