import json
import os
import datetime
import uuid

MEMORY_FILE = "memory/feedback_log.json"
MISSION_FILE = "memory/mission_log.json"

def init_files():
    """Ensures memory files exist."""
    if not os.path.exists("memory"):
        os.makedirs("memory")
    for fpath in [MEMORY_FILE, MISSION_FILE]:
        if not os.path.exists(fpath):
            with open(fpath, "w") as f:
                json.dump([], f)

def load_memory(limit=10):
    """Loads actionable learnings for the Brain."""
    init_files()
    try:
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
        return data[-limit:] 
    except:
        return []

def log_mission_start(event_data):
    """Logs a mission so we can check on it later."""
    init_files()
    new_mission = {
        "id": str(uuid.uuid4())[:8],
        "title": event_data.get('title', 'Event'),
        "end_time": event_data.get('end_time'), 
        "status": "pending",
        "snoozed_until": None 
    }
    
    try:
        with open(MISSION_FILE, "r") as f:
            data = json.load(f)
    except:
        data = []
        
    data.append(new_mission)
    with open(MISSION_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_pending_review():
    """Finds ONE past event that needs feedback and isn't snoozed."""
    init_files()
    try:
        with open(MISSION_FILE, "r") as f:
            data = json.load(f)
        
        now = datetime.datetime.now().isoformat()
        
        # Sort by end_time so we ask about the oldest unfinished task first
        data.sort(key=lambda x: x.get('end_time', ''))

        for mission in data:
            if mission['status'] == 'pending':
                # Check if event is actually over
                if mission.get('end_time') and mission['end_time'] < now:
                    # Check if snoozed
                    snooze_time = mission.get('snoozed_until')
                    if not snooze_time or snooze_time < now:
                        return mission
    except:
        return None
    return None

def snooze_mission(mission_id, hours=4):
    """Snoozes a mission so it doesn't annoy the user."""
    init_files()
    try:
        with open(MISSION_FILE, "r") as f:
            missions = json.load(f)
    except:
        return

    wake_time = (datetime.datetime.now() + datetime.timedelta(hours=hours)).isoformat()
    
    for m in missions:
        if m['id'] == mission_id:
            m['snoozed_until'] = wake_time
            break
            
    with open(MISSION_FILE, "w") as f:
        json.dump(missions, f, indent=4)

def complete_mission_review(mission_id, was_completed, reason):
    """Saves the feedback and closes the mission."""
    init_files()
    
    # 1. Update Mission Log
    try:
        with open(MISSION_FILE, "r") as f:
            missions = json.load(f)
    except:
        missions = []

    mission_title = "Unknown Mission"
    for m in missions:
        if m['id'] == mission_id:
            m['status'] = 'reviewed'
            mission_title = m['title']
            break
            
    with open(MISSION_FILE, "w") as f:
        json.dump(missions, f, indent=4)
        
    # 2. Update Brain Memory
    learning_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d"),
        "mission": mission_title,
        "feedback": f"User {'completed' if was_completed else 'skipped'} this. Reason: {reason}",
        "rating": "👍" if was_completed else "👎"
    }
    
    try:
        with open(MEMORY_FILE, "r") as f:
            memories = json.load(f)
    except:
        memories = []
        
    memories.append(learning_entry)
    with open(MEMORY_FILE, "w") as f:
        json.dump(memories, f, indent=4)
        
def save_manual_feedback(topic, feedback, rating):
    """For manual corrections."""
    init_files()
    entry = {
        "timestamp": "Manual", 
        "mission": topic, 
        "feedback": feedback, 
        "rating": rating
    }
    
    try:
        with open(MEMORY_FILE, "r") as f:
            d = json.load(f)
    except:
        d = []
    
    d.append(entry)
    with open(MEMORY_FILE, "w") as f:
        json.dump(d, f, indent=4)